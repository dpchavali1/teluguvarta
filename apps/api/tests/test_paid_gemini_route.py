"""ADR-018: the paid Gemini route — selection, pricing, and the gateway's
fail-closed checks."""

import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.ai import gateway as gateway_module
from app.ai.gateway import AiGateway, GatewayStatus, _resolve_provider
from app.ai.privacy import PrivacyDecision
from app.ai.providers.base import ProviderResponse
from app.ai.providers.gemini_provider import PaidGeminiProvider
from app.ai.providers.null_provider import NullProvider
from app.ai.tasks import (
    FREE_TIER_ROUTING,
    PAID_GEMINI_ROUTING,
    ROUTING,
    Task,
    TaskRoute,
    cost_usd,
    paid_provider_configured,
    route_for,
)
from app.models import AiCallLog

from .conftest import requires_postgres

KEYS = ("AI_OPENAI_API_KEY", "AI_ANTHROPIC_API_KEY", "AI_GEMINI_PAID_API_KEY", "AI_FREE_TIER_ENABLED")


@pytest.fixture
def env(monkeypatch):
    for key in KEYS:
        monkeypatch.delenv(key, raising=False)
    return monkeypatch


# --- selection (unit) --------------------------------------------------------


def test_paid_key_alone_counts_as_paid_provider(env):
    assert not paid_provider_configured()
    env.setenv("AI_GEMINI_PAID_API_KEY", "k")
    assert paid_provider_configured()


def test_paid_gemini_used_when_no_adr001_key(env):
    env.setenv("AI_GEMINI_PAID_API_KEY", "k")
    assert route_for(Task.SUMMARY, free_tier_allowed=False) == PAID_GEMINI_ROUTING[Task.SUMMARY]
    assert route_for(Task.SENSITIVE_VALIDATION, free_tier_allowed=False).always_human_review


def test_adr001_key_wins_over_paid_gemini(env):
    env.setenv("AI_GEMINI_PAID_API_KEY", "k")
    env.setenv("AI_OPENAI_API_KEY", "k")
    assert route_for(Task.SUMMARY, free_tier_allowed=False) == ROUTING[Task.SUMMARY]


def test_free_tier_still_first_for_allowed_story(env):
    env.setenv("AI_GEMINI_PAID_API_KEY", "k")
    env.setenv("AI_FREE_TIER_ENABLED", "1")
    assert route_for(Task.SUMMARY, free_tier_allowed=True) == FREE_TIER_ROUTING[Task.SUMMARY]
    assert route_for(Task.SUMMARY, free_tier_allowed=False) == PAID_GEMINI_ROUTING[Task.SUMMARY]


def test_dedup_embeddings_keep_their_route(env):
    env.setenv("AI_GEMINI_PAID_API_KEY", "k")
    assert route_for(Task.DEDUP_CLUSTER_ESCALATION, free_tier_allowed=False) == ROUTING[Task.DEDUP_CLUSTER_ESCALATION]


def test_paid_routes_use_pinned_models():
    for route in PAID_GEMINI_ROUTING.values():
        assert route.provider == "gemini_paid"
        assert not route.default_model.endswith("-latest")


# --- pricing (unit) ----------------------------------------------------------


def test_paid_calls_are_priced_free_calls_are_not():
    assert cost_usd("gemini-3.5-flash-lite", 1000, 1000, provider="gemini_paid") == pytest.approx(0.0028)
    assert cost_usd("gemini-flash-lite-latest", 1000, 1000, provider="gemini") == 0.0
    # A paid call on a free alias has no price, so the gateway refuses it.
    assert cost_usd("gemini-flash-lite-latest", 1000, 1000, provider="gemini_paid") == 0.0


def test_paid_provider_resolution(env):
    assert isinstance(_resolve_provider("gemini_paid"), NullProvider)
    env.setenv("AI_GEMINI_PAID_API_KEY", "k")
    provider = _resolve_provider("gemini_paid")
    assert isinstance(provider, PaidGeminiProvider)
    assert provider.name == "gemini_paid"


# --- gateway (Postgres) ------------------------------------------------------


class _Fake:
    name = "gemini_paid"

    def __init__(self):
        self.calls = 0

    def complete(self, **kwargs):
        self.calls += 1
        return ProviderResponse(output={"headline_te": "x", "summary_te": "y"}, tokens_in=1000, tokens_out=1000)


def _story(db):
    from app.models import Story

    story = Story(canonical_slug=f"s-{uuid.uuid4()}")
    db.add(story)
    db.commit()
    return story.id


@requires_postgres
@pytest.mark.parametrize("model", ["gemini-flash-lite-latest", "gemini-9.9-unpriced"])
def test_unpriced_or_alias_paid_model_is_refused(migrated_database, env, model):
    env.setenv("AI_GEMINI_PAID_API_KEY", "k")
    env.setitem(PAID_GEMINI_ROUTING, Task.TRANSLATION_EN_TE, TaskRoute(provider="gemini_paid", default_model=model))
    provider = _Fake()
    env.setattr(gateway_module, "_resolve_provider", lambda name: provider)
    with Session(create_engine(migrated_database)) as db:
        outcome = AiGateway(db).run_task(
            Task.TRANSLATION_EN_TE, "x", story_id=_story(db), privacy_decision=PrivacyDecision.UNKNOWN,
        )
        assert outcome.status == GatewayStatus.UNAVAILABLE
        assert [(r.provider, r.status) for r in db.query(AiCallLog).all()] == [("gemini_paid", "UNAVAILABLE")]
    assert provider.calls == 0


@requires_postgres
def test_unknown_story_goes_to_paid_route_and_is_priced(migrated_database, env):
    from app.ai.contracts import TranslationResult

    env.setenv("AI_GEMINI_PAID_API_KEY", "k")
    provider = _Fake()
    env.setattr(gateway_module, "_resolve_provider", lambda name: provider if name == "gemini_paid" else None)
    with Session(create_engine(migrated_database)) as db:
        AiGateway(db).run_task(
            Task.TRANSLATION_EN_TE, "x", story_id=_story(db), privacy_decision=PrivacyDecision.RESTRICTED,
            result_model=TranslationResult,
        )
        rows = db.query(AiCallLog).all()
        assert [r.provider for r in rows] == ["gemini_paid"]
        assert float(rows[0].cost_usd) == pytest.approx(0.0028)
    assert provider.calls >= 1
