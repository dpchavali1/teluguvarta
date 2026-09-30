"""ADR-025: audited, bounded ADMIN recovery of stories held by AI failures."""

import uuid

from sqlalchemy import select

from app.models import (
    AiWorkState,
    AuditEvent,
    ReviewTask,
    Source,
    SourceItem,
    Story,
    StorySource,
)
from tests.conftest import requires_postgres
from tests.test_editorial_workflow import (  # noqa: F401  (fixtures)
    _auth,
    _make_review_required_story,
    _token,
    client,
    db_session,
)

pytestmark = requires_postgres


def _held_story(db, *, reason="AI_RETRIES_EXHAUSTED"):
    story = _make_review_required_story(db)
    task = db.scalars(select(ReviewTask).where(ReviewTask.story_id == story.id)).one()
    task.reason = reason
    source = Source(name=f"src-{uuid.uuid4()}", rights_status="LINK_ONLY", active=True)
    db.add(source)
    db.flush()
    item = SourceItem(
        source_id=source.id, external_id=str(uuid.uuid4()), url="https://example.org/a",
        title="A title", raw_hash=uuid.uuid4().hex, ingest_status="REVIEW",
    )
    db.add(item)
    db.flush()
    db.add(StorySource(story_id=story.id, source_item_id=item.id, role="PRIMARY", evidence_rank=1))
    db.add(AiWorkState(story_id=story.id, stage="GENERATE", input_version="v1", failure_class="EXHAUSTED", last_status="UNAVAILABLE"))
    db.commit()
    return story, item


def _retry(api, token, story, stage="GENERATE", reason="provider back up"):
    return api.post(
        f"/v1/admin/stories/{story.id}/retry-ai", json={"stage": stage, "reason": reason}, headers=_auth(token)
    )


def test_retry_generation_sends_story_back_through_ai_and_audits(client, db_session):  # noqa: F811
    token = _token(client, db_session)
    story, item = _held_story(db_session)

    response = _retry(client, token, story)

    assert response.status_code == 200
    assert response.json()["status"] == "DRAFT"
    db_session.expire_all()
    assert db_session.get(SourceItem, item.id).ingest_status == "CLUSTERED"
    assert db_session.scalars(select(AiWorkState).where(AiWorkState.story_id == story.id)).first() is None
    assert db_session.scalars(select(ReviewTask).where(ReviewTask.story_id == story.id)).one().status == "REJECTED"
    event = db_session.scalars(
        select(AuditEvent).where(AuditEvent.entity_id == story.id, AuditEvent.action == "AI_RETRY_RESET")
    ).one()
    assert event.metadata_ == {"stage": "GENERATE", "reason": "provider back up", "reset_number": 1}


def test_retry_is_capped_at_two_resets(client, db_session):  # noqa: F811
    token = _token(client, db_session)
    story, _ = _held_story(db_session)
    for number in (1, 2):
        db_session.add(AuditEvent(actor="x", action="AI_RETRY_RESET", entity_type="story", entity_id=story.id, metadata_={"stage": "GENERATE", "reset_number": number}))
    db_session.commit()

    response = _retry(client, token, story)

    assert response.status_code == 409
    assert "RETRY_LIMIT_REACHED" in str(response.json())


def test_editor_cannot_retry(client, db_session):  # noqa: F811
    token = _token(client, db_session, role="EDITOR", email="editor@example.com")
    story, _ = _held_story(db_session)

    assert _retry(client, token, story).status_code == 403


def test_editorial_hold_is_not_retryable(client, db_session):  # noqa: F811
    token = _token(client, db_session)
    story = _make_review_required_story(db_session)  # reason TEST_SETUP, no AI state

    response = _retry(client, token, story)

    assert response.status_code == 409
    assert "NOT_AI_HELD" in str(response.json())


def test_exhausted_translation_is_listed_and_can_be_retried(client, db_session):  # noqa: F811
    token = _token(client, db_session)
    story = _make_review_required_story(db_session)
    db_session.add(AiWorkState(story_id=story.id, stage="TRANSLATE", input_version="v1", failure_class="EXHAUSTED", last_status="HOLD"))
    db_session.commit()

    holds = client.get("/v1/admin/ai-holds", headers=_auth(token)).json()
    hold = next(h for h in holds if h["story_id"] == str(story.id))
    assert (hold["stage"], hold["headline"], hold["resets_left"]) == ("TRANSLATE", "Old headline", 2)

    response = _retry(client, token, story, stage="TRANSLATE")

    assert response.status_code == 200
    db_session.expire_all()
    assert db_session.get(Story, story.id).status == "REVIEW_REQUIRED"
    assert db_session.scalars(select(AiWorkState).where(AiWorkState.story_id == story.id)).first() is None
