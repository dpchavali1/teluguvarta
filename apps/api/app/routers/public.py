"""Public endpoints — no auth, always available (NON_NEGOTIABLES #9).

T14: wired to real data via app/content/serialize.py. Only `PUBLIC_STATUSES`
stories (published at least once) are ever visible here — DRAFT/AI_READY/
REVIEW_REQUIRED/APPROVED/SCHEDULED/ARCHIVED stories stay internal.
"""

import base64
import os
import re

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import analytics
from app.content.ranking import Preferences, rank_stories
from app.content.serialize import (
    PUBLIC_STATUSES,
    story_to_out,
    story_to_rankable,
    topic_out,
)
from app.content.variants import resolve_display_variant
from app.content.why_matters import get_or_generate as get_or_generate_why_matters
from app.db import get_db
from app.errors import APIError
from app.models import (
    PilotSignup,
    Source,
    SourceItem,
    Story,
    StorySource,
    StoryTopic,
    StoryVariant,
    Topic,
)
from app.rate_limit import rate_limit_search, rate_limit_signup
from app.schemas import (
    AnalyticsEventIn,
    AnalyticsEventResponse,
    ConfigResponse,
    HomeResponse,
    PersonalizationOut,
    PilotSignupIn,
    PilotSignupOut,
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


def _published_story_ids(
    db: Session, *, topic_slug: str | None = None, country: str | None = None
) -> list:
    stmt = select(Story.id).where(Story.status.in_(PUBLIC_STATUSES))
    if topic_slug is not None:
        stmt = stmt.join(StoryTopic, StoryTopic.story_id == Story.id).join(
            Topic, Topic.id == StoryTopic.topic_id
        ).where(Topic.slug == topic_slug)
    if country is not None:
        stmt = stmt.join(StorySource, StorySource.story_id == Story.id).join(
            SourceItem, SourceItem.id == StorySource.source_item_id
        ).join(Source, Source.id == SourceItem.source_id).where(Source.country == country)
    stmt = stmt.order_by(Story.published_at.desc().nulls_last(), Story.id)
    return list(db.scalars(stmt).unique().all())


def _list_page(
    db: Session, *, topic_slug: str | None, country: str | None, limit: int, cursor: str | None
) -> StoriesListResponse:
    offset = _decode_cursor(cursor)
    ids = _published_story_ids(db, topic_slug=topic_slug, country=country)
    page_ids = ids[offset : offset + limit]
    stories = [db.get(Story, sid) for sid in page_ids]
    items = [story_to_out(db, s) for s in stories if s is not None]
    next_cursor = _encode_cursor(offset + limit) if offset + limit < len(ids) else None
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
    segment: Segment = Query(default="general"),
    db: Session = Depends(get_db),
) -> HomeResponse:
    prefs = Preferences(
        residence_country=residence_country,
        residence_region=residence_region,
        home_state=home_state,
        home_city=home_city,
        topics=tuple(t.strip() for t in topics_pref.split(",") if t.strip()) if topics_pref else (),
    )

    if prefs.is_empty():
        # T16/ADR-005: personalization is additive — no preferences supplied
        # (the common case for an anonymous, no-account-yet visitor per
        # NON_NEGOTIABLES #9) means the existing T14 chronological feed.
        ids = _published_story_ids(db)[:HOME_PAGE_SIZE]
        stories = [db.get(Story, sid) for sid in ids]
        top_stories = [story_to_out(db, s) for s in stories if s is not None]
    else:
        candidate_ids = _published_story_ids(db)[:HOME_CANDIDATE_POOL]
        candidate_rows = [db.get(Story, sid) for sid in candidate_ids]
        candidates: list[Story] = [s for s in candidate_rows if s is not None]
        rankable = [story_to_rankable(db, s) for s in candidates]
        ranked = rank_stories(rankable, prefs)[:HOME_PAGE_SIZE]
        stories_by_id = {str(s.id): s for s in candidates}
        top_stories = []
        for scored in ranked:
            story = stories_by_id[scored.story_id]
            out = story_to_out(db, story)
            why_matters = get_or_generate_why_matters(db, story, segment)
            out.personalization = PersonalizationOut(
                score=scored.score, explanation=scored.explanation, why_matters=why_matters,
            )
            top_stories.append(out)

    topics = db.scalars(select(Topic).where(Topic.active.is_(True)).order_by(Topic.name)).all()
    return HomeResponse(top_stories=top_stories, topics=[topic_out(t) for t in topics])


@router.get("/stories")
def list_stories(
    topic: str | None = Query(default=None),
    country: str | None = Query(default=None),
    limit: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=100),
    cursor: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> StoriesListResponse:
    return _list_page(db, topic_slug=topic, country=country, limit=limit, cursor=cursor)


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
def get_topic(slug: str, db: Session = Depends(get_db)) -> TopicDetailResponse:
    topic = db.scalars(select(Topic).where(Topic.slug == slug)).first()
    if topic is None:
        raise APIError(404, "TOPIC_NOT_FOUND", f"No topic with slug '{slug}'")
    page = _list_page(db, topic_slug=slug, country=None, limit=50, cursor=None)
    return TopicDetailResponse(topic=topic_out(topic), stories=page.items)


@router.get("/search", dependencies=[Depends(rate_limit_search)])
def search(
    q: str = Query(min_length=1), limit: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=100),
    db: Session = Depends(get_db),
) -> SearchResponse:
    # Postgres FTS/pg_trgm per NON_NEGOTIABLES #1 — `ILIKE` against the
    # already-`pg_trgm`-indexed `story_variants.headline`/`summary` (T03) is
    # the minimal correct query here; a ranked full-text query is future
    # scope once relevance tuning is actually measured, not before.
    pattern = f"%{q}%"
    story_ids = db.scalars(
        select(StoryVariant.story_id)
        .join(Story, Story.id == StoryVariant.story_id)
        .where(
            Story.status.in_(PUBLIC_STATUSES),
            StoryVariant.language == "en",
            (StoryVariant.headline.ilike(pattern) | StoryVariant.summary.ilike(pattern)),
        )
        .order_by(Story.published_at.desc().nulls_last())
        .limit(limit)
    ).unique().all()
    stories = [db.get(Story, sid) for sid in story_ids]
    items = [story_to_out(db, s) for s in stories if s is not None]
    return SearchResponse(query=q, items=items)


@router.get("/config")
def get_config(db: Session = Depends(get_db)) -> ConfigResponse:
    topics = db.scalars(select(Topic).where(Topic.active.is_(True)).order_by(Topic.name)).all()
    return ConfigResponse(
        features={
            "ai_translation_enabled": _env_flag("AI_TRANSLATION_ENABLED", default=False),
            "push_notifications_enabled": _env_flag("PUSH_NOTIFICATIONS_ENABLED", default=False),
        },
        topics=[topic_out(t) for t in topics],
    )


@router.post("/events")
def track_event(body: AnalyticsEventIn) -> AnalyticsEventResponse:
    """T17 §9.4 client-emitted events (`story_share`, `notification_received`,
    `notification_open`) — the ones the server can't observe on its own
    (a user tapping share, or a device receiving/opening a push). No auth:
    browsing/sharing works without login (NON_NEGOTIABLES #9), and there's
    no per-user data here beyond whatever the caller puts in `properties`.
    """

    analytics.track(body.event, body.properties)
    return AnalyticsEventResponse()


_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@router.post("/pilot-signups", status_code=201, dependencies=[Depends(rate_limit_signup)])
def create_pilot_signup(body: PilotSignupIn, db: Session = Depends(get_db)) -> PilotSignupOut:
    """T20 pre-build validation gate: capture a landing-page opt-in. Public,
    no auth (NON_NEGOTIABLES #9) — same-day-repeatable, tightly rate-limited
    since it's a write. Re-signup with the same email updates which example
    feed/segment drew them back rather than erroring, so a visitor who
    revisits and picks a different example feed still counts once.
    """
    email = body.email.strip().lower()
    if not _EMAIL_PATTERN.match(email):
        raise APIError(422, "INVALID_EMAIL", "Enter a valid email address")

    existing = db.scalars(select(PilotSignup).where(PilotSignup.email == email)).first()
    if existing is not None:
        existing.segment = body.segment or existing.segment
        existing.example_feed = body.example_feed or existing.example_feed
        if body.recommend_willingness is not None:
            existing.recommend_willingness = body.recommend_willingness
        db.commit()
        db.refresh(existing)
        return PilotSignupOut(id=existing.id, created_at=existing.created_at)

    signup = PilotSignup(
        email=email,
        segment=body.segment,
        example_feed=body.example_feed,
        recommend_willingness=body.recommend_willingness,
    )
    db.add(signup)
    db.commit()
    db.refresh(signup)
    analytics.track("pilot_signup_created", {"segment": body.segment, "example_feed": body.example_feed})
    return PilotSignupOut(id=signup.id, created_at=signup.created_at)
