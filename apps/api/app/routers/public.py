"""Public endpoints — no auth, always available (NON_NEGOTIABLES #9).

T14: wired to real data via app/content/serialize.py. Only `PUBLIC_STATUSES`
stories (published at least once) are ever visible here — DRAFT/AI_READY/
REVIEW_REQUIRED/APPROVED/SCHEDULED/ARCHIVED stories stay internal.
"""

import base64
import os
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app import analytics, reader_reports
from app.content.geography import EVENT, normalize_country
from app.content.places import (
    CATALOG,
    MAX_FOLLOWED_PLACES,
    normalize_place_ids,
    subtree_ids,
)
from app.content.ranking import Preferences, rank_stories
from app.content.search_cursor import decode_search_cursor, encode_search_cursor
from app.content.serialize import (
    PUBLIC_STATUSES,
    active_topics_out,
    load_story_relations,
    story_to_out,
    story_to_rankable,
    topic_out,
)
from app.content.variants import resolve_display_variant
from app.content.why_matters import generation_segment, get_cached_many
from app.db import get_db
from app.errors import APIError
from app.jobs.why_matters import enqueue_why_matters
from app.models import (
    Story,
    StoryCountry,
    StoryPlace,
    StoryTopic,
    StoryVariant,
    Topic,
)
from app.rate_limit import (
    _client_ip,
    rate_limit_events,
    rate_limit_reports,
    rate_limit_search,
)
from app.schemas import (
    AnalyticsEventIn,
    AnalyticsEventResponse,
    ConfigResponse,
    HomeResponse,
    PersonalizationOut,
    ReaderReportAccepted,
    ReaderReportIn,
    SearchResponse,
    Segment,
    ShareMetaResponse,
    StoriesListResponse,
    StoryOut,
    TopicDetailResponse,
)

router = APIRouter(prefix="/v1", tags=["public"])

DEFAULT_PAGE_SIZE = 20
HOME_PAGE_SIZE = 10
# T16/ADR-005: how many recent published stories are candidates for
# personalized ranking — bounded so a single `/v1/home` request never scores
# the entire published-story history.
HOME_CANDIDATE_POOL = 50

# S1: "Student Briefing" is a composed/filtered view over the same `/v1/home`
# feed and ranking (docs/tickets/S1.md) — not a separate content pipeline.
# Slugs must exist in SEED_TOPICS (infra/scripts/seed.py); "community" stands
# in for "campus/community" since there's no separate campus topic.
STUDENT_BRIEFING_TOPIC_SLUGS = (
    "immigration",
    "education",
    "jobs",
    "money",
    "travel",
    "community",
)


def _public_web_url() -> str:
    return os.environ.get("PUBLIC_WEB_URL", "http://localhost:3000").rstrip("/")


def _env_flag(name: str, *, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() not in ("0", "false", "no", "")


def _decode_cursor(cursor: str | None) -> int:
    if not cursor:
        return 0
    try:
        return max(0, int(base64.urlsafe_b64decode(cursor.encode()).decode()))
    except (ValueError, UnicodeDecodeError):
        return 0


def _encode_cursor(offset: int) -> str:
    return base64.urlsafe_b64encode(str(offset).encode()).decode()


def _published_query(*, topic_slug: str | None = None, country: str | None = None, place: str | None = None):
    stmt = select(Story).where(Story.status.in_(PUBLIC_STATUSES))
    if topic_slug is not None:
        stmt = stmt.where(Story.id.in_(
            select(StoryTopic.story_id).join(Topic, Topic.id == StoryTopic.topic_id).where(Topic.slug == topic_slug)
        ))
    if country is not None:
        # ADR-027: where the story happens, not where its publisher is.
        stmt = stmt.where(Story.id.in_(
            select(StoryCountry.story_id).where(
                StoryCountry.country_code == (normalize_country(country) or country.upper()),
                StoryCountry.role == EVENT,
            )
        ))
    if place is not None:
        # ADR-043: a story tagged beneath the place matches it; untagged never does.
        stmt = stmt.where(Story.id.in_(
            select(StoryPlace.story_id).where(StoryPlace.place_id.in_(subtree_ids(place)), StoryPlace.role == EVENT)
        ))
    return stmt.order_by(Story.published_at.desc().nulls_last(), Story.id)


def _list_page(
    db: Session, *, topic_slug: str | None, country: str | None, limit: int, cursor: str | None,
    ids: list[UUID] | None = None, place: str | None = None,
) -> StoriesListResponse:
    offset = _decode_cursor(cursor)
    stmt = _published_query(topic_slug=topic_slug, country=country, place=place)
    if ids is not None:
        stmt = stmt.where(Story.id.in_(ids))
    rows = list(db.scalars(stmt.offset(offset).limit(limit + 1)))
    stories = rows[:limit]
    loaded = load_story_relations(db, [story.id for story in stories])
    items = [story_to_out(db, story, loaded) for story in stories]
    next_cursor = _encode_cursor(offset + limit) if len(rows) > limit else None
    return StoriesListResponse(items=items, next_cursor=next_cursor)


def _get_published_story(db: Session, slug: str) -> Story:
    story = db.scalars(
        select(Story).where(Story.canonical_slug == slug, Story.status.in_(PUBLIC_STATUSES))
    ).first()
    if story is None:
        raise APIError(404, "STORY_NOT_FOUND", f"No story with slug '{slug}'")
    return story


@router.get("/home")
def get_home(
    residence_country: str | None = Query(default=None),
    residence_region: str | None = Query(default=None),
    home_state: str | None = Query(default=None),
    home_city: str | None = Query(default=None),
    topics_pref: str | None = Query(default=None, alias="topics"),
    places_pref: str | None = Query(default=None, alias="places", max_length=600),
    segment: Segment = Query(default="general"),
    student_briefing: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> HomeResponse:
    explicit_topics = tuple(t.strip() for t in topics_pref.split(",") if t.strip()) if topics_pref else ()
    if student_briefing:
        # Explicit-preference-only (NON_NEGOTIABLES / §3.5): this only fires
        # when the caller passes student_briefing=true, which only ever
        # happens because the user explicitly selected International Student
        # or Graduate/OPT during onboarding — never inferred from behavior.
        topics_for_prefs = tuple(dict.fromkeys((*STUDENT_BRIEFING_TOPIC_SLUGS, *explicit_topics)))
    else:
        topics_for_prefs = explicit_topics

    prefs = Preferences(
        residence_country=residence_country,
        residence_region=residence_region,
        home_state=home_state,
        home_city=home_city,
        topics=topics_for_prefs,
        follow_places=tuple(normalize_place_ids(places_pref.split(","))[:MAX_FOLLOWED_PLACES]) if places_pref else (),
    )

    if prefs.is_empty():
        # T16/ADR-005: personalization is additive — no preferences supplied
        # (the common case for an anonymous, no-account-yet visitor per
        # NON_NEGOTIABLES #9) means the existing T14 chronological feed.
        stories = list(db.scalars(_published_query().limit(HOME_PAGE_SIZE)))
        loaded = load_story_relations(db, [s.id for s in stories])
        top_stories = [story_to_out(db, s, loaded) for s in stories]
    else:
        candidates = list(db.scalars(_published_query().limit(HOME_CANDIDATE_POOL)))
        loaded = load_story_relations(db, [s.id for s in candidates])
        rankable = [story_to_rankable(db, s, loaded) for s in candidates]
        ranked = rank_stories(rankable, prefs)[:HOME_PAGE_SIZE]
        stories_by_id = {str(s.id): s for s in candidates}
        cached_why = get_cached_many(db, [s.id for s in candidates], generation_segment(segment))
        top_stories = []
        misses = []
        for scored in ranked:
            story = stories_by_id[scored.story_id]
            out = story_to_out(db, story, loaded)
            why_matters = cached_why.get(story.id)
            if why_matters is None:
                en = next((v for v in loaded.variants[story.id] if v.language == "en"), None)
                if en is not None:
                    misses.append((story, en))
            out.personalization = PersonalizationOut(
                score=scored.score, explanation=scored.explanation, why_matters=why_matters or None,
            )
            top_stories.append(out)
        enqueue_why_matters(db, misses, segment)
        db.commit()

    return HomeResponse(top_stories=top_stories, topics=active_topics_out(db))


@router.get("/stories")
def list_stories(
    topic: str | None = Query(default=None),
    country: str | None = Query(default=None),
    place: str | None = Query(default=None),
    limit: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=100),
    cursor: str | None = Query(default=None),
    ids: str | None = Query(default=None, max_length=3700),
    db: Session = Depends(get_db),
) -> StoriesListResponse:
    if place is not None and place not in {p.id for p in CATALOG}:
        raise APIError(422, "UNKNOWN_PLACE", f"Not a catalog place: {place}")
    selected_ids = None
    if ids is not None:
        try:
            selected_ids = list(dict.fromkeys(UUID(value.strip()) for value in ids.split(",")))
        except ValueError as err:
            raise APIError(422, "INVALID_STORY_IDS", "Story ids must be comma-separated UUIDs") from err
        if len(selected_ids) > 100:
            raise APIError(422, "TOO_MANY_STORY_IDS", "Request at most 100 saved stories at a time")
    return _list_page(db, topic_slug=topic, country=country, limit=limit, cursor=cursor, ids=selected_ids, place=place)


@router.get("/stories/{slug}")
def get_story(slug: str, db: Session = Depends(get_db)) -> StoryOut:
    return story_to_out(db, _get_published_story(db, slug))


@router.get("/stories/{slug}/share-meta")
def get_story_share_meta(slug: str, db: Session = Depends(get_db)) -> ShareMetaResponse:
    story = _get_published_story(db, slug)
    variants = db.scalars(select(StoryVariant).where(StoryVariant.story_id == story.id)).all()
    variants_by_lang: dict[str, StoryVariant] = {v.language: v for v in variants}
    resolved = resolve_display_variant(variants_by_lang, "en")  # type: ignore[arg-type]
    if resolved is None:
        raise APIError(404, "STORY_NOT_FOUND", f"No story with slug '{slug}'")
    variant = resolved.variant
    return ShareMetaResponse(
        title=variant.headline,
        description=variant.summary,
        canonical_url=f"{_public_web_url()}/story/{story.canonical_slug}",
        image_url=None,  # text-only preview in this phase, ADR-002
    )


@router.get("/topics/{slug}")
def get_topic(slug: str, cursor: str | None = Query(default=None), db: Session = Depends(get_db)) -> TopicDetailResponse:
    topic = db.scalars(select(Topic).where(Topic.slug == slug)).first()
    if topic is None:
        raise APIError(404, "TOPIC_NOT_FOUND", f"No topic with slug '{slug}'")
    page = _list_page(db, topic_slug=slug, country=None, limit=DEFAULT_PAGE_SIZE, cursor=cursor)
    count = db.scalar(select(func.count()).select_from(_published_query(topic_slug=slug).subquery())) or 0
    return TopicDetailResponse(topic=topic_out(topic, count), stories=page.items, next_cursor=page.next_cursor)


@router.get("/search", dependencies=[Depends(rate_limit_search)])
def search(
    q: str = Query(min_length=1, max_length=200), limit: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=100),
    cursor: str | None = Query(default=None, max_length=512),
    db: Session = Depends(get_db),
) -> SearchResponse:
    q = q.strip()
    if not q:
        raise APIError(422, "QUERY_REQUIRED", "Enter a search query")
    boundary = decode_search_cursor(cursor, q)
    # Search only displayable variants, preserving the English fallback gate.
    pattern = "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
    matching = select(StoryVariant.story_id).where(
        or_(StoryVariant.language == "en", and_(StoryVariant.language == "te", StoryVariant.qa_status == "PASSED")),
        or_(StoryVariant.headline.ilike(pattern, escape="\\"), StoryVariant.summary.ilike(pattern, escape="\\")),
    )
    stmt = _published_query().where(Story.id.in_(matching))
    if boundary is not None:
        at, story_id = boundary
        if at is None:
            stmt = stmt.where(Story.published_at.is_(None), Story.id > story_id)
        else:
            stmt = stmt.where(or_(Story.published_at < at, Story.published_at.is_(None),
                                  and_(Story.published_at == at, Story.id > story_id)))
    rows = list(db.scalars(stmt.limit(limit + 1)))
    stories = rows[:limit]
    loaded = load_story_relations(db, [s.id for s in stories])
    next_cursor = encode_search_cursor(q, stories[-1].published_at, stories[-1].id) if len(rows) > limit else None
    return SearchResponse(query=q, items=[story_to_out(db, s, loaded) for s in stories], next_cursor=next_cursor)


@router.get("/config")
def get_config(db: Session = Depends(get_db)) -> ConfigResponse:
    return ConfigResponse(
        features={
            "ai_translation_enabled": _env_flag("AI_TRANSLATION_ENABLED", default=False),
            "push_notifications_enabled": _env_flag("PUSH_NOTIFICATIONS_ENABLED", default=False),
        },
        topics=active_topics_out(db),
    )


@router.post("/events", dependencies=[Depends(rate_limit_events)])
def track_event(body: AnalyticsEventIn) -> AnalyticsEventResponse:
    """T17 §9.4 client-emitted events (`story_share`, `notification_received`,
    `notification_open`) — the ones the server can't observe on its own
    (a user tapping share, or a device receiving/opening a push). No auth:
    browsing/sharing works without login (NON_NEGOTIABLES #9), and there's
    no per-user data here beyond whatever the caller puts in `properties`.
    """

    analytics.track(body.event, body.properties)
    return AnalyticsEventResponse()


@router.post("/stories/{story_id}/reports", status_code=201, dependencies=[Depends(rate_limit_reports)])
def report_story(
    story_id: UUID, body: ReaderReportIn, request: Request, db: Session = Depends(get_db)
) -> ReaderReportAccepted:
    """ADR-029: a private reader report on a public story, for editors only.
    No login (NON_NEGOTIABLES #9). The free text is stored here and nowhere
    else — the analytics event carries only the story, category and platform.
    """

    story = db.scalars(select(Story).where(Story.id == story_id, Story.status.in_(PUBLIC_STATUSES))).first()
    if story is None:
        raise APIError(404, "STORY_NOT_FOUND", f"No story with id '{story_id}'")
    description = (body.description or "").strip() or None
    reader_reports.submit_report(
        db, story_id=story.id, category=body.category, description=description, language=body.language,
        platform=body.platform, sender=reader_reports.client_hash(_client_ip(request), datetime.now(UTC)),
    )
    analytics.track("report_issue", {"story_id": str(story.id), "category": body.category, "platform": body.platform})
    return ReaderReportAccepted()
