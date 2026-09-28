"""§7.2 model routing table — the only place default/escalation models are
named. Everything else (gateway, job handlers) reads this table instead of
naming a model directly, so swapping a provider/model touches one file.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum


class Task(str, Enum):
    LANGUAGE_DETECTION = "language_detection"
    RELEVANCE_CATEGORIZATION = "relevance_categorization"
    DEDUP_CLUSTER_ESCALATION = "dedup_cluster_escalation"
    SUMMARY = "summary"
    WHY_MATTERS = "why_matters"
    TRANSLATION_EN_TE = "translation_en_te"
    SENSITIVE_VALIDATION = "sensitive_validation"


# Gemini model names are aliases Google re-points as Flash versions ship and
# retire, so nothing here needs editing on a version change. Set the env var
# to a pinned id (e.g. gemini-3.8-flash) when an eval needs a frozen model.
GEMINI_FLASH = os.environ.get("AI_GEMINI_FLASH_MODEL") or "gemini-flash-latest"
GEMINI_FLASH_LITE = os.environ.get("AI_GEMINI_FLASH_LITE_MODEL") or "gemini-flash-lite-latest"


@dataclass(frozen=True)
class TaskRoute:
    provider: str | None  # None => deterministic, no provider call at all
    default_model: str | None
    escalation_provider: str | None = None
    escalation_model: str | None = None
    # §7.2: sensitive validation always goes to human review in V1
    # regardless of model confidence.
    always_human_review: bool = False


# Per ADR-001: OpenAI primary, Anthropic secondary (translation's
# second-provider escalation leg, and sensitive validation's reasoning
# model, so a single-vendor outage/policy change can't take out the whole
# pipeline).
ROUTING: dict[Task, TaskRoute] = {
    Task.LANGUAGE_DETECTION: TaskRoute(provider=None, default_model=None),
    Task.RELEVANCE_CATEGORIZATION: TaskRoute(
        provider="openai", default_model="gpt-4o-mini",
        escalation_provider="openai", escalation_model="gpt-4o",
    ),
    Task.DEDUP_CLUSTER_ESCALATION: TaskRoute(
        provider="openai", default_model="text-embedding-3-small",
    ),
    Task.SUMMARY: TaskRoute(
        provider="openai", default_model="gpt-4o-mini",
        escalation_provider="openai", escalation_model="gpt-4o",
    ),
    Task.WHY_MATTERS: TaskRoute(
        provider="openai", default_model="gpt-4o-mini",
        escalation_provider="openai", escalation_model="gpt-4o",
    ),
    Task.TRANSLATION_EN_TE: TaskRoute(
        provider="openai", default_model="gpt-4o-mini",
        escalation_provider="anthropic", escalation_model="claude-3-5-sonnet-20241022",
    ),
    Task.SENSITIVE_VALIDATION: TaskRoute(
        provider="anthropic", default_model="claude-3-5-sonnet-20241022",
        always_human_review=True,
    ),
}

# Tasks that degrade to "classification-only mode" (§7.5) once the monthly
# AI budget is breached: generation tasks producing publishable content are
# skipped; relevance/categorization and dedup escalation (needed just to
# keep the pipeline classifying/triaging incoming items) still run.
DEGRADABLE_ON_BUDGET_BREACH: frozenset[Task] = frozenset(
    {Task.SUMMARY, Task.WHY_MATTERS, Task.TRANSLATION_EN_TE}
)


@dataclass(frozen=True)
class ModelPricing:
    input_per_1k_usd: float
    output_per_1k_usd: float


# Best-effort figures, not billed rates — see ADR-001 Consequences.
MODEL_PRICING: dict[str, ModelPricing] = {
    "gpt-4o-mini": ModelPricing(0.00015, 0.0006),
    "gpt-4o": ModelPricing(0.0025, 0.01),
    "text-embedding-3-small": ModelPricing(0.00002, 0.0),
    "claude-3-5-sonnet-20241022": ModelPricing(0.003, 0.015),
    # Free tier: $0 billed. Paid-tier rates to be added by ADR-011.
    "gemini-flash-latest": ModelPricing(0.0, 0.0),
    "gemini-flash-lite-latest": ModelPricing(0.0, 0.0),
}


def cost_usd(model: str | None, tokens_in: int, tokens_out: int) -> float:
    pricing = MODEL_PRICING.get(model or "")
    if pricing is None:
        return 0.0
    return round(
        tokens_in / 1000 * pricing.input_per_1k_usd + tokens_out / 1000 * pricing.output_per_1k_usd,
        6,
    )
