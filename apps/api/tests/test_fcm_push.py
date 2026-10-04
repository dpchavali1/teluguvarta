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


def _retire_case(monkeypatch, status, body):
    _enabled(monkeypatch)
    _client(monkeypatch, lambda request: httpx.Response(status, json=body))
    return push.send_push(["tok"], title="t", body="b", data={})


def test_invalid_argument_on_token_field_retires_token(monkeypatch):
    body = {"error": {"status": "INVALID_ARGUMENT", "details": [
        {"@type": "type.googleapis.com/google.rpc.BadRequest", "fieldViolations": [{"field": "message.token"}]}]}}
    assert _retire_case(monkeypatch, 400, body).invalid_tokens == ("tok",)


def test_invalid_argument_on_other_field_does_not_retire_token(monkeypatch):
    body = {"error": {"status": "INVALID_ARGUMENT", "details": [{"fieldViolations": [{"field": "message.data"}]}]}}
    result = _retire_case(monkeypatch, 400, body)
    assert result.invalid_tokens == () and result.detail == "FCM_HTTP_400"


def test_sender_id_mismatch_retires_token(monkeypatch):
    assert _retire_case(monkeypatch, 403, {"error": {"details": [{"errorCode": "SENDER_ID_MISMATCH"}]}}).invalid_tokens == ("tok",)


def test_plain_403_does_not_retire_token(monkeypatch):
    assert _retire_case(monkeypatch, 403, {"error": {"status": "PERMISSION_DENIED"}}).invalid_tokens == ()


def test_auth_error_does_not_retire_token(monkeypatch):
    assert _retire_case(monkeypatch, 401, {"error": {"status": "UNAUTHENTICATED"}}).invalid_tokens == ()


def test_payload_sets_android_channel_id(monkeypatch):
    _enabled(monkeypatch)
    seen = {}

    def handler(request):
        seen.update(json.loads(request.content)["message"])
        return httpx.Response(200, json={"name": "x"})

    _client(monkeypatch, handler)
    push.send_push(["tok"], title="t", body="b", data={})
    assert seen["android"]["notification"]["channel_id"] == "alerts"


def test_access_token_is_cached_until_near_expiry(monkeypatch):
    from datetime import UTC, datetime, timedelta

    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "/tmp/cache-test.json")
    push._token_cache.clear()
    fetches = []

    class FakeCreds:
        def __init__(self):
            self.token, self.expiry = None, None

        def refresh(self, _request):
            fetches.append(1)
            self.token = f"tok-{len(fetches)}"
            self.expiry = (datetime.now(UTC) + timedelta(seconds=3600)).replace(tzinfo=None)

    monkeypatch.setattr(push.service_account.Credentials, "from_service_account_file", lambda *a, **k: FakeCreds())
    assert push._access_token() == "tok-1"
    assert push._access_token() == "tok-1" and len(fetches) == 1
    clock = push.time.monotonic()
    monkeypatch.setattr(push.time, "monotonic", lambda: clock + 3400)  # inside the 5-minute margin
    assert push._access_token() == "tok-2" and len(fetches) == 2
    push._token_cache.clear()
