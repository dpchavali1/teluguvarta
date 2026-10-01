"""Cost telemetry (§19) and the MONTHLY_AI_BUDGET_USD guardrail (§7.5:
crossing a configured cost threshold degrades to classification-only mode
rather than continuing to spend), plus ADR-024's MONTHLY_AI_HARD_CAP_USD,
which stops every paid call.
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.tasks import Task, cost_usd
from app.models import AiCallLog


def record_call(
    db: Session,
    *,
    task: Task,
    provider: str,
    model: str | None,
    status: str,
    tokens_in: int = 0,
    tokens_out: int = 0,
    story_id: uuid.UUID | None = None,
    tokens_thinking: int = 0,
    tokens_cached: int = 0,
) -> AiCallLog:
    row = AiCallLog(
        task=task.value,
        provider=provider,
        model=model or "",
        status=status,
        story_id=story_id,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        tokens_thinking=tokens_thinking,
        tokens_cached=tokens_cached,
        cost_usd=cost_usd(model, tokens_in, tokens_out, provider=provider),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _month_start(now: datetime) -> datetime:
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _day_start(now: datetime) -> datetime:
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def quota_day_start(now: datetime) -> datetime:
    """Start of the current provider-quota day, as a UTC instant. Google
    resets free-tier RPD at midnight Pacific, not UTC (plan §5), so a request
    counter must window on this, never on `_day_start`. Built from the
    Pacific *date*, so DST days (23h/25h) stay correct.
    """
    pacific = now.astimezone(ZoneInfo("America/Los_Angeles"))
    midnight = datetime(pacific.year, pacific.month, pacific.day, tzinfo=ZoneInfo("America/Los_Angeles"))
    return midnight.astimezone(UTC)


def today_cost_usd(db: Session, now: datetime | None = None) -> float:
    now = now or datetime.now(UTC)
    total = db.scalar(
        select(func.coalesce(func.sum(AiCallLog.cost_usd), 0)).where(AiCallLog.created_at >= _day_start(now))
    )
    return float(total or 0.0)


def month_to_date_cost_usd(db: Session, now: datetime | None = None) -> float:
    now = now or datetime.now(UTC)
    total = db.scalar(
        select(func.coalesce(func.sum(AiCallLog.cost_usd), 0)).where(AiCallLog.created_at >= _month_start(now))
    )
    return float(total or 0.0)


def is_over_monthly_budget(db: Session, now: datetime | None = None) -> bool:
    """False when MONTHLY_AI_BUDGET_USD isn't configured — there's no
    threshold to have crossed."""
    budget = os.environ.get("MONTHLY_AI_BUDGET_USD")
    if not budget:
        return False
    return month_to_date_cost_usd(db, now) >= float(budget)


def is_over_hard_cap(db: Session, now: datetime | None = None) -> bool:
    """ADR-024: at or above MONTHLY_AI_HARD_CAP_USD every paid call is
    refused, classification included. False when unset (dev/test only —
    production refuses to start without it, see `require_budget_config`)."""
    cap = os.environ.get("MONTHLY_AI_HARD_CAP_USD")
    if not cap:
        return False
    return month_to_date_cost_usd(db, now) >= float(cap)


def _env_usd(name: str) -> float | None:
    raw = os.environ.get(name)
    return float(raw) if raw else None


BudgetMode = Literal["NORMAL", "CLASSIFICATION_ONLY", "PAID_STOPPED"]


def budget_mode(month_to_date: float) -> BudgetMode:
    """Review 2026-09-30 R4: what the gateway does at this month-to-date
    spend, for admin to state. Same thresholds as `is_over_monthly_budget`
    and `is_over_hard_cap`, which are what actually gate calls:

    - NORMAL: below the monthly budget (or none set).
    - CLASSIFICATION_ONLY: budget reached, hard cap not. Summary, why-matters
      and translation stop on every provider (`DEGRADABLE_ON_BUDGET_BREACH`);
      classification and the other tasks continue, paid included.
    - PAID_STOPPED: hard cap reached. Paid calls stop too; free-tier routes
      for the non-degraded tasks can still run.

    The gates check spend before each call, so a call already in flight can
    finish past either threshold."""
    cap = _env_usd("MONTHLY_AI_HARD_CAP_USD")
    if cap is not None and month_to_date >= cap:
        return "PAID_STOPPED"
    budget = _env_usd("MONTHLY_AI_BUDGET_USD")
    if budget is not None and month_to_date >= budget:
        return "CLASSIFICATION_ONLY"
    return "NORMAL"


def reporting_windows(now: datetime) -> dict[str, datetime]:
    """Where admin's "today" and "month" start (UTC, like the budget), and
    when the Gemini free-tier quota next resets (midnight Pacific)."""
    pacific = quota_day_start(now).astimezone(ZoneInfo("America/Los_Angeles"))
    # Same-zone aware arithmetic is wall-clock, so this stays midnight across DST.
    next_reset = pacific + timedelta(days=1)
    return {
        "day_start": _day_start(now),
        "month_start": _month_start(now),
        "quota_resets_at": next_reset.astimezone(UTC),
    }


BUDGET_CONFIG_REQUIRED = ("MONTHLY_AI_BUDGET_USD", "MONTHLY_AI_HARD_CAP_USD", "DAILY_AI_ALERT_USD")


def require_budget_config() -> None:
    """ADR-024 option 5: with APP_ENV=production, refuse to start unless every
    budget variable is set to a positive number and the hard cap is at or
    above the degradation budget. An unset budget means no guardrail."""
    if os.environ.get("APP_ENV") != "production":
        return
    values: dict[str, float] = {}
    for name in BUDGET_CONFIG_REQUIRED:
        raw = os.environ.get(name, "").strip()
        try:
            values[name] = float(raw)
        except ValueError:
            raise RuntimeError(f"APP_ENV=production requires {name} to be a number (ADR-024)") from None
        if values[name] <= 0:
            raise RuntimeError(f"APP_ENV=production requires {name} > 0 (ADR-024)")
    if values["MONTHLY_AI_HARD_CAP_USD"] < values["MONTHLY_AI_BUDGET_USD"]:
        raise RuntimeError("MONTHLY_AI_HARD_CAP_USD must be at or above MONTHLY_AI_BUDGET_USD (ADR-024)")


def cost_by_task_and_day(db: Session, task: Task | None = None) -> list[dict]:
    """Queryable per-task-per-day cost breakdown, per T10's acceptance
    criteria. Returns rows sorted by day then task."""
    day = func.date(AiCallLog.created_at).label("day")
    query = select(
        AiCallLog.task,
        day,
        func.sum(AiCallLog.tokens_in).label("tokens_in"),
        func.sum(AiCallLog.tokens_out).label("tokens_out"),
        func.sum(AiCallLog.cost_usd).label("cost_usd"),
    ).group_by(AiCallLog.task, day)
    if task is not None:
        query = query.where(AiCallLog.task == task.value)
    query = query.order_by(day, AiCallLog.task)
    return [
        {
            "task": row.task,
            "day": row.day.isoformat() if hasattr(row.day, "isoformat") else str(row.day),
            "tokens_in": int(row.tokens_in or 0),
            "tokens_out": int(row.tokens_out or 0),
            "cost_usd": float(row.cost_usd or 0.0),
        }
        for row in db.execute(query)
    ]
