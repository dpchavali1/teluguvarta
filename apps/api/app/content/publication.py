"""ADR-026: the minimum content a FULL story must have to publish. One
check, run at manual approve, auto-approve, final publication and
correction, so no path can publish a story the others would refuse.

BRIEF stories are left to ADR-019's own rules (`app/jobs/brief_lane.py`).
Why-matters stays optional: the owner declined rule (a).
"""

from __future__ import annotations

import difflib
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.jobs.cluster import normalized_title_key
from app.models import SourceItem, Story, StorySource, StoryVariant

SUMMARY_REPEATS_HEADLINE = "SUMMARY_REPEATS_HEADLINE"
SUMMARY_TOO_SHORT = "SUMMARY_TOO_SHORT"
HEADLINE_COPIES_SOURCE = "HEADLINE_COPIES_SOURCE"

# Rule (b): at or above this, the summary just restates the headline.
SUMMARY_HEADLINE_SIMILARITY_LIMIT = 0.8
# Rule (c): a summary passes with either this many sentences or words.
MIN_SUMMARY_SENTENCES = 2
MIN_SUMMARY_WORDS = 25
# Rule (d): the same 0.6 threshold generation uses for summary vs source
# title (`app/jobs/generate.py::SUMMARY_SIMILARITY_FLAG_THRESHOLD`).
HEADLINE_SOURCE_SIMILARITY_LIMIT = 0.6

_SENTENCE_END_RE = re.compile(r"[.!?]+(?:\s+|$)")


def _similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, normalized_title_key(a), normalized_title_key(b)).ratio()


def _sentence_count(text: str) -> int:
    return len([part for part in _SENTENCE_END_RE.split(text.strip()) if part.strip()])


def content_rule_failures(headline: str, summary: str, source_titles: list[str]) -> list[str]:
    """The ADR-026 rules a FULL story's English text fails, in rule order."""
    failures = []
    if _similarity(headline, summary) >= SUMMARY_HEADLINE_SIMILARITY_LIMIT:
        failures.append(SUMMARY_REPEATS_HEADLINE)
    if _sentence_count(summary) < MIN_SUMMARY_SENTENCES and len(summary.split()) < MIN_SUMMARY_WORDS:
        failures.append(SUMMARY_TOO_SHORT)
    if any(
        normalized_title_key(title) and _similarity(headline, title) >= HEADLINE_SOURCE_SIMILARITY_LIMIT
        for title in source_titles
    ):
        failures.append(HEADLINE_COPIES_SOURCE)
    return failures


def validate_for_publication(db: Session, story: Story) -> list[str]:
    """Empty when the story may publish. A missing English draft is the
    caller's own NO_ENGLISH_DRAFT check, so it isn't repeated here."""
    if story.format != "FULL":
        return []
    en = db.scalars(
        select(StoryVariant).where(StoryVariant.story_id == story.id, StoryVariant.language == "en")
    ).first()
    if en is None:
        return []
    titles = db.scalars(
        select(SourceItem.title)
        .join(StorySource, StorySource.source_item_id == SourceItem.id)
        .where(StorySource.story_id == story.id)
    ).all()
    return content_rule_failures(en.headline, en.summary, [t for t in titles if t])
