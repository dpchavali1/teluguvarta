"""ADR-019: stories.format (FULL | BRIEF)

A link-first brief published by the auto-publish lane is marked BRIEF so
readers see a "Brief" label. Existing stories are FULL.

Revision ID: f6c9e3a4b8d2
Revises: e5b8d2f3a7c1
Create Date: 2026-09-29 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f6c9e3a4b8d2"
down_revision: Union[str, None] = "e5b8d2f3a7c1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("stories", sa.Column("format", sa.Text(), nullable=False, server_default="FULL"))
    op.create_check_constraint("ck_stories_format", "stories", "format IN ('FULL', 'BRIEF')")


def downgrade() -> None:
    op.drop_constraint("ck_stories_format", "stories", type_="check")
    op.drop_column("stories", "format")
