"""users.mfa_last_step: single-use TOTP codes

ADR-046 section 5.

Revision ID: a1c4e7b9d2f6
Revises: b8e2a6d4f1c3
Create Date: 2026-10-04 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1c4e7b9d2f6"
down_revision: Union[str, None] = "b8e2a6d4f1c3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("mfa_last_step", sa.BigInteger(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "mfa_last_step")
