"""source_items ingest_status (T08)

Adds the §6.4 ingestion-state column the ingestion worker needs to record
whether a fetched item cleared the rights gate. T08 only ever writes
DISCOVERED (never persisted — set at insert time in the same statement, see
app/adapters/base.py), RIGHTS_BLOCKED, or NORMALIZED; later tickets add the
rest of the §6.4 state machine (DEDUPED, CLUSTERED, ...) as their own values.

Revision ID: 1b4ff735cc70
Revises: 69110b7cfd3d
Create Date: 2026-09-08 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "1b4ff735cc70"
down_revision: Union[str, None] = "69110b7cfd3d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

INGEST_STATUSES = ("DISCOVERED", "RIGHTS_BLOCKED", "NORMALIZED")


def upgrade() -> None:
    op.add_column(
        "source_items",
        sa.Column("ingest_status", sa.Text(), nullable=False, server_default="DISCOVERED"),
    )
    op.create_check_constraint(
        "ck_source_items_ingest_status",
        "source_items",
        "ingest_status IN (" + ", ".join(f"'{status}'" for status in INGEST_STATUSES) + ")",
    )


def downgrade() -> None:
    op.drop_constraint("ck_source_items_ingest_status", "source_items", type_="check")
    op.drop_column("source_items", "ingest_status")
