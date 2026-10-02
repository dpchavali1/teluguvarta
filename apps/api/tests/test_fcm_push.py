"""FCM handoff tests with no live Google credentials or network."""

import json

import httpx

from app import push


def _enabled(monkeypatch):
    monkeypatch.setenv("PUSH_NOTIFICATIONS_ENABLED", "true")
    monkeypatch.setenv("FCM_PROJECT_ID", "theteluguedit-app")
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "/tmp/test-service-account.json")
    monkeypatch.setattr(push, "_access_token", lambda: "test-oauth-token")


def _client(monkeypatch, handler):
    real_client = httpx.Client
    monkeypatch.setattr(push.httpx, "Client", lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs))


def test_fcm_success_sends_string_data_and_omits_null(monkeypatch):
    _enabled(monkeypatch)

    def handler(request):
        assert request.url.path == "/v1/projects/theteluguedit-app/messages:send"
        assert request.headers["Authorization"] == "Bearer test-oauth-token"
        payload = json.loads(request.content)["message"]
        assert payload["token"] == "fcm-token"
        assert payload["data"] == {"type": "TOPIC_ALERT", "count": "2"}
        return httpx.Response(200, json={"name": "projects/test/messages/123"})

    _client(monkeypatch, handler)
    result = push.send_push(["fcm-token"], title="Hello", body="World", data={"type": "TOPIC_ALERT", "count": 2, "story_slug": None})
    assert result.ok and result.detail == "SENT"


def test_unregistered_token_is_invalid_and_not_sent(monkeypatch):
    _enabled(monkeypatch)
    _client(monkeypatch, lambda request: httpx.Response(404, json={"error": {"details": [{"errorCode": "UNREGISTERED"}]}}))
    result = push.send_push(["stale-token"], title="Hello", body="World", data={})
    assert not result.ok
    assert result.invalid_tokens == ("stale-token",)


def test_provider_failure_stays_retryable_and_does_not_retire_token(monkeypatch):
    _enabled(monkeypatch)
    _client(monkeypatch, lambda request: httpx.Response(503, json={"error": {"status": "UNAVAILABLE"}}))
    result = push.send_push(["fcm-token"], title="Hello", body="World", data={})
    assert not result.ok and result.detail == "FCM_HTTP_503"
    assert result.invalid_tokens == ()


def test_legacy_expo_tokens_are_not_sent_to_fcm(monkeypatch):
    _enabled(monkeypatch)
    result = push.send_push(["ExponentPushToken[old]"], title="Hello", body="World", data={})
    assert not result.ok and result.invalid_tokens == ("ExponentPushToken[old]",)


def test_kill_switch_blocks_delivery(monkeypatch):
    monkeypatch.setenv("PUSH_NOTIFICATIONS_ENABLED", "false")
    result = push.send_push(["fcm-token"], title="Hello", body="World", data={})
    assert not result.ok and result.detail == "PUSH_DISABLED"
