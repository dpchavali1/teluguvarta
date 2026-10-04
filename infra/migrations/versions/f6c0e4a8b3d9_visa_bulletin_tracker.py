"""visa_bulletins, visa_bulletin_entries, user_visa_follows, TRACKER_UPDATE

ADR-041 / P07.

Revision ID: f6c0e4a8b3d9
Revises: e5b9d3f7a2c8
Create Date: 2026-10-04 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "f6c0e4a8b3d9"
down_revision: Union[str, None] = "e5b9d3f7a2c8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "visa_bulletins",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("month", sa.Date(), nullable=False, unique=True),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="DRAFT"),
        sa.Column("entered_by", sa.Text(), nullable=False),
        sa.Column("approved_by", sa.Text(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('DRAFT', 'APPROVED')", name="ck_visa_bulletins_status"),
        sa.CheckConstraint("extract(day FROM month) = 1", name="ck_visa_bulletins_month_first"),
    )
    op.create_table(
        "visa_bulletin_entries",
        sa.Column("bulletin_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("visa_bulletins.id", ondelete="CASCADE"),
                  primary_key=True),
        sa.Column("chart", sa.Text(), primary_key=True),
        sa.Column("category", sa.Text(), primary_key=True),
        sa.Column("country", sa.Text(), primary_key=True),
        sa.Column("cutoff", sa.Text(), nullable=False),
        sa.CheckConstraint("chart IN ('FINAL_ACTION', 'DATES_FOR_FILING')", name="ck_visa_entries_chart"),
    )
    op.create_table(
        "user_visa_follows",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"),
                  primary_key=True),
        sa.Column("category", sa.Text(), primary_key=True),
        sa.Column("country", sa.Text(), primary_key=True),
        sa.Column("alerts", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.drop_constraint("ck_notifications_type", "notifications", type_="check")
    op.create_check_constraint(
        "ck_notifications_type", "notifications",
        "type IN ('DAILY_BRIEFING', 'TOPIC_ALERT', 'BREAKING_ALERT', 'DIGEST', 'STORY_UPDATE', 'TRACKER_UPDATE')",
    )


def downgrade() -> None:
    op.execute("DELETE FROM notifications WHERE type = 'TRACKER_UPDATE'")
    op.drop_constraint("ck_notifications_type", "notifications", type_="check")
    op.create_check_constraint(
        "ck_notifications_type", "notifications",
        "type IN ('DAILY_BRIEFING', 'TOPIC_ALERT', 'BREAKING_ALERT', 'DIGEST', 'STORY_UPDATE')",
    )
    op.drop_table("user_visa_follows")
    op.drop_table("visa_bulletin_entries")
    op.drop_table("visa_bulletins")
