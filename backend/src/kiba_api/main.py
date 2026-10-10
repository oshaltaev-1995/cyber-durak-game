"""FastAPI application entrypoint."""

import logging
from dataclasses import replace
from datetime import timedelta
from time import perf_counter
from uuid import UUID, uuid4

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text
from starlette.middleware.trustedhost import TrustedHostMiddleware

from kiba_api.api.account import router as account_router
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
from kiba_api.emailing import EmailSender, create_email_sender
from kiba_api.game import BoutActionError, GameActionError
from kiba_api.observability import configure_logging
from kiba_api.persistence import (
    AccountDataService,
    CosmeticAward,
    CosmeticError,
    CosmeticService,
    Database,
    MatchHistoryService,
    ProgressionService,
)
from kiba_api.pvp import (
    PvPError,
    PvPErrorCode,
    PvPParticipantCompletion,
    PvPRoomService,
    RoomTTLPolicy,
)
from kiba_api.sessions import (
    GameSessionService,
    HintError,
    InMemoryGameSessionStore,
    SessionActionError,
    SessionNotFoundError,
)

logger = logging.getLogger(__name__)


def create_app(
    game_service: GameSessionService | None = None,
    *,
    pvp_service: PvPRoomService | None = None,
    database: Database | None = None,
    settings: Settings | None = None,
    email_sender: EmailSender | None = None,
) -> FastAPI:
    """Create an API application with injectable game and persistence services."""
    resolved_settings = settings or Settings.from_env()
    configure_logging(json_logs=resolved_settings.log_json or resolved_settings.is_production)
    application = FastAPI(title="Kiba API", version="0.1.0")
    resolved_database = database or Database(resolved_settings.database_url)
    match_history_service = MatchHistoryService(resolved_database)
    progression_service = ProgressionService(resolved_database)
    cosmetic_service = CosmeticService(resolved_database, progression_service)
    account_data_service = AccountDataService(resolved_database)

    def with_cosmetics(award, user_id):
        cosmetic_sync = cosmetic_service.synchronize(user_id)
        return replace(
            award,
            new_cosmetics=tuple(
                CosmeticAward(
                    code=definition.code.value,
                    category=definition.category.value,
                    title=definition.title,
                    title_en=definition.title_en,
                )
                for definition in cosmetic_sync.new_unlocks
            ),
        )

    def record_completion(session):
        if session.user_id is None or not account_data_service.user_exists(session.user_id):
            return None
        match_history_service.record_completed_match(session)
        match = match_history_service.get_match_by_game_session(session.game_id)
        award = progression_service.synchronize_for_match(session.user_id, match.id)
        return with_cosmetics(award, session.user_id)

    def record_pvp_completion(room):
        matches = match_history_service.record_completed_pvp_room(room)
        results = []
        for participant in room.participants:
            if (
                participant.user_id is None
                or participant.participant_id not in matches
                or not account_data_service.user_exists(participant.user_id)
            ):
                results.append(PvPParticipantCompletion(participant.participant_id, False))
                continue
            match = matches[participant.participant_id]
            award = progression_service.synchronize_for_match(participant.user_id, match.id)
            results.append(
                PvPParticipantCompletion(
                    participant.participant_id,
                    True,
                    with_cosmetics(award, participant.user_id),
                )
            )
        return tuple(results)

    application.state.game_service = game_service or GameSessionService(
        store=InMemoryGameSessionStore(
            active_ttl=timedelta(seconds=resolved_settings.bot_session_active_ttl_seconds),
            complete_ttl=timedelta(seconds=resolved_settings.bot_session_complete_ttl_seconds),
        ),
        completion_recorder=record_completion,
    )
    application.state.pvp_service = pvp_service or PvPRoomService(
        completion_recorder=record_pvp_completion,
        ttl=RoomTTLPolicy(
            waiting=timedelta(seconds=resolved_settings.pvp_waiting_ttl_seconds),
            complete=timedelta(seconds=resolved_settings.pvp_complete_ttl_seconds),
            disconnected_active=timedelta(seconds=resolved_settings.pvp_disconnected_ttl_seconds),
        ),
    )
    application.state.pvp_hub = PvPConnectionHub()
    application.state.settings = resolved_settings
    application.state.database = resolved_database
    application.state.email_sender = email_sender or create_email_sender(resolved_settings)
    application.state.match_history_service = match_history_service
    application.state.progression_service = progression_service
    application.state.cosmetic_service = cosmetic_service
    application.state.account_data_service = account_data_service
    application.state.auth_rate_limiter = AuthRateLimiter(
        resolved_settings.auth_rate_limit_attempts,
        resolved_settings.auth_rate_limit_window_seconds,
    )
    application.state.account_token_rate_limiter = AuthRateLimiter(
        resolved_settings.account_token_rate_limit_attempts,
        resolved_settings.account_token_rate_limit_window_seconds,
    )
    application.state.pvp_action_rate_limiter = AuthRateLimiter(
        resolved_settings.pvp_action_rate_limit_attempts,
        resolved_settings.pvp_action_rate_limit_window_seconds,
    )
    application.include_router(auth_router)
    application.include_router(account_router)
    application.include_router(games_router)
    application.include_router(history_router)
    application.include_router(progression_router)
    application.include_router(cosmetics_router)
    application.include_router(pvp_router)

    if resolved_settings.is_production:
        application.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=list(resolved_settings.trusted_hosts),
        )

    @application.middleware("http")
    async def security_and_observability(request: Request, call_next):
        request_id = _request_id(request.headers.get("x-request-id"))
        request.state.request_id = request_id
        started = perf_counter()
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
        route = request.scope.get("route")
        path = getattr(route, "path", request.url.path)
        logger.info(
            "http_request",
            extra={
                "event": "http_request",
                "request_id": request_id,
                "method": request.method,
                "path": path,
                "status_code": response.status_code,
                "duration_ms": round((perf_counter() - started) * 1000, 2),
            },
        )
        return response

    @application.get("/health", tags=["system"])
    def health() -> dict[str, str]:
        """Report whether the API process is healthy."""
        return {"status": "ok"}

    @application.get("/api/capabilities", tags=["system"])
    def capabilities() -> dict[str, bool]:
        """Expose only safe public product capabilities needed by the client."""
        return {
            "multiplayer_3_4_enabled": resolved_settings.multiplayer_3_4_enabled,
            "deck_variants_enabled": resolved_settings.deck_variants_enabled,
        }

    @application.get("/ready", tags=["system"])
    def ready() -> JSONResponse:
        """Report whether PostgreSQL can serve application requests."""
        try:
            with resolved_database.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
        except Exception:
            logger.exception("readiness_database_unavailable")
            return JSONResponse(status_code=503, content={"status": "unavailable"})
        return JSONResponse(content={"status": "ready"})

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

    @application.exception_handler(HintError)
    async def invalid_hint_request(_request: Request, error: HintError) -> JSONResponse:
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
            AuthErrorCode.INVALID_ACCOUNT_TOKEN: 400,
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
            PvPErrorCode.ROOM_CLOSED: 410,
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
            PvPErrorCode.FEATURE_NOT_AVAILABLE: 409,
            PvPErrorCode.INVALID_CAPACITY: 422,
            PvPErrorCode.PARTICIPANT_ALREADY_JOINED: 409,
            PvPErrorCode.REMATCH_NOT_AVAILABLE: 409,
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

    @application.exception_handler(Exception)
    async def unexpected_error(request: Request, error: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", uuid4().hex)
        logger.exception(
            "unhandled_http_error",
            exc_info=error,
            extra={"event": "unhandled_http_error", "request_id": request_id},
        )
        return JSONResponse(
            status_code=500,
            content={"detail": {"code": "internal_error", "request_id": request_id}},
            headers={"X-Request-ID": request_id},
        )

    application.router.add_event_handler("shutdown", resolved_database.dispose)

    return application


def _error_response(status_code: int, code: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"detail": {"code": code}})


def _request_id(value: str | None) -> str:
    if value is not None:
        try:
            return str(UUID(value))
        except ValueError:
            pass
    return str(uuid4())


app = create_app()
