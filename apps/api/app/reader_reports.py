"""ADR-029: private reader reports — intake, editorial resolution and the
retention purge. Reports are editor-only; nothing here is reachable from a
public read endpoint, and the free text never goes to analytics."""

from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import AuditEvent, Correction, ReaderReport, Story
from app.security import _jwt_secret

CATEGORIES = ("FACTUAL_ERROR", "TRANSLATION", "BROKEN_LINK", "WRONG_IMAGE", "OFFENSIVE", "OTHER")
# Resolutions that close a report as RESOLVED (the story changed) vs.
# DISMISSED (it didn't).
RESOLVED_BY = {"CORRECTED", "RETRACTED"}
DISMISSED_BY = {"NO_CHANGE", "DUPLICATE", "SPAM"}
RESOLUTIONS = tuple(sorted(RESOLVED_BY | DISMISSED_BY))

DESCRIPTION_MAX_CHARS = 2000
# ADR-029 retention: the text goes, the row stays.
PURGE_AFTER_CLOSED = timedelta(days=90)
PURGE_AFTER_OPEN = timedelta(days=180)
PURGE_BATCH = 1000


def client_hash(client_ip: str, now: datetime) -> str:
    """HMAC of the client address and UTC day: links same-day reports from
    one sender without storing an IP or tracking anyone across days."""
    message = f"reader-report:{client_ip}:{now.date().isoformat()}".encode()
    return hmac.new(_jwt_secret().encode(), message, hashlib.sha256).hexdigest()[:32]


def submit_report(
    db: Session,
    *,
    story_id: UUID,
    category: str,
    description: str | None,
    language: str | None,
    platform: str | None,
    sender: str,
) -> ReaderReport:
    """Stores a report, or counts a repeat on the sender's OPEN report for
    the same story and category. Commits."""
    existing = _open_duplicate(db, sender, story_id, category)
    if existing is None:
        report = ReaderReport(
            story_id=story_id, category=category, description=description or None,
            language=language, platform=platform, client_hash=sender,
        )
        db.add(report)
        try:
            db.commit()
            return report
        except IntegrityError:
            # A concurrent identical report won the partial unique index.
            db.rollback()
            existing = _open_duplicate(db, sender, story_id, category)
            if existing is None:
                raise
    db.execute(update(ReaderReport).where(ReaderReport.id == existing.id).values(repeat_count=ReaderReport.repeat_count + 1))
    db.commit()
    db.refresh(existing)
    return existing


def _open_duplicate(db: Session, sender: str, story_id: UUID, category: str) -> ReaderReport | None:
    return db.scalars(
        select(ReaderReport).where(
            ReaderReport.client_hash == sender, ReaderReport.story_id == story_id,
            ReaderReport.category == category, ReaderReport.status == "OPEN",
        )
    ).first()


class ResolveError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


def resolve_report(
    db: Session,
    report: ReaderReport,
    *,
    resolution: str,
    note: str | None,
    correction_id: UUID | None,
    actor_email: str,
    actor_id: UUID,
    now: datetime,
) -> None:
    """Closes an OPEN report and audits it. A report never changes the story
    itself: CORRECTED must point at a correction already made on this story
    through the audited correction flow, RETRACTED at a retracted story."""
    if report.status != "OPEN":
        raise ResolveError(409, "REPORT_CLOSED", f"Report is already {report.status}")
    if resolution == "CORRECTED":
        correction = db.get(Correction, correction_id) if correction_id else None
        if correction is None or correction.story_id != report.story_id:
            raise ResolveError(422, "CORRECTION_REQUIRED", "CORRECTED needs a correction made on this report's story")
    elif correction_id is not None:
        raise ResolveError(422, "CORRECTION_NOT_ALLOWED", "Only a CORRECTED resolution links a correction")
    if resolution == "RETRACTED":
        story = db.get(Story, report.story_id)
        if story is None or story.status != "RETRACTED":
            raise ResolveError(422, "STORY_NOT_RETRACTED", "Retract the story first, then resolve the report as RETRACTED")

    report.status = "RESOLVED" if resolution in RESOLVED_BY else "DISMISSED"
    report.resolution = resolution
    report.resolution_note = note or None
    report.correction_id = correction_id
    report.resolved_by = actor_id
    report.resolved_at = now
    db.add(AuditEvent(
        actor=actor_email, action="READER_REPORT_RESOLVED", entity_type="reader_report", entity_id=report.id,
        metadata_={
            "story_id": str(report.story_id), "status": report.status, "resolution": resolution, "note": note,
            "correction_id": str(correction_id) if correction_id else None,
        },
    ))
    db.commit()


def purge_descriptions(db: Session, now: datetime) -> int:
    """Erases report text past its retention window, at most `PURGE_BATCH`
    rows per run (the next daily run takes the rest). Idempotent."""
    due = select(ReaderReport.id).where(
        ReaderReport.description.is_not(None),
        (
            ((ReaderReport.status != "OPEN") & (ReaderReport.resolved_at < now - PURGE_AFTER_CLOSED))
            | ((ReaderReport.status == "OPEN") & (ReaderReport.created_at < now - PURGE_AFTER_OPEN))
        ),
    ).limit(PURGE_BATCH)
    ids = list(db.scalars(due))
    if ids:
        db.execute(
            update(ReaderReport).where(ReaderReport.id.in_(ids)).values(description=None, description_purged_at=now)
        )
    db.commit()
    return len(ids)
