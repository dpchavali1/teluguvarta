"""Admin "test feed" probe: fetch a candidate feed URL and preview its headlines
before a source is saved. Read-only — nothing is persisted, no rights gate is
touched, and headlines go only to the authenticated admin who asked.

The URL is admin-supplied, so the fetch goes through `safe_fetch` (the same
policy the scheduled source fetch uses), with a tighter 2 MB cap.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from xml.etree.ElementTree import ParseError

import httpx
from defusedxml.common import DefusedXmlException

from app.models import Source

from .rss import RssFeedAdapter
from .safe_fetch import FeedFetchError, Resolver, fetch_public

MAX_BYTES = 2_000_000
PREVIEW_LIMIT = 5


@dataclass
class ProbeResult:
    ok: bool
    item_count: int = 0
    headlines: list[str] = field(default_factory=list)
    error: str | None = None


def probe_feed(url: str, client: httpx.Client | None = None, resolve: Resolver | None = None) -> ProbeResult:
    owns_client = client is None
    client = client or httpx.Client()
    try:
        body = fetch_public(client, url, max_bytes=MAX_BYTES, resolve=resolve)
    except FeedFetchError as exc:
        return ProbeResult(ok=False, error=str(exc))
    except httpx.HTTPError as exc:
        return ProbeResult(ok=False, error=f"Could not fetch feed ({type(exc).__name__})")
    finally:
        if owns_client:
            client.close()

    try:
        items = RssFeedAdapter(Source(name="probe")).parse(body).items
    except (ParseError, DefusedXmlException):
        return ProbeResult(ok=False, error="Response is not a valid RSS/Atom feed")
    if not items:
        return ProbeResult(ok=False, error="Feed parsed but contains no items")
    headlines = [i.title.strip() for i in items if i.title][:PREVIEW_LIMIT]
    return ProbeResult(ok=True, item_count=len(items), headlines=headlines)
