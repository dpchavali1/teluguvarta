"""Minimal alert dispatch (T18). One pluggable channel — default logs at
ERROR and, if `ALERT_WEBHOOK_URL` is set, POSTs a `{"text": message}` body
to it (works as-is against a Slack/generic incoming webhook; no new
infrastructure). Threshold checks below call `send_alert` when they detect
a crossing; they're called from the worker loop (see `app/jobs/worker.py`)
and are also directly unit-testable by passing a fake channel.
"""

from __future__ import annotations

import os
import threading
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.budget import (
    is_over_hard_cap,
    is_over_monthly_budget,
    month_to_date_cost_usd,
    today_cost_usd,
)
from app.jobs.source_fetch import CIRCUIT_BREAKER_THRESHOLD
from app.models import AiCallLog, Job, Source
from app.observability.logging import get_logger

logger = get_logger("alerts")

# Recent-attempts window + failure-rate threshold that counts as a job
# error-rate alert. Deliberately simple (not a full rolling SLO) — enough
# to surface "the queue is on fire" per the ticket's acceptance criteria.
JOB_ERROR_RATE_WINDOW = timedelta(hours=1)
JOB_ERROR_RATE_THRESHOLD = 0.5
JOB_ERROR_RATE_MIN_SAMPLES = 5
AI_REFUSAL_WINDOW = timedelta(hours=1)


def default_channel(severity: str, message: str) -> None:
    logger.error("ALERT [%s] %s", severity, message)
    webhook_url = os.environ.get("ALERT_WEBHOOK_URL")
    if not webhook_url:
        return

    def _deliver() -> None:
        try:
            httpx.post(webhook_url, json={"text": f"[{severity}] {message}"}, timeout=5.0)
        except httpx.HTTPError:
            logger.warning("failed to deliver alert to webhook")

    # Fire-and-forget: `check_all` can fire up to three of these in a row
    # from the worker's poll loop, and a slow/unreachable webhook must
    # never delay claiming the next job.
    threading.Thread(target=_deliver, daemon=True).start()


def send_alert(message: str, *, severity: str = "ERROR", channel=None) -> None:
    (channel or default_channel)(severity, message)


def check_budget_alerts(db: Session, *, now: datetime | None = None, channel=None) -> list[str]:
    """Fires when MONTHLY_AI_BUDGET_USD, MONTHLY_AI_HARD_CAP_USD or DAILY_AI_ALERT_USD is crossed.
    Returns the list of thresholds that fired, for tests/callers."""
    now = now or datetime.now(UTC)
    fired: list[str] = []

    if is_over_monthly_budget(db, now):
        mtd = month_to_date_cost_usd(db, now)
        budget = os.environ.get("MONTHLY_AI_BUDGET_USD")
        send_alert(f"AI spend ${mtd:.2f} has crossed the monthly budget of ${budget}", channel=channel)
        fired.append("MONTHLY_AI_BUDGET_USD")

    if is_over_hard_cap(db, now):
        mtd = month_to_date_cost_usd(db, now)
        cap = os.environ.get("MONTHLY_AI_HARD_CAP_USD")
        send_alert(f"AI spend ${mtd:.2f} has reached the monthly hard cap of ${cap}; all paid AI calls are stopped", channel=channel)
        fired.append("MONTHLY_AI_HARD_CAP_USD")

    daily_limit = os.environ.get("DAILY_AI_ALERT_USD")
    if daily_limit:
        today_cost = today_cost_usd(db, now)
        if today_cost >= float(daily_limit):
            send_alert(f"AI spend today ${today_cost:.2f} has crossed the daily alert threshold of ${daily_limit}", channel=channel)
            fired.append("DAILY_AI_ALERT_USD")

    return fired


def check_circuit_breaker_alerts(db: Session, *, channel=None) -> list[str]:
    """Fires once per currently-tripped source (fail_count over T08's
    circuit-breaker threshold — reusing that constant rather than defining
    a second one)."""
    tripped = db.scalars(select(Source).where(Source.fail_count >= CIRCUIT_BREAKER_THRESHOLD)).all()
    fired = []
    for source in tripped:
        send_alert(
            f"Source '{source.name}' ({source.id}) has tripped its circuit breaker "
            f"({source.fail_count} consecutive failures)",
            channel=channel,
        )
        fired.append(f"CIRCUIT_BREAKER:{source.id}")
    return fired


def check_job_error_rate_alert(db: Session, *, now: datetime | None = None, channel=None) -> list[str]:
    """Fires when the fraction of recently-completed jobs (DONE or FAILED,
    claimed within JOB_ERROR_RATE_WINDOW per `locked_at` — `run_after` isn't
    updated on terminal completion, so it can't stand in for "recently
    finished") that ended FAILED crosses JOB_ERROR_RATE_THRESHOLD — skipped
    below JOB_ERROR_RATE_MIN_SAMPLES so a couple of unlucky jobs right after
    startup don't page anyone."""
    now = now or datetime.now(UTC)
    window_start = now - JOB_ERROR_RATE_WINDOW
    rows = db.execute(
        select(Job.status, func.count()).where(Job.status.in_(["DONE", "FAILED"]), Job.locked_at >= window_start).group_by(Job.status)
    ).all()
    counts = {status: count for status, count in rows}
    total = sum(counts.values())
    if total < JOB_ERROR_RATE_MIN_SAMPLES:
        return []
    failure_rate = counts.get("FAILED", 0) / total
    if failure_rate < JOB_ERROR_RATE_THRESHOLD:
        return []
    send_alert(
        f"Job failure rate {failure_rate:.0%} over the last {JOB_ERROR_RATE_WINDOW} "
        f"({counts.get('FAILED', 0)}/{total}) has crossed {JOB_ERROR_RATE_THRESHOLD:.0%}",
        channel=channel,
    )
    return ["JOB_ERROR_RATE"]


def check_ai_model_refusal_alerts(db: Session, *, now: datetime | None = None, channel=None) -> list[str]:
    """Fires once per provider/model the gateway refused as misconfigured
    within AI_REFUSAL_WINDOW: a free-tier model with no FREE_TIER_LIMITS entry
    (ADR-015) or an unpriced/alias paid model (ADR-018). Only those refusals
    are recorded as UNAVAILABLE, and stories wait on them indefinitely."""
    now = now or datetime.now(UTC)
    rows = db.execute(
        select(AiCallLog.provider, AiCallLog.model, func.count())
        .where(AiCallLog.status == "UNAVAILABLE", AiCallLog.created_at >= now - AI_REFUSAL_WINDOW)
        .group_by(AiCallLog.provider, AiCallLog.model)
    ).all()
    fired = []
    for provider, model, count in rows:
        send_alert(
            f"AI gateway refused {count} call(s) to {provider} model '{model}' in the last "
            f"{AI_REFUSAL_WINDOW}: no quota limits or pricing configured for it",
            channel=channel,
        )
        fired.append(f"AI_MODEL_REFUSED:{provider}:{model}")
    return fired


def check_all(db: Session, *, now: datetime | None = None, channel=None) -> list[str]:
    fired: list[str] = []
    fired += check_budget_alerts(db, now=now, channel=channel)
    fired += check_circuit_breaker_alerts(db, channel=channel)
    fired += check_job_error_rate_alert(db, now=now, channel=channel)
    fired += check_ai_model_refusal_alerts(db, now=now, channel=channel)
    return fired
