"""FCM HTTP v1 gateway for the existing Postgres notification worker.

One Notification is a per-reader handoff: acceptance by any active device
completes it. Retrying after another device accepted it would duplicate that
reader's alert. Invalid registrations are returned for deactivation.
"""

from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime

import google.auth.exceptions
import google.auth.transport.requests
import httpx
from google.oauth2 import service_account

FCM_SCOPE = "https://www.googleapis.com/auth/firebase.messaging"


def _env_flag(name: str, *, default: bool) -> bool:
    return os.environ.get(name, str(default)).strip().lower() == "true"


@dataclass(frozen=True)
class PushSendResult:
    ok: bool
    detail: str
    invalid_tokens: tuple[str, ...] = ()


def push_enabled() -> bool:
    return (
        _env_flag("PUSH_NOTIFICATIONS_ENABLED", default=False)
        and bool(os.environ.get("FCM_PROJECT_ID"))
        and bool(os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"))
    )


ANDROID_CHANNEL_ID = "alerts"  # keep in sync with apps/mobile/src/push.ts
TOKEN_REFRESH_MARGIN_SECONDS = 300
_token_cache: dict[str, tuple[str, float]] = {}  # credential path -> (token, monotonic deadline)
_token_lock = threading.Lock()


def _access_token() -> str:
    """OAuth token cached until shortly before it expires (one fetch per ~hour,
    not one per send)."""

    path = os.environ["GOOGLE_APPLICATION_CREDENTIALS"]
    with _token_lock:
        cached = _token_cache.get(path)
        if cached is not None and time.monotonic() < cached[1]:
            return cached[0]
        credentials = service_account.Credentials.from_service_account_file(path, scopes=[FCM_SCOPE])
        credentials.refresh(google.auth.transport.requests.Request())
        if not credentials.token:
            raise ValueError("FCM credential refresh returned no token")
        lifetime = 3600.0
        if credentials.expiry is not None:
            lifetime = (credentials.expiry - datetime.now(UTC).replace(tzinfo=None)).total_seconds()
        token = str(credentials.token)
        _token_cache[path] = (token, time.monotonic() + lifetime - TOKEN_REFRESH_MARGIN_SECONDS)
        return token


def send_push(tokens: list[str], *, title: str, body: str, data: dict) -> PushSendResult:
    # Native registration replaces these legacy Expo tokens.
    fcm_tokens = [token for token in dict.fromkeys(tokens) if not token.startswith("ExponentPushToken[")]
    invalid = [token for token in tokens if token.startswith("ExponentPushToken[")]
    if not fcm_tokens:
        return PushSendResult(False, "NO_FCM_TOKENS", tuple(invalid))
    if not push_enabled():
        return PushSendResult(False, "PUSH_DISABLED", tuple(invalid))

    try:
        access_token = _access_token()
    except (OSError, ValueError, google.auth.exceptions.GoogleAuthError):
        return PushSendResult(False, "FCM_AUTH_ERROR", tuple(invalid))

    project_id = os.environ["FCM_PROJECT_ID"]
    url = f"https://fcm.googleapis.com/v1/projects/{project_id}/messages:send"
    accepted = 0
    errors: list[str] = []
    # FCM data values must be strings; omit absent deep-link values.
    safe_data = {key: str(value) for key, value in data.items() if value is not None}
    with httpx.Client(timeout=10.0) as client:
        for token in fcm_tokens:
            try:
                response = client.post(
                    url,
                    json={"message": {"token": token, "notification": {"title": title, "body": body}, "data": safe_data, "android": {"notification": {"channel_id": ANDROID_CHANNEL_ID}}}},
                    headers={"Authorization": f"Bearer {access_token}"},
                )
            except httpx.HTTPError:
                errors.append("FCM_NETWORK_ERROR")
                continue
            if response.status_code == 200 and _accepted(response):
                accepted += 1
            elif _token_is_dead(response):
                invalid.append(token)
            else:
                errors.append(f"FCM_HTTP_{response.status_code}")

    if accepted:
        return PushSendResult(True, "SENT" if not errors else "PARTIAL_DEVICE_FAILURE", tuple(invalid))
    return PushSendResult(False, errors[0] if errors else "NO_VALID_TOKENS", tuple(invalid))


def _token_is_dead(response: httpx.Response) -> bool:
    """FCM v1 says the registration token itself is bad: 404 UNREGISTERED,
    403 SENDER_ID_MISMATCH (token belongs to another project), or 400
    INVALID_ARGUMENT whose field violation names the token. Generic 400/401/
    403/5xx never retire a token (they are request, credential or outage)."""

    if response.status_code not in (400, 403, 404):
        return False
    try:
        error = response.json().get("error", {})
    except ValueError:
        return False
    if not isinstance(error, dict):
        return False
    details = [d for d in error.get("details", []) if isinstance(d, dict)]
    codes = {d.get("errorCode") for d in details}
    if response.status_code == 404:
        return "UNREGISTERED" in codes
    if response.status_code == 403:
        return "SENDER_ID_MISMATCH" in codes
    if error.get("status") != "INVALID_ARGUMENT" and "INVALID_ARGUMENT" not in codes:
        return False
    for detail in details:
        for violation in detail.get("fieldViolations", []) or []:
            if isinstance(violation, dict) and "message.token" in str(violation.get("field", "")):
                return True
    return False


def _accepted(response: httpx.Response) -> bool:
    try:
        return bool(response.json().get("name"))
    except ValueError:
        return False
