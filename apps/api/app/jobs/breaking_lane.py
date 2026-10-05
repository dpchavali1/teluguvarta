"""ADR-054: auto-publish lane for BREAKING and death stories, source text only.

`publish.auto_publish_stories` calls `publish_breaking_briefs` before its normal
pass. A story waiting in review as BREAKING (or as a RESTRICTED / AI-unclassified
hold that mentions a death, ADR-052) publishes as a `BRIEF` when it is backed by
at least `BREAKING_MIN_SOURCES` independent approved publishers, or by one source
on the owner's `BREAKING_TRUSTED_SOURCES` list. The published text is the
source's own headline plus a fixed attribution line: no AI writes or translates
anything here, so the AI can neither invent nor hide a death. Immigration,
legal, financial and accusation stories are never touched.

Closed unless `AUTO_PUBLISH_BREAKING=true`, the dashboard `breaking` switch is
on, and the dashboard `auto_publish` switch is on. Every publish is audited,
alerted, capped per day, and undone with the normal retract action.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import urlparse

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.privacy import TELUGU_DEATH_TERMS
from app.content.rights import RIGHTS_REVOKED_REASON, unpermitted_sources
from app.models import (
    AuditEvent,
    ReviewTask,
    Source,
    SourceItem,
    Story,
    StorySource,
    StoryVariant,
)
from app.switches import is_on

logger = logging.getLogger(__name__)

AUTO_PUBLISH_BREAKING_ENV = "AUTO_PUBLISH_BREAKING"
DAILY_CAP_ENV = "AUTO_PUBLISH_BREAKING_DAILY_CAP"
MIN_SOURCES_ENV = "BREAKING_MIN_SOURCES"
TRUSTED_SOURCES_ENV = "BREAKING_TRUSTED_SOURCES"
DEFAULT_DAILY_CAP = 10
DEFAULT_MIN_SOURCES = 2
MAX_ITEM_AGE = timedelta(hours=24)

BREAKING_ACTOR = "system:breaking_lane"
BREAKING_AUDIT_REASON = "BREAKING_SOURCE_TEXT"
BREAKING_TASK_DECISION = "AUTO_APPROVED_BREAKING"
# `StoryVariant.model_version` of a variant that is the source's own words; the
# translation sweep skips it (no machine translation is shown as fact).
SOURCE_TEXT_MODEL_VERSION = "source_text"

# NON_NEGOTIABLES #5 still holds for these: a source configured in one of these
# categories keeps its stories with a human.
ALWAYS_REVIEWED_SOURCE_CATEGORIES = frozenset({"immigration", "legal", "financial"})
# Sensitivity values this lane may take over. Everything else waits for a human.
_LANE_SENSITIVITIES = frozenset({"BREAKING", "NONE"})

# ADR-052: a RESTRICTED or AI-unclassifiable hold that mentions a death is
# treated like BREAKING. Deliberately narrow: other RESTRICTED topics
# (immigration, tax, court, ...) keep the 24h expiry.
DEATH_SIGNAL_PATTERN = re.compile(
    rf"{TELUGU_DEATH_TERMS}|"
    r"\b(died|dies|death|dead|killed|obituar\w*|pass(?:es|ed)\s+away|demise|funeral)\b",
    re.IGNORECASE,
)
DEATH_HOLD_REASONS = ("NO_PAID_PROVIDER", "AI_RETRIES_EXHAUSTED")

_TELUGU_SCRIPT = re.compile(r"[ఀ-౿]")
_SECOND_LEVEL_LABELS = frozenset({"co", "com", "org", "net", "gov", "ac", "edu"})


@dataclass
class _Candidate:
    story: Story
    tasks: list[ReviewTask]
    items: list[SourceItem]
    sources: dict  # source id -> Source


def death_hold_candidate(story: Story, tasks: list[ReviewTask]) -> bool:
    return story.status == "REVIEW_REQUIRED" and (
        story.privacy_decision == "RESTRICTED"
        or any(r in t.reason for t in tasks for r in DEATH_HOLD_REASONS)
    )


def lane_enabled() -> bool:
    return os.environ.get(AUTO_PUBLISH_BREAKING_ENV, "false").strip().lower() == "true"


def _int_env(name: str, default: int) -> int:
    try:
        return max(0, int(os.environ.get(name, default)))
    except ValueError:
        return default


def daily_cap() -> int:
    return _int_env(DAILY_CAP_ENV, DEFAULT_DAILY_CAP)


def min_sources() -> int:
    return max(1, _int_env(MIN_SOURCES_ENV, DEFAULT_MIN_SOURCES))


def trusted_sources() -> frozenset[str]:
    """Source ids or names (case-insensitive) the owner trusts alone. Empty by
    default, so nothing qualifies on one source until it is set."""
    raw = os.environ.get(TRUSTED_SOURCES_ENV, "")
    return frozenset(part.strip().lower() for part in raw.split(",") if part.strip())


def published_today(db: Session, now: datetime) -> int:
    from app.jobs.brief_lane import (
        cap_day_start,  # lazy: brief_lane -> generate -> translate imports this module
    )

    return db.scalar(
        select(func.count(AuditEvent.id)).where(
            AuditEvent.actor == BREAKING_ACTOR,
            AuditEvent.action == "STORY_AUTO_APPROVED",
            AuditEvent.created_at >= cap_day_start(now),
        )
    ) or 0


def publisher_domain(source: Source, item: SourceItem | None = None) -> str:
    """Registrable-ish domain used for the independence check: two sources on
    one domain (or a `www.` / feed subdomain of it) are one publisher."""
    host = ""
    for url in (source.base_url, source.feed_url, item.url if item else None):
        host = (urlparse(url or "").hostname or "").lower()
        if host:
            break
    labels = [part for part in host.split(".") if part]
    if len(labels) <= 2:
        return ".".join(labels) or f"source:{source.id}"
    keep = 3 if len(labels[-1]) == 2 and labels[-2] in _SECOND_LEVEL_LABELS else 2
    return ".".join(labels[-keep:])


def _source_approved(source: Source) -> bool:
    return (
        source.rights_status == "LINK_ONLY"
        and source.active
        and source.rights_reviewed_at is not None
        and bool(source.rights_evidence_url)
    )


def _is_trusted(source: Source, trusted: frozenset[str]) -> bool:
    return str(source.id).lower() in trusted or source.name.strip().lower() in trusted


def _in_scope(db: Session, c: _Candidate) -> bool:
    story = c.story
    if story.sensitivity not in _LANE_SENSITIVITIES:
        return False
    if any(RIGHTS_REVOKED_REASON in t.reason for t in c.tasks):
        return False
    if story.sensitivity == "BREAKING":
        return True
    if not death_hold_candidate(story, c.tasks):
        return False
    return any(DEATH_SIGNAL_PATTERN.search(item.title or "") for item in c.items)


def _fresh(items: list[SourceItem], now: datetime) -> bool:
    dated = [item.published_at for item in items if item.published_at]
    return not dated or max(dated) >= now - MAX_ITEM_AGE


def _trust_basis(c: _Candidate, trusted: frozenset[str], needed: int) -> dict | None:
    """The reason this story may skip review, or `None`. Counts only approved
    sources, and each publisher domain once."""
    approved = [(item, c.sources[item.source_id]) for item in c.items if _source_approved(c.sources[item.source_id])]
    domains = sorted({publisher_domain(source, item) for item, source in approved})
    if len(domains) >= needed:
        return {"basis": "INDEPENDENT_SOURCES", "publishers": domains}
    trusted_hit = sorted({source.name for _, source in approved if _is_trusted(source, trusted)})
    if trusted_hit:
        return {"basis": "TRUSTED_SOURCE", "publishers": trusted_hit}
    return None


def _english_title(items: list[SourceItem]) -> SourceItem | None:
    return next((i for i in items if i.title and i.title.strip() and not _TELUGU_SCRIPT.search(i.title)), None)


def _telugu_title(items: list[SourceItem], sources: dict) -> SourceItem | None:
    return next(
        (i for i in items if i.title and _TELUGU_SCRIPT.search(i.title) and (sources[i.source_id].language or "").startswith("te")),
        None,
    )


def _set_variant(db: Session, story: Story, language: str, headline: str, summary: str) -> dict | None:
    variant = db.scalars(
        select(StoryVariant).where(StoryVariant.story_id == story.id, StoryVariant.language == language)
    ).first()
    replaced = {"headline": variant.headline, "summary": variant.summary} if variant else None
    if variant is None:
        variant = StoryVariant(story_id=story.id, language=language, headline="", summary="")
        db.add(variant)
    variant.headline, variant.summary, variant.why_matters = headline, summary, None
    variant.model_version = SOURCE_TEXT_MODEL_VERSION
    variant.qa_status = "PENDING"
    variant.generated_at = datetime.now(UTC)
    return replaced


def _load_candidates(db: Session) -> list[_Candidate]:
    tasks = db.scalars(
        select(ReviewTask).join(Story, Story.id == ReviewTask.story_id).where(
            ReviewTask.status == "PENDING", Story.status == "REVIEW_REQUIRED", Story.sensitivity.in_(_LANE_SENSITIVITIES)
        )
    ).all()
    by_story: dict = {}
    for task in tasks:
        by_story.setdefault(task.story_id, []).append(task)
    out: list[_Candidate] = []
    for story in db.scalars(select(Story).where(Story.id.in_(by_story)).order_by(Story.id)).all():
        rows = db.execute(
            select(SourceItem, StorySource.evidence_rank)
            .join(StorySource, StorySource.source_item_id == SourceItem.id)
            .where(StorySource.story_id == story.id)
            .order_by(StorySource.evidence_rank.asc().nulls_last(), SourceItem.id)
        ).all()
        items = [row[0] for row in rows]
        sources = {s.id: s for s in db.scalars(select(Source).where(Source.id.in_({i.source_id for i in items}))).all()}
        out.append(_Candidate(story, by_story[story.id], items, sources))
    return out


def publish_breaking_briefs(db: Session, *, now: datetime | None = None) -> int:
    """Approves every eligible waiting story as a source-text brief, commits,
    then alerts. Returns how many were approved; the publish sweep finishes
    SCHEDULED -> PUBLISHED and re-checks rights."""
    if not lane_enabled() or not is_on(db, "breaking"):
        return 0
    now = now or datetime.now(UTC)
    left = daily_cap() - published_today(db, now)
    trusted, needed = trusted_sources(), min_sources()
    alerts: list[str] = []
    for c in _load_candidates(db):
        if left <= 0:
            break
        if not c.items or not _in_scope(db, c) or not _fresh(c.items, now):
            continue
        if unpermitted_sources(db, c.story.id):
            continue
        if any((s.category or "").strip().lower() in ALWAYS_REVIEWED_SOURCE_CATEGORIES for s in c.sources.values()):
            continue
        basis = _trust_basis(c, trusted, needed)
        english = _english_title(c.items)
        if basis is None or english is None:
            continue
        telugu = _telugu_title(c.items, c.sources)
        publisher = c.sources[english.source_id].name
        headline = (english.title or "").strip()
        replaced = {
            "en": _set_variant(
                db, c.story, "en", headline, f"Reported by {publisher}. Read the original for details."
            )
        }
        if telugu is not None:
            replaced["te"] = _set_variant(
                db, c.story, "te", (telugu.title or "").strip(), f"{c.sources[telugu.source_id].name} నివేదించింది. వివరాల కోసం మూల కథనాన్ని చూడండి."
            )
        else:
            replaced["te"] = _drop_telugu(db, c.story)
        c.story.format = "BRIEF"
        c.story.status = "APPROVED"
        db.flush()
        c.story.status = "SCHEDULED"
        for task in c.tasks:
            task.status, task.decision = "APPROVED", BREAKING_TASK_DECISION
        db.add(
            AuditEvent(
                actor=BREAKING_ACTOR, action="STORY_AUTO_APPROVED", entity_type="story", entity_id=c.story.id,
                metadata_={
                    "reason": BREAKING_AUDIT_REASON, **basis, "sensitivity": c.story.sensitivity,
                    "source_item_ids": [str(i.id) for i in c.items], "replaced_draft": replaced,
                },
            )
        )
        db.flush()
        left -= 1
        alerts.append(
            f"Auto-published breaking brief: {headline} | {english.url} | "
            f"{basis['basis']}: {', '.join(basis['publishers'])} | retract in admin if wrong (story {c.story.id})"
        )
    db.commit()
    from app import (
        alerts as alerts_module,  # lazy: alerts imports publish, which imports this module
    )

    for message in alerts:
        try:
            alerts_module.send_alert(message, severity="WARNING")
        except Exception:  # an alert failure must not undo or retry the publish
            logger.exception("breaking-lane alert failed")
    return len(alerts)


def _drop_telugu(db: Session, story: Story) -> dict | None:
    """No Telugu headline from a source: remove any machine draft so readers get
    the English fallback instead of an unreviewed translation of a death."""
    variant = db.scalars(select(StoryVariant).where(StoryVariant.story_id == story.id, StoryVariant.language == "te")).first()
    if variant is None:
        return None
    replaced = {"headline": variant.headline, "summary": variant.summary}
    db.delete(variant)
    return replaced
