"""Provider interface. Every concrete provider (openai_provider.py,
anthropic_provider.py, null_provider.py) implements this — the gateway
(`app/ai/gateway.py`) only ever talks to this shape, never a provider SDK
directly. This file itself imports no SDK.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from pydantic import BaseModel

if TYPE_CHECKING:
    from app.ai.tasks import Task


class ProviderResponse(BaseModel):
    output: dict
    tokens_in: int
    tokens_out: int


class ProviderUnavailableError(RuntimeError):
    """Raised when a provider can't be reached or isn't configured. Callers
    must queue the work for later, per §7.5 — never invent content."""


class Provider(Protocol):
    name: str

    def complete(
        self, *, model: str, task: Task, prompt: str, constrained: bool = False
    ) -> ProviderResponse: ...
