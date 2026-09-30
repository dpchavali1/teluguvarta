"""ADR-027 (review 2026-09-29 #10): model confidence is stored apart from
importance, importance is a deterministic score an editor can override, and
countries are where the story happens, never where its publisher is."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.content.geography import normalize_countries, normalize_country
from app.content.importance import compute_importance, recompute_importance
from app.content.notifications import (
    NotifiableStory,
    UserNotificationPrefs,
    breaking_alert_eligible,
)
from app.jobs.generate import generate_stories
from app.models import AuditEvent, SourceItem, StoryCountry, StorySource
from tests.conftest import requires_postgres
from tests.test_editorial_workflow import (  # noqa: F401  (fixtures)
    _auth,
    _make_review_required_story,
    _token,
    client,
    db_session,
)
from tests.test_generate import (
    _classification,
    _generation,
    _make_clustered_story,
    _make_source,
    _use_fake_provider,
)


@pytest.mark.parametrize(("kwargs", "expected"), [
    ({"urgent": False, "independent_sources": 1, "priority_topic": False}, 0.4),
    ({"urgent": True, "independent_sources": 1, "priority_topic": False}, 0.6),
    ({"urgent": False, "independent_sources": 3, "priority_topic": True}, 0.7),
    ({"urgent": False, "independent_sources": 10, "priority_topic": False}, 0.7),  # +0.3 cap
    ({"urgent": True, "independent_sources": 10, "priority_topic": True}, 1.0),
    ({"urgent": False, "independent_sources": 0, "priority_topic": False}, 0.4),  # hand-drafted, no sources
])
def test_compute_importance(kwargs, expected):
    assert compute_importance(**kwargs) == pytest.approx(expected)


def test_country_normalization_keeps_supported_codes_only():
    assert normalize_country("United Kingdom") == "GB"
    assert normalize_country("usa") == "US"
    assert normalize_country("in") == "IN"
    assert normalize_country("Narnia") is None
    assert normalize_country("FR") is None  # a real code, but not in the supported list
    assert normalize_countries(["UK", "Britain", "US", "", None]) == ["GB", "US"]


def _breaking(confidence):
    return NotifiableStory(
        id="s", topics=(), importance=0.5, classification_confidence=confidence, sensitivity="BREAKING",
        breaking_alert_approved=True, avg_source_quality=0.9,
    )


def test_breaking_alert_reads_confidence_not_importance():
    prefs = UserNotificationPrefs(
        subscribed_topics=(), breaking_alerts_enabled=True, daily_briefing_enabled=False,
        quiet_hours_start=None, quiet_hours_end=None, max_alerts_per_day=5,
    )
    assert breaking_alert_eligible(_breaking(0.9), prefs) is True
    assert breaking_alert_eligible(_breaking(0.5), prefs) is False
    # Hand-drafted: no model confidence; the editor's alert approval decides.
    assert breaking_alert_eligible(_breaking(None), prefs) is True


@requires_postgres
def test_generation_separates_confidence_importance_and_event_countries(migrated_database, monkeypatch):
    engine = create_engine(migrated_database)
    with Session(engine) as db:
        source = _make_source(db)
        source.country = "US"
        db.commit()
        story, item = _make_clustered_story(db, source)
        _use_fake_provider(monkeypatch, [
            # Very sure it's relevant, but minor: one source, normal urgency.
            _classification(confidence=0.97, countries=["United Kingdom", "Narnia"]),
            _generation(item_id=item.id),
        ])
        assert generate_stories(db) == 1
        db.refresh(story)

        assert story.classification_confidence == pytest.approx(0.97)
        assert story.urgency == "NORMAL"
        assert story.importance == pytest.approx(0.4)
        codes = db.scalars(select(StoryCountry.country_code).where(StoryCountry.story_id == story.id)).all()
        assert codes == ["GB"]  # not the publisher's US; unknown dropped


@requires_postgres
def test_another_independent_source_raises_importance(migrated_database):
    engine = create_engine(migrated_database)
    with Session(engine) as db:
        story, _item = _make_clustered_story(db, _make_source(db))
        recompute_importance(db, story)
        assert story.importance == pytest.approx(0.4)

        other = _make_source(db)
        item = SourceItem(
            source_id=other.id, external_id="b", url="https://example.org/b", title="Same event",
            published_at=datetime.now(UTC), raw_hash="hash-b", ingest_status="CLUSTERED",
        )
        db.add(item)
        db.flush()
        db.add(StorySource(story_id=story.id, source_item_id=item.id, role="SUPPORTING", evidence_rank=2))
        recompute_importance(db, story)
        assert story.importance == pytest.approx(0.5)

        story.importance_override = "LOW"
        recompute_importance(db, story)
        assert story.importance == pytest.approx(0.2)


@requires_postgres
def test_editor_sets_event_countries_and_importance(client, db_session):  # noqa: F811
    token = _token(client, db_session)
    story = _make_review_required_story(db_session)
    url = f"/v1/admin/stories/{story.id}"

    bad = client.put(f"{url}/countries", json={"countries": ["GB", "Narnia"]}, headers=_auth(token))
    assert bad.status_code == 422
    assert bad.json()["error"]["code"] == "UNKNOWN_COUNTRY"

    assert client.put(f"{url}/countries", json={"countries": ["uk", "IN"]}, headers=_auth(token)).status_code == 200
    detail = client.get(url, headers=_auth(token)).json()
    assert sorted(detail["countries"]) == ["GB", "IN"]
    assert detail["classification_confidence"] is None

    assert client.put(f"{url}/importance", json={"level": "HIGH"}, headers=_auth(token)).status_code == 200
    detail = client.get(url, headers=_auth(token)).json()
    assert detail["importance_override"] == "HIGH"
    assert detail["importance"] == pytest.approx(0.8)

    assert client.put(f"{url}/importance", json={"level": None}, headers=_auth(token)).status_code == 200
    detail = client.get(url, headers=_auth(token)).json()
    assert detail["importance_override"] is None
    assert detail["importance"] != pytest.approx(0.8)

    actions = set(db_session.scalars(
        select(AuditEvent.action).where(AuditEvent.entity_id == story.id)
    ).all())
    assert {"STORY_COUNTRIES_SET", "STORY_IMPORTANCE_SET"} <= actions


@requires_postgres
def test_migration_moves_confidence_and_rescores(scratch_database, monkeypatch):
    """Backfill: AI-written stories keep their old value as confidence;
    importance is recomputed from sources and topics; hand-drafted stories
    get no confidence. Downgrade restores importance from confidence."""
    from pathlib import Path

    from alembic import command
    from alembic.config import Config
    from sqlalchemy import text

    monkeypatch.setenv("DATABASE_URL", scratch_database)
    cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    command.upgrade(cfg, "c9f5d3e7a2b4")
    engine = create_engine(scratch_database)
    with engine.begin() as conn:
        src = [conn.execute(text(
            "INSERT INTO sources (name, rights_status) VALUES (:n, 'LINK_ONLY') RETURNING id"
        ), {"n": n}).scalar_one() for n in ("A", "B")]
        topic = conn.execute(text(
            "INSERT INTO topics (slug, name) VALUES ('immigration', 'Immigration') RETURNING id"
        )).scalar_one()
        ids = {}
        for key, importance, model_version in (("ai", 0.95, "summary"), ("editor", 0.0, "editor")):
            story = conn.execute(text(
                "INSERT INTO stories (canonical_slug, importance) VALUES (:s, :i) RETURNING id"
            ), {"s": f"s-{key}", "i": importance}).scalar_one()
            conn.execute(text(
                "INSERT INTO story_variants (story_id, language, headline, summary, model_version) "
                "VALUES (:s, 'en', 'h', 'x', :m)"
            ), {"s": story, "m": model_version})
            ids[key] = story
        for n, source_id in enumerate(src):  # the AI story has two independent sources
            item = conn.execute(text(
                "INSERT INTO source_items (source_id, external_id, url, title, raw_hash) "
                "VALUES (:s, :e, 'https://x', 't', :e) RETURNING id"
            ), {"s": source_id, "e": f"e{n}"}).scalar_one()
            conn.execute(text(
                "INSERT INTO story_sources (story_id, source_item_id, role, evidence_rank) VALUES (:s, :i, 'PRIMARY', :r)"
            ), {"s": ids["ai"], "i": item, "r": n})
        conn.execute(text("INSERT INTO story_topics (story_id, topic_id) VALUES (:s, :t)"),
                     {"s": ids["editor"], "t": topic})

    command.upgrade(cfg, "d1a6e4f8b3c5")
    with engine.connect() as conn:
        rows = {r.id: r for r in conn.execute(text(
            "SELECT id, importance, classification_confidence FROM stories"
        ))}
    assert rows[ids["ai"]].classification_confidence == pytest.approx(0.95)
    assert rows[ids["ai"]].importance == pytest.approx(0.5)  # base + one extra source
    assert rows[ids["editor"]].classification_confidence is None
    assert rows[ids["editor"]].importance == pytest.approx(0.5)  # base + priority topic

    command.downgrade(cfg, "c9f5d3e7a2b4")
    with engine.connect() as conn:
        restored = dict(conn.execute(text("SELECT id, importance FROM stories")).all())
    assert restored[ids["ai"]] == pytest.approx(0.95)
    assert restored[ids["editor"]] == pytest.approx(0.0)
    engine.dispose()
