"""ai_call_log table (T10)

One row per AI gateway call attempt, feeding §19's cost telemetry
(tokens/cost per task/provider/story/day) and the MONTHLY_AI_BUDGET_USD /
DAILY_AI_ALERT_USD guardrails. `status` records the §7.5 outcome (success,
retry-success, hold, review-queue, unavailable) so failure modes are
queryable too, not just successful spend.

Revision ID: 7a4c9e2b5d10
Revises: 2f6a0e7c9d41
Create Date: 2026-09-08 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "7a4c9e2b5d10"
down_revision: Union[str, None] = "2f6a0e7c9d41"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ai_call_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("task", sa.Text(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column(
            "story_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("stories.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("tokens_in", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tokens_out", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Numeric(12, 6), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(
            "status IN ('SUCCESS', 'RETRY_SUCCESS', 'HOLD', 'REVIEW_QUEUE', 'UNAVAILABLE')",
            name="ck_ai_call_log_status",
        ),
    )
    op.create_index("ix_ai_call_log_task_created_at", "ai_call_log", ["task", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_ai_call_log_task_created_at", table_name="ai_call_log")
    op.drop_table("ai_call_log")
