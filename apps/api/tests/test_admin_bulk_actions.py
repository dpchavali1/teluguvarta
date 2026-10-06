"""ADR-055: bulk story actions, clearing the review queue, restore, and
hard delete of stories and sources."""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.models import (
    AuditEvent,
    Job,
    ReviewTask,
    Source,
    SourceItem,
    Story,
    StorySource,
)
from tests.conftest import requires_postgres
from tests.test_editorial_workflow import (
    _auth,
    _make_review_required_story,
    _publish,
    _token,
)

pytestmark = requires_postgres


@pytest.fixture
def client(migrated_database, monkeypatch):
    monkeypatch.setenv("ADMIN_JWT_SECRET", "test-secret")

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


def _audit(db, story_id, action):
    return db.scalars(select(AuditEvent).where(AuditEvent.entity_id == story_id, AuditEvent.action == action)).all()


def test_bulk_archive_skips_ineligible_and_audits_each(client, db_session):
    token = _token(client, db_session)
    a, b = _make_review_required_story(db_session), _make_review_required_story(db_session)
    live = _make_review_required_story(db_session)
    _publish(db_session, live)
    missing = uuid.uuid4()

    response = client.post(
        "/v1/admin/stories/bulk",
        json={"action": "archive", "story_ids": [str(a.id), str(b.id), str(live.id), str(missing)], "reason": "spam"},
        headers=_auth(token),
    )
    assert response.status_code == 200
    body = response.json()
    assert set(body["done"]) == {str(a.id), str(b.id)}
    assert {s["code"] for s in body["skipped"]} == {"ILLEGAL_TRANSITION", "STORY_NOT_FOUND"}

    db_session.expire_all()
    assert db_session.get(Story, a.id).status == "ARCHIVED"
    assert db_session.get(Story, live.id).status == "PUBLISHED"
    assert len(_audit(db_session, a.id, "STORY_REJECTED")) == 1


def test_bulk_retract_then_restore_goes_back_to_review(client, db_session):
    token = _token(client, db_session)
    story = _make_review_required_story(db_session)
    _publish(db_session, story)

    response = client.post(
        "/v1/admin/stories/bulk", json={"action": "retract", "story_ids": [str(story.id)]}, headers=_auth(token)
    )
    assert response.json()["done"] == [str(story.id)]

    response = client.post(f"/v1/admin/stories/{story.id}/restore", json={"reason": "mistake"}, headers=_auth(token))
    assert response.status_code == 200
    assert response.json()["status"] == "REVIEW_REQUIRED"
    task = db_session.scalars(
        select(ReviewTask).where(ReviewTask.story_id == story.id, ReviewTask.status == "PENDING")
    ).one()
    assert task.reason == "RESTORED"


def test_restore_refuses_live_story(client, db_session):
    token = _token(client, db_session)
    story = _make_review_required_story(db_session)
    response = client.post(f"/v1/admin/stories/{story.id}/restore", json={}, headers=_auth(token))
    assert response.status_code == 409


def test_delete_story_is_admin_only_and_keeps_audit(client, db_session):
    editor = _token(client, db_session, role="EDITOR", email="editor@example.com")
    admin = _token(client, db_session)
    story = _make_review_required_story(db_session)
    _publish(db_session, story)

    assert client.post(
        f"/v1/admin/stories/{story.id}/delete", json={"reason": "legal"}, headers=_auth(editor)
    ).status_code == 403
    assert client.post(f"/v1/admin/stories/{story.id}/delete", json={"reason": ""}, headers=_auth(admin)).status_code == 422

    response = client.post(f"/v1/admin/stories/{story.id}/delete", json={"reason": "legal"}, headers=_auth(admin))
    assert response.status_code == 204
    story_id = story.id
    db_session.expire_all()
    assert db_session.get(Story, story_id) is None
    [event] = _audit(db_session, story_id, "STORY_DELETED")
    assert event.metadata_["headline"] == "Old headline"
    assert event.metadata_["status"] == "PUBLISHED"


def test_bulk_delete_needs_admin_and_reason(client, db_session):
    editor = _token(client, db_session, role="EDITOR", email="editor@example.com")
    admin = _token(client, db_session)
    story = _make_review_required_story(db_session)
    ids = [str(story.id)]

    assert client.post(
        "/v1/admin/stories/bulk", json={"action": "delete", "story_ids": ids, "reason": "x"}, headers=_auth(editor)
    ).status_code == 403
    assert client.post(
        "/v1/admin/stories/bulk", json={"action": "delete", "story_ids": ids}, headers=_auth(admin)
    ).status_code == 422
    response = client.post(
        "/v1/admin/stories/bulk", json={"action": "delete", "story_ids": ids, "reason": "junk"}, headers=_auth(admin)
    )
    assert response.json()["done"] == ids
    db_session.expire_all()
    assert db_session.get(Story, uuid.UUID(ids[0])) is None


def test_clear_queue_archives_matching_pending_only(client, db_session):
    editor = _token(client, db_session, role="EDITOR", email="editor@example.com")
    admin = _token(client, db_session)
    stories = [_make_review_required_story(db_session) for _ in range(3)]
    immigration = _make_review_required_story(db_session, sensitivity="IMMIGRATION")
    live = _make_review_required_story(db_session)
    _publish(db_session, live)

    assert client.post("/v1/admin/review-queue/clear", json={"reason": "flood"}, headers=_auth(editor)).status_code == 403

    response = client.post("/v1/admin/review-queue/clear", json={"reason": "flood"}, headers=_auth(admin))
    assert response.status_code == 200
    body = response.json()
    assert body == {"cleared": 4, "remaining": 0, "outcome": "ARCHIVED"}

    db_session.expire_all()
    assert {db_session.get(Story, s.id).status for s in [*stories, immigration]} == {"ARCHIVED"}
    assert db_session.get(Story, live.id).status == "PUBLISHED"
    assert client.get("/v1/admin/review-queue", headers=_auth(admin)).json()["pending_total"] == 0


def test_clear_queue_respects_filters(client, db_session):
    admin = _token(client, db_session)
    plain = _make_review_required_story(db_session)
    immigration = _make_review_required_story(db_session, sensitivity="IMMIGRATION")
    db_session.execute(
        ReviewTask.__table__.update().where(ReviewTask.story_id == immigration.id).values(reason="IMMIGRATION")
    )
    db_session.commit()

    response = client.post(
        "/v1/admin/review-queue/clear",
        json={"reason": "drop", "review_reason": "IMMIGRATION", "archive": False},
        headers=_auth(admin),
    )
    assert response.json() == {"cleared": 1, "remaining": 0, "outcome": "DRAFT"}
    db_session.expire_all()
    assert db_session.get(Story, immigration.id).status == "DRAFT"
    assert db_session.get(Story, plain.id).status == "REVIEW_REQUIRED"


def _source(db, name="Feed"):
    source = Source(name=name, base_url="https://example.com", feed_url=f"https://example.com/{uuid.uuid4()}.xml",
                    source_type="RSS", country="US", language="en")
    db.add(source)
    db.flush()
    return source


def test_delete_source_refused_while_stories_cite_it(client, db_session):
    admin = _token(client, db_session)
    source = _source(db_session)
    source_id = source.id
    item = SourceItem(source_id=source.id, external_id="1", url="https://example.com/1", title="t", raw_hash="h")
    db_session.add(item)
    story = _make_review_required_story(db_session)
    db_session.add(StorySource(story_id=story.id, source_item_id=item.id, role="PRIMARY", evidence_rank=1))
    db_session.commit()

    response = client.post(f"/v1/admin/sources/{source.id}/delete", json={"reason": "gone"}, headers=_auth(admin))
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "SOURCE_HAS_STORIES"

    # Delete the citing story first; then the source goes.
    client.post(f"/v1/admin/stories/{story.id}/delete", json={"reason": "gone"}, headers=_auth(admin))
    response = client.post(f"/v1/admin/sources/{source.id}/delete", json={"reason": "gone"}, headers=_auth(admin))
    assert response.status_code == 200
    assert response.json()["deleted_items"] == 1
    db_session.expire_all()
    assert db_session.get(Source, source_id) is None
    assert _audit(db_session, source_id, "SOURCE_DELETED")


def test_delete_source_admin_only_and_drops_queued_fetch(client, db_session):
    editor = _token(client, db_session, role="EDITOR", email="editor@example.com")
    admin = _token(client, db_session)
    source = _source(db_session)
    source_id = str(source.id)
    db_session.add(Job(type="source_fetch", payload={"source_id": str(source.id)}))
    db_session.commit()

    assert client.post(
        f"/v1/admin/sources/{source.id}/delete", json={"reason": "x"}, headers=_auth(editor)
    ).status_code == 403
    assert client.post(
        f"/v1/admin/sources/{source.id}/delete", json={"reason": "x"}, headers=_auth(admin)
    ).status_code == 200
    db_session.expire_all()
    assert not db_session.scalars(select(Job).where(Job.payload["source_id"].astext == source_id)).all()
