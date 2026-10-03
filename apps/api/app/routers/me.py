"""Authenticated end-user endpoints. Real persistence as of T17 (ADR-006
anonymous identity, resolved in `app/auth.py::current_user`) — T04 through
T16 only ever echoed the request back; there was nothing to attach
persisted state to until push tokens/preferences needed to be readable
outside a request, by the `notification_dispatch` job.

`save_story`/`unsave_story` stay stub-echo: saved stories are client-side
only (web `localStorage` / mobile `AsyncStorage`, see T14/T15) since no
`saved_stories` table exists — there's nothing server-side to save to yet.

`delete_account` (T19 §16/§5.5 cross-system deletion) is real: deleting the
`users` row cascades in the database itself (T03's `ondelete="CASCADE"` FKs
on `profiles`/`user_topics`/`push_tokens`/`notifications`, and
`ondelete="SET NULL"` on `review_tasks.reviewer_id`/`corrections.created_by`
so editorial history survives losing the anonymous identity that made it) —
there is no separate per-table purge to keep in sync. This only reaches
`users` rows with no admin `role` (an anonymous end-user identity); an
admin's own account is out of scope for this self-service endpoint.
"""

from datetime import UTC, datetime
from typing import Literal, cast
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.auth import Principal, current_user
from app.db import get_db
from app.models import (
    Notification,
    Profile,
    PushToken,
    Story,
    Topic,
    User,
    UserKeyword,
    UserSavedStory,
    UserTopic,
)
from app.schemas import (
    DeleteAccountResponse,
    Language,
    MeResponse,
    NotificationOut,
    NotificationType,
    PreferencesUpdate,
    ProfileOut,
    PushTokenCreate,
    PushTokenResponse,
    SavedStoryResponse,
    TopicOut,
    TopicUrgency,
)

router = APIRouter(prefix="/v1/me", tags=["me"])

NOTIFICATION_HISTORY_LIMIT = 100


def _topic_urgency(db: Session, user_id: UUID) -> dict[str, str]:
    rows = db.execute(
        select(Topic.slug, UserTopic.urgency).join(UserTopic, UserTopic.topic_id == Topic.id).where(UserTopic.user_id == user_id)
    ).all()
    return {slug: urgency for slug, urgency in rows}


def _subscribed_topics(db: Session, user_id: UUID) -> list[TopicOut]:
    topics = db.scalars(
        select(Topic).join(UserTopic, UserTopic.topic_id == Topic.id).where(UserTopic.user_id == user_id)
    ).all()
    return [TopicOut(slug=t.slug, name=t.name) for t in topics]


def _profile_out(db: Session, user_id: UUID, profile: Profile | None) -> ProfileOut:
    if profile is None:
        return ProfileOut(topics=_subscribed_topics(db, user_id))
    return ProfileOut(
        residence_country=profile.residence_country,
        residence_region=profile.residence_region,
        home_state=profile.home_state,
        home_city=profile.home_city,
        language=cast(Language, profile.language),
        notification_mode=profile.notification_mode,
        topics=_subscribed_topics(db, user_id),
        breaking_alerts_enabled=profile.breaking_alerts_enabled,
        daily_briefing_enabled=profile.daily_briefing_enabled,
        quiet_hours_start=profile.quiet_hours_start,
        quiet_hours_end=profile.quiet_hours_end,
        max_alerts_per_day=profile.max_alerts_per_day,
        home_tz=profile.home_tz,
        residence_tz=profile.residence_tz,
        digest_morning_hour=profile.digest_morning_hour,
        digest_evening_hour=profile.digest_evening_hour,
        topic_urgency=cast(dict[str, TopicUrgency], _topic_urgency(db, user_id)),
        keywords=sorted(db.scalars(select(UserKeyword.keyword).where(UserKeyword.user_id == user_id)).all()),
        saved_story_ids=list(db.scalars(select(UserSavedStory.story_id).where(UserSavedStory.user_id == user_id)).all()),
    )


@router.get("")
def get_me(principal: Principal = Depends(current_user), db: Session = Depends(get_db)) -> MeResponse:
    user = db.get(User, principal.user_id)
    profile = db.get(Profile, principal.user_id)
    return MeResponse(id=principal.user_id, email=user.email if user else None, profile=_profile_out(db, principal.user_id, profile))


@router.patch("/preferences")
def update_preferences(
    body: PreferencesUpdate, principal: Principal = Depends(current_user), db: Session = Depends(get_db)
) -> ProfileOut:
    profile = db.get(Profile, principal.user_id)
    if profile is None:
        profile = Profile(user_id=principal.user_id)
        db.add(profile)

    for field in (
        "residence_country", "residence_region", "home_state", "home_city",
        "language", "notification_mode", "breaking_alerts_enabled",
        "daily_briefing_enabled", "quiet_hours_start", "quiet_hours_end", "max_alerts_per_day",
    ):
        value = getattr(body, field)
        if value is not None:
            setattr(profile, field, value)
    # An explicit null clears these (null elsewhere means "not provided").
    for field in ("home_tz", "residence_tz", "digest_morning_hour", "digest_evening_hour"):
        if field in body.model_fields_set:
            setattr(profile, field, getattr(body, field))
    db.flush()

    if body.topic_slugs is not None:
        previous = _topic_urgency(db, principal.user_id)
        db.query(UserTopic).filter(UserTopic.user_id == principal.user_id).delete()
        if body.topic_slugs:
            topics = db.execute(select(Topic.id, Topic.slug).where(Topic.slug.in_(body.topic_slugs))).all()
            for topic_id, slug in topics:
                urgency = (body.topic_urgency or {}).get(slug) or previous.get(slug, "INSTANT")
                db.add(UserTopic(user_id=principal.user_id, topic_id=topic_id, urgency=urgency))
    elif body.topic_urgency:
        for slug, urgency in body.topic_urgency.items():
            topic_uuid = db.scalar(select(Topic.id).where(Topic.slug == slug))
            row = db.get(UserTopic, (principal.user_id, topic_uuid)) if topic_uuid else None
            if row is not None:
                row.urgency = urgency

    if body.keywords is not None:
        db.query(UserKeyword).filter(UserKeyword.user_id == principal.user_id).delete()
        for keyword in body.keywords:
            db.add(UserKeyword(user_id=principal.user_id, keyword=keyword))

    if body.saved_story_ids is not None:
        db.query(UserSavedStory).filter(UserSavedStory.user_id == principal.user_id).delete()
        # Unknown ids are dropped rather than failing the whole sync.
        known = db.scalars(select(Story.id).where(Story.id.in_(set(body.saved_story_ids)))).all()
        for story_id in known:
            db.add(UserSavedStory(user_id=principal.user_id, story_id=story_id))

    db.commit()
    db.refresh(profile)
    return _profile_out(db, principal.user_id, profile)


@router.post("/saved/{story_id}")
def save_story(story_id: UUID, principal: Principal = Depends(current_user)) -> SavedStoryResponse:
    return SavedStoryResponse(story_id=story_id, saved=True)


@router.delete("/saved/{story_id}")
def unsave_story(story_id: UUID, principal: Principal = Depends(current_user)) -> SavedStoryResponse:
    return SavedStoryResponse(story_id=story_id, saved=False)


@router.post("/push-tokens")
def register_push_token(
    body: PushTokenCreate, principal: Principal = Depends(current_user), db: Session = Depends(get_db)
) -> PushTokenResponse:
    now = datetime.now(UTC)
    insert_stmt = pg_insert(PushToken).values(
        user_id=principal.user_id, platform=body.platform, token=body.token, active=True,
        created_at=now, last_seen_at=now,
    )
    insert_stmt = insert_stmt.on_conflict_do_update(
        index_elements=[PushToken.token],
        set_={"user_id": principal.user_id, "platform": body.platform, "active": True, "last_seen_at": now},
    )
    db.execute(insert_stmt)
    db.commit()
    return PushTokenResponse(registered=True)


@router.get("/notifications")
def list_notifications(
    principal: Principal = Depends(current_user), db: Session = Depends(get_db)
) -> list[NotificationOut]:
    notifications = db.scalars(
        select(Notification)
        .where(Notification.user_id == principal.user_id)
        .order_by(Notification.created_at.desc())
        .limit(NOTIFICATION_HISTORY_LIMIT)
    ).all()
    return [
        NotificationOut(
            id=n.id, type=cast(NotificationType, n.type),
            story_id=n.story_id, status=cast(Literal["PENDING", "SENT", "FAILED", "SUPPRESSED"], n.status),
            suppressed_reason=cast(Literal["QUIET_HOURS", "DAILY_CAP"] | None, n.suppressed_reason),
            sent_at=n.sent_at, created_at=n.created_at,
        )
        for n in notifications
    ]


@router.delete("/account")
def delete_account(principal: Principal = Depends(current_user), db: Session = Depends(get_db)) -> DeleteAccountResponse:
    user = db.get(User, principal.user_id)
    if user is not None:
        db.delete(user)
        db.commit()
    return DeleteAccountResponse(deleted=True)
