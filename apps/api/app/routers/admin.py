"""Admin endpoints. Auth is stubbed pending T05 — see app/auth.py.

Approve/reject/retract/correct only change `stories.status` (T03's
DB-enforced state machine already rejects illegal transitions); the actual
editorial workflow (review UI, notifications, etc.) is T12.

Source registry (docs/tickets/T06.md): only `DISABLED` and `LINK_ONLY` are
reachable rights tiers in this build phase (ADR-002); moving a source off
`DISABLED` requires rights evidence to already be on file and is restricted
to the `ADMIN` role (see the ADR-002 addendum) — an `EDITOR` can create/edit
everything else about a source but cannot flip the rights gate itself.
"""

import os
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import AdminPrincipal, current_admin
from app.db import get_db
from app.errors import APIError
from app.models import AuditEvent, Source
from app.schemas import (
    AdminActionRequest,
    AdminActionResponse,
    AdminAuditEventOut,
    AdminJobOut,
    AdminSourceCreate,
    AdminSourceOut,
    AdminSourceUpdate,
    KillSwitchesOut,
    ReviewQueueItemOut,
    RightsEvidence,
)

router = APIRouter(prefix="/v1/admin", tags=["admin"], dependencies=[Depends(current_admin)])

# ADR-002: only these two tiers are reachable in this build phase.
ENABLABLE_RIGHTS_STATUSES = {"DISABLED", "LINK_ONLY"}
# Fields that must already be on file before a source can move off DISABLED.
REQUIRED_EVIDENCE_FIELDS = ("rights_evidence_url", "rights_reviewed_at", "reviewer")


def _write_audit_event(db: Session, actor: str, action: str, entity_type: str, entity_id: UUID, metadata: dict) -> None:
    db.add(AuditEvent(actor=actor, action=action, entity_type=entity_type, entity_id=entity_id, metadata_=metadata))


def _source_out(source: Source) -> AdminSourceOut:
    return AdminSourceOut(
        id=source.id,
        name=source.name,
        base_url=source.base_url,
        feed_url=source.feed_url,
        source_type=source.source_type,
        country=source.country,
        language=source.language,
        rights_status=source.rights_status,
        rights_evidence_url=source.rights_evidence_url,
        rights_reviewed_at=source.rights_reviewed_at,
        reviewer=source.reviewer,
        rights_evidence=RightsEvidence(**source.rights_evidence),
        refresh_minutes=source.refresh_minutes,
        active=source.active,
        fail_count=source.fail_count,
        last_success_at=source.last_success_at,
        last_error_at=source.last_error_at,
    )


@router.get("/sources")
def list_sources(db: Session = Depends(get_db)) -> list[AdminSourceOut]:
    sources = db.scalars(select(Source).order_by(Source.name)).all()
    return [_source_out(s) for s in sources]


@router.post("/sources", status_code=201)
def create_source(
    body: AdminSourceCreate, admin: AdminPrincipal = Depends(current_admin), db: Session = Depends(get_db)
) -> AdminSourceOut:
    source = Source(
        name=body.name,
        base_url=body.base_url,
        feed_url=body.feed_url,
        source_type=body.source_type,
        country=body.country,
        language=body.language,
        refresh_minutes=body.refresh_minutes,
    )
    db.add(source)
    db.flush()
    _write_audit_event(db, admin.email, "SOURCE_CREATED", "source", source.id, {"name": source.name})
    db.commit()
    db.refresh(source)
    return _source_out(source)


@router.patch("/sources/{source_id}")
def update_source(
    source_id: UUID,
    body: AdminSourceUpdate,
    admin: AdminPrincipal = Depends(current_admin),
    db: Session = Depends(get_db),
) -> AdminSourceOut:
    source = db.get(Source, source_id)
    if source is None:
        raise APIError(404, "SOURCE_NOT_FOUND", f"No source with id '{source_id}'")

    updates = body.model_dump(exclude_unset=True, exclude={"rights_evidence"})
    # Dumped separately (with mode="json") so nested datetimes serialize to
    # strings for the JSONB column — `updates` above keeps real datetime
    # objects, since those map onto real DateTime columns.
    rights_evidence = body.rights_evidence.model_dump(mode="json") if body.rights_evidence is not None else None
    new_rights_status = updates.get("rights_status")

    if new_rights_status is not None and new_rights_status not in ENABLABLE_RIGHTS_STATUSES:
        raise APIError(
            422,
            "RIGHTS_TIER_NOT_ENABLED",
            f"'{new_rights_status}' is not enabled in this build phase — only DISABLED and LINK_ONLY "
            "are reachable per ADR-002",
        )

    if new_rights_status is not None and new_rights_status != "DISABLED" and new_rights_status != source.rights_status:
        if admin.role != "ADMIN":
            raise APIError(403, "FORBIDDEN", "Only an ADMIN can enable a source (move it off DISABLED)")
        merged: dict[str, Any] = {field: updates.get(field, getattr(source, field)) for field in REQUIRED_EVIDENCE_FIELDS}
        missing = [field for field, value in merged.items() if not value]
        if missing:
            raise APIError(
                422,
                "RIGHTS_EVIDENCE_REQUIRED",
                f"Cannot enable source: missing rights evidence field(s) {', '.join(missing)}",
            )

    for field, value in updates.items():
        setattr(source, field, value)
    if rights_evidence is not None:
        source.rights_evidence = rights_evidence

    audit_metadata = body.model_dump(exclude_unset=True, mode="json")
    _write_audit_event(db, admin.email, "SOURCE_UPDATED", "source", source.id, audit_metadata)
    db.commit()
    db.refresh(source)
    return _source_out(source)


@router.get("/kill-switches")
def get_kill_switches() -> KillSwitchesOut:
    return KillSwitchesOut(
        auto_publish_global=os.environ.get("AUTO_PUBLISH_GLOBAL", "false").lower() == "true",
        auto_publish_category_immigration=os.environ.get("AUTO_PUBLISH_CATEGORY_IMMIGRATION", "false").lower()
        == "true",
    )


@router.get("/review-queue")
def get_review_queue() -> list[ReviewQueueItemOut]:
    return []


@router.post("/stories/{story_id}/approve")
def approve_story(story_id: UUID, body: AdminActionRequest) -> AdminActionResponse:
    raise APIError(404, "STORY_NOT_FOUND", f"No story with id '{story_id}'")


@router.post("/stories/{story_id}/reject")
def reject_story(story_id: UUID, body: AdminActionRequest) -> AdminActionResponse:
    raise APIError(404, "STORY_NOT_FOUND", f"No story with id '{story_id}'")


@router.post("/stories/{story_id}/retract")
def retract_story(story_id: UUID, body: AdminActionRequest) -> AdminActionResponse:
    raise APIError(404, "STORY_NOT_FOUND", f"No story with id '{story_id}'")


@router.post("/stories/{story_id}/correct")
def correct_story(story_id: UUID, body: AdminActionRequest) -> AdminActionResponse:
    raise APIError(404, "STORY_NOT_FOUND", f"No story with id '{story_id}'")


@router.get("/jobs")
def list_jobs() -> list[AdminJobOut]:
    return []


@router.get("/audit")
def list_audit_events() -> list[AdminAuditEventOut]:
    return []
