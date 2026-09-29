"""ADR-015 wiring: generate/translate compute, persist and pass the privacy
decision, and only a FREE_TIER_ALLOWED story is routed to Gemini."""

import hashlib

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.ai import gateway as gateway_module
from app.ai import ratelimit
from app.jobs.generate import generate_stories
from app.jobs.translate import translate_stories
from app.models import Correction, ReviewTask, Source, Story, StoryVariant

from .conftest import requires_postgres
from .test_generate import (
    FakeProvider,
    _classification,
    _generation,
    _make_clustered_story,
)


@pytest.fixture(autouse=True)
def _paid_provider_configured(monkeypatch):
    # Routing tests assume a paid route exists; the hold tests remove it.
    monkeypatch.setenv("AI_OPENAI_API_KEY", "test-key")
    monkeypatch.delenv("AI_ANTHROPIC_API_KEY", raising=False)


def _no_paid_provider(monkeypatch):
    monkeypatch.delenv("AI_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("AI_ANTHROPIC_API_KEY", raising=False)


def _spy(monkeypatch, responses):
    provider = FakeProvider(responses)
    names: list[str] = []

    def resolve(name):
        names.append(name)
        return provider

    monkeypatch.setattr(gateway_module, "_resolve_provider", resolve)
    monkeypatch.setattr(ratelimit, "_buckets", {})
    return names


def _source(db: Session, category: str | None) -> Source:
    source = Source(
        name="S", feed_url="https://example.org/f.xml", rights_status="LINK_ONLY", active=True, category=category
    )
    db.add(source)
    db.commit()
    return source


@requires_postgres
def test_allowlisted_story_routes_to_gemini_when_enabled(migrated_database, monkeypatch):
    monkeypatch.setenv("AI_FREE_TIER_ENABLED", "1")
    with Session(create_engine(migrated_database)) as db:
        story, item = _make_clustered_story(db, _source(db, "sports"), title="Local team wins derby")
        names = _spy(monkeypatch, [_classification(categories=["Sports"]), _generation(item_id=item.id)])
        generate_stories(db)
        db.refresh(story)
        assert names == ["gemini", "gemini"]
        assert story.privacy_decision == "FREE_TIER_ALLOWED"


@requires_postgres
def test_flag_off_or_no_category_never_routes_to_gemini(migrated_database, monkeypatch):
    with Session(create_engine(migrated_database)) as db:
        # flag off, allowlisted category
        _, item = _make_clustered_story(db, _source(db, "sports"), title="Local team wins derby")
        names = _spy(monkeypatch, [_classification(), _generation(item_id=item.id)])
        generate_stories(db)
        assert "gemini" not in names

        # flag on, no category
        monkeypatch.setenv("AI_FREE_TIER_ENABLED", "1")
        story2, item2 = _make_clustered_story(db, _source(db, None), title="Local team wins derby 2")
        names = _spy(monkeypatch, [_classification(), _generation(item_id=item2.id)])
        generate_stories(db)
        db.refresh(story2)
        assert "gemini" not in names
        assert story2.privacy_decision == "UNKNOWN"


@requires_postgres
def test_model_reported_sensitivity_tightens_before_generation(migrated_database, monkeypatch):
    monkeypatch.setenv("AI_FREE_TIER_ENABLED", "1")
    with Session(create_engine(migrated_database)) as db:
        story, item = _make_clustered_story(db, _source(db, "entertainment"), title="Film festival lineup")
        names = _spy(
            monkeypatch,
            [_classification(sensitivity="LEGAL"), _generation(item_id=item.id, sensitivity="LEGAL")],
        )
        generate_stories(db)
        db.refresh(story)
        assert names[0] == "gemini"  # classification was allowed
        assert names[1] != "gemini"  # generation was not, once tightened
        assert story.privacy_decision == "RESTRICTED"


@requires_postgres
def test_restricted_title_beats_allowlisted_category(migrated_database, monkeypatch):
    monkeypatch.setenv("AI_FREE_TIER_ENABLED", "1")
    with Session(create_engine(migrated_database)) as db:
        story, item = _make_clustered_story(db, _source(db, "sports"), title="Star player H-1B visa delay")
        names = _spy(monkeypatch, [_classification(), _generation(item_id=item.id)])
        generate_stories(db)
        db.refresh(story)
        assert "gemini" not in names
        assert story.privacy_decision == "RESTRICTED"


@requires_postgres
def test_translation_of_corrected_story_never_uses_gemini(migrated_database, monkeypatch):
    monkeypatch.setenv("AI_FREE_TIER_ENABLED", "1")
    with Session(create_engine(migrated_database)) as db:
        story = Story(canonical_slug="corrected", privacy_decision="FREE_TIER_ALLOWED")
        db.add(story)
        db.flush()
        db.add(StoryVariant(story_id=story.id, language="en", headline="H", summary="S", qa_status="PENDING"))
        db.add(
            Correction(
                story_id=story.id, reason="typo",
                old_text_hash=hashlib.sha256(b"a").hexdigest(), new_text_hash=hashlib.sha256(b"b").hexdigest(),
            )
        )
        db.commit()
        names = _spy(monkeypatch, [{"headline_te": "హెచ్", "summary_te": "ఎస్", "why_matters_te": None}])
        translate_stories(db)
        assert "gemini" not in names
        assert names  # it was translated, on the paid route


@requires_postgres
def test_unknown_story_holds_for_triage_without_paid_provider(migrated_database, monkeypatch):
    monkeypatch.setenv("AI_FREE_TIER_ENABLED", "1")
    _no_paid_provider(monkeypatch)
    with Session(create_engine(migrated_database)) as db:
        story, item = _make_clustered_story(db, _source(db, "politics"), title="Council meets")
        names = _spy(monkeypatch, [])
        generate_stories(db)
        db.refresh(story)
        db.refresh(item)
        task = db.scalars(select(ReviewTask).where(ReviewTask.story_id == story.id)).one()
        assert names == []  # no provider was ever resolved
        assert story.status == "REVIEW_REQUIRED"
        assert item.ingest_status == "REVIEW"
        assert "NO_PAID_PROVIDER" in task.reason
        assert generate_stories(db) == 0  # idempotent: not retried next sweep


@requires_postgres
def test_allowed_story_is_not_held_without_paid_provider(migrated_database, monkeypatch):
    monkeypatch.setenv("AI_FREE_TIER_ENABLED", "1")
    _no_paid_provider(monkeypatch)
    with Session(create_engine(migrated_database)) as db:
        story, item = _make_clustered_story(db, _source(db, "sports"), title="Local team wins derby")
        names = _spy(monkeypatch, [_classification(categories=["Sports"]), _generation(item_id=item.id)])
        generate_stories(db)
        db.refresh(story)
        assert names == ["gemini", "gemini"]
        assert story.status == "AI_READY"


@requires_postgres
def test_sensitivity_tightening_without_paid_provider_holds(migrated_database, monkeypatch):
    monkeypatch.setenv("AI_FREE_TIER_ENABLED", "1")
    _no_paid_provider(monkeypatch)
    with Session(create_engine(migrated_database)) as db:
        story, _ = _make_clustered_story(db, _source(db, "entertainment"), title="Film festival lineup")
        names = _spy(monkeypatch, [_classification(sensitivity="LEGAL")])
        generate_stories(db)
        db.refresh(story)
        task = db.scalars(select(ReviewTask).where(ReviewTask.story_id == story.id)).one()
        assert names == ["gemini"]  # only the allowed classification call ran
        assert story.status == "REVIEW_REQUIRED"
        assert story.sensitivity == "LEGAL"
        assert "SENSITIVE_CATEGORY" in task.reason and "NO_PAID_PROVIDER" in task.reason
