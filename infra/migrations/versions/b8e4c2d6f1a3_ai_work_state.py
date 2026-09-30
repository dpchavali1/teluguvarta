"""ai_work_state: durable per-story retry state for AI sweeps

Review 2026-09-29 finding #1: each time-bucketed `ai_classify` /
`ai_translate` sweep is a new job, so the queue's bounded `attempts` never
limited how often one story was re-sent to the provider. One row per
(story, stage) records failures, the next permitted attempt, and a cached
successful classification for the current input version.

Revision ID: b8e4c2d6f1a3
Revises: a7d3f5b9c2e1
Create Date: 2026-09-29 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "b8e4c2d6f1a3"
down_revision: Union[str, None] = "a7d3f5b9c2e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ai_work_state",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "story_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("stories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("stage", sa.Text(), nullable=False),
        sa.Column("input_version", sa.Text(), nullable=False),
        sa.Column("invalid_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("transient_failures", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_status", sa.Text(), nullable=True),
        sa.Column("failure_class", sa.Text(), nullable=True),
        sa.Column("cached_classification", postgresql.JSONB(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("stage IN ('GENERATE', 'TRANSLATE')", name="ck_ai_work_state_stage"),
        sa.CheckConstraint(
            "failure_class IS NULL OR failure_class IN ('TRANSIENT', 'INVALID_OUTPUT', 'EXHAUSTED')",
            name="ck_ai_work_state_failure_class",
        ),
        sa.UniqueConstraint("story_id", "stage", name="uq_ai_work_state_story_stage"),
    )


def downgrade() -> None:
    op.drop_table("ai_work_state")
