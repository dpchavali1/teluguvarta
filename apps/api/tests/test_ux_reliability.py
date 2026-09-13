"""Regression coverage for the 2026-09-12 reading-journey review."""
from datetime import UTC, datetime

from sqlalchemy import event, select

from app.models import Job, Story, StoryVariant, StoryWhyMattersCache
from tests.conftest import requires_postgres
from tests.test_public_web import _seed_published_story
from tests.test_public_web import client  # noqa: F401 -- shared pytest fixture
from tests.test_public_web import db_session  # noqa: F401 -- shared pytest fixture

pytestmark = requires_postgres


def test_saved_lookup_finds_old_bookmark_without_exposing_drafts(client, db_session):
    saved = _seed_published_story(db_session)
    saved.published_at = datetime(2000, 1, 1, tzinfo=UTC)
    drafts = Story(canonical_slug="hidden-bookmark", status="DRAFT")
    db_session.add(drafts)
    for n in range(105):
        db_session.add(Story(canonical_slug=f"newer-{n}", status="PUBLISHED", published_at=datetime.now(UTC)))
    db_session.commit()
    response = client.get("/v1/stories", params={"ids": f"{saved.id},{drafts.id}", "limit": 100})
    assert response.status_code == 200
    assert [item["id"] for item in response.json()["items"]] == [str(saved.id)]
    assert response.json()["next_cursor"] is None
    assert client.get("/v1/stories", params={"ids": "bad-id"}).status_code == 422


def test_telugu_search_only_matches_passed_variants_once(client, db_session):
    story = _seed_published_story(db_session, te_qa="PASSED")
    response = client.get("/v1/search", params={"q": "తెలుగు"})
    assert [item["id"] for item in response.json()["items"]] == [str(story.id)]
    te = db_session.scalar(select(StoryVariant).where(StoryVariant.story_id == story.id, StoryVariant.language == "te"))
    te.qa_status = "FAILED"
    db_session.commit()
    assert client.get("/v1/search", params={"q": "తెలుగు"}).json()["items"] == []
    te.qa_status = "PASSED"
    te.headline = "Original headline"
    db_session.commit()
    assert len(client.get("/v1/search", params={"q": "Original"}).json()["items"]) == 1
    assert client.get("/v1/search", params={"q": "%"}).json()["items"] == []


def test_feed_miss_queues_once_without_calling_ai(client, db_session, monkeypatch):
    from app.ai.gateway import AiGateway
    story = _seed_published_story(db_session)
    def unexpected(*args, **kwargs):
        raise AssertionError("Public feed must never call AI")
    monkeypatch.setattr(AiGateway, "run_task", unexpected)
    for _ in range(2):
        response = client.get("/v1/home", params={"residence_country": "US", "segment": "professional"})
        assert response.status_code == 200
        assert response.json()["top_stories"][0]["personalization"]["why_matters"] is None
    jobs = list(db_session.scalars(select(Job).where(Job.type == "ai_summarize")))
    assert len(jobs) == 1
    assert jobs[0].payload["story_id"] == str(story.id)


def test_sensitive_story_never_uses_unreviewed_segment_cache(client, db_session):
    story = _seed_published_story(db_session)
    story.sensitivity = "IMMIGRATION"
    db_session.add(StoryWhyMattersCache(story_id=story.id, segment="professional", why_matters="Unreviewed", model_version="test"))
    db_session.commit()
    result = client.get("/v1/home", params={"residence_country": "US", "segment": "professional"}).json()
    assert result["top_stories"][0]["personalization"]["why_matters"] is None
    assert list(db_session.scalars(select(Job).where(Job.type == "ai_summarize"))) == []


def test_public_page_has_bounded_queries_and_cursor(client, db_session):
    import os

    from app.db import _engine_for
    for n in range(23):
        _seed_published_story(db_session, topic_slug=f"topic-{n}")
    engine = _engine_for(os.environ["DATABASE_URL"])
    statements = []
    def capture(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)
    event.listen(engine, "before_cursor_execute", capture)
    try:
        first = client.get("/v1/stories").json()
    finally:
        event.remove(engine, "before_cursor_execute", capture)
    assert len(first["items"]) == 20
    assert len(statements) <= 7, statements
    assert any("LIMIT" in stmt and "stories" in stmt for stmt in statements)
    second = client.get("/v1/stories", params={"cursor": first["next_cursor"]}).json()
    assert len(second["items"]) == 3
    assert {s["id"] for s in first["items"]}.isdisjoint({s["id"] for s in second["items"]})
