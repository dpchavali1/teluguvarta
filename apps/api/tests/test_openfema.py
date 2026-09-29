"""OpenFEMA adapter and the one-off RSS-to-API cutover. Recorded fixture only;
`httpx.MockTransport` stands in for the network."""

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

import httpx
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.adapters.openfema import (
    OPENFEMA_URL,
    OpenFemaAdapter,
    retire_legacy_feed_items,
)
from app.adapters.rss import RssFeedAdapter
from app.jobs.source_fetch import adapter_for
from app.models import Source, SourceItem, Story, StorySource

from .conftest import requires_postgres

FIXTURE = (Path(__file__).parent / "fixtures" / "openfema_declarations.json").read_bytes()
NOW = datetime(2026, 9, 29, tzinfo=UTC)
LEGACY_RSS_URL = "https://www.fema.gov/feeds/disasters.rss"


def _source(**overrides) -> Source:
    fields = {"name": "FEMA Disaster Declarations", "feed_url": OPENFEMA_URL, "rights_status": "LINK_ONLY", "active": True}
    fields.update(overrides)
    return Source(**fields)


def test_parse_builds_titles_and_skips_stale_declarations():
    adapter = OpenFemaAdapter(_source())
    items = [adapter.normalize(raw) for raw in adapter.parse(FIXTURE, now=NOW).items]

    assert [i.title for i in items] == [
        "Emergency declaration for Hawaii: Tropical Storm Nolo",
        "Major Disaster declaration for Kansas: Severe Storms, Straight-line Winds, Tornadoes, and Flooding",
    ]
    assert [i.external_id for i in items] == ["fema-disaster-3654", "fema-disaster-4940"]
    assert items[0].url == "https://www.fema.gov/disaster/3654"
    assert items[0].published_at == datetime(2026, 9, 25, tzinfo=UTC)
    assert all(adapter.validate(i).valid for i in items)


def test_parse_drops_record_without_name():
    content = json.dumps({"FemaWebDisasterDeclarations": [
        {"disasterNumber": 9, "declarationDate": "2026-09-20T00:00:00.000Z", "stateName": "Ohio",
         "disasterPageUrl": "https://www.fema.gov/disaster/9"},
    ]}).encode()
    adapter = OpenFemaAdapter(_source())
    [raw] = adapter.parse(content, now=NOW).items
    assert "missing title" in adapter.validate(adapter.normalize(raw)).errors


def test_fetch_asks_the_api_for_recent_declarations_only():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, content=FIXTURE)

    OpenFemaAdapter(_source()).fetch(httpx.Client(transport=httpx.MockTransport(handler)))
    params = seen[0].url.params
    assert seen[0].url.path == "/api/open/v1/FemaWebDisasterDeclarations"
    assert params["$filter"].startswith("declarationDate ge '")
    assert params["$orderby"] == "declarationDate desc"


def test_digit_only_title_is_rejected_for_any_source():
    feed = b"<rss><channel><item><title> 100 </title><link>https://www.fema.gov/disaster/100</link></item></channel></rss>"
    adapter = RssFeedAdapter(_source(feed_url=LEGACY_RSS_URL))
    [raw] = adapter.parse(feed).items
    assert adapter.validate(adapter.normalize(raw)).errors == ["title is only digits"]


def test_adapter_for_picks_openfema_by_url():
    assert isinstance(adapter_for(_source()), OpenFemaAdapter)
    assert isinstance(adapter_for(_source(feed_url=LEGACY_RSS_URL)), RssFeedAdapter)
    assert isinstance(adapter_for(_source(feed_url="https://example.org/api/open/x")), RssFeedAdapter)


def _item(db: Session, source: Source, external_id: str) -> SourceItem:
    item = SourceItem(source_id=source.id, external_id=external_id, url="https://www.fema.gov/disaster/1",
                      title="1", raw_hash="h", ingest_status="CLUSTERED")
    db.add(item)
    db.flush()
    return item


def _story(db: Session, status: str, *items: SourceItem) -> Story:
    story = Story(canonical_slug=f"story-{uuid.uuid4()}", status=status)
    db.add(story)
    db.flush()
    for rank, item in enumerate(items, start=1):
        db.add(StorySource(story_id=story.id, source_item_id=item.id, role="PRIMARY" if rank == 1 else "SUPPORTING",
                           evidence_rank=rank))
    db.flush()
    return story


@requires_postgres
def test_cutover_deletes_only_unpublished_fema_only_stories_and_their_items(migrated_database):
    with Session(create_engine(migrated_database)) as db:
        fema = _source(feed_url=LEGACY_RSS_URL, active=False, fail_count=3)
        other = _source(name="Other", feed_url="https://example.org/feed.xml")
        db.add_all([fema, other])
        db.flush()

        queued = _story(db, "REVIEW_REQUIRED", _item(db, fema, "https://www.fema.gov/disaster/1"))
        published_item = _item(db, fema, "https://www.fema.gov/disaster/2")
        published = _story(db, "PUBLISHED", published_item)
        mixed_item = _item(db, fema, "https://www.fema.gov/disaster/3")
        mixed = _story(db, "REVIEW_REQUIRED", mixed_item, _item(db, other, "o-1"))
        _item(db, fema, "https://www.fema.gov/disaster/4")  # never clustered
        api_item = _item(db, fema, "fema-disaster-3654")
        db.commit()
        queued_id = queued.id

        summary = retire_legacy_feed_items(db, fema)
        db.commit()

        assert summary == {"stories_deleted": 1, "stories_kept": 2, "legacy_items_deleted": 2, "legacy_items_kept": 2}
        assert db.get(Story, queued_id) is None
        assert db.get(Story, published.id) is not None and db.get(Story, mixed.id) is not None
        remaining = set(db.scalars(select(SourceItem.id).where(SourceItem.source_id == fema.id)))
        assert remaining == {published_item.id, mixed_item.id, api_item.id}
        assert fema.feed_url == OPENFEMA_URL and fema.fail_count == 0 and fema.active is False

        # A rerun finds nothing left to remove and never touches API items.
        assert retire_legacy_feed_items(db, fema)["legacy_items_deleted"] == 0
        assert db.get(SourceItem, api_item.id) is not None
