"""§4.3 glossary enforcement: names/places/organizations/domain terms with a
known canonical Telugu spelling must never be left to whatever a raw
machine-translation pass produces (which typically either leaves the term
in Latin script or transliterates it inconsistently). This is deterministic
post-processing, not a model call, per NON_NEGOTIABLES' "prefer
deterministic code" default — the AI gateway's translation call still
produces the Telugu draft; this only corrects known terms inside it.

Entries are keyed by the canonical English term. `naive_variants` lists the
renderings a real translation call is known to produce instead of the
canonical spelling (including the bare English term itself, left
untranslated) — expand this list as real provider output surfaces new
variants worth catching.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class GlossaryEntry:
    canonical_te: str
    naive_variants: tuple[str, ...] = field(default_factory=tuple)


# Seed set — names/places/orgs this product's coverage area (US immigration,
# federal agencies, Telugu-diaspora geography) already touches. Extend as
# real translation output surfaces terms worth pinning.
GLOSSARY_EN_TE: dict[str, GlossaryEntry] = {
    "United States": GlossaryEntry("అమెరికా", naive_variants=("యునైటెడ్ స్టేట్స్", "United States")),
    "USCIS": GlossaryEntry("యుఎస్‌సిఐఎస్", naive_variants=("యుఎస్ సిఐఎస్", "USCIS")),
    "White House": GlossaryEntry("వైట్ హౌస్", naive_variants=("తెల్ల ఇల్లు", "White House")),
    "Telangana": GlossaryEntry("తెలంగాణ", naive_variants=("తెలంగణ", "Telangana")),
    "Andhra Pradesh": GlossaryEntry("ఆంధ్రప్రదేశ్", naive_variants=("ఆంధ్ర ప్రదేశ్", "Andhra Pradesh")),
}


def apply_glossary(en_text: str, te_text: str, glossary: dict[str, GlossaryEntry] | None = None) -> str:
    """Returns `te_text` with every glossary term present in `en_text`
    forced to its canonical Telugu spelling."""
    glossary = GLOSSARY_EN_TE if glossary is None else glossary
    for term, entry in glossary.items():
        if not re.search(rf"\b{re.escape(term)}\b", en_text, flags=re.IGNORECASE):
            continue
        if entry.canonical_te in te_text:
            continue
        for variant in entry.naive_variants:
            if variant in te_text:
                te_text = te_text.replace(variant, entry.canonical_te)
                break
    return te_text
