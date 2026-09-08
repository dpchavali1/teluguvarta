"""Authenticated endpoints. Auth is stubbed pending T05 — see app/auth.py."""

from uuid import UUID, uuid4

from fastapi import APIRouter, Depends

from app.auth import Principal, current_user
from app.schemas import (
    DeleteAccountResponse,
    MeResponse,
    PreferencesUpdate,
    ProfileOut,
    PushTokenCreate,
    PushTokenResponse,
    SavedStoryResponse,
)

router = APIRouter(prefix="/v1/me", tags=["me"])


@router.get("")
def get_me(principal: Principal = Depends(current_user)) -> MeResponse:
    return MeResponse(id=uuid4(), profile=ProfileOut())


@router.patch("/preferences")
def update_preferences(
    body: PreferencesUpdate, principal: Principal = Depends(current_user)
) -> ProfileOut:
    return ProfileOut(
        residence_country=body.residence_country,
        residence_region=body.residence_region,
        home_state=body.home_state,
        home_city=body.home_city,
        language=body.language or "en",
        notification_mode=body.notification_mode,
    )


@router.post("/saved/{story_id}")
def save_story(story_id: UUID, principal: Principal = Depends(current_user)) -> SavedStoryResponse:
    return SavedStoryResponse(story_id=story_id, saved=True)


@router.delete("/saved/{story_id}")
def unsave_story(story_id: UUID, principal: Principal = Depends(current_user)) -> SavedStoryResponse:
    return SavedStoryResponse(story_id=story_id, saved=False)


@router.post("/push-tokens")
def register_push_token(
    body: PushTokenCreate, principal: Principal = Depends(current_user)
) -> PushTokenResponse:
    return PushTokenResponse(registered=True)


@router.delete("/account")
def delete_account(principal: Principal = Depends(current_user)) -> DeleteAccountResponse:
    return DeleteAccountResponse(deleted=True)
