"""Real Postgres search boundaries, visibility, literal matching and cursors."""

import base64
import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select

from app import rate_limit
from app.content.search_cursor import encode_search_cursor
from app.models import Story, StoryVariant
from tests.conftest import requires_postgres
from tests.test_public_web import _seed_published_story

pytestmark = requires_postgres
DATE = datetime(2026, 10, 1, 12, tzinfo=UTC)


@pytest.fixture(autouse=True)
def reset_search_rate_limit():
    rate_limit._WINDOWS.clear()
    yield
    rate_limit._WINDOWS.clear()


def _story(db, at=DATE, *, en="Page match", te=None, qa="PASSED"):
    story = _seed_published_story(db, topic_slug=f"topic-{uuid4()}")
    story.published_at = at
    variant = db.scalars(select(StoryVariant).where(StoryVariant.story_id == story.id)).one()
    variant.headline = en
    variant.summary = "Summary"
    if te:
        db.add(StoryVariant(story_id=story.id, language="te", headline=te, summary="తెలుగు వివరాలు", qa_status=qa))
    db.commit()
    return story


def _page(client, q="match", **params):
    response = client.get("/v1/search", params={"q": q, **params})
    assert response.status_code == 200, response.text
    return response.json()


def test_pages_cover_ties_nulls_and_exact_final_page(client, db_session):
    stories = [_story(db_session, at) for at in [DATE, DATE, DATE - timedelta(days=1), None, None, None]]
    expected = sorted(stories, key=lambda story: (story.published_at is None,
                                                -(story.published_at.timestamp()) if story.published_at else 0, story.id))
    ids, cursor = [], None
    for index in range(3):
        page = _page(client, limit=2, **({"cursor": cursor} if cursor else {}))
        ids.extend(item["id"] for item in page["items"])
        cursor = page["next_cursor"]
        assert bool(cursor) == (index < 2)
    assert ids == [str(story.id) for story in expected]
    assert len(set(ids)) == 6


def test_insertion_and_removal_ahead_of_boundary_do_not_shift_pages(client, db_session):
    first = _story(db_session, DATE)
    second = _story(db_session, DATE - timedelta(days=1))
    third = _story(db_session, DATE - timedelta(days=2))
    cursor = _page(client, limit=1)["next_cursor"]
    _story(db_session, DATE + timedelta(days=1))
    # Make the already returned row stop matching without shifting later rows.
    db_session.scalars(select(StoryVariant).where(StoryVariant.story_id == first.id)).one().headline = "Other story"
    db_session.commit()
    page = _page(client, limit=2, cursor=cursor)
    assert [item["id"] for item in page["items"]] == [str(second.id), str(third.id)]
    assert page["next_cursor"] is None


@pytest.mark.parametrize("query", ["match", "తెలుగు"])
def test_bilingual_pages_deduplicate_and_exclude_failed_te_and_drafts(client, db_session, query):
    both = _story(db_session, en="match తెలుగు", te="match తెలుగు")
    other = _story(db_session, DATE - timedelta(days=1), en="English", te="match తెలుగు")
    _story(db_session, en="English", te="match తెలుగు", qa="FAILED")
    hidden = Story(canonical_slug=f"draft-{uuid4()}", status="DRAFT", sensitivity="NONE", importance=1)
    db_session.add(hidden)
    db_session.flush()
    db_session.add(StoryVariant(story_id=hidden.id, language="en", headline="match తెలుగు", summary="Hidden"))
    db_session.commit()
    page = _page(client, query, limit=1)
    assert [item["id"] for item in page["items"]] == [str(both.id)]
    tail = _page(client, query, limit=1, cursor=page["next_cursor"])
    assert [item["id"] for item in tail["items"]] == [str(other.id)]
    assert tail["next_cursor"] is None


@pytest.mark.parametrize("query", ["%", "_", "\\"])
def test_literal_wildcards_remain_literal_across_pages(client, db_session, query):
    first = _story(db_session, en=f"Literal {query}")
    second = _story(db_session, DATE - timedelta(days=1), en=f"Literal {query}")
    _story(db_session, en="Other text")
    page = _page(client, query, limit=1)
    tail = _page(client, query, limit=1, cursor=page["next_cursor"])
    assert [item["id"] for item in page["items"] + tail["items"]] == [str(first.id), str(second.id)]
    assert tail["next_cursor"] is None


@pytest.mark.parametrize("cursor", ["", "!bad!", "0" * 513, base64.b64encode(b"[]").decode(),
                                    base64.b64encode(b"\xff").decode()])
def test_invalid_cursor_is_explicit(client, cursor):
    response = client.get("/v1/search", params={"q": "match", "cursor": cursor})
    assert response.status_code == 422
    assert response.json()["error"]["code"] in ("INVALID_SEARCH_CURSOR", "VALIDATION_ERROR")


@pytest.mark.parametrize("change", ["query", "date", "id", "version"])
def test_query_bound_cursor_fields_are_validated(client, change):
    cursor = encode_search_cursor("match", DATE, uuid4())
    payload = json.loads(base64.urlsafe_b64decode(cursor))
    if change == "date": payload["at"] = "2026-10-01T12:00:00"
    if change == "id": payload["id"] = "invalid"
    if change == "version": payload["v"] = True
    cursor = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()
    response = client.get("/v1/search", params={"q": "other" if change == "query" else "match", "cursor": cursor})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_SEARCH_CURSOR"


def test_query_is_trimmed_empty_end_has_no_cursor_and_limits_are_bounded(client, db_session):
    _story(db_session)
    assert _page(client, " match ")["query"] == "match"
    assert _page(client, "missing") == {"query": "missing", "items": [], "next_cursor": None}
    for params in [{"q": " "}, {"q": "x" * 201}, {"q": "match", "limit": 0}, {"q": "match", "limit": 101}]:
        assert client.get("/v1/search", params=params).status_code == 422
