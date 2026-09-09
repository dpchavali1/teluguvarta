"""pilot signups (T20 pre-build validation gate): opt-ins captured on the
landing page while running the 50-100 user validation pilot from
`docs/BUILD_ORDER.md`. Standalone from the `users`/`profiles` account model
(ADR-006's anonymous client-token identity) since a landing-page visitor has
neither — this table exists to measure the gate's own opt-in metric, not to
back the product.

Revision ID: 8c4f2a1e9d03
Revises: 5931ea7a3293
Create Date: 2026-09-09 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "8c4f2a1e9d03"
down_revision: Union[str, None] = "5931ea7a3293"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
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


def downgrade() -> None:
    op.drop_table("pilot_signups")
