"""Generic job-queue mechanics: claim, complete, fail, enqueue.

Implements the claiming pattern and retry/backoff parameters decided in
ADR-003 (`docs/adr/ADR-003-database-job-queue-strategy.md`). Nothing here
knows what a `source_fetch` job actually does — that's `source_fetch.py`.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models import Job

# Bounded retries (NON_NEGOTIABLES #10: no infinite retry loop). Attempts are
# counted at claim time, so MAX_JOB_ATTEMPTS is the total number of times a
# job is ever run, not the number of retries after the first.
MAX_JOB_ATTEMPTS = 5
BACKOFF_BASE_SECONDS = 60
BACKOFF_CAP_SECONDS = 3600
# How long a claimed job may run before another worker is allowed to treat
# it as crashed and reclaim it.
LOCK_TTL_SECONDS = 300


def _now() -> datetime:
    return datetime.now(UTC)


def backoff_seconds(attempts: int) -> int:
    return min(BACKOFF_BASE_SECONDS * (2 ** max(attempts - 1, 0)), BACKOFF_CAP_SECONDS)


def enqueue_job(
    db: Session,
    job_type: str,
    payload: dict,
    *,
    dedupe_key: str | None = None,
    run_after: datetime | None = None,
) -> Job | None:
    """Inserts a new PENDING job. If `dedupe_key` collides with an existing
    job (any status — recurring jobs pass a time-bucketed key so a fresh key
    is available next cycle, see `source_fetch.schedule_due_source_fetches`),
    this is a no-op and returns None rather than erroring — callers that
    schedule on every poll rely on this to stay idempotent.
    """
    insert_stmt = pg_insert(Job).values(
        type=job_type,
        payload=payload,
        run_after=run_after or _now(),
        dedupe_key=dedupe_key,
    )
    if dedupe_key is not None:
        insert_stmt = insert_stmt.on_conflict_do_nothing(index_elements=[Job.dedupe_key])
    job_id = db.execute(insert_stmt.returning(Job.id)).scalar_one_or_none()
    if job_id is None:
        return None
    return db.get(Job, job_id)


def claim_job(db: Session, job_types: Sequence[str]) -> Job | None:
    """Claims and returns at most one runnable job, or None if none are
    available. Safe for multiple worker processes to call concurrently
    against the same table: `FOR UPDATE SKIP LOCKED` means a second claimer
    never blocks on, or double-picks, a row a first claimer already holds —
    each call either gets a distinct job or nothing.

    A job counts as runnable if it's PENDING and due (`run_after <= now()`),
    or if it's RUNNING but its lock has expired (a previous worker crashed
    mid-job) — that reclaim path is what keeps a crash from stalling a job
    forever without needing a separate sweep process.
    """
    now = _now()
    stmt = (
        select(Job)
        .where(
            Job.type.in_(job_types),
            (
                (Job.status == "PENDING") & (Job.run_after <= now)
                | (Job.status == "RUNNING") & (Job.lock_expiry < now)
            ),
        )
        .order_by(Job.run_after)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    job = db.scalars(stmt).first()
    if job is None:
        return None

    job.status = "RUNNING"
    job.attempts += 1
    job.locked_at = now
    job.lock_expiry = now + timedelta(seconds=LOCK_TTL_SECONDS)
    db.commit()
    return job


def complete_job(db: Session, job: Job) -> None:
    job.status = "DONE"
    job.last_error = None
    db.commit()


def fail_job(db: Session, job: Job, error: str) -> None:
    """Bounded retry with exponential backoff. After MAX_JOB_ATTEMPTS the
    job is left FAILED — a terminal, observable record — instead of being
    rescheduled again.
    """
    job.last_error = error[:4000]
    if job.attempts >= MAX_JOB_ATTEMPTS:
        job.status = "FAILED"
    else:
        job.status = "PENDING"
        job.run_after = _now() + timedelta(seconds=backoff_seconds(job.attempts))
    db.commit()
