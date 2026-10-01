"""admin_sessions: server-side admin sessions behind an HttpOnly cookie

ADR-028 option A (review 2026-09-30 R11). Replaces the admin JWT the browser
kept in localStorage. Only the SHA-256 of the cookie value is stored.

Revision ID: b8e3f1a6d2c9
Revises: a4d9e2b7c5f1
Create Date: 2026-09-30 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "b8e3f1a6d2c9"
down_revision: Union[str, None] = "a4d9e2b7c5f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "admin_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("token_hash", sa.Text(), nullable=False, unique=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scope", sa.Text(), nullable=False),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("scope IN ('full', 'mfa_enrollment')", name="ck_admin_sessions_scope"),
    )
    # Sign-out-everywhere and the session list read a user's live sessions.
    op.create_index(
        "ix_admin_sessions_user_live", "admin_sessions", ["user_id"], postgresql_where=sa.text("revoked_at IS NULL")
    )


def downgrade() -> None:
    op.drop_index("ix_admin_sessions_user_live", table_name="admin_sessions")
    op.drop_table("admin_sessions")
