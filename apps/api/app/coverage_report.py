"""Review 2026-09-30 R8: is what we publish spread across publishers and
topics, and how much of what each feed sends ever reaches readers?

Two cohorts, kept apart like the cost report's (R5):

- **Item cohort**: source items whose publisher date falls in the window.
  Each is counted once, in exactly one outcome, so the outcomes add up to
  the item total. Items without a publisher date can't be placed in a
  window and are left out (source items record no fetch time).
- **Publication cohort**: stories that went live in the window (live now,
  `published_at` in range). A story belongs to the publisher of its PRIMARY
  item, the one that started the cluster.

A publisher is the host of a source's site, so the several section feeds of
one paper count as one publisher.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import and_, distinct, func, select
from sqlalchemy.orm import Session

from app.ai.cost_report import window
from app.models import Source, SourceItem, Story, StorySource, StoryTopic, Topic

LIVE_STATUSES = ("PUBLISHED", "UPDATED")
# Hours from the publisher's own timestamp to our publication.
LAG_BUCKETS = ((1, "under_1h"), (3, "under_3h"), (12, "under_12h"), (24, "under_24h"))


def publisher_of(source: Source) -> str:
    for url in (source.base_url, source.feed_url):
        host = urlparse(url or "").hostname
        if host:
            return host.removeprefix("www.")
    return source.name


def _lag_bucket(hours: float | None) -> str:
    if hours is None:
        return "unknown"
    for limit, key in LAG_BUCKETS:
        if hours < limit:
            return key
    return "over_24h"


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    return ordered[mid] if len(ordered) % 2 else (ordered[mid - 1] + ordered[mid]) / 2


def coverage_report(db: Session, start: date, end: date) -> dict:
    lo, hi = window(start, end)
    sources = {s.id: s for s in db.scalars(select(Source))}

    # --- Item cohort: one outcome per item ---------------------------------
    item = SourceItem
    linked = StorySource.id.is_not(None)
    archived = item.ingest_status == "ARCHIVED"
    outcomes = {
        "rights_blocked": item.ingest_status == "RIGHTS_BLOCKED",
        # Archived before clustering: the first-fetch backlog cutoff.
        "backlog_skipped": and_(archived, ~linked),
        # Archived after clustering: the classifier judged it not relevant.
        "not_relevant": and_(archived, linked),
        "live": and_(~archived, Story.status.in_(LIVE_STATUSES)),
        "in_review": and_(~archived, Story.status == "REVIEW_REQUIRED"),
    }
    item_rows = db.execute(
        select(
            item.source_id,
            func.count(distinct(item.id)).label("items"),
            *(func.count(distinct(item.id)).filter(cond).label(key) for key, cond in outcomes.items()),
        )
        .outerjoin(StorySource, StorySource.source_item_id == item.id)
        .outerjoin(Story, Story.id == StorySource.story_id)
        .where(item.published_at >= lo, item.published_at < hi)
        .group_by(item.source_id)
    ).all()

    def funnel(row) -> dict:
        counts = {"items": int(row.items), **{key: int(getattr(row, key)) for key in outcomes}}
        # Not yet clustered, still being generated, approved/scheduled, or
        # withdrawn after publishing.
        counts["other"] = counts["items"] - sum(counts[key] for key in outcomes)
        return counts

    funnels = {row.source_id: funnel(row) for row in item_rows}

    # --- Publication cohort -------------------------------------------------
    published = db.execute(
        select(Story.id, Story.published_at, item.source_id, item.published_at.label("item_published_at"))
        .join(StorySource, and_(StorySource.story_id == Story.id, StorySource.role == "PRIMARY"))
        .join(item, item.id == StorySource.source_item_id)
        .where(Story.status.in_(LIVE_STATUSES), Story.published_at >= lo, Story.published_at < hi)
    ).all()
    # Hand-drafted stories have no PRIMARY item; count them without a publisher.
    published_total = db.scalar(
        select(func.count()).where(
            Story.status.in_(LIVE_STATUSES), Story.published_at >= lo, Story.published_at < hi
        )
    ) or 0

    lag_hours: dict = {}
    published_by_source: dict = {}
    lag = {key: 0 for _, key in LAG_BUCKETS} | {"over_24h": 0, "unknown": 0}
    by_day: dict[date, dict] = {}
    for row in published:
        hours = (
            max((row.published_at - row.item_published_at).total_seconds() / 3600, 0)
            if row.item_published_at is not None
            else None
        )
        lag[_lag_bucket(hours)] += 1
        published_by_source[row.source_id] = published_by_source.get(row.source_id, 0) + 1
        if hours is not None:
            lag_hours.setdefault(row.source_id, []).append(hours)
        day = by_day.setdefault(row.published_at.astimezone(lo.tzinfo).date(), {"stories": 0, "publishers": set()})
        day["stories"] += 1
        source = sources.get(row.source_id)
        day["publishers"].add(publisher_of(source) if source else str(row.source_id))

    published_ids = [row.id for row in published]
    days = []
    current = start
    while current <= end:
        entry = by_day.get(current)
        days.append({
            "day": current,
            "published": entry["stories"] if entry else 0,
            "publishers": len(entry["publishers"]) if entry else 0,
        })
        current += timedelta(days=1)

    # --- Per source and per publisher ----------------------------------------
    empty = {"items": 0, **{key: 0 for key in outcomes}, "other": 0}
    source_rows = []
    publishers: dict[str, dict] = {}
    for source_id, source in sources.items():
        counts = funnels.get(source_id, empty)
        pub = published_by_source.get(source_id, 0)
        if not source.active and counts["items"] == 0 and pub == 0:
            continue
        name = publisher_of(source)
        median = _median(lag_hours.get(source_id, []))
        source_rows.append({
            "source_id": source_id,
            "name": source.name,
            "publisher": name,
            "category": source.category,
            "active": source.active,
            "rights_status": source.rights_status,
            **counts,
            "published": pub,
            "median_lag_hours": round(median, 1) if median is not None else None,
        })
        rollup = publishers.setdefault(name, {"publisher": name, "feeds": 0, "items": 0, "live": 0, "published": 0})
        rollup["feeds"] += 1
        rollup["items"] += counts["items"]
        rollup["live"] += counts["live"]
        rollup["published"] += pub
    source_rows.sort(key=lambda r: (-r["published"], -r["items"], r["name"]))
    publisher_rows = sorted(publishers.values(), key=lambda r: (-r["published"], -r["items"], r["publisher"]))
    for rollup in publisher_rows:
        rollup["share"] = round(rollup["published"] / published_total, 3) if published_total else 0.0

    # --- Topics: every active topic, zero-filled, so gaps show ---------------
    topic_published = dict(
        db.execute(
            select(StoryTopic.topic_id, func.count())
            .where(StoryTopic.story_id.in_(published_ids))
            .group_by(StoryTopic.topic_id)
        ).all()
    ) if published_ids else {}
    topic_review = dict(
        db.execute(
            select(StoryTopic.topic_id, func.count())
            .join(Story, Story.id == StoryTopic.story_id)
            .where(Story.status == "REVIEW_REQUIRED")
            .group_by(StoryTopic.topic_id)
        ).all()
    )
    topic_rows: list[dict[str, Any]] = [
        {
            "slug": topic.slug,
            "name": topic.name,
            "active": topic.active,
            "published": int(topic_published.get(topic.id, 0)),
            "in_review": int(topic_review.get(topic.id, 0)),
        }
        for topic in db.scalars(select(Topic))
        if topic.active or topic.id in topic_published
    ]
    topic_rows.sort(key=lambda r: (-r["published"], -r["in_review"], r["slug"]))
    tagged = db.scalar(
        select(func.count(distinct(StoryTopic.story_id))).where(StoryTopic.story_id.in_(published_ids))
    ) if published_ids else 0

    totals = {"items": 0, **{key: 0 for key in outcomes}, "other": 0}
    for counts in funnels.values():
        for key in totals:
            totals[key] += counts[key]
    top = publisher_rows[0] if publisher_rows and publisher_rows[0]["published"] else None

    return {
        "start": start,
        "end": end,
        "items": totals,
        "published": int(published_total),
        "published_without_source": int(published_total) - len(published),
        "published_untagged": len(published) - int(tagged or 0),
        "publishers_published": sum(1 for r in publisher_rows if r["published"]),
        "top_publisher": top["publisher"] if top else None,
        "top_publisher_share": top["share"] if top else 0.0,
        "lag": lag,
        "by_day": days,
        "publishers": publisher_rows,
        "sources": source_rows,
        "topics": topic_rows,
    }
