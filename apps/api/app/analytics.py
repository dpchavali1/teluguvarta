"""§9.4/§17 analytics events (T17 client-observable events; T18 wires the
actual PostHog-or-equivalent sink). A structured log line is always
written — that's the deterministic, no-new-infrastructure record
NON_NEGOTIABLES asks for, and what T17's tests assert against directly
(caplog). T18 adds a best-effort forward to PostHog's plain HTTP capture
endpoint alongside it, gated on `POSTHOG_API_KEY` — no SDK dependency, and
a safe no-op when unset (local dev/CI never need a PostHog account).
"""

from __future__ import annotations

import logging
import os

import httpx

logger = logging.getLogger("analytics")

EVENT_NAMES = frozenset(
    {
        # §17 core list (T18) — one client-side event stream shared by
        # apps/web and apps/mobile, posted through POST /v1/events.
        "app_open",
        "feed_view",
        "story_open",
        "story_save",
        "story_share",
        "language_switch",
        "search",
        "notification_open",
        "notification_opt_in",
        "onboarding_complete",
        "account_delete_request",
        "report_issue",
        # Pre-T18 (T17) events, some client-posted and some server-only
        # (emitted directly by app/jobs/notify.py, never through the
        # client-facing endpoint — see AnalyticsEventName in app/schemas.py).
        "share_channel",
        "notification_received",
        "notification_skipped_due_to_quiet_hours",
        "notification_suppressed_by_daily_cap",
        "notification_failed",
        # T20 pre-build validation gate: landing-page opt-in, tracked
        # separately from the §17 in-product events above since it happens
        # before there's a product session at all.
        "pilot_signup_created",
    }
)


# Properties that stay in our own structured log (for editorial follow-up)
# but must never leave the system via the PostHog forward — `report_issue`'s
# `description` is free text a user can type anything into (name, email,
# phone number), unlike every other §17 event's structured ids.
_FORWARD_REDACT = {"report_issue": {"description"}}


def _forward_to_posthog(event: str, properties: dict) -> None:
    api_key = os.environ.get("POSTHOG_API_KEY")
    if not api_key:
        return
    host = os.environ.get("POSTHOG_HOST", "https://us.i.posthog.com")
    # PostHog's capture API requires a distinct_id to attribute an event to
    # a person/session — without one it rejects the event. Callers pass
    # either `user_id` (server-emitted events, e.g. app/jobs/notify.py) or
    # `anon_id` (client-emitted events — see apps/web/src/lib/analytics.ts
    # and apps/mobile/src/lib/api.ts, both of which mint and persist a
    # non-secret per-device id distinct from the ADR-006 auth token).
    distinct_id = properties.get("user_id") or properties.get("anon_id") or "unknown"
    redacted_keys = _FORWARD_REDACT.get(event, set())
    forwarded_properties = {k: v for k, v in properties.items() if k not in redacted_keys}
    try:
        httpx.post(
            f"{host}/capture/",
            json={
                "api_key": api_key,
                "event": event,
                "distinct_id": distinct_id,
                "properties": {**forwarded_properties, "$lib": "teluguvarta-api"},
            },
            timeout=5.0,
        )
    except httpx.HTTPError:
        logger.warning("failed to forward analytics event %s to PostHog", event)


def track(event: str, properties: dict | None = None, **kwargs: object) -> None:
    if event not in EVENT_NAMES:
        raise ValueError(f"unknown analytics event: {event!r}")
    merged = {**(properties or {}), **kwargs}
    logger.info("%s", event, extra={"analytics_event": event, "analytics_properties": merged})
    _forward_to_posthog(event, merged)
