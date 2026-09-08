"""core data model

Implements every entity from docs/SPEC.md §12 (`User` through `AuditEvent`)
plus the two DB-level guarantees docs/tickets/T03.md calls out explicitly:

- `sources.rights_status` is a native enum defaulting to DISABLED at the
  column level (not just app validation) — NON_NEGOTIABLES #4.
- `stories.status` legal transitions are enforced by a BEFORE UPDATE trigger
  (`enforce_story_status_transition`), not an app-level guard function or a
  plain CHECK constraint, because a CHECK constraint alone cannot see the
  previous row value needed to validate OLD -> NEW pairs, and there is no
  application/domain layer yet for T03 to hook a guard function into (T04+
  build the API; this ticket is DB-only). This keeps the state machine
  enforced as close to the data as possible, consistent with how
  `rights_status` is handled.

Table names are the plural of each §12 entity (`users`, `stories`, ...) to
avoid `user` being a reserved identifier; every field from the entity's
field list in §12 is present, plus a surrogate UUID `id` primary key (not in
the §12 field lists, added uniformly for stable FK targets and easy
indexing) and a few columns the ticket text or referenced spec sections
require explicitly beyond the §12 table (`jobs.lock_expiry`/`dedupe_key` per
the ticket description of §14's queue pattern; `notifications.notification_key`
per §14's stated dedupe rule "deduplicate by user_id + notification_key").

Revision ID: 0c23c235e618
Revises:
Create Date: 2026-09-08 17:02:38.991151

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '0c23c235e618'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


SOURCE_RIGHTS_STATUSES = ("DISABLED", "LINK_ONLY", "LICENSED_METADATA", "LICENSED_REPURPOSE")
STORY_STATUSES = (
    "DRAFT", "AI_READY", "REVIEW_REQUIRED", "APPROVED", "SCHEDULED",
    "PUBLISHED", "UPDATED", "RETRACTED", "CORRECTION_PENDING",
)
# V1 jobs, verbatim from docs/SPEC.md §14.
JOB_TYPES = (
    "source_fetch", "x_official_account_fetch", "source_normalize",
    "story_fingerprint", "story_cluster", "ai_classify", "ai_summarize",
    "ai_translate", "story_validate", "review_reminder", "publish_scheduler",
    "notification_dispatch", "cleanup", "health_check", "backup_verify",
)

source_rights_status = postgresql.ENUM(*SOURCE_RIGHTS_STATUSES, name="source_rights_status", create_type=False)
story_status_enum = postgresql.ENUM(*STORY_STATUSES, name="story_status", create_type=False)

UUID_PK = lambda: sa.Column(  # noqa: E731
    "id",
    postgresql.UUID(as_uuid=True),
    primary_key=True,
    server_default=sa.text("gen_random_uuid()"),
)

STORY_TRANSITION_TRIGGER_SQL = """
CREATE FUNCTION enforce_story_status_transition() RETURNS trigger AS $$
DECLARE
  allowed boolean;
BEGIN
  IF NEW.status = OLD.status THEN
    RETURN NEW;
  END IF;
  allowed := (
    (OLD.status = 'DRAFT' AND NEW.status = 'AI_READY') OR
    (OLD.status = 'AI_READY' AND NEW.status = 'REVIEW_REQUIRED') OR
    (OLD.status = 'REVIEW_REQUIRED' AND NEW.status = 'APPROVED') OR
    (OLD.status = 'APPROVED' AND NEW.status = 'SCHEDULED') OR
    (OLD.status = 'SCHEDULED' AND NEW.status = 'PUBLISHED') OR
    (OLD.status = 'PUBLISHED' AND NEW.status = 'UPDATED') OR
    (OLD.status = 'PUBLISHED' AND NEW.status = 'RETRACTED') OR
    (OLD.status = 'UPDATED' AND NEW.status = 'CORRECTION_PENDING') OR
    (OLD.status = 'CORRECTION_PENDING' AND NEW.status = 'UPDATED')
  );
  IF NOT allowed THEN
    RAISE EXCEPTION 'illegal story status transition: % -> %', OLD.status, NEW.status
      USING ERRCODE = '23514';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""

STORY_TRANSITION_TRIGGER_DROP_SQL = "DROP FUNCTION enforce_story_status_transition() CASCADE;"


def upgrade() -> None:
    bind = op.get_bind()

    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    source_rights_status.create(bind, checkfirst=True)
    story_status_enum.create(bind, checkfirst=True)

    op.create_table(
        "users",
        UUID_PK(),
        sa.Column("email", sa.Text(), nullable=True, unique=True),
        sa.Column("auth_provider", sa.Text(), nullable=True),
        sa.Column("auth_provider_id", sa.Text(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.UniqueConstraint("auth_provider", "auth_provider_id", name="uq_users_auth_provider_identity"),
    )

    op.create_table(
        "profiles",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("residence_country", sa.Text(), nullable=True),
        sa.Column("residence_region", sa.Text(), nullable=True),
        sa.Column("home_state", sa.Text(), nullable=True),
        sa.Column("home_city", sa.Text(), nullable=True),
        sa.Column("language", sa.Text(), nullable=False, server_default="en"),
        sa.Column("notification_mode", sa.Text(), nullable=True),
        sa.CheckConstraint("language IN ('en', 'te')", name="ck_profiles_language"),
    )

    op.create_table(
        "topics",
        UUID_PK(),
        sa.Column("slug", sa.Text(), nullable=False, unique=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )

    op.create_table(
        "user_topics",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("topic_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("topics.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("weight", sa.Numeric(), nullable=False, server_default="1"),
    )

    op.create_table(
        "sources",
        UUID_PK(),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("feed_url", sa.Text(), nullable=True),
        sa.Column("rights_status", source_rights_status, nullable=False, server_default="DISABLED"),
        sa.Column("rights_evidence", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("health", sa.Text(), nullable=True),
    )

    op.create_table(
        "source_items",
        UUID_PK(),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("external_id", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("published_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("raw_hash", sa.Text(), nullable=False),
        sa.UniqueConstraint("source_id", "external_id", name="uq_source_items_source_external_id"),
    )

    op.create_table(
        "stories",
        UUID_PK(),
        sa.Column("canonical_slug", sa.Text(), nullable=False, unique=True),
        sa.Column("status", story_status_enum, nullable=False, server_default="DRAFT"),
        sa.Column("sensitivity", sa.Text(), nullable=False, server_default="NONE"),
        sa.Column("importance", sa.Float(), nullable=False, server_default="0"),
        sa.Column("published_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(
            "sensitivity IN ('NONE', 'IMMIGRATION', 'LEGAL', 'FINANCIAL', 'BREAKING', 'OBITUARY_ACCUSATION')",
            name="ck_stories_sensitivity",
        ),
    )

    op.execute(STORY_TRANSITION_TRIGGER_SQL)
    op.execute(
        """
        CREATE TRIGGER story_status_transition_guard
        BEFORE UPDATE OF status ON stories
        FOR EACH ROW
        EXECUTE FUNCTION enforce_story_status_transition();
        """
    )

    op.create_table(
        "story_variants",
        UUID_PK(),
        sa.Column("story_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("stories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("language", sa.Text(), nullable=False),
        sa.Column("headline", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("why_matters", sa.Text(), nullable=True),
        sa.Column("generated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("model_version", sa.Text(), nullable=True),
        sa.Column("qa_status", sa.Text(), nullable=False, server_default="PENDING"),
        sa.CheckConstraint("language IN ('en', 'te')", name="ck_story_variants_language"),
        sa.CheckConstraint("qa_status IN ('PENDING', 'PASSED', 'FAILED')", name="ck_story_variants_qa_status"),
        sa.UniqueConstraint("story_id", "language", name="uq_story_variants_story_language"),
    )
    op.execute(
        "CREATE INDEX ix_story_variants_headline_trgm ON story_variants USING gin (headline gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX ix_story_variants_summary_trgm ON story_variants USING gin (summary gin_trgm_ops)"
    )

    op.create_table(
        "story_sources",
        UUID_PK(),
        sa.Column("story_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("stories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("source_items.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("evidence_rank", sa.Integer(), nullable=True),
        sa.CheckConstraint("role IN ('PRIMARY', 'SUPPORTING')", name="ck_story_sources_role"),
        sa.UniqueConstraint("story_id", "source_item_id", name="uq_story_sources_story_source_item"),
    )

    op.create_table(
        "entities",
        UUID_PK(),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("canonical_name", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "type IN ('PERSON', 'ORGANIZATION', 'LOCATION', 'EVENT', 'OTHER')",
            name="ck_entities_type",
        ),
    )

    op.create_table(
        "story_entities",
        sa.Column("story_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("stories.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("entities.id", ondelete="CASCADE"), primary_key=True),
    )

    op.create_table(
        "entity_aliases",
        UUID_PK(),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("entities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("alias", sa.Text(), nullable=False),
        sa.Column("language", sa.Text(), nullable=False),
        sa.CheckConstraint("language IN ('en', 'te')", name="ck_entity_aliases_language"),
        sa.UniqueConstraint("entity_id", "alias", "language", name="uq_entity_aliases_entity_alias_language"),
    )

    op.create_table(
        "story_topics",
        sa.Column("story_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("stories.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("topic_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("topics.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("weight", sa.Numeric(), nullable=False, server_default="1"),
    )

    op.create_table(
        "review_tasks",
        UUID_PK(),
        sa.Column("story_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("stories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reviewer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="PENDING"),
        sa.Column("decision", sa.Text(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(
            "status IN ('PENDING', 'IN_REVIEW', 'APPROVED', 'REJECTED')",
            name="ck_review_tasks_status",
        ),
    )

    op.create_table(
        "corrections",
        UUID_PK(),
        sa.Column("story_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("stories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("old_text_hash", sa.Text(), nullable=False),
        sa.Column("new_text_hash", sa.Text(), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table(
        "notifications",
        UUID_PK(),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("story_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("stories.id", ondelete="CASCADE"), nullable=True),
        sa.Column("type", sa.Text(), nullable=False),
        # Idempotency key per §14: "deduplicate by user_id + notification_key".
        sa.Column("notification_key", sa.Text(), nullable=False),
        sa.Column("sent_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="PENDING"),
        sa.CheckConstraint(
            "type IN ('DAILY_BRIEFING', 'TOPIC_ALERT', 'BREAKING_ALERT')",
            name="ck_notifications_type",
        ),
        sa.CheckConstraint(
            "status IN ('PENDING', 'SENT', 'FAILED', 'SUPPRESSED')",
            name="ck_notifications_status",
        ),
        sa.UniqueConstraint("user_id", "notification_key", name="uq_notifications_user_notification_key"),
    )

    op.create_table(
        "jobs",
        UUID_PK(),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("status", sa.Text(), nullable=False, server_default="PENDING"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("run_after", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        # lock_expiry/dedupe_key: required by docs/tickets/T03.md's description
        # of the §14 Postgres job queue pattern, beyond the §12 field list.
        sa.Column("lock_expiry", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("locked_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("dedupe_key", sa.Text(), nullable=True, unique=True),
        sa.CheckConstraint(
            "type IN (" + ", ".join(f"'{job_type}'" for job_type in JOB_TYPES) + ")",
            name="ck_jobs_type",
        ),
        sa.CheckConstraint("status IN ('PENDING', 'RUNNING', 'DONE', 'FAILED')", name="ck_jobs_status"),
    )
    op.create_index("ix_jobs_status_run_after", "jobs", ["status", "run_after"])

    op.create_table(
        "audit_events",
        UUID_PK(),
        sa.Column("actor", sa.Text(), nullable=True),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("entity_type", sa.Text(), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_index("ix_jobs_status_run_after", table_name="jobs")
    op.drop_table("jobs")
    op.drop_table("notifications")
    op.drop_table("corrections")
    op.drop_table("review_tasks")
    op.drop_table("story_topics")
    op.drop_table("entity_aliases")
    op.drop_table("story_entities")
    op.drop_table("entities")
    op.drop_table("story_sources")
    op.execute("DROP INDEX IF EXISTS ix_story_variants_summary_trgm")
    op.execute("DROP INDEX IF EXISTS ix_story_variants_headline_trgm")
    op.drop_table("story_variants")
    op.execute("DROP TRIGGER story_status_transition_guard ON stories")
    op.execute(STORY_TRANSITION_TRIGGER_DROP_SQL)
    op.drop_table("stories")
    op.drop_table("source_items")
    op.drop_table("sources")
    op.drop_table("user_topics")
    op.drop_table("topics")
    op.drop_table("profiles")
    op.drop_table("users")

    bind = op.get_bind()
    story_status_enum.drop(bind, checkfirst=True)
    source_rights_status.drop(bind, checkfirst=True)
