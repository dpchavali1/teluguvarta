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
# Free-tier limits (plan [R7]): Flash is 20 RPD, Flash Lite 500 RPD, so bulk
# tasks must route to GEMINI_FLASH_LITE; GEMINI_FLASH is opt-in only.
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

# ADR-015: routes used ONLY for a story whose persisted privacy decision is
# FREE_TIER_ALLOWED, and only while AI_FREE_TIER_ENABLED is set. Everything
# else keeps its ROUTING entry above; a non-allowed story is never sent here.
FREE_TIER_ROUTING: dict[Task, TaskRoute] = {
    task: TaskRoute(provider="gemini", default_model=GEMINI_FLASH_LITE)
    for task in (Task.RELEVANCE_CATEGORIZATION, Task.SUMMARY, Task.TRANSLATION_EN_TE)
}


def free_tier_enabled() -> bool:
    return os.environ.get("AI_FREE_TIER_ENABLED", "").strip().lower() in ("1", "true", "yes")


def adr001_provider_configured() -> bool:
    return bool(os.environ.get("AI_OPENAI_API_KEY") or os.environ.get("AI_ANTHROPIC_API_KEY"))


def paid_gemini_configured() -> bool:
    return bool(os.environ.get("AI_GEMINI_PAID_API_KEY"))


def paid_provider_configured() -> bool:
    return adr001_provider_configured() or paid_gemini_configured()


# ADR-018: the billed Gemini project, used only when no ADR-001 key is set
# (see `route_for`). Pinned ids, never `-latest` aliases, so each call's
# price and the Telugu-quality evidence refer to one model.
GEMINI_PAID_FLASH = os.environ.get("AI_GEMINI_PAID_FLASH_MODEL") or "gemini-3.8-flash"
GEMINI_PAID_FLASH_LITE = os.environ.get("AI_GEMINI_PAID_FLASH_LITE_MODEL") or "gemini-3.5-flash-lite"

PAID_GEMINI_ROUTING: dict[Task, TaskRoute] = {
    **{
        task: TaskRoute(
            provider="gemini_paid", default_model=GEMINI_PAID_FLASH_LITE,
            escalation_provider="gemini_paid", escalation_model=GEMINI_PAID_FLASH,
        )
        for task in (Task.RELEVANCE_CATEGORIZATION, Task.SUMMARY, Task.WHY_MATTERS, Task.TRANSLATION_EN_TE)
    },
    Task.SENSITIVE_VALIDATION: TaskRoute(
        provider="gemini_paid", default_model=GEMINI_PAID_FLASH, always_human_review=True,
    ),
}


def route_for(task: Task, *, free_tier_allowed: bool) -> TaskRoute:
    """ADR-015 free tier first for an allowed story, then ADR-001's ROUTING
    when an OpenAI/Anthropic key is set, else the ADR-018 paid Gemini route."""
    if free_tier_allowed and task in FREE_TIER_ROUTING and free_tier_enabled():
        return FREE_TIER_ROUTING[task]
    if not adr001_provider_configured() and paid_gemini_configured() and task in PAID_GEMINI_ROUTING:
        return PAID_GEMINI_ROUTING[task]
    return ROUTING[task]


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
    # Free tier: $0 billed.
    "gemini-flash-latest": ModelPricing(0.0, 0.0),
    "gemini-flash-lite-latest": ModelPricing(0.0, 0.0),
}

# ADR-018: the same model ids cost money on the billed project, so paid
# Gemini is priced from its own table. From ai.google.dev/gemini-api/docs/pricing
# (2026-09-29, standard text). 3.8 Flash uses its 2027 list price, not the
# lower 2026 promo, so the budget gate over-counts rather than under-counts.
PAID_GEMINI_PRICING: dict[str, ModelPricing] = {
    "gemini-3.5-flash-lite": ModelPricing(0.0003, 0.0025),
    "gemini-3.8-flash": ModelPricing(0.0015, 0.0075),
}


def pricing_for(provider: str | None, model: str | None) -> ModelPricing | None:
    table = PAID_GEMINI_PRICING if provider == "gemini_paid" else MODEL_PRICING
    return table.get(model or "")


def cost_usd(model: str | None, tokens_in: int, tokens_out: int, *, provider: str | None = None) -> float:
    pricing = pricing_for(provider, model)
    if pricing is None:
        return 0.0
    return round(
        tokens_in / 1000 * pricing.input_per_1k_usd + tokens_out / 1000 * pricing.output_per_1k_usd,
        6,
    )
