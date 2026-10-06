"""Shared fixtures for schema/migration tests.

These tests exercise real Postgres behavior (enum defaults, the story status
transition trigger) that cannot be verified against a mock, so they need a
reachable Postgres server. They create and drop their own throw-away
databases alongside whatever DATABASE_URL points at, so they never touch
dev data. If no server is reachable at all, the whole module is skipped
rather than failed, since T02's local Postgres is an opt-in dev dependency.
"""

import os
import time
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from psycopg import sql
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

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


_POSTGRES_REACHABLE = _server_reachable()

requires_postgres = pytest.mark.skipif(
    not _POSTGRES_REACHABLE,
    reason="No reachable Postgres server (set DATABASE_URL / run docker compose up -d)",
)


def pytest_configure(config):
    # A green run with most database tests skipped is not evidence (review
    # 2026-10-04): CI must fail, and a local run must say so loudly.
    if _POSTGRES_REACHABLE:
        return
    if os.environ.get("CI") or os.environ.get("REQUIRE_POSTGRES"):
        raise pytest.UsageError("No reachable Postgres server: database tests would be skipped, not run")


def pytest_terminal_summary(terminalreporter, config):
    if not _POSTGRES_REACHABLE:
        terminalreporter.write_line(
            "WARNING: no reachable Postgres - database tests were skipped or errored; "
            "this run does not verify database behaviour.",
            red=True,
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


def _drop_scratch_database(admin_conn, db_name):
    # Local teardown can briefly refuse FORCE after all application engines
    # have closed. Give those backends time to finish; never change privileges
    # or swallow a persistent refusal. The caller owns this unique database.
    for attempt in range(10):
        try:
            with admin_conn.cursor() as cur:
                cur.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(db_name)))
            return
        except psycopg.errors.InsufficientPrivilege:
            if attempt == 9:
                raise
            time.sleep(0.1)


@pytest.fixture
def scratch_database():
    """Create a unique owned database; never pre-drop another run's database."""
    admin_conn, url = _admin_connect()
    db_name = f"teluguvarta_test_{uuid4().hex}"
    created = False
    try:
        with admin_conn.cursor() as cur:
            cur.execute(
                sql.SQL("CREATE DATABASE {} OWNER {}").format(
                    sql.Identifier(db_name), sql.Identifier(url.username)
                )
            )
        created = True
        yield url.set(database=db_name).render_as_string(hide_password=False)
    finally:
        try:
            if created:
                _drop_scratch_database(admin_conn, db_name)
        finally:
            admin_conn.close()


@pytest.fixture
def migrated_database(scratch_database, monkeypatch):
    """A scratch database with all migrations applied, torn down after."""
    from alembic import command
    from alembic.config import Config

    # cache_clear() forgets engines without closing their pooled connections.
    # Track every application engine, including ones local client fixtures forget,
    # and dispose them before scratch_database attempts to drop its database.
    from app import db as app_db

    engines = []
    original_create_engine = app_db.create_engine

    def tracked_create_engine(*args, **kwargs):
        engine = original_create_engine(*args, **kwargs)
        engines.append(engine)
        return engine

    monkeypatch.setattr(app_db, "create_engine", tracked_create_engine)
    app_db._engine_for.cache_clear()
    monkeypatch.setenv("DATABASE_URL", scratch_database)
    cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    try:
        command.upgrade(cfg, "head")
        yield scratch_database
    finally:
        for engine in engines:
            engine.dispose()
        app_db._engine_for.cache_clear()


@pytest.fixture
def client(migrated_database):
    from app.db import _engine_for
    from app.main import app

    _engine_for.cache_clear()
    yield TestClient(app)
    _engine_for.cache_clear()


@pytest.fixture
def db_session(migrated_database):
    engine = create_engine(migrated_database)
    with Session(engine) as session:
        yield session
    engine.dispose()


@pytest.fixture(autouse=True)
def _no_real_dns(monkeypatch):
    """Feed fetches check the host resolves to public addresses
    (app/adapters/safe_fetch.py). Tests use mock transports, so answer that
    check without real DNS; SSRF tests override it."""
    monkeypatch.setattr("app.adapters.safe_fetch._resolve", lambda host: ["93.184.216.34"])


@pytest.fixture(autouse=True)
def _fresh_rate_limits():
    """The rate limiter's windows are process-global; without this, requests
    from earlier tests count against later ones and they fail with 429."""
    from app.rate_limit import _WINDOWS

    _WINDOWS.clear()
    yield
    _WINDOWS.clear()
