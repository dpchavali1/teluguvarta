"""source_items ingest_status: add ENRICHED, REVIEW, SCHEDULED, ARCHIVED (T11)

Continues the incremental pattern from `2f6a0e7c9d41` (CLUSTERED). T11's
story-generation job advances a story's `SourceItem`s from `CLUSTERED` to
`ENRICHED` once AI generation succeeds, then immediately on to `REVIEW`
(§15 priority tiers P0/P1, or low-confidence classification) or `SCHEDULED`
(P2, eligible for auto-publish once T12/T06's gate is applied) — mirroring
how `2f6a0e7c9d41` skipped persisting the intermediate `DEDUPED` state.

`ARCHIVED` has no equivalent in §6.4's literal state-machine text
(`DISCOVERED -> RIGHTS_BLOCKED | NORMALIZED -> DEDUPED -> CLUSTERED ->
ENRICHED -> REVIEW | SCHEDULED -> PUBLISHED -> UPDATED | RETRACTED`), but
T11's ticket text explicitly requires a terminal outcome for "P3 (low-value/
duplicate) -> archived, not published" and the AI-classify step is exactly
where that's decided (before the more expensive generation call ever runs,
per §19 cost control) — added here as the smallest state-machine extension
that satisfies the ticket's own explicit scope rather than leaving P3
stories with no distinguishable terminal state.

Revision ID: 9d3f6b1a2c47
Revises: 7a4c9e2b5d10
Create Date: 2026-09-08 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "9d3f6b1a2c47"
down_revision: Union[str, None] = "7a4c9e2b5d10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

OLD_STATUSES = ("DISCOVERED", "RIGHTS_BLOCKED", "NORMALIZED", "CLUSTERED")
NEW_STATUSES = (*OLD_STATUSES, "ENRICHED", "REVIEW", "SCHEDULED", "ARCHIVED")


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
