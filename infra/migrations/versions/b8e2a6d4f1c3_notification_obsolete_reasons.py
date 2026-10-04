"""retract after correction; suppression reasons for obsolete alerts

Review 2026-10-04: a corrected story (UPDATED / CORRECTION_PENDING) can now be
retracted. A queued alert is re-checked at delivery and suppressed when
its story is no longer public (STORY_UNAVAILABLE) or the reader's current
settings no longer qualify it (NO_LONGER_ELIGIBLE).

Revision ID: b8e2a6d4f1c3
Revises: a7d1f5b9c3e2
Create Date: 2026-10-04 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b8e2a6d4f1c3"
down_revision: Union[str, None] = "a7d1f5b9c3e2"
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
    (OLD.status = 'PUBLISHED' AND NEW.status = 'RETRACTED') OR{extra}
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


_RETRACT_AFTER_CORRECTION = """
    (OLD.status = 'UPDATED' AND NEW.status = 'RETRACTED') OR
    (OLD.status = 'CORRECTION_PENDING' AND NEW.status = 'RETRACTED') OR"""


def upgrade() -> None:
    op.execute(_trigger_sql(_RETRACT_AFTER_CORRECTION))
    op.drop_constraint("ck_notifications_suppressed_reason", "notifications", type_="check")
    op.create_check_constraint(
        "ck_notifications_suppressed_reason", "notifications",
        "suppressed_reason IS NULL OR suppressed_reason IN "
        "('QUIET_HOURS', 'DAILY_CAP', 'STORY_UNAVAILABLE', 'NO_LONGER_ELIGIBLE')",
    )


def downgrade() -> None:
    op.execute(_trigger_sql(""))
    op.execute(
        "UPDATE notifications SET suppressed_reason = 'DAILY_CAP' "
        "WHERE suppressed_reason IN ('STORY_UNAVAILABLE', 'NO_LONGER_ELIGIBLE')"
    )
    op.drop_constraint("ck_notifications_suppressed_reason", "notifications", type_="check")
    op.create_check_constraint(
        "ck_notifications_suppressed_reason", "notifications",
        "suppressed_reason IS NULL OR suppressed_reason IN ('QUIET_HOURS', 'DAILY_CAP')",
    )
