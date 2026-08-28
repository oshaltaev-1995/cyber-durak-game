"""Authenticated completed-match statistics and private history routes."""

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel

from kiba_api.api.auth import CurrentUser
from kiba_api.persistence import (
    CompletedMatch,
    MatchHistoryService,
    MatchStatistics,
    OpponentType,
)

router = APIRouter(tags=["history"])


class StatisticsResponse(BaseModel):
    games_played: int
    wins: int
    losses: int
    draws: int
    win_rate: float
    current_win_streak: int
    best_win_streak: int
    total_transfers: int
    total_takes: int
    total_throw_ins: int
    highest_transfer_target: int
    arithmetic_mean_throw_ins: int
    bot_games: int
    bot_wins: int
    pvp_games: int
    pvp_wins: int


class MatchResponse(BaseModel):
    id: str
    outcome: Literal["WIN", "LOSS", "DRAW"]
    opponent_type: Literal["BOT", "PVP"]
    opponent_display_name: str | None
    started_at: datetime
    completed_at: datetime
    duration_seconds: int
    initial_attacker: Literal["HUMAN", "BOT", "YOU", "OPPONENT"]
    final_human_card_count: int
    final_bot_card_count: int
    human_action_count: int
    human_transfer_count: int
    human_take_count: int
    human_throw_in_count: int
    max_transfer_target: int
    arithmetic_mean_throw_in_count: int


class MatchHistoryResponse(BaseModel):
    items: list[MatchResponse]
    total: int
    limit: int
    offset: int


def get_match_history_service(request: Request) -> MatchHistoryService:
    return request.app.state.match_history_service


MatchHistoryDependency = Annotated[
    MatchHistoryService,
    Depends(get_match_history_service),
]


@router.get("/api/stats", response_model=StatisticsResponse, summary="Get account statistics")
def get_statistics(
    user: CurrentUser,
    service: MatchHistoryDependency,
) -> StatisticsResponse:
    """Return aggregates derived only from the current account's match rows."""
    return _serialize_statistics(service.get_statistics(user.id))


@router.get("/api/matches", response_model=MatchHistoryResponse, summary="Get match history")
def get_matches(
    user: CurrentUser,
    service: MatchHistoryDependency,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    opponent_type: Literal["BOT", "PVP"] | None = None,
) -> MatchHistoryResponse:
    """Return the current account's newest completed matches."""
    selected_type = OpponentType(opponent_type) if opponent_type is not None else None
    matches = service.list_matches(
        user.id,
        limit=limit,
        offset=offset,
        opponent_type=selected_type,
    )
    return MatchHistoryResponse(
        items=[_serialize_match(match) for match in matches],
        total=service.count_matches(user.id, selected_type),
        limit=limit,
        offset=offset,
    )


def _serialize_statistics(statistics: MatchStatistics) -> StatisticsResponse:
    return StatisticsResponse(
        **{field: getattr(statistics, field) for field in StatisticsResponse.model_fields}
    )


def _serialize_match(match: CompletedMatch) -> MatchResponse:
    initial_attacker = "HUMAN" if match.initial_attacker == match.user_seat else "BOT"
    if match.opponent_type == OpponentType.PVP.value:
        initial_attacker = "YOU" if match.initial_attacker == match.user_seat else "OPPONENT"
    return MatchResponse(
        id=str(match.id),
        outcome=match.outcome,
        opponent_type=match.opponent_type,
        opponent_display_name=match.opponent_display_name,
        started_at=match.started_at,
        completed_at=match.completed_at,
        duration_seconds=match.duration_seconds,
        initial_attacker=initial_attacker,
        final_human_card_count=match.final_human_card_count,
        final_bot_card_count=match.final_bot_card_count,
        human_action_count=match.human_action_count,
        human_transfer_count=match.human_transfer_count,
        human_take_count=match.human_take_count,
        human_throw_in_count=match.human_throw_in_count,
        max_transfer_target=match.max_transfer_target,
        arithmetic_mean_throw_in_count=match.arithmetic_mean_throw_in_count,
    )
