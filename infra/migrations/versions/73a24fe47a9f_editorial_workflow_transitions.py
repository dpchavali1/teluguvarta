"""editorial workflow: story_status ARCHIVED + reject transitions (T12)

T12 adds the `reject` editorial action, which needs a genuine terminal
"archived" `stories.status` outcome (§6.4's ARCHIVED concept already exists
at the `source_items.ingest_status` level from T11, but `stories.status` had
no equivalent) — REVIEW_REQUIRED -> DRAFT (send back for reprocessing) and
REVIEW_REQUIRED -> ARCHIVED (editor decides it should never publish) are the
two outcomes the ticket text calls for ("reject -> back to draft or
archived"). Every other T12 transition (approve's REVIEW_REQUIRED ->
APPROVED -> SCHEDULED -> PUBLISHED, retract's PUBLISHED -> RETRACTED,
correct's PUBLISHED -> UPDATED / UPDATED -> CORRECTION_PENDING -> UPDATED)
was already legal in T03's trigger, so this migration only adds what was
actually missing.

Revision ID: 73a24fe47a9f
Revises: 9d3f6b1a2c47
Create Date: 2026-09-08 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "73a24fe47a9f"
down_revision: Union[str, None] = "9d3f6b1a2c47"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NEW_TRIGGER_SQL = """
CREATE OR REPLACE FUNCTION enforce_story_status_transition() RETURNS trigger AS $$
DECLARE
  allowed boolean;
BEGIN
  IF NEW.status = OLD.status THEN
    RETURN NEW;
  END IF;
  allowed := (
    (OLD.status = 'DRAFT' AND NEW.status = 'AI_READY') OR
    (OLD.status = 'AI_READY' AND NEW.status = 'REVIEW_REQUIRED') OR
    (OLD.status = 'REVIEW_REQUIRED' AND NEW.status = 'APPROVED') OR
    (OLD.status = 'REVIEW_REQUIRED' AND NEW.status = 'DRAFT') OR
    (OLD.status = 'REVIEW_REQUIRED' AND NEW.status = 'ARCHIVED') OR
    (OLD.status = 'APPROVED' AND NEW.status = 'SCHEDULED') OR
    (OLD.status = 'SCHEDULED' AND NEW.status = 'PUBLISHED') OR
    (OLD.status = 'PUBLISHED' AND NEW.status = 'UPDATED') OR
    (OLD.status = 'PUBLISHED' AND NEW.status = 'RETRACTED') OR
    (OLD.status = 'UPDATED' AND NEW.status = 'CORRECTION_PENDING') OR
    (OLD.status = 'CORRECTION_PENDING' AND NEW.status = 'UPDATED')
  );
  IF NOT allowed THEN
    RAISE EXCEPTION 'illegal story status transition: % -> %', OLD.status, NEW.status
      USING ERRCODE = '23514';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""

OLD_TRIGGER_SQL = """
CREATE OR REPLACE FUNCTION enforce_story_status_transition() RETURNS trigger AS $$
DECLARE
  allowed boolean;
BEGIN
  IF NEW.status = OLD.status THEN
    RETURN NEW;
  END IF;
  allowed := (
    (OLD.status = 'DRAFT' AND NEW.status = 'AI_READY') OR
    (OLD.status = 'AI_READY' AND NEW.status = 'REVIEW_REQUIRED') OR
    (OLD.status = 'REVIEW_REQUIRED' AND NEW.status = 'APPROVED') OR
    (OLD.status = 'APPROVED' AND NEW.status = 'SCHEDULED') OR
    (OLD.status = 'SCHEDULED' AND NEW.status = 'PUBLISHED') OR
    (OLD.status = 'PUBLISHED' AND NEW.status = 'UPDATED') OR
    (OLD.status = 'PUBLISHED' AND NEW.status = 'RETRACTED') OR
    (OLD.status = 'UPDATED' AND NEW.status = 'CORRECTION_PENDING') OR
    (OLD.status = 'CORRECTION_PENDING' AND NEW.status = 'UPDATED')
  );
  IF NOT allowed THEN
    RAISE EXCEPTION 'illegal story status transition: % -> %', OLD.status, NEW.status
      USING ERRCODE = '23514';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""


def upgrade() -> None:
    # Safe to run inside Alembic's migration transaction: the new label is
    # only referenced as plpgsql source text below, never cast/compared to
    # in this same transaction (Postgres forbids *using* a value added by
    # ALTER TYPE ... ADD VALUE before that transaction commits, not merely
    # mentioning it in a function body).
    op.execute("ALTER TYPE story_status ADD VALUE IF NOT EXISTS 'ARCHIVED'")
    op.execute(NEW_TRIGGER_SQL)


def downgrade() -> None:
    # Postgres has no DROP VALUE for enums; rebuild the type without
    # ARCHIVED. Fails loudly (invalid input value cast) if any row still
    # uses it — correct, since a downgrade must not silently discard
    # archived stories. The guard trigger depends on the column's type, so
    # it must be dropped before the ALTER COLUMN TYPE and recreated after.
    op.execute("DROP TRIGGER story_status_transition_guard ON stories")
    op.execute(OLD_TRIGGER_SQL)
    op.execute("ALTER TABLE stories ALTER COLUMN status DROP DEFAULT")
    op.execute("ALTER TYPE story_status RENAME TO story_status_old")
    op.execute(
        "CREATE TYPE story_status AS ENUM ("
        "'DRAFT','AI_READY','REVIEW_REQUIRED','APPROVED','SCHEDULED',"
        "'PUBLISHED','UPDATED','RETRACTED','CORRECTION_PENDING')"
    )
    op.execute(
        "ALTER TABLE stories ALTER COLUMN status TYPE story_status "
        "USING status::text::story_status"
    )
    op.execute("ALTER TABLE stories ALTER COLUMN status SET DEFAULT 'DRAFT'::story_status")
    op.execute("DROP TYPE story_status_old")
    op.execute(
        """
        CREATE TRIGGER story_status_transition_guard
        BEFORE UPDATE OF status ON stories
        FOR EACH ROW
        EXECUTE FUNCTION enforce_story_status_transition();
        """
    )
