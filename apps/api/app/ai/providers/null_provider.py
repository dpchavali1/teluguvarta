"""Fallback provider used whenever a real provider has no API key configured
(local dev, CI, this sandbox) — every call surfaces the §7.5 "model
unavailable" failure mode through the real gateway code path instead of a
mock, without ever making a network call.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.ai.providers.base import ProviderResponse, ProviderUnavailableError

if TYPE_CHECKING:
    from app.ai.tasks import Task


class NullProvider:
    name = "none"

    def complete(
        self, *, model: str, task: Task, prompt: str, constrained: bool = False
    ) -> ProviderResponse:
        raise ProviderUnavailableError(f"no AI provider configured for model={model!r}")
