"""x accounts

Adds `x_accounts` for docs/tickets/X1.md: the fields the X official-account
adapter (X2+) needs beyond the generic `sources` row it's linked to
(`x_user_id, handle, priority, polling_cadence, since_id, budget_class`).

Deliberately does *not* duplicate `rights_status`/`active`/`last_success_at`/
`last_error_at` — those already live on the linked `sources` row and an X
account reuses that exact rights gate (ADR-002, NON_NEGOTIABLES #12) rather
than a parallel one. `source_id` is one-to-one (unique) since each X account
is exactly one `Source` row with `source_type='X_ACCOUNT'`.

Revision ID: a1b2c3d4e5f6
Revises: 8c4f2a1e9d03
Create Date: 2026-09-09 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "8c4f2a1e9d03"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "x_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "source_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sources.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("x_user_id", sa.Text(), nullable=False, unique=True),
        sa.Column("handle", sa.Text(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("polling_cadence", sa.Integer(), nullable=True),
        sa.Column("since_id", sa.Text(), nullable=True),
        sa.Column("budget_class", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("x_accounts")
