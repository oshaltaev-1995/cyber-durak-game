"""Authenticated XP, level, and achievement routes."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from kiba_api.api.auth import CurrentUser
from kiba_api.api.cosmetics import CosmeticDependency
from kiba_api.api.locale import RequestLocale
from kiba_api.persistence import ProgressionService, ProgressionSummary

router = APIRouter(tags=["progression"])


class ProgressionResponse(BaseModel):
    total_xp: int
    level: int
    level_start_xp: int
    next_level_xp: int
    xp_into_level: int
    xp_needed_for_next_level: int
    progress_fraction: float
    achievements_unlocked: int
    achievements_total: int


class AchievementResponse(BaseModel):
    code: str
    title: str
    description: str
    bonus_xp: int
    unlocked: bool
    unlocked_at: datetime | None


def get_progression_service(request: Request) -> ProgressionService:
    return request.app.state.progression_service


ProgressionDependency = Annotated[ProgressionService, Depends(get_progression_service)]


@router.get("/api/progression", response_model=ProgressionResponse, summary="Get XP and level")
def get_progression(
    user: CurrentUser,
    service: ProgressionDependency,
    cosmetics: CosmeticDependency,
) -> ProgressionResponse:
    """Synchronize historical matches and return derived account progression."""
    summary = service.synchronize(user.id)
    cosmetics.synchronize(user.id)
    return _serialize_summary(summary)


@router.get(
    "/api/achievements",
    response_model=list[AchievementResponse],
    summary="Get achievement catalogue",
)
def get_achievements(
    user: CurrentUser,
    service: ProgressionDependency,
    cosmetics: CosmeticDependency,
    locale: RequestLocale,
) -> list[AchievementResponse]:
    """Return the authoritative catalogue with current account unlock state."""
    service.synchronize(user.id)
    cosmetics.synchronize(user.id)
    return [
        AchievementResponse(
            code=state.definition.code.value,
            title=state.definition.localized_title(locale),
            description=state.definition.localized_description(locale),
            bonus_xp=state.definition.bonus_xp,
            unlocked=state.unlocked,
            unlocked_at=state.unlocked_at,
        )
        for state in service.get_achievements(user.id)
    ]


def _serialize_summary(summary: ProgressionSummary) -> ProgressionResponse:
    return ProgressionResponse(
        **{field: getattr(summary, field) for field in ProgressionResponse.model_fields}
    )
