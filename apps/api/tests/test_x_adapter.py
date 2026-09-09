"""X2 adapter contract tests — `XAdapter.fetch()` against a mocked X API v2
transport (never a live network call), then the shared
normalize/validate/emit pipeline from `app/adapters/base.py` (same as every
other `SourceAdapter`).
"""

import httpx
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.adapters.x import XAdapter
from app.models import Source, SourceItem, XAccount
from app.x import client as x_client
from app.x.client import XRateLimitedError

from .conftest import requires_postgres


def _tweets_response(tweets: list[dict], next_token: str | None = None) -> dict:
    body: dict = {"data": tweets}
    meta = {"result_count": len(tweets)}
    if next_token:
        meta["next_token"] = next_token
    body["meta"] = meta
    return body


def _client_for(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def _make_source(**overrides) -> Source:
    defaults = {"name": "Official Account", "rights_status": "LINK_ONLY", "active": True}
    defaults.update(overrides)
    return Source(**defaults)


def _make_x_account(source_id=None, **overrides) -> XAccount:
    defaults = {
        "source_id": source_id,
        "x_user_id": "12345",
        "handle": "telugu_news",
        "since_id": None,
    }
    defaults.update(overrides)
    return XAccount(**defaults)


def test_fetch_normalizes_and_validates_tweets():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer test-token"
        return httpx.Response(200, json=_tweets_response([
            {"id": "100", "text": "First official update", "created_at": "2026-09-09T12:00:00.000Z"},
            {"id": "101", "text": "Second official update", "created_at": "2026-09-09T12:05:00.000Z"},
        ]))

    source = _make_source()
    x_account = _make_x_account()
    adapter = XAdapter(source, x_account, "test-token")

    raw_items = adapter.fetch(_client_for(handler))
    assert len(raw_items.items) == 2
    assert adapter.posts_read == 2
    assert adapter.newest_id == "101"

    normalized = [adapter.normalize(raw) for raw in raw_items.items]
    assert all(adapter.validate(item).valid for item in normalized)
    assert normalized[0].url == "https://x.com/telugu_news/status/100"


def test_fetch_only_requests_posts_newer_than_since_id():
    """Acceptance criterion: fetch calls only request posts newer than the
    stored `since_id` — never a full re-fetch."""
    seen_params: list[httpx.QueryParams] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_params.append(request.url.params)
        return httpx.Response(200, json=_tweets_response([
            {"id": "205", "text": "Newer than since_id", "created_at": "2026-09-09T13:00:00.000Z"},
        ]))

    source = _make_source()
    x_account = _make_x_account(since_id="200")
    adapter = XAdapter(source, x_account, "test-token")

    adapter.fetch(_client_for(handler))

    assert len(seen_params) == 1
    assert seen_params[0]["since_id"] == "200"
    assert adapter.newest_id == "205"


def test_fetch_paginates_and_keeps_max_newest_id():
    pages = [
        _tweets_response([{"id": "300", "text": "Page one", "created_at": "2026-09-09T14:00:00.000Z"}], next_token="tok-2"),
        _tweets_response([{"id": "301", "text": "Page two", "created_at": "2026-09-09T14:05:00.000Z"}]),
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=pages.pop(0))

    source = _make_source()
    x_account = _make_x_account()
    adapter = XAdapter(source, x_account, "test-token")

    raw_items = adapter.fetch(_client_for(handler))
    assert len(raw_items.items) == 2
    assert adapter.posts_read == 2
    assert adapter.newest_id == "301"


def test_fetch_raises_on_429_without_retrying_itself():
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(429, json={"title": "Too Many Requests"})

    source = _make_source()
    x_account = _make_x_account()
    adapter = XAdapter(source, x_account, "test-token")

    try:
        adapter.fetch(_client_for(handler))
        raise AssertionError("expected XRateLimitedError")
    except XRateLimitedError:
        pass

    assert call_count == 1


def test_client_only_ever_targets_the_official_api_host():
    """NON_NEGOTIABLES #14: the X client only ever talks to the official
    API, never scrapes x.com's public website."""
    assert x_client.BASE_URL == "https://api.x.com/2"


@requires_postgres
def test_emit_is_idempotent_and_rights_gated(migrated_database):
    engine = create_engine(migrated_database)
    with Session(engine) as db:
        source = _make_source()
        db.add(source)
        db.commit()
        x_account = _make_x_account(source_id=source.id)
        db.add(x_account)
        db.commit()

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=_tweets_response([
                {"id": "400", "text": "Emitted post", "created_at": "2026-09-09T15:00:00.000Z"},
            ]))

        for _ in range(2):
            adapter = XAdapter(source, x_account, "test-token")
            raw_items = adapter.fetch(_client_for(handler))
            for raw in raw_items.items:
                item = adapter.normalize(raw)
                if adapter.validate(item).valid:
                    adapter.emit(db, item)
            db.commit()

        rows = db.scalars(select(SourceItem).where(SourceItem.source_id == source.id)).all()
        assert len(rows) == 1
        assert rows[0].ingest_status == "NORMALIZED"
