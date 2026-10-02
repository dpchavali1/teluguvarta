"""T17's `notification_dispatch` job (reserved in T03's `ck_jobs_type`,
unimplemented until now): daily briefing, topic alerts, and gated breaking
alerts, batched per §14 ("compute story-level eligibility once, not per-user
AI calls") rather than one gateway/DB round trip per user.

Two phases, matching the ticket's own ordering:

1. `_generate_candidates` walks each *newly published* story (bounded by
   `NOTIFICATION_LOOKBACK_MINUTES` so this never becomes an unbounded full
   scan) once, computes its topics/importance/source-quality once, then
   fans out to the (usually much smaller) set of users who could possibly
   care — topic subscribers for `TOPIC_ALERT`, everyone with breaking
   alerts on for `BREAKING_ALERT` — via `app/content/notifications.py`'s
   pure eligibility functions. A `PENDING` `Notification` row is inserted
   per (user, notification_key) with `ON CONFLICT DO NOTHING` on the T03
   unique constraint — this, not application logic, is what makes dedupe
   safe under retries/duplicate triggers (same pattern as
   `app/jobs/queue.py::enqueue_job`).
2. `_process_pending` sweeps `PENDING` rows that are due, applies quiet
   hours and the daily cap (each generates its own analytics event instead
   of silently dropping the send), then attempts delivery via
   `app/push.py`. A delivery failure gets bounded, backed-off retry
   (`attempts`/`next_attempt_at`, same shape as `app/jobs/queue.py`'s job
   backoff) rather than being resent from scratch — the dedupe key was
   already consumed at INSERT, so "retry" here means updating that same
   row, never inserting a second one.

Daily briefing is per-user, not per-story (dedupe key is
`daily_briefing:{utc_date}`, `story_id` is NULL — the deep link falls back
to the home feed, matching the ticket's "opening it goes to the intended
story/topic page; if unavailable, fall back to the inbox or home feed").
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app import analytics
from app.content.notifications import (
    NotifiableStory,
    UserNotificationPrefs,
    breaking_alert_eligible,
    daily_cap_reached,
    in_quiet_hours,
    topic_alert_eligible,
)
from app.jobs.queue import backoff_seconds, enqueue_job
from app.models import (
    Job,
    Notification,
    Profile,
    PushToken,
    Source,
    SourceItem,
    Story,
    StorySource,
    StoryTopic,
    Topic,
    UserTopic,
)
from app.push import send_push

NOTIFICATION_LOOKBACK_MINUTES = 120
MAX_NOTIFICATION_ATTEMPTS = 5
PENDING_BATCH_LIMIT = 500
SCHEDULE_INTERVAL_MINUTES = 1


def _now() -> datetime:
    return datetime.now(UTC)


def _story_topic_slugs(db: Session, story_id) -> tuple[str, ...]:
    slugs = db.scalars(
        select(Topic.slug).join(StoryTopic, StoryTopic.topic_id == Topic.id).where(StoryTopic.story_id == story_id)
    ).all()
    return tuple(slugs)


def _avg_source_quality(db: Session, story_id) -> float:
    scores = db.scalars(
        select(Source.quality_score)
        .join(SourceItem, SourceItem.source_id == Source.id)
        .join(StorySource, StorySource.source_item_id == SourceItem.id)
        .where(StorySource.story_id == story_id)
    ).all()
    if not scores:
        return 0.5
    return sum(scores) / len(scores)


def _to_notifiable(db: Session, story: Story) -> NotifiableStory:
    return NotifiableStory(
        id=str(story.id),
        topics=_story_topic_slugs(db, story.id),
        importance=story.importance,
        classification_confidence=story.classification_confidence,
        sensitivity=story.sensitivity,
        breaking_alert_approved=story.breaking_alert_approved_at is not None,
        avg_source_quality=_avg_source_quality(db, story.id),
    )


def _load_prefs(db: Session, user_id) -> UserNotificationPrefs:
    profile = db.get(Profile, user_id)
    topic_slugs = db.scalars(
        select(Topic.slug).join(UserTopic, UserTopic.topic_id == Topic.id).where(UserTopic.user_id == user_id)
    ).all()
    if profile is None:
        return UserNotificationPrefs(
            subscribed_topics=tuple(topic_slugs),
            breaking_alerts_enabled=True,
            daily_briefing_enabled=True,
            quiet_hours_start=None,
            quiet_hours_end=None,
            max_alerts_per_day=5,
        )
    return UserNotificationPrefs(
        subscribed_topics=tuple(topic_slugs),
        breaking_alerts_enabled=profile.breaking_alerts_enabled,
        daily_briefing_enabled=profile.daily_briefing_enabled,
        quiet_hours_start=profile.quiet_hours_start,
        quiet_hours_end=profile.quiet_hours_end,
        max_alerts_per_day=profile.max_alerts_per_day,
    )


def _insert_pending(db: Session, *, user_id, story_id, notif_type: str, notification_key: str) -> None:
    insert_stmt = pg_insert(Notification).values(
        user_id=user_id, story_id=story_id, type=notif_type, notification_key=notification_key, status="PENDING"
    )
    insert_stmt = insert_stmt.on_conflict_do_nothing(
        index_elements=[Notification.user_id, Notification.notification_key]
    )
    db.execute(insert_stmt)


def _generate_topic_and_breaking_candidates(db: Session, now: datetime) -> None:
    lookback_start = now - timedelta(minutes=NOTIFICATION_LOOKBACK_MINUTES)
    stories = db.scalars(
        select(Story).where(
            Story.status.in_(("PUBLISHED", "UPDATED")),
            Story.published_at.is_not(None),
            Story.published_at >= lookback_start,
        )
    ).all()

    for story in stories:
        notifiable = _to_notifiable(db, story)

        candidate_user_ids: set = set()
        if notifiable.topics:
            candidate_user_ids |= set(
                db.scalars(
                    select(UserTopic.user_id)
                    .join(Topic, Topic.id == UserTopic.topic_id)
                    .where(Topic.slug.in_(notifiable.topics))
                ).all()
            )
        if notifiable.sensitivity == "BREAKING" and notifiable.breaking_alert_approved:
            candidate_user_ids |= set(
                db.scalars(select(Profile.user_id).where(Profile.breaking_alerts_enabled.is_(True))).all()
            )

        for user_id in candidate_user_ids:
            prefs = _load_prefs(db, user_id)
            if topic_alert_eligible(notifiable, prefs):
                _insert_pending(
                    db, user_id=user_id, story_id=story.id,
                    notif_type="TOPIC_ALERT", notification_key=f"topic_alert:{story.id}",
                )
            if breaking_alert_eligible(notifiable, prefs):
                _insert_pending(
                    db, user_id=user_id, story_id=story.id,
                    notif_type="BREAKING_ALERT", notification_key=f"breaking_alert:{story.id}",
                )
        db.commit()


def _generate_daily_briefing_candidates(db: Session, now: datetime) -> None:
    utc_date = now.date().isoformat()
    user_ids = db.scalars(select(Profile.user_id).where(Profile.daily_briefing_enabled.is_(True))).all()
    for user_id in user_ids:
        _insert_pending(
            db, user_id=user_id, story_id=None,
            notif_type="DAILY_BRIEFING", notification_key=f"daily_briefing:{utc_date}",
        )
    db.commit()


def _sent_today_count(db: Session, user_id, now: datetime) -> int:
    day_start = datetime(now.year, now.month, now.day, tzinfo=UTC)
    return db.scalar(
        select(func.count())
        .select_from(Notification)
        .where(Notification.user_id == user_id, Notification.status == "SENT", Notification.sent_at >= day_start)
    ) or 0


def _push_copy(notification: Notification) -> tuple[str, str]:
    if notification.type == "DAILY_BRIEFING":
        return "Your TTE briefing", "Today's top stories are ready."
    if notification.type == "BREAKING_ALERT":
        return "Breaking", "A breaking story just published."
    return "New story in a topic you follow", "Open to read the full story."


def _process_one(db: Session, notification: Notification, now: datetime) -> None:
    prefs = _load_prefs(db, notification.user_id)

    if in_quiet_hours(now.hour, prefs.quiet_hours_start, prefs.quiet_hours_end):
        notification.status = "SUPPRESSED"
        notification.suppressed_reason = "QUIET_HOURS"
        db.commit()
        analytics.track(
            "notification_skipped_due_to_quiet_hours",
            user_id=str(notification.user_id), notification_type=notification.type,
        )
        return

    if daily_cap_reached(_sent_today_count(db, notification.user_id, now), prefs.max_alerts_per_day):
        notification.status = "SUPPRESSED"
        notification.suppressed_reason = "DAILY_CAP"
        db.commit()
        analytics.track(
            "notification_suppressed_by_daily_cap",
            user_id=str(notification.user_id), notification_type=notification.type,
        )
        return

    tokens = db.scalars(
        select(PushToken.token).where(PushToken.user_id == notification.user_id, PushToken.active.is_(True))
    ).all()
    title, body = _push_copy(notification)
    # The deep-link target the client navigates by (T14/T15 route on slug,
    # not id) — None when there's no story (DAILY_BRIEFING) or it's since
    # become unreachable, both of which the client already falls back to
    # the home feed for (ApiNotFoundError on GET /v1/stories/{slug}).
    canonical_slug = (
        db.scalar(select(Story.canonical_slug).where(Story.id == notification.story_id))
        if notification.story_id else None
    )
    result = send_push(
        list(tokens), title=title, body=body,
        data={"type": notification.type, "story_slug": canonical_slug},
    )
    if result.invalid_tokens:
        db.query(PushToken).filter(PushToken.token.in_(result.invalid_tokens)).update(
            {PushToken.active: False}, synchronize_session=False
        )

    notification.attempts += 1
    if result.ok:
        notification.status = "SENT"
        notification.sent_at = now
    elif notification.attempts >= MAX_NOTIFICATION_ATTEMPTS:
        notification.status = "FAILED"
        analytics.track(
            "notification_failed",
            user_id=str(notification.user_id), notification_type=notification.type, detail=result.detail,
        )
    else:
        notification.next_attempt_at = now + timedelta(seconds=backoff_seconds(notification.attempts))
    db.commit()


def _process_pending(db: Session, now: datetime) -> None:
    pending = db.scalars(
        select(Notification)
        .where(
            Notification.status == "PENDING",
            (Notification.next_attempt_at.is_(None)) | (Notification.next_attempt_at <= now),
        )
        .limit(PENDING_BATCH_LIMIT)
    ).all()
    for notification in pending:
        _process_one(db, notification, now)


def run_notification_dispatch(db: Session, job: Job) -> None:
    now = _now()
    _generate_topic_and_breaking_candidates(db, now)
    _generate_daily_briefing_candidates(db, now)
    _process_pending(db, now)


def _schedule_window(now: datetime) -> datetime:
    epoch = datetime(1970, 1, 1, tzinfo=UTC)
    elapsed_minutes = int((now - epoch).total_seconds() // 60)
    bucket_start_minutes = (elapsed_minutes // SCHEDULE_INTERVAL_MINUTES) * SCHEDULE_INTERVAL_MINUTES
    return epoch + timedelta(minutes=bucket_start_minutes)


def schedule_notification_dispatch(db: Session) -> Job | None:
    now = _now()
    dedupe_key = f"notification_dispatch:{_schedule_window(now).isoformat()}"
    return enqueue_job(db, "notification_dispatch", {}, dedupe_key=dedupe_key)
