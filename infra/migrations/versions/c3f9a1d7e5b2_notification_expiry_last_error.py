"""notifications: EXPIRED suppression reason and last_error

ADR-050. Deferred rows (quiet hours, daily cap, push disabled) stay PENDING
and are re-swept via the existing `next_attempt_at`; a row older than its
type's max age becomes SUPPRESSED with reason EXPIRED. `last_error` records
why a PENDING row is waiting (e.g. PUSH_DISABLED) without burning attempts.

Revision ID: c3f9a1d7e5b2
Revises: a1c4e7b9d2f6
Create Date: 2026-10-04 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3f9a1d7e5b2"
down_revision: Union[str, None] = "a1c4e7b9d2f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("notifications", sa.Column("last_error", sa.Text(), nullable=True))
    op.drop_constraint("ck_notifications_suppressed_reason", "notifications", type_="check")
    op.create_check_constraint(
        "ck_notifications_suppressed_reason", "notifications",
        "suppressed_reason IS NULL OR suppressed_reason IN "
        "('QUIET_HOURS', 'DAILY_CAP', 'STORY_UNAVAILABLE', 'NO_LONGER_ELIGIBLE', 'EXPIRED')",
    )


def downgrade() -> None:
    op.execute("UPDATE notifications SET suppressed_reason = 'DAILY_CAP' WHERE suppressed_reason = 'EXPIRED'")
    op.drop_constraint("ck_notifications_suppressed_reason", "notifications", type_="check")
    op.create_check_constraint(
        "ck_notifications_suppressed_reason", "notifications",
        "suppressed_reason IS NULL OR suppressed_reason IN "
        "('QUIET_HOURS', 'DAILY_CAP', 'STORY_UNAVAILABLE', 'NO_LONGER_ELIGIBLE')",
    )
    op.drop_column("notifications", "last_error")
