"""ADR-027 event geography: where a story happens, stored in
`story_countries` (role EVENT). Publisher origin (`Source.country`) is never
shown or matched as the story's location.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import StoryCountry

EVENT = "EVENT"

# The country list clients offer (`packages/domain` `countryCode`). Codes
# outside it are dropped rather than guessed.
SUPPORTED_COUNTRIES: tuple[str, ...] = ("US", "IN", "CA", "GB", "AU", "AE", "SG", "NZ", "DE")

_ALIASES: dict[str, str] = {
    "united states": "US", "united states of america": "US", "usa": "US", "u.s.": "US", "america": "US",
    "india": "IN", "canada": "CA", "united kingdom": "GB", "uk": "GB", "britain": "GB",
    "great britain": "GB", "england": "GB", "australia": "AU", "united arab emirates": "AE",
    "uae": "AE", "singapore": "SG", "new zealand": "NZ", "germany": "DE",
}


def normalize_country(value: str | None) -> str | None:
    """A supported ISO 3166-1 alpha-2 code, or None."""
    if not value or not value.strip():
        return None
    text = value.strip()
    code = _ALIASES.get(text.lower(), text.upper())
    return code if code in SUPPORTED_COUNTRIES else None


def normalize_countries(values: Iterable[str | None]) -> list[str]:
    return list(dict.fromkeys(c for c in (normalize_country(v) for v in values) if c))


def set_event_countries(db: Session, story_id: uuid.UUID, codes: Iterable[str]) -> None:
    """Replaces the story's EVENT countries. `codes` must already be normalized."""
    db.execute(delete(StoryCountry).where(StoryCountry.story_id == story_id, StoryCountry.role == EVENT))
    for code in dict.fromkeys(codes):
        db.add(StoryCountry(story_id=story_id, country_code=code, role=EVENT))
    db.flush()


def event_countries_many(db: Session, story_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[str]]:
    result: dict[uuid.UUID, list[str]] = {sid: [] for sid in story_ids}
    if not story_ids:
        return result
    rows = db.execute(
        select(StoryCountry.story_id, StoryCountry.country_code)
        .where(StoryCountry.story_id.in_(story_ids), StoryCountry.role == EVENT)
        .order_by(StoryCountry.country_code)
    ).all()
    for story_id, code in rows:
        result[story_id].append(code)
    return result
