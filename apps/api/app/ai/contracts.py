"""§7.3 structured output contract — the schema every generation-task
response is validated against before any caller may trust it.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, ValidationError

__all__ = ["Claim", "GenerationResult", "TranslationResult", "ValidationError"]


class Claim(BaseModel):
    text: str
    source_refs: list[str] = Field(default_factory=list)


class GenerationResult(BaseModel):
    relevant: bool
    confidence: float = Field(ge=0.0, le=1.0)
    categories: list[str] = Field(default_factory=list)
    countries: list[str] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)
    sensitivity: str
    urgency: str
    # Added by T11: ADR-002 requires every published story to carry an
    # AI-drafted *original* headline — never the source's own headline text
    # — and `story_variants.headline` is NOT NULL, but §7.3's contract as T10
    # implemented it had no field for one. Required (no default) so a
    # generation call that omits it fails schema validation and holds,
    # exactly like a missing summary_en would, rather than silently landing
    # an empty headline.
    headline_en: str
    summary_en: str
    why_matters_en: str
    claims: list[Claim] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)
    publish_recommendation: str


class TranslationResult(BaseModel):
    """§7.3 contract for `Task.TRANSLATION_EN_TE` — deliberately not
    `GenerationResult`: a translation has no relevance/confidence/claims of
    its own, it's a rendering of an already-approved English variant."""

    headline_te: str
    summary_te: str
    why_matters_te: str | None = None
