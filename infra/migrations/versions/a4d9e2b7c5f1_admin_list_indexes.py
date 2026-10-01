"""admin list indexes: paged review queue and audit history

Review 2026-09-30 R7. The review queue and audit history are now paged on
the server by keyset cursor; neither table had an index beyond its key.

Revision ID: a4d9e2b7c5f1
Revises: f3b8d1c6a2e7
Create Date: 2026-09-30 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a4d9e2b7c5f1"
down_revision: Union[str, None] = "f3b8d1c6a2e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX ix_review_tasks_pending ON review_tasks (created_at, id) WHERE status = 'PENDING'"
    )
    op.execute("CREATE INDEX ix_review_tasks_story_id ON review_tasks (story_id)")
    op.execute("CREATE INDEX ix_audit_events_created ON audit_events (created_at DESC, id DESC)")
    op.execute("CREATE INDEX ix_audit_events_entity ON audit_events (entity_type, entity_id, created_at DESC)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_audit_events_entity")
    op.execute("DROP INDEX IF EXISTS ix_audit_events_created")
    op.execute("DROP INDEX IF EXISTS ix_review_tasks_story_id")
    op.execute("DROP INDEX IF EXISTS ix_review_tasks_pending")
