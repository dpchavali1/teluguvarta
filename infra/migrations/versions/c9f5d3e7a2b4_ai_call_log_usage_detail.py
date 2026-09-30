"""ai_call_log: thinking/cached token detail and parse/block/transport statuses

Review 2026-09-29 finding #3. Gemini bills thinking tokens as output, and a
response that fails to parse or is safety-blocked still carries (billed)
usage. `tokens_out` now includes thinking tokens; `tokens_thinking` and
`tokens_cached` break them out. New statuses: PARSE_ERROR (malformed JSON),
BLOCKED (safety/recitation block), PROVIDER_ERROR (transport/HTTP failure —
kept apart from UNAVAILABLE, which the refusal alert reads as misconfiguration).

Revision ID: c9f5d3e7a2b4
Revises: b8e4c2d6f1a3
Create Date: 2026-09-29 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c9f5d3e7a2b4"
down_revision: Union[str, None] = "b8e4c2d6f1a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OLD = "'SUCCESS', 'RETRY_SUCCESS', 'HOLD', 'REVIEW_QUEUE', 'UNAVAILABLE', 'DEFERRED'"
_NEW = _OLD + ", 'PARSE_ERROR', 'BLOCKED', 'PROVIDER_ERROR'"


def upgrade() -> None:
    op.add_column("ai_call_log", sa.Column("tokens_thinking", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("ai_call_log", sa.Column("tokens_cached", sa.Integer(), nullable=False, server_default="0"))
    op.drop_constraint("ck_ai_call_log_status", "ai_call_log", type_="check")
    op.create_check_constraint("ck_ai_call_log_status", "ai_call_log", f"status IN ({_NEW})")


def downgrade() -> None:
    op.execute("DELETE FROM ai_call_log WHERE status IN ('PARSE_ERROR', 'BLOCKED', 'PROVIDER_ERROR')")
    op.drop_constraint("ck_ai_call_log_status", "ai_call_log", type_="check")
    op.create_check_constraint("ck_ai_call_log_status", "ai_call_log", f"status IN ({_OLD})")
    op.drop_column("ai_call_log", "tokens_cached")
    op.drop_column("ai_call_log", "tokens_thinking")
