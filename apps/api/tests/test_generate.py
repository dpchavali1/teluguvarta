"""T11 acceptance tests: story generation (classify -> generate -> validate
-> priority routing) via the AI gateway. Uses a `FakeProvider` monkeypatched
into the gateway, same pattern as `test_ai_gateway.py`, since these tests
care about T11's routing/state-machine logic, not real model output.
"""

import uuid
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
    StoryClaim,
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


def _generation(*, item_id, **overrides):
    """`item_id` must be a real `SourceItem.id` from the cluster under test —
    P0-1's gateway ref-membership check HOLDs the whole story if a claim
    cites a source_ref that isn't a real item in the cluster."""
    ref = str(item_id)
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
        "claims": [{"text": "Processing times will increase", "source_refs": [ref]}],
        "source_refs": [ref],
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
        _use_fake_provider(monkeypatch, [_classification(), _generation(item_id=item.id)])

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
            [
                _classification(sensitivity="IMMIGRATION", confidence=0.99),
                _generation(item_id=item.id, confidence=0.99),
            ],
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
        _use_fake_provider(monkeypatch, [_classification(confidence=0.2), _generation(item_id=_item.id)])

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
            [_classification(), _generation(item_id=item.id, claims=[{"text": "unsupported", "source_refs": []}])],
        )

        generate_stories(db)

        db.refresh(story)
        db.refresh(item)
        assert story.status == "DRAFT"
        assert item.ingest_status == "CLUSTERED"
        assert db.scalars(select(StoryVariant).where(StoryVariant.story_id == story.id)).first() is None


@requires_postgres
def test_kept_and_removed_claims_are_persisted_for_audit(migrated_database, monkeypatch):
    """P0-1: the gateway's per-claim decision must be reviewable after the
    fact, not just discarded with the `GatewayOutcome`."""
    engine = create_engine(migrated_database)
    with Session(engine) as db:
        source = _make_source(db)
        story, item = _make_clustered_story(db, source)
        _use_fake_provider(
            monkeypatch,
            [
                _classification(),
                _generation(
                    item_id=item.id,
                    claims=[
                        {"text": "kept claim", "source_refs": [str(item.id)]},
                        {"text": "no-evidence claim", "source_refs": []},
                    ],
                ),
            ],
        )

        generate_stories(db)

        db.refresh(story)
        assert story.status == "AI_READY"
        claims = db.scalars(select(StoryClaim).where(StoryClaim.story_id == story.id)).all()
        assert {(c.text, c.status) for c in claims} == {
            ("kept claim", "KEPT"),
            ("no-evidence claim", "REMOVED_NO_REF"),
        }


@requires_postgres
def test_fabricated_source_ref_holds_story_instead_of_publishing(migrated_database, monkeypatch):
    """P0-1: a claim citing a source_ref that names no real `SourceItem` in
    the cluster — e.g. one injected via a crafted feed title — must never
    reach publication. The story stays `DRAFT` for a later retry, exactly
    like any other gateway HOLD."""
    engine = create_engine(migrated_database)
    with Session(engine) as db:
        source = _make_source(db)
        story, item = _make_clustered_story(db, source)
        _use_fake_provider(
            monkeypatch,
            [
                _classification(),
                _generation(
                    item_id=item.id,
                    claims=[{"text": "fabricated claim", "source_refs": ["injected-fake-id"]}],
                ),
            ],
        )

        generate_stories(db)

        db.refresh(story)
        db.refresh(item)
        assert story.status == "DRAFT"
        assert item.ingest_status == "CLUSTERED"
        assert db.scalars(select(StoryVariant).where(StoryVariant.story_id == story.id)).first() is None
        assert db.scalars(select(StoryClaim).where(StoryClaim.story_id == story.id)).all() == []


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
        _, item = _make_clustered_story(db, source)
        _use_fake_provider(monkeypatch, [_classification(), _generation(item_id=item.id)])

        assert generate_stories(db) == 1
        # No new fake responses queued — a second pass touching the same
        # story would raise IndexError, proving it's skipped.
        assert generate_stories(db) == 0


# ADR-020: stored descriptions in evidence and the verbatim-run copy guard.


def test_evidence_block_includes_description_unless_excluded():
    import json

    from app.jobs.generate import _evidence_block
    from app.models import SourceItem

    item = SourceItem(id=uuid.uuid4(), url="https://x.gov/a", title="T", description="Advisory text.")
    assert json.loads(_evidence_block([item]))[0]["description"] == "Advisory text."
    assert "description" not in json.loads(_evidence_block([item], include_description=False))[0]
    item.description = None
    assert "description" not in json.loads(_evidence_block([item]))[0]


def test_summary_sharing_twelve_words_with_description_is_flagged():
    from app.jobs.generate import _summary_too_similar_to_source
    from app.models import SourceItem

    advisory = "Do not travel to the region due to active armed conflict and the risk of missile attacks near the border."
    item = SourceItem(id=uuid.uuid4(), url="https://x.gov/a", title="Ukraine Travel Advisory", description=advisory)
    copied = "Officials said: do not travel to the region due to active armed conflict and the risk of missiles."
    original = "The State Department told Americans to stay away from the area because fighting continues there."
    assert _summary_too_similar_to_source(copied, [item])
    assert not _summary_too_similar_to_source(original, [item])
