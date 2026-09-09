"""Authenticated end-user endpoints. Real persistence as of T17 (ADR-006
anonymous identity, resolved in `app/auth.py::current_user`) — T04 through
T16 only ever echoed the request back; there was nothing to attach
persisted state to until push tokens/preferences needed to be readable
outside a request, by the `notification_dispatch` job.

`save_story`/`unsave_story`/`delete_account` stay stub-echo: saved stories
and account deletion are out of T17's scope (no `saved_stories` table
exists yet) and unaffected by push notifications.
"""

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.auth import Principal, current_user
from app.db import get_db
from app.models import Notification, Profile, PushToken, Topic, User, UserTopic
from app.schemas import (
    DeleteAccountResponse,
    MeResponse,
    NotificationOut,
    PreferencesUpdate,
    ProfileOut,
    PushTokenCreate,
    PushTokenResponse,
    SavedStoryResponse,
    TopicOut,
)

router = APIRouter(prefix="/v1/me", tags=["me"])

NOTIFICATION_HISTORY_LIMIT = 100


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
        language=profile.language,
        notification_mode=profile.notification_mode,
        topics=_subscribed_topics(db, user_id),
        breaking_alerts_enabled=profile.breaking_alerts_enabled,
        daily_briefing_enabled=profile.daily_briefing_enabled,
        quiet_hours_start=profile.quiet_hours_start,
        quiet_hours_end=profile.quiet_hours_end,
        max_alerts_per_day=profile.max_alerts_per_day,
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
    db.flush()

    if body.topic_slugs is not None:
        db.query(UserTopic).filter(UserTopic.user_id == principal.user_id).delete()
        if body.topic_slugs:
            topic_ids = db.scalars(select(Topic.id).where(Topic.slug.in_(body.topic_slugs))).all()
            for topic_id in topic_ids:
                db.add(UserTopic(user_id=principal.user_id, topic_id=topic_id))

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
            id=n.id, type=n.type, story_id=n.story_id, status=n.status,
            suppressed_reason=n.suppressed_reason, sent_at=n.sent_at, created_at=n.created_at,
        )
        for n in notifications
    ]


@router.delete("/account")
def delete_account(principal: Principal = Depends(current_user)) -> DeleteAccountResponse:
    return DeleteAccountResponse(deleted=True)
