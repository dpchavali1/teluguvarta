"""X API cost telemetry (§19) and the optional MONTHLY_X_API_BUDGET_USD
guardrail — same pattern as `app.ai.budget`, scoped to the X
official-account adapter (X2) instead of the AI gateway.
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import XApiCallLog


def record_call(
    db: Session,
    *,
    x_account_id: uuid.UUID,
    posts_read: int,
    cost_usd: float,
    status: str,
) -> XApiCallLog:
    row = XApiCallLog(
        x_account_id=x_account_id,
        posts_read=posts_read,
        cost_usd=cost_usd,
        status=status,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def estimate_cost_usd(posts_read: int) -> float:
    """0.0 when X_API_COST_PER_POST_USD isn't configured — there's no rate
    to estimate against."""
    per_post = os.environ.get("X_API_COST_PER_POST_USD")
    if not per_post:
        return 0.0
    return posts_read * float(per_post)


def _month_start(now: datetime) -> datetime:
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def month_to_date_cost_usd(db: Session, now: datetime | None = None) -> float:
    now = now or datetime.now(UTC)
    total = db.scalar(
        select(func.coalesce(func.sum(XApiCallLog.cost_usd), 0)).where(XApiCallLog.created_at >= _month_start(now))
    )
    return float(total or 0.0)


def is_over_monthly_budget(db: Session, now: datetime | None = None) -> bool:
    """False when MONTHLY_X_API_BUDGET_USD isn't configured — there's no
    threshold to have crossed, matching `app.ai.budget.is_over_monthly_budget`."""
    budget = os.environ.get("MONTHLY_X_API_BUDGET_USD")
    if not budget:
        return False
    return month_to_date_cost_usd(db, now) >= float(budget)


def budget_remaining_usd(db: Session, now: datetime | None = None) -> float | None:
    """None when no budget is configured, matching `is_over_monthly_budget`."""
    budget = os.environ.get("MONTHLY_X_API_BUDGET_USD")
    if not budget:
        return None
    return float(budget) - month_to_date_cost_usd(db, now)
