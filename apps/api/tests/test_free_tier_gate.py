"""T22 / ADR-015: privacy pre-classifier, rate limiter, request counter, and the
gateway's free-tier guard."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.ai import gateway as gateway_module
from app.ai import ratelimit
from app.ai.budget import record_call
from app.ai.gateway import AiGateway, FreeTierViolation, GatewayStatus
from app.ai.privacy import PrivacyDecision, classify_privacy, coerce, tighten
from app.ai.providers.base import ProviderQuotaError
from app.ai.ratelimit import TokenBucket
from app.ai.tasks import GEMINI_FLASH_LITE, ROUTING, Task, TaskRoute
from app.models import AiCallLog

from .conftest import requires_postgres

ALLOWED = PrivacyDecision.FREE_TIER_ALLOWED


# --- pre-classifier (unit) --------------------------------------------------


@pytest.mark.parametrize("category", ["entertainment", "sports", "community_events", " Sports "])
def test_allowlisted_category_without_signal_is_allowed(category):
    assert classify_privacy(category, "Local team wins derby") == ALLOWED


@pytest.mark.parametrize("category", [None, "", "politics", "immigration", "money", "students"])
def test_missing_or_unlisted_category_is_unknown(category):
    assert classify_privacy(category, "Local team wins derby") == PrivacyDecision.UNKNOWN


def test_restricted_signal_beats_allowlisted_category():
    assert classify_privacy("sports", "Star player fights H-1B visa delay") == PrivacyDecision.RESTRICTED
    assert classify_privacy("entertainment", "Actor arrested", None) == PrivacyDecision.RESTRICTED


def test_tighten_never_loosens():
    assert tighten(PrivacyDecision.UNKNOWN, ALLOWED) == PrivacyDecision.UNKNOWN
    assert tighten(PrivacyDecision.RESTRICTED, ALLOWED) == PrivacyDecision.RESTRICTED
    assert tighten(ALLOWED, PrivacyDecision.UNKNOWN) == PrivacyDecision.UNKNOWN
    assert tighten(PrivacyDecision.UNKNOWN, PrivacyDecision.RESTRICTED) == PrivacyDecision.RESTRICTED


def test_coerce_fails_closed():
    assert coerce(None) == PrivacyDecision.UNKNOWN
    assert coerce("garbage") == PrivacyDecision.UNKNOWN
    assert coerce("FREE_TIER_ALLOWED") == ALLOWED


# --- token bucket (unit) ----------------------------------------------------


def test_bucket_refuses_above_rpm_then_refills():
    now = [0.0]
    bucket = TokenBucket(rpm=5, clock=lambda: now[0])
    assert [bucket.try_acquire() for _ in range(6)] == [True] * 5 + [False]
    now[0] += 12.0  # 5 rpm -> one token per 12s
    assert bucket.try_acquire() is True
    assert bucket.try_acquire() is False


def test_unknown_model_is_refused():
    assert ratelimit.acquire(None, "gemini-mystery") is False


def test_routing_still_has_no_gemini_route():
    assert all(r.provider != "gemini" for r in ROUTING.values())


# --- gateway guard and counter (Postgres) ------------------------------------


class _Boom:
    name = "gemini"

    def __init__(self, exc=None):
        self.calls = 0
        self._exc = exc

    def complete(self, **kwargs):
        self.calls += 1
        if self._exc:
            raise self._exc
        raise AssertionError("should not be reached in these tests")


def _route_gemini(monkeypatch, provider):
    route = TaskRoute(provider="gemini", default_model=GEMINI_FLASH_LITE)
    monkeypatch.setitem(ROUTING, Task.SUMMARY, route)
    monkeypatch.setattr(gateway_module, "_resolve_provider", lambda name: provider)
    monkeypatch.setattr(ratelimit, "_buckets", {})


@requires_postgres
@pytest.mark.parametrize(
    "kwargs",
    [
        {"story_id": None, "privacy_decision": ALLOWED},
        {"story_id": uuid.uuid4(), "privacy_decision": PrivacyDecision.UNKNOWN},
        {"story_id": uuid.uuid4(), "privacy_decision": PrivacyDecision.RESTRICTED},
        {"story_id": uuid.uuid4(), "privacy_decision": None},
        {"story_id": uuid.uuid4(), "privacy_decision": ALLOWED, "editor_authored": True},
    ],
)
def test_gemini_dispatch_without_clearance_raises_and_never_calls(migrated_database, monkeypatch, kwargs):
    provider = _Boom()
    _route_gemini(monkeypatch, provider)
    with Session(create_engine(migrated_database)) as db, pytest.raises(FreeTierViolation):
        AiGateway(db).run_task(Task.SUMMARY, "x", **kwargs)
    assert provider.calls == 0


@requires_postgres
def test_provider_429_is_a_recorded_deferral(migrated_database, monkeypatch):
    provider = _Boom(ProviderQuotaError("429"))
    _route_gemini(monkeypatch, provider)
    with Session(create_engine(migrated_database)) as db:
        outcome = AiGateway(db).run_task(Task.SUMMARY, "x", story_id=None or _story(db), privacy_decision=ALLOWED)
        assert outcome.status == GatewayStatus.DEFERRED
        assert [r.status for r in db.query(AiCallLog).all()] == ["DEFERRED"]


@requires_postgres
def test_rpd_exhaustion_defers_without_calling_provider(migrated_database, monkeypatch):
    provider = _Boom()
    _route_gemini(monkeypatch, provider)
    monkeypatch.setitem(ratelimit.FREE_TIER_LIMITS, GEMINI_FLASH_LITE, ratelimit.Limits(rpm=15, rpd=2))
    with Session(create_engine(migrated_database)) as db:
        for status in ("SUCCESS", "UNAVAILABLE"):  # unavailable attempts still count
            record_call(db, task=Task.SUMMARY, provider="gemini", model=GEMINI_FLASH_LITE, status=status)
        outcome = AiGateway(db).run_task(Task.SUMMARY, "x", story_id=_story(db), privacy_decision=ALLOWED)
        assert outcome.status == GatewayStatus.DEFERRED
    assert provider.calls == 0


@requires_postgres
def test_free_tier_model_without_limits_is_unavailable_not_deferred(migrated_database, monkeypatch):
    provider = _Boom()
    monkeypatch.setitem(ROUTING, Task.SUMMARY, TaskRoute(provider="gemini", default_model="gemini-9.9-flash"))
    monkeypatch.setattr(gateway_module, "_resolve_provider", lambda name: provider)
    with Session(create_engine(migrated_database)) as db:
        outcome = AiGateway(db).run_task(Task.SUMMARY, "x", story_id=_story(db), privacy_decision=ALLOWED)
        assert outcome.status == GatewayStatus.UNAVAILABLE
        assert [(r.status, r.model) for r in db.query(AiCallLog).all()] == [("UNAVAILABLE", "gemini-9.9-flash")]
    assert provider.calls == 0


@requires_postgres
def test_requests_today_counts_pacific_day_and_model_only(migrated_database):
    now = datetime(2026, 9, 28, 20, tzinfo=UTC)  # Pacific day began 07:00 UTC
    with Session(create_engine(migrated_database)) as db:
        for created, model in [
            (now - timedelta(hours=1), GEMINI_FLASH_LITE),
            (now - timedelta(hours=12), GEMINI_FLASH_LITE),  # 08:00 UTC, same Pacific day
            (now - timedelta(hours=14), GEMINI_FLASH_LITE),  # 06:00 UTC, previous Pacific day
            (now - timedelta(hours=1), "gemini-flash-latest"),  # other model
        ]:
            row = record_call(db, task=Task.SUMMARY, provider="gemini", model=model, status="SUCCESS")
            row.created_at = created
        db.commit()
        assert ratelimit.requests_today(db, GEMINI_FLASH_LITE, now) == 2


def _story(db):
    from app.models import Story

    story = Story(canonical_slug=f"s-{uuid.uuid4()}")
    db.add(story)
    db.commit()
    return story.id
