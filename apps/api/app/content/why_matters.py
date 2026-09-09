"""§8.3: "why this matters" generated once per (story, audience segment),
then cached — never a fresh AI-gateway call per feed request (T16/ADR-005).
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.contracts import WhyMattersResult
from app.ai.gateway import AiGateway, GatewayStatus
from app.ai.tasks import Task
from app.models import Story, StoryVariant, StoryWhyMattersCache

SEGMENTS = (
    "general",
    "international_student",
    "graduate_opt",
    "professional",
    "family_parent",
    "other",
)

_SEGMENT_LABELS: dict[str, str] = {
    "general": "a general reader",
    "international_student": "an international student in the US",
    "graduate_opt": "someone on OPT after graduate study",
    "professional": "a working professional",
    "family_parent": "a parent or family member of someone abroad",
    "other": "a general reader",
}


def _prompt(en: StoryVariant, segment: str) -> str:
    label = _SEGMENT_LABELS.get(segment, _SEGMENT_LABELS["general"])
    return (
        f"Headline: {en.headline}\nSummary: {en.summary}\n\n"
        f"In one or two sentences, explain why this specifically matters to {label}."
    )


def get_or_generate(db: Session, story: Story, segment: str) -> str | None:
    """Returns the cached/generated "why this matters" for this
    (story, segment), or None if it isn't cached and generation didn't
    succeed (e.g. `UNAVAILABLE`/`HOLD`) — callers fall back to the story's
    generic `why_matters` in that case, never blocking the response."""

    if segment not in SEGMENTS:
        segment = "general"

    cached = db.scalars(
        select(StoryWhyMattersCache).where(
            StoryWhyMattersCache.story_id == story.id, StoryWhyMattersCache.segment == segment
        )
    ).first()
    if cached is not None:
        return cached.why_matters

    en = db.scalars(
        select(StoryVariant).where(StoryVariant.story_id == story.id, StoryVariant.language == "en")
    ).first()
    if en is None:
        return None

    gateway = AiGateway(db)
    outcome = gateway.run_task(
        Task.WHY_MATTERS, _prompt(en, segment), story_id=story.id, result_model=WhyMattersResult
    )
    if outcome.status != GatewayStatus.OK or outcome.result is None:
        return None

    result: WhyMattersResult = outcome.result  # type: ignore[assignment]
    row = StoryWhyMattersCache(
        id=uuid.uuid4(), story_id=story.id, segment=segment,
        why_matters=result.why_matters, model_version=Task.WHY_MATTERS.value,
    )
    db.add(row)
    db.commit()
    return row.why_matters
