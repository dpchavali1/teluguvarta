"""Cost telemetry (§19) and the MONTHLY_AI_BUDGET_USD guardrail (§7.5:
crossing a configured cost threshold degrades to classification-only mode
rather than continuing to spend).
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime

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
) -> AiCallLog:
    row = AiCallLog(
        task=task.value,
        provider=provider,
        model=model or "",
        status=status,
        story_id=story_id,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cost_usd=cost_usd(model, tokens_in, tokens_out),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _month_start(now: datetime) -> datetime:
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _day_start(now: datetime) -> datetime:
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


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
