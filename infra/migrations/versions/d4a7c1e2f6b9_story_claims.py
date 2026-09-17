"""story_claims table (P0-1)

Audit trail for every factual claim a `SUMMARY` generation call returns.
Before this, `AiGateway._remove_unsupported_claims` decided which claims to
keep/strip and then discarded that decision — nothing persisted which
claims a story was published on, or which ones were silently stripped for
having no source_ref. `status` records the P0-1 ref-membership outcome only
('KEPT' | 'REMOVED_NO_REF'); a claim citing a source_ref that names no real
`SourceItem` in the cluster never reaches this table at all — the gateway
HOLDs the whole story instead of persisting a claim built on a fabricated
reference.

Revision ID: d4a7c1e2f6b9
Revises: c3d4e5f6a7b8
Create Date: 2026-09-16 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "d4a7c1e2f6b9"
down_revision: Union[str, None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "story_claims",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "story_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("stories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("source_refs", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("status IN ('KEPT', 'REMOVED_NO_REF')", name="ck_story_claims_status"),
    )
    op.create_index("ix_story_claims_story_id", "story_claims", ["story_id"])


def downgrade() -> None:
    op.drop_index("ix_story_claims_story_id", table_name="story_claims")
    op.drop_table("story_claims")
