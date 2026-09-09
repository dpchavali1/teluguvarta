"""T12's `publish_scheduler` job (reserved in T03's `ck_jobs_type` since the
initial schema, unimplemented until now): the auto-publish path for T11's
`AI_READY` output, gated by the §15 kill switches, plus the always-on
promotion of already-*approved* stories (manual or automatic) to `PUBLISHED`.

Two responsibilities, one job type, same "combine adjacent pipeline stages
with no independent retry value" precedent as T08/T09/T11:

1. `auto_publish_stories` — sweeps `Story.status == AI_READY` (T11 leaves
   every P2, non-sensitive story here). If `AUTO_PUBLISH_GLOBAL` is off,
   nothing here should silently rot forever: each is pushed to
   `REVIEW_REQUIRED` with a `ReviewTask` so an editor sees it in the queue
   and can approve it by hand. If the flag is on, each is auto-approved
   (`REVIEW_REQUIRED -> APPROVED -> SCHEDULED`) and a `system` `AuditEvent`
   is written — no exceptions per the audit-trail requirement. Defense in
   depth (matching T08's rights-gate double-check): any story whose
   `sensitivity != NONE` is *never* auto-approved even if it somehow reached
   `AI_READY`, full stop, regardless of the flag — NON_NEGOTIABLES #5 has no
   auto-publish override. `AUTO_PUBLISH_CATEGORY_IMMIGRATION` is
   deliberately never read here: T11 never lets an IMMIGRATION story reach
   `AI_READY` in the first place (always routed straight to
   `REVIEW_REQUIRED`), so gating on that flag would be dead code — this *is*
   the "should be a no-op" acceptance criterion, satisfied structurally.
2. `publish_due_stories` — promotes every `Story.status == SCHEDULED` (from
   either path above, or a human editor's `POST .../approve`, which itself
   already cascades `REVIEW_REQUIRED -> APPROVED -> SCHEDULED` per the
   ticket text) to `PUBLISHED`, stamping `published_at`. This step is
   intentionally *not* gated by `AUTO_PUBLISH_GLOBAL` — the approve decision
   (human or automatic) already happened; this only finishes moving an
   approved story live, which must keep working even with the global switch
   off, or a human editor's approvals would silently never publish.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.budget import is_over_monthly_budget
from app.jobs.queue import enqueue_job
from app.models import AuditEvent, Job, ReviewTask, Story

SCHEDULE_INTERVAL_MINUTES = 2

AUTO_PUBLISH_GLOBAL_ENV = "AUTO_PUBLISH_GLOBAL"
AUTO_PUBLISH_DISABLE_ON_BUDGET_BREACH_ENV = "AUTO_PUBLISH_DISABLE_ON_BUDGET_BREACH"


def _now() -> datetime:
    return datetime.now(UTC)


def _auto_publish_enabled() -> bool:
    return os.environ.get(AUTO_PUBLISH_GLOBAL_ENV, "false").lower() == "true"


def _budget_breach_disables_auto_publish(db: Session) -> bool:
    """§19: `AUTO_PUBLISH_DISABLE_ON_BUDGET_BREACH` — once `MONTHLY_AI_BUDGET_USD`
    is crossed, auto-publish stops (falls back to the review queue, same as
    `AUTO_PUBLISH_GLOBAL` off) until an operator raises the budget or a new
    month resets it. Defaults to enabled: a cost breach should fail toward
    "more human review", not toward "keep auto-publishing regardless of
    cost" — an operator opts *out* of the safety behavior, not into it."""
    if os.environ.get(AUTO_PUBLISH_DISABLE_ON_BUDGET_BREACH_ENV, "true").lower() != "true":
        return False
    return is_over_monthly_budget(db)


def auto_publish_stories(db: Session) -> int:
    stories = db.scalars(select(Story).where(Story.status == "AI_READY")).all()
    if not stories:
        return 0

    enabled = _auto_publish_enabled() and not _budget_breach_disables_auto_publish(db)
    count = 0
    for story in stories:
        # NON_NEGOTIABLES #5: never auto-publish a sensitive category,
        # regardless of the kill switch — defense in depth, this should
        # already be unreachable via T11's own routing.
        if story.sensitivity != "NONE":
            story.status = "REVIEW_REQUIRED"
            db.flush()
            db.add(ReviewTask(story_id=story.id, reason="SENSITIVE_CATEGORY", status="PENDING"))
            count += 1
            continue

        if not enabled:
            story.status = "REVIEW_REQUIRED"
            db.flush()
            db.add(ReviewTask(story_id=story.id, reason="AUTO_PUBLISH_DISABLED", status="PENDING"))
            count += 1
            continue

        story.status = "REVIEW_REQUIRED"
        db.flush()
        story.status = "APPROVED"
        db.flush()
        story.status = "SCHEDULED"
        db.flush()
        db.add(
            AuditEvent(
                actor="system:auto_publish",
                action="STORY_AUTO_APPROVED",
                entity_type="story",
                entity_id=story.id,
                metadata_={"reason": "AUTO_PUBLISH_GLOBAL"},
            )
        )
        count += 1

    db.commit()
    return count


def publish_due_stories(db: Session) -> int:
    # Both the manual approve endpoint and auto_publish_stories() above
    # already cascade through APPROVED to SCHEDULED themselves (the ticket's
    # own "approve -> APPROVED/SCHEDULED" wording), so this only has the
    # last hop, SCHEDULED -> PUBLISHED, left to do.
    stories = db.scalars(select(Story).where(Story.status == "SCHEDULED")).all()
    count = 0
    for story in stories:
        story.status = "PUBLISHED"
        story.published_at = _now()
        db.flush()
        db.add(
            AuditEvent(
                actor="system:publish_scheduler",
                action="STORY_PUBLISHED",
                entity_type="story",
                entity_id=story.id,
                metadata_={},
            )
        )
        count += 1
    db.commit()
    return count


def run_publish_scheduler(db: Session, job: Job) -> None:
    """Job handler wrapping both sweeps for the worker."""
    auto_publish_stories(db)
    publish_due_stories(db)


def _schedule_window(now: datetime) -> datetime:
    epoch = datetime(1970, 1, 1, tzinfo=UTC)
    elapsed_minutes = int((now - epoch).total_seconds() // 60)
    bucket_start_minutes = (elapsed_minutes // SCHEDULE_INTERVAL_MINUTES) * SCHEDULE_INTERVAL_MINUTES
    return epoch + timedelta(minutes=bucket_start_minutes)


def schedule_publish_scheduler(db: Session) -> Job | None:
    """Enqueues one `publish_scheduler` job per `SCHEDULE_INTERVAL_MINUTES`
    window, same time-bucketed-dedupe_key pattern as `schedule_ai_classify`."""
    now = _now()
    dedupe_key = f"publish_scheduler:{_schedule_window(now).isoformat()}"
    return enqueue_job(db, "publish_scheduler", {}, dedupe_key=dedupe_key)
