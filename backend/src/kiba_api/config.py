"""Environment-driven backend configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_DATABASE_URL = "postgresql+psycopg://kiba:kiba@database:5432/kiba"
DEFAULT_COOKIE_NAME = "kiba_session"
DEFAULT_CSRF_ORIGINS = (
    "http://localhost:14200",
    "http://127.0.0.1:14200",
    "http://localhost:18000",
    "http://127.0.0.1:18000",
)


def _as_bool(value: str) -> bool:
    return value.strip().casefold() in {"1", "true", "yes", "on"}


@dataclass(frozen=True, slots=True)
class Settings:
    """Runtime settings with development-safe defaults and production overrides."""

    database_url: str = DEFAULT_DATABASE_URL
    auth_cookie_name: str = DEFAULT_COOKIE_NAME
    auth_cookie_secure: bool = False
    auth_session_days: int = 30
    auth_rate_limit_attempts: int = 10
    auth_rate_limit_window_seconds: int = 60
    pvp_action_rate_limit_attempts: int = 120
    pvp_action_rate_limit_window_seconds: int = 1
    pvp_max_websocket_message_bytes: int = 16_384
    csrf_trusted_origins: tuple[str, ...] = DEFAULT_CSRF_ORIGINS

    @classmethod
    def from_env(cls) -> Settings:
        """Build settings from Kiba-specific environment variables."""
        origins = os.getenv("KIBA_CSRF_TRUSTED_ORIGINS")
        return cls(
            database_url=os.getenv("KIBA_DATABASE_URL", DEFAULT_DATABASE_URL),
            auth_cookie_name=os.getenv("KIBA_AUTH_COOKIE_NAME", DEFAULT_COOKIE_NAME),
            auth_cookie_secure=_as_bool(os.getenv("KIBA_AUTH_COOKIE_SECURE", "false")),
            auth_session_days=int(os.getenv("KIBA_AUTH_SESSION_DAYS", "30")),
            auth_rate_limit_attempts=int(os.getenv("KIBA_AUTH_RATE_LIMIT_ATTEMPTS", "10")),
            auth_rate_limit_window_seconds=int(
                os.getenv(
                    "KIBA_AUTH_RATE_LIMIT_WINDOW_SECONDS",
                    "60",
                )
            ),
            pvp_action_rate_limit_attempts=int(
                os.getenv("KIBA_PVP_ACTION_RATE_LIMIT_ATTEMPTS", "120")
            ),
            pvp_action_rate_limit_window_seconds=int(
                os.getenv("KIBA_PVP_ACTION_RATE_LIMIT_WINDOW_SECONDS", "1")
            ),
            pvp_max_websocket_message_bytes=int(
                os.getenv("KIBA_PVP_MAX_WEBSOCKET_MESSAGE_BYTES", "16384")
            ),
            csrf_trusted_origins=(
                tuple(item.strip().rstrip("/") for item in origins.split(",") if item.strip())
                if origins is not None
                else DEFAULT_CSRF_ORIGINS
            ),
        )
