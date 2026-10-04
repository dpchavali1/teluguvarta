"""P07 / ADR-041: exam and deadline reminders.

Public reads serve only APPROVED, upcoming items. Editors enter a date from an
official page (DRAFT), then a review step approves it; approval queues one alert
per alert-enabled follower of that exam. Reminders before the date are queued by
the notification job."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import AdminPrincipal, current_admin
from app.content.exam_deadline import entry_error, normalize_exam
from app.content.exam_deadline_db import queue_alerts
from app.db import get_db
from app.errors import APIError
from app.models import AuditEvent, ExamDeadline
from app.rate_limit import rate_limit_admin
from app.schemas import ExamDeadlineIn, ExamDeadlineOut

public_router = APIRouter(prefix="/v1/exam-deadlines", tags=["public"])
admin_router = APIRouter(
    prefix="/v1/admin/exam-deadlines", tags=["admin"], dependencies=[Depends(current_admin), Depends(rate_limit_admin)]
)


def _out(row: ExamDeadline) -> ExamDeadlineOut:
    return ExamDeadlineOut(
        id=row.id, exam=row.exam, kind=row.kind, title=row.title, deadline=row.deadline,
        source_url=row.source_url, status=row.status,
    )


def _validated(body: ExamDeadlineIn) -> str:
    problem = entry_error(body.exam, body.kind, body.title, body.source_url)
    if problem:
        raise APIError(422, "INVALID_ENTRY", problem)
    exam = normalize_exam(body.exam)
    assert exam is not None
    return exam


def _get(db: Session, item_id: UUID) -> ExamDeadline:
    row = db.scalars(select(ExamDeadline).where(ExamDeadline.id == item_id).with_for_update()).first()
    if row is None:
        raise APIError(404, "EXAM_DEADLINE_NOT_FOUND", "No such exam deadline")
    return row


@public_router.get("")
def list_upcoming(exam: str | None = Query(default=None), db: Session = Depends(get_db)) -> list[ExamDeadlineOut]:
    query = select(ExamDeadline).where(ExamDeadline.status == "APPROVED", ExamDeadline.deadline >= datetime.now(UTC).date())
    if exam is not None:
        key = normalize_exam(exam)
        if key is None:
            return []
        query = query.where(ExamDeadline.exam == key)
    return [_out(row) for row in db.scalars(query.order_by(ExamDeadline.deadline, ExamDeadline.exam).limit(100))]


@admin_router.get("")
def list_all(db: Session = Depends(get_db)) -> list[ExamDeadlineOut]:
    return [_out(row) for row in db.scalars(select(ExamDeadline).order_by(ExamDeadline.deadline.desc()).limit(200))]


@admin_router.post("", status_code=201)
def create_item(body: ExamDeadlineIn, admin: AdminPrincipal = Depends(current_admin), db: Session = Depends(get_db)) -> ExamDeadlineOut:
    exam = _validated(body)
    row = ExamDeadline(
        exam=exam, kind=body.kind, title=body.title.strip(), deadline=body.deadline,
        source_url=body.source_url, entered_by=admin.email,
    )
    db.add(row)
    db.flush()
    db.add(AuditEvent(actor=admin.email, action="EXAM_DEADLINE_DRAFTED", entity_type="exam_deadline", entity_id=row.id,
                      metadata_={"exam": exam, "kind": body.kind}))
    db.commit()
    return _out(row)


@admin_router.put("/{item_id}")
def edit_item(item_id: UUID, body: ExamDeadlineIn, admin: AdminPrincipal = Depends(current_admin), db: Session = Depends(get_db)) -> ExamDeadlineOut:
    exam = _validated(body)
    row = _get(db, item_id)
    if row.status != "DRAFT":
        raise APIError(409, "NOT_DRAFT", "Only a draft can be edited; withdraw and re-enter instead")
    row.exam, row.kind, row.title = exam, body.kind, body.title.strip()
    row.deadline, row.source_url, row.entered_by = body.deadline, body.source_url, admin.email
    db.add(AuditEvent(actor=admin.email, action="EXAM_DEADLINE_DRAFTED", entity_type="exam_deadline", entity_id=row.id,
                      metadata_={"exam": exam, "kind": body.kind}))
    db.commit()
    return _out(row)


@admin_router.post("/{item_id}/approve")
def approve_item(item_id: UUID, admin: AdminPrincipal = Depends(current_admin), db: Session = Depends(get_db)) -> ExamDeadlineOut:
    row = _get(db, item_id)
    if row.status == "WITHDRAWN":
        raise APIError(409, "WITHDRAWN", "A withdrawn date cannot be approved")
    if row.status != "APPROVED":
        row.status, row.approved_by, row.approved_at = "APPROVED", admin.email, datetime.now(UTC)
        db.flush()
        queue_alerts(db, row.id, row.exam, "new")
        db.add(AuditEvent(actor=admin.email, action="EXAM_DEADLINE_APPROVED", entity_type="exam_deadline", entity_id=row.id,
                          metadata_={"exam": row.exam}))
        db.commit()
    return _out(row)


@admin_router.post("/{item_id}/withdraw")
def withdraw_item(item_id: UUID, admin: AdminPrincipal = Depends(current_admin), db: Session = Depends(get_db)) -> ExamDeadlineOut:
    row = _get(db, item_id)
    if row.status != "WITHDRAWN":
        row.status = "WITHDRAWN"
        db.add(AuditEvent(actor=admin.email, action="EXAM_DEADLINE_WITHDRAWN", entity_type="exam_deadline", entity_id=row.id,
                          metadata_={"exam": row.exam}))
        db.commit()
    return _out(row)
