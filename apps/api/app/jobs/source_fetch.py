"""The `source_fetch` job (T08): scheduling + the actual fetch/normalize/
validate/emit run against one source's adapter.

Only §6.4's DISCOVERED -> RIGHTS_BLOCKED | NORMALIZED slice happens here;
DEDUPED/CLUSTERED/... are later tickets (T09+).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy.orm import Session

from app.adapters.base import SourceAdapter
from app.adapters.openfema import OpenFemaAdapter, is_openfema_url
from app.adapters.rss import RssFeedAdapter
from app.jobs.queue import enqueue_job
from app.models import Job, Source

# §6.5 circuit breaker: once a source has this many *consecutive* failures
# (reset to 0 on any success), the scheduler stops enqueueing new
# source_fetch jobs for it. Deliberately manual-reset — fail_count/
# last_error_at/last_success_at are already visible via T06's
# /v1/admin/sources fields, so an editor/admin investigates and fixes the
# source (or re-enables it) rather than the breaker auto-clearing on a timer.
CIRCUIT_BREAKER_THRESHOLD = 5

FETCH_TIMEOUT_SECONDS = 10.0

# A new source's first successful fetch returns its whole feed history
# (ntnews: 200 items going back days). Items older than this are stored
# ARCHIVED so they dedupe on later fetches but never reach the AI pipeline.
# Items with no published date are kept.
FIRST_FETCH_MAX_AGE = timedelta(hours=48)


def _now() -> datetime:
    return datetime.now(UTC)


def _fetch_window(refresh_minutes: int, now: datetime) -> datetime:
    """Floors `now` to a `refresh_minutes`-wide bucket since the epoch, used
    as part of the job's dedupe_key so scheduling is idempotent: calling the
    scheduler any number of times within the same window enqueues at most
    one job for a given source (the unique `dedupe_key` constraint makes the
    second+ call a no-op), and a fresh key becomes available next window.
    """
    epoch = datetime(1970, 1, 1, tzinfo=UTC)
    elapsed_minutes = int((now - epoch).total_seconds() // 60)
    bucket_start_minutes = (elapsed_minutes // refresh_minutes) * refresh_minutes
    return epoch + timedelta(minutes=bucket_start_minutes)


def schedule_due_source_fetches(db: Session) -> int:
    """Enqueues a `source_fetch` job for every active, non-DISABLED source
    that isn't already covered by a pending/running job for its current
    cadence window and hasn't tripped the circuit breaker. Returns the
    number of jobs actually enqueued (dedupe collisions don't count).
    """
    now = _now()
    sources = db.query(Source).filter(
        Source.active.is_(True),
        Source.rights_status != "DISABLED",
        Source.source_type.is_distinct_from("X_ACCOUNT"),
        Source.refresh_minutes.isnot(None),
    ).all()

    enqueued = 0
    for source in sources:
        if source.fail_count >= CIRCUIT_BREAKER_THRESHOLD:
            continue
        assert source.refresh_minutes is not None  # filtered by the query above
        window = _fetch_window(source.refresh_minutes, now)
        dedupe_key = f"source_fetch:{source.id}:{window.isoformat()}"
        job = enqueue_job(db, "source_fetch", {"source_id": str(source.id)}, dedupe_key=dedupe_key)
        if job is not None:
            enqueued += 1
    return enqueued


def adapter_for(source: Source) -> SourceAdapter:
    """OpenFEMA is the only non-feed source; every other source is RSS/Atom."""
    if is_openfema_url(source.feed_url):
        return OpenFemaAdapter(source)
    return RssFeedAdapter(source)


def run_source_fetch(db: Session, job: Job) -> None:
    """Runs one source's `fetch -> normalize -> validate -> emit` pipeline
    (T07's adapter contract) and updates the source's health fields. Raises
    on any fetch/parse failure so the caller's job-queue retry/backoff
    (`app.jobs.queue.fail_job`) takes over — this function itself never
    retries.
    """
    source_id = job.payload["source_id"]
    source = db.get(Source, source_id)
    if source is None:
        raise ValueError(f"source_fetch job references missing source {source_id}")

    adapter = adapter_for(source)
    backlog_cutoff = _now() - FIRST_FETCH_MAX_AGE if source.last_success_at is None else None
    try:
        with httpx.Client(timeout=FETCH_TIMEOUT_SECONDS) as client:
            raw_items = adapter.fetch(client)
        for raw_item in raw_items.items:
            normalized = adapter.normalize(raw_item)
            result = adapter.validate(normalized)
            if result.valid:
                archive = (
                    backlog_cutoff is not None
                    and normalized.published_at is not None
                    and normalized.published_at < backlog_cutoff
                )
                adapter.emit(db, normalized, archive=archive)
    except Exception:
        source.fail_count += 1
        source.last_error_at = _now()
        db.commit()
        raise

    source.fail_count = 0
    source.last_success_at = _now()
    db.commit()
