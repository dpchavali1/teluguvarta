"""personalization ranking: source quality + why-matters cache (T16)

Adds `sources.quality_score` (the §8.2 `source_quality` ranking input, see
ADR-005) and `story_why_matters_cache` (§8.3's generate-once-per-segment
cache, unique on (story_id, segment)).

Revision ID: 4c6e1a8f2b7d
Revises: 73a24fe47a9f
Create Date: 2026-09-08 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "4c6e1a8f2b7d"
down_revision: Union[str, None] = "73a24fe47a9f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "sources",
        sa.Column("quality_score", sa.Float(), nullable=False, server_default="0.5"),
    )
    op.create_check_constraint(
        "ck_sources_quality_score_range", "sources", "quality_score >= 0 AND quality_score <= 1"
    )

    op.create_table(
        "story_why_matters_cache",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "story_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("stories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("segment", sa.Text(), nullable=False),
        sa.Column("why_matters", sa.Text(), nullable=False),
        sa.Column("model_version", sa.Text(), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(
            "segment IN ('general', 'international_student', 'graduate_opt', "
            "'professional', 'family_parent', 'other')",
            name="ck_story_why_matters_cache_segment",
        ),
        sa.UniqueConstraint("story_id", "segment", name="uq_story_why_matters_cache_story_segment"),
    )


def downgrade() -> None:
    op.drop_table("story_why_matters_cache")
    op.drop_constraint("ck_sources_quality_score_range", "sources", type_="check")
    op.drop_column("sources", "quality_score")
