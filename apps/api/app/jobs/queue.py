"""Generic job-queue mechanics: claim, complete, fail, enqueue.

Implements the claiming pattern and retry/backoff parameters decided in
ADR-003 (`docs/adr/ADR-003-database-job-queue-strategy.md`). Nothing here
knows what a `source_fetch` job actually does — that's `source_fetch.py`.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
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


class LeaseLost(RuntimeError):
    """This worker's lease on a job expired and another worker reclaimed it
    (review 2026-09-29 #8). The handler must stop: the job is no longer ours
    to continue, complete, or fail."""


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

    An expired job that has already used `MAX_JOB_ATTEMPTS` is marked FAILED
    instead of reclaimed, so a job that keeps outliving its lease (or crashing
    the worker) still has a bounded number of runs.
    """
    now = _now()
    db.execute(
        update(Job)
        .where(
            Job.type.in_(job_types),
            Job.status == "RUNNING",
            Job.lock_expiry < now,
            Job.attempts >= MAX_JOB_ATTEMPTS,
        )
        .values(status="FAILED", last_error="lease expired after the final attempt")
    )
    stmt = (
        select(Job)
        .where(
            Job.type.in_(job_types),
            (
                (Job.status == "PENDING") & (Job.run_after <= now)
                | (Job.status == "RUNNING") & (Job.lock_expiry < now) & (Job.attempts < MAX_JOB_ATTEMPTS)
            ),
        )
        .order_by(Job.run_after)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    job = db.scalars(stmt).first()
    if job is None:
        db.commit()
        return None

    job.status = "RUNNING"
    job.attempts += 1
    job.locked_at = now
    job.lock_expiry = now + timedelta(seconds=LOCK_TTL_SECONDS)
    db.commit()
    # The claim's `locked_at` is this worker's ownership token. Kept as a
    # plain attribute: mapped ones are reloaded from the row after a commit.
    job.lease_token = now
    return job


def _owns(db: Session, job: Job) -> bool:
    """True unless this job was claimed by us and has since been reclaimed.
    A job never claimed through `claim_job` (tests, scripts) has no token."""
    token = getattr(job, "lease_token", None)
    if token is None:
        return True
    row = db.execute(
        select(Job.status, Job.locked_at).where(Job.id == job.id).with_for_update()
    ).one_or_none()
    return row is not None and row.status == "RUNNING" and row.locked_at == token


def renew_lease(db: Session, job: Job | None) -> None:
    """Extends a running job's lease, committing the caller's work so far.
    Long handlers call it between units of work (per story), so the lease
    only has to cover one unit. Raises `LeaseLost` if another worker has
    reclaimed the job. With no job (a direct call) it only commits."""
    if job is None:
        db.commit()
        return
    if not _owns(db, job):
        db.rollback()
        raise LeaseLost(f"job {job.id} was reclaimed by another worker")
    job.lock_expiry = _now() + timedelta(seconds=LOCK_TTL_SECONDS)
    db.commit()


def complete_job(db: Session, job: Job) -> None:
    if not _owns(db, job):
        db.rollback()
        raise LeaseLost(f"job {job.id} was reclaimed by another worker")
    job.status = "DONE"
    job.last_error = None
    db.commit()


def fail_job(db: Session, job: Job, error: str) -> None:
    """Bounded retry with exponential backoff. After MAX_JOB_ATTEMPTS the
    job is left FAILED — a terminal, observable record — instead of being
    rescheduled again. A job another worker has reclaimed is left to it.
    """
    if not _owns(db, job):
        db.rollback()
        return
    job.last_error = error[:4000]
    if job.attempts >= MAX_JOB_ATTEMPTS:
        job.status = "FAILED"
    else:
        job.status = "PENDING"
        job.run_after = _now() + timedelta(seconds=backoff_seconds(job.attempts))
    db.commit()
