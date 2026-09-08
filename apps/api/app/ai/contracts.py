"""§7.3 structured output contract — the schema every generation-task
response is validated against before any caller may trust it.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, ValidationError

__all__ = ["Claim", "GenerationResult", "ValidationError"]


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
    summary_en: str
    why_matters_en: str
    claims: list[Claim] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)
    publish_recommendation: str
