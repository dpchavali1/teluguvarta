"""smart_alerts: topic urgency, digests, keyword follows, saved stories, timezones

ADR-042 / P02.

Revision ID: d4a8c2e6b1f9
Revises: c3f7a1d9e4b2
Create Date: 2026-10-03 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "d4a8c2e6b1f9"
down_revision: Union[str, None] = "c3f7a1d9e4b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("profiles", sa.Column("home_tz", sa.Text(), nullable=True))
    op.add_column("profiles", sa.Column("residence_tz", sa.Text(), nullable=True))
    op.add_column("profiles", sa.Column("digest_morning_hour", sa.Integer(), nullable=True))
    op.add_column("profiles", sa.Column("digest_evening_hour", sa.Integer(), nullable=True))
    op.create_check_constraint(
        "ck_profiles_digest_hours", "profiles",
        "(digest_morning_hour IS NULL OR digest_morning_hour BETWEEN 0 AND 23)"
        " AND (digest_evening_hour IS NULL OR digest_evening_hour BETWEEN 0 AND 23)",
    )
    op.add_column("user_topics", sa.Column("urgency", sa.Text(), nullable=False, server_default="INSTANT"))
    op.create_check_constraint(
        "ck_user_topics_urgency", "user_topics", "urgency IN ('INSTANT', 'BREAKING_ONLY', 'DIGEST')"
    )
    op.create_table(
        "user_keywords",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("keyword", sa.Text(), primary_key=True),
        sa.CheckConstraint("char_length(keyword) BETWEEN 1 AND 40", name="ck_user_keywords_length"),
    )
    op.create_table(
        "user_saved_stories",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("story_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("stories.id", ondelete="CASCADE"), primary_key=True),
    )
    op.drop_constraint("ck_notifications_type", "notifications", type_="check")
    op.create_check_constraint(
        "ck_notifications_type", "notifications",
        "type IN ('DAILY_BRIEFING', 'TOPIC_ALERT', 'BREAKING_ALERT', 'DIGEST', 'STORY_UPDATE')",
    )


def downgrade() -> None:
    op.execute("DELETE FROM notifications WHERE type IN ('DIGEST', 'STORY_UPDATE')")
    op.drop_constraint("ck_notifications_type", "notifications", type_="check")
    op.create_check_constraint(
        "ck_notifications_type", "notifications", "type IN ('DAILY_BRIEFING', 'TOPIC_ALERT', 'BREAKING_ALERT')"
    )
    op.drop_table("user_saved_stories")
    op.drop_table("user_keywords")
    op.drop_constraint("ck_user_topics_urgency", "user_topics", type_="check")
    op.drop_column("user_topics", "urgency")
    op.drop_constraint("ck_profiles_digest_hours", "profiles", type_="check")
    for col in ("digest_evening_hour", "digest_morning_hour", "residence_tz", "home_tz"):
        op.drop_column("profiles", col)
