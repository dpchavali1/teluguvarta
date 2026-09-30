"""OpenAI adapter — the only file besides anthropic_provider.py allowed to
import the `openai` SDK (CI grep check enforces this; see ADR-001).
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from app.ai.providers.base import (
    ProviderResponse,
    ProviderUnavailableError,
    parse_json_output,
)

if TYPE_CHECKING:
    from app.ai.tasks import Task

CONSTRAINED_SUFFIX = (
    "\n\nReturn ONLY valid JSON matching the required schema exactly — no "
    "prose, no markdown fences, no extra keys."
)


class OpenAiProvider:
    name = "openai"

    def __init__(self) -> None:
        api_key = os.environ.get("AI_OPENAI_API_KEY")
        if not api_key:
            raise ProviderUnavailableError("AI_OPENAI_API_KEY not set")
        import openai  # imported here, and only here besides tests, per ADR-001

        self._client = openai.OpenAI(api_key=api_key)

    def complete(
        self, *, model: str, task: Task, prompt: str, constrained: bool = False
    ) -> ProviderResponse:
        text = prompt + (CONSTRAINED_SUFFIX if constrained else "")
        response = self._client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": text}],
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content or "{}"
        usage = response.usage
        output, failure = parse_json_output(content)
        return ProviderResponse(
            output=output,
            tokens_in=getattr(usage, "prompt_tokens", 0) or 0,
            tokens_out=getattr(usage, "completion_tokens", 0) or 0,
            failure=failure,
        )
