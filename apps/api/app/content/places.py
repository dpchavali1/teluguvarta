"""ADR-043 place catalog and story place tags.

The catalog is fixed and versioned here; `packages/domain/places.ts` is
generated from it (`python -m app.content.places > packages/domain/places.ts`,
checked by `tests/test_places.py`). Place ids outside the catalog are dropped,
never guessed. A district/city tag implies its ancestors for matching.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterable
from typing import NamedTuple

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import StoryPlace

EVENT = "EVENT"
CATALOG_VERSION = 1
MAX_FOLLOWED_PLACES = 10


class Place(NamedTuple):
    id: str
    country: str
    kind: str  # COUNTRY | STATE | DISTRICT | CITY
    name_en: str
    name_te: str
    parent_id: str | None


def _c(code: str, en: str, te: str) -> Place:
    return Place(code, code, "COUNTRY", en, te, None)


def _s(pid: str, en: str, te: str) -> Place:
    country = pid.split("-")[0]
    return Place(pid, country, "STATE", en, te, country)


def _d(pid: str, en: str, te: str) -> Place:
    state = "-".join(pid.split("-")[:2])
    return Place(pid, pid.split("-")[0], "DISTRICT", en, te, state)


def _city(pid: str, en: str, te: str, parent: str) -> Place:
    return Place(pid, pid.split("-")[0], "CITY", en, te, parent)


# V1 scope (ADR-043): diaspora countries at country level; India (AP/Telangana
# in depth) and US below country level. More places are added by demand, with
# native-speaker review of the Telugu names.
CATALOG: tuple[Place, ...] = (
    _c("US", "United States", "అమెరికా"),
    _c("IN", "India", "భారతదేశం"),
    _c("GB", "United Kingdom", "యునైటెడ్ కింగ్‌డమ్"),
    _c("CA", "Canada", "కెనడా"),
    _c("AU", "Australia", "ఆస్ట్రేలియా"),
    _c("DE", "Germany", "జర్మనీ"),
    _c("AE", "UAE", "యూఏఈ"),
    _c("SG", "Singapore", "సింగపూర్"),
    _c("NZ", "New Zealand", "న్యూజిలాండ్"),
    # India — states
    _s("IN-AP", "Andhra Pradesh", "ఆంధ్రప్రదేశ్"),
    _s("IN-TG", "Telangana", "తెలంగాణ"),
    _s("IN-KA", "Karnataka", "కర్ణాటక"),
    _s("IN-TN", "Tamil Nadu", "తమిళనాడు"),
    _s("IN-MH", "Maharashtra", "మహారాష్ట్ర"),
    _s("IN-DL", "Delhi", "ఢిల్లీ"),
    # Andhra Pradesh districts
    _d("IN-AP-visakhapatnam", "Visakhapatnam", "విశాఖపట్నం"),
    _d("IN-AP-krishna", "Krishna", "కృష్ణా"),
    _d("IN-AP-ntr", "NTR (Vijayawada)", "ఎన్టీఆర్ (విజయవాడ)"),
    _d("IN-AP-guntur", "Guntur", "గుంటూరు"),
    _d("IN-AP-tirupati", "Tirupati", "తిరుపతి"),
    _d("IN-AP-east-godavari", "East Godavari", "తూర్పు గోదావరి"),
    _d("IN-AP-west-godavari", "West Godavari", "పశ్చిమ గోదావరి"),
    _d("IN-AP-nellore", "Nellore", "నెల్లూరు"),
    _d("IN-AP-kurnool", "Kurnool", "కర్నూలు"),
    _d("IN-AP-anantapur", "Anantapur", "అనంతపురం"),
    _d("IN-AP-kadapa", "Kadapa", "కడప"),
    _d("IN-AP-srikakulam", "Srikakulam", "శ్రీకాకుళం"),
    _d("IN-AP-prakasam", "Prakasam", "ప్రకాశం"),
    # Telangana districts
    _d("IN-TG-hyderabad", "Hyderabad", "హైదరాబాద్"),
    _d("IN-TG-rangareddy", "Ranga Reddy", "రంగారెడ్డి"),
    _d("IN-TG-medchal", "Medchal-Malkajgiri", "మేడ్చల్-మల్కాజిగిరి"),
    _d("IN-TG-warangal", "Warangal", "వరంగల్"),
    _d("IN-TG-hanumakonda", "Hanumakonda", "హనుమకొండ"),
    _d("IN-TG-karimnagar", "Karimnagar", "కరీంనగర్"),
    _d("IN-TG-nizamabad", "Nizamabad", "నిజామాబాద్"),
    _d("IN-TG-khammam", "Khammam", "ఖమ్మం"),
    _d("IN-TG-nalgonda", "Nalgonda", "నల్గొండ"),
    _d("IN-TG-mahabubnagar", "Mahabubnagar", "మహబూబ్‌నగర్"),
    _d("IN-TG-adilabad", "Adilabad", "ఆదిలాబాద్"),
    _d("IN-TG-medak", "Medak", "మెదక్"),
    _d("IN-TG-sangareddy", "Sangareddy", "సంగారెడ్డి"),
    # India — other major cities
    _city("IN-KA-bengaluru", "Bengaluru", "బెంగళూరు", "IN-KA"),
    _city("IN-TN-chennai", "Chennai", "చెన్నై", "IN-TN"),
    _city("IN-MH-mumbai", "Mumbai", "ముంబై", "IN-MH"),
    _city("IN-MH-pune", "Pune", "పుణె", "IN-MH"),
    # US — states with large Telugu communities
    _s("US-CA", "California", "కాలిఫోర్నియా"),
    _s("US-TX", "Texas", "టెక్సాస్"),
    _s("US-NJ", "New Jersey", "న్యూజెర్సీ"),
    _s("US-NY", "New York", "న్యూయార్క్"),
    _s("US-IL", "Illinois", "ఇల్లినాయిస్"),
    _s("US-WA", "Washington", "వాషింగ్టన్"),
    _s("US-VA", "Virginia", "వర్జీనియా"),
    _s("US-GA", "Georgia", "జార్జియా"),
    _s("US-NC", "North Carolina", "నార్త్ కరోలినా"),
    _s("US-FL", "Florida", "ఫ్లోరిడా"),
    _s("US-MA", "Massachusetts", "మసాచుసెట్స్"),
    _s("US-PA", "Pennsylvania", "పెన్సిల్వేనియా"),
    _s("US-MI", "Michigan", "మిషిగన్"),
    _s("US-OH", "Ohio", "ఓహియో"),
    _s("US-AZ", "Arizona", "అరిజోనా"),
    _s("US-MD", "Maryland", "మేరీల్యాండ్"),
    _s("US-DC", "Washington, D.C.", "వాషింగ్టన్ డి.సి."),
    # US — major cities
    _city("US-CA-san-francisco-bay-area", "San Francisco Bay Area", "శాన్ ఫ్రాన్సిస్కో బే ఏరియా", "US-CA"),
    _city("US-TX-dallas", "Dallas", "డాలస్", "US-TX"),
    _city("US-TX-houston", "Houston", "హ్యూస్టన్", "US-TX"),
    _city("US-TX-austin", "Austin", "ఆస్టిన్", "US-TX"),
    _city("US-WA-seattle", "Seattle", "సియాటిల్", "US-WA"),
    _city("US-NY-new-york-city", "New York City", "న్యూయార్క్ సిటీ", "US-NY"),
    _city("US-NJ-edison", "Edison", "ఎడిసన్", "US-NJ"),
    _city("US-IL-chicago", "Chicago", "చికాగో", "US-IL"),
    _city("US-GA-atlanta", "Atlanta", "అట్లాంటా", "US-GA"),
    _city("US-NC-charlotte", "Charlotte", "షార్లెట్", "US-NC"),
)

_BY_ID: dict[str, Place] = {p.id: p for p in CATALOG}


def get_place(place_id: str) -> Place | None:
    return _BY_ID.get(place_id)


def normalize_place_ids(values: Iterable[str | None]) -> list[str]:
    """Catalog ids only, deduplicated in order. Unknown values are dropped."""
    return list(dict.fromkeys(v.strip() for v in values if v and v.strip() in _BY_ID))


def ancestors(place_id: str) -> list[str]:
    """The place's parent chain (nearest first), excluding itself."""
    chain: list[str] = []
    current = _BY_ID.get(place_id)
    while current and current.parent_id:
        chain.append(current.parent_id)
        current = _BY_ID.get(current.parent_id)
    return chain


def expand_with_ancestors(place_ids: Iterable[str]) -> set[str]:
    """Matching set for a story's tags: each tag plus every ancestor."""
    expanded: set[str] = set()
    for pid in place_ids:
        if pid in _BY_ID:
            expanded.add(pid)
            expanded.update(ancestors(pid))
    return expanded


def subtree_ids(place_id: str) -> list[str]:
    """The place plus every place beneath it, so following Telangana lists
    a Warangal story."""
    if place_id not in _BY_ID:
        return []
    return [p.id for p in CATALOG if p.id == place_id or place_id in ancestors(p.id)]


def catalog_prompt_ids() -> str:
    """Compact id list for the classification prompt."""
    return ", ".join(p.id for p in CATALOG if p.kind != "COUNTRY")


def set_event_places(db: Session, story_id: uuid.UUID, place_ids: Iterable[str]) -> None:
    """Replaces the story's EVENT places. `place_ids` must already be normalized."""
    db.execute(delete(StoryPlace).where(StoryPlace.story_id == story_id, StoryPlace.role == EVENT))
    for pid in dict.fromkeys(place_ids):
        db.add(StoryPlace(story_id=story_id, place_id=pid, role=EVENT))
    db.flush()


def event_places_many(db: Session, story_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[str]]:
    result: dict[uuid.UUID, list[str]] = {sid: [] for sid in story_ids}
    if not story_ids:
        return result
    rows = db.execute(
        select(StoryPlace.story_id, StoryPlace.place_id)
        .where(StoryPlace.story_id.in_(story_ids), StoryPlace.role == EVENT)
        .order_by(StoryPlace.place_id)
    ).all()
    for story_id, place_id in rows:
        result[story_id].append(place_id)
    return result


def render_typescript() -> str:
    """Source of `packages/domain/places.ts`."""
    rows = ",\n".join(
        "  " + json.dumps(
            {"id": p.id, "country": p.country, "kind": p.kind, "nameEn": p.name_en,
             "nameTe": p.name_te, "parentId": p.parent_id},
            ensure_ascii=False,
        )
        for p in CATALOG
    )
    return (
        "// Generated from apps/api/app/content/places.py (ADR-043). Do not edit;\n"
        "// run `python -m app.content.places > packages/domain/places.ts` in apps/api.\n"
        'export type PlaceKind = "COUNTRY" | "STATE" | "DISTRICT" | "CITY";\n'
        "export interface Place {\n"
        "  id: string;\n  country: string;\n  kind: PlaceKind;\n"
        "  nameEn: string;\n  nameTe: string;\n  parentId: string | null;\n}\n\n"
        f"export const PLACE_CATALOG_VERSION = {CATALOG_VERSION};\n"
        f"export const MAX_FOLLOWED_PLACES = {MAX_FOLLOWED_PLACES};\n\n"
        f"export const PLACES: readonly Place[] = [\n{rows},\n];\n\n"
        "const BY_ID = new Map(PLACES.map((place) => [place.id, place]));\n\n"
        "export function getPlace(id: string): Place | undefined {\n  return BY_ID.get(id);\n}\n\n"
        "export function placeName(id: string, language: \"en\" | \"te\"): string {\n"
        "  const place = BY_ID.get(id);\n"
        "  if (!place) return id;\n"
        "  return language === \"te\" ? place.nameTe : place.nameEn;\n}\n\n"
        "// A tag plus every ancestor, for matching a story against follows.\n"
        "export function expandPlaceIds(ids: readonly string[]): Set<string> {\n"
        "  const out = new Set<string>();\n"
        "  for (const id of ids) {\n"
        "    let current = BY_ID.get(id);\n"
        "    while (current) {\n"
        "      out.add(current.id);\n"
        "      current = current.parentId ? BY_ID.get(current.parentId) : undefined;\n"
        "    }\n"
        "  }\n"
        "  return out;\n}\n"
    )


if __name__ == "__main__":
    print(render_typescript(), end="")
