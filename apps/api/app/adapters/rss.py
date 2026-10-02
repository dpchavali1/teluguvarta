"""Generic RSS 2.0 / Atom feed adapter.

Every source seeded in T07 (see `infra/scripts/seed_sources.py`) is a plain
RSS or Atom feed, so one parser covers all of them instead of a bespoke
adapter per source — a future non-feed source gets its own `SourceAdapter`
subclass.
"""

from __future__ import annotations

from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import TYPE_CHECKING

import httpx

# T19 SAST finding (bandit B314): raw stdlib ElementTree.fromstring on a
# fetched feed body is exactly the untrusted-external-content case
# NON_NEGOTIABLES warns about (XXE/billion-laughs). defusedxml.ElementTree
# is a drop-in replacement with the same API, hardened against those.
from defusedxml import ElementTree as ET

if TYPE_CHECKING:
    from xml.etree.ElementTree import Element

from .base import RawItem, RawItems, SourceAdapter
from .safe_fetch import fetch_public

ATOM_NS = "{http://www.w3.org/2005/Atom}"


class RssFeedAdapter(SourceAdapter):
    def fetch(self, client: httpx.Client) -> RawItems:
        assert self.source.feed_url, f"source {self.source.name!r} has no feed_url configured"
        return self.parse(fetch_public(client, self.source.feed_url))

    def parse(self, content: bytes) -> RawItems:
        root = ET.fromstring(content)
        items = [_from_rss_item(entry) for entry in root.iter("item")]
        items += [_from_atom_entry(entry) for entry in root.iter(f"{ATOM_NS}entry")]
        return RawItems(items=items)


def _from_rss_item(entry: Element) -> RawItem:
    link = (entry.findtext("link") or "").strip()
    guid = (entry.findtext("guid") or link).strip()
    return RawItem(
        external_id=guid,
        url=link,
        title=_clean_title(entry.findtext("title")),
        published_at=_parse_rfc822(entry.findtext("pubDate")),
        raw_bytes=ET.tostring(entry, encoding="utf-8"),
        description=entry.findtext("description"),
    )


def _from_atom_entry(entry: Element) -> RawItem:
    link_el = entry.find(f"{ATOM_NS}link")
    link = (link_el.get("href") or "").strip() if link_el is not None else ""
    guid = (entry.findtext(f"{ATOM_NS}id") or link).strip()
    published = entry.findtext(f"{ATOM_NS}updated") or entry.findtext(f"{ATOM_NS}published")
    return RawItem(
        external_id=guid,
        url=link,
        title=_clean_title(entry.findtext(f"{ATOM_NS}title")),
        published_at=_parse_iso8601(published),
        raw_bytes=ET.tostring(entry, encoding="utf-8"),
        description=entry.findtext(f"{ATOM_NS}summary") or entry.findtext(f"{ATOM_NS}content"),
    )


def _clean_title(value: str | None) -> str | None:
    """Collapses whitespace and drops a repeated trailing " - " segment: the
    State Dept feed sends e.g. "Israel - Level 3: Reconsider Travel - Level 3:
    Reconsider Travel". The title seeds the admin headline pre-fill."""
    if value is None:
        return None
    title = " ".join(value.split())
    parts = title.split(" - ")
    while len(parts) > 1 and parts[-1] == parts[-2]:
        parts.pop()
    return " - ".join(parts) or None


def _parse_rfc822(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None


def _parse_iso8601(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None
