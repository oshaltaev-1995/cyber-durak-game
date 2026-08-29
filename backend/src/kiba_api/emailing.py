"""Provider-neutral account email delivery."""

from __future__ import annotations

import logging
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from threading import RLock
from typing import Protocol

from kiba_api.config import EmailMode, Settings
from kiba_api.locale import Locale

logger = logging.getLogger(__name__)


class EmailDeliveryError(RuntimeError):
    """A recoverable email transport failure."""


@dataclass(frozen=True, slots=True)
class DeliveredEmail:
    """Development/test delivery record, never used as production persistence."""

    kind: str
    recipient: str
    link: str
    locale: Locale
    subject: str
    body: str


class EmailSender(Protocol):
    def send_verification(self, recipient: str, link: str, locale: Locale = Locale.RU) -> None: ...

    def send_password_reset(
        self, recipient: str, link: str, locale: Locale = Locale.RU
    ) -> None: ...


class DevelopmentEmailSender:
    """Process-local delivery seam with explicitly development-only link logging."""

    def __init__(self) -> None:
        self._messages: list[DeliveredEmail] = []
        self._lock = RLock()

    @property
    def messages(self) -> tuple[DeliveredEmail, ...]:
        with self._lock:
            return tuple(self._messages)

    def send_verification(self, recipient: str, link: str, locale: Locale = Locale.RU) -> None:
        subject, body = verification_email(locale, link)
        self._deliver("EMAIL_VERIFICATION", recipient, link, locale, subject, body)

    def send_password_reset(self, recipient: str, link: str, locale: Locale = Locale.RU) -> None:
        subject, body = password_reset_email(locale, link)
        self._deliver("PASSWORD_RESET", recipient, link, locale, subject, body)

    def _deliver(
        self,
        kind: str,
        recipient: str,
        link: str,
        locale: Locale,
        subject: str,
        body: str,
    ) -> None:
        with self._lock:
            self._messages.append(DeliveredEmail(kind, recipient, link, locale, subject, body))
        logger.warning(
            "development_email kind=%s recipient=%s locale=%s link=%s",
            kind,
            recipient,
            locale.value,
            link,
        )


class SMTPEmailSender:
    """Generic SMTP adapter configured without vendor-specific dependencies."""

    def __init__(self, settings: Settings) -> None:
        self._host = settings.smtp_host or ""
        self._port = settings.smtp_port
        self._username = settings.smtp_username or ""
        self._password = settings.smtp_password or ""
        self._from = settings.smtp_from or ""
        self._starttls = settings.smtp_starttls
        self._timeout = settings.smtp_timeout_seconds

    def send_verification(self, recipient: str, link: str, locale: Locale = Locale.RU) -> None:
        subject, body = verification_email(locale, link)
        self._send(recipient, subject, body)

    def send_password_reset(self, recipient: str, link: str, locale: Locale = Locale.RU) -> None:
        subject, body = password_reset_email(locale, link)
        self._send(recipient, subject, body)

    def _send(self, recipient: str, subject: str, body: str) -> None:
        message = EmailMessage()
        message["From"] = self._from
        message["To"] = recipient
        message["Subject"] = subject
        message.set_content(body)
        try:
            with smtplib.SMTP(self._host, self._port, timeout=self._timeout) as client:
                if self._starttls:
                    client.starttls()
                client.login(self._username, self._password)
                client.send_message(message)
        except (OSError, smtplib.SMTPException) as error:
            raise EmailDeliveryError("email delivery failed") from error


def create_email_sender(settings: Settings) -> EmailSender:
    if settings.email_mode is EmailMode.SMTP:
        return SMTPEmailSender(settings)
    return DevelopmentEmailSender()


def verification_email(locale: Locale, link: str) -> tuple[str, str]:
    """Return localized, provider-neutral verification copy."""
    if locale is Locale.EN:
        return (
            "Verify your email — KIBA",
            "Verify your email address to secure your KIBA account:\n\n"
            f"{link}\n\nThis link expires in 24 hours.",
        )
    return (
        "Подтвердите email — KIBA",
        "Подтвердите адрес электронной почты для аккаунта KIBA:\n\n"
        f"{link}\n\nСсылка действует 24 часа.",
    )


def password_reset_email(locale: Locale, link: str) -> tuple[str, str]:
    """Return localized, provider-neutral password-reset copy."""
    if locale is Locale.EN:
        return (
            "Reset your password — KIBA",
            "Open this link to set a new KIBA password:\n\n"
            f"{link}\n\nThis link expires in 30 minutes.",
        )
    return (
        "Сброс пароля — KIBA",
        "Чтобы установить новый пароль KIBA, откройте ссылку:\n\n"
        f"{link}\n\nСсылка действует 30 минут.",
    )
