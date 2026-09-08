"""The one lightweight always-on worker process decided in ADR-003.

Run with `python -m app.jobs.worker`. Polls for due `source_fetch` jobs
(scheduling new ones on its own cadence) and processes at most one per loop
iteration, sleeping when there's nothing to do.
"""

from __future__ import annotations

import logging
import os
import time

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.jobs.queue import claim_job, complete_job, fail_job
from app.jobs.source_fetch import run_source_fetch, schedule_due_source_fetches

logger = logging.getLogger(__name__)

JOB_HANDLERS = {
    "source_fetch": run_source_fetch,
}

POLL_INTERVAL_SECONDS = 5.0


def _session() -> Session:
    engine = create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)
    return sessionmaker(bind=engine)()


def process_one(db: Session) -> bool:
    """Runs one unit of work. Returns True if a job was processed."""
    schedule_due_source_fetches(db)
    db.commit()

    job = claim_job(db, list(JOB_HANDLERS))
    if job is None:
        return False

    handler = JOB_HANDLERS[job.type]
    try:
        handler(db, job)
    except Exception as exc:  # noqa: BLE001 - any handler failure must be retried/bounded, not crash the worker
        logger.warning("job %s (%s) failed: %s", job.id, job.type, exc)
        fail_job(db, job, str(exc))
    else:
        complete_job(db, job)
    return True


def run_forever() -> None:
    db = _session()
    try:
        while True:
            processed = process_one(db)
            if not processed:
                time.sleep(POLL_INTERVAL_SECONDS)
    finally:
        db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_forever()
