"""x_api_call_log table (X2)

One row per X official-account fetch attempt, feeding §19's X API cost
telemetry (x_api_posts_read/x_api_cost_estimate/x_api_budget_remaining/
rate-limit error counts) and the optional MONTHLY_X_API_BUDGET_USD
guardrail — same shape as T10's `ai_call_log` (`app/ai/budget.py`), scoped
to `app/x/budget.py` instead.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-09-09 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "x_api_call_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "x_account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("x_accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("posts_read", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Numeric(12, 6), nullable=False, server_default="0"),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("status IN ('OK', 'RATE_LIMITED', 'ERROR')", name="ck_x_api_call_log_status"),
    )
    op.create_index("ix_x_api_call_log_account_created_at", "x_api_call_log", ["x_account_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_x_api_call_log_account_created_at", table_name="x_api_call_log")
    op.drop_table("x_api_call_log")
