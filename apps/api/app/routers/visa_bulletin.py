"""P07 / ADR-041: visa bulletin tracker.

Public reads serve only APPROVED bulletins. Editors enter a month from the
official notice (DRAFT), then approve it; approval queues one alert per
alert-enabled follower whose final-action cutoff moved."""

from __future__ import annotations

import base64
from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.auth import AdminPrincipal, current_admin, require_second_approver
from app.content.visa_bulletin import entry_errors, movement, official_source_url
from app.content.visa_bulletin_db import (
    entry_map,
    followers_changes,
    latest_approved,
    previous_approved,
)
from app.content.visa_bulletin_parse import parse_bulletin_text, text_from_pdf
from app.db import get_db
from app.errors import APIError
from app.models import AuditEvent, Notification, VisaBulletin, VisaBulletinEntry
from app.rate_limit import rate_limit_admin
from app.schemas import (
    VisaBulletinEntryIn,
    VisaBulletinEntryOut,
    VisaBulletinIn,
    VisaBulletinOut,
    VisaBulletinParseIn,
    VisaBulletinParseOut,
)

public_router = APIRouter(prefix="/v1/visa-bulletins", tags=["public"])
admin_router = APIRouter(
    prefix="/v1/admin/visa-bulletins", tags=["admin"], dependencies=[Depends(current_admin), Depends(rate_limit_admin)]
)


def _parse_month(value: str) -> date:
    try:
        parsed = date.fromisoformat(f"{value}-01")
    except ValueError:
        raise APIError(422, "INVALID_MONTH", "Month must be YYYY-MM") from None
    return parsed


def _out(db: Session, bulletin: VisaBulletin, category: str | None = None, country: str | None = None) -> VisaBulletinOut:
    before = previous_approved(db, bulletin.month)
    was = entry_map(db, before.id) if before else {}
    entries = [
        VisaBulletinEntryOut(
            chart=chart, category=cat, country=ctry, cutoff=cutoff,
            previous=was.get((chart, cat, ctry)), movement=movement(was.get((chart, cat, ctry)), cutoff) if before else "NEW",
        )
        for (chart, cat, ctry), cutoff in sorted(entry_map(db, bulletin.id).items())
        if (category is None or cat == category) and (country is None or ctry == country)
    ]
    return VisaBulletinOut(
        id=bulletin.id, month=bulletin.month.strftime("%Y-%m"), status=bulletin.status,
        source_url=bulletin.source_url, entries=entries,
    )


@public_router.get("/latest")
def latest_bulletin(
    category: str | None = Query(default=None), country: str | None = Query(default=None), db: Session = Depends(get_db)
) -> VisaBulletinOut:
    bulletin = latest_approved(db)
    if bulletin is None:
        raise APIError(404, "NO_VISA_BULLETIN", "No approved visa bulletin yet")
    return _out(db, bulletin, category, country)


@admin_router.get("")
def list_bulletins(db: Session = Depends(get_db)) -> list[VisaBulletinOut]:
    rows = db.scalars(select(VisaBulletin).order_by(VisaBulletin.month.desc()).limit(24)).all()
    return [_out(db, row) for row in rows]


@admin_router.post("/parse")
def parse_bulletin(body: VisaBulletinParseIn) -> VisaBulletinParseOut:
    """Read-only helper (ADR-049): text pasted from the official PDF -> entries to review. Saves nothing."""
    if (body.text is None) == (body.pdf_base64 is None):
        raise APIError(422, "PARSE_INPUT", "Send either text or pdf_base64")
    try:
        text = body.text if body.text is not None else text_from_pdf(base64.b64decode(body.pdf_base64 or "", validate=True))
    except ValueError as exc:  # includes binascii.Error
        raise APIError(422, "PDF_UNREADABLE", str(exc)) from exc
    parsed = parse_bulletin_text(text)
    return VisaBulletinParseOut(
        month=parsed.month, entries=[VisaBulletinEntryIn(**e) for e in parsed.entries], warnings=parsed.warnings
    )


@admin_router.put("/{month}")
def put_bulletin(
    month: str, body: VisaBulletinIn, admin: AdminPrincipal = Depends(current_admin), db: Session = Depends(get_db)
) -> VisaBulletinOut:
    first = _parse_month(month)
    if not official_source_url(body.source_url):
        raise APIError(422, "SOURCE_NOT_OFFICIAL", "Source link must be an https travel.state.gov page")
    for entry in body.entries:
        problem = entry_errors(entry.chart, entry.category, entry.country, entry.cutoff)
        if problem:
            raise APIError(422, "INVALID_ENTRY", problem)
    bulletin = db.scalars(select(VisaBulletin).where(VisaBulletin.month == first).with_for_update()).first()
    if bulletin is not None and bulletin.status == "APPROVED":
        raise APIError(409, "BULLETIN_APPROVED", "An approved bulletin cannot be edited")
    if bulletin is None:
        bulletin = VisaBulletin(month=first, source_url=body.source_url, entered_by=admin.email)
        db.add(bulletin)
        db.flush()
    else:
        bulletin.source_url = body.source_url
        bulletin.entered_by = admin.email
        db.execute(delete(VisaBulletinEntry).where(VisaBulletinEntry.bulletin_id == bulletin.id))
    for entry in {(e.chart, e.category, e.country): e for e in body.entries}.values():
        db.add(VisaBulletinEntry(
            bulletin_id=bulletin.id, chart=entry.chart, category=entry.category, country=entry.country, cutoff=entry.cutoff
        ))
    db.add(AuditEvent(
        actor=admin.email, action="VISA_BULLETIN_DRAFTED", entity_type="visa_bulletin", entity_id=bulletin.id,
        metadata_={"month": month, "entries": len(body.entries)},
    ))
    db.commit()
    return _out(db, bulletin)


@admin_router.post("/{month}/approve")
def approve_bulletin(
    month: str, admin: AdminPrincipal = Depends(current_admin), db: Session = Depends(get_db)
) -> VisaBulletinOut:
    first = _parse_month(month)
    bulletin = db.scalars(select(VisaBulletin).where(VisaBulletin.month == first).with_for_update()).first()
    if bulletin is None:
        raise APIError(404, "BULLETIN_NOT_FOUND", f"No bulletin for {month}")
    if bulletin.status != "APPROVED":
        require_second_approver(bulletin.entered_by, admin)
        bulletin.status = "APPROVED"
        bulletin.approved_by = admin.email
        bulletin.approved_at = datetime.now(UTC)
        db.flush()
        # Idempotent: one row per user per bulletin (user_id, notification_key unique).
        for user_id in followers_changes(db, bulletin):
            db.execute(
                pg_insert(Notification)
                .values(user_id=user_id, story_id=None, type="TRACKER_UPDATE",
                        notification_key=f"visa_bulletin:{bulletin.id}", status="PENDING")
                .on_conflict_do_nothing(index_elements=[Notification.user_id, Notification.notification_key])
            )
        db.add(AuditEvent(
            actor=admin.email, action="VISA_BULLETIN_APPROVED", entity_type="visa_bulletin", entity_id=bulletin.id,
            metadata_={"month": month},
        ))
        db.commit()
    return _out(db, bulletin)
