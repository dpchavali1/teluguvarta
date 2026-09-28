"""SQLAlchemy ORM models — only the columns app code currently reads/writes.

These map onto tables created by `infra/migrations/`, which stays the source
of truth for the full column list/constraints. Add fields here as later
tickets need them; don't mirror every migration column speculatively.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ENUM, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Matches the native Postgres enum created in infra/migrations (T03) — using
# the enum type here (not Text) so SQLAlchemy binds values the way psycopg
# expects for a `USER-DEFINED` column type, instead of relying on implicit
# unknown-type coercion.
_source_rights_status_enum = ENUM(
    "DISABLED", "LINK_ONLY", "LICENSED_METADATA", "LICENSED_REPURPOSE",
    name="source_rights_status",
    create_type=False,
)

# Matches the native `story_status` enum (T03) — needed (not just Text) so a
# query can compare `Story.status` against a plain string; Postgres has no
# implicit `story_status = varchar` operator (T11 hit this the first time
# anything filtered on `stories.status`).
_story_status_enum = ENUM(
    "DRAFT", "AI_READY", "REVIEW_REQUIRED", "APPROVED", "SCHEDULED",
    "PUBLISHED", "UPDATED", "RETRACTED", "CORRECTION_PENDING", "ARCHIVED",
    name="story_status",
    create_type=False,
)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str | None] = mapped_column(Text, nullable=True)
    role: Mapped[str | None] = mapped_column(Text, nullable=True)
    password_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    mfa_secret: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # ADR-006 device-scoped anonymous identity (T17): the opaque token the
    # client mints on first launch and sends as `Authorization: Bearer`.
    # NULL for admin users (identified by JWT, see app/routers/admin_auth.py).
    client_token: Mapped[str | None] = mapped_column(Text, nullable=True)


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    base_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    feed_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    country: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str | None] = mapped_column(Text, nullable=True)
    rights_status: Mapped[str] = mapped_column(_source_rights_status_enum, nullable=False, server_default="DISABLED")
    rights_evidence_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    rights_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewer: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Structured §5.1 evidence record beyond the first-class columns above:
    # terms_url, permitted_fields, restrictions, territory, expires_at, notes.
    rights_evidence: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    refresh_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    fail_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # §8.2 ranking's `source_quality` input (T16/ADR-005). Neutral default
    # until a later ticket exposes it in the source-registry admin CRUD.
    quality_score: Mapped[float] = mapped_column(Float, nullable=False, server_default="0.5")
    # ADR-015: configured category, the only input to the free-tier allowlist.
    category: Mapped[str | None] = mapped_column(Text, nullable=True)


class XAccount(Base):
    """X1: the X official-account adapter's fields, linked one-to-one to a
    `Source` row (`source_type='X_ACCOUNT'`). Deliberately doesn't duplicate
    `rights_status`/`active`/`last_success_at`/`last_error_at` — those live
    on the linked `Source` and are read through it, so an X account goes
    through the exact same rights gate as any other source (ADR-002) instead
    of a parallel approval flow.
    """

    __tablename__ = "x_accounts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sources.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    # Stable X user ID (§6.3.1) — admin records this on approval, not the
    # mutable @handle.
    x_user_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    handle: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    polling_cadence: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Incremental-fetch cursor for X2's `since_id`-only polling.
    since_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    budget_class: Mapped[str | None] = mapped_column(Text, nullable=True)


class XApiCallLog(Base):
    """X2 cost telemetry — one row per X official-account fetch attempt
    (§19: x_api_posts_read/x_api_cost_estimate/x_api_budget_remaining/
    rate-limit error counts). Mirrors `AiCallLog`'s per-call-attempt shape;
    see `app/x/budget.py`."""

    __tablename__ = "x_api_call_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    x_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("x_accounts.id", ondelete="CASCADE"), nullable=False
    )
    posts_read: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    cost_usd: Mapped[float] = mapped_column(Numeric(12, 6), nullable=False, server_default="0")
    # 'OK' | 'RATE_LIMITED' | 'ERROR' per `ck_x_api_call_log_status`.
    status: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class SourceItem(Base):
    __tablename__ = "source_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    external_id: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Fingerprint for near-duplicate detection (T09): sha256 of the
    # normalized title text, not the raw fetch bytes — see
    # `app/adapters/base.py::normalize()`.
    raw_hash: Mapped[str] = mapped_column(Text, nullable=False)
    # §6.4 ingestion state machine: DISCOVERED -> RIGHTS_BLOCKED | NORMALIZED
    # (T08) -> CLUSTERED (T09, fingerprint+cluster in one pass, so DEDUPED is
    # never persisted separately); later tickets add ENRICHED/REVIEW/... .
    ingest_status: Mapped[str] = mapped_column(Text, nullable=False, server_default="DISCOVERED")


class Story(Base):
    __tablename__ = "stories"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    canonical_slug: Mapped[str] = mapped_column(Text, nullable=False)
    # Native `story_status` enum (T03); defaults to DRAFT at the column level
    # like `Source.rights_status` — every Story T09 creates starts there.
    status: Mapped[str] = mapped_column(_story_status_enum, nullable=False, server_default="DRAFT")
    # 'NONE' | 'IMMIGRATION' | 'LEGAL' | 'FINANCIAL' | 'BREAKING' |
    # 'OBITUARY_ACCUSATION' per `ck_stories_sensitivity` (T11: §5.2's
    # publication-rules gate reads this).
    sensitivity: Mapped[str] = mapped_column(Text, nullable=False, server_default="NONE")
    # ADR-015: 'FREE_TIER_ALLOWED' | 'RESTRICTED' | 'UNKNOWN' (see app/ai/privacy.py).
    privacy_decision: Mapped[str] = mapped_column(Text, nullable=False, server_default="UNKNOWN")
    importance: Mapped[float] = mapped_column(Float, nullable=False, server_default="0")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # T17: separate, always-manual editorial gate for *sending a breaking
    # push* — distinct from the publish approval that already guards
    # `sensitivity == 'BREAKING'` reaching PUBLISHED at all (NON_NEGOTIABLES
    # #5). NULL means never send; set once an editor explicitly approves the
    # alert (see `app/routers/admin.py::approve_breaking_alert`).
    breaking_alert_approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class StoryVariant(Base):
    __tablename__ = "story_variants"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    story_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("stories.id", ondelete="CASCADE"), nullable=False)
    # 'en' | 'te' per `ck_story_variants_language`.
    language: Mapped[str] = mapped_column(Text, nullable=False)
    headline: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    why_matters: Mapped[str | None] = mapped_column(Text, nullable=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    model_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 'PENDING' | 'PASSED' | 'FAILED' per `ck_story_variants_qa_status`.
    qa_status: Mapped[str] = mapped_column(Text, nullable=False, server_default="PENDING")


class Entity(Base):
    __tablename__ = "entities"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # 'PERSON' | 'ORGANIZATION' | 'LOCATION' | 'EVENT' | 'OTHER' per
    # `ck_entities_type`.
    type: Mapped[str] = mapped_column(Text, nullable=False)
    canonical_name: Mapped[str] = mapped_column(Text, nullable=False)


class StoryEntity(Base):
    __tablename__ = "story_entities"

    story_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("stories.id", ondelete="CASCADE"), primary_key=True)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("entities.id", ondelete="CASCADE"), primary_key=True)


class EntityAlias(Base):
    __tablename__ = "entity_aliases"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("entities.id", ondelete="CASCADE"), nullable=False)
    alias: Mapped[str] = mapped_column(Text, nullable=False)
    # 'en' | 'te' per `ck_entity_aliases_language`.
    language: Mapped[str] = mapped_column(Text, nullable=False)


class Topic(Base):
    __tablename__ = "topics"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")


class StoryTopic(Base):
    __tablename__ = "story_topics"

    story_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("stories.id", ondelete="CASCADE"), primary_key=True)
    topic_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("topics.id", ondelete="CASCADE"), primary_key=True)
    weight: Mapped[float] = mapped_column(Numeric(), nullable=False, server_default="1")


class Profile(Base):
    """T17: first real persistence for §8.1 preferences and §9.4 notification
    controls, gated behind ADR-006's anonymous `users` row rather than a real
    account. T16 deliberately kept ranking preferences as request-time query
    params instead of reading this table — push notifications can't do that
    (the dispatch job has no request to read params from), so this is where
    persisted preferences become load-bearing."""

    __tablename__ = "profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    residence_country: Mapped[str | None] = mapped_column(Text, nullable=True)
    residence_region: Mapped[str | None] = mapped_column(Text, nullable=True)
    home_state: Mapped[str | None] = mapped_column(Text, nullable=True)
    home_city: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str] = mapped_column(Text, nullable=False, server_default="en")
    notification_mode: Mapped[str | None] = mapped_column(Text, nullable=True)
    breaking_alerts_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    daily_briefing_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    # Quiet hours as UTC hour-of-day (0-23); no per-user timezone column
    # exists in §12, so UTC is the deterministic, no-new-migration reading
    # (same class of judgment call as T16's "home" topic reuse).
    quiet_hours_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quiet_hours_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_alerts_per_day: Mapped[int] = mapped_column(Integer, nullable=False, server_default="5")


class UserTopic(Base):
    __tablename__ = "user_topics"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    topic_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("topics.id", ondelete="CASCADE"), primary_key=True)
    weight: Mapped[float] = mapped_column(Numeric(), nullable=False, server_default="1")


class PushToken(Base):
    __tablename__ = "push_tokens"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    # 'ios' | 'android' | 'web' per `ck_push_tokens_platform`.
    platform: Mapped[str] = mapped_column(Text, nullable=False)
    token: Mapped[str] = mapped_column(Text, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class Notification(Base):
    """T17 §14 `notification_dispatch` bookkeeping. `notification_key` +
    `user_id` is the dedupe unit (`uq_notifications_user_notification_key`,
    T03): a row is inserted (status=PENDING) *before* the send decision is
    made, so a retried/duplicate dispatch pass can never double-send — the
    unique constraint, not application logic, is what makes dedupe safe
    under concurrent workers."""

    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    story_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("stories.id", ondelete="CASCADE"), nullable=True)
    # 'DAILY_BRIEFING' | 'TOPIC_ALERT' | 'BREAKING_ALERT' per `ck_notifications_type`.
    type: Mapped[str] = mapped_column(Text, nullable=False)
    notification_key: Mapped[str] = mapped_column(Text, nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # 'PENDING' | 'SENT' | 'FAILED' | 'SUPPRESSED' per `ck_notifications_status`.
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="PENDING")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    # 'QUIET_HOURS' | 'DAILY_CAP' | NULL per `ck_notifications_suppressed_reason`.
    suppressed_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ReviewTask(Base):
    __tablename__ = "review_tasks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    story_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("stories.id", ondelete="CASCADE"), nullable=False)
    reviewer_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    # 'PENDING' | 'IN_REVIEW' | 'APPROVED' | 'REJECTED' per `ck_review_tasks_status`.
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="PENDING")
    decision: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class Correction(Base):
    """T12: one row per applied correction (`old_text_hash`/`new_text_hash`
    over the English variant's headline+summary+why_matters, not a full
    diff — the ticket's stated acceptance criterion). Also the wired hook
    for Telugu-variant invalidation: T13 owns regenerating the `te` variant
    this creates a gap for."""

    __tablename__ = "corrections"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    story_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("stories.id", ondelete="CASCADE"), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    old_text_hash: Mapped[str] = mapped_column(Text, nullable=False)
    new_text_hash: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class StorySource(Base):
    __tablename__ = "story_sources"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    story_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("stories.id", ondelete="CASCADE"), nullable=False)
    source_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("source_items.id", ondelete="RESTRICT"), nullable=False
    )
    # 'PRIMARY' | 'SUPPORTING' per the §12 `ck_story_sources_role` check.
    role: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)


class StoryClaim(Base):
    """P0-1 audit trail: every factual claim a `SUMMARY` generation call
    returned, and what the gateway did with it, persisted so the
    ref-membership/strip decision (`app/ai/gateway.py::_check_claims`) is
    auditable after the fact instead of vanishing with `GatewayOutcome`.
    """

    __tablename__ = "story_claims"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    story_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("stories.id", ondelete="CASCADE"), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    source_refs: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    # 'KEPT' | 'REMOVED_NO_REF' per `ck_story_claims_status`. Only these two
    # exist until ADR-011 decides the corroboration/title-match sufficiency
    # rule (docs/plans/gemini-hetzner-telugu-plan.md P0-1) — a claim citing a
    # real source_ref is KEPT as-is for now, same trust level as before P0-1,
    # minus the fabricated-ref case, which HOLDs the whole story instead of
    # ever reaching this table.
    status: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    type: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="PENDING")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    run_after: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    lock_expiry: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    dedupe_key: Mapped[str | None] = mapped_column(Text, nullable=True)


class AiCallLog(Base):
    """T10 cost telemetry — one row per AI gateway call attempt (§19: tokens/
    cost per task/provider/story/day). `status` distinguishes a successful
    call from one that hit a §7.5 failure mode, so both are queryable."""

    __tablename__ = "ai_call_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(Text, nullable=False)
    # 'SUCCESS' | 'RETRY_SUCCESS' | 'HOLD' | 'REVIEW_QUEUE' | 'UNAVAILABLE'
    status: Mapped[str] = mapped_column(Text, nullable=False)
    story_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stories.id", ondelete="SET NULL"), nullable=True
    )
    tokens_in: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    tokens_out: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    cost_usd: Mapped[float] = mapped_column(Numeric(12, 6), nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class StoryWhyMattersCache(Base):
    """T16/§8.3: one AI-generated "why this matters" per (story, audience
    segment), generated at most once and reused by every subsequent request
    for that pair — see `app/content/why_matters.py`."""

    __tablename__ = "story_why_matters_cache"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    story_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("stories.id", ondelete="CASCADE"), nullable=False)
    # 'general' | 'international_student' | 'graduate_opt' | 'professional' |
    # 'family_parent' | 'other' per `ck_story_why_matters_cache_segment`.
    segment: Mapped[str] = mapped_column(Text, nullable=False)
    why_matters: Mapped[str] = mapped_column(Text, nullable=False)
    model_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    actor: Mapped[str | None] = mapped_column(Text, nullable=True)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    entity_type: Mapped[str] = mapped_column(Text, nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class AdminLoginAttempt(Base):
    __tablename__ = "admin_login_attempts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(Text, nullable=False)
    ip: Mapped[str | None] = mapped_column(Text, nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
