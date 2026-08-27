"""FastAPI application entrypoint."""

from dataclasses import replace

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from kiba_api.api.auth import router as auth_router
from kiba_api.api.cards import CardCodeError
from kiba_api.api.cosmetics import router as cosmetics_router
from kiba_api.api.games import router as games_router
from kiba_api.api.history import router as history_router
from kiba_api.api.progression import router as progression_router
from kiba_api.api.pvp import PvPConnectionHub
from kiba_api.api.pvp import router as pvp_router
from kiba_api.auth import AuthError, AuthErrorCode, AuthRateLimiter
from kiba_api.config import Settings
from kiba_api.game import BoutActionError, GameActionError
from kiba_api.persistence import (
    CosmeticAward,
    CosmeticError,
    CosmeticService,
    Database,
    MatchHistoryService,
    ProgressionService,
)
from kiba_api.pvp import PvPError, PvPErrorCode, PvPRoomService
from kiba_api.sessions import GameSessionService, SessionActionError, SessionNotFoundError


def create_app(
    game_service: GameSessionService | None = None,
    *,
    pvp_service: PvPRoomService | None = None,
    database: Database | None = None,
    settings: Settings | None = None,
) -> FastAPI:
    """Create an API application with injectable game and persistence services."""
    resolved_settings = settings or Settings.from_env()
    application = FastAPI(title="Kiba API", version="0.1.0")
    resolved_database = database or Database(resolved_settings.database_url)
    match_history_service = MatchHistoryService(resolved_database)
    progression_service = ProgressionService(resolved_database)
    cosmetic_service = CosmeticService(resolved_database, progression_service)

    def record_completion(session):
        match_history_service.record_completed_match(session)
        match = match_history_service.get_match_by_game_session(session.game_id)
        award = progression_service.synchronize_for_match(session.user_id, match.id)
        cosmetic_sync = cosmetic_service.synchronize(session.user_id)
        return replace(
            award,
            new_cosmetics=tuple(
                CosmeticAward(
                    code=definition.code.value,
                    category=definition.category.value,
                    title=definition.title,
                )
                for definition in cosmetic_sync.new_unlocks
            ),
        )

    application.state.game_service = game_service or GameSessionService(
        completion_recorder=record_completion
    )
    application.state.pvp_service = pvp_service or PvPRoomService()
    application.state.pvp_hub = PvPConnectionHub()
    application.state.settings = resolved_settings
    application.state.database = resolved_database
    application.state.match_history_service = match_history_service
    application.state.progression_service = progression_service
    application.state.cosmetic_service = cosmetic_service
    application.state.auth_rate_limiter = AuthRateLimiter(
        resolved_settings.auth_rate_limit_attempts,
        resolved_settings.auth_rate_limit_window_seconds,
    )
    application.state.pvp_action_rate_limiter = AuthRateLimiter(
        resolved_settings.pvp_action_rate_limit_attempts,
        resolved_settings.pvp_action_rate_limit_window_seconds,
    )
    application.include_router(auth_router)
    application.include_router(games_router)
    application.include_router(history_router)
    application.include_router(progression_router)
    application.include_router(cosmetics_router)
    application.include_router(pvp_router)

    @application.get("/health", tags=["system"])
    def health() -> dict[str, str]:
        """Report whether the API process is healthy."""
        return {"status": "ok"}

    @application.exception_handler(SessionNotFoundError)
    async def session_not_found(
        _request: Request,
        error: SessionNotFoundError,
    ) -> JSONResponse:
        return _error_response(404, error.code)

    @application.exception_handler(CardCodeError)
    async def invalid_card_code(_request: Request, error: CardCodeError) -> JSONResponse:
        return _error_response(422, error.code.value)

    @application.exception_handler(SessionActionError)
    async def invalid_session_action(
        _request: Request,
        error: SessionActionError,
    ) -> JSONResponse:
        return _error_response(409, error.code.value)

    @application.exception_handler(GameActionError)
    async def invalid_game_action(_request: Request, error: GameActionError) -> JSONResponse:
        return _error_response(409, error.code.value)

    @application.exception_handler(BoutActionError)
    async def invalid_bout_action(_request: Request, error: BoutActionError) -> JSONResponse:
        return _error_response(409, error.code.value)

    @application.exception_handler(AuthError)
    async def invalid_auth_action(_request: Request, error: AuthError) -> JSONResponse:
        status_codes = {
            AuthErrorCode.EMAIL_ALREADY_REGISTERED: 409,
            AuthErrorCode.INVALID_CREDENTIALS: 401,
            AuthErrorCode.AUTHENTICATION_REQUIRED: 401,
            AuthErrorCode.RATE_LIMITED: 429,
            AuthErrorCode.INVALID_CSRF_ORIGIN: 403,
        }
        return _error_response(status_codes[error.code], error.code.value)

    @application.exception_handler(CosmeticError)
    async def invalid_cosmetic(_request: Request, error: CosmeticError) -> JSONResponse:
        return _error_response(409, error.code.value)

    @application.exception_handler(PvPError)
    async def invalid_pvp_action(_request: Request, error: PvPError) -> JSONResponse:
        status_codes = {
            PvPErrorCode.ROOM_NOT_FOUND: 404,
            PvPErrorCode.INVITE_EXPIRED: 410,
            PvPErrorCode.INVALID_NICKNAME: 422,
            PvPErrorCode.INVALID_CREDENTIAL: 401,
            PvPErrorCode.ROOM_FULL: 409,
            PvPErrorCode.GAME_NOT_READY: 409,
            PvPErrorCode.GAME_COMPLETE: 409,
            PvPErrorCode.WRONG_TURN: 409,
            PvPErrorCode.ILLEGAL_ACTION: 409,
            PvPErrorCode.STALE_VERSION: 409,
            PvPErrorCode.RATE_LIMITED: 429,
            PvPErrorCode.MESSAGE_TOO_LARGE: 413,
        }
        return _error_response(status_codes[error.code], error.code.value)

    @application.exception_handler(RequestValidationError)
    async def invalid_request(_request: Request, error: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "detail": {
                    "code": "invalid_request",
                    "errors": jsonable_encoder(error.errors()),
                }
            },
        )

    return application


def _error_response(status_code: int, code: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"detail": {"code": code}})


app = create_app()
