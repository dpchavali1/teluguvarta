"""story restore: ARCHIVED/RETRACTED -> REVIEW_REQUIRED

ADR-055. An admin can undo an archive or retraction; the story goes back
through human review rather than straight to PUBLISHED.

Revision ID: e5b9d3f7a2c4
Revises: d4a8c2e6f1b3
Create Date: 2026-10-05 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5b9d3f7a2c4"
down_revision: Union[str, None] = "d4a8c2e6f1b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _trigger_sql(extra: str) -> str:
    return f"""
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
    (OLD.status = 'UPDATED' AND NEW.status = 'RETRACTED') OR
    (OLD.status = 'CORRECTION_PENDING' AND NEW.status = 'RETRACTED') OR{extra}
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


_RESTORE = """
    (OLD.status = 'ARCHIVED' AND NEW.status = 'REVIEW_REQUIRED') OR
    (OLD.status = 'RETRACTED' AND NEW.status = 'REVIEW_REQUIRED') OR"""


def upgrade() -> None:
    op.execute(_trigger_sql(_RESTORE))


def downgrade() -> None:
    op.execute(_trigger_sql(""))
