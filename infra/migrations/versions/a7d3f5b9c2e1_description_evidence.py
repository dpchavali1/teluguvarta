"""ADR-020: sources.description_evidence + source_items.description

An ADMIN may flag a public-domain LINK_ONLY source so its feed description is
stored (HTML-stripped, capped) as internal evidence. Existing sources stay off.

Revision ID: a7d3f5b9c2e1
Revises: f6c9e3a4b8d2
Create Date: 2026-09-29 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a7d3f5b9c2e1"
down_revision: Union[str, None] = "f6c9e3a4b8d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "sources", sa.Column("description_evidence", sa.Boolean(), nullable=False, server_default="false")
    )
    op.add_column("source_items", sa.Column("description", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("source_items", "description")
    op.drop_column("sources", "description_evidence")
