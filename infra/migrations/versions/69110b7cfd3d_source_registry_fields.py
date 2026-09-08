"""source registry fields

Expands `sources` to the full §6.2 field list for docs/tickets/T06.md:
`base_url, source_type, country, language, rights_evidence_url,
rights_reviewed_at, reviewer, refresh_minutes, fail_count,
last_success_at, last_error_at`.

Drops the two placeholder columns T03 added before this field list existed:
`health` (free-text placeholder — superseded by the three real health
columns above) and `rights_evidence` (was a bare Text field — replaced by a
JSONB `rights_evidence` holding the fuller §5.1 record: terms/policy URL,
permitted fields, restrictions, territory, expiration, notes — plus the
first-class `rights_evidence_url`/`rights_reviewed_at`/`reviewer` columns
the API validates directly). No source rows exist yet in any real
environment (T06 is the first ticket to write to this table), so this is a
plain drop-and-add rather than a data-preserving migration.

Revision ID: 69110b7cfd3d
Revises: 8f1a2c9d4b3e
Create Date: 2026-09-08 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '69110b7cfd3d'
down_revision: Union[str, Sequence[str], None] = '8f1a2c9d4b3e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("sources", "health")
    op.drop_column("sources", "rights_evidence")

    op.add_column("sources", sa.Column("base_url", sa.Text(), nullable=True))
    op.add_column("sources", sa.Column("source_type", sa.Text(), nullable=True))
    op.add_column("sources", sa.Column("country", sa.Text(), nullable=True))
    op.add_column("sources", sa.Column("language", sa.Text(), nullable=True))
    op.add_column("sources", sa.Column("rights_evidence_url", sa.Text(), nullable=True))
    op.add_column("sources", sa.Column("rights_reviewed_at", sa.TIMESTAMP(timezone=True), nullable=True))
    op.add_column("sources", sa.Column("reviewer", sa.Text(), nullable=True))
    op.add_column("sources", sa.Column("refresh_minutes", sa.Integer(), nullable=True))
    op.add_column(
        "sources",
        sa.Column("fail_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("sources", sa.Column("last_success_at", sa.TIMESTAMP(timezone=True), nullable=True))
    op.add_column("sources", sa.Column("last_error_at", sa.TIMESTAMP(timezone=True), nullable=True))
    op.add_column(
        "sources",
        sa.Column("rights_evidence", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )


def downgrade() -> None:
    op.drop_column("sources", "rights_evidence")
    op.drop_column("sources", "last_error_at")
    op.drop_column("sources", "last_success_at")
    op.drop_column("sources", "fail_count")
    op.drop_column("sources", "refresh_minutes")
    op.drop_column("sources", "reviewer")
    op.drop_column("sources", "rights_reviewed_at")
    op.drop_column("sources", "rights_evidence_url")
    op.drop_column("sources", "language")
    op.drop_column("sources", "country")
    op.drop_column("sources", "source_type")
    op.drop_column("sources", "base_url")

    op.add_column("sources", sa.Column("rights_evidence", sa.Text(), nullable=True))
    op.add_column("sources", sa.Column("health", sa.Text(), nullable=True))
