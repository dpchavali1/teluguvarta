"""Review 2026-09-30 R7: admin lists that stay usable at volume.

The review queue, the content library and audit history are paged on the
server with real totals, instead of the admin downloading every row. The
queue and audit history page by keyset cursor (rows are resolved or appended
while an editor pages, so offsets would skip or repeat rows); the library
pages by offset, ordered by last activity.

Nothing here changes a story: decisions stay one story at a time on the
review page (NON_NEGOTIABLES #5, no bulk sensitive approvals).
"""

import base64
import json
from collections import defaultdict
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import (
    ColumnElement,
    Text,
    case,
    cast,
    exists,
    func,
    literal,
    or_,
    select,
    tuple_,
)
from sqlalchemy.dialects.postgresql import ARRAY, array
from sqlalchemy.orm import Session

from app.content.serialize import load_story_relations
from app.errors import APIError
from app.models import (
    AuditEvent,
    Correction,
    ReviewTask,
    SourceItem,
    Story,
    StorySource,
    StoryTopic,
    StoryVariant,
    Topic,
)

# Mirrors `apps/admin/src/lib/reviewReasons.ts::DANGER_REASONS`: the review
# reasons for the always-human-reviewed categories, listed first in the queue.
DANGER_REASONS = ("SENSITIVE_CATEGORY", "IMMIGRATION", "LEGAL", "FINANCIAL", "BREAKING")
UNCLASSIFIED_REASON = "NO_PAID_PROVIDER"


QUEUE_MAX_LIMIT = 100
LIBRARY_MAX_LIMIT = 100
AUDIT_MAX_LIMIT = 200


def _reasons() -> ColumnElement:
    return func.string_to_array(func.replace(ReviewTask.reason, " ", ""), ",")


def _has_reason(*codes: str) -> ColumnElement:
    return _reasons().op("&&")(cast(array(codes), ARRAY(Text)))


def _encode_cursor(values: list[Any]) -> str:
    return base64.urlsafe_b64encode(json.dumps(values).encode()).decode().rstrip("=")


def _decode_cursor(cursor: str, parsers: tuple[Callable[[Any], Any], ...]) -> list[Any]:
    try:
        values = json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)))
        if not isinstance(values, list) or len(values) != len(parsers):
            raise ValueError
        return [parse(value) for parse, value in zip(parsers, values, strict=True)]
    except (ValueError, TypeError, UnicodeDecodeError):
        raise APIError(422, "INVALID_CURSOR", "This page link is no longer valid — reload the list") from None


def _like(text: str) -> str:
    escaped = text.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def story_filters(
    story_id: Any, *, q: str | None, topic: str | None, source_id: UUID | None, telugu: str | None
) -> list[ColumnElement]:
    """Filters on a story id column shared by the queue and the library."""
    filters: list[ColumnElement] = []
    if q and q.strip():
        pattern = _like(q)
        filters.append(or_(
            exists().where(StoryVariant.story_id == story_id, StoryVariant.headline.ilike(pattern)),
            exists().where(
                StorySource.story_id == story_id,
                SourceItem.id == StorySource.source_item_id,
                SourceItem.title.ilike(pattern),
            ),
            exists().where(Story.id == story_id, Story.canonical_slug.ilike(pattern)),
        ))
    if topic:
        filters.append(exists().where(
            StoryTopic.story_id == story_id, Topic.id == StoryTopic.topic_id, Topic.slug == topic
        ))
    if source_id is not None:
        filters.append(exists().where(
            StorySource.story_id == story_id,
            SourceItem.id == StorySource.source_item_id,
            SourceItem.source_id == source_id,
        ))
    if telugu == "MISSING":
        filters.append(~exists().where(StoryVariant.story_id == story_id, StoryVariant.language == "te"))
    elif telugu is not None:
        filters.append(exists().where(
            StoryVariant.story_id == story_id, StoryVariant.language == "te", StoryVariant.qa_status == telugu
        ))
    return filters


def _source_summary(loaded: Any, story_id: UUID) -> tuple[str | None, list[str]]:
    links = loaded.links[story_id]
    primary = next((link for link in links if link.role == "PRIMARY"), links[0] if links else None)
    primary_item = loaded.items.get(primary.source_item_id) if primary else None
    names: list[str] = []
    for link in links:
        item = loaded.items.get(link.source_item_id)
        source = loaded.sources.get(item.source_id) if item else None
        if source is not None and source.name not in names:
            names.append(source.name)
    return (primary_item.title if primary_item else None), names


def _variant(loaded: Any, story_id: UUID, language: str) -> StoryVariant | None:
    return next((v for v in loaded.variants[story_id] if v.language == language), None)


# --- Review queue -----------------------------------------------------------


def review_queue(
    db: Session,
    *,
    now: datetime,
    cursor: str | None = None,
    limit: int = 50,
    danger_only: bool = False,
    reason: str | None = None,
    q: str | None = None,
    topic: str | None = None,
    source_id: UUID | None = None,
    telugu: str | None = None,
    older_than_hours: int | None = None,
) -> dict[str, Any]:
    """PENDING tasks, always-human-reviewed reasons first, then oldest first."""
    limit = max(1, min(limit, QUEUE_MAX_LIMIT))
    rank = case((_has_reason(*DANGER_REASONS), 0), else_=1)
    pending = ReviewTask.status == "PENDING"
    filters = [pending, *story_filters(ReviewTask.story_id, q=q, topic=topic, source_id=source_id, telugu=telugu)]
    if danger_only:
        filters.append(_has_reason(*DANGER_REASONS))
    if reason:
        filters.append(_has_reason(reason.strip()))
    if older_than_hours is not None:
        filters.append(ReviewTask.created_at <= now - timedelta(hours=max(0, older_than_hours)))

    page_filters = list(filters)
    if cursor:
        r, created_at, task_id = _decode_cursor(cursor, (int, datetime.fromisoformat, UUID))
        page_filters.append(
            tuple_(rank, ReviewTask.created_at, ReviewTask.id) > tuple_(literal(r), literal(created_at), literal(task_id))
        )
    rows = db.execute(
        select(ReviewTask, rank).where(*page_filters)
        .order_by(rank, ReviewTask.created_at, ReviewTask.id).limit(limit + 1)
    ).all()
    has_more = len(rows) > limit
    rows = rows[:limit]

    loaded = load_story_relations(db, [task.story_id for task, _ in rows])
    items = []
    for task, _ in rows:
        en = _variant(loaded, task.story_id, "en")
        te = _variant(loaded, task.story_id, "te")
        source_title, names = _source_summary(loaded, task.story_id)
        items.append({
            "id": task.id, "story_id": task.story_id, "reason": task.reason, "status": task.status,
            "decision": task.decision, "created_at": task.created_at,
            "headline": en.headline if en else None, "source_title": source_title, "source_names": names,
            "topics": sorted(loaded.topics[task.story_id]), "te_qa_status": te.qa_status if te else None,
        })
    last_task, last_rank = rows[-1] if rows else (None, None)

    counts = db.execute(select(
        func.count(),
        func.count().filter(_has_reason(*DANGER_REASONS)),
        func.count().filter(_has_reason(UNCLASSIFIED_REASON)),
        func.min(ReviewTask.created_at),
    ).where(pending)).one()
    return {
        "items": items,
        "total": db.scalar(select(func.count()).select_from(ReviewTask).where(*filters)) or 0,
        "pending_total": counts[0],
        "danger_total": counts[1],
        "unclassified_total": counts[2],
        "oldest_created_at": counts[3],
        "next_cursor": _encode_cursor([last_rank, last_task.created_at.isoformat(), str(last_task.id)])
        if has_more and last_task is not None else None,
        "generated_at": now,
    }


# --- Content library ---------------------------------------------------------


def _last_activity() -> ColumnElement:
    latest_variant = (
        select(func.max(StoryVariant.generated_at)).where(StoryVariant.story_id == Story.id).scalar_subquery()
    )
    return func.coalesce(Story.published_at, latest_variant)


def story_library(
    db: Session,
    *,
    now: datetime,
    status: str | None = None,
    corrected: bool = False,
    q: str | None = None,
    topic: str | None = None,
    source_id: UUID | None = None,
    telugu: str | None = None,
    format: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """Every story by last activity (published, else newest draft), newest first.

    Stories have no creation time, so a story with neither a publish time nor
    a draft sorts last.
    """
    limit = max(1, min(limit, LIBRARY_MAX_LIMIT))
    offset = max(0, offset)
    filters = story_filters(Story.id, q=q, topic=topic, source_id=source_id, telugu=telugu)
    if status is not None:
        filters.append(Story.status == status)
    if corrected:
        filters.append(exists().where(Correction.story_id == Story.id))
    if format is not None:
        filters.append(Story.format == format)

    activity = _last_activity().label("last_activity")
    rows = db.execute(
        select(Story, activity).where(*filters)
        .order_by(activity.desc().nulls_last(), Story.id).offset(offset).limit(limit)
    ).all()
    ids = [story.id for story, _ in rows]
    loaded = load_story_relations(db, ids)
    corrections: dict[UUID, int] = defaultdict(int)
    reviewing: set[UUID] = set()
    if ids:
        corrections.update(db.execute(
            select(Correction.story_id, func.count()).where(Correction.story_id.in_(ids)).group_by(Correction.story_id)
        ).tuples().all())
        reviewing = set(db.scalars(
            select(ReviewTask.story_id).where(ReviewTask.story_id.in_(ids), ReviewTask.status == "PENDING")
        ))

    items = []
    for story, last_activity in rows:
        en = _variant(loaded, story.id, "en")
        te = _variant(loaded, story.id, "te")
        source_title, names = _source_summary(loaded, story.id)
        items.append({
            "id": story.id, "canonical_slug": story.canonical_slug, "status": story.status,
            "format": story.format, "sensitivity": story.sensitivity, "published_at": story.published_at,
            "last_activity_at": last_activity, "headline": en.headline if en else None,
            "te_headline": te.headline if te else None, "te_qa_status": te.qa_status if te else None,
            "source_title": source_title, "source_names": names, "topics": sorted(loaded.topics[story.id]),
            "corrections": corrections[story.id], "review_pending": story.id in reviewing,
        })

    status_counts = dict(db.execute(select(Story.status, func.count()).group_by(Story.status)).tuples().all())
    corrected_total = db.scalar(select(func.count(func.distinct(Correction.story_id))))
    return {
        "items": items,
        "total": db.scalar(select(func.count()).select_from(Story).where(*filters)) or 0,
        "status_counts": status_counts,
        "corrected_total": corrected_total or 0,
        "generated_at": now,
    }


# --- Audit history -----------------------------------------------------------


def audit_history(
    db: Session,
    *,
    cursor: str | None = None,
    limit: int = 100,
    action: str | None = None,
    entity_type: str | None = None,
    entity_id: UUID | None = None,
    actor: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
) -> dict[str, Any]:
    """Newest first. `actor` matches part of the actor (an email or a job name)."""
    limit = max(1, min(limit, AUDIT_MAX_LIMIT))
    filters: list[ColumnElement] = []
    if action:
        filters.append(AuditEvent.action == action.strip())
    if entity_type:
        filters.append(AuditEvent.entity_type == entity_type.strip())
    if entity_id is not None:
        filters.append(AuditEvent.entity_id == entity_id)
    if actor and actor.strip():
        filters.append(AuditEvent.actor.ilike(_like(actor)))
    if since is not None:
        filters.append(AuditEvent.created_at >= since)
    if until is not None:
        filters.append(AuditEvent.created_at < until)
    page_filters = list(filters)
    if cursor:
        created_at, event_id = _decode_cursor(cursor, (datetime.fromisoformat, UUID))
        page_filters.append(
            tuple_(AuditEvent.created_at, AuditEvent.id) < tuple_(literal(created_at), literal(event_id))
        )
    events = db.scalars(
        select(AuditEvent).where(*page_filters)
        .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc()).limit(limit + 1)
    ).all()
    has_more = len(events) > limit
    events = events[:limit]
    last = events[-1] if events else None
    return {
        "items": [
            {
                "id": e.id, "actor": e.actor, "action": e.action, "entity_type": e.entity_type,
                "entity_id": e.entity_id, "metadata": e.metadata_, "created_at": e.created_at,
            }
            for e in events
        ],
        "next_cursor": _encode_cursor([last.created_at.isoformat(), str(last.id)]) if has_more and last else None,
    }
