"""Account registration, password verification, and opaque sessions."""

from __future__ import annotations

import hashlib
import secrets
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from threading import RLock
from time import monotonic

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from kiba_api.persistence import AuthSession, User


class AuthErrorCode(StrEnum):
    """Stable API-facing account failure codes."""

    EMAIL_ALREADY_REGISTERED = "email_already_registered"
    INVALID_CREDENTIALS = "invalid_credentials"
    AUTHENTICATION_REQUIRED = "authentication_required"
    RATE_LIMITED = "rate_limited"
    INVALID_CSRF_ORIGIN = "invalid_csrf_origin"


class AuthError(ValueError):
    """Typed account error without user-sensitive detail."""

    def __init__(self, code: AuthErrorCode) -> None:
        self.code = code
        super().__init__(code.value)


@dataclass(frozen=True, slots=True)
class AuthenticatedSession:
    """A user plus the raw token that is returned only in an HTTP-only cookie."""

    user: User
    token: str


class AuthRateLimiter:
    """Small process-local sliding-window limiter for login and registration."""

    def __init__(self, attempts: int, window_seconds: int) -> None:
        if attempts <= 0 or window_seconds <= 0:
            raise ValueError("rate limit values must be positive")
        self._attempts = attempts
        self._window_seconds = window_seconds
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = RLock()

    def check(self, key: str) -> None:
        """Record one attempt or reject when its window is already full."""
        now = monotonic()
        cutoff = now - self._window_seconds
        with self._lock:
            events = self._events[key]
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= self._attempts:
                raise AuthError(AuthErrorCode.RATE_LIMITED)
            events.append(now)


class AuthService:
    """Persist users and revocable server-side sessions through SQLAlchemy."""

    def __init__(
        self,
        database_session: Session,
        *,
        session_days: int = 30,
        password_hasher: PasswordHasher | None = None,
    ) -> None:
        if session_days <= 0:
            raise ValueError("session_days must be positive")
        self._db = database_session
        self._session_lifetime = timedelta(days=session_days)
        self._password_hasher = password_hasher or PasswordHasher()

    def register(self, email: str, display_name: str, password: str) -> AuthenticatedSession:
        """Create a unique account and its first authenticated session."""
        normalized_email = normalize_email(email)
        if self._find_user(normalized_email) is not None:
            raise AuthError(AuthErrorCode.EMAIL_ALREADY_REGISTERED)

        user = User(
            email=email.strip(),
            normalized_email=normalized_email,
            display_name=display_name.strip(),
            password_hash=self._password_hasher.hash(password),
            is_active=True,
        )
        self._db.add(user)
        try:
            self._db.flush()
        except IntegrityError as error:
            self._db.rollback()
            raise AuthError(AuthErrorCode.EMAIL_ALREADY_REGISTERED) from error
        authenticated = self._new_session(user)
        self._db.commit()
        return authenticated

    def login(self, email: str, password: str) -> AuthenticatedSession:
        """Verify generic credentials and issue a new opaque session."""
        user = self._find_user(normalize_email(email))
        if user is None or not user.is_active or not self._password_matches(user, password):
            raise AuthError(AuthErrorCode.INVALID_CREDENTIALS)

        if self._password_hasher.check_needs_rehash(user.password_hash):
            user.password_hash = self._password_hasher.hash(password)
        user.last_login_at = utc_now()
        authenticated = self._new_session(user)
        self._db.commit()
        return authenticated

    def authenticate(self, token: str | None) -> User:
        """Resolve a valid, unexpired, unrevoked session token."""
        if not token:
            raise AuthError(AuthErrorCode.AUTHENTICATION_REQUIRED)
        now = utc_now()
        auth_session = self._db.scalar(
            select(AuthSession)
            .where(AuthSession.token_hash == hash_session_token(token))
            .where(AuthSession.revoked_at.is_(None))
        )
        if auth_session is None or _as_utc(auth_session.expires_at) <= now:
            raise AuthError(AuthErrorCode.AUTHENTICATION_REQUIRED)
        if not auth_session.user.is_active:
            raise AuthError(AuthErrorCode.AUTHENTICATION_REQUIRED)
        auth_session.last_seen_at = now
        self._db.commit()
        return auth_session.user

    def authenticate_optional(self, token: str | None) -> User | None:
        """Resolve a cookie when present while leaving true guests untouched."""
        if not token:
            return None
        try:
            return self.authenticate(token)
        except AuthError:
            return None

    def logout(self, token: str | None) -> None:
        """Revoke the current session when it exists."""
        if token:
            auth_session = self._db.scalar(
                select(AuthSession).where(AuthSession.token_hash == hash_session_token(token))
            )
            if auth_session is not None and auth_session.revoked_at is None:
                auth_session.revoked_at = utc_now()
                self._db.commit()

    def update_display_name(self, user: User, display_name: str) -> User:
        """Update the only Phase 4A mutable profile field."""
        user.display_name = display_name.strip()
        user.updated_at = utc_now()
        self._db.commit()
        return user

    def _find_user(self, normalized_email: str) -> User | None:
        return self._db.scalar(select(User).where(User.normalized_email == normalized_email))

    def _password_matches(self, user: User, password: str) -> bool:
        try:
            return self._password_hasher.verify(user.password_hash, password)
        except (InvalidHashError, VerificationError, VerifyMismatchError):
            return False

    def _new_session(self, user: User) -> AuthenticatedSession:
        token = secrets.token_urlsafe(32)
        now = utc_now()
        self._db.add(
            AuthSession(
                user=user,
                token_hash=hash_session_token(token),
                last_seen_at=now,
                expires_at=now + self._session_lifetime,
            )
        )
        return AuthenticatedSession(user=user, token=token)


def normalize_email(email: str) -> str:
    """Return the value used by the database case-insensitive uniqueness constraint."""
    return email.strip().casefold()


def hash_session_token(token: str) -> str:
    """Return a deterministic one-way digest; raw tokens are never persisted."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def utc_now() -> datetime:
    return datetime.now(UTC)


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
