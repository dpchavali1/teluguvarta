"""ADR-015 wiring: generate/translate compute, persist and pass the privacy
decision, and only a FREE_TIER_ALLOWED story is routed to Gemini."""

import hashlib

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.ai import gateway as gateway_module
from app.ai import ratelimit
from app.jobs.generate import generate_stories
from app.jobs.translate import translate_stories
from app.models import Correction, Source, Story, StoryVariant

from .conftest import requires_postgres
from .test_generate import (
    FakeProvider,
    _classification,
    _generation,
    _make_clustered_story,
)


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
