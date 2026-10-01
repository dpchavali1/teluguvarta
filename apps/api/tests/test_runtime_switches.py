"""ADR-031: dashboard pause switches for AI and auto-publish, and stale
expiry of stories queued only because auto-publish was off."""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.ai import AiGateway, GatewayStatus, Task
from app.jobs.publish import auto_publish_stories, expire_stale_holds
from app.jobs.queue import enqueue_job
from app.jobs.worker import process_one
from app.models import AuditEvent, Job, ReviewTask, Story, StoryVariant, User
from app.switches import is_on, set_switch
from tests.admin_session_helpers import admin_auth, admin_session_token
from tests.conftest import requires_postgres

pytestmark = requires_postgres

GOOD_SUMMARY = (
    "The county opened two new cooling centres on Tuesday as temperatures climbed. "
    "Officials said the centres will stay open through the weekend for anyone who needs them."
)


def _story(db, *, status="AI_READY", age_hours=1.0, sensitivity="NONE") -> Story:
    story = Story(canonical_slug=f"story-{uuid.uuid4()}", status="AI_READY", sensitivity=sensitivity)
    db.add(story)
    db.flush()
    db.add(StoryVariant(
        story_id=story.id, language="en", headline="Cooling centres open across the county",
        summary=GOOD_SUMMARY, generated_at=datetime.now(UTC) - timedelta(hours=age_hours),
    ))
    if status == "REVIEW_REQUIRED":
        story.status = "REVIEW_REQUIRED"
        db.flush()
        db.add(ReviewTask(story_id=story.id, reason="AUTO_PUBLISH_DISABLED", status="PENDING"))
    db.commit()
    return story


def _task(db, story) -> ReviewTask:
    return db.scalars(select(ReviewTask).where(ReviewTask.story_id == story.id)).one()


def _admin(client, db, role="ADMIN"):
    from app.security import hash_password

    user = User(id=uuid.uuid4(), email=f"{role.lower()}@example.com", role=role, password_hash=hash_password("pw-long-enough"))
    db.add(user)
    db.commit()
    return admin_auth(admin_session_token(db, user.id))


# --- auto-publish switch -----------------------------------------------------


def test_auto_publish_paused_holds_stories_in_ai_ready_without_queueing(db_session, monkeypatch):
    monkeypatch.setenv("AUTO_PUBLISH_GLOBAL", "true")
    set_switch(db_session, "auto_publish", False, "admin@example.com", None)
    db_session.commit()
    story = _story(db_session)

    assert auto_publish_stories(db_session) == 0
    db_session.refresh(story)
    assert story.status == "AI_READY"
    assert db_session.scalars(select(ReviewTask).where(ReviewTask.story_id == story.id)).first() is None

    set_switch(db_session, "auto_publish", True, "admin@example.com", None)
    db_session.commit()
    auto_publish_stories(db_session)
    db_session.refresh(story)
    assert story.status == "SCHEDULED"


def test_env_off_is_a_ceiling_the_dashboard_cannot_lift(db_session, monkeypatch):
    monkeypatch.setenv("AUTO_PUBLISH_GLOBAL", "false")
    set_switch(db_session, "auto_publish", True, "admin@example.com", None)
    db_session.commit()
    assert is_on(db_session, "auto_publish") is False


def test_stale_ai_ready_story_is_archived_on_resume(db_session, monkeypatch):
    monkeypatch.setenv("AUTO_PUBLISH_GLOBAL", "true")
    story = _story(db_session, age_hours=30)

    auto_publish_stories(db_session)
    db_session.refresh(story)
    assert story.status == "ARCHIVED"
    task = _task(db_session, story)
    assert (task.status, task.decision) == ("REJECTED", "STALE")
    assert db_session.scalars(
        select(AuditEvent).where(AuditEvent.entity_id == story.id, AuditEvent.action == "STORY_EXPIRED_STALE")
    ).first() is not None


# --- backlog re-sweep -----------------------------------------------------------


def test_backlog_queued_only_for_switch_is_published_when_fresh_and_archived_when_stale(db_session, monkeypatch):
    monkeypatch.setenv("AUTO_PUBLISH_GLOBAL", "true")
    fresh = _story(db_session, status="REVIEW_REQUIRED", age_hours=2)
    stale = _story(db_session, status="REVIEW_REQUIRED", age_hours=72)

    auto_publish_stories(db_session)
    for s in (fresh, stale):
        db_session.refresh(s)
    assert fresh.status == "SCHEDULED"
    assert _task(db_session, fresh).status == "APPROVED"
    assert stale.status == "ARCHIVED"
    assert _task(db_session, stale).decision == "STALE"


def test_backlog_resweep_leaves_editorial_holds_alone(db_session, monkeypatch):
    monkeypatch.setenv("AUTO_PUBLISH_GLOBAL", "true")
    sensitive = _story(db_session, status="REVIEW_REQUIRED", age_hours=2, sensitivity="IMMIGRATION")
    other = _story(db_session, age_hours=2)
    other.status = "REVIEW_REQUIRED"
    db_session.flush()
    db_session.add(ReviewTask(story_id=other.id, reason="LOW_CONFIDENCE", status="PENDING"))
    db_session.commit()

    auto_publish_stories(db_session)
    for s in (sensitive, other):
        db_session.refresh(s)
        assert s.status == "REVIEW_REQUIRED"
        assert _task(db_session, s).status == "PENDING"


def test_backlog_failing_content_rules_is_retagged_with_the_real_reason(db_session, monkeypatch):
    monkeypatch.setenv("AUTO_PUBLISH_GLOBAL", "true")
    story = _story(db_session, status="REVIEW_REQUIRED", age_hours=2)
    en = db_session.scalars(select(StoryVariant).where(StoryVariant.story_id == story.id)).one()
    en.summary = "Too short."
    db_session.commit()

    auto_publish_stories(db_session)
    db_session.refresh(story)
    task = _task(db_session, story)
    assert story.status == "REVIEW_REQUIRED"
    assert task.status == "PENDING"
    assert task.reason.startswith("CONTENT_RULES_FAILED:")


def test_backlog_stays_queued_while_env_flag_is_off(db_session, monkeypatch):
    monkeypatch.setenv("AUTO_PUBLISH_GLOBAL", "false")
    story = _story(db_session, status="REVIEW_REQUIRED", age_hours=2)

    auto_publish_stories(db_session)
    db_session.refresh(story)
    assert story.status == "REVIEW_REQUIRED"


# --- ADR-032: every stale hold expires -------------------------------------------


def _hold(db, story, reason):
    story.status = "REVIEW_REQUIRED"
    db.flush()
    db.add(ReviewTask(story_id=story.id, reason=reason, status="PENDING"))
    db.commit()


def _expired_audits(db, story, action="STORY_EXPIRED_STALE"):
    return db.scalars(
        select(AuditEvent).where(AuditEvent.entity_id == story.id, AuditEvent.action == action)
    ).all()


def test_stale_editorial_holds_are_archived_whatever_the_switches_say(db_session, monkeypatch):
    monkeypatch.setenv("AUTO_PUBLISH_GLOBAL", "false")
    set_switch(db_session, "auto_publish", False, "admin@example.com", None)
    db_session.commit()
    sensitive = _story(db_session, age_hours=30, sensitivity="IMMIGRATION")
    _hold(db_session, sensitive, "SENSITIVE_CATEGORY")
    low = _story(db_session, age_hours=30)
    _hold(db_session, low, "LOW_CONFIDENCE_GENERATION")
    fresh = _story(db_session, age_hours=2)
    _hold(db_session, fresh, "LOW_CONFIDENCE_GENERATION")

    assert auto_publish_stories(db_session) == 2
    for story, reason in ((sensitive, "SENSITIVE_CATEGORY"), (low, "LOW_CONFIDENCE_GENERATION")):
        db_session.refresh(story)
        task = _task(db_session, story)
        assert story.status == "ARCHIVED"
        assert (task.status, task.decision) == ("REJECTED", "STALE")
        [audit] = _expired_audits(db_session, story)
        assert audit.metadata_["reasons"] == [reason]
    db_session.refresh(fresh)
    assert fresh.status == "REVIEW_REQUIRED"
    assert _task(db_session, fresh).status == "PENDING"


def test_hold_without_a_draft_ages_from_when_it_was_queued(db_session):
    story = Story(canonical_slug=f"story-{uuid.uuid4()}", status="AI_READY", sensitivity="NONE")
    db_session.add(story)
    db_session.flush()
    _hold(db_session, story, "NO_PAID_PROVIDER")
    task = _task(db_session, story)

    expire_stale_holds(db_session)
    assert task.status == "PENDING"

    task.created_at = datetime.now(UTC) - timedelta(hours=30)
    db_session.commit()
    expire_stale_holds(db_session)
    db_session.refresh(story)
    assert story.status == "ARCHIVED"
    assert task.decision == "STALE"


def test_stale_task_on_a_published_story_is_closed_without_unpublishing(db_session):
    story = _story(db_session, age_hours=30)
    for status in ("REVIEW_REQUIRED", "APPROVED", "SCHEDULED", "PUBLISHED"):
        story.status = status
        db_session.flush()
    story.published_at = datetime.now(UTC)
    db_session.add(ReviewTask(story_id=story.id, reason="TELUGU_TRANSLATION_SAMPLE_REVIEW", status="PENDING"))
    db_session.commit()

    assert expire_stale_holds(db_session) == 1
    db_session.refresh(story)
    assert story.status == "PUBLISHED"
    assert _task(db_session, story).decision == "STALE"
    assert _expired_audits(db_session, story) == []
    assert len(_expired_audits(db_session, story, "REVIEW_TASK_EXPIRED_STALE")) == 1


# --- AI switch -------------------------------------------------------------------


def test_ai_paused_gateway_defers_without_calling_a_provider(db_session):
    set_switch(db_session, "ai", False, "admin@example.com", None)
    db_session.commit()
    outcome = AiGateway(db_session).run_task(Task.DEDUP_CLUSTER_ESCALATION, "prompt")
    assert outcome.status == GatewayStatus.DEFERRED


def test_ai_paused_worker_leaves_ai_jobs_queued(db_session, monkeypatch):
    for name in ("schedule_due_source_fetches", "schedule_due_x_fetches", "schedule_dedup_cluster",
                 "schedule_publish_scheduler", "schedule_notification_dispatch", "schedule_cleanup"):
        monkeypatch.setattr(f"app.jobs.worker.{name}", lambda db: None)
    set_switch(db_session, "ai", False, "admin@example.com", None)
    job = enqueue_job(db_session, "ai_translate", {}, dedupe_key=f"t-{uuid.uuid4()}")
    db_session.commit()

    assert process_one(db_session) is False
    db_session.refresh(job)
    assert job.status == "PENDING"
    assert db_session.scalars(select(Job).where(Job.type == "ai_classify")).first() is None


# --- admin API -------------------------------------------------------------------


def test_admin_can_pause_and_resume_with_audit(client, db_session):
    headers = _admin(client, db_session)
    _story(db_session)

    rows = client.get("/v1/admin/switches", headers=headers).json()
    assert {r["key"]: r["enabled"] for r in rows} == {"ai": True, "auto_publish": True}

    res = client.put("/v1/admin/switches/ai", json={"enabled": False, "note": "spend check"}, headers=headers)
    assert res.status_code == 200
    body = res.json()
    assert body["enabled"] is False and body["effective"] is False and body["note"] == "spend check"

    auto = next(r for r in client.get("/v1/admin/switches", headers=headers).json() if r["key"] == "auto_publish")
    assert auto["waiting"] == 1

    event = db_session.scalars(select(AuditEvent).where(AuditEvent.action == "RUNTIME_SWITCH_CHANGED")).one()
    assert event.metadata_ == {"key": "ai", "from": True, "to": False, "note": "spend check"}


def test_editor_cannot_flip_a_switch(client, db_session):
    headers = _admin(client, db_session, role="EDITOR")
    res = client.put("/v1/admin/switches/auto_publish", json={"enabled": False}, headers=headers)
    assert res.status_code == 403
