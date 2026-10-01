"""Review 2026-09-30 R5: where stories are in the editorial pipeline, and how
long the oldest has waited at each stage that records a start time. Stories
carry no created_at, so DRAFT/AI_READY counts have no age."""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import exists, func, select
from sqlalchemy.orm import Session

from app.models import AiWorkState, ReviewTask, Story, StoryVariant

# Readers see English for these until a PASSED Telugu variant exists.
LIVE_STATUSES = ("PUBLISHED", "UPDATED")


def pipeline_status(db: Session, now: datetime) -> dict:
    stories_by_status = {status: int(count) for status, count in db.execute(
        select(Story.status, func.count()).group_by(Story.status)
    )}

    published_24h = db.scalar(select(func.count()).where(Story.published_at >= now - timedelta(hours=24)))

    # Same rows as GET /v1/admin/review-queue.
    review_count, review_oldest = db.execute(
        select(func.count(), func.min(ReviewTask.created_at)).where(ReviewTask.status == "PENDING")
    ).one()

    ai_work = []
    for stage in ("GENERATE", "TRANSLATE"):
        exhausted = AiWorkState.failure_class == "EXHAUSTED"
        retrying, exhausted_count, oldest = db.execute(
            select(
                func.count().filter(~exhausted | AiWorkState.failure_class.is_(None)),
                func.count().filter(exhausted),
                func.min(AiWorkState.updated_at),
            ).where(AiWorkState.stage == stage)
        ).one()
        ai_work.append({"stage": stage, "retrying": int(retrying), "exhausted": int(exhausted_count), "oldest_update_at": oldest})

    te_passed = exists().where(
        StoryVariant.story_id == Story.id, StoryVariant.language == "te", StoryVariant.qa_status == "PASSED"
    )
    te_failed = exists().where(
        StoryVariant.story_id == Story.id, StoryVariant.language == "te", StoryVariant.qa_status == "FAILED"
    )
    english_only = (Story.status.in_(LIVE_STATUSES), ~te_passed)
    te_count, te_oldest = db.execute(select(func.count(), func.min(Story.published_at)).where(*english_only)).one()
    te_failed_count = db.scalar(select(func.count()).where(*english_only, te_failed))

    return {
        "stories_by_status": stories_by_status,
        "published_24h": int(published_24h or 0),
        "review_pending": int(review_count),
        "review_oldest_at": review_oldest,
        "ai_work": ai_work,
        "telugu_missing": int(te_count),
        "telugu_failed_qa": int(te_failed_count or 0),
        "telugu_missing_oldest_published_at": te_oldest,
    }
