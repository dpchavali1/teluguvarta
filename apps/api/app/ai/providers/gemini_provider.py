"""Gemini adapter — talks to the Gemini REST API over httpx, so unlike
openai_provider.py/anthropic_provider.py it needs no provider SDK.

NOT wired into `ROUTING` (app/ai/tasks.py). The Gemini free tier may use
prompts/responses to improve Google's products, so routing any task to it
is an ADR-011 decision (docs/plans/gemini-hetzner-telugu-plan.md §4) that
must land together with a pre-call privacy gate; until then this adapter is
only reachable by naming provider="gemini" explicitly.
"""

from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING

import httpx

from app.ai.providers.base import ProviderResponse, ProviderUnavailableError

if TYPE_CHECKING:
    from app.ai.tasks import Task

BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
TIMEOUT_SECONDS = 60.0
CONSTRAINED_SUFFIX = (
    "\n\nReturn ONLY valid JSON matching the required schema exactly — no "
    "prose, no markdown fences, no extra keys."
)


class GeminiProvider:
    name = "gemini"

    def __init__(self) -> None:
        api_key = os.environ.get("AI_GEMINI_API_KEY")
        if not api_key:
            raise ProviderUnavailableError("AI_GEMINI_API_KEY not set")
        self._api_key = api_key

    def complete(
        self, *, model: str, task: Task, prompt: str, constrained: bool = False
    ) -> ProviderResponse:
        text = prompt + (CONSTRAINED_SUFFIX if constrained else "")
        try:
            response = httpx.post(
                f"{BASE_URL}/models/{model}:generateContent",
                headers={"x-goog-api-key": self._api_key},
                json={
                    "contents": [{"role": "user", "parts": [{"text": text}]}],
                    "generationConfig": {"responseMimeType": "application/json"},
                },
                timeout=TIMEOUT_SECONDS,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            # 429 (free-tier quota) and 5xx land here: queue for later, per §7.5.
            raise ProviderUnavailableError(f"Gemini request failed: {type(exc).__name__}") from exc
        body = response.json()
        try:
            parts = body["candidates"][0]["content"]["parts"]
            content = "".join(p.get("text", "") for p in parts if not p.get("thought")) or "{}"
        except (KeyError, IndexError, TypeError):
            content = "{}"  # blocked/empty candidate: gateway's schema check handles it
        usage = body.get("usageMetadata", {})
        return ProviderResponse(
            output=json.loads(content),
            tokens_in=usage.get("promptTokenCount", 0) or 0,
            tokens_out=usage.get("candidatesTokenCount", 0) or 0,
        )
