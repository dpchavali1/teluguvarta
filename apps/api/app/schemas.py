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
    "PUBLISHED", "UPDATED", "RETRACTED", "CORRECTION_PENDING",
]
Sensitivity = Literal["NONE", "IMMIGRATION", "LEGAL", "FINANCIAL", "BREAKING", "OBITUARY_ACCUSATION"]


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


class AdminSourceOut(BaseModel):
    id: UUID
    name: str
    feed_url: str | None = None
    rights_status: RightsStatus
    active: bool
    health: str | None = None


class AdminSourceUpdate(BaseModel):
    name: str | None = None
    feed_url: str | None = None
    rights_status: RightsStatus | None = None
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


class AdminActionResponse(BaseModel):
    story_id: UUID
    status: StoryStatus


class AdminJobOut(BaseModel):
    id: UUID
    type: str
    status: Literal["PENDING", "RUNNING", "DONE", "FAILED"]
    attempts: int
    run_after: datetime
    locked_at: datetime | None = None
    last_error: str | None = None


class AdminAuditEventOut(BaseModel):
    id: UUID
    actor: str | None = None
    action: str
    entity_type: str
    entity_id: UUID
    metadata: dict = Field(default_factory=dict)
    created_at: datetime
