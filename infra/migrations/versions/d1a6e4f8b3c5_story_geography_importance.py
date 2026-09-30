"""stories: confidence, urgency and importance override; story_countries

ADR-027 (review 2026-09-29 #10). `importance` held classification confidence
and countries were derived from the publisher's `Source.country`.
`classification_confidence` now holds the model's confidence; `importance` is
a deterministic score (`app/content/importance.py`) that an editor can
override. `story_countries` holds event geography (role EVENT; AUDIENCE is
reserved and not written yet).

Existing rows: confidence is copied from `importance` for stories with a
model-written English variant, then `importance` is recomputed from sources
and topics. Urgency was never stored, so no existing story gets the urgency
term. No story gets event countries: they were never stored either.

Revision ID: d1a6e4f8b3c5
Revises: c9f5d3e7a2b4
Create Date: 2026-09-30 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "d1a6e4f8b3c5"
down_revision: Union[str, None] = "c9f5d3e7a2b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Mirrors app/content/importance.py at the time of this migration.
_PRIORITY_SLUGS = (
    "immigration", "cpt", "opt", "stem-opt", "internships", "university-policy",
    "campus-safety", "scholarships", "student-community", "international-student-jobs",
)


def upgrade() -> None:
    op.add_column("stories", sa.Column("classification_confidence", sa.Float(), nullable=True))
    op.add_column("stories", sa.Column("urgency", sa.Text(), nullable=True))
    op.add_column("stories", sa.Column("importance_override", sa.Text(), nullable=True))
    op.create_check_constraint("ck_stories_urgency", "stories", "urgency IN ('NORMAL', 'HIGH')")
    op.create_check_constraint(
        "ck_stories_importance_override", "stories", "importance_override IN ('LOW', 'NORMAL', 'HIGH')"
    )
    op.create_table(
        "story_countries",
        sa.Column("story_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("stories.id", ondelete="CASCADE"),
                  primary_key=True),
        sa.Column("country_code", sa.Text(), primary_key=True),
        sa.Column("role", sa.Text(), primary_key=True, server_default="EVENT"),
        sa.CheckConstraint("country_code ~ '^[A-Z]{2}$'", name="ck_story_countries_code"),
        sa.CheckConstraint("role IN ('EVENT', 'AUDIENCE')", name="ck_story_countries_role"),
    )
    op.create_index("ix_story_countries_country_role", "story_countries", ["country_code", "role"])

    op.execute(
        """
        UPDATE stories s SET classification_confidence = s.importance
        WHERE EXISTS (SELECT 1 FROM story_variants v
                      WHERE v.story_id = s.id AND v.language = 'en' AND v.model_version IS DISTINCT FROM 'editor')
        """
    )
    slugs = ", ".join(f"'{slug}'" for slug in _PRIORITY_SLUGS)
    op.execute(
        f"""
        UPDATE stories s SET importance = LEAST(1.0,
            0.4
            + 0.1 * LEAST(3, GREATEST(0, (
                SELECT COUNT(DISTINCT si.source_id) FROM story_sources ss
                JOIN source_items si ON si.id = ss.source_item_id WHERE ss.story_id = s.id) - 1))
            + CASE WHEN EXISTS (
                SELECT 1 FROM story_topics st JOIN topics t ON t.id = st.topic_id
                WHERE st.story_id = s.id AND t.slug IN ({slugs})) THEN 0.1 ELSE 0 END)
        """
    )


def downgrade() -> None:
    op.execute(
        "UPDATE stories SET importance = COALESCE(classification_confidence, 0)"
    )
    op.drop_index("ix_story_countries_country_role", table_name="story_countries")
    op.drop_table("story_countries")
    op.drop_constraint("ck_stories_importance_override", "stories", type_="check")
    op.drop_constraint("ck_stories_urgency", "stories", type_="check")
    op.drop_column("stories", "importance_override")
    op.drop_column("stories", "urgency")
    op.drop_column("stories", "classification_confidence")
