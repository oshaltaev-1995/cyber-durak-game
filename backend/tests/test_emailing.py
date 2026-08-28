from __future__ import annotations

from email.message import EmailMessage

import pytest

from kiba_api.config import EmailMode, Settings
from kiba_api.emailing import EmailDeliveryError, SMTPEmailSender


class RecordingSMTP:
    instances: list[RecordingSMTP] = []

    def __init__(self, host: str, port: int, *, timeout: int) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self.started_tls = False
        self.credentials: tuple[str, str] | None = None
        self.message: EmailMessage | None = None
        self.instances.append(self)

    def __enter__(self) -> RecordingSMTP:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def starttls(self) -> None:
        self.started_tls = True

    def login(self, username: str, password: str) -> None:
        self.credentials = (username, password)

    def send_message(self, message: EmailMessage) -> None:
        self.message = message


def smtp_settings() -> Settings:
    return Settings(
        app_env="test",
        database_url="sqlite://",
        email_mode=EmailMode.SMTP,
        smtp_host="smtp.example.com",
        smtp_port=2525,
        smtp_username="kiba",
        smtp_password="secret",
        smtp_from="no-reply@example.com",
    )


def test_smtp_adapter_uses_configured_transport(monkeypatch: pytest.MonkeyPatch) -> None:
    RecordingSMTP.instances.clear()
    monkeypatch.setattr("kiba_api.emailing.smtplib.SMTP", RecordingSMTP)

    SMTPEmailSender(smtp_settings()).send_verification(
        "player@example.com", "https://kiba.example.com/verify-email?token=opaque"
    )

    client = RecordingSMTP.instances[-1]
    assert (client.host, client.port, client.timeout) == ("smtp.example.com", 2525, 10)
    assert client.started_tls is True
    assert client.credentials == ("kiba", "secret")
    assert client.message is not None
    assert client.message["To"] == "player@example.com"
    assert "token=opaque" in client.message.get_content()


def test_smtp_adapter_converts_transport_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    class FailingSMTP:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            raise OSError("offline")

    monkeypatch.setattr("kiba_api.emailing.smtplib.SMTP", FailingSMTP)

    with pytest.raises(EmailDeliveryError, match="email delivery failed"):
        SMTPEmailSender(smtp_settings()).send_password_reset(
            "player@example.com", "https://kiba.example.com/reset-password?token=opaque"
        )
