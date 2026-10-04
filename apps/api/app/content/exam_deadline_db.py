"""P07 / ADR-041: exam-deadline alert queueing shared by the API and the notify job."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.content.exam_deadline import notification_key
from app.models import Notification, UserExamFollow


def queue_alerts(db: Session, item_id: UUID, exam: str, tag: str) -> None:
    """One PENDING row per alert-enabled follower; idempotent per (user, key)."""

    key = notification_key(item_id, tag)
    for user_id in db.scalars(select(UserExamFollow.user_id).where(UserExamFollow.exam == exam, UserExamFollow.alerts.is_(True))):
        db.execute(
            pg_insert(Notification)
            .values(user_id=user_id, story_id=None, type="TRACKER_UPDATE", notification_key=key, status="PENDING")
            .on_conflict_do_nothing(index_elements=[Notification.user_id, Notification.notification_key])
        )
