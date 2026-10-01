"""The reserved `cleanup` job type (T03's `ck_jobs_type`), first used for
ADR-029's reader-report retention: once a day, erase report text past its
window. The same daily run deletes admin sessions (ADR-028) that ended more
than 30 days ago. Idempotent (re-running finds nothing new) and bounded per run."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.admin_sessions import purge_ended_sessions
from app.jobs.queue import enqueue_job
from app.models import Job
from app.observability.logging import get_logger
from app.reader_reports import purge_descriptions

logger = get_logger(__name__)

READER_REPORT_PURGE = "reader_report_purge"


def schedule_cleanup(db: Session) -> Job | None:
    """One job per UTC day; the dedupe key makes every other poll a no-op."""
    today = datetime.now(UTC).date().isoformat()
    return enqueue_job(db, "cleanup", {"task": READER_REPORT_PURGE}, dedupe_key=f"cleanup:{READER_REPORT_PURGE}:{today}")


def run_cleanup(db: Session, job: Job) -> None:
    task = job.payload.get("task") if isinstance(job.payload, dict) else None
    if task != READER_REPORT_PURGE:
        raise ValueError(f"unknown cleanup task: {task!r}")
    now = datetime.now(UTC)
    purged = purge_descriptions(db, now)
    if purged:
        logger.info("erased text of %d reader reports past retention", purged)
    sessions = purge_ended_sessions(db, now)
    if sessions:
        logger.info("deleted %d ended admin sessions past retention", sessions)
