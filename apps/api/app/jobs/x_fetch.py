"""The `x_official_account_fetch` job (X2): scheduling + the actual
incremental fetch/normalize/validate/emit run for one approved X account.

Reuses T07/T08's exact adapter and job-queue contract (`app/adapters/x.py`,
`app/jobs/queue.py`) rather than a bespoke retry loop, so a 429 or any other
fetch failure gets the same bounded exponential backoff as every other job
type (NON_NEGOTIABLES #10) instead of hammering the API.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy.orm import Session

from app.adapters.x import XAdapter
from app.jobs.queue import enqueue_job
from app.jobs.source_fetch import CIRCUIT_BREAKER_THRESHOLD
from app.models import Job, Source, XAccount
from app.x.budget import (
    estimate_cost_usd,
    is_low_priority,
    is_over_monthly_budget,
    record_call,
)
from app.x.client import XRateLimitedError

FETCH_TIMEOUT_SECONDS = 10.0


def _now() -> datetime:
    return datetime.now(UTC)


def _fetch_window(cadence_minutes: int, now: datetime) -> datetime:
    """Same time-bucketed-dedupe_key pattern as
    `source_fetch._fetch_window`, keyed on the account's own
    `polling_cadence` instead of a source's `refresh_minutes`."""
    epoch = datetime(1970, 1, 1, tzinfo=UTC)
    elapsed_minutes = int((now - epoch).total_seconds() // 60)
    bucket_start_minutes = (elapsed_minutes // cadence_minutes) * cadence_minutes
    return epoch + timedelta(minutes=bucket_start_minutes)


def schedule_due_x_fetches(db: Session) -> int:
    """Enqueues an `x_official_account_fetch` job for every X account whose
    linked source is active + `LINK_ONLY` (the same rights gate as any other
    source, ADR-002/NON_NEGOTIABLES #12), has a configured polling cadence,
    and hasn't tripped the circuit breaker. X4/§19: once the monthly X API
    budget is exhausted, skips only accounts with `budget_class="LOW"` for
    this cycle — never higher-priority X accounts, and never unrelated
    ingestion sources, as a side effect of the guard. Returns the number of
    jobs actually enqueued.
    """
    over_budget = is_over_monthly_budget(db)
    now = _now()
    rows = (
        db.query(XAccount, Source)
        .join(Source, XAccount.source_id == Source.id)
        .filter(
            Source.active.is_(True),
            Source.rights_status == "LINK_ONLY",
            XAccount.polling_cadence.isnot(None),
        )
        .all()
    )

    enqueued = 0
    for x_account, source in rows:
        if source.fail_count >= CIRCUIT_BREAKER_THRESHOLD:
            continue
        if over_budget and is_low_priority(x_account):
            continue
        assert x_account.polling_cadence is not None  # filtered by the query above
        window = _fetch_window(x_account.polling_cadence, now)
        dedupe_key = f"x_official_account_fetch:{x_account.id}:{window.isoformat()}"
        job = enqueue_job(db, "x_official_account_fetch", {"x_account_id": str(x_account.id)}, dedupe_key=dedupe_key)
        if job is not None:
            enqueued += 1
    return enqueued


def run_x_official_account_fetch(db: Session, job: Job) -> None:
    """Runs one X account's `fetch -> normalize -> validate -> emit`
    pipeline, advances `since_id` to the newest post seen, records cost
    telemetry, and updates the linked source's health fields. Raises on any
    failure (including a 429) so the caller's job-queue retry/backoff
    (`app.jobs.queue.fail_job`) takes over — this function itself never
    retries.
    """
    x_account_id = job.payload["x_account_id"]
    x_account = db.get(XAccount, x_account_id)
    if x_account is None:
        raise ValueError(f"x_official_account_fetch job references missing x_account {x_account_id}")
    source = db.get(Source, x_account.source_id)
    if source is None:
        raise ValueError(f"x_account {x_account_id} references missing source {x_account.source_id}")

    bearer_token = os.environ.get("X_API_BEARER_TOKEN")
    if not bearer_token:
        # NON_NEGOTIABLES #14 / §6.3.1: no scraping fallback when API access
        # is unavailable — fail closed like any other fetch failure (circuit
        # breaker + backoff) instead of reaching for an unofficial path.
        raise RuntimeError("X_API_BEARER_TOKEN not set; cannot fetch official X account")

    adapter = XAdapter(source, x_account, bearer_token)
    try:
        with httpx.Client(timeout=FETCH_TIMEOUT_SECONDS) as client:
            raw_items = adapter.fetch(client)
        for raw_item in raw_items.items:
            normalized = adapter.normalize(raw_item)
            result = adapter.validate(normalized)
            if result.valid:
                adapter.emit(db, normalized)
    except XRateLimitedError:
        record_call(db, x_account_id=x_account.id, posts_read=0, cost_usd=0.0, status="RATE_LIMITED")
        source.fail_count += 1
        source.last_error_at = _now()
        db.commit()
        raise
    except Exception:
        record_call(
            db,
            x_account_id=x_account.id,
            posts_read=adapter.posts_read,
            cost_usd=estimate_cost_usd(adapter.posts_read),
            status="ERROR",
        )
        source.fail_count += 1
        source.last_error_at = _now()
        db.commit()
        raise

    record_call(
        db,
        x_account_id=x_account.id,
        posts_read=adapter.posts_read,
        cost_usd=estimate_cost_usd(adapter.posts_read),
        status="OK",
    )
    x_account.since_id = adapter.newest_id
    source.fail_count = 0
    source.last_success_at = _now()
    db.commit()
