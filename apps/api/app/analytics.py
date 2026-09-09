"""§9.4 analytics events (T17). No PostHog-or-equivalent wiring exists yet
(that's T18 Observability's job per docs/BUILD_ORDER.md) — until then, a
structured log line is the deterministic, no-new-infrastructure sink
NON_NEGOTIABLES asks for, and it's exactly what T18 will forward once a real
sink is chosen. Tests assert against these log records directly (caplog).
"""

from __future__ import annotations

import logging

logger = logging.getLogger("analytics")

EVENT_NAMES = frozenset(
    {
        "story_share",
        "share_channel",
        "notification_received",
        "notification_open",
        "notification_skipped_due_to_quiet_hours",
        "notification_suppressed_by_daily_cap",
        "notification_failed",
    }
)


def track(event: str, properties: dict | None = None, **kwargs: object) -> None:
    if event not in EVENT_NAMES:
        raise ValueError(f"unknown analytics event: {event!r}")
    merged = {**(properties or {}), **kwargs}
    logger.info("%s", event, extra={"analytics_event": event, "analytics_properties": merged})
