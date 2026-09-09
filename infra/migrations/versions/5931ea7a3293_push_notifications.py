"""push notifications (T17): anonymous-identity token, push tokens,
notification controls on profiles, breaking-alert editorial gate, and
notification history/dedupe bookkeeping.

`users.client_token` is the ADR-006 "opaque, unguessable user token" the
client mints on first launch and sends as `Authorization: Bearer` from then
on (see `app/auth.py::current_user` for the get-or-create resolution ADR-006
explicitly deferred to "a later ticket" — T17 is that ticket, since push
tokens/preferences are the first state that must be looked up outside a
request, by the `notification_dispatch` job).

Revision ID: 5931ea7a3293
Revises: 4c6e1a8f2b7d
Create Date: 2026-09-08 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "5931ea7a3293"
down_revision: Union[str, None] = "4c6e1a8f2b7d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("client_token", sa.Text(), nullable=True))
    op.create_unique_constraint("uq_users_client_token", "users", ["client_token"])

    op.add_column(
        "profiles",
        sa.Column("breaking_alerts_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.add_column(
        "profiles",
        sa.Column("daily_briefing_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.add_column("profiles", sa.Column("quiet_hours_start", sa.SmallInteger(), nullable=True))
    op.add_column("profiles", sa.Column("quiet_hours_end", sa.SmallInteger(), nullable=True))
    op.add_column(
        "profiles",
        sa.Column("max_alerts_per_day", sa.Integer(), nullable=False, server_default="5"),
    )
    op.create_check_constraint(
        "ck_profiles_quiet_hours_start_range", "profiles",
        "quiet_hours_start IS NULL OR (quiet_hours_start >= 0 AND quiet_hours_start <= 23)",
    )
    op.create_check_constraint(
        "ck_profiles_quiet_hours_end_range", "profiles",
        "quiet_hours_end IS NULL OR (quiet_hours_end >= 0 AND quiet_hours_end <= 23)",
    )
    op.create_check_constraint(
        "ck_profiles_max_alerts_per_day_positive", "profiles", "max_alerts_per_day > 0"
    )

    op.create_table(
        "push_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("platform", sa.Text(), nullable=False),
        sa.Column("token", sa.Text(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("last_seen_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("platform IN ('ios', 'android', 'web')", name="ck_push_tokens_platform"),
        sa.UniqueConstraint("token", name="uq_push_tokens_token"),
    )

    op.add_column("stories", sa.Column("breaking_alert_approved_at", sa.TIMESTAMP(timezone=True), nullable=True))

    op.add_column(
        "notifications",
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.add_column("notifications", sa.Column("suppressed_reason", sa.Text(), nullable=True))
    op.create_check_constraint(
        "ck_notifications_suppressed_reason", "notifications",
        "suppressed_reason IS NULL OR suppressed_reason IN ('QUIET_HOURS', 'DAILY_CAP')",
    )
    # Bounded-retry bookkeeping for a per-notification send failure (e.g. a
    # transient Expo/FCM/APNs error) — mirrors `jobs.attempts`/backoff
    # (ADR-003) at the notification-send granularity, since a dedupe key
    # already consumed at INSERT can't just be re-enqueued as a fresh job.
    op.add_column("notifications", sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("notifications", sa.Column("next_attempt_at", sa.TIMESTAMP(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("notifications", "next_attempt_at")
    op.drop_column("notifications", "attempts")
    op.drop_constraint("ck_notifications_suppressed_reason", "notifications", type_="check")
    op.drop_column("notifications", "suppressed_reason")
    op.drop_column("notifications", "created_at")

    op.drop_column("stories", "breaking_alert_approved_at")

    op.drop_table("push_tokens")

    op.drop_constraint("ck_profiles_max_alerts_per_day_positive", "profiles", type_="check")
    op.drop_constraint("ck_profiles_quiet_hours_end_range", "profiles", type_="check")
    op.drop_constraint("ck_profiles_quiet_hours_start_range", "profiles", type_="check")
    op.drop_column("profiles", "max_alerts_per_day")
    op.drop_column("profiles", "quiet_hours_end")
    op.drop_column("profiles", "quiet_hours_start")
    op.drop_column("profiles", "daily_briefing_enabled")
    op.drop_column("profiles", "breaking_alerts_enabled")

    op.drop_constraint("uq_users_client_token", "users", type_="unique")
    op.drop_column("users", "client_token")
