"""Worker liveness check that runs outside the worker (review 2026-09-29 #9).

The worker's own alerts (`app/alerts.py`) can't report the worker's absence,
so `infra/deploy/monitor.sh` runs this from the host's cron via the api
container: `python -m app.jobs.monitor`. It prints one line per problem and
exits 1, or prints a one-line summary and exits 0.

The worker enqueues `publish_scheduler`/`notification_dispatch` every couple
of minutes (see `app/jobs/worker.py`), so a live worker always has a recent
claim; no claim for `WORKER_STALE_AFTER` means it is dead or wedged.
"""

from __future__ import annotations

import os
import sys
from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.models import Job

WORKER_STALE_AFTER = timedelta(minutes=10)
QUEUE_BACKLOG_AFTER = timedelta(minutes=15)


def worker_problems(db: Session, now: datetime | None = None) -> list[str]:
    now = now or datetime.now(UTC)
    last_claim = db.scalar(select(func.max(Job.locked_at)))
    live_lease = db.scalar(
        select(func.count()).select_from(Job).where(Job.status == "RUNNING", Job.lock_expiry > now)
    )
    oldest_due = db.scalar(
        select(func.min(Job.run_after)).where(Job.status == "PENDING", Job.run_after <= now)
    )

    problems = []
    if not live_lease and (last_claim is None or now - last_claim > WORKER_STALE_AFTER):
        since = "never" if last_claim is None else f"{int((now - last_claim).total_seconds() // 60)} min ago"
        problems.append(f"WORKER_STALE: last job claimed {since}")
    if oldest_due is not None and now - oldest_due > QUEUE_BACKLOG_AFTER:
        problems.append(f"QUEUE_BACKLOG: oldest due job waiting {int((now - oldest_due).total_seconds() // 60)} min")
    return problems


def main() -> int:
    engine = create_engine(os.environ["DATABASE_URL"])
    try:
        with Session(engine) as db:
            problems = worker_problems(db)
    finally:
        engine.dispose()
    if problems:
        print("\n".join(problems))
        return 1
    print("worker ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
