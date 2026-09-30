"""ADR-027 importance: how much a story matters, separate from how sure the
model was (`Story.classification_confidence`). Deterministic, no model call,
so ranking stays out of the LLM; an editor's override takes precedence.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import SourceItem, Story, StorySource, StoryTopic, Topic

BASE = 0.4
URGENT_BONUS = 0.2
PER_EXTRA_SOURCE = 0.1
MAX_EXTRA_SOURCES = 3
PRIORITY_TOPIC_BONUS = 0.1

# Immigration plus the student topics (infra/scripts/seed.py). The migration
# `d1a6e4f8b3c5` backfilled with this list; keep them in step if it changes.
AUDIENCE_PRIORITY_TOPIC_SLUGS: frozenset[str] = frozenset({
    "immigration", "cpt", "opt", "stem-opt", "internships", "university-policy",
    "campus-safety", "scholarships", "student-community", "international-student-jobs",
})

OVERRIDE_VALUES: dict[str, float] = {"LOW": 0.2, "NORMAL": 0.5, "HIGH": 0.8}


def compute_importance(*, urgent: bool, independent_sources: int, priority_topic: bool) -> float:
    extra = min(MAX_EXTRA_SOURCES, max(0, independent_sources - 1))
    score = (
        BASE
        + (URGENT_BONUS if urgent else 0.0)
        + PER_EXTRA_SOURCE * extra
        + (PRIORITY_TOPIC_BONUS if priority_topic else 0.0)
    )
    return round(min(1.0, score), 4)


def recompute_importance(db: Session, story: Story) -> None:
    """Call after anything the score depends on changes: generation, a new
    source joining the story, topics, or the editor's override."""
    if story.importance_override in OVERRIDE_VALUES:
        story.importance = OVERRIDE_VALUES[story.importance_override]
        return
    db.flush()
    sources = db.scalar(
        select(func.count(func.distinct(SourceItem.source_id)))
        .join(StorySource, StorySource.source_item_id == SourceItem.id)
        .where(StorySource.story_id == story.id)
    ) or 0
    priority = db.scalar(
        select(StoryTopic.story_id).join(Topic, Topic.id == StoryTopic.topic_id)
        .where(StoryTopic.story_id == story.id, Topic.slug.in_(AUDIENCE_PRIORITY_TOPIC_SLUGS)).limit(1)
    ) is not None
    story.importance = compute_importance(
        urgent=story.urgency == "HIGH", independent_sources=sources, priority_topic=priority,
    )
