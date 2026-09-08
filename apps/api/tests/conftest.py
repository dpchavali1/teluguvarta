"""Shared fixtures for schema/migration tests.

These tests exercise real Postgres behavior (enum defaults, the story status
transition trigger) that cannot be verified against a mock, so they need a
reachable Postgres server. They create and drop their own throw-away
databases alongside whatever DATABASE_URL points at, so they never touch
dev data. If no server is reachable at all, the whole module is skipped
rather than failed, since T02's local Postgres is an opt-in dev dependency.
"""

import os
from pathlib import Path

import psycopg
import pytest
from dotenv import load_dotenv
from sqlalchemy.engine import make_url

load_dotenv(Path(__file__).resolve().parents[3] / ".env")

BASE_DATABASE_URL = os.environ.get("DATABASE_URL")


def _server_reachable() -> bool:
    if not BASE_DATABASE_URL:
        return False
    url = make_url(BASE_DATABASE_URL)
    try:
        with psycopg.connect(
            dbname="postgres",
            user=url.username,
            password=url.password,
            host=url.host,
            port=url.port,
            connect_timeout=2,
        ):
            return True
    except psycopg.OperationalError:
        return False


requires_postgres = pytest.mark.skipif(
    not _server_reachable(),
    reason="No reachable Postgres server (set DATABASE_URL / run docker compose up -d)",
)


def _admin_connect():
    url = make_url(BASE_DATABASE_URL)
    conn = psycopg.connect(
        dbname="postgres",
        user=url.username,
        password=url.password,
        host=url.host,
        port=url.port,
        autocommit=True,
    )
    return conn, url


@pytest.fixture
def scratch_database(request):
    """Creates a fresh, uniquely-named database for one test; drops it after."""
    admin_conn, url = _admin_connect()
    db_name = f"teluguvarta_test_{request.node.name}"[:63].lower().replace("[", "_").replace("]", "_")
    with admin_conn.cursor() as cur:
        cur.execute(f'DROP DATABASE IF EXISTS "{db_name}" WITH (FORCE)')
        cur.execute(f'CREATE DATABASE "{db_name}" OWNER "{url.username}"')
    test_url = url.set(database=db_name).render_as_string(hide_password=False)
    try:
        yield test_url
    finally:
        with admin_conn.cursor() as cur:
            cur.execute(f'DROP DATABASE IF EXISTS "{db_name}" WITH (FORCE)')
        admin_conn.close()


@pytest.fixture
def migrated_database(scratch_database, monkeypatch):
    """A scratch database with all migrations applied, torn down after."""
    from alembic import command
    from alembic.config import Config

    monkeypatch.setenv("DATABASE_URL", scratch_database)
    cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    command.upgrade(cfg, "head")
    yield scratch_database
