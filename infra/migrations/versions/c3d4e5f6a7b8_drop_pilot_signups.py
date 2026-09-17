"""drop pilot_signups: product decision to remove the pre-build validation
pilot entirely (no landing-page signup capture, no T20 gate) — see
`docs/BUILD_ORDER.md` and PROGRESS.md's 2026-09-16 pilot-removal entry.

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-09-16 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table("pilot_signups")


def downgrade() -> None:
    op.create_table(
        "pilot_signups",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("segment", sa.Text(), nullable=True),
        sa.Column("example_feed", sa.Text(), nullable=True),
        sa.Column("recommend_willingness", sa.SmallInteger(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(
            "segment IS NULL OR segment IN "
            "('general', 'international_student', 'graduate_opt', 'professional', 'family_parent', 'other')",
            name="ck_pilot_signups_segment",
        ),
        sa.CheckConstraint(
            "recommend_willingness IS NULL OR (recommend_willingness >= 0 AND recommend_willingness <= 10)",
            name="ck_pilot_signups_recommend_willingness_range",
        ),
        sa.UniqueConstraint("email", name="uq_pilot_signups_email"),
    )
