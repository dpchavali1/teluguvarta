"""Provider interface. Every concrete provider (openai_provider.py,
anthropic_provider.py, null_provider.py) implements this — the gateway
(`app/ai/gateway.py`) only ever talks to this shape, never a provider SDK
directly. This file itself imports no SDK.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Protocol

from pydantic import BaseModel

if TYPE_CHECKING:
    from app.ai.tasks import Task


class ProviderResponse(BaseModel):
    output: dict
    tokens_in: int
    # Billed output tokens, including any thinking tokens.
    tokens_out: int
    tokens_thinking: int = 0
    tokens_cached: int = 0
    # Set when the provider answered (and billed) but gave no usable JSON:
    # 'PARSE_ERROR' or 'BLOCKED'. `output` is then `{}`, which fails schema
    # validation in the gateway, so usage is still recorded (review #3).
    failure: str | None = None


def parse_json_output(content: str | None) -> tuple[dict, str | None]:
    """Parses a provider's JSON text without raising, so a malformed reply
    still reaches the gateway with its usage attached."""
    try:
        output = json.loads(content or "")
    except (json.JSONDecodeError, TypeError):
        return {}, "PARSE_ERROR"
    if not isinstance(output, dict):
        return {}, "PARSE_ERROR"
    return output, None


class ProviderUnavailableError(RuntimeError):
    """Raised when a provider can't be reached or isn't configured. Callers
    must queue the work for later, per §7.5 — never invent content."""


class ProviderQuotaError(ProviderUnavailableError):
    """The provider rejected the call for quota (HTTP 429). A deferral: the
    gateway records it and returns DEFERRED rather than counting a failure."""


class Provider(Protocol):
    name: str

    def complete(
        self, *, model: str, task: Task, prompt: str, constrained: bool = False
    ) -> ProviderResponse: ...
