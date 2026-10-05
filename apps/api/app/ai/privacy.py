"""ADR-015 per-story privacy decision. Deterministic (no model call), computed
once and persisted on `stories.privacy_decision`; every dispatch to the Gemini
free tier consults the persisted value. `FREE_TIER_ALLOWED` is earned, never
defaulted: it needs an allowlisted source category AND no restricted signal.
"""

from __future__ import annotations

import re
from enum import Enum


class PrivacyDecision(str, Enum):
    FREE_TIER_ALLOWED = "FREE_TIER_ALLOWED"
    RESTRICTED = "RESTRICTED"
    UNKNOWN = "UNKNOWN"


# ADR-015 decision 3. Extending this list needs a new ADR with owner sign-off.
ALLOWLIST_V1: frozenset[str] = frozenset({"entertainment", "sports", "community_events"})

# Restricted signals: NON_NEGOTIABLES #5 topics (immigration, legal, financial,
# breaking) plus obituary/accusation. A miss here is safe: it only leaves the
# story on the category-allowlist path, which is itself narrow.
# Telugu death/breaking terms, shared with publish.DEATH_SIGNAL_PATTERN. Plain
# substring alternation: \b is unreliable next to Telugu combining marks, and
# prefixes (కన్నుమూ, మరణించ, అస్తమించ) deliberately cover every inflection.
# నివాళి (tribute) can false-positive on non-obituary tributes; that only costs
# a RESTRICTED (paid-tier) route, never a loosening.
TELUGU_DEATH_TERMS = "ఇకలేరు|కన్నుమూ|మరణించ|మరణం|మృతి|తుదిశ్వాస|అస్తమించ|కాలం చెందా|నివాళి|హత్య"
TELUGU_BREAKING_TERMS = "బ్రేకింగ్"

_RESTRICTED_PATTERN = re.compile(
    rf"{TELUGU_DEATH_TERMS}|{TELUGU_BREAKING_TERMS}|"
    r"\b(immigra\w*|visa|h-?1b|green\s*card|uscis|deport\w*|asylum|opt|stem\s*opt|"
    r"court|lawsuit|sued|indict\w*|arrest\w*|verdict|attorney|lawyer|legal|"
    r"tax|irs|loan|mortgage|stock|market|inflation|bank\w*|fraud|scam|"
    r"breaking|killed|dead|death|died|obituar\w*|accus\w*|allegation\w*)\b",
    re.IGNORECASE,
)

_RANK = {
    PrivacyDecision.FREE_TIER_ALLOWED: 0,
    PrivacyDecision.UNKNOWN: 1,
    PrivacyDecision.RESTRICTED: 2,
}


def has_restricted_signal(*texts: str | None) -> bool:
    return any(t and _RESTRICTED_PATTERN.search(t) for t in texts)


def classify_privacy(category: str | None, *texts: str | None) -> PrivacyDecision:
    if has_restricted_signal(*texts):
        return PrivacyDecision.RESTRICTED
    if category is not None and category.strip().lower() in ALLOWLIST_V1:
        return PrivacyDecision.FREE_TIER_ALLOWED
    return PrivacyDecision.UNKNOWN


def tighten(current: PrivacyDecision, new: PrivacyDecision) -> PrivacyDecision:
    """Model-reported or later signals may tighten a decision, never loosen it."""
    return new if _RANK[new] > _RANK[current] else current


def coerce(value: str | None) -> PrivacyDecision:
    """Unrecognised or missing stored values fail closed to UNKNOWN."""
    try:
        return PrivacyDecision(value)
    except ValueError:
        return PrivacyDecision.UNKNOWN
