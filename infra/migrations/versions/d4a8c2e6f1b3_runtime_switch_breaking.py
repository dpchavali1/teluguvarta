"""runtime_switches: allow the 'breaking' key

ADR-054. The dashboard kill switch for source-text breaking/death briefs.

Revision ID: d4a8c2e6f1b3
Revises: c3f9a1d7e5b2
Create Date: 2026-10-04 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4a8c2e6f1b3"
down_revision: Union[str, None] = "c3f9a1d7e5b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("ck_runtime_switches_key", "runtime_switches", type_="check")
    op.create_check_constraint(
        "ck_runtime_switches_key", "runtime_switches", "key IN ('ai', 'auto_publish', 'breaking')"
    )


def downgrade() -> None:
    op.execute("DELETE FROM runtime_switches WHERE key = 'breaking'")
    op.drop_constraint("ck_runtime_switches_key", "runtime_switches", type_="check")
    op.create_check_constraint("ck_runtime_switches_key", "runtime_switches", "key IN ('ai', 'auto_publish')")
