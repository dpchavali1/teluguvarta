"""Bounded background preparation of non-sensitive segment explanations.

Uses the existing ai_summarize job type and ADR-003 retry/deduplication.
Sensitive stories always retain their human-reviewed generic explanation.
"""
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.content.why_matters import SEGMENTS, content_version, get_or_generate
from app.jobs.queue import enqueue_job
from app.models import Job, Story, StoryVariant


def enqueue_why_matters(db: Session, story: Story, en: StoryVariant, segment: str) -> None:
    if story.sensitivity != "NONE" or story.status not in ("PUBLISHED", "UPDATED") or segment not in SEGMENTS:
        return
    version = content_version(en)
    enqueue_job(db, "ai_summarize", {"story_id": str(story.id), "segment": segment, "version": version},
                dedupe_key=f"why:{story.id}:{segment}:{version}")


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
