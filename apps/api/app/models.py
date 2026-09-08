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
    "PUBLISHED", "UPDATED", "RETRACTED", "CORRECTION_PENDING",
    name="story_status",
    create_type=False,
)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    email: Mapped[str | None] = mapped_column(Text, nullable=True)
    role: Mapped[str | None] = mapped_column(Text, nullable=True)
    password_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    mfa_secret: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


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
    importance: Mapped[float] = mapped_column(Float, nullable=False, server_default="0")


class StoryVariant(Base):
    __tablename__ = "story_variants"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    story_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("stories.id", ondelete="CASCADE"), nullable=False)
    # 'en' | 'te' per `ck_story_variants_language`.
    language: Mapped[str] = mapped_column(Text, nullable=False)
    headline: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    why_matters: Mapped[str | None] = mapped_column(Text, nullable=True)
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
