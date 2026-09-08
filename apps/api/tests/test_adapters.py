"""Adapter contract tests (T07) — fetch -> normalize -> validate -> emit
against recorded fixtures, never a live network call. `fetch()` still runs
its real code path: `httpx.MockTransport` serves fixture bytes in place of
the network, so only the transport is faked, not the parsing logic.
"""

from pathlib import Path

import httpx
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.adapters.rss import RssFeedAdapter
from app.models import Source, SourceItem

from .conftest import requires_postgres

FIXTURES = Path(__file__).parent / "fixtures"


def _client_for_fixture(name: str) -> httpx.Client:
    content = (FIXTURES / name).read_bytes()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=content)

    return httpx.Client(transport=httpx.MockTransport(handler))


def _make_source(**overrides) -> Source:
    defaults = {
        "name": "Test Source",
        "feed_url": "https://example.org/feed.xml",
        "rights_status": "LINK_ONLY",
        "active": True,
    }
    defaults.update(overrides)
    return Source(**defaults)


def test_npr_news_normalize_and_validate():
    client = _client_for_fixture("npr_news.xml")
    adapter = RssFeedAdapter(_make_source(feed_url="https://feeds.npr.org/1001/rss.xml"))
    raw_items = adapter.fetch(client)
    assert len(raw_items.items) == 2

    normalized = [adapter.normalize(raw) for raw in raw_items.items]
    results = [adapter.validate(item) for item in normalized]
    assert all(r.valid for r in results), results

    first = normalized[0]
    assert first.external_id.startswith("https://www.npr.org/2026/09/08/")
    assert first.title == "New report shows the economic toll of ICE raids"
    assert first.published_at is not None


def test_state_travel_advisories_normalize_and_validate():
    client = _client_for_fixture("state_travel_advisories.xml")
    adapter = RssFeedAdapter(
        _make_source(name="State Dept Travel Advisories", feed_url="https://travel.state.gov/_res/rss/TAsTWs.xml")
    )
    raw_items = adapter.fetch(client)
    assert len(raw_items.items) == 2

    normalized = [adapter.normalize(raw) for raw in raw_items.items]
    assert all(adapter.validate(item).valid for item in normalized)
    assert {item.external_id for item in normalized} == {
        "travel-advisory-india-2026-09-08",
        "travel-advisory-ukraine-2026-09-08",
    }


def test_fema_disasters_rejects_invalid_item():
    """One fixture item has no title — validate() must reject it rather
    than emit() silently accepting bad data."""
    client = _client_for_fixture("fema_disasters.xml")
    adapter = RssFeedAdapter(_make_source(name="FEMA Disaster Declarations", feed_url="https://www.fema.gov/feeds/disasters.rss"))
    raw_items = adapter.fetch(client)
    assert len(raw_items.items) == 2

    normalized = [adapter.normalize(raw) for raw in raw_items.items]
    results = [adapter.validate(item) for item in normalized]
    assert results[0].valid
    assert not results[1].valid
    assert "missing title" in results[1].errors


@requires_postgres
def test_emit_creates_source_item(migrated_database):
    engine = create_engine(migrated_database)
    with Session(engine) as db:
        source = _make_source(feed_url="https://feeds.npr.org/1001/rss.xml")
        db.add(source)
        db.commit()

        adapter = RssFeedAdapter(source)
        client = _client_for_fixture("npr_news.xml")
        raw_items = adapter.fetch(client)
        normalized = [adapter.normalize(raw) for raw in raw_items.items]
        assert all(adapter.validate(item).valid for item in normalized)

        for item in normalized:
            adapter.emit(db, item)
        db.commit()

        rows = db.scalars(select(SourceItem).where(SourceItem.source_id == source.id)).all()
        assert len(rows) == 2
        assert {r.external_id for r in rows} == {n.external_id for n in normalized}


@requires_postgres
def test_emit_is_idempotent_on_rerun(migrated_database):
    """Re-running fetch -> normalize -> validate -> emit on the same items
    must not duplicate SourceItem rows (§6 "never duplicate ... when the
    same source item reappears")."""
    engine = create_engine(migrated_database)
    with Session(engine) as db:
        source = _make_source(feed_url="https://feeds.npr.org/1001/rss.xml")
        db.add(source)
        db.commit()

        adapter = RssFeedAdapter(source)

        for _ in range(2):
            client = _client_for_fixture("npr_news.xml")
            raw_items = adapter.fetch(client)
            for raw in raw_items.items:
                item = adapter.normalize(raw)
                if adapter.validate(item).valid:
                    adapter.emit(db, item)
            db.commit()

        rows = db.scalars(select(SourceItem).where(SourceItem.source_id == source.id)).all()
        assert len(rows) == 2
