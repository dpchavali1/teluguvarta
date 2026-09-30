"""Gemini adapter — talks to the Gemini REST API over httpx, so unlike
openai_provider.py/anthropic_provider.py it needs no provider SDK.

NOT in `ROUTING` (app/ai/tasks.py). The free tier may use prompts/responses
to improve Google's products, so `gemini` is reachable only via
FREE_TIER_ROUTING behind ADR-015's privacy gate. `gemini_paid` (ADR-018) is
reachable only via PAID_GEMINI_ROUTING.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import httpx

from app.ai.providers.base import (
    ProviderQuotaError,
    ProviderResponse,
    ProviderUnavailableError,
    parse_json_output,
)

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
    key_env = "AI_GEMINI_API_KEY"

    def __init__(self) -> None:
        api_key = os.environ.get(self.key_env)
        if not api_key:
            raise ProviderUnavailableError(f"{self.key_env} not set")
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
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429:
                raise ProviderQuotaError("Gemini quota exhausted (429)") from exc
            raise ProviderUnavailableError(f"Gemini request failed: HTTP {exc.response.status_code}") from exc
        except httpx.HTTPError as exc:
            # 429 (free-tier quota) and 5xx land here: queue for later, per §7.5.
            raise ProviderUnavailableError(f"Gemini request failed: {type(exc).__name__}") from exc
        try:
            body = response.json()
        except ValueError:
            body = {}
        usage = body.get("usageMetadata") or {}
        # Review 2026-09-29 #3: thinking tokens are billed at the output rate
        # but reported apart from candidatesTokenCount. Cached input is part of
        # promptTokenCount; it's priced at the full rate (an overestimate).
        thinking = usage.get("thoughtsTokenCount", 0) or 0
        output, failure = _parse_body(body)
        return ProviderResponse(
            output=output,
            tokens_in=usage.get("promptTokenCount", 0) or 0,
            tokens_out=(usage.get("candidatesTokenCount", 0) or 0) + thinking,
            tokens_thinking=thinking,
            tokens_cached=usage.get("cachedContentTokenCount", 0) or 0,
            failure=failure,
        )


# finishReason values meaning the model's answer was withheld, not truncated.
_BLOCKED_FINISH_REASONS = frozenset(
    {"SAFETY", "RECITATION", "BLOCKLIST", "PROHIBITED_CONTENT", "SPII", "IMAGE_SAFETY"}
)


def _parse_body(body: dict) -> tuple[dict, str | None]:
    if (body.get("promptFeedback") or {}).get("blockReason"):
        return {}, "BLOCKED"
    try:
        candidate = body["candidates"][0]
    except (KeyError, IndexError, TypeError):
        return {}, "BLOCKED"  # no candidate at all: nothing was returned
    if candidate.get("finishReason") in _BLOCKED_FINISH_REASONS:
        return {}, "BLOCKED"
    parts = (candidate.get("content") or {}).get("parts") or []
    content = "".join(p.get("text", "") for p in parts if isinstance(p, dict) and not p.get("thought"))
    return parse_json_output(content)


class PaidGeminiProvider(GeminiProvider):
    """ADR-018: the same API on a separate, billed Cloud project. Billing is
    per project, so this key's calls are all paid tier (not used for
    training), and they're logged and priced as `gemini_paid`."""

    name = "gemini_paid"
    key_env = "AI_GEMINI_PAID_API_KEY"
