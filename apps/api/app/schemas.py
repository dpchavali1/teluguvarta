"""Pydantic request/response models — the typed contract for every endpoint
in docs/SPEC.md §13. `packages/contracts` TS types are generated from these
via the FastAPI OpenAPI schema (see infra/scripts/generate_contracts.py).

Field shapes follow docs/SPEC.md §12 (core data model) and Appendix A
(sample content object). Endpoints in app/routers/ return stub/placeholder
data built from these models until the tickets that produce real data
(T06+) land — the ticket's acceptance criteria is that the *shape* is final.
"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

Language = Literal["en", "te"]
RightsStatus = Literal["DISABLED", "LINK_ONLY", "LICENSED_METADATA", "LICENSED_REPURPOSE"]
StoryStatus = Literal[
    "DRAFT", "AI_READY", "REVIEW_REQUIRED", "APPROVED", "SCHEDULED",
    "PUBLISHED", "UPDATED", "RETRACTED", "CORRECTION_PENDING", "ARCHIVED",
]
Sensitivity = Literal["NONE", "IMMIGRATION", "LEGAL", "FINANCIAL", "BREAKING", "OBITUARY_ACCUSATION"]
# §3.1 life-stage values, explicit-only per NON_NEGOTIABLES (never inferred) — §8.3's
# "why this matters" audience segment (T16).
Segment = Literal[
    "general", "international_student", "graduate_opt", "professional", "family_parent", "other",
]


# --- Shared ---

class TopicOut(BaseModel):
    slug: str
    name: str
    active: bool = True


class StoryVariantOut(BaseModel):
    language: Language
    headline: str
    summary: str
    why_matters: str | None = None
    qa_status: Literal["PENDING", "PASSED", "FAILED"] = "PENDING"


class StorySourceOut(BaseModel):
    url: str
    title: str | None = None
    published_at: datetime | None = None


class PersonalizationOut(BaseModel):
    """§8.4 explainability: present only when the request supplied
    preferences to rank against, and only ever built from signals that
    actually matched (T16/ADR-005)."""

    score: float
    explanation: str | None = None
    why_matters: str | None = None


class StoryOut(BaseModel):
    """Appendix A's sample content object, shaped for API consumption."""

    id: UUID
    canonical_slug: str
    status: StoryStatus
    sensitivity: Sensitivity
    importance: float
    published_at: datetime | None = None
    updated_at: datetime
    topics: list[str] = Field(default_factory=list)
    countries: list[str] = Field(default_factory=list)
    variants: dict[Language, StoryVariantOut] = Field(default_factory=dict)
    sources: list[StorySourceOut] = Field(default_factory=list)
    personalization: PersonalizationOut | None = None


class StoriesListResponse(BaseModel):
    items: list[StoryOut]
    next_cursor: str | None = None


# --- Public ---

class HomeResponse(BaseModel):
    top_stories: list[StoryOut] = Field(default_factory=list)
    topics: list[TopicOut] = Field(default_factory=list)


class TopicDetailResponse(BaseModel):
    topic: TopicOut
    stories: list[StoryOut] = Field(default_factory=list)


class SearchResponse(BaseModel):
    query: str
    items: list[StoryOut] = Field(default_factory=list)


class ConfigResponse(BaseModel):
    languages: list[Language] = Field(default_factory=lambda: ["en", "te"])
    features: dict[str, bool] = Field(default_factory=dict)
    topics: list[TopicOut] = Field(default_factory=list)


class ShareMetaResponse(BaseModel):
    title: str
    description: str
    canonical_url: str
    image_url: str | None = None  # branded Share Card deferred, ADR-002


# --- Authenticated (/v1/me) ---

class ProfileOut(BaseModel):
    residence_country: str | None = None
    residence_region: str | None = None
    home_state: str | None = None
    home_city: str | None = None
    language: Language = "en"
    notification_mode: str | None = None
    topics: list[TopicOut] = Field(default_factory=list)


class MeResponse(BaseModel):
    id: UUID
    email: str | None = None
    profile: ProfileOut
    saved_story_ids: list[UUID] = Field(default_factory=list)


class PreferencesUpdate(BaseModel):
    residence_country: str | None = None
    residence_region: str | None = None
    home_state: str | None = None
    home_city: str | None = None
    language: Language | None = None
    notification_mode: str | None = None
    topic_slugs: list[str] | None = None


class SavedStoryResponse(BaseModel):
    story_id: UUID
    saved: bool


class PushTokenCreate(BaseModel):
    token: str
    platform: Literal["ios", "android", "web"]


class PushTokenResponse(BaseModel):
    registered: bool


class DeleteAccountResponse(BaseModel):
    deleted: bool


# --- Admin ---

class AdminLoginRequest(BaseModel):
    email: str
    password: str


class AdminLoginResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    role: Literal["EDITOR", "ADMIN"]


class RightsEvidence(BaseModel):
    """§5.1 evidence record beyond the first-class rights_evidence_url/
    rights_reviewed_at/reviewer columns on `AdminSourceOut`."""

    terms_url: str | None = None
    permitted_fields: list[str] = Field(default_factory=list)
    restrictions: str | None = None
    territory: str | None = None
    expires_at: datetime | None = None
    notes: str | None = None


class AdminSourceOut(BaseModel):
    id: UUID
    name: str
    base_url: str | None = None
    feed_url: str | None = None
    source_type: str | None = None
    country: str | None = None
    language: str | None = None
    rights_status: RightsStatus
    rights_evidence_url: str | None = None
    rights_reviewed_at: datetime | None = None
    reviewer: str | None = None
    rights_evidence: RightsEvidence = Field(default_factory=RightsEvidence)
    refresh_minutes: int | None = None
    active: bool
    fail_count: int
    last_success_at: datetime | None = None
    last_error_at: datetime | None = None


class AdminSourceCreate(BaseModel):
    name: str
    base_url: str | None = None
    feed_url: str | None = None
    source_type: str | None = None
    country: str | None = None
    language: str | None = None
    refresh_minutes: int | None = None


class AdminSourceUpdate(BaseModel):
    name: str | None = None
    base_url: str | None = None
    feed_url: str | None = None
    source_type: str | None = None
    country: str | None = None
    language: str | None = None
    rights_status: RightsStatus | None = None
    rights_evidence_url: str | None = None
    rights_reviewed_at: datetime | None = None
    reviewer: str | None = None
    rights_evidence: RightsEvidence | None = None
    refresh_minutes: int | None = None
    active: bool | None = None


class ReviewQueueItemOut(BaseModel):
    id: UUID
    story_id: UUID
    reason: str
    status: Literal["PENDING", "IN_REVIEW", "APPROVED", "REJECTED"]
    decision: str | None = None
    created_at: datetime


class AdminActionRequest(BaseModel):
    reason: str | None = None


class AdminRejectRequest(BaseModel):
    reason: str | None = None
    # False (default) sends the story back to DRAFT for reprocessing; True
    # archives it (editor decision that it should never publish) — the
    # ticket's literal "reject -> back to draft or archived".
    archive: bool = False


class AdminCorrectionRequest(BaseModel):
    reason: str
    headline: str | None = None
    summary: str | None = None
    why_matters: str | None = None


class AdminActionResponse(BaseModel):
    story_id: UUID
    status: StoryStatus


class AdminStorySourceOut(BaseModel):
    role: Literal["PRIMARY", "SUPPORTING"]
    url: str
    title: str | None = None
    published_at: datetime | None = None
    source_name: str
    source_rights_status: RightsStatus


class AdminCorrectionOut(BaseModel):
    id: UUID
    reason: str
    old_text_hash: str
    new_text_hash: str
    created_at: datetime


class AdminStoryDetailOut(BaseModel):
    """The §9.3/§15 review-screen payload: source + rights state, original
    metadata, the AI draft, sensitivity, and correction/audit history side
    by side."""

    id: UUID
    canonical_slug: str
    status: StoryStatus
    sensitivity: Sensitivity
    importance: float
    published_at: datetime | None = None
    variants: dict[Language, StoryVariantOut] = Field(default_factory=dict)
    sources: list[AdminStorySourceOut] = Field(default_factory=list)
    review_task: ReviewQueueItemOut | None = None
    corrections: list[AdminCorrectionOut] = Field(default_factory=list)


class AdminJobOut(BaseModel):
    id: UUID
    type: str
    status: Literal["PENDING", "RUNNING", "DONE", "FAILED"]
    attempts: int
    run_after: datetime
    locked_at: datetime | None = None
    last_error: str | None = None


class KillSwitchesOut(BaseModel):
    """Read-only view of the §15 global kill switches (env-backed; no
    publish logic exists to gate yet — see T12)."""

    auto_publish_global: bool
    auto_publish_category_immigration: bool


class AdminAuditEventOut(BaseModel):
    id: UUID
    actor: str | None = None
    action: str
    entity_type: str
    entity_id: UUID
    metadata: dict = Field(default_factory=dict)
    created_at: datetime
