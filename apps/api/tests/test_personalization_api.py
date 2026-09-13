"""T16 acceptance tests: `GET /v1/home` personalizes against explicit
query-param preferences (ADR-005 — no server-persisted account exists yet),
every personalized item carries a signal-derived explanation, and a
segment's "why this matters" is generated at most once and then cached
(verified via T10's `ai_call_log` telemetry). Fixtures mirror
`test_public_web.py`.
"""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.ai import gateway as gateway_module
from app.ai.providers.base import ProviderResponse
from app.models import (
    AiCallLog,
    Job,
    Source,
    SourceItem,
    Story,
    StorySource,
    StoryTopic,
    StoryVariant,
    Topic,
)
from tests.conftest import requires_postgres

pytestmark = requires_postgres


class FakeProvider:
    name = "fake"

    def __init__(self, responses):
        self._responses = list(responses)

    def complete(self, *, model, task, prompt, constrained=False):
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return ProviderResponse(output=item, tokens_in=10, tokens_out=5)


def _use_fake_provider(monkeypatch, responses):
    provider = FakeProvider(responses)
    monkeypatch.setattr(gateway_module, "_resolve_provider", lambda name: provider)
    return provider


@pytest.fixture
def client(migrated_database):
    from app.db import _engine_for
    from app.main import app

    _engine_for.cache_clear()
    yield TestClient(app)
    _engine_for.cache_clear()


@pytest.fixture
def db_session(migrated_database):
    engine = create_engine(migrated_database)
    with Session(engine) as session:
        yield session
    engine.dispose()


def _seed_published_story(
    db: Session, *, country: str = "US", topic_slug: str = "immigration",
    importance: float = 0.8, headline: str = "Original headline",
) -> Story:
    source = Source(name="Example Wire", base_url="https://example.com", rights_status="LINK_ONLY", country=country)
    db.add(source)
    db.flush()
    item = SourceItem(
        source_id=source.id, external_id=str(uuid.uuid4()), url="https://example.com/article",
        title="Original source title", raw_hash=str(uuid.uuid4()),
    )
    db.add(item)
    db.flush()

    story = Story(canonical_slug=f"story-{uuid.uuid4()}", status="DRAFT", sensitivity="NONE", importance=importance)
    db.add(story)
    db.flush()
    db.add(StorySource(story_id=story.id, source_item_id=item.id, role="PRIMARY", evidence_rank=0))
    topic = db.scalars(select(Topic).where(Topic.slug == topic_slug)).first()
    if topic is None:
        topic = Topic(slug=topic_slug, name=topic_slug.title())
        db.add(topic)
        db.flush()
    db.add(StoryTopic(story_id=story.id, topic_id=topic.id, weight=1))
    db.add(StoryVariant(story_id=story.id, language="en", headline=headline, summary="Original summary", why_matters="Why it matters"))
    db.flush()

    for intermediate in ("AI_READY", "REVIEW_REQUIRED", "APPROVED", "SCHEDULED", "PUBLISHED"):
        story.status = intermediate
        db.flush()
    db.commit()
    db.refresh(story)
    return story


def test_home_without_preferences_is_unpersonalized(client, db_session):
    _seed_published_story(db_session)
    response = client.get("/v1/home")
    assert response.status_code == 200
    body = response.json()
    assert body["top_stories"][0]["personalization"] is None


def test_home_personalizes_by_residence_and_explains_why(client, db_session):
    matching = _seed_published_story(db_session, country="US", topic_slug="immigration", headline="US story")
    _seed_published_story(db_session, country="IN", topic_slug="money", headline="India story")

    response = client.get("/v1/home", params={"residence_country": "US", "topics": "immigration"})
    assert response.status_code == 200
    body = response.json()

    slugs = [s["canonical_slug"] for s in body["top_stories"]]
    assert slugs[0] == matching.canonical_slug

    top = body["top_stories"][0]
    assert top["personalization"] is not None
    assert top["personalization"]["score"] > 0
    explanation = top["personalization"]["explanation"]
    assert "US" in explanation
    assert "Immigration" in explanation


def test_student_briefing_composes_fixed_topics_without_explicit_topics_param(client, db_session):
    """S1: `student_briefing=true` should personalize using the fixed
    immigration/education/jobs/money/travel/community topic set even with
    no `topics` query param — it's a filtered/composed view over the same
    `/v1/home` ranking, not a separate pipeline (docs/tickets/S1.md)."""
    matching = _seed_published_story(db_session, country="IN", topic_slug="education", headline="Education story")
    _seed_published_story(db_session, country="IN", topic_slug="sports", headline="Sports story")

    unpersonalized = client.get("/v1/home")
    assert unpersonalized.json()["top_stories"][0]["personalization"] is None

    response = client.get("/v1/home", params={"student_briefing": "true"})
    assert response.status_code == 200
    body = response.json()
    slugs = [s["canonical_slug"] for s in body["top_stories"]]
    assert slugs[0] == matching.canonical_slug
    assert body["top_stories"][0]["personalization"] is not None


def test_why_matters_generated_once_and_cached(client, db_session, monkeypatch):
    _seed_published_story(db_session, country="US", topic_slug="immigration")
    _use_fake_provider(monkeypatch, [
        {"why_matters": "Because it affects US immigrants."},
    ])

    first = client.get(
        "/v1/home", params={"residence_country": "US", "segment": "international_student"}
    )
    second = client.get(
        "/v1/home", params={"residence_country": "US", "segment": "international_student"}
    )
    assert first.status_code == 200
    assert second.status_code == 200

    # A public read queues work but never performs provider I/O.
    assert first.json()["top_stories"][0]["personalization"]["why_matters"] is None
    from app.jobs.why_matters import run_why_matters
    job = db_session.scalar(select(Job).where(Job.type == "ai_summarize"))
    assert job is not None
    run_why_matters(db_session, job)
    run_why_matters(db_session, job)  # job retries use the existing cached output
    first = client.get("/v1/home", params={"residence_country": "US", "segment": "international_student"})
    second = client.get("/v1/home", params={"residence_country": "US", "segment": "international_student"})
    first_why = first.json()["top_stories"][0]["personalization"]["why_matters"]
    second_why = second.json()["top_stories"][0]["personalization"]["why_matters"]
    assert first_why == "Because it affects US immigrants."
    assert second_why == first_why

    call_count = db_session.scalar(
        select(func.count()).select_from(AiCallLog).where(AiCallLog.task == "why_matters")
    )
    assert call_count == 1
