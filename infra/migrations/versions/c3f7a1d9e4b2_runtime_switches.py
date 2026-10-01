"""runtime_switches: dashboard pause switches for AI and auto-publish

ADR-031. A missing row means the switch is on.

Revision ID: c3f7a1d9e4b2
Revises: b8e3f1a6d2c9
Create Date: 2026-10-01 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3f7a1d9e4b2"
down_revision: Union[str, None] = "b8e3f1a6d2c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "runtime_switches",
        sa.Column("key", sa.Text(), primary_key=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("updated_by", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("note", sa.Text(), nullable=True),
        sa.CheckConstraint("key IN ('ai', 'auto_publish')", name="ck_runtime_switches_key"),
    )


def downgrade() -> None:
    op.drop_table("runtime_switches")
