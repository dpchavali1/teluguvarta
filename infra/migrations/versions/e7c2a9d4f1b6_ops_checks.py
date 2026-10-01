"""ops_checks: last success/failure of host-side operations

Review 2026-09-30 R3. Backups, the restore drill and the monitor run on the
VPS host, outside the api container, so admin could not see whether they
work. The host scripts (`infra/deploy/ops-record.sh`) upsert one row per check
here; `GET /v1/admin/observability` reports age and failure.

Revision ID: e7c2a9d4f1b6
Revises: d1a6e4f8b3c5
Create Date: 2026-09-30 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e7c2a9d4f1b6"
down_revision: Union[str, None] = "d1a6e4f8b3c5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ops_checks",
        sa.Column("check_name", sa.Text(), primary_key=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("success_detail", sa.Text(), nullable=True),
        sa.Column("last_failure_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_detail", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "check_name IN ('BACKUP', 'OFFSITE_COPY', 'RESTORE_DRILL', 'MONITOR', 'ALERT_TEST')",
            name="ck_ops_checks_name",
        ),
    )


def downgrade() -> None:
    op.drop_table("ops_checks")
