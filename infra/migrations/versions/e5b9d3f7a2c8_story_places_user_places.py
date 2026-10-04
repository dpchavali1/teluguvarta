"""story_places, user_places: place tags and place follows

ADR-043 / P03.

Revision ID: e5b9d3f7a2c8
Revises: d4a8c2e6b1f9
Create Date: 2026-10-04 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "e5b9d3f7a2c8"
down_revision: Union[str, None] = "d4a8c2e6b1f9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "story_places",
        sa.Column("story_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("stories.id", ondelete="CASCADE"),
                  primary_key=True),
        sa.Column("place_id", sa.Text(), primary_key=True),
        sa.Column("role", sa.Text(), primary_key=True, server_default="EVENT"),
        sa.CheckConstraint("role = 'EVENT'", name="ck_story_places_role"),
    )
    op.create_index("ix_story_places_place_role", "story_places", ["place_id", "role"])
    op.create_table(
        "user_places",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"),
                  primary_key=True),
        sa.Column("place_id", sa.Text(), primary_key=True),
        sa.Column("alerts", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_table("user_places")
    op.drop_index("ix_story_places_place_role", table_name="story_places")
    op.drop_table("story_places")
