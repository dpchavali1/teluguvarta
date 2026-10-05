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
   ADR-019: with the global switch off, a story first gets a chance at the
   link-first brief lane (`app/jobs/brief_lane.py`, `AUTO_PUBLISH_BRIEFS`,
   daily cap). Lane failures add their reason to the review task.
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
from app.content.publication import validate_for_publication
from app.content.rights import RIGHTS_REVOKED_REASON, unpermitted_sources
from app.jobs.breaking_lane import (
    DEATH_SIGNAL_PATTERN,
    death_hold_candidate,
    publish_breaking_briefs,
)
from app.jobs.brief_lane import LaneOutcome, daily_cap, published_today, try_brief_lane
from app.jobs.queue import enqueue_job
from app.models import (
    AuditEvent,
    Job,
    ReviewTask,
    SourceItem,
    Story,
    StorySource,
    StoryVariant,
)
from app.switches import ai_paused, auto_publish_paused, env_allows

SCHEDULE_INTERVAL_MINUTES = 2

AUTO_PUBLISH_GLOBAL_ENV = "AUTO_PUBLISH_GLOBAL"
AUTO_PUBLISH_DISABLE_ON_BUDGET_BREACH_ENV = "AUTO_PUBLISH_DISABLE_ON_BUDGET_BREACH"

# ADR-031: a story older than this is archived rather than auto-published or
# left in the queue only because auto-publish was off when it was ready.
STALE_AFTER_HOURS_ENV = "STALE_AFTER_HOURS"
DEFAULT_STALE_AFTER_HOURS = 24
SWITCH_OFF_REASON = "AUTO_PUBLISH_DISABLED"
STALE_DECISION = "STALE"


def _now() -> datetime:
    return datetime.now(UTC)


def _auto_publish_enabled() -> bool:
    return env_allows("auto_publish")


def _stale_after() -> timedelta:
    try:
        hours = int(os.environ.get(STALE_AFTER_HOURS_ENV, DEFAULT_STALE_AFTER_HOURS))
    except ValueError:
        hours = DEFAULT_STALE_AFTER_HOURS
    return timedelta(hours=max(1, hours))


def _is_stale(db: Session, story: Story) -> bool:
    """Age is when the English draft was written; no draft, no verdict (the
    content rules hold it instead)."""
    generated_at = db.scalars(
        select(StoryVariant.generated_at).where(StoryVariant.story_id == story.id, StoryVariant.language == "en")
    ).first()
    return generated_at is not None and generated_at < _now() - _stale_after()


def _audit(db: Session, story: Story, action: str, metadata: dict) -> None:
    db.add(
        AuditEvent(
            actor="system:auto_publish", action=action, entity_type="story", entity_id=story.id, metadata_=metadata
        )
    )


def _approve(db: Session, story: Story, reason: str) -> None:
    """REVIEW_REQUIRED -> APPROVED -> SCHEDULED; the publish sweep does the rest."""
    story.status = "APPROVED"
    db.flush()
    story.status = "SCHEDULED"
    db.flush()
    _audit(db, story, "STORY_AUTO_APPROVED", {"reason": reason})


def _expire_stale(db: Session, story: Story, task: ReviewTask) -> None:
    story.status = "ARCHIVED"
    db.flush()
    task.status = "REJECTED"
    task.decision = STALE_DECISION
    _audit(db, story, "STORY_EXPIRED_STALE", {"stale_after_hours": int(_stale_after().total_seconds() // 3600)})


NO_EXPIRY_SENSITIVITIES = frozenset({"BREAKING", "OBITUARY_ACCUSATION"})
NO_EXPIRY_REASON = "HIGH_IMPORTANCE"
def death_signal_story_ids(db: Session, pairs: list[tuple[Story, list[ReviewTask]]]) -> frozenset:
    """Story ids (among `pairs`) held as RESTRICTED / AI-unclassifiable whose English
    headline+summary mention a death, or, with no English variant yet, whose linked
    source-item titles do. Two batched queries regardless of queue size."""
    candidates = [s.id for s, tasks in pairs if death_hold_candidate(s, tasks)]
    if not candidates:
        return frozenset()
    variants = {
        sid: f"{headline} {summary}"
        for sid, headline, summary in db.execute(
            select(StoryVariant.story_id, StoryVariant.headline, StoryVariant.summary).where(
                StoryVariant.story_id.in_(candidates), StoryVariant.language == "en"
            )
        ).all()
    }
    titles: dict = {}
    undrafted = [sid for sid in candidates if sid not in variants]
    if undrafted:
        for sid, title in db.execute(
            select(StorySource.story_id, SourceItem.title)
            .join(SourceItem, SourceItem.id == StorySource.source_item_id)
            .where(StorySource.story_id.in_(undrafted))
        ).all():
            titles[sid] = f"{titles.get(sid, '')} {title or ''}"
    return frozenset(
        sid for sid in candidates if DEATH_SIGNAL_PATTERN.search(variants.get(sid) or titles.get(sid) or "")
    )


def never_expires(story: Story, tasks: list[ReviewTask], death_ids: frozenset = frozenset()) -> bool:
    """ADR-052: breaking/obituary stories, high-importance holds and death-signal
    holds (`death_ids`, from `death_signal_story_ids`) wait for a human however
    long it takes; only the other classes expire (ADR-032)."""
    if story.sensitivity in NO_EXPIRY_SENSITIVITIES or story.id in death_ids:
        return True
    return any(NO_EXPIRY_REASON in t.reason.split(",") for t in tasks)


def _is_switch_off_reason(reason: str) -> bool:
    # The brief lane may have appended its outcome: "AUTO_PUBLISH_DISABLED,DAILY_CAP".
    return reason == SWITCH_OFF_REASON or reason.startswith(SWITCH_OFF_REASON + ",")


def expire_stale_holds(db: Session) -> int:
    """ADR-032: a hold of any kind that nobody acted on before the story went
    stale leaves the queue. A story still waiting in REVIEW_REQUIRED is
    archived (never published, so NON_NEGOTIABLES #5 holds); a task left on a
    story that moved on (e.g. a Telugu sample on a published story) is closed.
    Age is the English draft's `generated_at`, or, for a story held before it
    was drafted, when it was first queued."""
    tasks = db.scalars(select(ReviewTask).where(ReviewTask.status == "PENDING")).all()
    by_story: dict = {}
    for task in tasks:
        by_story.setdefault(task.story_id, []).append(task)
    if not by_story:
        return 0
    drafted = dict(
        db.execute(
            select(StoryVariant.story_id, StoryVariant.generated_at).where(
                StoryVariant.story_id.in_(by_story), StoryVariant.language == "en"
            )
        ).all()
    )
    cutoff = _now() - _stale_after()
    stale_after_hours = int(_stale_after().total_seconds() // 3600)
    stale = {sid: ts for sid, ts in by_story.items() if (drafted.get(sid) or min(t.created_at for t in ts)) < cutoff}
    stories = {s.id: s for s in db.scalars(select(Story).where(Story.id.in_(stale))).all()} if stale else {}
    death_ids = death_signal_story_ids(db, [(stories[sid], ts) for sid, ts in stale.items() if sid in stories])
    count = 0
    for story_id, story_tasks in stale.items():
        story = stories.get(story_id)
        if story is None or (story.status == "REVIEW_REQUIRED" and never_expires(story, story_tasks, death_ids)):
            continue
        for task in story_tasks:
            task.status = "REJECTED"
            task.decision = STALE_DECISION
        metadata = {"stale_after_hours": stale_after_hours, "reasons": sorted({t.reason for t in story_tasks})}
        if story.status == "REVIEW_REQUIRED":
            story.status = "ARCHIVED"
            db.flush()
            _audit(db, story, "STORY_EXPIRED_STALE", metadata)
        else:
            _audit(db, story, "REVIEW_TASK_EXPIRED_STALE", {**metadata, "story_status": story.status})
        count += 1
    db.flush()
    return count


def resweep_switch_queue(db: Session) -> int:
    """ADR-031: stories queued only because auto-publish was off get the
    automatic decision they would get now — published if fresh and clean, or
    re-tagged with the real reason a person must look (stale ones are already
    gone via `expire_stale_holds`). Stories with any other pending task are
    left alone."""
    tasks = db.scalars(
        select(ReviewTask)
        .join(Story, Story.id == ReviewTask.story_id)
        .where(ReviewTask.status == "PENDING", Story.status == "REVIEW_REQUIRED")
    ).all()
    by_story: dict = {}
    for task in tasks:
        by_story.setdefault(task.story_id, []).append(task)
    count = 0
    for story_tasks in by_story.values():
        if len(story_tasks) != 1 or not _is_switch_off_reason(story_tasks[0].reason):
            continue
        task = story_tasks[0]
        story = db.get(Story, task.story_id)
        if story is None or story.sensitivity != "NONE":
            continue
        if unpermitted_sources(db, story.id):
            task.reason = RIGHTS_REVOKED_REASON
        elif failures := validate_for_publication(db, story):
            task.reason = f"{CONTENT_RULES_REASON}:{','.join(failures)}"
        else:
            _approve(db, story, "AUTO_PUBLISH_RESWEEP")
            task.status = "APPROVED"
            task.decision = "AUTO_APPROVED"
        count += 1
    db.flush()
    return count


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
    # ADR-032: expiry only archives, so it runs whatever the switches say.
    count = expire_stale_holds(db)

    # ADR-031: paused from the dashboard -> nothing publishes automatically and
    # nothing is queued; stories wait in AI_READY until it is switched back on.
    if auto_publish_paused(db):
        db.commit()
        return count

    # ADR-054: breaking/death stories with source-text briefs need no AI, so
    # this runs ahead of (and independent of) the budget and AI switches.
    count += publish_breaking_briefs(db)

    budget_breached = _budget_breach_disables_auto_publish(db)
    enabled = _auto_publish_enabled() and not budget_breached
    if enabled:
        count += resweep_switch_queue(db)

    stories = db.scalars(select(Story).where(Story.status == "AI_READY")).all()
    if not stories:
        db.commit()
        return count

    # ADR-019: the brief lane only runs where a story would otherwise wait for
    # review because the global switch is off, and closes on a budget breach.
    # ADR-031: it needs the AI, so it also closes while AI is paused.
    brief_lane_open = not enabled and not budget_breached and not ai_paused(db)
    brief_cap_left = daily_cap() - published_today(db, _now()) if brief_lane_open else None
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

        # Review 2026-09-29 #7: a source disabled since ingest blocks every
        # automatic approval, brief lane included.
        if unpermitted_sources(db, story.id):
            story.status = "REVIEW_REQUIRED"
            db.flush()
            db.add(ReviewTask(story_id=story.id, reason=RIGHTS_REVOKED_REASON, status="PENDING"))
            count += 1
            continue

        if not enabled:
            lane = LaneOutcome.NOT_ATTEMPTED
            if brief_cap_left is not None:
                lane = try_brief_lane(db, story, remaining_cap=brief_cap_left)
            if lane == LaneOutcome.PUBLISHED:
                brief_cap_left = (brief_cap_left or 0) - 1
                count += 1
                continue
            reason = "AUTO_PUBLISH_DISABLED"
            if lane != LaneOutcome.NOT_ATTEMPTED:
                reason += f",{lane.value}"
            story.status = "REVIEW_REQUIRED"
            db.flush()
            db.add(ReviewTask(story_id=story.id, reason=reason, status="PENDING"))
            count += 1
            continue

        # ADR-031: too old to go out as news.
        if _is_stale(db, story):
            story.status = "REVIEW_REQUIRED"
            db.flush()
            task = ReviewTask(story_id=story.id, reason=SWITCH_OFF_REASON, status="PENDING")
            db.add(task)
            _expire_stale(db, story, task)
            count += 1
            continue

        # ADR-026: a draft short of the minimum content waits for an editor.
        if failures := validate_for_publication(db, story):
            story.status = "REVIEW_REQUIRED"
            db.flush()
            db.add(ReviewTask(story_id=story.id, reason=f"{CONTENT_RULES_REASON}:{','.join(failures)}", status="PENDING"))
            count += 1
            continue

        story.status = "REVIEW_REQUIRED"
        db.flush()
        _approve(db, story, "AUTO_PUBLISH_GLOBAL")
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
        if blocked := unpermitted_sources(db, story.id):
            _hold_for_rights(db, story, blocked)
            continue
        if failures := validate_for_publication(db, story):
            _hold_once(db, story, CONTENT_HOLD_ACTION, {"failures": failures})
            continue
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


RIGHTS_HOLD_ACTION = "STORY_PUBLISH_BLOCKED_RIGHTS"
# ADR-026: an approved story short of the minimum content (in practice, one
# approved before the rules existed) is held the same way as a rights hold.
CONTENT_HOLD_ACTION = "STORY_PUBLISH_BLOCKED_CONTENT"
CONTENT_RULES_REASON = "CONTENT_RULES_FAILED"


def _hold_for_rights(db: Session, story: Story, blocked: list) -> None:
    """Review #7: an approved story whose source was disabled after approval
    stays SCHEDULED and unpublished; the status machine has no way back to
    review from SCHEDULED (see ADR-023, proposed). It publishes on
    a later sweep if the rights are restored. Audited once per story."""
    _hold_once(
        db, story, RIGHTS_HOLD_ACTION,
        {"source_ids": [str(s.id) for s in blocked], "rights": [s.rights_status for s in blocked]},
    )


def _hold_once(db: Session, story: Story, action: str, metadata: dict) -> None:
    already = db.scalars(
        select(AuditEvent.id).where(AuditEvent.entity_id == story.id, AuditEvent.action == action)
    ).first()
    if already is None:
        db.add(
            AuditEvent(
                actor="system:publish_scheduler",
                action=action,
                entity_type="story",
                entity_id=story.id,
                metadata_=metadata,
            )
        )
        db.flush()


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
