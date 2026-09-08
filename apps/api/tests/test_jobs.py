"""T08 acceptance tests: job-queue claiming/retry mechanics and the
`source_fetch` job (scheduling, circuit breaker, rights gate, idempotency).
"""

import threading
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.jobs import source_fetch
from app.jobs.queue import (
    MAX_JOB_ATTEMPTS,
    backoff_seconds,
    claim_job,
    enqueue_job,
    fail_job,
)
from app.models import Job, Source, SourceItem

from .conftest import requires_postgres

FIXTURES = Path(__file__).parent / "fixtures"

# Captured before any test monkeypatches `source_fetch.httpx.Client` — the
# factories below must build a real Client, not recurse into the patched one
# (source_fetch's `httpx` is the same module object this file imports).
_RealClient = httpx.Client


def _mock_httpx_client(status_code: int = 200, content: bytes = b""):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, content=content)

    def factory(*args, **kwargs) -> httpx.Client:
        return _RealClient(transport=httpx.MockTransport(handler))

    return factory


def _make_source(**overrides) -> Source:
    defaults = {
        "name": "Test Source",
        "feed_url": "https://example.org/feed.xml",
        "rights_status": "LINK_ONLY",
        "active": True,
        "refresh_minutes": 15,
        "fail_count": 0,
    }
    defaults.update(overrides)
    return Source(**defaults)


def test_backoff_seconds_is_exponential_and_capped():
    assert backoff_seconds(1) == 60
    assert backoff_seconds(2) == 120
    assert backoff_seconds(3) == 240
    assert backoff_seconds(10) == 3600  # capped


@requires_postgres
def test_fail_job_reschedules_before_max_attempts(migrated_database):
    engine = create_engine(migrated_database)
    with Session(engine) as db:
        job = enqueue_job(db, "source_fetch", {}, dedupe_key="dk-retry")
        db.commit()
        job.attempts = 1
        before = datetime.now(UTC)
        fail_job(db, job, "transient error")

        assert job.status == "PENDING"
        assert job.last_error == "transient error"
        assert job.run_after > before


@requires_postgres
def test_fail_job_is_terminal_after_max_attempts(migrated_database):
    engine = create_engine(migrated_database)
    with Session(engine) as db:
        job = enqueue_job(db, "source_fetch", {}, dedupe_key="dk-terminal")
        db.commit()
        job.attempts = MAX_JOB_ATTEMPTS
        fail_job(db, job, "still failing")

        assert job.status == "FAILED"
        # A FAILED job is never claimable again — no infinite retry loop.
        assert claim_job(db, ["source_fetch"]) is None


@requires_postgres
def test_claim_job_never_double_claims_under_concurrency(migrated_database):
    engine = create_engine(migrated_database)
    with Session(engine) as db:
        for i in range(5):
            enqueue_job(db, "source_fetch", {"i": i}, dedupe_key=f"dk-race-{i}")
        db.commit()

    claimed_ids: list = []
    lock = threading.Lock()

    def worker() -> None:
        thread_engine = create_engine(migrated_database)
        with Session(thread_engine) as thread_db:
            while True:
                job = claim_job(thread_db, ["source_fetch"])
                if job is None:
                    break
                with lock:
                    claimed_ids.append(job.id)
        thread_engine.dispose()

    threads = [threading.Thread(target=worker) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(claimed_ids) == 5
    assert len(set(claimed_ids)) == 5


@requires_postgres
def test_schedule_skips_disabled_and_circuit_broken_sources(migrated_database):
    engine = create_engine(migrated_database)
    with Session(engine) as db:
        good = _make_source(name="Good")
        disabled = _make_source(name="Disabled", rights_status="DISABLED")
        circuit_broken = _make_source(
            name="Circuit broken", fail_count=source_fetch.CIRCUIT_BREAKER_THRESHOLD
        )
        db.add_all([good, disabled, circuit_broken])
        db.commit()

        enqueued = source_fetch.schedule_due_source_fetches(db)
        db.commit()

        assert enqueued == 1
        jobs = db.scalars(select(Job).where(Job.type == "source_fetch")).all()
        assert len(jobs) == 1
        assert jobs[0].payload["source_id"] == str(good.id)


@requires_postgres
def test_schedule_is_idempotent_within_the_same_cadence_window(migrated_database):
    engine = create_engine(migrated_database)
    with Session(engine) as db:
        source = _make_source()
        db.add(source)
        db.commit()

        source_fetch.schedule_due_source_fetches(db)
        db.commit()
        source_fetch.schedule_due_source_fetches(db)
        db.commit()

        jobs = db.scalars(select(Job).where(Job.type == "source_fetch")).all()
        assert len(jobs) == 1


@requires_postgres
def test_run_source_fetch_success_resets_health_and_normalizes_items(migrated_database, monkeypatch):
    engine = create_engine(migrated_database)
    with Session(engine) as db:
        source = _make_source(feed_url="https://feeds.npr.org/1001/rss.xml", fail_count=3)
        db.add(source)
        db.commit()

        content = (FIXTURES / "npr_news.xml").read_bytes()
        monkeypatch.setattr(source_fetch.httpx, "Client", _mock_httpx_client(200, content))

        job = Job(type="source_fetch", payload={"source_id": str(source.id)})
        db.add(job)
        db.commit()

        source_fetch.run_source_fetch(db, job)

        db.refresh(source)
        assert source.fail_count == 0
        assert source.last_success_at is not None

        items = db.scalars(select(SourceItem).where(SourceItem.source_id == source.id)).all()
        assert len(items) == 2
        assert all(item.ingest_status == "NORMALIZED" for item in items)


@requires_postgres
def test_run_source_fetch_blocks_rights_for_disabled_source(migrated_database, monkeypatch):
    engine = create_engine(migrated_database)
    with Session(engine) as db:
        source = _make_source(feed_url="https://feeds.npr.org/1001/rss.xml", rights_status="DISABLED")
        db.add(source)
        db.commit()

        content = (FIXTURES / "npr_news.xml").read_bytes()
        monkeypatch.setattr(source_fetch.httpx, "Client", _mock_httpx_client(200, content))

        job = Job(type="source_fetch", payload={"source_id": str(source.id)})
        db.add(job)
        db.commit()

        source_fetch.run_source_fetch(db, job)

        items = db.scalars(select(SourceItem).where(SourceItem.source_id == source.id)).all()
        assert len(items) == 2
        assert all(item.ingest_status == "RIGHTS_BLOCKED" for item in items)


@requires_postgres
def test_run_source_fetch_failure_updates_source_health_and_raises(migrated_database, monkeypatch):
    engine = create_engine(migrated_database)
    with Session(engine) as db:
        source = _make_source(fail_count=0)
        db.add(source)
        db.commit()

        monkeypatch.setattr(source_fetch.httpx, "Client", _mock_httpx_client(500, b""))

        job = Job(type="source_fetch", payload={"source_id": str(source.id)})
        db.add(job)
        db.commit()

        with pytest.raises(httpx.HTTPStatusError):
            source_fetch.run_source_fetch(db, job)

        db.refresh(source)
        assert source.fail_count == 1
        assert source.last_error_at is not None


@requires_postgres
def test_run_source_fetch_rerun_does_not_duplicate_items(migrated_database, monkeypatch):
    engine = create_engine(migrated_database)
    with Session(engine) as db:
        source = _make_source(feed_url="https://feeds.npr.org/1001/rss.xml")
        db.add(source)
        db.commit()

        content = (FIXTURES / "npr_news.xml").read_bytes()
        monkeypatch.setattr(source_fetch.httpx, "Client", _mock_httpx_client(200, content))

        for _ in range(2):
            job = Job(type="source_fetch", payload={"source_id": str(source.id)})
            db.add(job)
            db.commit()
            source_fetch.run_source_fetch(db, job)

        items = db.scalars(select(SourceItem).where(SourceItem.source_id == source.id)).all()
        assert len(items) == 2
