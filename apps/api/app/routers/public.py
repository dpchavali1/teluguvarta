"""Public endpoints — no auth, always available (NON_NEGOTIABLES #9).

All data is stub/placeholder: T06+ (source registry, ingestion, story
generation) haven't landed yet. The response *shapes* are final.
"""

from fastapi import APIRouter, Query

from app.errors import APIError
from app.schemas import (
    ConfigResponse,
    HomeResponse,
    SearchResponse,
    ShareMetaResponse,
    StoriesListResponse,
    StoryOut,
    TopicDetailResponse,
)

router = APIRouter(prefix="/v1", tags=["public"])


@router.get("/home")
def get_home() -> HomeResponse:
    return HomeResponse()


@router.get("/stories")
def list_stories() -> StoriesListResponse:
    return StoriesListResponse(items=[])


@router.get("/stories/{slug}")
def get_story(slug: str) -> StoryOut:
    raise APIError(404, "STORY_NOT_FOUND", f"No story with slug '{slug}'")


@router.get("/stories/{slug}/share-meta")
def get_story_share_meta(slug: str) -> ShareMetaResponse:
    raise APIError(404, "STORY_NOT_FOUND", f"No story with slug '{slug}'")


@router.get("/topics/{slug}")
def get_topic(slug: str) -> TopicDetailResponse:
    raise APIError(404, "TOPIC_NOT_FOUND", f"No topic with slug '{slug}'")


@router.get("/search")
def search(q: str = Query(min_length=1)) -> SearchResponse:
    return SearchResponse(query=q, items=[])


@router.get("/config")
def get_config() -> ConfigResponse:
    return ConfigResponse(
        features={
            "ai_translation_enabled": False,
            "push_notifications_enabled": False,
        }
    )
