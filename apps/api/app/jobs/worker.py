"""The one lightweight always-on worker process decided in ADR-003.

Run with `python -m app.jobs.worker`. Polls for due `source_fetch` jobs
(scheduling new ones on its own cadence) and processes at most one per loop
iteration, sleeping when there's nothing to do.
"""

from __future__ import annotations

import os
import time

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.ai.budget import require_budget_config
from app.alerts import check_all
from app.jobs.cleanup import run_cleanup, schedule_cleanup
from app.jobs.cluster import run_dedup_cluster, schedule_dedup_cluster
from app.jobs.generate import run_ai_classify, schedule_ai_classify
from app.jobs.notify import run_notification_dispatch, schedule_notification_dispatch
from app.jobs.publish import run_publish_scheduler, schedule_publish_scheduler
from app.jobs.queue import LeaseLost, claim_job, complete_job, fail_job
from app.jobs.source_fetch import run_source_fetch, schedule_due_source_fetches
from app.jobs.translate import run_ai_translate, schedule_ai_translate
from app.jobs.why_matters import run_why_matters
from app.jobs.x_fetch import run_x_official_account_fetch, schedule_due_x_fetches
from app.observability.error_tracking import capture_exception
from app.observability.logging import configure_logging, get_logger, job_context
from app.switches import ai_paused

logger = get_logger(__name__)

# How often (in process_one calls) to run the alert threshold checks —
# every call would just re-fire the same still-tripped condition on every
# poll; once every ~5 minutes at the default 5s poll interval is enough to
# be "observable in a reasonable time" without spamming the channel.
ALERT_CHECK_EVERY_N_LOOPS = 60

JOB_HANDLERS = {
    "source_fetch": run_source_fetch,
    "x_official_account_fetch": run_x_official_account_fetch,
    "story_cluster": run_dedup_cluster,
    "ai_classify": run_ai_classify,
    "ai_translate": run_ai_translate,
    "ai_summarize": run_why_matters,
    "publish_scheduler": run_publish_scheduler,
    "notification_dispatch": run_notification_dispatch,
    "cleanup": run_cleanup,
}

# ADR-031: jobs whose whole purpose is an AI call. While AI is paused they are
# neither scheduled nor claimed, so they wait without using retry attempts.
AI_JOB_TYPES = frozenset({"ai_classify", "ai_translate", "ai_summarize"})

POLL_INTERVAL_SECONDS = 5.0


def _session() -> Session:
    engine = create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)
    return sessionmaker(bind=engine)()


def process_one(db: Session) -> bool:
    """Runs one unit of work. Returns True if a job was processed."""
    schedule_due_source_fetches(db)
    schedule_due_x_fetches(db)
    schedule_dedup_cluster(db)
    paused = ai_paused(db)
    if not paused:
        schedule_ai_classify(db)
        schedule_ai_translate(db)
    schedule_publish_scheduler(db)
    schedule_notification_dispatch(db)
    schedule_cleanup(db)
    db.commit()

    job = claim_job(db, [t for t in JOB_HANDLERS if not (paused and t in AI_JOB_TYPES)])
    if job is None:
        return False

    job_id, job_type = job.id, job.type
    handler = JOB_HANDLERS[job_type]
    story_id = job.payload.get("story_id") if isinstance(job.payload, dict) else None
    with job_context(job_type, job_id=job_id, story_id=story_id):
        try:
            handler(db, job)
            complete_job(db, job)
        except LeaseLost as exc:
            # Another worker owns the job now; its run decides the outcome.
            logger.warning("job %s (%s) abandoned: %s", job_id, job_type, exc)
        except Exception as exc:  # noqa: BLE001 - any handler failure must be retried/bounded, not crash the worker
            # Review 2026-09-29 #8: a failed flush leaves the session unusable
            # (even reading `job.id`) until rolled back, and recording the
            # failure needs it.
            db.rollback()
            logger.warning("job %s (%s) failed: %s", job_id, job_type, exc)
            capture_exception(exc, job_id=str(job_id), job_type=job_type)
            fail_job(db, job, str(exc))
    return True


def run_forever() -> None:
    configure_logging()
    require_budget_config()
    # Jobs themselves only log on failure, so this line is how `docker logs`
    # shows the worker (re)started.
    logger.info("worker started, handling %s", ", ".join(JOB_HANDLERS))
    db = _session()
    loop_count = 0
    try:
        while True:
            processed = process_one(db)
            loop_count += 1
            if loop_count % ALERT_CHECK_EVERY_N_LOOPS == 0:
                try:
                    check_all(db)
                except Exception as exc:  # noqa: BLE001 - alerting must never take the worker down
                    logger.warning("alert check failed: %s", exc)
            if not processed:
                time.sleep(POLL_INTERVAL_SECONDS)
    finally:
        db.close()


if __name__ == "__main__":
    run_forever()
