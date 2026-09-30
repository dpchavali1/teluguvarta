"""ADR-019: the auto-publish lane for link-first briefs.

`publish.auto_publish_stories` calls `try_brief_lane` for a clean `AI_READY`
story that would otherwise go to review only because `AUTO_PUBLISH_GLOBAL` is
off. The lane publishes without review only when the story is small enough to
check deterministically against the source title: an original headline, one
sentence of at most 30 words limited to facts in the cited titles, and the
source link. Everything that fails a check goes to the review queue with the
full draft left intact.

The lane closes (returns `NOT_ATTEMPTED`, so the caller files the usual
`AUTO_PUBLISH_DISABLED` review task) when `AUTO_PUBLISH_BRIEFS` is off, when
the P1 review flag is off (urgency is not persisted, so the P1 route is the
only thing keeping HIGH-urgency stories out of `AI_READY`), or when the story
fails an eligibility rule in ADR-019 section 2.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from zoneinfo import ZoneInfo

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.ai import AiGateway, GatewayStatus, Task
from app.ai.contracts import BriefResult
from app.jobs.generate import (
    P1_REVIEW_ENV_VAR,
    _env_flag,
    _evidence_block,
    _evidence_item_ids,
    _story_items,
    _summary_too_similar_to_source,
    _untrusted_data_block,
)
from app.models import AuditEvent, Source, SourceItem, Story, StoryVariant

AUTO_PUBLISH_BRIEFS_ENV = "AUTO_PUBLISH_BRIEFS"
AUTO_PUBLISH_BRIEFS_DAILY_CAP_ENV = "AUTO_PUBLISH_BRIEFS_DAILY_CAP"
DEFAULT_DAILY_CAP = 20
CAP_TIMEZONE = ZoneInfo("America/New_York")

BRIEF_ACTOR = "system:brief_lane"
BRIEF_AUDIT_REASON = "BRIEF_LANE"
BRIEF_MODEL_VERSION = "brief"

MIN_CONFIDENCE = 0.8
MAX_WORDS = 30

# NON_NEGOTIABLES #5: a source configured in one of these categories never
# qualifies, whatever the AI classified the story as.
ALWAYS_REVIEWED_SOURCE_CATEGORIES = frozenset({"immigration", "legal", "financial", "breaking"})

# A causal link the title doesn't state is an added fact.
_CAUSAL_WORDS = frozenset({"because", "after", "due", "since", "following", "amid", "caused", "causes"})

# Capitalized words that carry no fact of their own (sentence starts, articles).
_STOP_WORDS = frozenset({
    "a", "an", "the", "this", "that", "these", "those", "it", "its", "in", "on", "at", "of", "for",
    "to", "from", "by", "with", "and", "or", "but", "as", "is", "are", "was", "were", "be", "has",
    "have", "had", "will", "new", "officials", "authorities",
})

# A negation the titles don't carry reverses a fact; one they carry and the
# text drops reverses it the other way.
_NEGATION_WORDS = frozenset({"not", "no", "never", "without", "nor", "neither", "none", "cannot"})

_TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9'’.,/-]*")
_SENTENCE_BREAK_RE = re.compile(r"[.!?]\s+\S")


class LaneOutcome(str, Enum):
    NOT_ATTEMPTED = "NOT_ATTEMPTED"
    PUBLISHED = "PUBLISHED"
    DAILY_CAP = "BRIEF_DAILY_CAP"
    TITLE_MISMATCH = "BRIEF_TITLE_MISMATCH"
    REJECTED = "BRIEF_REJECTED"


@dataclass
class TitleMatch:
    ok: bool
    matched: list[str] = field(default_factory=list)
    unmatched: list[str] = field(default_factory=list)


def briefs_enabled() -> bool:
    return os.environ.get(AUTO_PUBLISH_BRIEFS_ENV, "false").strip().lower() == "true"


def daily_cap() -> int:
    try:
        return max(0, int(os.environ.get(AUTO_PUBLISH_BRIEFS_DAILY_CAP_ENV, DEFAULT_DAILY_CAP)))
    except ValueError:
        return DEFAULT_DAILY_CAP


def cap_day_start(now: datetime) -> datetime:
    local = now.astimezone(CAP_TIMEZONE)
    return datetime(local.year, local.month, local.day, tzinfo=CAP_TIMEZONE).astimezone(UTC)


def published_today(db: Session, now: datetime) -> int:
    return db.scalar(
        select(func.count(AuditEvent.id)).where(
            AuditEvent.actor == BRIEF_ACTOR,
            AuditEvent.action == "STORY_AUTO_APPROVED",
            AuditEvent.created_at >= cap_day_start(now),
        )
    ) or 0


def _normalize(token: str) -> str:
    return token.lower().strip(".,'’").replace(",", "")


def _tokens(text: str) -> list[str]:
    return [t.strip(".,") for t in _TOKEN_RE.findall(text or "") if t.strip(".,")]


def _is_negation(key: str) -> bool:
    return key in _NEGATION_WORDS or key.endswith(("n't", "n’t"))


def _has_negation(text: str) -> bool:
    return any(_is_negation(_normalize(t)) for t in _tokens(text))


def _order_inversions(checked_keys: list[str], titles: list[str]) -> list[str]:
    """Adjacent checked tokens that `text` puts in the opposite order from a
    single title: "Smith sues Jones" -> "Jones sues Smith", "from 5 to 10" ->
    "from 10 to 5". A legitimate passive rewrite trips this too; that goes to
    review, which is the safe side."""
    inversions: list[str] = []
    for title in titles:
        positions: dict[str, int] = {}
        for index, token in enumerate(_tokens(title)):
            positions.setdefault(_normalize(token), index)
        seen = [positions[k] for k in dict.fromkeys(checked_keys) if k in positions]
        ordered = [k for k in dict.fromkeys(checked_keys) if k in positions]
        for i in range(len(seen) - 1):
            if seen[i] > seen[i + 1]:
                inversions.append(f"ORDER:{ordered[i]}>{ordered[i + 1]}")
    return inversions


def title_match(text: str, titles: list[str], *, order: str = "all") -> TitleMatch:
    """Every number/date token and every capitalized non-stop-word in `text`
    must appear in one of `titles`, and a causal word may appear only if a
    title uses it. Catches added facts, not dropped qualifiers (ADR-019).
    Review 2026-09-29 #4 adds two guards: negation must be present in `text`
    exactly when a title has it, and checked tokens that share a title must
    keep that title's order (`order="numbers"` limits that to numbers, for
    headlines, which reorder freely). Still lexical: it can't prove
    entailment."""
    title_words = {_normalize(t) for title in titles for t in _tokens(title)}
    matched: list[str] = []
    unmatched: list[str] = []
    checked_keys: list[str] = []
    for token in _tokens(text):
        key = _normalize(token)
        if not key:
            continue
        checked = (
            any(ch.isdigit() for ch in token)
            or (token[0].isupper() and key not in _STOP_WORDS)
            or key in _CAUSAL_WORDS
        )
        if not checked:
            continue
        checked_keys.append(key)
        (matched if key in title_words else unmatched).append(token)
    if _has_negation(text) != any(_has_negation(title) for title in titles):
        unmatched.append("NEGATION")
    if order == "numbers":
        checked_keys = [k for k in checked_keys if any(ch.isdigit() for ch in k)]
    unmatched += _order_inversions(checked_keys, titles)
    return TitleMatch(ok=not unmatched, matched=matched, unmatched=unmatched)


def is_single_sentence(text: str) -> bool:
    return not _SENTENCE_BREAK_RE.search(text.strip())


def _ineligible(db: Session, story: Story, items: list[SourceItem]) -> str | None:
    """ADR-019 section 2 rules checked before any AI call. `None` = eligible."""
    if not items:
        return "no source items"
    if story.sensitivity != "NONE":
        return "sensitivity"
    if story.privacy_decision == "RESTRICTED":
        return "restricted signal"
    if story.importance < MIN_CONFIDENCE:  # generate stores classification confidence here
        return "classification confidence"
    for item in items:
        source = db.get(Source, item.source_id)
        if source is None or source.rights_status != "LINK_ONLY":
            return "rights status"
        if source.rights_reviewed_at is None or not source.rights_evidence_url:
            return "rights not reviewed"
        if (source.category or "").strip().lower() in ALWAYS_REVIEWED_SOURCE_CATEGORIES:
            return "source category"
    return None


def _brief_prompt(items: list[SourceItem]) -> str:
    return (
        "Write a link-first news brief for this story cluster: an original "
        "headline (never the source's own headline wording) and ONE sentence "
        f"of at most {MAX_WORDS} words. The sentence may state only facts that "
        "appear in the evidence titles below: no added names, numbers, dates, "
        "causes, or context. List each factual claim with the source_ref(s) "
        "whose title states it. Give a confidence from 0 to 1 that the "
        "sentence adds nothing beyond the titles. Evidence items:\n"
        + _untrusted_data_block(_evidence_block(items, include_description=False))
    )


def _check_brief(brief: BriefResult, items: list[SourceItem], evidence_ids: frozenset[str]) -> tuple[LaneOutcome | None, TitleMatch | None]:
    if brief.confidence < MIN_CONFIDENCE:
        return LaneOutcome.REJECTED, None
    text = brief.brief_en.strip()
    headline = brief.headline_en.strip()
    if not text or not headline or len(text.split()) > MAX_WORDS or not is_single_sentence(text):
        return LaneOutcome.REJECTED, None
    if _summary_too_similar_to_source(headline, items):
        return LaneOutcome.REJECTED, None
    if not brief.claims or any(not c.source_refs or any(r not in evidence_ids for r in c.source_refs) for c in brief.claims):
        return LaneOutcome.REJECTED, None

    titles_by_id = {str(item.id): item.title or "" for item in items}

    def titles_for(refs) -> list[str]:
        return [titles_by_id[ref] for ref in dict.fromkeys(refs)]

    cited_titles = titles_for(ref for claim in brief.claims for ref in claim.source_refs)
    match = title_match(text, cited_titles)
    # Review 2026-09-29 #4: the headline is checked like the sentence (an
    # original-looking headline can add a name or number too), and each claim
    # only against the titles it cites, not every claim's citations.
    headline_match = title_match(headline, cited_titles, order="numbers")
    claim_matches = [title_match(c.text, titles_for(c.source_refs)) for c in brief.claims]
    if not match.ok or not headline_match.ok or not all(m.ok for m in claim_matches):
        failed = next(m for m in (match, headline_match, *claim_matches) if not m.ok)
        return LaneOutcome.TITLE_MISMATCH, failed
    return None, match


def _publish_brief(db: Session, story: Story, brief: BriefResult, match: TitleMatch) -> None:
    en = db.scalars(
        select(StoryVariant).where(StoryVariant.story_id == story.id, StoryVariant.language == "en")
    ).first()
    if en is None:
        en = StoryVariant(story_id=story.id, language="en", headline="", summary="")
        db.add(en)
    en.headline = brief.headline_en.strip()
    en.summary = brief.brief_en.strip()
    en.why_matters = None
    en.model_version = BRIEF_MODEL_VERSION
    en.qa_status = "PENDING"
    en.generated_at = datetime.now(UTC)
    # English changed, so any Telugu made from the full draft is stale;
    # `ai_translate` re-derives it (NON_NEGOTIABLES #7).
    db.execute(delete(StoryVariant).where(StoryVariant.story_id == story.id, StoryVariant.language == "te"))
    story.format = "BRIEF"

    story.status = "REVIEW_REQUIRED"
    db.flush()
    story.status = "APPROVED"
    db.flush()
    story.status = "SCHEDULED"
    db.flush()
    db.add(
        AuditEvent(
            actor=BRIEF_ACTOR,
            action="STORY_AUTO_APPROVED",
            entity_type="story",
            entity_id=story.id,
            metadata_={
                "reason": BRIEF_AUDIT_REASON,
                "title_match": {"matched": match.matched},
                "claims": [c.model_dump() for c in brief.claims],
            },
        )
    )
    db.flush()


def try_brief_lane(db: Session, story: Story, *, remaining_cap: int) -> LaneOutcome:
    """Publishes `story` as a brief, or says why not. The caller owns the
    commit and, for anything but `PUBLISHED`, the review-queue fallback."""
    if not briefs_enabled() or not _env_flag(P1_REVIEW_ENV_VAR, default=True):
        return LaneOutcome.NOT_ATTEMPTED
    items = _story_items(db, story)
    if _ineligible(db, story, items) is not None:
        return LaneOutcome.NOT_ATTEMPTED
    if remaining_cap <= 0:
        return LaneOutcome.DAILY_CAP

    evidence_ids = _evidence_item_ids(items)
    outcome = AiGateway(db).run_task(
        Task.SUMMARY,
        _brief_prompt(items),
        story_id=story.id,
        result_model=BriefResult,
        evidence_item_ids=evidence_ids,
        privacy_decision=story.privacy_decision,
    )
    if outcome.status != GatewayStatus.OK or not isinstance(outcome.result, BriefResult):
        return LaneOutcome.REJECTED

    failure, match = _check_brief(outcome.result, items, evidence_ids)
    if failure is not None:
        return failure
    assert match is not None
    _publish_brief(db, story, outcome.result, match)
    return LaneOutcome.PUBLISHED
