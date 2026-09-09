"""X2 acceptance tests: `x_official_account_fetch` scheduling (rights gate,
circuit breaker, budget gate, idempotency) and the run function's
since_id/telemetry/health bookkeeping.
"""

import httpx
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.jobs import x_fetch
from app.models import Job, Source, XAccount, XApiCallLog

from .conftest import requires_postgres

_RealClient = httpx.Client


def _mock_httpx_client(status_code: int = 200, json_body: dict | None = None):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json=json_body or {"data": [], "meta": {}})

    def factory(*args, **kwargs) -> httpx.Client:
        return _RealClient(transport=httpx.MockTransport(handler))

    return factory


def _make_source(**overrides) -> Source:
    defaults = {"name": "Official Account", "rights_status": "LINK_ONLY", "active": True, "fail_count": 0}
    defaults.update(overrides)
    return Source(**defaults)


def _make_x_account(source_id, **overrides) -> XAccount:
    defaults = {
        "source_id": source_id,
        "x_user_id": "999",
        "handle": "telugu_news",
        "polling_cadence": 5,
        "since_id": None,
    }
    defaults.update(overrides)
    return XAccount(**defaults)


@requires_postgres
def test_schedule_skips_disabled_circuit_broken_and_uncadenced_accounts(migrated_database):
    engine = create_engine(migrated_database)
    with Session(engine) as db:
        good_source = _make_source(name="Good")
        disabled_source = _make_source(name="Disabled", rights_status="DISABLED")
        broken_source = _make_source(name="Broken", fail_count=x_fetch.CIRCUIT_BREAKER_THRESHOLD)
        no_cadence_source = _make_source(name="No cadence")
        db.add_all([good_source, disabled_source, broken_source, no_cadence_source])
        db.commit()

        good = _make_x_account(good_source.id, handle="good", x_user_id="900")
        disabled = _make_x_account(disabled_source.id, handle="disabled", x_user_id="901")
        broken = _make_x_account(broken_source.id, handle="broken", x_user_id="902")
        no_cadence = _make_x_account(no_cadence_source.id, handle="no_cadence", x_user_id="903", polling_cadence=None)
        db.add_all([good, disabled, broken, no_cadence])
        db.commit()

        enqueued = x_fetch.schedule_due_x_fetches(db)
        db.commit()

        assert enqueued == 1
        jobs = db.scalars(select(Job).where(Job.type == "x_official_account_fetch")).all()
        assert len(jobs) == 1
        assert jobs[0].payload["x_account_id"] == str(good.id)


@requires_postgres
def test_schedule_skips_everyone_when_over_monthly_budget(migrated_database, monkeypatch):
    monkeypatch.setenv("MONTHLY_X_API_BUDGET_USD", "1")
    engine = create_engine(migrated_database)
    with Session(engine) as db:
        source = _make_source()
        db.add(source)
        db.commit()
        x_account = _make_x_account(source.id)
        db.add(x_account)
        db.commit()
        # Spend past budget via a real logged call.
        x_fetch.record_call(db, x_account_id=x_account.id, posts_read=0, cost_usd=5.0, status="OK")
        db.commit()

        enqueued = x_fetch.schedule_due_x_fetches(db)
        assert enqueued == 0
        jobs = db.scalars(select(Job).where(Job.type == "x_official_account_fetch")).all()
        assert len(jobs) == 0


@requires_postgres
def test_schedule_is_idempotent_within_the_same_cadence_window(migrated_database):
    engine = create_engine(migrated_database)
    with Session(engine) as db:
        source = _make_source()
        db.add(source)
        db.commit()
        x_account = _make_x_account(source.id)
        db.add(x_account)
        db.commit()

        x_fetch.schedule_due_x_fetches(db)
        db.commit()
        x_fetch.schedule_due_x_fetches(db)
        db.commit()

        jobs = db.scalars(select(Job).where(Job.type == "x_official_account_fetch")).all()
        assert len(jobs) == 1


@requires_postgres
def test_run_success_advances_since_id_resets_health_and_logs_cost(migrated_database, monkeypatch):
    monkeypatch.setenv("X_API_BEARER_TOKEN", "test-token")
    monkeypatch.setenv("X_API_COST_PER_POST_USD", "0.01")
    engine = create_engine(migrated_database)
    with Session(engine) as db:
        source = _make_source(fail_count=3)
        db.add(source)
        db.commit()
        x_account = _make_x_account(source.id, since_id="500")
        db.add(x_account)
        db.commit()

        monkeypatch.setattr(
            x_fetch.httpx,
            "Client",
            _mock_httpx_client(200, {"data": [{"id": "501", "text": "New post", "created_at": "2026-09-09T16:00:00.000Z"}], "meta": {}}),
        )

        job = Job(type="x_official_account_fetch", payload={"x_account_id": str(x_account.id)})
        db.add(job)
        db.commit()

        x_fetch.run_x_official_account_fetch(db, job)

        db.refresh(source)
        db.refresh(x_account)
        assert source.fail_count == 0
        assert source.last_success_at is not None
        assert x_account.since_id == "501"

        logs = db.scalars(select(XApiCallLog).where(XApiCallLog.x_account_id == x_account.id)).all()
        assert len(logs) == 1
        assert logs[0].status == "OK"
        assert logs[0].posts_read == 1
        assert float(logs[0].cost_usd) == pytest.approx(0.01)


@requires_postgres
def test_run_missing_bearer_token_fails_closed_without_scraping(migrated_database, monkeypatch):
    monkeypatch.delenv("X_API_BEARER_TOKEN", raising=False)
    engine = create_engine(migrated_database)
    with Session(engine) as db:
        source = _make_source()
        db.add(source)
        db.commit()
        x_account = _make_x_account(source.id)
        db.add(x_account)
        db.commit()

        job = Job(type="x_official_account_fetch", payload={"x_account_id": str(x_account.id)})
        db.add(job)
        db.commit()

        with pytest.raises(RuntimeError, match="X_API_BEARER_TOKEN"):
            x_fetch.run_x_official_account_fetch(db, job)


@requires_postgres
def test_run_rate_limit_updates_health_and_logs_without_retrying_itself(migrated_database, monkeypatch):
    monkeypatch.setenv("X_API_BEARER_TOKEN", "test-token")
    engine = create_engine(migrated_database)
    with Session(engine) as db:
        source = _make_source(fail_count=0)
        db.add(source)
        db.commit()
        x_account = _make_x_account(source.id)
        db.add(x_account)
        db.commit()

        monkeypatch.setattr(x_fetch.httpx, "Client", _mock_httpx_client(429, {"title": "Too Many Requests"}))

        job = Job(type="x_official_account_fetch", payload={"x_account_id": str(x_account.id)})
        db.add(job)
        db.commit()

        from app.x.client import XRateLimitedError

        with pytest.raises(XRateLimitedError):
            x_fetch.run_x_official_account_fetch(db, job)

        db.refresh(source)
        assert source.fail_count == 1
        assert source.last_error_at is not None

        logs = db.scalars(select(XApiCallLog).where(XApiCallLog.x_account_id == x_account.id)).all()
        assert len(logs) == 1
        assert logs[0].status == "RATE_LIMITED"


@requires_postgres
def test_run_does_not_duplicate_items_on_rerun(migrated_database, monkeypatch):
    monkeypatch.setenv("X_API_BEARER_TOKEN", "test-token")
    engine = create_engine(migrated_database)
    with Session(engine) as db:
        source = _make_source()
        db.add(source)
        db.commit()
        x_account = _make_x_account(source.id)
        db.add(x_account)
        db.commit()

        monkeypatch.setattr(
            x_fetch.httpx,
            "Client",
            _mock_httpx_client(200, {"data": [{"id": "600", "text": "Repeated post", "created_at": "2026-09-09T17:00:00.000Z"}], "meta": {}}),
        )

        from app.models import SourceItem

        for _ in range(2):
            job = Job(type="x_official_account_fetch", payload={"x_account_id": str(x_account.id)})
            db.add(job)
            db.commit()
            x_fetch.run_x_official_account_fetch(db, job)

        rows = db.scalars(select(SourceItem).where(SourceItem.source_id == source.id)).all()
        assert len(rows) == 1
