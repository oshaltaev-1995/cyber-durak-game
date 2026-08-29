"""Authenticated cosmetic catalogue and loadout routes."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, model_validator

from kiba_api.api.auth import CsrfDependency, CurrentUser
from kiba_api.api.locale import RequestLocale
from kiba_api.locale import Locale
from kiba_api.persistence import (
    ACHIEVEMENTS,
    CosmeticCatalogueState,
    CosmeticService,
    CosmeticUnlockType,
)

router = APIRouter(tags=["cosmetics"])


class _StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CosmeticLoadoutResponse(BaseModel):
    card_back_code: str
    table_theme_code: str
    profile_frame_code: str


class CosmeticUnlockResponse(BaseModel):
    type: str
    requirement: int | str | None
    achievement_title: str | None


class CosmeticItemResponse(BaseModel):
    code: str
    category: str
    title: str
    description: str
    unlocked: bool
    equipped: bool
    unlock: CosmeticUnlockResponse
    unlocked_at: datetime | None


class CosmeticsResponse(BaseModel):
    items: list[CosmeticItemResponse]
    loadout: CosmeticLoadoutResponse


class CosmeticEquipRequest(_StrictRequest):
    card_back_code: str | None = None
    table_theme_code: str | None = None
    profile_frame_code: str | None = None

    @model_validator(mode="after")
    def require_one_selection(self) -> CosmeticEquipRequest:
        if not any(
            (
                self.card_back_code,
                self.table_theme_code,
                self.profile_frame_code,
            )
        ):
            raise ValueError("at least one cosmetic selection is required")
        return self


def get_cosmetic_service(request: Request) -> CosmeticService:
    return request.app.state.cosmetic_service


CosmeticDependency = Annotated[CosmeticService, Depends(get_cosmetic_service)]


@router.get("/api/cosmetics", response_model=CosmeticsResponse, summary="Get cosmetic catalogue")
def get_cosmetics(
    user: CurrentUser,
    service: CosmeticDependency,
    locale: RequestLocale,
) -> CosmeticsResponse:
    """Synchronize rewards and return the account's catalogue and loadout."""
    return _serialize_catalogue(service.get_catalogue(user.id), locale)


@router.patch(
    "/api/profile/cosmetics",
    response_model=CosmeticsResponse,
    summary="Equip unlocked cosmetics",
)
def equip_cosmetics(
    payload: CosmeticEquipRequest,
    _csrf: CsrfDependency,
    user: CurrentUser,
    service: CosmeticDependency,
    locale: RequestLocale,
) -> CosmeticsResponse:
    """Update only supplied loadout categories after server-side ownership checks."""
    return _serialize_catalogue(
        service.equip(
            user.id,
            card_back_code=payload.card_back_code,
            table_theme_code=payload.table_theme_code,
            profile_frame_code=payload.profile_frame_code,
        ),
        locale,
    )


def _serialize_catalogue(state: CosmeticCatalogueState, locale: Locale) -> CosmeticsResponse:
    achievement_titles = {
        definition.code.value: definition.localized_title(locale) for definition in ACHIEVEMENTS
    }
    return CosmeticsResponse(
        items=[
            CosmeticItemResponse(
                code=item.definition.code.value,
                category=item.definition.category.value,
                title=item.definition.localized_title(locale),
                description=item.definition.localized_description(locale),
                unlocked=item.unlocked,
                equipped=item.equipped,
                unlock=CosmeticUnlockResponse(
                    type=item.definition.unlock_type.value,
                    requirement=(
                        item.definition.unlock_requirement.value
                        if hasattr(item.definition.unlock_requirement, "value")
                        else item.definition.unlock_requirement
                    ),
                    achievement_title=(
                        achievement_titles.get(item.definition.unlock_requirement.value)
                        if item.definition.unlock_type is CosmeticUnlockType.ACHIEVEMENT
                        else None
                    ),
                ),
                unlocked_at=item.unlocked_at,
            )
            for item in state.items
        ],
        loadout=CosmeticLoadoutResponse(
            card_back_code=state.loadout.card_back_code,
            table_theme_code=state.loadout.table_theme_code,
            profile_frame_code=state.loadout.profile_frame_code,
        ),
    )
