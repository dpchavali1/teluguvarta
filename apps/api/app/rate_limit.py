"""In-process sliding-window rate limiting (T19 §16 baseline: rate limiting
on auth/search/admin).

Admin *login* already has its own Postgres-backed limiter keyed by email
(`app/security.py::is_login_rate_limited`) — that stays as-is, it's the one
that matters for credential stuffing. This module covers request-volume
limiting on the public search endpoint and the general admin surface: a
plain in-memory sliding window per client, not Redis, per NON_NEGOTIABLES
(no new infra without a measured need) — request volume here is far below
what would need anything faster.

This is process-local: correct for the single-instance modular monolith
this build targets today. If the API is ever horizontally scaled, this
needs a shared store (still Postgres, not Redis) — flagged as a follow-up
in ADR-007 rather than built speculatively now.
"""

import time
from collections import defaultdict, deque

from fastapi import Request

from app.errors import APIError

_WINDOWS: dict[str, deque[float]] = defaultdict(deque)

SEARCH_MAX_REQUESTS = 30
SEARCH_WINDOW_SECONDS = 60.0

ADMIN_MAX_REQUESTS = 120
ADMIN_WINDOW_SECONDS = 60.0

# T20: the pilot-signup form is a public write (not a read like search), so
# it's throttled much tighter — a handful of real signups per visitor, not
# a search-volume ceiling.
SIGNUP_MAX_REQUESTS = 5
SIGNUP_WINDOW_SECONDS = 300.0


def _check(key: str, *, max_requests: int, window_seconds: float) -> None:
    now = time.monotonic()
    bucket = _WINDOWS[key]
    cutoff = now - window_seconds
    while bucket and bucket[0] < cutoff:
        bucket.popleft()
    if len(bucket) >= max_requests:
        raise APIError(429, "RATE_LIMITED", "Too many requests — try again shortly")
    bucket.append(now)


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def rate_limit_search(request: Request) -> None:
    _check(f"search:{_client_ip(request)}", max_requests=SEARCH_MAX_REQUESTS, window_seconds=SEARCH_WINDOW_SECONDS)


def rate_limit_admin(request: Request) -> None:
    _check(f"admin:{_client_ip(request)}", max_requests=ADMIN_MAX_REQUESTS, window_seconds=ADMIN_WINDOW_SECONDS)


def rate_limit_signup(request: Request) -> None:
    _check(f"signup:{_client_ip(request)}", max_requests=SIGNUP_MAX_REQUESTS, window_seconds=SIGNUP_WINDOW_SECONDS)


def reset() -> None:
    """Test-only: clear all windows between test cases in the same process."""
    _WINDOWS.clear()
