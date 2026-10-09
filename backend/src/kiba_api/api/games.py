"""FastAPI routes for process-local human-versus-bot games."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from kiba_api.api.auth import OptionalCurrentUser
from kiba_api.api.cards import parse_card_codes
from kiba_api.api.cosmetics import CosmeticDependency
from kiba_api.api.locale import RequestLocale
from kiba_api.api.schemas import (
    CreateGameRequest,
    GameResponse,
    HintRequest,
    HintResponse,
    HumanActionRequest,
    RestartGameRequest,
)
from kiba_api.api.serialization import serialize_game_session, serialize_move_hints
from kiba_api.sessions import (
    GameAppearance,
    GameSessionService,
    SessionActionError,
    SessionErrorCode,
)

router = APIRouter(prefix="/api/games", tags=["games"])


def get_game_service(request: Request) -> GameSessionService:
    """Resolve the process-local service configured by the application factory."""
    return request.app.state.game_service


GameServiceDependency = Annotated[GameSessionService, Depends(get_game_service)]


@router.post("", response_model=GameResponse, status_code=201, summary="Create a new game")
def create_game(
    request: Request,
    service: GameServiceDependency,
    cosmetics: CosmeticDependency,
    user: OptionalCurrentUser,
    locale: RequestLocale,
    payload: CreateGameRequest | None = None,
) -> GameResponse:
    """Create one human plus one-to-three bots; omitted payload remains legacy two-player."""
    options = payload or CreateGameRequest()
    if options.total_players > 2 and not request.app.state.settings.multiplayer_3_4_enabled:
        raise SessionActionError(SessionErrorCode.FEATURE_NOT_AVAILABLE)
    user_id = user.id if user is not None else None
    appearance = GameAppearance()
    if user_id is not None:
        loadout = cosmetics.get_loadout(user_id)
        appearance = GameAppearance(
            card_back_code=loadout.card_back_code,
            table_theme_code=loadout.table_theme_code,
            profile_frame_code=loadout.profile_frame_code,
        )
    return serialize_game_session(
        service.create_game(
            user_id=user_id,
            appearance=appearance,
            total_players=options.total_players,
            human_display_name=(
                user.display_name if user is not None else options.human_display_name
            ),
        ),
        locale,
    )


@router.get("/{game_id}", response_model=GameResponse, summary="Get public game state")
def get_game(
    game_id: str,
    service: GameServiceDependency,
    locale: RequestLocale,
) -> GameResponse:
    """Return public state without bot cards or hidden draw-pile order."""
    return serialize_game_session(service.get_game(game_id), locale)


@router.post(
    "/{game_id}/restart",
    response_model=GameResponse,
    summary="Restart a bot game in the same session",
)
def restart_game(
    game_id: str,
    request: Request,
    service: GameServiceDependency,
    locale: RequestLocale,
    payload: RestartGameRequest | None = None,
) -> GameResponse:
    """Create a fresh authoritative deal while retaining the human-owned roster."""
    del payload
    session = service.get_game(game_id)
    if session.total_players > 2 and not request.app.state.settings.multiplayer_3_4_enabled:
        raise SessionActionError(SessionErrorCode.FEATURE_NOT_AVAILABLE)
    return serialize_game_session(service.restart_game(game_id), locale)


@router.post("/{game_id}/hints", response_model=HintResponse, summary="Get canonical move hints")
def get_hints(
    game_id: str,
    request: HintRequest,
    service: GameServiceDependency,
) -> HintResponse:
    """Return bounded read-only hints without bot cards or draw-pile order."""
    cards = parse_card_codes(request.selected_card_ids)
    return serialize_move_hints(service.get_hints(game_id, cards))


@router.post("/{game_id}/actions", response_model=GameResponse, summary="Play a human action")
def play_action(
    game_id: str,
    action: HumanActionRequest,
    service: GameServiceDependency,
    locale: RequestLocale,
) -> GameResponse:
    """Apply one human action and auto-advance all following bot decisions."""
    cards = parse_card_codes(getattr(action, "cards", []))
    session = service.play_human_action(game_id, action.action, cards)
    return serialize_game_session(session, locale)
