"""SSRF and size policy for every fetch of an admin-configured URL.

A source's `feed_url` is admin-supplied, so the scheduled fetch gets the same
guards as the admin "test feed" probe (review #15): http(s) only, the host must
resolve to public addresses only, redirects are not followed, and the body is
read in chunks and capped rather than buffered whole.

Residual: the check resolves the host, then httpx resolves it again to
connect, so a DNS answer that changes in between (rebinding) is not caught.
Closing that needs a transport that connects to the checked address.
"""

from __future__ import annotations

import ipaddress
import socket
from collections.abc import Callable
from typing import Any
from urllib.parse import urlparse

import httpx

MAX_FEED_BYTES = 5_000_000
TIMEOUT_SECONDS = 10.0

Resolver = Callable[[str], list[str]]


class FeedFetchError(Exception):
    """The fetch was refused or failed; the message is safe to show an admin."""


def _resolve(host: str) -> list[str]:
    return [info[4][0] for info in socket.getaddrinfo(host, None)]


def check_public_url(url: str, resolve: Resolver | None = None) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise FeedFetchError("URL must start with http:// or https://")
    try:
        addresses = (resolve or _resolve)(parsed.hostname)
    except OSError:
        raise FeedFetchError("Could not resolve that host")
    if not addresses or not all(ipaddress.ip_address(a).is_global for a in addresses):
        raise FeedFetchError("That host is not a public address")


def fetch_public(
    client: httpx.Client,
    url: str,
    *,
    params: dict[str, Any] | None = None,
    max_bytes: int | None = None,
    timeout: float = TIMEOUT_SECONDS,
    resolve: Resolver | None = None,
) -> bytes:
    """Returns the body, or raises `FeedFetchError` (refused, redirect, HTTP
    error, too large) or `httpx.HTTPError` (transport)."""
    check_public_url(url, resolve)
    max_bytes = max_bytes or MAX_FEED_BYTES
    with client.stream("GET", url, params=params, timeout=timeout, follow_redirects=False) as response:
        if response.is_redirect:
            raise FeedFetchError("Feed redirects elsewhere — use the final URL")
        if response.status_code >= 400:
            raise FeedFetchError(f"Feed returned HTTP {response.status_code}")
        body = bytearray()
        for chunk in response.iter_bytes():
            body.extend(chunk)
            if len(body) > max_bytes:
                raise FeedFetchError(f"Feed is larger than {max_bytes // 1_000_000} MB")
    return bytes(body)
