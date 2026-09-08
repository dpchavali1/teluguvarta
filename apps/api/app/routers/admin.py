"""Admin endpoints. Auth is stubbed pending T05 — see app/auth.py.

Approve/reject/retract/correct only change `stories.status` (T03's
DB-enforced state machine already rejects illegal transitions); the actual
editorial workflow (review UI, notifications, etc.) is T12.
"""

from uuid import UUID

from fastapi import APIRouter, Depends

from app.auth import current_admin
from app.errors import APIError
from app.schemas import (
    AdminActionRequest,
    AdminActionResponse,
    AdminAuditEventOut,
    AdminJobOut,
    AdminSourceOut,
    AdminSourceUpdate,
    ReviewQueueItemOut,
)

router = APIRouter(prefix="/v1/admin", tags=["admin"], dependencies=[Depends(current_admin)])


@router.get("/sources")
def list_sources() -> list[AdminSourceOut]:
    return []


@router.patch("/sources/{source_id}")
def update_source(source_id: UUID, body: AdminSourceUpdate) -> AdminSourceOut:
    raise APIError(404, "SOURCE_NOT_FOUND", f"No source with id '{source_id}'")


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
