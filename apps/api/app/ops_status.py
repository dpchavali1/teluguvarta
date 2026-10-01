"""Review 2026-09-30 R3: status of the host-side operations that admin cannot
otherwise see — backups, the offsite copy, the restore drill, the monitor and
the last confirmed alert test.

The host scripts write `ops_checks` rows (`infra/deploy/ops-record.sh`); this
module turns them into a state per check. A row only proves what the script
reported: an alert test is recorded when the owner confirms the alert arrived
(`infra/deploy/ops-evidence.sh`), since nothing on the server can see that.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import OpsCheck

# check name -> (label, how old the last success may be before it is STALE).
# Cadences come from the scripts' schedules: nightly backup cron
# (deploy.sh, 03:30) plus slack, the 5-minute monitor cron plus two missed
# runs, and the monthly drill in infra/deploy/BACKUPS.md plus slack. The alert
# test has no cadence: it is shown as evidence, never STALE.
CHECKS: dict[str, tuple[str, timedelta | None]] = {
    "BACKUP": ("Nightly encrypted backup", timedelta(hours=26)),
    "OFFSITE_COPY": ("Offsite copy (Storage Box)", timedelta(hours=26)),
    "RESTORE_DRILL": ("Restore drill", timedelta(days=35)),
    "MONITOR": ("Health monitor", timedelta(minutes=15)),
    "ALERT_TEST": ("Alert test received", None),
}


@dataclass(frozen=True)
class OpsCheckStatus:
    check: str
    label: str
    # 'OK' | 'STALE' | 'FAILING' | 'NEVER'
    state: str
    last_success_at: datetime | None
    success_detail: str | None
    last_failure_at: datetime | None
    failure_detail: str | None
    max_age_seconds: int | None


def _state(row: OpsCheck | None, max_age: timedelta | None, now: datetime) -> str:
    if row is None or (row.last_success_at is None and row.last_failure_at is None):
        return "NEVER"
    if row.last_failure_at is not None and (row.last_success_at is None or row.last_failure_at > row.last_success_at):
        return "FAILING"
    if max_age is not None and row.last_success_at is not None and now - row.last_success_at > max_age:
        return "STALE"
    return "OK"


def ops_statuses(db: Session, now: datetime) -> list[OpsCheckStatus]:
    rows = {row.check_name: row for row in db.scalars(select(OpsCheck)).all()}
    result = []
    for check, (label, max_age) in CHECKS.items():
        row = rows.get(check)
        result.append(
            OpsCheckStatus(
                check=check,
                label=label,
                state=_state(row, max_age, now),
                last_success_at=row.last_success_at if row else None,
                success_detail=row.success_detail if row else None,
                last_failure_at=row.last_failure_at if row else None,
                failure_detail=row.failure_detail if row else None,
                max_age_seconds=int(max_age.total_seconds()) if max_age else None,
            )
        )
    return result
