"""P07 / ADR-041: bulletin queries shared by the API and the notify job."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.content.visa_bulletin import alert_copy, movement
from app.models import UserVisaFollow, VisaBulletin, VisaBulletinEntry

Key = tuple[str, str, str]  # (chart, category, country)


def entry_map(db: Session, bulletin_id: UUID) -> dict[Key, str]:
    rows = db.execute(
        select(VisaBulletinEntry.chart, VisaBulletinEntry.category, VisaBulletinEntry.country, VisaBulletinEntry.cutoff)
        .where(VisaBulletinEntry.bulletin_id == bulletin_id)
    ).all()
    return {(chart, category, country): cutoff for chart, category, country, cutoff in rows}


def previous_approved(db: Session, month: date) -> VisaBulletin | None:
    return db.scalars(
        select(VisaBulletin)
        .where(VisaBulletin.status == "APPROVED", VisaBulletin.month < month)
        .order_by(VisaBulletin.month.desc())
        .limit(1)
    ).first()


def latest_approved(db: Session) -> VisaBulletin | None:
    return db.scalars(
        select(VisaBulletin).where(VisaBulletin.status == "APPROVED").order_by(VisaBulletin.month.desc()).limit(1)
    ).first()


def followers_changes(db: Session, bulletin: VisaBulletin, user_id: UUID | None = None) -> dict[UUID, list[tuple[str, str, str, str, str]]]:
    """Alert-enabled followers → their changed final-action cutoffs as
    (category, country, previous, current, movement). No earlier approved
    bulletin means a baseline: nothing changed, so nobody is alerted."""

    before = previous_approved(db, bulletin.month)
    if before is None:
        return {}
    now_map, was_map = entry_map(db, bulletin.id), entry_map(db, before.id)
    query = select(UserVisaFollow).where(UserVisaFollow.alerts.is_(True))
    if user_id is not None:
        query = query.where(UserVisaFollow.user_id == user_id)
    out: dict[UUID, list[tuple[str, str, str, str, str]]] = {}
    for follow in db.scalars(query).all():
        key = ("FINAL_ACTION", follow.category, follow.country)
        current, previous = now_map.get(key), was_map.get(key)
        if current is None or previous is None:
            continue
        move = movement(previous, current)
        if move in ("FORWARD", "BACKWARD"):
            out.setdefault(follow.user_id, []).append((follow.category, follow.country, previous, current, move))
    return out


def push_copy(changes: list[tuple[str, str, str, str, str]]) -> tuple[str, str]:
    if not changes:
        return "Visa Bulletin updated", "A new Visa Bulletin is out."
    if len(changes) == 1:
        category, country, previous, current, move = changes[0]
        return alert_copy(category, country, previous, current, move)
    return "Visa Bulletin: your categories moved", f"{len(changes)} categories you track changed. Open to see them."
