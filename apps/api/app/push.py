"""Push delivery via Expo's push API (§10.1: "FCM/APNs via Expo/React
Native tooling" — Expo's service is the single endpoint that fans out to
both platforms, so the gateway here talks to Expo, not FCM/APNs directly).

Mirrors the T10 AI gateway's shape: a `send()` result the caller (T17's
`notification_dispatch` job) can act on without knowing about `httpx` or
Expo's response format, and a "disabled" mode (kill switch off, or no
access token configured) that degrades to "nothing sent" instead of
raising, matching every other §15 kill-switch precedent in this repo.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import httpx

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"


def _env_flag(name: str, *, default: bool) -> bool:
    return os.environ.get(name, str(default)).strip().lower() == "true"


@dataclass(frozen=True)
class PushSendResult:
    ok: bool
    detail: str


def push_enabled() -> bool:
    return _env_flag("PUSH_NOTIFICATIONS_ENABLED", default=False) and bool(
        os.environ.get("EXPO_PUSH_ACCESS_TOKEN")
    )


def send_push(tokens: list[str], *, title: str, body: str, data: dict) -> PushSendResult:
    if not tokens:
        return PushSendResult(ok=False, detail="NO_TOKENS")
    if not push_enabled():
        return PushSendResult(ok=False, detail="PUSH_DISABLED")

    access_token = os.environ["EXPO_PUSH_ACCESS_TOKEN"]
    messages = [{"to": token, "title": title, "body": body, "data": data} for token in tokens]
    try:
        response = httpx.post(
            EXPO_PUSH_URL,
            json=messages,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            timeout=10.0,
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        return PushSendResult(ok=False, detail=f"EXPO_ERROR: {exc}")
    return PushSendResult(ok=True, detail="SENT")
