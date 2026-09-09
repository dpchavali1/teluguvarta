"""T18 acceptance test: crossing a configured budget/error-rate/circuit-
breaker threshold produces an observable alert (dispatched through a fake
channel here — no real webhook/Sentry delivery required)."""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app import alerts
from app.ai import budget
from app.ai.tasks import Task
from app.jobs.source_fetch import CIRCUIT_BREAKER_THRESHOLD
from app.models import Job, Source

from .conftest import requires_postgres

pytestmark = requires_postgres


class _FakeChannel:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def __call__(self, severity: str, message: str) -> None:
        self.calls.append((severity, message))


def _make_source(**overrides) -> Source:
    defaults = {"name": "Test Source", "rights_status": "LINK_ONLY", "active": True}
    defaults.update(overrides)
    return Source(**defaults)


def test_monthly_budget_alert_fires_once_crossed(migrated_database, monkeypatch):
    engine = create_engine(migrated_database)
    with Session(engine) as db:
        monkeypatch.setenv("MONTHLY_AI_BUDGET_USD", "1.00")
        budget.record_call(
            db, task=Task.SUMMARY, provider="openai", model="gpt-4o-mini",
            status="SUCCESS", tokens_in=2_000_000, tokens_out=2_000_000,
        )
        channel = _FakeChannel()
        fired = alerts.check_budget_alerts(db, channel=channel)

        assert "MONTHLY_AI_BUDGET_USD" in fired
        assert any("monthly budget" in message for _, message in channel.calls)


def test_daily_alert_threshold_fires(migrated_database, monkeypatch):
    engine = create_engine(migrated_database)
    with Session(engine) as db:
        monkeypatch.delenv("MONTHLY_AI_BUDGET_USD", raising=False)
        monkeypatch.setenv("DAILY_AI_ALERT_USD", "0.01")
        budget.record_call(
            db, task=Task.SUMMARY, provider="openai", model="gpt-4o-mini",
            status="SUCCESS", tokens_in=200_000, tokens_out=200_000,
        )
        channel = _FakeChannel()
        fired = alerts.check_budget_alerts(db, channel=channel)

        assert "DAILY_AI_ALERT_USD" in fired
        assert any("daily alert threshold" in message for _, message in channel.calls)


def test_no_budget_alert_when_under_threshold(migrated_database, monkeypatch):
    engine = create_engine(migrated_database)
    with Session(engine) as db:
        monkeypatch.setenv("MONTHLY_AI_BUDGET_USD", "1000.00")
        monkeypatch.delenv("DAILY_AI_ALERT_USD", raising=False)
        channel = _FakeChannel()
        fired = alerts.check_budget_alerts(db, channel=channel)

        assert fired == []
        assert channel.calls == []


def test_circuit_breaker_alert_fires_for_tripped_source(migrated_database):
    engine = create_engine(migrated_database)
    with Session(engine) as db:
        source = _make_source(fail_count=CIRCUIT_BREAKER_THRESHOLD)
        db.add(source)
        db.commit()

        channel = _FakeChannel()
        fired = alerts.check_circuit_breaker_alerts(db, channel=channel)

        assert fired == [f"CIRCUIT_BREAKER:{source.id}"]
        assert any("circuit breaker" in message for _, message in channel.calls)


def test_circuit_breaker_alert_silent_when_healthy(migrated_database):
    engine = create_engine(migrated_database)
    with Session(engine) as db:
        db.add(_make_source(fail_count=CIRCUIT_BREAKER_THRESHOLD - 1))
        db.commit()

        channel = _FakeChannel()
        assert alerts.check_circuit_breaker_alerts(db, channel=channel) == []
        assert channel.calls == []


def test_job_error_rate_alert_fires_over_threshold(migrated_database):
    engine = create_engine(migrated_database)
    with Session(engine) as db:
        now = datetime.now(UTC)
        for _ in range(6):
            db.add(Job(id=uuid.uuid4(), type="source_fetch", status="FAILED", run_after=now, locked_at=now, payload={}))
        for _ in range(2):
            db.add(Job(id=uuid.uuid4(), type="source_fetch", status="DONE", run_after=now, locked_at=now, payload={}))
        db.commit()

        channel = _FakeChannel()
        fired = alerts.check_job_error_rate_alert(db, now=now, channel=channel)

        assert fired == ["JOB_ERROR_RATE"]
        assert any("failure rate" in message for _, message in channel.calls)


def test_job_error_rate_alert_ignores_stale_jobs_outside_window(migrated_database):
    engine = create_engine(migrated_database)
    with Session(engine) as db:
        now = datetime.now(UTC)
        stale = now - timedelta(hours=2)
        for _ in range(6):
            db.add(Job(id=uuid.uuid4(), type="source_fetch", status="FAILED", run_after=stale, locked_at=stale, payload={}))
        db.commit()

        channel = _FakeChannel()
        assert alerts.check_job_error_rate_alert(db, now=now, channel=channel) == []
