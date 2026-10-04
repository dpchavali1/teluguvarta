"""Pydantic request/response models — the typed contract for every endpoint
in docs/SPEC.md §13. `packages/contracts` TS types are generated from these
via the FastAPI OpenAPI schema (see infra/scripts/generate_contracts.py).

Field shapes follow docs/SPEC.md §12 (core data model) and Appendix A
(sample content object). Endpoints in app/routers/ return stub/placeholder
data built from these models until the tickets that produce real data
(T06+) land — the ticket's acceptance criteria is that the *shape* is final.
"""

from datetime import date, datetime
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.content.places import MAX_FOLLOWED_PLACES
from app.content.visa_bulletin import MAX_VISA_FOLLOWS

Language = Literal["en", "te"]
TopicUrgency = Literal["INSTANT", "BREAKING_ONLY", "DIGEST"]
MAX_KEYWORDS = 20
MAX_KEYWORD_LENGTH = 40
MAX_SAVED_STORIES = 200
RightsStatus = Literal["DISABLED", "LINK_ONLY", "LICENSED_METADATA", "LICENSED_REPURPOSE"]
StoryStatus = Literal[
    "DRAFT", "AI_READY", "REVIEW_REQUIRED", "APPROVED", "SCHEDULED",
    "PUBLISHED", "UPDATED", "RETRACTED", "CORRECTION_PENDING", "ARCHIVED",
]
# ADR-019: BRIEF = a link-first brief from the auto-publish lane; readers label it.
StoryFormat = Literal["FULL", "BRIEF"]
# Review 2026-09-30 R7: admin list filter on the Telugu variant (MISSING = none).
TeluguFilter = Literal["MISSING", "PENDING", "PASSED", "FAILED"]
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
    # Published stories tagged with this topic (review #11: navigation shows
    # populated topics first).
    story_count: int = 0


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
    is_x_post: bool = False


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
    format: StoryFormat = "FULL"
    importance: float
    published_at: datetime | None = None
    updated_at: datetime
    topics: list[str] = Field(default_factory=list)
    countries: list[str] = Field(default_factory=list)
    places: list[str] = Field(default_factory=list)
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
    next_cursor: str | None = None
    topic: TopicOut
    stories: list[StoryOut] = Field(default_factory=list)


class SearchResponse(BaseModel):
    query: str
    items: list[StoryOut] = Field(default_factory=list)
    next_cursor: str | None = None


def _default_languages() -> list[Language]:
    return ["en", "te"]


class ConfigResponse(BaseModel):
    languages: list[Language] = Field(default_factory=_default_languages)
    features: dict[str, bool] = Field(default_factory=dict)
    topics: list[TopicOut] = Field(default_factory=list)


class ShareMetaResponse(BaseModel):
    title: str
    description: str
    canonical_url: str
    image_url: str | None = None  # branded Share Card deferred, ADR-002


# --- Authenticated (/v1/me) ---

class PlaceFollow(BaseModel):
    """ADR-043: a followed catalog place and its per-place alert switch."""

    place_id: str
    alerts: bool = False


class VisaFollow(BaseModel):
    """P07 / ADR-041: a tracked visa bulletin category + country."""

    category: str
    country: str = "ALL"
    alerts: bool = False


class VisaBulletinEntryIn(BaseModel):
    chart: str
    category: str
    country: str
    cutoff: str


class VisaBulletinIn(BaseModel):
    """Editor entry from the official bulletin; replaces a DRAFT's entries."""

    source_url: str
    entries: list[VisaBulletinEntryIn] = Field(min_length=1, max_length=200)


class VisaBulletinEntryOut(BaseModel):
    chart: str
    category: str
    country: str
    cutoff: str
    previous: str | None = None
    movement: str


class VisaBulletinOut(BaseModel):
    id: UUID
    month: str
    status: str
    source_url: str
    entries: list[VisaBulletinEntryOut]


class ProfileOut(BaseModel):
    residence_country: str | None = None
    residence_region: str | None = None
    home_state: str | None = None
    home_city: str | None = None
    language: Language = "en"
    notification_mode: str | None = None
    topics: list[TopicOut] = Field(default_factory=list)
    # §9.4 notification controls (T17). Defaults favor low frequency/high
    # relevance per the ticket text.
    breaking_alerts_enabled: bool = True
    daily_briefing_enabled: bool = True
    quiet_hours_start: int | None = None
    quiet_hours_end: int | None = None
    max_alerts_per_day: int = 5
    # P02 / ADR-042
    home_tz: str | None = None
    residence_tz: str | None = None
    digest_morning_hour: int | None = None
    digest_evening_hour: int | None = None
    topic_urgency: dict[str, TopicUrgency] = Field(default_factory=dict)
    keywords: list[str] = Field(default_factory=list)
    saved_story_ids: list[UUID] = Field(default_factory=list)
    follow_places: list[PlaceFollow] = Field(default_factory=list)
    follow_visa: list[VisaFollow] = Field(default_factory=list)


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
    breaking_alerts_enabled: bool | None = None
    daily_briefing_enabled: bool | None = None
    quiet_hours_start: int | None = None
    quiet_hours_end: int | None = None
    max_alerts_per_day: int | None = None
    # P02 / ADR-042. For tz and digest hours an explicit null clears the value;
    # keywords/saved_story_ids: omitted keeps, [] clears.
    home_tz: str | None = None
    residence_tz: str | None = None
    digest_morning_hour: int | None = Field(default=None, ge=0, le=23)
    digest_evening_hour: int | None = Field(default=None, ge=0, le=23)
    topic_urgency: dict[str, TopicUrgency] | None = None
    keywords: list[str] | None = Field(default=None, max_length=MAX_KEYWORDS)
    saved_story_ids: list[UUID] | None = Field(default=None, max_length=MAX_SAVED_STORIES)
    # ADR-043: omitted keeps, [] clears; unknown ids are dropped, more than 10 is a 422.
    follow_places: list[PlaceFollow] | None = Field(default=None, max_length=MAX_FOLLOWED_PLACES)
    follow_visa: list[VisaFollow] | None = Field(default=None, max_length=MAX_VISA_FOLLOWS)

    @field_validator("home_tz", "residence_tz")
    @classmethod
    def _valid_tz(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError, OSError) as exc:
            raise ValueError("must be an IANA timezone name, e.g. America/Chicago") from exc
        return value

    @field_validator("keywords")
    @classmethod
    def _normalize_keywords(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        cleaned: list[str] = []
        for raw in value:
            keyword = " ".join(raw.lower().split())
            if not 1 <= len(keyword) <= MAX_KEYWORD_LENGTH:
                raise ValueError(f"each keyword must be 1-{MAX_KEYWORD_LENGTH} characters")
            if keyword not in cleaned:
                cleaned.append(keyword)
        return cleaned


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


NotificationType = Literal["DAILY_BRIEFING", "TOPIC_ALERT", "BREAKING_ALERT", "DIGEST", "STORY_UPDATE", "TRACKER_UPDATE"]


class NotificationOut(BaseModel):
    """§9.4 notification history — deep link is `story_id` (None means the
    home feed, e.g. DAILY_BRIEFING or a suppressed/retracted target)."""

    id: UUID
    type: NotificationType
    story_id: UUID | None
    status: Literal["PENDING", "SENT", "FAILED", "SUPPRESSED"]
    suppressed_reason: Literal["QUIET_HOURS", "DAILY_CAP"] | None = None
    sent_at: datetime | None
    created_at: datetime


AnalyticsEventName = Literal[
    # §17 core events (T18) — every client-observable one; server-only
    # events (a job outcome — see app/analytics.py's EVENT_NAMES) are
    # logged directly by the job code, never posted through this endpoint.
    "app_open", "feed_view", "story_open", "story_save", "story_share",
    "language_switch", "search", "notification_open", "notification_opt_in",
    "onboarding_complete", "account_delete_request", "report_issue",
    # Pre-T18 (T17) client-posted event kept for backward compatibility.
    "notification_received",
]


EVENT_MAX_PROPERTIES = 20
EVENT_MAX_KEY_CHARS = 64
EVENT_MAX_VALUE_CHARS = 500


class AnalyticsEventIn(BaseModel):
    event: AnalyticsEventName
    # ADR-029: flat, bounded properties — clients only send ids, counts and
    # short strings, so anything larger is rejected rather than logged.
    properties: dict[str, str | int | float | bool | None] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _drop_report_text(cls, data: object) -> object:
        # ADR-029: report text goes to POST /v1/stories/{id}/reports only.
        # Older app builds still send it here; drop it before validation so
        # they keep working and the text is never logged.
        if isinstance(data, dict) and data.get("event") == "report_issue" and isinstance(data.get("properties"), dict):
            data = {**data, "properties": {k: v for k, v in data["properties"].items() if k != "description"}}
        return data

    @field_validator("properties")
    @classmethod
    def _bounded(cls, properties: dict) -> dict:
        if len(properties) > EVENT_MAX_PROPERTIES:
            raise ValueError(f"at most {EVENT_MAX_PROPERTIES} properties")
        for key, value in properties.items():
            if len(key) > EVENT_MAX_KEY_CHARS:
                raise ValueError(f"property names are at most {EVENT_MAX_KEY_CHARS} characters")
            if isinstance(value, str) and len(value) > EVENT_MAX_VALUE_CHARS:
                raise ValueError(f"property values are at most {EVENT_MAX_VALUE_CHARS} characters")
        return properties


class AnalyticsEventResponse(BaseModel):
    accepted: bool = True


ReaderReportCategory = Literal["FACTUAL_ERROR", "TRANSLATION", "BROKEN_LINK", "WRONG_IMAGE", "OFFENSIVE", "OTHER"]
ReaderReportStatus = Literal["OPEN", "RESOLVED", "DISMISSED"]
ReaderReportResolution = Literal["CORRECTED", "RETRACTED", "NO_CHANGE", "DUPLICATE", "SPAM"]


class ReaderReportIn(BaseModel):
    """ADR-029: a private report on a public story. No login required."""

    model_config = ConfigDict(extra="forbid")

    category: ReaderReportCategory
    description: str | None = Field(default=None, max_length=2000)
    language: Language | None = None
    platform: Literal["web", "ios", "android"] | None = None


class ReaderReportAccepted(BaseModel):
    accepted: bool = True


# --- Admin ---

class AdminLoginRequest(BaseModel):
    email: str
    password: str
    # Required only once this admin has MFA enrolled (see
    # `app/routers/admin_auth.py`'s /mfa/enroll). Omitting it when MFA is
    # enrolled fails with MFA_REQUIRED, not a silent bypass.
    mfa_code: str | None = None


class AdminLoginResponse(BaseModel):
    # ADR-028: the session itself is the HttpOnly `tte_admin` cookie set on
    # this response; the body carries nothing a script could reuse.
    expires_in: int
    role: Literal["EDITOR", "ADMIN"]
    # ADR-012: true when the session is a restricted mfa_enrollment one (no
    # mfa_secret set yet) — only /mfa/setup and /mfa/enroll accept it. The
    # admin UI must route straight to enrollment, not a normal session.
    mfa_enrollment_required: bool = False


class AdminCurrentSessionOut(BaseModel):
    email: str
    role: Literal["EDITOR", "ADMIN"]
    mfa_enrollment_required: bool
    # The session ends at the earlier of these unless a request comes first
    # (which moves `idle_expires_at`).
    expires_at: datetime
    idle_expires_at: datetime


class AdminSessionOut(BaseModel):
    id: UUID
    created_at: datetime
    last_seen_at: datetime
    expires_at: datetime
    user_agent: str | None
    current: bool


class AdminSessionListOut(BaseModel):
    items: list[AdminSessionOut]


class MfaSetupResponse(BaseModel):
    secret: str
    otpauth_url: str


class MfaEnrollRequest(BaseModel):
    secret: str
    code: str


class MfaStatusResponse(BaseModel):
    enabled: bool


class MfaDisableRequest(BaseModel):
    code: str


class RightsEvidence(BaseModel):
    """§5.1 evidence record beyond the first-class rights_evidence_url/
    rights_reviewed_at/reviewer columns on `AdminSourceOut`."""

    terms_url: str | None = None
    permitted_fields: list[str] = Field(default_factory=list)
    restrictions: str | None = None
    territory: str | None = None
    expires_at: datetime | None = None
    notes: str | None = None
    # ADR-020: why the feed text is public domain; required to turn on
    # `description_evidence`.
    public_domain_basis: str | None = None


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
    description_evidence: bool = False
    refresh_minutes: int | None = None
    category: str | None = None
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
    category: str | None = None
    # Optional: enable + activate in one call (preset flow). Same ADR-002 gate
    # as PATCH; omitted → the source starts DISABLED/inactive as before.
    rights_status: RightsStatus | None = None
    rights_evidence_url: str | None = None
    rights_reviewed_at: datetime | None = None
    reviewer: str | None = None
    rights_evidence: RightsEvidence | None = None
    active: bool | None = None


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
    # ADR-020: ADMIN only; needs LINK_ONLY + rights_evidence.public_domain_basis.
    description_evidence: bool | None = None
    refresh_minutes: int | None = None
    category: str | None = None
    active: bool | None = None


class AdminXAccountOut(BaseModel):
    id: UUID
    source_id: UUID
    x_user_id: str
    handle: str
    priority: int
    polling_cadence: int | None = None
    since_id: str | None = None
    budget_class: str | None = None
    # Denormalized from the linked Source — same rights gate as any other
    # source (ADR-002), no parallel approval flow for X accounts.
    rights_status: RightsStatus
    active: bool
    last_success_at: datetime | None = None
    last_error_at: datetime | None = None
    # X4: per-account health/cost, so an admin never has to read logs.
    fail_count: int
    circuit_breaker_tripped: bool
    recent_error_count_24h: int
    month_to_date_cost_usd: float
    # True when the X4 budget guard is currently skipping this account's
    # polling (over monthly budget AND `budget_class="LOW"`) — distinct from
    # `active`, which is the manual/rights-gate on/off switch.
    budget_paused: bool


class AdminXAccountCreate(BaseModel):
    x_user_id: str
    handle: str
    priority: int = 0
    polling_cadence: int | None = None
    budget_class: str | None = None


class AdminXAccountUpdate(BaseModel):
    handle: str | None = None
    priority: int | None = None
    polling_cadence: int | None = None
    since_id: str | None = None
    budget_class: str | None = None


class ReviewQueueItemOut(BaseModel):
    headline: str | None = None
    # The primary source item's own title, so a story with no draft yet is
    # still identifiable in the queue.
    source_title: str | None = None
    source_names: list[str] = Field(default_factory=list)
    id: UUID
    story_id: UUID
    reason: str
    status: Literal["PENDING", "IN_REVIEW", "APPROVED", "REJECTED"]
    decision: str | None = None
    created_at: datetime
    topics: list[str] = Field(default_factory=list)
    te_qa_status: Literal["PENDING", "PASSED", "FAILED"] | None = None


class ReviewQueuePageOut(BaseModel):
    """Review 2026-09-30 R7: one page of the queue. `total` counts the
    filtered queue; the `*_total` counts are the whole queue."""

    items: list[ReviewQueueItemOut]
    total: int
    pending_total: int
    danger_total: int
    unclassified_total: int
    oldest_created_at: datetime | None = None
    next_cursor: str | None = None
    generated_at: datetime


class AdminStoryListItemOut(BaseModel):
    id: UUID
    canonical_slug: str
    status: StoryStatus
    format: StoryFormat
    sensitivity: str
    published_at: datetime | None = None
    last_activity_at: datetime | None = None
    headline: str | None = None
    te_headline: str | None = None
    te_qa_status: Literal["PENDING", "PASSED", "FAILED"] | None = None
    source_title: str | None = None
    source_names: list[str] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)
    corrections: int
    review_pending: bool


class AdminStoryListOut(BaseModel):
    items: list[AdminStoryListItemOut]
    total: int
    status_counts: dict[str, int]
    corrected_total: int
    generated_at: datetime


class AdminActionRequest(BaseModel):
    reason: str | None = None


class AdminRetryAiRequest(BaseModel):
    """ADR-025: `stage` is which AI stage to try again."""

    stage: Literal["GENERATE", "TRANSLATE"]
    reason: str = Field(min_length=1)


class AdminAiHoldOut(BaseModel):
    story_id: UUID
    stage: str
    story_status: str
    headline: str | None
    last_status: str | None
    updated_at: datetime
    resets_used: int
    resets_left: int


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


class AdminTopicsRequest(BaseModel):
    """The full set of topic slugs for a story (replaces what it had)."""

    topics: list[str] = Field(max_length=5)
    reason: str | None = None


ImportanceLevel = Literal["LOW", "NORMAL", "HIGH"]


class AdminCountriesRequest(BaseModel):
    """ADR-027: the full set of event countries for a story (replaces what it had)."""

    countries: list[str] = Field(max_length=5)
    reason: str | None = None


class AdminPlacesRequest(BaseModel):
    """ADR-043: the full set of event places for a story (replaces what it had)."""

    places: list[str] = Field(max_length=8)
    reason: str | None = None


class AdminImportanceRequest(BaseModel):
    """ADR-027: an editor's importance level; null returns to the computed score."""

    level: ImportanceLevel | None
    reason: str | None = None


class AdminDraftRequest(BaseModel):
    """An editor-written story variant for a story still in review — the
    fallback when no AI route may draft it (e.g. NO_PAID_PROVIDER)."""

    headline: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    why_matters: str | None = None
    reason: str | None = None


class AdminActionResponse(BaseModel):
    story_id: UUID
    status: StoryStatus


class AdminTeluguRepairRequest(BaseModel):
    action: Literal["withhold", "regenerate"]
    reason: str = Field(min_length=1, max_length=500)
    english_text_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    telugu_text_hash: str = Field(pattern=r"^[a-f0-9]{64}$")


class AdminTeluguRepairOut(BaseModel):
    qa_issues: list[str] = Field(default_factory=list)
    english_text_hash: str | None = None
    telugu_text_hash: str | None = None
    resets_left: int
    can_regenerate: bool


class AdminStorySourceOut(BaseModel):
    role: Literal["PRIMARY", "SUPPORTING"]
    url: str
    title: str | None = None
    published_at: datetime | None = None
    source_name: str
    source_rights_status: RightsStatus
    # ADR-020: stored feed description (public-domain sources only). Admin only.
    description: str | None = None


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
    format: StoryFormat = "FULL"
    importance: float
    # ADR-027: the editor's override, if any, and the model's confidence
    # (None for a story no model classified).
    importance_override: ImportanceLevel | None = None
    classification_confidence: float | None = None
    published_at: datetime | None = None
    variants: dict[Language, StoryVariantOut] = Field(default_factory=dict)
    telugu_repair: AdminTeluguRepairOut | None = None
    topics: list[str] = Field(default_factory=list)
    countries: list[str] = Field(default_factory=list)
    places: list[str] = Field(default_factory=list)
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
    # ADR-019 link-first brief lane.
    auto_publish_briefs: bool = False
    auto_publish_briefs_daily_cap: int = 0
    briefs_published_today: int = 0


class RuntimeSwitchOut(BaseModel):
    """ADR-031: one dashboard pause switch and its effective state."""

    key: Literal["ai", "auto_publish"]
    # What the dashboard switch says (no row = on).
    enabled: bool
    # False when a server env flag holds it off whatever the dashboard says.
    env_allows: bool
    effective: bool
    updated_by: str | None = None
    updated_at: datetime | None = None
    note: str | None = None
    # Stories waiting on this switch: DRAFT for ai, AI_READY for auto_publish.
    waiting: int = 0


class RuntimeSwitchUpdate(BaseModel):
    enabled: bool
    note: str | None = Field(default=None, max_length=500)


class AdminAutoBriefOut(BaseModel):
    """ADR-019: a story the brief lane auto-approved, for the after-publish
    check (retract/correct from the story page)."""

    story_id: UUID
    status: StoryStatus
    headline: str | None = None
    summary: str | None = None
    source_titles: list[str] = Field(default_factory=list)
    matched_tokens: list[str] = Field(default_factory=list)
    approved_at: datetime


class AdminAuditEventOut(BaseModel):
    id: UUID
    actor: str | None = None
    action: str
    entity_type: str
    entity_id: UUID
    metadata: dict = Field(default_factory=dict)
    created_at: datetime


class AdminAuditPageOut(BaseModel):
    items: list[AdminAuditEventOut]
    next_cursor: str | None = None


class SourceIngestionHealthOut(BaseModel):
    """T18 §9.3 "ingestion health": one row per source, scoped to the
    `source_fetch` jobs run in the last 24h (not all-time counters, which
    `fail_count`/`AdminSourceOut` already expose)."""

    source_id: UUID
    source_name: str
    success_count_24h: int
    failure_count_24h: int
    fail_count: int
    circuit_breaker_tripped: bool
    last_success_at: datetime | None = None
    last_error_at: datetime | None = None


class JobQueueHealthOut(BaseModel):
    counts_by_status: dict[str, int]
    oldest_pending_age_seconds: float | None = None


class AiCostRowOut(BaseModel):
    task: str
    day: str
    tokens_in: int
    tokens_out: int
    cost_usd: float


class AiCostSummaryOut(BaseModel):
    month_to_date_cost_usd: float
    monthly_budget_usd: float | None = None
    monthly_budget_remaining_usd: float | None = None
    today_cost_usd: float
    daily_alert_usd: float | None = None
    over_monthly_budget: bool
    # Review 2026-09-30 R4: ADR-024's hard cap and what the gateway is doing
    # (`app.ai.budget.budget_mode`). Costs are token-price estimates.
    monthly_hard_cap_usd: float | None = None
    hard_cap_remaining_usd: float | None = None
    mode: Literal["NORMAL", "CLASSIFICATION_ONLY", "PAID_STOPPED"]
    # Today/month (and the budget) are UTC; the Gemini free-tier quota resets
    # at midnight Pacific.
    day_start: datetime
    month_start: datetime
    quota_resets_at: datetime
    rows: list[AiCostRowOut]


class XCostSummaryOut(BaseModel):
    """X4 §19: same shape as `AiCostSummaryOut` but scoped to X API spend,
    plus how many low-priority accounts the budget guard is currently
    pausing as a result."""

    month_to_date_cost_usd: float
    monthly_budget_usd: float | None = None
    monthly_budget_remaining_usd: float | None = None
    over_monthly_budget: bool
    low_priority_accounts_paused: int


class OpsCheckOut(BaseModel):
    """Review 2026-09-30 R3: one host-side operation (`app/ops_status.py`)."""

    check: str
    label: str
    state: Literal["OK", "STALE", "FAILING", "NEVER"]
    last_success_at: datetime | None = None
    success_detail: str | None = None
    last_failure_at: datetime | None = None
    failure_detail: str | None = None
    max_age_seconds: int | None = None


class ObservabilityOut(BaseModel):
    ingestion_health: list[SourceIngestionHealthOut]
    job_queue: JobQueueHealthOut
    ai_cost: AiCostSummaryOut
    x_cost: XCostSummaryOut
    operations: list[OpsCheckOut]


class AiCostFiguresOut(BaseModel):
    calls: int
    cost_usd: float
    tokens_in: int
    # Part of tokens_out / tokens_in respectively (see AiCallLog).
    tokens_out: int
    tokens_thinking: int
    tokens_cached: int
    # Outcomes other than SUCCESS / RETRY_SUCCESS: billed, output not used.
    unusable_calls: int
    unusable_cost_usd: float


class AiCostTotalsOut(AiCostFiguresOut):
    # Cost of constrained retries that succeeded after an unusable first reply.
    retry_cost_usd: float


class AiCostDayOut(AiCostFiguresOut):
    day: date


class AiCostBreakdownOut(AiCostFiguresOut):
    provider: str
    model: str
    task: str
    tier: Literal["PAID", "FREE", "NONE"]


class AiCostOutcomeOut(BaseModel):
    status: str
    calls: int
    cost_usd: float


class AiCostStoryStatusOut(BaseModel):
    status: str
    stories: int
    calls: int
    cost_usd: float


class AiCostCohortOut(BaseModel):
    """Stories first published in the window and every call ever linked to
    them — a lifecycle figure, not window spend."""

    stories_published: int
    lifecycle_calls: int
    lifecycle_cost_usd: float


class AiCostStoryOut(BaseModel):
    story_id: UUID
    headline: str | None
    status: str
    calls: int
    unusable_calls: int
    cost_usd: float


class AiCostReportOut(BaseModel):
    """Review 2026-09-30 R5: `app.ai.cost_report.cost_report`. Inclusive UTC days."""

    start: date
    end: date
    window_start: datetime
    window_end: datetime
    totals: AiCostTotalsOut
    by_day: list[AiCostDayOut]
    breakdown: list[AiCostBreakdownOut]
    outcomes: list[AiCostOutcomeOut]
    unlinked: AiCostFiguresOut
    by_story_status: list[AiCostStoryStatusOut]
    publication_cohort: AiCostCohortOut
    top_stories: list[AiCostStoryOut]


class PipelineAiWorkOut(BaseModel):
    stage: Literal["GENERATE", "TRANSLATE"]
    retrying: int
    exhausted: int
    oldest_update_at: datetime | None


class PipelineStatusOut(BaseModel):
    """Review 2026-09-30 R5: `app.pipeline_status.pipeline_status`."""

    stories_by_status: dict[str, int]
    published_24h: int
    review_pending: int
    review_oldest_at: datetime | None
    ai_work: list[PipelineAiWorkOut]
    # Live stories readers see only in English: no PASSED Telugu variant.
    telugu_missing: int
    telugu_failed_qa: int
    telugu_missing_oldest_published_at: datetime | None
    # ADR-029: reader reports no editor has closed yet.
    reports_open: int = 0
    reports_oldest_open_at: datetime | None = None


class CoverageItemsOut(BaseModel):
    """Item cohort outcomes; every key but `items` adds up to `items`."""

    items: int
    rights_blocked: int
    backlog_skipped: int
    not_relevant: int
    live: int
    in_review: int
    other: int


class CoverageSourceOut(CoverageItemsOut):
    source_id: UUID
    name: str
    publisher: str
    category: str | None
    active: bool
    rights_status: str
    published: int
    median_lag_hours: float | None


class CoveragePublisherOut(BaseModel):
    publisher: str
    feeds: int
    items: int
    live: int
    published: int
    share: float


class CoverageTopicOut(BaseModel):
    slug: str
    name: str
    active: bool
    published: int
    in_review: int


class CoverageDayOut(BaseModel):
    day: date
    published: int
    publishers: int


class CoverageLagOut(BaseModel):
    """Publication cohort by hours from the publisher's timestamp to ours.
    Each bucket starts where the previous one ends."""

    under_1h: int
    under_3h: int
    under_12h: int
    under_24h: int
    over_24h: int
    unknown: int


class CoverageReportOut(BaseModel):
    """Review 2026-09-30 R8: `app.coverage_report.coverage_report`. Inclusive UTC days."""

    start: date
    end: date
    items: CoverageItemsOut
    published: int
    published_without_source: int
    published_untagged: int
    publishers_published: int
    top_publisher: str | None
    top_publisher_share: float
    lag: CoverageLagOut
    by_day: list[CoverageDayOut]
    publishers: list[CoveragePublisherOut]
    sources: list[CoverageSourceOut]
    topics: list[CoverageTopicOut]


class AdminReaderReportOut(BaseModel):
    """ADR-029: one reader report, with enough story context for the list."""

    id: UUID
    story_id: UUID
    story_slug: str
    story_status: StoryStatus
    story_headline: str | None
    category: ReaderReportCategory
    # None when the reader left it blank or the retention purge erased it.
    description: str | None
    description_purged_at: datetime | None
    language: Language | None
    platform: Literal["web", "ios", "android"] | None
    # Daily-rotating sender id: equal values = same sender, same UTC day.
    sender: str
    repeat_count: int
    status: ReaderReportStatus
    resolution: ReaderReportResolution | None
    resolution_note: str | None
    resolved_by_email: str | None
    resolved_at: datetime | None
    correction_id: UUID | None
    created_at: datetime


class AdminReaderReportListOut(BaseModel):
    items: list[AdminReaderReportOut]
    total: int
    open_count: int


class AdminReaderReportResolveRequest(BaseModel):
    """ADR-029: CORRECTED/RETRACTED close as RESOLVED, the rest as DISMISSED."""

    model_config = ConfigDict(extra="forbid")

    resolution: ReaderReportResolution
    note: str | None = Field(default=None, max_length=1000)
    correction_id: UUID | None = None


class AdminFeedTestRequest(BaseModel):
    feed_url: str


class AdminFeedTestOut(BaseModel):
    ok: bool
    item_count: int
    headlines: list[str]
    error: str | None
