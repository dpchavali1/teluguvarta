"""ADR-015: sources.category and stories.privacy_decision

`sources.category` is the configured category the free-tier allowlist keys on.
`stories.privacy_decision` is the persisted three-state decision every Gemini
dispatch consults; it defaults to UNKNOWN so existing stories never qualify.

Revision ID: e5b8d2f3a7c1
Revises: d4a7c1e2f6b9
Create Date: 2026-09-28 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5b8d2f3a7c1"
down_revision: Union[str, None] = "d4a7c1e2f6b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("sources", sa.Column("category", sa.Text(), nullable=True))
    op.add_column(
        "stories",
        sa.Column("privacy_decision", sa.Text(), nullable=False, server_default="UNKNOWN"),
    )
    op.create_check_constraint(
        "ck_stories_privacy_decision",
        "stories",
        "privacy_decision IN ('FREE_TIER_ALLOWED', 'RESTRICTED', 'UNKNOWN')",
    )
    # Quota deferrals are recorded like any other attempt (ADR-015 decision 6).
    op.drop_constraint("ck_ai_call_log_status", "ai_call_log", type_="check")
    op.create_check_constraint(
        "ck_ai_call_log_status",
        "ai_call_log",
        "status IN ('SUCCESS', 'RETRY_SUCCESS', 'HOLD', 'REVIEW_QUEUE', 'UNAVAILABLE', 'DEFERRED')",
    )


def downgrade() -> None:
    op.execute("DELETE FROM ai_call_log WHERE status = 'DEFERRED'")
    op.drop_constraint("ck_ai_call_log_status", "ai_call_log", type_="check")
    op.create_check_constraint(
        "ck_ai_call_log_status",
        "ai_call_log",
        "status IN ('SUCCESS', 'RETRY_SUCCESS', 'HOLD', 'REVIEW_QUEUE', 'UNAVAILABLE')",
    )
    op.drop_constraint("ck_stories_privacy_decision", "stories", type_="check")
    op.drop_column("stories", "privacy_decision")
    op.drop_column("sources", "category")
