"""The AI gateway — the single chokepoint every task-shaped AI call in the
system must go through (NON_NEGOTIABLES #8). Implements §7.2 model routing,
§7.3's schema validation, and §7.5's failure behavior. No caller outside
`app/ai/` may import a provider SDK or construct a `GenerationResult`
except by calling `AiGateway.run_task`.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum

from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from app.ai.budget import is_over_monthly_budget, record_call
from app.ai.contracts import GenerationResult
from app.ai.providers.base import Provider, ProviderUnavailableError
from app.ai.providers.null_provider import NullProvider
from app.ai.tasks import DEGRADABLE_ON_BUDGET_BREACH, ROUTING, Task

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


@dataclass
class GatewayOutcome:
    status: GatewayStatus
    result: BaseModel | None = None
    removed_claims: list[str] = field(default_factory=list)


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


class AiGateway:
    def __init__(self, db: Session):
        self._db = db

    def run_task(
        self,
        task: Task,
        prompt: str,
        *,
        story_id: uuid.UUID | None = None,
        result_model: type[BaseModel] = GenerationResult,
        evidence_item_ids: frozenset[str] | None = None,
    ) -> GatewayOutcome:
        route = ROUTING[task]

        if route.provider is None:
            raise ValueError(f"{task} has no provider route — call the deterministic helper instead")

        if task in DEGRADABLE_ON_BUDGET_BREACH and is_over_monthly_budget(self._db):
            return GatewayOutcome(status=GatewayStatus.CLASSIFICATION_ONLY)

        provider = _resolve_provider(route.provider)
        model = route.default_model

        try:
            response = provider.complete(model=model, task=task, prompt=prompt)
        except ProviderUnavailableError:
            return GatewayOutcome(status=GatewayStatus.UNAVAILABLE)

        try:
            result = result_model.model_validate(response.output)
            record_call(
                self._db, task=task, provider=provider.name, model=model, status="SUCCESS",
                tokens_in=response.tokens_in, tokens_out=response.tokens_out, story_id=story_id,
            )
        except ValidationError:
            record_call(
                self._db, task=task, provider=provider.name, model=model, status="HOLD",
                tokens_in=response.tokens_in, tokens_out=response.tokens_out, story_id=story_id,
            )
            # §7.5: retry once with a constrained prompt.
            try:
                retry_response = provider.complete(model=model, task=task, prompt=prompt, constrained=True)
            except ProviderUnavailableError:
                return GatewayOutcome(status=GatewayStatus.UNAVAILABLE)
            try:
                result = result_model.model_validate(retry_response.output)
                record_call(
                    self._db, task=task, provider=provider.name, model=model, status="RETRY_SUCCESS",
                    tokens_in=retry_response.tokens_in, tokens_out=retry_response.tokens_out, story_id=story_id,
                )
            except ValidationError:
                record_call(
                    self._db, task=task, provider=provider.name, model=model, status="HOLD",
                    tokens_in=retry_response.tokens_in, tokens_out=retry_response.tokens_out, story_id=story_id,
                )
                return GatewayOutcome(status=GatewayStatus.HOLD)

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
