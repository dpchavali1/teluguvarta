"""The AI gateway — the single chokepoint every task-shaped AI call in the
system must go through (NON_NEGOTIABLES #8). Implements §7.2 model routing,
§7.3's schema validation, and §7.5's failure behavior. No caller outside
`app/ai/` may import a provider SDK or construct a `GenerationResult`
except by calling `AiGateway.run_task`.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from enum import Enum

from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from app.ai.budget import is_over_hard_cap, is_over_monthly_budget, record_call
from app.ai.contracts import GenerationResult
from app.ai.privacy import PrivacyDecision, coerce
from app.ai.providers.base import (
    Provider,
    ProviderQuotaError,
    ProviderResponse,
    ProviderUnavailableError,
)
from app.ai.providers.null_provider import NullProvider
from app.ai.ratelimit import acquire, has_limits
from app.ai.tasks import (
    DEGRADABLE_ON_BUDGET_BREACH,
    Task,
    pricing_for,
    route_for,
)
from app.observability.logging import get_logger
from app.switches import ai_paused

logger = get_logger("ai.gateway")

# §7.5: "low confidence -> review queue." Below this, a syntactically valid
# result still isn't trusted enough to auto-publish. Only applies to
# `GenerationResult`-shaped tasks — a translation carries no confidence of
# its own (see `run_task`'s `result_model` param).
CONFIDENCE_REVIEW_THRESHOLD = 0.5


class GatewayStatus(str, Enum):
    OK = "OK"
    HOLD = "HOLD"
    REVIEW_QUEUE = "REVIEW_QUEUE"
    UNAVAILABLE = "UNAVAILABLE"
    CLASSIFICATION_ONLY = "CLASSIFICATION_ONLY"
    # ADR-015: free-tier quota or a provider 429. A deferral, not a failure.
    DEFERRED = "DEFERRED"


@dataclass
class GatewayOutcome:
    status: GatewayStatus
    result: BaseModel | None = None
    removed_claims: list[str] = field(default_factory=list)


class FreeTierViolation(RuntimeError):
    """A dispatch to the Gemini free tier that ADR-015 forbids. Raised, never
    logged-and-continued: a violation is a bug, not a runtime condition."""


def _resolve_provider(name: str | None) -> Provider:
    if name == "openai":
        try:
            from app.ai.providers.openai_provider import OpenAiProvider

            return OpenAiProvider()
        except ProviderUnavailableError:
            return NullProvider()
    if name == "anthropic":
        try:
            from app.ai.providers.anthropic_provider import AnthropicProvider

            return AnthropicProvider()
        except ProviderUnavailableError:
            return NullProvider()
    if name == "gemini":
        try:
            from app.ai.providers.gemini_provider import GeminiProvider

            return GeminiProvider()
        except ProviderUnavailableError:
            return NullProvider()
    if name == "gemini_paid":
        try:
            from app.ai.providers.gemini_provider import PaidGeminiProvider

            return PaidGeminiProvider()
        except ProviderUnavailableError:
            return NullProvider()
    return NullProvider()


def _check_claims(
    result: GenerationResult, evidence_item_ids: frozenset[str] | None
) -> tuple[GenerationResult, list[str], bool]:
    """P0-1: a claim with no `source_refs` is stripped silently, same as
    before — the model gave no evidence, which is honest. A claim whose
    `source_refs` name something other than a real evidence item in this
    cluster is a *fabrication* — a crafted feed title injecting a fake
    `source_ref=` line, or the model hallucinating one — and must never be
    silently stripped-and-published; the caller HOLDs the whole result.
    `evidence_item_ids` is the caller's set of real item ids for this call;
    `None` means the caller didn't supply one (no `SourceItem` cluster to
    check against), in which case membership can't be checked and only the
    empty-refs strip applies, same as before P0-1.
    """
    kept = []
    removed: list[str] = []
    fabricated = False
    for claim in result.claims:
        if not claim.source_refs:
            removed.append(claim.text)
            continue
        if evidence_item_ids is not None and any(ref not in evidence_item_ids for ref in claim.source_refs):
            fabricated = True
            continue
        kept.append(claim)
    if removed or fabricated:
        result = result.model_copy(update={"claims": kept})
    return result, removed, fabricated


def _with_output_contract(prompt: str, result_model: type[BaseModel]) -> str:
    """Append the result model's JSON Schema. The task prompts only describe
    the content, so without this a real model picks its own key names and
    every call fails schema validation (prod, 2026-09-30)."""
    schema = json.dumps(result_model.model_json_schema(), ensure_ascii=False)
    return (
        f"{prompt}\n\nRespond with one JSON object that conforms to this JSON Schema, "
        f"using exactly these property names:\n{schema}"
    )


class AiGateway:
    def __init__(self, db: Session):
        self._db = db

    @staticmethod
    def _guard_free_tier(story_id, privacy_decision, editor_authored: bool) -> None:
        if editor_authored:
            raise FreeTierViolation("editor-authored text never goes to the free tier")
        if story_id is None:
            raise FreeTierViolation("free-tier dispatch requires a story with a recorded privacy decision")
        if coerce(getattr(privacy_decision, "value", privacy_decision)) != PrivacyDecision.FREE_TIER_ALLOWED:
            raise FreeTierViolation("story is not FREE_TIER_ALLOWED")

    def run_task(
        self,
        task: Task,
        prompt: str,
        *,
        story_id: uuid.UUID | None = None,
        result_model: type[BaseModel] = GenerationResult,
        evidence_item_ids: frozenset[str] | None = None,
        privacy_decision: PrivacyDecision | str | None = None,
        editor_authored: bool = False,
    ) -> GatewayOutcome:
        route = route_for(
            task,
            free_tier_allowed=(
                not editor_authored
                and story_id is not None
                and coerce(getattr(privacy_decision, "value", privacy_decision)) == PrivacyDecision.FREE_TIER_ALLOWED
            ),
        )

        if route.provider is None:
            raise ValueError(f"{task} has no provider route — call the deterministic helper instead")

        # ADR-031: an admin paused AI from the dashboard. A deferral, so the
        # caller retries after resume; the worker already stops claiming AI
        # jobs, this covers AI calls made inside other jobs.
        if ai_paused(self._db):
            return GatewayOutcome(status=GatewayStatus.DEFERRED)

        if task in DEGRADABLE_ON_BUDGET_BREACH and is_over_monthly_budget(self._db):
            return GatewayOutcome(status=GatewayStatus.CLASSIFICATION_ONLY)

        # ADR-024: past the hard cap no paid call runs, classification
        # included. UNAVAILABLE is transient, so the story waits under
        # review #1's backoff. Nothing is logged: no call was made, and the
        # budget alert already reports the crossing.
        paid = route.provider != "gemini"
        if paid and is_over_hard_cap(self._db):
            logger.warning("monthly AI hard cap reached; refusing paid %s call", task.value)
            return GatewayOutcome(status=GatewayStatus.UNAVAILABLE)

        if route.default_model is None:
            logger.error("provider route %s has no model; refusing %s", route.provider, task.value)
            record_call(self._db, task=task, provider=route.provider, model=None,
                        status="UNAVAILABLE", story_id=story_id)
            return GatewayOutcome(status=GatewayStatus.UNAVAILABLE)

        # ADR-018 decisions 5 and 7: a paid call that can't be priced, or that
        # names a moving alias, would slip past the budget gate. Refuse it.
        if route.provider == "gemini_paid" and (
            route.default_model is None
            or route.default_model.endswith("-latest")
            or pricing_for(route.provider, route.default_model) is None
        ):
            record_call(
                self._db, task=task, provider="gemini_paid", model=route.default_model,
                status="UNAVAILABLE", story_id=story_id,
            )
            return GatewayOutcome(status=GatewayStatus.UNAVAILABLE)

        if route.provider == "gemini":
            self._guard_free_tier(story_id, privacy_decision, editor_authored)
            # A model with no FREE_TIER_LIMITS entry (e.g. a pinned id set via
            # AI_GEMINI_*_MODEL) can never run. That's misconfiguration, not a
            # quota wait, so record it as UNAVAILABLE for the alert to catch.
            if not has_limits(route.default_model):
                logger.error("free-tier model %r has no FREE_TIER_LIMITS entry; refusing", route.default_model)
                record_call(
                    self._db, task=task, provider="gemini", model=route.default_model,
                    status="UNAVAILABLE", story_id=story_id,
                )
                return GatewayOutcome(status=GatewayStatus.UNAVAILABLE)
            if not acquire(self._db, route.default_model):
                record_call(
                    self._db, task=task, provider="gemini", model=route.default_model,
                    status="DEFERRED", story_id=story_id,
                )
                return GatewayOutcome(status=GatewayStatus.DEFERRED)

        provider = _resolve_provider(route.provider)
        model = route.default_model
        prompt = _with_output_contract(prompt, result_model)

        def _record(status: str, response: ProviderResponse | None = None) -> None:
            usage = {}
            if response is not None:
                usage = {
                    "tokens_in": response.tokens_in, "tokens_out": response.tokens_out,
                    "tokens_thinking": response.tokens_thinking, "tokens_cached": response.tokens_cached,
                }
            record_call(
                self._db, task=task, provider=provider.name, model=model, status=status, story_id=story_id, **usage
            )

        def _call(constrained: bool) -> ProviderResponse | GatewayOutcome:
            # Review 2026-09-29 #3: every provider failure is logged, so the
            # failure rate is visible. PROVIDER_ERROR, not UNAVAILABLE: the
            # refusal alert reads UNAVAILABLE as misconfiguration.
            try:
                return provider.complete(model=model, task=task, prompt=prompt, constrained=constrained)
            except ProviderQuotaError:
                _record("DEFERRED")
                return GatewayOutcome(status=GatewayStatus.DEFERRED)
            except ProviderUnavailableError:
                _record("PROVIDER_ERROR")
                return GatewayOutcome(status=GatewayStatus.UNAVAILABLE)

        response = _call(constrained=False)
        if isinstance(response, GatewayOutcome):
            return response

        def _validate(response: ProviderResponse) -> BaseModel | None:
            if response.failure:
                return None
            try:
                return result_model.model_validate(response.output)
            except ValidationError:
                return None

        result = _validate(response)
        if result is not None:
            _record("SUCCESS", response)
        else:
            # A malformed or blocked reply is still billed: log its usage.
            _record(response.failure or "HOLD", response)
            # ADR-024: the first call may have crossed the cap; re-check it
            # before paying for the retry.
            if paid and is_over_hard_cap(self._db):
                return GatewayOutcome(status=GatewayStatus.UNAVAILABLE)
            # §7.5: retry once with a constrained prompt.
            retry_response = _call(constrained=True)
            if isinstance(retry_response, GatewayOutcome):
                return retry_response
            result = _validate(retry_response)
            if result is None:
                _record(retry_response.failure or "HOLD", retry_response)
                return GatewayOutcome(status=GatewayStatus.HOLD)
            _record("RETRY_SUCCESS", retry_response)

        # §7.2: sensitive validation always goes to human review in V1,
        # regardless of confidence.
        if route.always_human_review:
            return GatewayOutcome(status=GatewayStatus.REVIEW_QUEUE, result=result)

        # Confidence-threshold review and unsupported-claim stripping are
        # `GenerationResult`-specific (it's the only contract carrying a
        # `confidence`/`claims` shape) — a `TranslationResult` (or any future
        # non-generation contract) has nothing to check here and returns OK
        # once it parses, same as sensitive-validation's own result shape
        # already skips this via `always_human_review` above.
        if isinstance(result, GenerationResult):
            if result.confidence < CONFIDENCE_REVIEW_THRESHOLD:
                return GatewayOutcome(status=GatewayStatus.REVIEW_QUEUE, result=result)

            result, removed, fabricated = _check_claims(result, evidence_item_ids)
            if fabricated:
                # A claim cited a source_ref that names no real evidence
                # item — a fabrication, not an honest "no evidence given."
                # Never silently strip and publish on this; hold the whole
                # result for retry/investigation instead (P0-1).
                return GatewayOutcome(status=GatewayStatus.HOLD, removed_claims=removed)
            if removed and not result.claims:
                # Every claim was unsupported — nothing left to publish on.
                return GatewayOutcome(status=GatewayStatus.HOLD, removed_claims=removed)

            return GatewayOutcome(status=GatewayStatus.OK, result=result, removed_claims=removed)

        return GatewayOutcome(status=GatewayStatus.OK, result=result)
