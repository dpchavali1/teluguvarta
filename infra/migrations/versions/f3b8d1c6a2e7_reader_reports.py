"""reader_reports: private reader reports and their editorial lifecycle

ADR-029 (review 2026-09-30 R6). A reader's "Report an issue" used to land
only in container logs. Each report is now a row an editor resolves or
dismisses; its free text is erased on a schedule (`app/jobs/cleanup.py`)
while the row stays for correction-rate metrics.

Revision ID: f3b8d1c6a2e7
Revises: e7c2a9d4f1b6
Create Date: 2026-09-30 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "f3b8d1c6a2e7"
down_revision: Union[str, None] = "e7c2a9d4f1b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "reader_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("story_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("stories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("language", sa.Text(), nullable=True),
        sa.Column("platform", sa.Text(), nullable=True),
        sa.Column("client_hash", sa.Text(), nullable=False),
        sa.Column("repeat_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.Text(), nullable=False, server_default="OPEN"),
        sa.Column("resolution", sa.Text(), nullable=True),
        sa.Column("resolution_note", sa.Text(), nullable=True),
        sa.Column("resolved_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "correction_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("corrections.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("description_purged_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "category IN ('FACTUAL_ERROR', 'TRANSLATION', 'BROKEN_LINK', 'WRONG_IMAGE', 'OFFENSIVE', 'OTHER')",
            name="ck_reader_reports_category",
        ),
        sa.CheckConstraint("status IN ('OPEN', 'RESOLVED', 'DISMISSED')", name="ck_reader_reports_status"),
        sa.CheckConstraint(
            "resolution IS NULL OR resolution IN ('CORRECTED', 'RETRACTED', 'NO_CHANGE', 'DUPLICATE', 'SPAM')",
            name="ck_reader_reports_resolution",
        ),
        sa.CheckConstraint("platform IS NULL OR platform IN ('web', 'ios', 'android')", name="ck_reader_reports_platform"),
        sa.CheckConstraint("(status = 'OPEN') = (resolution IS NULL)", name="ck_reader_reports_resolved_has_resolution"),
    )
    op.create_index("ix_reader_reports_status_created", "reader_reports", ["status", "created_at"])
    op.create_index("ix_reader_reports_story", "reader_reports", ["story_id"])
    # ADR-029: at most one OPEN report per sender + story + category.
    op.create_index(
        "uq_reader_reports_open_sender",
        "reader_reports",
        ["client_hash", "story_id", "category"],
        unique=True,
        postgresql_where=sa.text("status = 'OPEN'"),
    )


def downgrade() -> None:
    op.drop_table("reader_reports")
