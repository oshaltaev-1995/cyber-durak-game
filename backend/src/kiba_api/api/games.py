"""FastAPI routes for process-local human-versus-bot games."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from kiba_api.api.cards import parse_card_codes
from kiba_api.api.schemas import GameResponse, HumanActionRequest
from kiba_api.api.serialization import serialize_game_session
from kiba_api.sessions import GameSessionService

router = APIRouter(prefix="/api/games", tags=["games"])


def get_game_service(request: Request) -> GameSessionService:
    """Resolve the process-local service configured by the application factory."""
    return request.app.state.game_service


GameServiceDependency = Annotated[GameSessionService, Depends(get_game_service)]


@router.post("", response_model=GameResponse, status_code=201, summary="Create a new game")
def create_game(service: GameServiceDependency) -> GameResponse:
    """Create a fresh human Seat.ONE versus bot Seat.TWO session."""
    return serialize_game_session(service.create_game())


@router.get("/{game_id}", response_model=GameResponse, summary="Get public game state")
def get_game(game_id: str, service: GameServiceDependency) -> GameResponse:
    """Return public state without bot cards or hidden draw-pile order."""
    return serialize_game_session(service.get_game(game_id))


@router.post("/{game_id}/actions", response_model=GameResponse, summary="Play a human action")
def play_action(
    game_id: str,
    action: HumanActionRequest,
    service: GameServiceDependency,
) -> GameResponse:
    """Apply one human action and auto-advance all following bot decisions."""
    cards = parse_card_codes(getattr(action, "cards", []))
    session = service.play_human_action(game_id, action.action, cards)
    return serialize_game_session(session)
