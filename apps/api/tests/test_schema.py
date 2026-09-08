"""T03 acceptance tests: migrations apply/roll back cleanly, and the two
DB-level guarantees (rights_status default, story status transition guard)
actually hold at the database level, not just in application code.
"""

from pathlib import Path

import psycopg
import pytest
from sqlalchemy.engine import make_url

from tests.conftest import requires_postgres

EXPECTED_TABLES = {
    "users", "profiles", "topics", "user_topics", "sources", "source_items",
    "stories", "story_variants", "story_sources", "story_entities", "entities",
    "entity_aliases", "story_topics", "review_tasks", "corrections",
    "notifications", "jobs", "audit_events",
}


def _connect(database_url: str):
    url = make_url(database_url)
    return psycopg.connect(
        dbname=url.database,
        user=url.username,
        password=url.password,
        host=url.host,
        port=url.port,
    )


@requires_postgres
def test_migration_creates_every_core_entity_table(migrated_database):
    with _connect(migrated_database) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
        )
        tables = {row[0] for row in cur.fetchall()}
    assert EXPECTED_TABLES <= tables


@requires_postgres
def test_migration_apply_and_rollback_round_trip(scratch_database, monkeypatch):
    from alembic import command
    from alembic.config import Config

    monkeypatch.setenv("DATABASE_URL", scratch_database)
    cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))

    command.upgrade(cfg, "head")
    with _connect(scratch_database) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
        )
        tables = {row[0] for row in cur.fetchall()}
    assert EXPECTED_TABLES <= tables

    command.downgrade(cfg, "base")
    with _connect(scratch_database) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
        )
        tables = {row[0] for row in cur.fetchall()}
    assert EXPECTED_TABLES.isdisjoint(tables)


@requires_postgres
def test_source_rights_status_defaults_to_disabled(migrated_database):
    with _connect(migrated_database) as conn, conn.cursor() as cur:
        cur.execute("INSERT INTO sources (name) VALUES ('Test Source') RETURNING rights_status")
        (rights_status,) = cur.fetchone()
        conn.rollback()
    assert rights_status == "DISABLED"


@requires_postgres
def test_source_rights_status_rejects_unknown_values(migrated_database):
    with _connect(migrated_database) as conn, conn.cursor() as cur:
        with pytest.raises(psycopg.errors.InvalidTextRepresentation):
            cur.execute(
                "INSERT INTO sources (name, rights_status) VALUES ('Bad', 'NOT_A_STATUS')"
            )
        conn.rollback()


@requires_postgres
def test_story_status_rejects_illegal_transition(migrated_database):
    with _connect(migrated_database) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO stories (canonical_slug) VALUES ('illegal-transition-story') RETURNING status"
        )
        (status,) = cur.fetchone()
        assert status == "DRAFT"

        with pytest.raises(psycopg.errors.CheckViolation):
            cur.execute(
                "UPDATE stories SET status = 'PUBLISHED' WHERE canonical_slug = 'illegal-transition-story'"
            )
        conn.rollback()


@requires_postgres
def test_story_status_allows_legal_transition(migrated_database):
    with _connect(migrated_database) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO stories (canonical_slug) VALUES ('legal-transition-story')"
        )
        cur.execute(
            "UPDATE stories SET status = 'AI_READY' WHERE canonical_slug = 'legal-transition-story' RETURNING status"
        )
        (status,) = cur.fetchone()
        conn.rollback()
    assert status == "AI_READY"
