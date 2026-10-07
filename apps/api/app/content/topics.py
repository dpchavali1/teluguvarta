"""ADR-056: the fixed topic taxonomy. The classifier picks from these slugs
and nothing else; before this, every new phrasing of a category ("Crime &
Safety", "Crime and Justice", "Law and Order") became its own active topic,
so readers' subscriptions rarely matched new stories.

`TOPIC_ALIASES` maps every retired slug seen in production (2026-10-06) to
its canonical slug, or to None when no single topic fits (e.g. "local-news",
which could be either state). It is used for classifier output that drifts
off-list and for older app builds that still send retired slugs; migration
`f6a2c8e4b1d7` holds a frozen copy for the one-time merge.
"""

from __future__ import annotations

import re

GENERAL_TOPICS: tuple[tuple[str, str], ...] = (
    ("immigration", "Immigration"),
    ("andhra-pradesh", "Andhra Pradesh"),
    ("telangana", "Telangana"),
    ("hyderabad", "Hyderabad"),
    ("india", "India"),
    ("us-news", "US News"),
    ("world", "World"),
    ("politics", "Politics"),
    ("government", "Government & Welfare"),
    ("community", "NRI & Community"),
    ("entertainment", "Entertainment"),
    ("sports", "Sports"),
    ("money", "Money"),
    ("business", "Business"),
    ("jobs", "Jobs"),
    ("education", "Education"),
    ("property", "Property"),
    ("technology", "Technology"),
    ("health", "Health"),
    ("crime-safety", "Crime & Safety"),
    ("legal", "Courts & Legal"),
    ("agriculture", "Agriculture"),
    ("infrastructure", "Infrastructure"),
    ("environment", "Weather & Environment"),
    ("culture", "Culture & Religion"),
    ("travel", "Travel"),
    ("parents", "Parents"),
)

# S2 / §3.1; `packages/domain`'s STUDENT_TOPIC_SLUGS groups these in the UI.
STUDENT_TOPICS: tuple[tuple[str, str], ...] = (
    ("f1", "F-1"),
    ("cpt", "CPT"),
    ("opt", "OPT"),
    ("stem-opt", "STEM OPT"),
    ("h1b-transition", "H-1B Transition"),
    ("internships", "Internships"),
    ("university-policy", "University Policy"),
    ("campus-safety", "Campus Safety"),
    ("taxes", "Taxes"),
    ("housing", "Housing"),
    ("scholarships", "Scholarships"),
    ("student-community", "Student Community"),
    ("international-student-jobs", "International Student Jobs"),
)

CANONICAL_TOPICS: tuple[tuple[str, str], ...] = GENERAL_TOPICS + STUDENT_TOPICS
CANONICAL_SLUGS: frozenset[str] = frozenset(slug for slug, _ in CANONICAL_TOPICS)

_RETIRED: dict[str | None, tuple[str, ...]] = {
    "immigration": (
        "immigration-visas", "us-immigration", "us-visas", "visa-updates",
        "us-immigration-diaspora", "immigration-education",
    ),
    "andhra-pradesh": ("andhra-pradesh-news",),
    "telangana": ("telangana-news", "telangana-local-news", "telangana-politics"),
    "india": ("national", "national-news", "india-news", "defense"),
    "us-news": ("us-politics", "us-policy", "usa"),
    "world": ("international-news", "international-relations"),
    "politics": (
        "state-politics", "regional-politics", "elections", "local-elections", "state-elections",
        "politics-government", "government-politics", "politics-governance",
        "state-politics-governance", "protests", "public-protests", "water-disputes",
    ),
    "government": (
        "state-government", "local-governance", "local-administration", "welfare-schemes",
        "governance", "state-governance", "social-welfare", "government-policy", "public-welfare",
        "state-government-schemes", "government-administration", "government-schemes",
        "government-services", "land-administration", "land-governance", "local-government",
        "policy", "regional-governance", "state-administration", "state-government-employees",
        "pensioners", "welfare", "housing-and-welfare", "cooperative-society", "land-acquisition",
        "land-issues", "appointments",
    ),
    "community": (
        "nri-news", "nri", "nris", "diaspora", "diaspora-affairs", "telugu-diaspora",
        "community-events", "community-diaspora", "community-news", "community-development",
        "events", "local-events", "regional-events", "philanthropy", "success-story",
        "success-stories", "achievements", "awards", "awards-honors",
    ),
    "entertainment": (
        "tollywood", "cinema", "telugu-cinema", "telugu-cinema-and-entertainment", "television",
        "movies", "ott", "movie-review", "movie-reviews", "box-office", "celebrity",
        "culture-entertainment", "interviews",
    ),
    "sports": ("cricket",),
    "money": (
        "economy", "economy-finance", "finance", "market-updates", "consumer", "consumer-affairs",
        "consumer-news",
    ),
    "business": (
        "business-economy", "local-industry", "startups", "economic-development",
        "women-entrepreneurs",
    ),
    "jobs": (
        "employment", "labor", "labor-employment", "labor-and-employment", "labor-rights",
        "labor-welfare", "labor-issues", "career-jobs",
    ),
    "education": ("jobs-education", "education-jobs"),
    "property": ("real-estate", "real-estate-housing", "housing-and-real-estate"),
    "technology": ("science-technology", "innovation", "cyber-security"),
    "health": ("healthcare", "health-fitness", "health-safety"),
    "crime-safety": (
        "crime", "accidents", "crime-and-accidents", "law-and-order", "local-crime-accidents",
        "police-and-crime", "accidents-disasters", "accidents-safety", "accidents-tragedies",
        "crime-accidents", "crime-atrocities", "crime-corruption", "crime-security",
        "crime-and-justice", "crime-justice", "law-order", "law-enforcement", "public-safety",
        "safety", "safety-security", "security", "society-safety", "tragedy", "fraud",
        "cybercrime", "corruption", "corruption-governance",
    ),
    "legal": ("crime-courts", "crime-legal", "legal-governance", "legal-judiciary", "law-governance"),
    "agriculture": ("agriculture-irrigation",),
    "infrastructure": (
        "transport", "transportation", "infrastructure-development", "energy",
        "energy-infrastructure", "public-infrastructure", "infrastructure-utilities",
        "development", "state-development", "local-development", "civic-and-sanitation",
        "aviation", "water-resources",
    ),
    "environment": ("weather", "natural-disasters"),
    "culture": (
        "religion", "history-culture", "arts-culture", "culture-heritage", "culture-religion",
        "devotional", "traditions", "religion-spirituality", "festivals", "heritage", "history",
        "culture-events", "culture-awards",
    ),
    "travel": ("tourism",),
    "taxes": ("taxation",),
    None: (
        "local-news", "regional-news", "state-news", "regional", "local", "state-events",
        "telugu-states", "telugu", "media", "media-journalism", "controversy", "society",
        "social-issues", "social-justice", "memorial", "obituary", "obituaries",
        "practical-advice", "traditional-occupations",
    ),
}

TOPIC_ALIASES: dict[str, str | None] = {
    retired: canonical for canonical, retired_slugs in _RETIRED.items() for retired in retired_slugs
}

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(text: str) -> str:
    return _SLUG_RE.sub("-", text.lower()).strip("-")


def canonical_topic_slug(value: str) -> str | None:
    """The canonical slug for a slug or category label, or None if it has no
    place in the taxonomy (the caller then drops it)."""

    slug = slugify(value)
    if slug in CANONICAL_SLUGS:
        return slug
    return TOPIC_ALIASES.get(slug)


def canonical_topic_slugs(values: list[str]) -> list[str]:
    """Order-preserving, de-duplicated canonical slugs for `values`."""

    return list(dict.fromkeys(s for s in (canonical_topic_slug(v) for v in values) if s is not None))


def classifier_topic_ids() -> str:
    return ", ".join(slug for slug, _ in CANONICAL_TOPICS)
