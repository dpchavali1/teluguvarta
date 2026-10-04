"""exam_deadlines, user_exam_follows

ADR-041 / P07 (exam and deadline reminders).

Revision ID: a7d1f5b9c3e2
Revises: f6c0e4a8b3d9
Create Date: 2026-10-04 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "a7d1f5b9c3e2"
down_revision: Union[str, None] = "f6c0e4a8b3d9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "exam_deadlines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("exam", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("deadline", sa.Date(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="DRAFT"),
        sa.Column("entered_by", sa.Text(), nullable=False),
        sa.Column("approved_by", sa.Text(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('DRAFT', 'APPROVED', 'WITHDRAWN')", name="ck_exam_deadlines_status"),
        sa.CheckConstraint(
            "kind IN ('REGISTRATION_DEADLINE', 'EXAM_DATE', 'RESULT_DATE', 'APPLICATION_DEADLINE')",
            name="ck_exam_deadlines_kind",
        ),
    )
    op.create_index("ix_exam_deadlines_exam_deadline", "exam_deadlines", ["exam", "deadline"])
    op.create_table(
        "user_exam_follows",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"),
                  primary_key=True),
        sa.Column("exam", sa.Text(), primary_key=True),
        sa.Column("alerts", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.execute("DELETE FROM notifications WHERE notification_key LIKE 'exam_deadline:%'")
    op.drop_table("user_exam_follows")
    op.drop_index("ix_exam_deadlines_exam_deadline", table_name="exam_deadlines")
    op.drop_table("exam_deadlines")
