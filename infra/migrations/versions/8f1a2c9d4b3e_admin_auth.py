"""admin auth

Adds staff (editor/admin) authentication to the existing `users` table
instead of a parallel table — the schema already treats `users.id` as the
identity for staff-ish references (`review_tasks.reviewer_id`,
`corrections.created_by`), so a `role` column on the same table is the
natural fit rather than a second identity table (docs/tickets/T05.md).
A `NULL` role means an ordinary end user; `EDITOR`/`ADMIN` are staff.

`mfa_secret` is added now but unused by any app code yet — the ticket asks
for the session/table shape to be "MFA-ready" without requiring MFA itself
this ticket; a later ticket can start writing to it without a migration.

`admin_login_attempts` backs rate limiting on the admin login endpoint,
consistent with NON_NEGOTIABLES' "no Redis" — the sliding window is a plain
indexed table query, not a new piece of infrastructure.

Revision ID: 8f1a2c9d4b3e
Revises: 0c23c235e618
Create Date: 2026-09-08 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '8f1a2c9d4b3e'
down_revision: Union[str, Sequence[str], None] = '0c23c235e618'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


UUID_PK = lambda: sa.Column(  # noqa: E731
    "id",
    postgresql.UUID(as_uuid=True),
    primary_key=True,
    server_default=sa.text("gen_random_uuid()"),
)


def upgrade() -> None:
    op.add_column("users", sa.Column("role", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("password_hash", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("mfa_secret", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("last_login_at", sa.TIMESTAMP(timezone=True), nullable=True))
    op.create_check_constraint("ck_users_role", "users", "role IN ('EDITOR', 'ADMIN')")

    op.create_table(
        "admin_login_attempts",
        UUID_PK(),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("ip", sa.Text(), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index(
        "ix_admin_login_attempts_email_created_at",
        "admin_login_attempts",
        ["email", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_admin_login_attempts_email_created_at", table_name="admin_login_attempts")
    op.drop_table("admin_login_attempts")
    op.drop_constraint("ck_users_role", "users", type_="check")
    op.drop_column("users", "last_login_at")
    op.drop_column("users", "mfa_secret")
    op.drop_column("users", "password_hash")
    op.drop_column("users", "role")
