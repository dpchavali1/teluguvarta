"""Review 2026-09-30 R5: where AI money goes over a bounded date range.

Everything is aggregated from `ai_call_log` (one row per call attempt) in UTC
days, like the budget. Costs are the same token-price estimates the budget
uses. Two figures are kept deliberately apart: spend *in the window* (by
call time) and the *lifecycle* cost of stories published in the window (all
their calls, whenever made). Dividing one by the other would not be a unit
cost, so the report never does.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models import AiCallLog, Story, StoryVariant

MAX_RANGE_DAYS = 93
TOP_STORIES = 15
# Outcomes whose output was used. Every other billed outcome (HOLD,
# PARSE_ERROR, BLOCKED, ...) paid for nothing usable.
USABLE_STATUSES = ("SUCCESS", "RETRY_SUCCESS")
# `gateway._call`'s second, constrained attempt after an unusable first reply.
RETRY_STATUS = "RETRY_SUCCESS"
# ADR-018: the free-tier route; "none" is the null provider (no call made).
UNBILLED_PROVIDERS = {"gemini": "FREE", "none": "NONE"}


def window(start: date, end: date) -> tuple[datetime, datetime]:
    """[start 00:00 UTC, the day after end 00:00 UTC)."""
    return datetime.combine(start, time(), UTC), datetime.combine(end + timedelta(days=1), time(), UTC)


def _sums():
    return (
        func.count().label("calls"),
        func.coalesce(func.sum(AiCallLog.cost_usd), 0).label("cost"),
        func.coalesce(func.sum(AiCallLog.tokens_in), 0).label("tokens_in"),
        func.coalesce(func.sum(AiCallLog.tokens_out), 0).label("tokens_out"),
        func.coalesce(func.sum(AiCallLog.tokens_thinking), 0).label("tokens_thinking"),
        func.coalesce(func.sum(AiCallLog.tokens_cached), 0).label("tokens_cached"),
        func.coalesce(func.sum(case((AiCallLog.status.in_(USABLE_STATUSES), 0), else_=1)), 0).label("unusable_calls"),
        func.coalesce(
            func.sum(case((AiCallLog.status.in_(USABLE_STATUSES), 0), else_=AiCallLog.cost_usd)), 0
        ).label("unusable_cost"),
    )


def _figures(row) -> dict:
    return {
        "calls": int(row.calls),
        "cost_usd": float(row.cost),
        "tokens_in": int(row.tokens_in),
        "tokens_out": int(row.tokens_out),
        "tokens_thinking": int(row.tokens_thinking),
        "tokens_cached": int(row.tokens_cached),
        "unusable_calls": int(row.unusable_calls),
        "unusable_cost_usd": float(row.unusable_cost),
    }


def cost_report(db: Session, start: date, end: date) -> dict:
    lo, hi = window(start, end)
    in_window = (AiCallLog.created_at >= lo, AiCallLog.created_at < hi)

    totals = _figures(db.execute(select(*_sums()).where(*in_window)).one())
    retry_cost = db.scalar(
        select(func.coalesce(func.sum(AiCallLog.cost_usd), 0)).where(*in_window, AiCallLog.status == RETRY_STATUS)
    )
    totals["retry_cost_usd"] = float(retry_cost or 0)

    day = func.date(func.timezone("UTC", AiCallLog.created_at)).label("day")
    per_day = {
        row.day: row for row in db.execute(select(day, *_sums()).where(*in_window).group_by(day))
    }
    by_day = []
    current = start
    while current <= end:
        row = per_day.get(current)
        by_day.append({"day": current.isoformat(), **(_figures(row) if row else _figures(_ZERO))})
        current += timedelta(days=1)

    breakdown = [
        {
            "provider": row.provider,
            "model": row.model,
            "task": row.task,
            "tier": UNBILLED_PROVIDERS.get(row.provider, "PAID"),
            **_figures(row),
        }
        for row in db.execute(
            select(AiCallLog.provider, AiCallLog.model, AiCallLog.task, *_sums())
            .where(*in_window)
            .group_by(AiCallLog.provider, AiCallLog.model, AiCallLog.task)
            .order_by(func.sum(AiCallLog.cost_usd).desc(), AiCallLog.task)
        )
    ]

    outcomes = [
        {"status": row.status, "calls": int(row.calls), "cost_usd": float(row.cost)}
        for row in db.execute(
            select(AiCallLog.status, func.count().label("calls"), func.coalesce(func.sum(AiCallLog.cost_usd), 0).label("cost"))
            .where(*in_window)
            .group_by(AiCallLog.status)
            .order_by(func.count().desc())
        )
    ]

    unlinked = _figures(db.execute(select(*_sums()).where(*in_window, AiCallLog.story_id.is_(None))).one())

    # Linked spend in the window, by where each story stands now.
    by_story_status = [
        {"status": row.status, "stories": int(row.stories), "calls": int(row.calls), "cost_usd": float(row.cost)}
        for row in db.execute(
            select(
                Story.status,
                func.count(func.distinct(Story.id)).label("stories"),
                func.count().label("calls"),
                func.coalesce(func.sum(AiCallLog.cost_usd), 0).label("cost"),
            )
            .join(Story, Story.id == AiCallLog.story_id)
            .where(*in_window)
            .group_by(Story.status)
            .order_by(func.sum(AiCallLog.cost_usd).desc())
        )
    ]

    # Publication cohort: stories first published in the window, and every
    # call ever linked to them.
    cohort = select(Story.id).where(Story.published_at >= lo, Story.published_at < hi)
    published = db.scalar(select(func.count()).select_from(cohort.subquery()))
    cohort_row = db.execute(
        select(func.count().label("calls"), func.coalesce(func.sum(AiCallLog.cost_usd), 0).label("cost")).where(
            AiCallLog.story_id.in_(cohort)
        )
    ).one()

    headline = (
        select(StoryVariant.headline)
        .where(StoryVariant.story_id == Story.id, StoryVariant.language == "en")
        .limit(1)
        .scalar_subquery()
    )
    top_stories = [
        {
            "story_id": row.id,
            "headline": row.headline,
            "status": row.status,
            "calls": int(row.calls),
            "unusable_calls": int(row.unusable_calls),
            "cost_usd": float(row.cost),
        }
        for row in db.execute(
            select(
                Story.id,
                Story.status,
                headline.label("headline"),
                func.count().label("calls"),
                func.coalesce(func.sum(case((AiCallLog.status.in_(USABLE_STATUSES), 0), else_=1)), 0).label(
                    "unusable_calls"
                ),
                func.coalesce(func.sum(AiCallLog.cost_usd), 0).label("cost"),
            )
            .join(Story, Story.id == AiCallLog.story_id)
            .where(*in_window)
            .group_by(Story.id, Story.status)
            .order_by(func.sum(AiCallLog.cost_usd).desc(), func.count().desc())
            .limit(TOP_STORIES)
        )
    ]

    return {
        "start": start,
        "end": end,
        "window_start": lo,
        "window_end": hi,
        "totals": totals,
        "by_day": by_day,
        "breakdown": breakdown,
        "outcomes": outcomes,
        "unlinked": unlinked,
        "by_story_status": by_story_status,
        "publication_cohort": {
            "stories_published": int(published or 0),
            "lifecycle_calls": int(cohort_row.calls),
            "lifecycle_cost_usd": float(cohort_row.cost),
        },
        "top_stories": top_stories,
    }


class _Zero:
    calls = cost = tokens_in = tokens_out = tokens_thinking = tokens_cached = unusable_calls = unusable_cost = 0


_ZERO = _Zero()
