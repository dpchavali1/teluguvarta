"""Bounded background preparation of non-sensitive segment explanations.

Uses the existing ai_summarize job type and ADR-003 retry/deduplication.
Sensitive stories always retain their human-reviewed generic explanation.
"""
import os
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.content.why_matters import (
    SEGMENTS,
    content_version,
    generation_segment,
    get_or_generate,
)
from app.jobs.queue import enqueue_job
from app.models import Job, Story, StoryVariant

# Review 2026-09-29 #13: anonymous home requests choose the segment and, via
# their preferences, which stories rank; each (story, segment, version) is
# queued at most once, but that is still a paid call per combination. This
# caps how many are queued per rolling 24 h; past it, readers keep the
# approved generic explanation. Concurrent requests can pass the count
# together, so the cap can be exceeded by a few.
DAILY_JOB_CAP_ENV = "WHY_MATTERS_DAILY_JOB_CAP"
DEFAULT_DAILY_JOB_CAP = 50
_DEDUPE_PREFIX = "why:"


def daily_job_cap() -> int:
    try:
        return max(0, int(os.environ.get(DAILY_JOB_CAP_ENV, DEFAULT_DAILY_JOB_CAP)))
    except ValueError:
        return DEFAULT_DAILY_JOB_CAP


def _queued_last_day(db: Session) -> int:
    # `run_after` is the enqueue time: these jobs are never scheduled ahead.
    since = datetime.now(UTC) - timedelta(days=1)
    return db.scalar(select(func.count()).select_from(Job).where(
        Job.type == "ai_summarize", Job.dedupe_key.startswith(_DEDUPE_PREFIX), Job.run_after >= since,
    )) or 0


def enqueue_why_matters(db: Session, misses: list[tuple[Story, StoryVariant]], segment: str) -> None:
    """Queues generation for stories with no cached explanation, in order,
    until the daily cap is reached."""
    if segment not in SEGMENTS:
        return
    segment = generation_segment(segment)
    eligible = [(s, en) for s, en in misses if s.sensitivity == "NONE" and s.status in ("PUBLISHED", "UPDATED")]
    if not eligible:
        return
    remaining = daily_job_cap() - _queued_last_day(db)
    for story, en in eligible:
        if remaining <= 0:
            return
        version = content_version(en)
        if enqueue_job(db, "ai_summarize", {"story_id": str(story.id), "segment": segment, "version": version},
                       dedupe_key=f"{_DEDUPE_PREFIX}{story.id}:{segment}:{version}") is not None:
            remaining -= 1


def run_why_matters(db: Session, job: Job) -> None:
    story = db.get(Story, UUID(job.payload["story_id"]))
    if story is None or story.sensitivity != "NONE" or story.status not in ("PUBLISHED", "UPDATED"):
        return
    segment = job.payload["segment"]
    if segment not in SEGMENTS:
        return
    en = db.scalar(select(StoryVariant).where(StoryVariant.story_id == story.id, StoryVariant.language == "en"))
    if en is None or content_version(en) != job.payload["version"]:
        return  # An obsolete job cannot regenerate against a correction.
    if get_or_generate(db, story, segment) is None:
        raise RuntimeError("Segment explanation unavailable; generic approved text remains visible")
