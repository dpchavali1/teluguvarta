"""FCM HTTP v1 gateway for the existing Postgres notification worker.

One Notification is a per-reader handoff: acceptance by any active device
completes it. Retrying after another device accepted it would duplicate that
reader's alert. Invalid registrations are returned for deactivation.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

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


def _access_token() -> str:
    credentials = service_account.Credentials.from_service_account_file(
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"], scopes=[FCM_SCOPE]
    )
    credentials.refresh(google.auth.transport.requests.Request())
    if not credentials.token:
        raise ValueError("FCM credential refresh returned no token")
    return str(credentials.token)


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
                    json={"message": {"token": token, "notification": {"title": title, "body": body}, "data": safe_data}},
                    headers={"Authorization": f"Bearer {access_token}"},
                )
            except httpx.HTTPError:
                errors.append("FCM_NETWORK_ERROR")
                continue
            if response.status_code == 200 and _accepted(response):
                accepted += 1
            elif response.status_code == 404 and _unregistered(response):
                invalid.append(token)
            else:
                errors.append(f"FCM_HTTP_{response.status_code}")

    if accepted:
        return PushSendResult(True, "SENT" if not errors else "PARTIAL_DEVICE_FAILURE", tuple(invalid))
    return PushSendResult(False, errors[0] if errors else "NO_VALID_TOKENS", tuple(invalid))


def _unregistered(response: httpx.Response) -> bool:
    try:
        details = response.json().get("error", {}).get("details", [])
    except ValueError:
        return False
    return any(
        detail.get("errorCode") == "UNREGISTERED"
        for detail in details if isinstance(detail, dict)
    )


def _accepted(response: httpx.Response) -> bool:
    try:
        return bool(response.json().get("name"))
    except ValueError:
        return False
