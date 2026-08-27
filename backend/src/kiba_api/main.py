"""FastAPI application entrypoint."""

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from kiba_api.api.auth import router as auth_router
from kiba_api.api.cards import CardCodeError
from kiba_api.api.games import router as games_router
from kiba_api.api.history import router as history_router
from kiba_api.auth import AuthError, AuthErrorCode, AuthRateLimiter
from kiba_api.config import Settings
from kiba_api.game import BoutActionError, GameActionError
from kiba_api.persistence import Database, MatchHistoryService
from kiba_api.sessions import GameSessionService, SessionActionError, SessionNotFoundError


def create_app(
    game_service: GameSessionService | None = None,
    *,
    database: Database | None = None,
    settings: Settings | None = None,
) -> FastAPI:
    """Create an API application with injectable game and persistence services."""
    resolved_settings = settings or Settings.from_env()
    application = FastAPI(title="Kiba API", version="0.1.0")
    resolved_database = database or Database(resolved_settings.database_url)
    match_history_service = MatchHistoryService(resolved_database)
    application.state.game_service = game_service or GameSessionService(
        completion_recorder=match_history_service.record_completed_match
    )
    application.state.settings = resolved_settings
    application.state.database = resolved_database
    application.state.match_history_service = match_history_service
    application.state.auth_rate_limiter = AuthRateLimiter(
        resolved_settings.auth_rate_limit_attempts,
        resolved_settings.auth_rate_limit_window_seconds,
    )
    application.include_router(auth_router)
    application.include_router(games_router)
    application.include_router(history_router)

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
