"""Error tracking (T18): "Sentry or equivalent" per the ticket. Rather than
add the `sentry-sdk` dependency, this speaks Sentry's plain HTTP envelope
protocol directly with `httpx` (already a dependency) — a `SENTRY_DSN` of
the form `https://<key>@<host>/<project_id>` is all that's needed, and it's
a safe no-op when unset (local dev / CI never need a real DSN).

Every capture is tagged with whatever's in the current logging context
(request_id, actor, job_type, story_id — see `app.observability.logging`),
so an error in Sentry (or in the local JSON log, which always gets a line
regardless of whether a DSN is configured) carries the same fields a log
line would.
"""

from __future__ import annotations

import os
import threading
import time
import uuid
from urllib.parse import urlparse

import httpx

from app.observability.logging import current_context, get_logger

logger = get_logger("error_tracking")


def _parse_dsn(dsn: str) -> tuple[str, str] | None:
    """Returns (store_url, public_key) or None if the DSN is malformed."""
    try:
        parsed = urlparse(dsn)
        if not parsed.hostname or not parsed.username or not parsed.path:
            return None
        project_id = parsed.path.strip("/")
        port = f":{parsed.port}" if parsed.port else ""
        store_url = f"{parsed.scheme}://{parsed.hostname}{port}/api/{project_id}/store/"
        return store_url, parsed.username
    except ValueError:
        return None


def capture_exception(exc: BaseException, **extra: object) -> str:
    """Logs the exception with full context and, if SENTRY_DSN is set,
    ships it to Sentry. Returns an event id (generated locally either way)
    so callers/tests can correlate."""
    event_id = uuid.uuid4().hex
    context = {**current_context(), **{k: str(v) for k, v in extra.items() if v is not None}}
    logger.error("unhandled exception: %s", exc, exc_info=exc, extra={"event_id": event_id, **context})

    dsn = os.environ.get("SENTRY_DSN")
    if not dsn:
        return event_id
    parsed = _parse_dsn(dsn)
    if parsed is None:
        return event_id
    store_url, public_key = parsed

    payload = {
        "event_id": event_id,
        "timestamp": time.time(),
        "platform": "python",
        "logger": "teluguvarta-api",
        "tags": context,
        "extra": context,
        "exception": {
            "values": [
                {
                    "type": type(exc).__name__,
                    "value": str(exc),
                }
            ]
        },
    }
    headers = {
        "Content-Type": "application/json",
        "X-Sentry-Auth": (
            f"Sentry sentry_version=7, sentry_client=teluguvarta-api/1.0, sentry_key={public_key}"
        ),
    }
    def _deliver() -> None:
        try:
            httpx.post(store_url, json=payload, headers=headers, timeout=5.0)
        except httpx.HTTPError:
            # Never let telemetry delivery failure mask (or replace) the
            # original error being reported.
            logger.warning("failed to deliver error event %s to Sentry", event_id)

    # Fire-and-forget on a daemon thread: `capture_exception` runs inside
    # both the async request-handler path (errors.py) and the sync worker
    # loop, and an unreachable/slow Sentry must never block either — a
    # request or a job — for up to the 5s timeout above.
    threading.Thread(target=_deliver, daemon=True).start()
    return event_id
