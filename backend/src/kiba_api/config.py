"""Environment-driven backend configuration and production validation."""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import StrEnum
from urllib.parse import urlsplit

DEFAULT_DATABASE_URL = "postgresql+psycopg://kiba:kiba@database:5432/kiba"
DEFAULT_COOKIE_NAME = "kiba_session"
DEFAULT_CSRF_ORIGINS = (
    "http://localhost:14200",
    "http://127.0.0.1:14200",
    "http://localhost:18000",
    "http://127.0.0.1:18000",
)
DEFAULT_TRUSTED_HOSTS = ("localhost", "127.0.0.1", "testserver")


class AppEnvironment(StrEnum):
    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"


class EmailMode(StrEnum):
    DEVELOPMENT = "development"
    SMTP = "smtp"


def _as_bool(value: str) -> bool:
    return value.strip().casefold() in {"1", "true", "yes", "on"}


def _items(value: str | None, default: tuple[str, ...]) -> tuple[str, ...]:
    if value is None:
        return default
    return tuple(item.strip().rstrip("/") for item in value.split(",") if item.strip())


@dataclass(frozen=True, slots=True)
class Settings:
    """Runtime settings with friendly development defaults and strict production checks."""

    app_env: AppEnvironment = AppEnvironment.DEVELOPMENT
    database_url: str = DEFAULT_DATABASE_URL
    public_base_url: str = "http://localhost:14200"
    trusted_hosts: tuple[str, ...] = DEFAULT_TRUSTED_HOSTS
    csrf_trusted_origins: tuple[str, ...] = DEFAULT_CSRF_ORIGINS
    auth_cookie_name: str = DEFAULT_COOKIE_NAME
    auth_cookie_secure: bool = False
    auth_session_days: int = 30
    auth_session_idle_days: int = 14
    auth_session_touch_minutes: int = 15
    auth_rate_limit_attempts: int = 10
    auth_rate_limit_window_seconds: int = 60
    account_token_rate_limit_attempts: int = 5
    account_token_rate_limit_window_seconds: int = 300
    verification_token_hours: int = 24
    password_reset_token_minutes: int = 30
    email_mode: EmailMode = EmailMode.DEVELOPMENT
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from: str | None = None
    smtp_starttls: bool = True
    smtp_timeout_seconds: int = 10
    bot_session_active_ttl_seconds: int = 6 * 60 * 60
    bot_session_complete_ttl_seconds: int = 30 * 60
    pvp_waiting_ttl_seconds: int = 30 * 60
    pvp_complete_ttl_seconds: int = 15 * 60
    pvp_disconnected_ttl_seconds: int = 2 * 60 * 60
    pvp_action_rate_limit_attempts: int = 120
    pvp_action_rate_limit_window_seconds: int = 1
    pvp_max_websocket_message_bytes: int = 16_384
    multiplayer_3_4_enabled: bool = False
    mixed_rooms_enabled: bool = False
    deck_variants_enabled: bool = False
    log_json: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.app_env, AppEnvironment):
            object.__setattr__(self, "app_env", AppEnvironment(self.app_env))
        if not isinstance(self.email_mode, EmailMode):
            object.__setattr__(self, "email_mode", EmailMode(self.email_mode))
        positive = (
            "auth_session_days",
            "auth_session_idle_days",
            "auth_session_touch_minutes",
            "auth_rate_limit_attempts",
            "auth_rate_limit_window_seconds",
            "account_token_rate_limit_attempts",
            "account_token_rate_limit_window_seconds",
            "verification_token_hours",
            "password_reset_token_minutes",
            "smtp_port",
            "smtp_timeout_seconds",
            "bot_session_active_ttl_seconds",
            "bot_session_complete_ttl_seconds",
            "pvp_waiting_ttl_seconds",
            "pvp_complete_ttl_seconds",
            "pvp_disconnected_ttl_seconds",
            "pvp_action_rate_limit_attempts",
            "pvp_action_rate_limit_window_seconds",
            "pvp_max_websocket_message_bytes",
        )
        if any(getattr(self, name) <= 0 for name in positive):
            raise ValueError("duration and limit settings must be positive")
        if self.app_env is AppEnvironment.PRODUCTION:
            self.validate_production()

    @property
    def is_production(self) -> bool:
        return self.app_env is AppEnvironment.PRODUCTION

    def validate_production(self) -> None:
        """Fail before startup when a production configuration is unsafe."""
        errors: list[str] = []
        public = urlsplit(self.public_base_url)
        database = urlsplit(self.database_url.replace("postgresql+psycopg", "postgresql", 1))
        if not self.database_url or self.database_url == DEFAULT_DATABASE_URL:
            errors.append("KIBA_DATABASE_URL must not use the development default")
        if database.password in {None, "", "kiba", "kiba-local-only", "change-me"}:
            errors.append("database password must be non-default")
        if not self.auth_cookie_secure:
            errors.append("KIBA_AUTH_COOKIE_SECURE must be true")
        if public.scheme != "https" or public.hostname in {None, "localhost", "127.0.0.1"}:
            errors.append("KIBA_PUBLIC_BASE_URL must be a non-local HTTPS URL")
        if not self.trusted_hosts or "*" in self.trusted_hosts:
            errors.append("KIBA_TRUSTED_HOSTS must contain exact hosts")
        if not self.csrf_trusted_origins or "*" in self.csrf_trusted_origins:
            errors.append("KIBA_CSRF_TRUSTED_ORIGINS must contain exact origins")
        if self.email_mode is not EmailMode.SMTP:
            errors.append("KIBA_EMAIL_MODE must be smtp")
        if not all((self.smtp_host, self.smtp_username, self.smtp_password, self.smtp_from)):
            errors.append("SMTP host, username, password, and from address are required")
        if errors:
            raise ValueError("unsafe production configuration: " + "; ".join(errors))

    @classmethod
    def from_env(cls) -> Settings:
        """Build settings from Kiba-specific environment variables."""
        return cls(
            app_env=AppEnvironment(os.getenv("APP_ENV", "development").strip().casefold()),
            database_url=os.getenv("KIBA_DATABASE_URL", DEFAULT_DATABASE_URL),
            public_base_url=os.getenv("KIBA_PUBLIC_BASE_URL", "http://localhost:14200").rstrip("/"),
            trusted_hosts=_items(os.getenv("KIBA_TRUSTED_HOSTS"), DEFAULT_TRUSTED_HOSTS),
            csrf_trusted_origins=_items(
                os.getenv("KIBA_CSRF_TRUSTED_ORIGINS"), DEFAULT_CSRF_ORIGINS
            ),
            auth_cookie_name=os.getenv("KIBA_AUTH_COOKIE_NAME", DEFAULT_COOKIE_NAME),
            auth_cookie_secure=_as_bool(os.getenv("KIBA_AUTH_COOKIE_SECURE", "false")),
            auth_session_days=int(os.getenv("KIBA_AUTH_SESSION_DAYS", "30")),
            auth_session_idle_days=int(os.getenv("KIBA_AUTH_SESSION_IDLE_DAYS", "14")),
            auth_session_touch_minutes=int(os.getenv("KIBA_AUTH_SESSION_TOUCH_MINUTES", "15")),
            auth_rate_limit_attempts=int(os.getenv("KIBA_AUTH_RATE_LIMIT_ATTEMPTS", "10")),
            auth_rate_limit_window_seconds=int(
                os.getenv(
                    "KIBA_AUTH_RATE_LIMIT_WINDOW_SECONDS",
                    "60",
                )
            ),
            account_token_rate_limit_attempts=int(
                os.getenv("KIBA_ACCOUNT_TOKEN_RATE_LIMIT_ATTEMPTS", "5")
            ),
            account_token_rate_limit_window_seconds=int(
                os.getenv("KIBA_ACCOUNT_TOKEN_RATE_LIMIT_WINDOW_SECONDS", "300")
            ),
            verification_token_hours=int(os.getenv("KIBA_VERIFICATION_TOKEN_HOURS", "24")),
            password_reset_token_minutes=int(os.getenv("KIBA_PASSWORD_RESET_TOKEN_MINUTES", "30")),
            email_mode=EmailMode(os.getenv("KIBA_EMAIL_MODE", "development").strip().casefold()),
            smtp_host=os.getenv("KIBA_SMTP_HOST"),
            smtp_port=int(os.getenv("KIBA_SMTP_PORT", "587")),
            smtp_username=os.getenv("KIBA_SMTP_USERNAME"),
            smtp_password=os.getenv("KIBA_SMTP_PASSWORD"),
            smtp_from=os.getenv("KIBA_SMTP_FROM"),
            smtp_starttls=_as_bool(os.getenv("KIBA_SMTP_STARTTLS", "true")),
            smtp_timeout_seconds=int(os.getenv("KIBA_SMTP_TIMEOUT_SECONDS", "10")),
            bot_session_active_ttl_seconds=int(
                os.getenv("KIBA_BOT_SESSION_ACTIVE_TTL_SECONDS", str(6 * 60 * 60))
            ),
            bot_session_complete_ttl_seconds=int(
                os.getenv("KIBA_BOT_SESSION_COMPLETE_TTL_SECONDS", str(30 * 60))
            ),
            pvp_waiting_ttl_seconds=int(os.getenv("KIBA_PVP_WAITING_TTL_SECONDS", "1800")),
            pvp_complete_ttl_seconds=int(os.getenv("KIBA_PVP_COMPLETE_TTL_SECONDS", "900")),
            pvp_disconnected_ttl_seconds=int(
                os.getenv("KIBA_PVP_DISCONNECTED_TTL_SECONDS", "7200")
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
            multiplayer_3_4_enabled=_as_bool(os.getenv("KIBA_MULTIPLAYER_3_4_ENABLED", "false")),
            mixed_rooms_enabled=_as_bool(os.getenv("KIBA_MIXED_ROOMS_ENABLED", "false")),
            deck_variants_enabled=_as_bool(os.getenv("KIBA_DECK_VARIANTS_ENABLED", "false")),
            log_json=_as_bool(os.getenv("KIBA_LOG_JSON", "false")),
        )
