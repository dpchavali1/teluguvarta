"""T18 acceptance tests: structured logging context, error-tracking capture
(request_id/actor/job context reaches the captured event), and the admin
observability endpoint (ingestion health / job queue / AI cost)."""

import json
import logging
import uuid
from datetime import UTC, datetime, timedelta
from io import StringIO

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.jobs.source_fetch import CIRCUIT_BREAKER_THRESHOLD
from app.models import Job, Source
from app.observability import error_tracking
from app.observability.logging import (
    JsonFormatter,
    current_context,
    job_context,
    request_context,
)

from .conftest import requires_postgres

pytestmark = requires_postgres

ADMIN_EMAIL = "admin@example.com"
PASSWORD = "correct horse battery staple"


@pytest.fixture
def client(migrated_database, monkeypatch):
    monkeypatch.setenv("ADMIN_JWT_SECRET", "test-secret")

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


def _token(client, db_session, *, role="ADMIN", email=ADMIN_EMAIL):
    # Mints a full-session token directly rather than via /login: these tests
    # exercise observability endpoints, not P0-3/ADR-012's MFA-enrollment gate.
    from app.models import User
    from app.security import create_admin_access_token, hash_password

    user = User(id=uuid.uuid4(), email=email, role=role, password_hash=hash_password(PASSWORD))
    db_session.add(user)
    db_session.commit()

    token, _ = create_admin_access_token(user.id, user.email, role)
    return token


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


# --- structured logging -----------------------------------------------


def test_request_context_populates_current_context():
    assert current_context() == {}
    with request_context("req-1", "actor@example.com"):
        assert current_context() == {"request_id": "req-1", "actor": "actor@example.com"}
    assert current_context() == {}


def test_job_context_nests_inside_request_context():
    with request_context("req-1"):
        with job_context("source_fetch", job_id="job-1", story_id="story-1"):
            ctx = current_context()
            assert ctx["request_id"] == "req-1"
            assert ctx["job_type"] == "source_fetch"
            assert ctx["job_id"] == "job-1"
            assert ctx["story_id"] == "story-1"
        assert current_context() == {"request_id": "req-1"}


def test_json_formatter_emits_context_fields():
    logger = logging.getLogger("test.observability")
    logger.setLevel(logging.INFO)
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    try:
        with request_context("req-42", "actor@example.com"):
            logger.info("hello")
    finally:
        logger.removeHandler(handler)

    payload = json.loads(stream.getvalue())
    assert payload["message"] == "hello"
    assert payload["request_id"] == "req-42"
    assert payload["actor"] == "actor@example.com"


# --- error tracking ------------------------------------------------------


def test_capture_exception_without_dsn_is_a_safe_noop(monkeypatch):
    monkeypatch.delenv("SENTRY_DSN", raising=False)
    with request_context("req-1", "actor@example.com"):
        event_id = error_tracking.capture_exception(RuntimeError("boom"))
    assert event_id


def test_capture_exception_ships_context_to_sentry_dsn(monkeypatch):
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["auth_header"] = request.headers["X-Sentry-Auth"]
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"id": "abc"})

    monkeypatch.setenv("SENTRY_DSN", "https://testkey@sentry.example.com/123")
    monkeypatch.setattr(
        error_tracking.httpx, "post",
        lambda url, json, headers, timeout: handler(httpx.Request("POST", url, json=json, headers=headers)),
    )

    with request_context("req-99", "actor@example.com"), job_context("source_fetch", story_id="story-9"):
        error_tracking.capture_exception(RuntimeError("boom"))

    assert captured["url"] == "https://sentry.example.com/api/123/store/"
    assert "testkey" in captured["auth_header"]
    assert captured["body"]["tags"]["request_id"] == "req-99"
    assert captured["body"]["tags"]["actor"] == "actor@example.com"
    assert captured["body"]["tags"]["story_id"] == "story-9"


def test_debug_throw_endpoint_surfaces_error_with_context(client, db_session):
    token = _token(client, db_session)

    from app.main import app

    lenient_client = TestClient(app, raise_server_exceptions=False)
    response = lenient_client.get("/v1/admin/_debug/throw", headers=_auth(token))

    assert response.status_code == 500
    body = response.json()
    assert body["error"]["code"] == "INTERNAL_ERROR"
    assert body["error"]["request_id"]


# --- admin observability endpoint -----------------------------------------


def test_observability_endpoint_reports_ingestion_job_and_cost_health(client, db_session):
    token = _token(client, db_session)

    source = Source(name="Tripped Source", rights_status="LINK_ONLY", active=True, fail_count=CIRCUIT_BREAKER_THRESHOLD)
    db_session.add(source)
    db_session.commit()

    now = datetime.now(UTC)
    db_session.add(
        Job(
            id=uuid.uuid4(), type="source_fetch", status="DONE", run_after=now,
            payload={"source_id": str(source.id)},
        )
    )
    db_session.add(Job(id=uuid.uuid4(), type="source_fetch", status="PENDING", run_after=now - timedelta(minutes=5), payload={}))
    db_session.commit()

    response = client.get("/v1/admin/observability", headers=_auth(token))
    assert response.status_code == 200
    body = response.json()

    ingestion = {row["source_id"]: row for row in body["ingestion_health"]}
    assert ingestion[str(source.id)]["success_count_24h"] == 1
    assert ingestion[str(source.id)]["circuit_breaker_tripped"] is True

    assert body["job_queue"]["counts_by_status"]["PENDING"] >= 1
    assert body["job_queue"]["oldest_pending_age_seconds"] >= 0

    assert body["ai_cost"]["month_to_date_cost_usd"] >= 0
    assert body["x_cost"]["month_to_date_cost_usd"] >= 0
    assert body["x_cost"]["low_priority_accounts_paused"] == 0


# --- review 2026-09-30 R3: host-side operations ------------------------


def test_observability_reports_ops_check_states(client, db_session):
    from app.models import OpsCheck

    token = _token(client, db_session)
    now = datetime.now(UTC)
    db_session.add_all([
        OpsCheck(check_name="BACKUP", last_success_at=now - timedelta(hours=2), success_detail="teluguvarta_x.dump.age 12M"),
        OpsCheck(check_name="OFFSITE_COPY", last_success_at=now - timedelta(hours=30)),
        OpsCheck(
            check_name="MONITOR", last_success_at=now - timedelta(minutes=20),
            last_failure_at=now - timedelta(minutes=5), failure_detail="WORKER_STALE: no job claimed",
        ),
        # A failure older than the latest success is history, not the current state.
        OpsCheck(
            check_name="RESTORE_DRILL", last_success_at=now - timedelta(days=1),
            success_detail="RTO 14s, RPO 320 min", last_failure_at=now - timedelta(days=2),
        ),
    ])
    db_session.commit()

    response = client.get("/v1/admin/observability", headers=_auth(token))
    assert response.status_code == 200
    ops = {row["check"]: row for row in response.json()["operations"]}

    assert list(ops) == ["BACKUP", "OFFSITE_COPY", "RESTORE_DRILL", "MONITOR", "ALERT_TEST"]
    assert ops["BACKUP"]["state"] == "OK"
    assert ops["BACKUP"]["success_detail"] == "teluguvarta_x.dump.age 12M"
    assert ops["OFFSITE_COPY"]["state"] == "STALE"
    assert ops["MONITOR"]["state"] == "FAILING"
    assert ops["MONITOR"]["failure_detail"] == "WORKER_STALE: no job claimed"
    assert ops["RESTORE_DRILL"]["state"] == "OK"
    assert ops["ALERT_TEST"]["state"] == "NEVER"
    assert ops["ALERT_TEST"]["max_age_seconds"] is None


def test_ops_check_names_match_db_constraint(db_session):
    """Every name ops_status reports must be writable by ops-record.sh."""
    from app.models import OpsCheck
    from app.ops_status import CHECKS

    db_session.add_all([OpsCheck(check_name=name) for name in CHECKS])
    db_session.commit()
    db_session.add(OpsCheck(check_name="SOMETHING_ELSE"))
    with pytest.raises(Exception, match="ck_ops_checks_name"):
        db_session.commit()
    db_session.rollback()


def test_ops_state_never_stale_without_cadence():
    from app.models import OpsCheck
    from app.ops_status import _state

    now = datetime.now(UTC)
    old = OpsCheck(check_name="ALERT_TEST", last_success_at=now - timedelta(days=400))
    assert _state(old, None, now) == "OK"
    assert _state(OpsCheck(check_name="ALERT_TEST"), None, now) == "NEVER"
    assert _state(None, timedelta(hours=1), now) == "NEVER"
    only_failed = OpsCheck(check_name="BACKUP", last_failure_at=now)
    assert _state(only_failed, timedelta(hours=1), now) == "FAILING"


def test_observability_reports_budget_mode_and_windows(client, db_session, monkeypatch):
    monkeypatch.setenv("MONTHLY_AI_BUDGET_USD", "50")
    monkeypatch.setenv("MONTHLY_AI_HARD_CAP_USD", "60")
    token = _token(client, db_session)

    ai = client.get("/v1/admin/observability", headers=_auth(token)).json()["ai_cost"]
    assert ai["mode"] == "NORMAL"
    assert ai["monthly_hard_cap_usd"] == 60.0
    assert ai["hard_cap_remaining_usd"] == pytest.approx(60.0 - ai["month_to_date_cost_usd"])
    day_start = datetime.fromisoformat(ai["day_start"])
    assert day_start.utcoffset() == timedelta(0) and day_start.hour == 0
    assert datetime.fromisoformat(ai["quota_resets_at"]) > datetime.now(UTC)
