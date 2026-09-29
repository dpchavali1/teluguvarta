"""Admin "test feed" probe: fetch a candidate feed URL and preview its headlines
before a source is saved. Read-only — nothing is persisted, no rights gate is
touched, and headlines go only to the authenticated admin who asked.

The URL is admin-supplied, so the fetch is SSRF-hardened: http(s) only, the
host must resolve to public addresses only, redirects are not followed, and
the body is size-capped.
"""

from __future__ import annotations

import ipaddress
import socket
from collections.abc import Callable
from dataclasses import dataclass, field
from urllib.parse import urlparse
from xml.etree.ElementTree import ParseError

import httpx
from defusedxml.common import DefusedXmlException

from app.models import Source

from .rss import RssFeedAdapter

MAX_BYTES = 2_000_000
PREVIEW_LIMIT = 5
TIMEOUT_SECONDS = 10.0

Resolver = Callable[[str], list[str]]


@dataclass
class ProbeResult:
    ok: bool
    item_count: int = 0
    headlines: list[str] = field(default_factory=list)
    error: str | None = None


def _resolve(host: str) -> list[str]:
    return [info[4][0] for info in socket.getaddrinfo(host, None)]


def _check_url(url: str, resolve: Resolver) -> str | None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return "URL must start with http:// or https://"
    try:
        addresses = resolve(parsed.hostname)
    except OSError:
        return "Could not resolve that host"
    if not addresses or not all(ipaddress.ip_address(a).is_global for a in addresses):
        return "That host is not a public address"
    return None


def probe_feed(url: str, client: httpx.Client | None = None, resolve: Resolver = _resolve) -> ProbeResult:
    problem = _check_url(url, resolve)
    if problem:
        return ProbeResult(ok=False, error=problem)

    owns_client = client is None
    client = client or httpx.Client(follow_redirects=False)
    try:
        with client.stream("GET", url, timeout=TIMEOUT_SECONDS) as response:
            if response.is_redirect:
                return ProbeResult(ok=False, error="Feed redirects elsewhere — use the final URL")
            if response.status_code >= 400:
                return ProbeResult(ok=False, error=f"Feed returned HTTP {response.status_code}")
            body = bytearray()
            for chunk in response.iter_bytes():
                body.extend(chunk)
                if len(body) > MAX_BYTES:
                    return ProbeResult(ok=False, error="Feed is larger than 2 MB")
    except httpx.HTTPError as exc:
        return ProbeResult(ok=False, error=f"Could not fetch feed ({type(exc).__name__})")
    finally:
        if owns_client:
            client.close()

    try:
        items = RssFeedAdapter(Source(name="probe")).parse(bytes(body)).items
    except (ParseError, DefusedXmlException):
        return ProbeResult(ok=False, error="Response is not a valid RSS/Atom feed")
    if not items:
        return ProbeResult(ok=False, error="Feed parsed but contains no items")
    headlines = [i.title.strip() for i in items if i.title][:PREVIEW_LIMIT]
    return ProbeResult(ok=True, item_count=len(items), headlines=headlines)
