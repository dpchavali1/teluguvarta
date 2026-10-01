"""Review 2026-09-30 R7: the review queue, content library and audit history
page on the server with real totals and filters. Every test scopes its rows
to a fresh source (or entity) so rows other tests left behind don't count."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app import rate_limit
from app.models import (
    AuditEvent,
    Correction,
    ReviewTask,
    Source,
    SourceItem,
    Story,
    StorySource,
    StoryTopic,
    StoryVariant,
    Topic,
)

from .conftest import requires_postgres
from .test_observability import _auth, _token, client  # noqa: F401  (fixture)

pytestmark = requires_postgres

NOW = datetime.now(UTC)


@pytest.fixture(autouse=True)
def _fresh_limits():
    # These tests make many admin requests; don't leave the shared admin limit spent.
    rate_limit.reset()
    yield
    rate_limit.reset()


def _source(db):
    source = Source(name=f"Src {uuid.uuid4().hex[:6]}", feed_url=f"https://example.org/{uuid.uuid4()}.xml", rights_status="LINK_ONLY")
    db.add(source)
    db.flush()
    return source


def _story(db, source, *, status="REVIEW_REQUIRED", headline="Plain story", reason=None, age_hours=1,
           te=None, published_at=None, topic=None):
    story = Story(canonical_slug=f"s-{uuid.uuid4()}", status=status, published_at=published_at)
    db.add(story)
    db.flush()
    item = SourceItem(source_id=source.id, external_id=str(uuid.uuid4()), url=f"https://example.org/{story.id}",
                      title=f"Source title for {headline}", raw_hash=str(story.id), ingest_status="REVIEW")
    db.add(item)
    db.flush()
    db.add(StorySource(story_id=story.id, source_item_id=item.id, role="PRIMARY", evidence_rank=1))
    created = NOW - timedelta(hours=age_hours)
    db.add(StoryVariant(story_id=story.id, language="en", headline=headline, summary="s", qa_status="PASSED",
                        generated_at=created))
    if te is not None:
        db.add(StoryVariant(story_id=story.id, language="te", headline="తెలుగు", summary="s", qa_status=te,
                            generated_at=created))
    if topic is not None:
        db.add(StoryTopic(story_id=story.id, topic_id=topic.id))
    if reason is not None:
        db.add(ReviewTask(story_id=story.id, reason=reason, status="PENDING", created_at=created))
    db.flush()
    return story


def _queue(client, token, source, **params):  # noqa: F811
    response = client.get("/v1/admin/review-queue", params={"source_id": str(source.id), **params}, headers=_auth(token))
    assert response.status_code == 200, response.text
    return response.json()


def test_queue_pages_danger_first_then_oldest_without_skipping(client, db_session):  # noqa: F811
    token = _token(client, db_session)
    source = _source(db_session)
    routine_old = _story(db_session, source, reason="AUTO_PUBLISH_DISABLED", age_hours=30)
    legal = _story(db_session, source, reason="LEGAL", age_hours=2)
    routine_new = _story(db_session, source, reason="LOW_CONFIDENCE_GENERATION", age_hours=1)
    breaking = _story(db_session, source, reason="HIGH_IMPORTANCE, BREAKING", age_hours=5)
    routine_mid = _story(db_session, source, reason="SIMILARITY_TO_SOURCE", age_hours=10)
    db_session.commit()

    first = _queue(client, token, source, limit=2)
    assert first["total"] == 5
    assert first["pending_total"] >= 5 and first["danger_total"] >= 2
    seen = [row["story_id"] for row in first["items"]]
    assert seen == [str(breaking.id), str(legal.id)]

    # A reviewer resolves a row they already saw; the next page neither skips nor repeats.
    task = db_session.query(ReviewTask).filter_by(story_id=legal.id).one()
    task.status = "APPROVED"
    db_session.commit()
    cursor = first["next_cursor"]
    while cursor:
        page = _queue(client, token, source, limit=2, cursor=cursor)
        seen += [row["story_id"] for row in page["items"]]
        cursor = page["next_cursor"]
    assert seen == [str(s.id) for s in (breaking, legal, routine_old, routine_mid, routine_new)]


def test_queue_filters(client, db_session):  # noqa: F811
    token = _token(client, db_session)
    source = _source(db_session)
    topic = Topic(slug=f"t-{uuid.uuid4().hex[:8]}", name="Test topic")
    db_session.add(topic)
    db_session.flush()
    visa = _story(db_session, source, headline="Visa fee rises", reason="IMMIGRATION", age_hours=50, te="PASSED", topic=topic)
    unclassified = _story(db_session, source, headline="Budget session", reason="NO_PAID_PROVIDER", age_hours=3, te="FAILED")
    plain = _story(db_session, source, headline="Cricket result", reason="AUTO_PUBLISH_DISABLED", age_hours=1)
    db_session.commit()

    def ids(**params):
        return {row["story_id"] for row in _queue(client, token, source, **params)["items"]}

    assert ids(danger_only=True) == {str(visa.id)}
    assert ids(reason="NO_PAID_PROVIDER") == {str(unclassified.id)}
    assert ids(older_than_hours=24) == {str(visa.id)}
    assert ids(telugu="MISSING") == {str(plain.id)}
    assert ids(telugu="FAILED") == {str(unclassified.id)}
    assert ids(topic=topic.slug) == {str(visa.id)}
    assert ids(q="visa FEE") == {str(visa.id)}
    assert ids(q="Source title for Cricket") == {str(plain.id)}
    assert ids(q="100%_") == set()
    row = next(r for r in _queue(client, token, source)["items"] if r["story_id"] == str(visa.id))
    assert (row["topics"], row["te_qa_status"], row["source_names"]) == ([topic.slug], "PASSED", [source.name])

    bad = client.get("/v1/admin/review-queue", params={"cursor": "not-a-cursor"}, headers=_auth(token))
    assert (bad.status_code, bad.json()["error"]["code"]) == (422, "INVALID_CURSOR")
    assert client.get("/v1/admin/review-queue").status_code == 401


def test_library_lists_every_status_by_last_activity(client, db_session):  # noqa: F811
    token = _token(client, db_session)
    source = _source(db_session)
    live = _story(db_session, source, status="PUBLISHED", published_at=NOW - timedelta(minutes=5), te="PASSED")
    corrected = _story(db_session, source, status="PUBLISHED", published_at=NOW - timedelta(days=2))
    db_session.add(Correction(story_id=corrected.id, reason="date fix", old_text_hash="a", new_text_hash="b"))
    draft = _story(db_session, source, status="REVIEW_REQUIRED", reason="LEGAL", age_hours=1)
    retracted = _story(db_session, source, status="RETRACTED", published_at=NOW - timedelta(days=5))
    db_session.commit()

    def get(**params):
        response = client.get("/v1/admin/stories", params={"source_id": str(source.id), **params}, headers=_auth(token))
        assert response.status_code == 200, response.text
        return response.json()

    everything = get()
    assert everything["total"] == 4
    assert [row["id"] for row in everything["items"]] == [str(s.id) for s in (live, draft, corrected, retracted)]
    by_id = {row["id"]: row for row in everything["items"]}
    assert by_id[str(draft.id)]["review_pending"] is True
    assert by_id[str(corrected.id)]["corrections"] == 1
    assert by_id[str(live.id)]["te_qa_status"] == "PASSED"
    assert everything["status_counts"]["PUBLISHED"] >= 2 and everything["corrected_total"] >= 1

    assert [row["id"] for row in get(status="RETRACTED")["items"]] == [str(retracted.id)]
    assert [row["id"] for row in get(corrected=True)["items"]] == [str(corrected.id)]
    assert {row["id"] for row in get(telugu="MISSING")["items"]} == {str(corrected.id), str(draft.id), str(retracted.id)}
    paged = get(limit=2, offset=2)
    assert paged["total"] == 4 and [row["id"] for row in paged["items"]] == [str(corrected.id), str(retracted.id)]
    assert client.get("/v1/admin/stories", params={"status": "NOPE"}, headers=_auth(token)).status_code == 422


def test_audit_history_filters_and_pages_past_200(client, db_session):  # noqa: F811
    token = _token(client, db_session)
    entity = uuid.uuid4()
    for i in range(205):
        db_session.add(AuditEvent(
            actor="editor@example.com" if i % 2 else "job:brief_lane", action="STORY_APPROVED" if i % 5 else "STORY_RETRACTED",
            entity_type="story", entity_id=entity, metadata_={"i": i}, created_at=NOW - timedelta(minutes=i),
        ))
    db_session.commit()

    def get(**params):
        response = client.get("/v1/admin/audit", params={"entity_id": str(entity), **params}, headers=_auth(token))
        assert response.status_code == 200, response.text
        return response.json()

    seen, cursor = [], None
    while True:
        page = get(limit=200, **({"cursor": cursor} if cursor else {}))
        seen += [row["metadata"]["i"] for row in page["items"]]
        cursor = page["next_cursor"]
        if not cursor:
            break
    assert seen == list(range(205))
    assert {row["metadata"]["i"] for row in get(action="STORY_RETRACTED")["items"]} == set(range(0, 205, 5))
    assert all(row["actor"] == "editor@example.com" for row in get(actor="EDITOR@")["items"])
    window = get(since=(NOW - timedelta(minutes=10)).isoformat(), until=(NOW - timedelta(minutes=4)).isoformat())
    assert [row["metadata"]["i"] for row in window["items"]] == list(range(5, 11))
