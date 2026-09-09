"""T18: the §17 core event list is posted through the same `POST /v1/events`
endpoint T17 already built (apps/mobile's `trackEvent`, and now apps/web's
`track()`), and `app.analytics.track` forwards to PostHog when configured.
No real Postgres/DB dependency — this endpoint and module don't touch the
database.
"""

import json

import httpx
from fastapi.testclient import TestClient

from app import analytics
from app.main import app

client = TestClient(app)

CORE_EVENTS = [
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
]


def test_every_core_event_is_accepted_by_the_events_endpoint():
    for event in CORE_EVENTS:
        response = client.post("/v1/events", json={"event": event, "properties": {"k": "v"}})
        assert response.status_code == 200, f"{event} was rejected: {response.json()}"
        assert response.json() == {"accepted": True}


def test_unknown_event_name_is_rejected_by_schema_validation():
    response = client.post("/v1/events", json={"event": "not_a_real_event"})
    assert response.status_code == 422


def test_track_rejects_event_not_in_analytics_event_names():
    try:
        analytics.track("not_a_real_event")
        raised = False
    except ValueError:
        raised = True
    assert raised


def test_track_is_a_safe_noop_without_posthog_api_key(monkeypatch):
    monkeypatch.delenv("POSTHOG_API_KEY", raising=False)
    analytics.track("app_open", {"platform": "web"})


def test_track_forwards_to_posthog_when_configured(monkeypatch):
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content)
        return httpx.Response(200)

    monkeypatch.setenv("POSTHOG_API_KEY", "test-key")
    monkeypatch.setattr(
        analytics.httpx, "post",
        lambda url, json, timeout: handler(httpx.Request("POST", url, json=json)),
    )

    analytics.track("story_open", {"story_id": "abc"})

    assert captured["url"] == "https://us.i.posthog.com/capture/"
    assert captured["body"]["event"] == "story_open"
    assert captured["body"]["api_key"] == "test-key"
    assert captured["body"]["properties"]["story_id"] == "abc"


def _capture_posthog_body(monkeypatch) -> dict:
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(200)

    monkeypatch.setenv("POSTHOG_API_KEY", "test-key")
    monkeypatch.setattr(
        analytics.httpx, "post",
        lambda url, json, timeout: handler(httpx.Request("POST", url, json=json)),
    )
    return captured


def test_forward_uses_anon_id_as_distinct_id_when_no_user_id(monkeypatch):
    captured = _capture_posthog_body(monkeypatch)
    analytics.track("story_open", {"story_id": "abc", "anon_id": "device-123"})
    assert captured["body"]["distinct_id"] == "device-123"


def test_forward_prefers_user_id_over_anon_id_as_distinct_id(monkeypatch):
    captured = _capture_posthog_body(monkeypatch)
    analytics.track("notification_open", {"user_id": "user-1", "anon_id": "device-123"})
    assert captured["body"]["distinct_id"] == "user-1"


def test_forward_falls_back_to_unknown_distinct_id_without_any_id(monkeypatch):
    captured = _capture_posthog_body(monkeypatch)
    analytics.track("app_open", {})
    assert captured["body"]["distinct_id"] == "unknown"


def test_report_issue_description_is_never_forwarded_to_posthog(monkeypatch):
    captured = _capture_posthog_body(monkeypatch)
    analytics.track("report_issue", {"story_id": "abc", "description": "call me at 555-1234"})
    assert "description" not in captured["body"]["properties"]
    assert captured["body"]["properties"]["story_id"] == "abc"
