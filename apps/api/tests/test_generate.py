"""T11 acceptance tests: story generation (classify -> generate -> validate
-> priority routing) via the AI gateway. Uses a `FakeProvider` monkeypatched
into the gateway, same pattern as `test_ai_gateway.py`, since these tests
care about T11's routing/state-machine logic, not real model output.
"""

from datetime import UTC, datetime

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.ai import gateway as gateway_module
from app.ai.providers.base import ProviderResponse
from app.jobs.generate import generate_stories
from app.models import (
    ReviewTask,
    Source,
    SourceItem,
    Story,
    StorySource,
    StoryTopic,
    StoryVariant,
)

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


def _use_fake_provider(monkeypatch, responses):
    provider = FakeProvider(responses)
    monkeypatch.setattr(gateway_module, "_resolve_provider", lambda name: provider)
    return provider


def _classification(**overrides):
    base = {
        "relevant": True,
        "confidence": 0.9,
        "categories": ["Immigration Policy"],
        "countries": ["US"],
        "entities": ["USCIS"],
        "sensitivity": "NONE",
        "urgency": "NORMAL",
        "headline_en": "n/a",
        "summary_en": "n/a",
        "why_matters_en": "n/a",
        "claims": [],
        "source_refs": [],
        "publish_recommendation": "PUBLISH",
    }
    base.update(overrides)
    return base


def _generation(**overrides):
    base = {
        "relevant": True,
        "confidence": 0.9,
        "categories": [],
        "countries": [],
        "entities": [],
        "sensitivity": "NONE",
        "urgency": "NORMAL",
        "headline_en": "New rule changes visa processing times",
        "summary_en": "A federal agency announced changes to visa processing timelines this week.",
        "why_matters_en": "Applicants should expect longer waits for certain visa categories.",
        "claims": [{"text": "Processing times will increase", "source_refs": ["src-1"]}],
        "source_refs": ["src-1"],
        "publish_recommendation": "PUBLISH",
    }
    base.update(overrides)
    return base


def _make_source(db: Session) -> Source:
    source = Source(name="Test Source", feed_url="https://example.org/feed.xml", rights_status="LINK_ONLY", active=True)
    db.add(source)
    db.commit()
    return source


def _make_clustered_story(db: Session, source: Source, *, title: str = "Agency announces visa rule change") -> tuple[Story, SourceItem]:
    item = SourceItem(
        source_id=source.id,
        external_id="a",
        url="https://example.org/a",
        title=title,
        published_at=datetime.now(UTC),
        raw_hash="hash-a",
        ingest_status="CLUSTERED",
    )
    db.add(item)
    db.flush()
    story = Story(canonical_slug=f"story-{item.id}")
    db.add(story)
    db.flush()
    db.add(StorySource(story_id=story.id, source_item_id=item.id, role="PRIMARY", evidence_rank=1))
    db.commit()
    return story, item


@requires_postgres
def test_low_risk_story_generates_and_becomes_ai_ready(migrated_database, monkeypatch):
    engine = create_engine(migrated_database)
    with Session(engine) as db:
        source = _make_source(db)
        story, item = _make_clustered_story(db, source)
        _use_fake_provider(monkeypatch, [_classification(), _generation()])

        processed = generate_stories(db)
        assert processed == 1

        db.refresh(story)
        db.refresh(item)
        assert story.status == "AI_READY"
        assert item.ingest_status == "SCHEDULED"
        assert db.scalars(select(ReviewTask).where(ReviewTask.story_id == story.id)).first() is None

        variant = db.scalars(select(StoryVariant).where(StoryVariant.story_id == story.id)).first()
        assert variant is not None
        assert variant.headline == "New rule changes visa processing times"
        assert variant.language == "en"

        topics = db.scalars(select(StoryTopic).where(StoryTopic.story_id == story.id)).all()
        assert len(topics) == 1


@requires_postgres
def test_sensitive_category_always_goes_to_review_required(migrated_database, monkeypatch):
    """NON_NEGOTIABLES #5: immigration/legal/financial/breaking is never
    auto-published, regardless of AI confidence."""
    engine = create_engine(migrated_database)
    with Session(engine) as db:
        source = _make_source(db)
        story, item = _make_clustered_story(db, source)
        _use_fake_provider(
            monkeypatch,
            [_classification(sensitivity="IMMIGRATION", confidence=0.99), _generation(confidence=0.99)],
        )

        generate_stories(db)

        db.refresh(story)
        db.refresh(item)
        assert story.status == "REVIEW_REQUIRED"
        assert story.sensitivity == "IMMIGRATION"
        assert item.ingest_status == "REVIEW"

        task = db.scalars(select(ReviewTask).where(ReviewTask.story_id == story.id)).first()
        assert task is not None
        assert "SENSITIVE_CATEGORY" in task.reason


@requires_postgres
def test_low_confidence_classification_goes_to_review(migrated_database, monkeypatch):
    engine = create_engine(migrated_database)
    with Session(engine) as db:
        source = _make_source(db)
        story, _item = _make_clustered_story(db, source)
        _use_fake_provider(monkeypatch, [_classification(confidence=0.2), _generation()])

        generate_stories(db)

        db.refresh(story)
        assert story.status == "REVIEW_REQUIRED"
        task = db.scalars(select(ReviewTask).where(ReviewTask.story_id == story.id)).first()
        assert "LOW_CONFIDENCE_CLASSIFICATION" in task.reason


@requires_postgres
def test_irrelevant_story_is_archived_without_a_generation_call(migrated_database, monkeypatch):
    engine = create_engine(migrated_database)
    with Session(engine) as db:
        source = _make_source(db)
        story, item = _make_clustered_story(db, source)
        # Only one response queued — a second gateway call would raise
        # IndexError (list.pop on empty), proving generation never runs.
        _use_fake_provider(monkeypatch, [_classification(relevant=False)])

        generate_stories(db)

        db.refresh(story)
        db.refresh(item)
        assert story.status == "DRAFT"
        assert item.ingest_status == "ARCHIVED"
        assert db.scalars(select(StoryVariant).where(StoryVariant.story_id == story.id)).first() is None


@requires_postgres
def test_story_with_only_unsupported_claims_is_held_not_published(migrated_database, monkeypatch):
    """Every claim must have source_refs (§7.4); a story with none is held,
    not published — enforced by the gateway itself (T10)."""
    engine = create_engine(migrated_database)
    with Session(engine) as db:
        source = _make_source(db)
        story, item = _make_clustered_story(db, source)
        _use_fake_provider(
            monkeypatch,
            [_classification(), _generation(claims=[{"text": "unsupported", "source_refs": []}])],
        )

        generate_stories(db)

        db.refresh(story)
        db.refresh(item)
        assert story.status == "DRAFT"
        assert item.ingest_status == "CLUSTERED"
        assert db.scalars(select(StoryVariant).where(StoryVariant.story_id == story.id)).first() is None


@requires_postgres
def test_provider_unavailable_leaves_story_for_a_later_sweep(migrated_database, monkeypatch):
    engine = create_engine(migrated_database)
    with Session(engine) as db:
        source = _make_source(db)
        story, item = _make_clustered_story(db, source)
        monkeypatch.delenv("AI_OPENAI_API_KEY", raising=False)

        processed = generate_stories(db)
        assert processed == 1  # attempted, but not advanced

        db.refresh(story)
        db.refresh(item)
        assert story.status == "DRAFT"
        assert item.ingest_status == "CLUSTERED"


@requires_postgres
def test_generate_stories_is_idempotent(migrated_database, monkeypatch):
    engine = create_engine(migrated_database)
    with Session(engine) as db:
        source = _make_source(db)
        _make_clustered_story(db, source)
        _use_fake_provider(monkeypatch, [_classification(), _generation()])

        assert generate_stories(db) == 1
        # No new fake responses queued — a second pass touching the same
        # story would raise IndexError, proving it's skipped.
        assert generate_stories(db) == 0
