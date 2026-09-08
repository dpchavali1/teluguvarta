"""Anthropic adapter — the only file besides openai_provider.py allowed to
import the `anthropic` SDK (CI grep check enforces this; see ADR-001).
"""

from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING

from app.ai.providers.base import ProviderResponse, ProviderUnavailableError

if TYPE_CHECKING:
    from app.ai.tasks import Task

CONSTRAINED_SUFFIX = (
    "\n\nReturn ONLY valid JSON matching the required schema exactly — no "
    "prose, no markdown fences, no extra keys."
)


class AnthropicProvider:
    name = "anthropic"

    def __init__(self) -> None:
        api_key = os.environ.get("AI_ANTHROPIC_API_KEY")
        if not api_key:
            raise ProviderUnavailableError("AI_ANTHROPIC_API_KEY not set")
        import anthropic  # imported here, and only here besides tests, per ADR-001

        self._client = anthropic.Anthropic(api_key=api_key)

    def complete(
        self, *, model: str, task: Task, prompt: str, constrained: bool = False
    ) -> ProviderResponse:
        text = prompt + (CONSTRAINED_SUFFIX if constrained else "")
        response = self._client.messages.create(
            model=model,
            max_tokens=2048,
            messages=[{"role": "user", "content": text}],
        )
        content = "".join(block.text for block in response.content if getattr(block, "type", None) == "text")
        return ProviderResponse(
            output=json.loads(content or "{}"),
            tokens_in=getattr(response.usage, "input_tokens", 0) or 0,
            tokens_out=getattr(response.usage, "output_tokens", 0) or 0,
        )
