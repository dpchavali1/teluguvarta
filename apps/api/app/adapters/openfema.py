"""OpenFEMA disaster-declaration adapter.

FEMA's RSS feed (`/feeds/disasters.rss`) sends bare disaster numbers as titles
("1", "100", ...) and 2004-era dates, so the FEMA source reads the OpenFEMA
JSON API instead. `FemaWebDisasterDeclarations` has one row per disaster with a
real name, state and date. `DisasterDeclarationsSummaries` has one row per
county, so it would need grouping.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from urllib.parse import urlparse

import httpx
from sqlalchemy import delete, exists, func, select
from sqlalchemy.orm import Session

from app.models import Source, SourceItem, Story, StorySource

from .base import RawItem, RawItems, SourceAdapter

OPENFEMA_URL = "https://www.fema.gov/api/open/v1/FemaWebDisasterDeclarations"
EXTERNAL_ID_PREFIX = "fema-disaster-"
# Declarations older than this are not news; the API is filtered to this
# window and anything older that slips through is dropped too.
MAX_AGE_DAYS = 30
PAGE_SIZE = 200
_SMALL_WORDS = {"a", "an", "and", "as", "at", "by", "for", "in", "of", "on", "or", "the", "to"}
_SELECT = "disasterNumber,declarationDate,disasterName,declarationType,stateName,disasterPageUrl"
# Stories never shown to readers; only these are deleted by the cutover.
_UNPUBLISHED_STATUSES = ("DRAFT", "AI_READY", "REVIEW_REQUIRED")


def is_openfema_url(url: str | None) -> bool:
    parsed = urlparse(url or "")
    return parsed.hostname == "www.fema.gov" and parsed.path.startswith("/api/open/")


class OpenFemaAdapter(SourceAdapter):
    def fetch(self, client: httpx.Client) -> RawItems:
        assert self.source.feed_url, f"source {self.source.name!r} has no feed_url configured"
        cutoff = _now() - timedelta(days=MAX_AGE_DAYS)
        params = {
            "$filter": f"declarationDate ge '{cutoff.strftime('%Y-%m-%dT00:00:00.000Z')}'",
            "$orderby": "declarationDate desc",
            "$top": str(PAGE_SIZE),
            "$select": _SELECT,
        }
        response = client.get(self.source.feed_url, params=params, timeout=10.0)
        response.raise_for_status()
        return self.parse(response.content, now=_now())

    def parse(self, content: bytes, now: datetime) -> RawItems:
        cutoff = now - timedelta(days=MAX_AGE_DAYS)
        records = json.loads(content).get("FemaWebDisasterDeclarations", [])
        items = []
        for record in records:
            published_at = _parse_iso8601(record.get("declarationDate"))
            if published_at is None or published_at < cutoff:
                continue
            number = record.get("disasterNumber")
            items.append(
                RawItem(
                    external_id=f"{EXTERNAL_ID_PREFIX}{number}" if number is not None else "",
                    url=record.get("disasterPageUrl") or "",
                    title=_title(record),
                    published_at=published_at,
                    raw_bytes=json.dumps(record, sort_keys=True).encode("utf-8"),
                )
            )
        return RawItems(items=items)


def _title(record: dict) -> str | None:
    """"Emergency declaration for Hawaii: Tropical Storm Nolo". The API sends
    names in capitals; they are title-cased with small words kept lowercase."""
    name = (record.get("disasterName") or "").strip()
    state = (record.get("stateName") or "").strip()
    kind = (record.get("declarationType") or "").strip()
    if not name or not state:
        return None
    words = name.lower().split()
    cased = " ".join(w if i and w in _SMALL_WORDS else w.capitalize() for i, w in enumerate(words))
    prefix = f"{kind} declaration" if kind else "Disaster declaration"
    return f"{prefix} for {state}: {cased}"


def _parse_iso8601(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _now() -> datetime:
    return datetime.now(UTC)


def retire_legacy_feed_items(db: Session, source: Source) -> dict[str, int]:
    """One-off cutover from the FEMA RSS feed to OpenFEMA. Deletes unpublished
    stories built only from the RSS-era items, deletes the RSS-era items no
    story still references, and points the source at the API. Published or
    mixed stories and their items are kept and counted. API items (external
    id `fema-disaster-N`) are never touched, so a rerun is safe. The caller
    commits."""
    legacy_ids = select(SourceItem.id).where(
        SourceItem.source_id == source.id, SourceItem.external_id.not_like(f"{EXTERNAL_ID_PREFIX}%")
    )
    story_ids = set(db.scalars(select(StorySource.story_id).where(StorySource.source_item_id.in_(legacy_ids))))
    # A story that also links any other item is mixed, not legacy-FEMA-only.
    mixed = set(
        db.scalars(
            select(StorySource.story_id).where(
                StorySource.story_id.in_(story_ids), StorySource.source_item_id.not_in(legacy_ids)
            )
        )
    )
    deletable = set(
        db.scalars(select(Story.id).where(Story.id.in_(story_ids - mixed), Story.status.in_(_UNPUBLISHED_STATUSES)))
    )
    db.execute(delete(Story).where(Story.id.in_(deletable)))

    referenced = exists().where(StorySource.source_item_id == SourceItem.id)
    items_deleted = len(
        db.scalars(delete(SourceItem).where(SourceItem.id.in_(legacy_ids), ~referenced).returning(SourceItem.id)).all()
    )
    items_kept = db.scalar(select(func.count()).select_from(SourceItem).where(SourceItem.id.in_(legacy_ids)))

    source.feed_url = OPENFEMA_URL
    source.fail_count = 0
    db.flush()
    return {
        "stories_deleted": len(deletable),
        "stories_kept": len(story_ids) - len(deletable),
        "legacy_items_deleted": items_deleted,
        "legacy_items_kept": items_kept or 0,
    }
