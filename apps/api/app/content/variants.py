"""§4.2 English-canonical/Telugu-derived fallback: given the variants a
story actually has, decide which one to serve for a requested language.
Pure function, no DB access — callers (T14's public API, T12's admin detail
view) hand it whatever `StoryVariant` rows they already loaded.

The public `/v1/stories/{slug}` endpoint itself is still T04 stub data
(wiring it to real rows is T14's "Web MVP" job per `docs/BUILD_ORDER.md`);
this is the resolver T14 must call once it does, so the fallback rule is
implemented and tested once here rather than reinvented per caller.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.privacy import PrivacyDecision, coerce, tighten
from app.models import Correction, Story, StoryVariant
from app.schemas import Language

# `StoryVariant.model_version` for text an editor wrote in admin rather than a
# model generated. Editor-authored copy is staff pre-publication text, so the
# translation job never sends it to the free tier (ADR-015).
EDITOR_MODEL_VERSION = "editor"


def dispatch_privacy(db: Session, story: Story, en: StoryVariant) -> tuple[PrivacyDecision, bool]:
    """ADR-015 routing inputs for an AI call over a story's English text:
    the persisted decision (tightened for a sensitive story) and whether the
    text is editor-authored — written in admin or touched by a correction —
    which never goes to the free tier."""
    decision = coerce(story.privacy_decision)
    if story.sensitivity != "NONE":
        decision = tighten(decision, PrivacyDecision.RESTRICTED)
    editor_authored = en.model_version == EDITOR_MODEL_VERSION or (
        db.scalars(select(Correction.id).where(Correction.story_id == story.id)).first() is not None
    )
    return decision, editor_authored


class VariantLike(Protocol):
    language: str
    qa_status: str
    headline: str
    summary: str


@dataclass(frozen=True)
class ResolvedVariant:
    variant: VariantLike
    served_language: Language
    fallback: bool


def resolve_display_variant(
    variants: dict[str, VariantLike], requested: Language
) -> ResolvedVariant | None:
    """English is canonical, so a request for `en` never falls back further
    within this function — if there's no `en` variant at all, there's
    nothing to serve (a story is required to have one by the time it's
    published; see T11/T12). A request for `te` falls back to `en` when the
    Telugu variant is missing or failed QA (§4.2/§4.3) rather than serving
    broken or absent translated text."""
    en = variants.get("en")

    if requested == "en":
        return ResolvedVariant(en, "en", fallback=False) if en is not None else None

    te = variants.get("te")
    if te is not None and te.qa_status == "PASSED":
        return ResolvedVariant(te, "te", fallback=False)

    if en is not None:
        return ResolvedVariant(en, "en", fallback=True)

    return None
