"""HTTP boundary for optional accounts and profiles."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from ipaddress import ip_address
from typing import Annotated
from urllib.parse import quote, urlsplit

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from sqlalchemy.orm import Session

from kiba_api.auth import AuthError, AuthErrorCode, AuthService, normalize_email
from kiba_api.config import Settings
from kiba_api.emailing import EmailDeliveryError, EmailSender
from kiba_api.persistence import Database, User

router = APIRouter(tags=["auth"])
logger = logging.getLogger(__name__)


class _StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RegisterRequest(_StrictRequest):
    email: EmailStr
    display_name: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("display_name")
    @classmethod
    def display_name_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("display name must not be blank")
        return value.strip()


class LoginRequest(_StrictRequest):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class ProfileUpdateRequest(_StrictRequest):
    display_name: str = Field(min_length=1, max_length=50)

    @field_validator("display_name")
    @classmethod
    def display_name_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("display name must not be blank")
        return value.strip()


class TokenRequest(_StrictRequest):
    token: str = Field(min_length=20, max_length=512)


class ForgotPasswordRequest(_StrictRequest):
    email: EmailStr


class ResetPasswordRequest(TokenRequest):
    new_password: str = Field(min_length=8, max_length=128)


class MessageResponse(BaseModel):
    message: str


class UserResponse(BaseModel):
    id: str
    email: EmailStr
    display_name: str
    created_at: str
    email_verified: bool
    verification_email_sent: bool | None = None


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_database(request: Request) -> Database:
    return request.app.state.database


def get_email_sender(request: Request) -> EmailSender:
    return request.app.state.email_sender


def get_database_session(database: Annotated[Database, Depends(get_database)]) -> Iterator[Session]:
    with database.session() as session:
        yield session


DatabaseSession = Annotated[Session, Depends(get_database_session)]
SettingsDependency = Annotated[Settings, Depends(get_settings)]
EmailSenderDependency = Annotated[EmailSender, Depends(get_email_sender)]


def get_auth_service(
    session: DatabaseSession,
    settings: SettingsDependency,
) -> AuthService:
    return AuthService(
        session,
        session_days=settings.auth_session_days,
        session_idle_days=settings.auth_session_idle_days,
        session_touch_minutes=settings.auth_session_touch_minutes,
        verification_token_hours=settings.verification_token_hours,
        password_reset_token_minutes=settings.password_reset_token_minutes,
    )


AuthServiceDependency = Annotated[AuthService, Depends(get_auth_service)]


def verify_csrf_origin(request: Request, settings: SettingsDependency) -> None:
    """Reject browser cross-site mutations while retaining direct non-browser clients."""
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return
    origin = request.headers.get("origin")
    referer = request.headers.get("referer")
    candidate = origin or (_origin_from_url(referer) if referer else None)
    if candidate is None:
        if settings.is_production or request.headers.get("sec-fetch-site") == "cross-site":
            raise AuthError(AuthErrorCode.INVALID_CSRF_ORIGIN)
        return
    request_origin = f"{request.url.scheme}://{request.headers.get('host', '')}".rstrip("/")
    if not is_trusted_origin(candidate, request_origin, settings):
        raise AuthError(AuthErrorCode.INVALID_CSRF_ORIGIN)


CsrfDependency = Annotated[None, Depends(verify_csrf_origin)]


def current_user(
    request: Request,
    service: AuthServiceDependency,
    settings: SettingsDependency,
) -> User:
    return service.authenticate(request.cookies.get(settings.auth_cookie_name))


CurrentUser = Annotated[User, Depends(current_user)]


def optional_current_user(
    request: Request,
    service: AuthServiceDependency,
    settings: SettingsDependency,
) -> User | None:
    return service.authenticate_optional(request.cookies.get(settings.auth_cookie_name))


OptionalCurrentUser = Annotated[User | None, Depends(optional_current_user)]


@router.post(
    "/api/auth/register",
    response_model=UserResponse,
    status_code=201,
    summary="Create an optional Kiba account",
)
def register(
    payload: RegisterRequest,
    response: Response,
    request: Request,
    _csrf: CsrfDependency,
    service: AuthServiceDependency,
    settings: SettingsDependency,
    email_sender: EmailSenderDependency,
) -> UserResponse:
    _check_rate_limit(request, "register")
    authenticated = service.register(str(payload.email), payload.display_name, payload.password)
    _set_auth_cookie(response, authenticated.token, settings)
    sent = _send_verification(service, email_sender, authenticated.user, settings)
    return _serialize_user(authenticated.user, verification_email_sent=sent)


@router.post("/api/auth/login", response_model=UserResponse, summary="Log in to Kiba")
def login(
    payload: LoginRequest,
    response: Response,
    request: Request,
    _csrf: CsrfDependency,
    service: AuthServiceDependency,
    settings: SettingsDependency,
) -> UserResponse:
    _check_rate_limit(request, "login")
    authenticated = service.login(str(payload.email), payload.password)
    _set_auth_cookie(response, authenticated.token, settings)
    return _serialize_user(authenticated.user)


@router.post("/api/auth/logout", status_code=204, summary="Log out of Kiba")
def logout(
    response: Response,
    request: Request,
    _csrf: CsrfDependency,
    service: AuthServiceDependency,
    settings: SettingsDependency,
) -> None:
    service.logout(request.cookies.get(settings.auth_cookie_name))
    response.delete_cookie(
        settings.auth_cookie_name,
        path="/",
        secure=settings.auth_cookie_secure,
        httponly=True,
        samesite="lax",
    )


@router.post("/api/auth/logout-all", status_code=204, summary="Log out on every device")
def logout_all(
    response: Response,
    _csrf: CsrfDependency,
    user: CurrentUser,
    service: AuthServiceDependency,
    settings: SettingsDependency,
) -> None:
    service.logout_all(user)
    _clear_auth_cookie(response, settings)


@router.post(
    "/api/auth/verification/send",
    response_model=MessageResponse,
    summary="Send or replace an email verification link",
)
def send_verification(
    request: Request,
    _csrf: CsrfDependency,
    user: CurrentUser,
    service: AuthServiceDependency,
    settings: SettingsDependency,
    email_sender: EmailSenderDependency,
) -> MessageResponse:
    _check_rate_limit(request, "verification", normalize_email(user.email), token_endpoint=True)
    sent = _send_verification(service, email_sender, user, settings)
    return MessageResponse(message="verification_sent" if sent else "already_verified")


@router.post(
    "/api/auth/verification/confirm",
    response_model=UserResponse,
    summary="Confirm ownership of an account email",
)
def confirm_verification(
    payload: TokenRequest,
    _csrf: CsrfDependency,
    service: AuthServiceDependency,
) -> UserResponse:
    return _serialize_user(service.confirm_email(payload.token))


@router.post(
    "/api/auth/password/forgot",
    response_model=MessageResponse,
    summary="Request password reset instructions",
)
def forgot_password(
    payload: ForgotPasswordRequest,
    request: Request,
    _csrf: CsrfDependency,
    service: AuthServiceDependency,
    settings: SettingsDependency,
    email_sender: EmailSenderDependency,
) -> MessageResponse:
    _check_rate_limit(request, "forgot", normalize_email(str(payload.email)), token_endpoint=True)
    delivery = service.issue_password_reset(str(payload.email))
    if delivery is not None:
        user, raw_token = delivery
        link = f"{settings.public_base_url}/reset-password?token={quote(raw_token)}"
        try:
            email_sender.send_password_reset(user.email, link)
        except EmailDeliveryError:
            logger.exception("password_reset_email_delivery_failed")
    return MessageResponse(message="password_reset_requested")


@router.post(
    "/api/auth/password/reset",
    response_model=MessageResponse,
    summary="Set a new password with a one-use reset token",
)
def reset_password(
    payload: ResetPasswordRequest,
    response: Response,
    request: Request,
    _csrf: CsrfDependency,
    service: AuthServiceDependency,
    settings: SettingsDependency,
) -> MessageResponse:
    _check_rate_limit(request, "reset", token_endpoint=True)
    service.reset_password(payload.token, payload.new_password)
    _clear_auth_cookie(response, settings)
    return MessageResponse(message="password_reset")


@router.get("/api/auth/me", response_model=UserResponse, summary="Get the current account")
def me(user: CurrentUser) -> UserResponse:
    return _serialize_user(user)


@router.patch("/api/profile", response_model=UserResponse, summary="Update the current profile")
def update_profile(
    payload: ProfileUpdateRequest,
    _csrf: CsrfDependency,
    user: CurrentUser,
    service: AuthServiceDependency,
) -> UserResponse:
    return _serialize_user(service.update_display_name(user, payload.display_name))


def _check_rate_limit(
    request: Request,
    action: str,
    subject: str = "",
    *,
    token_endpoint: bool = False,
) -> None:
    client = request.client.host if request.client is not None else "unknown"
    limiter = (
        request.app.state.account_token_rate_limiter
        if token_endpoint
        else request.app.state.auth_rate_limiter
    )
    limiter.check(f"{action}:{client}:{subject}")


def _set_auth_cookie(response: Response, token: str, settings: Settings) -> None:
    response.set_cookie(
        settings.auth_cookie_name,
        token,
        max_age=settings.auth_session_days * 24 * 60 * 60,
        path="/",
        secure=settings.auth_cookie_secure,
        httponly=True,
        samesite="lax",
    )


def _clear_auth_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        settings.auth_cookie_name,
        path="/",
        secure=settings.auth_cookie_secure,
        httponly=True,
        samesite="lax",
    )


def _serialize_user(
    user: User,
    *,
    verification_email_sent: bool | None = None,
) -> UserResponse:
    return UserResponse(
        id=str(user.id),
        email=user.email,
        display_name=user.display_name,
        created_at=user.created_at.isoformat(),
        email_verified=user.email_verified_at is not None,
        verification_email_sent=verification_email_sent,
    )


def _send_verification(
    service: AuthService,
    sender: EmailSender,
    user: User,
    settings: Settings,
) -> bool:
    raw_token = service.issue_email_verification(user)
    if raw_token is None:
        return False
    link = f"{settings.public_base_url}/verify-email?token={quote(raw_token)}"
    try:
        sender.send_verification(user.email, link)
    except EmailDeliveryError:
        logger.exception("verification_email_delivery_failed")
        return False
    return True


def _origin_from_url(value: str) -> str:
    parsed = urlsplit(value)
    return f"{parsed.scheme}://{parsed.netloc}"


def is_trusted_origin(candidate: str, request_origin: str, settings: Settings) -> bool:
    """Return whether an HTTP/WebSocket browser origin is trusted for this server."""
    normalized = candidate.rstrip("/")
    if normalized in {*settings.csrf_trusted_origins, request_origin}:
        return True
    if settings.auth_cookie_secure:
        return False
    parsed = urlsplit(normalized)
    if parsed.scheme != "http" or parsed.port not in {4200, 8000, 14200, 18000}:
        return False
    try:
        address = ip_address(parsed.hostname or "")
    except ValueError:
        return False
    return address.is_private or address.is_loopback
