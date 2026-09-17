"""T10 acceptance tests: AI gateway routing, §7.3 schema validation, and
every §7.5 failure mode, plus cost telemetry and the budget-breach degrade.
"""

from datetime import UTC, datetime

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.ai import budget
from app.ai import gateway as gateway_module
from app.ai.gateway import AiGateway, GatewayStatus
from app.ai.language import detect_language
from app.ai.providers.base import ProviderResponse
from app.ai.tasks import ROUTING, Task
from app.jobs.cluster import cluster_normalized_items
from app.models import AiCallLog, Source, SourceItem

from .conftest import requires_postgres


class FakeProvider:
    name = "fake"

    def __init__(self, responses):
        self._responses = list(responses)

    def complete(self, *, model, task, prompt, constrained=False):
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return ProviderResponse(output=item, tokens_in=100, tokens_out=50)


def _valid_payload(**overrides):
    base = {
        "relevant": True,
        "confidence": 0.9,
        "categories": ["politics"],
        "countries": ["US"],
        "entities": [],
        "sensitivity": "LOW",
        "urgency": "NORMAL",
        "headline_en": "Headline.",
        "summary_en": "Summary.",
        "why_matters_en": "Why this matters.",
        "claims": [{"text": "claim one", "source_refs": ["src-1"]}],
        "source_refs": ["src-1"],
        "publish_recommendation": "PUBLISH",
    }
    base.update(overrides)
    return base


def _use_fake_provider(monkeypatch, responses):
    provider = FakeProvider(responses)
    monkeypatch.setattr(gateway_module, "_resolve_provider", lambda name: provider)
    return provider


# --- routing table (unit, no DB) -------------------------------------------


def test_routing_table_covers_every_spec_task():
    assert set(ROUTING) == set(Task)


def test_translation_escalates_to_a_second_provider():
    route = ROUTING[Task.TRANSLATION_EN_TE]
    assert route.provider == "openai"
    assert route.escalation_provider == "anthropic"
    assert route.escalation_provider != route.provider


def test_sensitive_validation_always_requires_human_review():
    assert ROUTING[Task.SENSITIVE_VALIDATION].always_human_review is True


def test_language_detection_has_no_provider_route():
    assert ROUTING[Task.LANGUAGE_DETECTION].provider is None


# --- deterministic language detection (unit, no DB) -------------------------


def test_detect_language_telugu_script():
    assert detect_language("తెలుగు వార్తలు") == "te"


def test_detect_language_english():
    assert detect_language("Breaking news today") == "en"


def test_detect_language_empty_is_unknown():
    assert detect_language("   ") == "unknown"


# --- gateway behavior (requires Postgres — telemetry writes) ---------------


@requires_postgres
def test_successful_call_returns_ok_and_records_telemetry(migrated_database, monkeypatch):
    engine = create_engine(migrated_database)
    with Session(engine) as db:
        _use_fake_provider(monkeypatch, [_valid_payload()])
        outcome = AiGateway(db).run_task(Task.SUMMARY, "summarize this")

        assert outcome.status == GatewayStatus.OK
        assert outcome.result.summary_en == "Summary."

        rows = db.scalars(select(AiCallLog)).all()
        assert len(rows) == 1
        assert rows[0].status == "SUCCESS"
        assert rows[0].task == Task.SUMMARY.value
        assert rows[0].tokens_in == 100
        assert rows[0].cost_usd > 0


@requires_postgres
def test_schema_validation_failure_retries_then_succeeds(migrated_database, monkeypatch):
    engine = create_engine(migrated_database)
    with Session(engine) as db:
        _use_fake_provider(monkeypatch, [{"not": "valid"}, _valid_payload()])
        outcome = AiGateway(db).run_task(Task.SUMMARY, "summarize this")

        assert outcome.status == GatewayStatus.OK
        rows = db.scalars(select(AiCallLog).order_by(AiCallLog.created_at)).all()
        assert [r.status for r in rows] == ["HOLD", "RETRY_SUCCESS"]


@requires_postgres
def test_schema_validation_failure_retry_also_fails_holds(migrated_database, monkeypatch):
    engine = create_engine(migrated_database)
    with Session(engine) as db:
        _use_fake_provider(monkeypatch, [{"not": "valid"}, {"still": "not valid"}])
        outcome = AiGateway(db).run_task(Task.SUMMARY, "summarize this")

        assert outcome.status == GatewayStatus.HOLD
        rows = db.scalars(select(AiCallLog)).all()
        assert [r.status for r in rows] == ["HOLD", "HOLD"]


@requires_postgres
def test_low_confidence_goes_to_review_queue(migrated_database, monkeypatch):
    engine = create_engine(migrated_database)
    with Session(engine) as db:
        _use_fake_provider(monkeypatch, [_valid_payload(confidence=0.2)])
        outcome = AiGateway(db).run_task(Task.SUMMARY, "summarize this")
        assert outcome.status == GatewayStatus.REVIEW_QUEUE
        assert outcome.result is not None


@requires_postgres
def test_sensitive_validation_goes_to_review_queue_even_when_confident(migrated_database, monkeypatch):
    engine = create_engine(migrated_database)
    with Session(engine) as db:
        _use_fake_provider(monkeypatch, [_valid_payload(confidence=0.99)])
        outcome = AiGateway(db).run_task(Task.SENSITIVE_VALIDATION, "validate this")
        assert outcome.status == GatewayStatus.REVIEW_QUEUE


@requires_postgres
def test_unsupported_claim_is_removed_but_story_still_publishes(migrated_database, monkeypatch):
    engine = create_engine(migrated_database)
    with Session(engine) as db:
        payload = _valid_payload(
            claims=[
                {"text": "supported claim", "source_refs": ["src-1"]},
                {"text": "unsupported claim", "source_refs": []},
            ]
        )
        _use_fake_provider(monkeypatch, [payload])
        outcome = AiGateway(db).run_task(
            Task.SUMMARY, "summarize this", evidence_item_ids=frozenset({"src-1"})
        )

        assert outcome.status == GatewayStatus.OK
        assert outcome.removed_claims == ["unsupported claim"]
        assert [c.text for c in outcome.result.claims] == ["supported claim"]


@requires_postgres
def test_story_held_when_every_claim_is_unsupported(migrated_database, monkeypatch):
    engine = create_engine(migrated_database)
    with Session(engine) as db:
        payload = _valid_payload(claims=[{"text": "unsupported claim", "source_refs": []}])
        _use_fake_provider(monkeypatch, [payload])
        outcome = AiGateway(db).run_task(
            Task.SUMMARY, "summarize this", evidence_item_ids=frozenset({"src-1"})
        )

        assert outcome.status == GatewayStatus.HOLD
        assert outcome.removed_claims == ["unsupported claim"]


@requires_postgres
def test_fabricated_source_ref_holds_the_whole_result(migrated_database, monkeypatch):
    """P0-1: a claim citing a source_ref that names no real evidence item —
    e.g. one injected via an unescaped prompt field — must never be silently
    stripped and published. The whole result HOLDs instead."""
    engine = create_engine(migrated_database)
    with Session(engine) as db:
        payload = _valid_payload(
            claims=[
                {"text": "real claim", "source_refs": ["src-1"]},
                {"text": "fabricated claim", "source_refs": ["injected-fake-id"]},
            ]
        )
        _use_fake_provider(monkeypatch, [payload])
        outcome = AiGateway(db).run_task(
            Task.SUMMARY, "summarize this", evidence_item_ids=frozenset({"src-1"})
        )

        assert outcome.status == GatewayStatus.HOLD
        assert outcome.result is None


@requires_postgres
def test_no_evidence_item_ids_skips_membership_check(migrated_database, monkeypatch):
    """Callers that don't supply `evidence_item_ids` (no SourceItem cluster
    to check against) get the pre-P0-1 behavior: any non-empty source_refs
    is accepted. Only real callers with a cluster (T11's `generate.py`) get
    the fabrication check."""
    engine = create_engine(migrated_database)
    with Session(engine) as db:
        _use_fake_provider(monkeypatch, [_valid_payload()])
        outcome = AiGateway(db).run_task(Task.SUMMARY, "summarize this")

        assert outcome.status == GatewayStatus.OK


@requires_postgres
def test_provider_unavailable_never_invents_content(migrated_database, monkeypatch):
    """No API key is configured in this test env, so the real provider
    resolution path (not a mock) surfaces UNAVAILABLE."""
    engine = create_engine(migrated_database)
    with Session(engine) as db:
        monkeypatch.delenv("AI_OPENAI_API_KEY", raising=False)
        outcome = AiGateway(db).run_task(Task.SUMMARY, "summarize this")

        assert outcome.status == GatewayStatus.UNAVAILABLE
        assert outcome.result is None
        # Nothing was recorded — no provider call was ever made.
        assert db.scalars(select(AiCallLog)).all() == []


@requires_postgres
def test_cost_threshold_breach_degrades_to_classification_only(migrated_database, monkeypatch):
    engine = create_engine(migrated_database)
    with Session(engine) as db:
        monkeypatch.setenv("MONTHLY_AI_BUDGET_USD", "1.00")
        budget.record_call(
            db, task=Task.SUMMARY, provider="openai", model="gpt-4o-mini",
            status="SUCCESS", tokens_in=2_000_000, tokens_out=2_000_000,
        )
        assert budget.is_over_monthly_budget(db) is True

        provider = _use_fake_provider(monkeypatch, [_valid_payload()])
        outcome = AiGateway(db).run_task(Task.SUMMARY, "summarize this")

        assert outcome.status == GatewayStatus.CLASSIFICATION_ONLY
        assert outcome.result is None
        # The provider was never called — spend didn't continue.
        assert len(provider._responses) == 1
        # Relevance/categorization is not degradable — still runs normally.
        _use_fake_provider(monkeypatch, [_valid_payload()])
        relevance_outcome = AiGateway(db).run_task(Task.RELEVANCE_CATEGORIZATION, "classify this")
        assert relevance_outcome.status == GatewayStatus.OK


@requires_postgres
def test_cost_telemetry_queryable_per_task_and_day(migrated_database, monkeypatch):
    engine = create_engine(migrated_database)
    with Session(engine) as db:
        _use_fake_provider(monkeypatch, [_valid_payload()])
        AiGateway(db).run_task(Task.SUMMARY, "summarize this")

        rows = budget.cost_by_task_and_day(db, task=Task.SUMMARY)
        assert len(rows) == 1
        assert rows[0]["task"] == Task.SUMMARY.value
        assert rows[0]["tokens_in"] == 100
        assert rows[0]["cost_usd"] > 0


# --- T09 wiring: ambiguous-band pairs route through the gateway ------------


@requires_postgres
def test_ambiguous_pair_falls_back_to_no_match_without_a_provider(migrated_database):
    """Titles similar enough to land in the ambiguous band (between the two
    thresholds) escalate to the AI gateway; with no provider configured,
    that's UNAVAILABLE, so cluster.py conservatively keeps them separate."""
    engine = create_engine(migrated_database)
    with Session(engine) as db:
        source = Source(name="S", feed_url="https://example.org/feed.xml", rights_status="LINK_ONLY", active=True)
        db.add(source)
        db.commit()
        now = datetime.now(UTC)
        db.add_all(
            [
                SourceItem(
                    source_id=source.id, external_id="a", url="https://example.org/a",
                    title="City council approves new downtown parking garage plan",
                    published_at=now, raw_hash="hash-a", ingest_status="NORMALIZED",
                ),
                SourceItem(
                    source_id=source.id, external_id="b", url="https://example.org/b",
                    title="Council votes to approve downtown parking structure",
                    published_at=now, raw_hash="hash-b", ingest_status="NORMALIZED",
                ),
            ]
        )
        db.commit()

        processed = cluster_normalized_items(db)
        assert processed == 2

        from app.models import Story

        stories = db.scalars(select(Story)).all()
        assert len(stories) == 2
