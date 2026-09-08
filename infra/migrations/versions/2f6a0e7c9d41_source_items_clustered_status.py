"""source_items ingest_status: add CLUSTERED (T09)

T09's dedup/clustering job does fingerprinting and clustering in one
deterministic pass, so DEDUPED is never persisted as its own row state
(fingerprint-equal items are simply clustered directly) — only CLUSTERED is
added here. Later tickets add the rest of the §6.4 state machine (ENRICHED,
REVIEW, ...) as their own values.

Revision ID: 2f6a0e7c9d41
Revises: 1b4ff735cc70
Create Date: 2026-09-08 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "2f6a0e7c9d41"
down_revision: Union[str, None] = "1b4ff735cc70"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

OLD_STATUSES = ("DISCOVERED", "RIGHTS_BLOCKED", "NORMALIZED")
NEW_STATUSES = (*OLD_STATUSES, "CLUSTERED")


def upgrade() -> None:
    op.drop_constraint("ck_source_items_ingest_status", "source_items", type_="check")
    op.create_check_constraint(
        "ck_source_items_ingest_status",
        "source_items",
        "ingest_status IN (" + ", ".join(f"'{status}'" for status in NEW_STATUSES) + ")",
    )


def downgrade() -> None:
    op.drop_constraint("ck_source_items_ingest_status", "source_items", type_="check")
    op.create_check_constraint(
        "ck_source_items_ingest_status",
        "source_items",
        "ingest_status IN (" + ", ".join(f"'{status}'" for status in OLD_STATUSES) + ")",
    )
