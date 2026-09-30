"""Review 2026-09-29 #7: source rights are rechecked at every approval and
publication transition, not only at ingest."""

from sqlalchemy import select

from app.jobs.publish import (
    RIGHTS_HOLD_ACTION,
    auto_publish_stories,
    publish_due_stories,
)
from app.models import AuditEvent, ReviewTask, Source

from .test_brief_lane import _brief, _fake, _story, lane_on  # noqa: F401  (fixture)
from .test_editorial_workflow import _auth, _token, client  # noqa: F401  (fixture)


def _set_rights(db, item, rights_status="DISABLED", **fields):
    source = db.get(Source, item.source_id)
    source.rights_status = rights_status
    for key, value in fields.items():
        setattr(source, key, value)
    db.commit()


def _reason(db, story):
    return db.scalars(select(ReviewTask.reason).where(ReviewTask.story_id == story.id)).first()


def test_global_auto_publish_holds_story_whose_source_was_disabled(db_session, monkeypatch):
    monkeypatch.setenv("AUTO_PUBLISH_GLOBAL", "true")
    story, item = _story(db_session)
    _set_rights(db_session, item)

    auto_publish_stories(db_session)
    db_session.refresh(story)
    assert story.status == "REVIEW_REQUIRED"
    assert _reason(db_session, story) == "SOURCE_RIGHTS_REVOKED"


def test_brief_lane_is_not_tried_for_a_disabled_source(db_session, lane_on, monkeypatch):  # noqa: F811
    story, item = _story(db_session)
    _set_rights(db_session, item)
    _fake(monkeypatch, [])  # no AI call expected

    auto_publish_stories(db_session)
    db_session.refresh(story)
    assert story.status == "REVIEW_REQUIRED"
    assert _reason(db_session, story) == "SOURCE_RIGHTS_REVOKED"


def test_scheduled_story_is_not_published_after_its_source_is_disabled(db_session, lane_on, monkeypatch):  # noqa: F811
    story, item = _story(db_session)
    _fake(monkeypatch, [_brief(item.id)])
    auto_publish_stories(db_session)
    db_session.refresh(story)
    assert story.status == "SCHEDULED"

    _set_rights(db_session, item)
    assert publish_due_stories(db_session) == 0
    assert publish_due_stories(db_session) == 0
    db_session.refresh(story)
    assert story.status == "SCHEDULED"
    holds = db_session.scalars(
        select(AuditEvent).where(AuditEvent.entity_id == story.id, AuditEvent.action == RIGHTS_HOLD_ACTION)
    ).all()
    assert len(holds) == 1  # audited once, not every sweep

    _set_rights(db_session, item, "LINK_ONLY")  # rights restored
    assert publish_due_stories(db_session) == 1


def test_inactive_source_keeps_its_rights(db_session, lane_on, monkeypatch):  # noqa: F811
    _story_row, item = _story(db_session)
    _fake(monkeypatch, [_brief(item.id)])
    auto_publish_stories(db_session)
    _set_rights(db_session, item, "LINK_ONLY", active=False)
    assert publish_due_stories(db_session) == 1


def test_admin_approve_rechecks_rights(client, db_session):  # noqa: F811
    token = _token(client, db_session)
    story, item = _story(db_session)
    story.status = "REVIEW_REQUIRED"
    db_session.commit()
    _set_rights(db_session, item)

    response = client.post(f"/v1/admin/stories/{story.id}/approve", json={}, headers=_auth(token))
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "SOURCE_RIGHTS_REVOKED"
    db_session.refresh(story)
    assert story.status == "REVIEW_REQUIRED"

    _set_rights(db_session, item, "LINK_ONLY")
    response = client.post(f"/v1/admin/stories/{story.id}/approve", json={}, headers=_auth(token))
    assert response.status_code == 200
