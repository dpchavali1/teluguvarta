"""P07 / ADR-041: visa bulletin tracker rules (pure, no DB).

Cutoffs are entered by an editor from the official State Department bulletin
(its page blocks automated fetching, so there is no ingest job). A cutoff is
an ISO date, "C" (current) or "U" (unavailable)."""

from __future__ import annotations

from datetime import date
from urllib.parse import urlparse

CHARTS = ("FINAL_ACTION", "DATES_FOR_FILING")
CATEGORIES = ("F1", "F2A", "F2B", "F3", "F4", "EB1", "EB2", "EB3", "EB3-OW", "EB4", "EB5")
COUNTRIES = ("ALL", "CHINA", "INDIA", "MEXICO", "PHILIPPINES")
MAX_VISA_FOLLOWS = 5
OFFICIAL_HOST = "travel.state.gov"

Movement = str  # "FORWARD" | "BACKWARD" | "SAME" | "NEW"


def valid_cutoff(value: str) -> bool:
    if value in ("C", "U"):
        return True
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return len(value) == 10


def official_source_url(url: str) -> bool:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    return parsed.scheme == "https" and (host == OFFICIAL_HOST or host.endswith("." + OFFICIAL_HOST))


def entry_errors(chart: str, category: str, country: str, cutoff: str) -> str | None:
    if chart not in CHARTS:
        return f"Unknown chart: {chart}"
    if category not in CATEGORIES:
        return f"Unknown category: {category}"
    if country not in COUNTRIES:
        return f"Unknown country: {country}"
    if not valid_cutoff(cutoff):
        return f"Cutoff must be YYYY-MM-DD, C or U: {cutoff}"
    return None


def _rank(cutoff: str) -> tuple[int, str]:
    # "U" is the least favourable, "C" the most; dates order lexicographically.
    if cutoff == "U":
        return (0, "")
    if cutoff == "C":
        return (2, "")
    return (1, cutoff)


def movement(previous: str | None, current: str) -> Movement:
    if previous is None:
        return "NEW"
    if previous == current:
        return "SAME"
    return "FORWARD" if _rank(current) > _rank(previous) else "BACKWARD"


def describe_cutoff(cutoff: str) -> str:
    return {"C": "current", "U": "unavailable"}.get(cutoff, cutoff)


def alert_copy(category: str, country: str, previous: str, current: str, move: Movement) -> tuple[str, str]:
    where = "all countries" if country == "ALL" else country.title()
    verb = "moved forward" if move == "FORWARD" else "retrogressed"
    return (
        f"Visa Bulletin: {category} {verb}",
        f"{category} ({where}) final action date: {describe_cutoff(previous)} → {describe_cutoff(current)}.",
    )
