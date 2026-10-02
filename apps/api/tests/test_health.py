from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from app.jobs.monitor import worker_problems
from app.main import app
from app.models import Job

client = TestClient(app)


def test_health_returns_ok() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_revision_is_public_non_cached_and_matches_environment(monkeypatch) -> None:
    monkeypatch.setenv("RELEASE_SHA", "a" * 40)
    response = client.get("/health/revision")
    assert response.status_code == 200
    assert response.text == "a" * 40
    assert response.headers["cache-control"] == "no-store"

    monkeypatch.setenv("RELEASE_SHA", "invalid-or-secret")
    assert client.get("/health/revision").text == "unknown"


def test_ready_checks_the_database(client) -> None:
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "db": "ok"}


def test_ready_is_503_when_the_database_is_unreachable(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://nobody:x@127.0.0.1:1/none")
    response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json() == {"status": "unavailable", "db": "error"}


NOW = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)


def _job(db, **fields) -> None:
    db.add(Job(type="publish_scheduler", payload={}, **fields))
    db.flush()


def test_worker_ok_with_a_recent_claim(db_session) -> None:
    _job(db_session, status="DONE", locked_at=NOW - timedelta(minutes=2), run_after=NOW - timedelta(minutes=2))
    assert worker_problems(db_session, NOW) == []


def test_worker_stale_when_nothing_ever_claimed(db_session) -> None:
    assert worker_problems(db_session, NOW) == ["WORKER_STALE: last job claimed never"]


def test_worker_stale_after_ten_minutes_without_a_claim(db_session) -> None:
    _job(db_session, status="DONE", locked_at=NOW - timedelta(minutes=11), run_after=NOW - timedelta(minutes=11))
    assert worker_problems(db_session, NOW) == ["WORKER_STALE: last job claimed 11 min ago"]


def test_long_running_job_with_a_live_lease_is_not_stale(db_session) -> None:
    _job(
        db_session,
        status="RUNNING",
        locked_at=NOW - timedelta(minutes=12),
        lock_expiry=NOW + timedelta(minutes=2),
        run_after=NOW - timedelta(minutes=12),
    )
    assert worker_problems(db_session, NOW) == []


def test_queue_backlog_when_a_due_job_waits_too_long(db_session) -> None:
    _job(db_session, status="DONE", locked_at=NOW - timedelta(minutes=1), run_after=NOW - timedelta(minutes=1))
    _job(db_session, status="PENDING", run_after=NOW - timedelta(minutes=20))
    _job(db_session, status="PENDING", run_after=NOW + timedelta(hours=1))  # backing off, not due
    assert worker_problems(db_session, NOW) == ["QUEUE_BACKLOG: oldest due job waiting 20 min"]
