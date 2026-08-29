from __future__ import annotations

from datetime import timedelta
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update

from kiba_api.auth import hash_token, utc_now
from kiba_api.config import Settings
from kiba_api.emailing import DevelopmentEmailSender, EmailDeliveryError
from kiba_api.main import create_app
from kiba_api.persistence import AccountToken, AuthSession, Base, Database, User

ORIGIN = "http://testserver"
PASSWORD = "correct horse battery staple"


@pytest.fixture
def database() -> Database:
    value = Database("sqlite://")
    Base.metadata.create_all(value.engine)
    yield value
    value.dispose()


@pytest.fixture
def sender() -> DevelopmentEmailSender:
    return DevelopmentEmailSender()


@pytest.fixture
def client(database: Database, sender: DevelopmentEmailSender) -> TestClient:
    settings = Settings(
        app_env="test",
        database_url="sqlite://",
        public_base_url="http://testserver",
        csrf_trusted_origins=(ORIGIN,),
    )
    return TestClient(create_app(database=database, settings=settings, email_sender=sender))


def register(client: TestClient, email: str = "player@example.com"):
    return client.post(
        "/api/auth/register",
        headers={"Origin": ORIGIN},
        json={"email": email, "display_name": "Игрок", "password": PASSWORD},
    )


def delivered_token(sender: DevelopmentEmailSender, kind: str) -> str:
    message = next(value for value in reversed(sender.messages) if value.kind == kind)
    return parse_qs(urlsplit(message.link).query)["token"][0]


def verify(client: TestClient, sender: DevelopmentEmailSender) -> str:
    token = delivered_token(sender, "EMAIL_VERIFICATION")
    response = client.post(
        "/api/auth/verification/confirm",
        headers={"Origin": ORIGIN},
        json={"token": token},
    )
    assert response.status_code == 200
    return token


def test_registration_is_unverified_and_stores_only_verification_token_hash(
    client: TestClient,
    database: Database,
    sender: DevelopmentEmailSender,
) -> None:
    response = register(client)
    raw_token = delivered_token(sender, "EMAIL_VERIFICATION")

    assert response.status_code == 201
    assert response.json()["email_verified"] is False
    assert response.json()["verification_email_sent"] is True
    with database.session() as session:
        user = session.scalar(select(User))
        token = session.scalar(select(AccountToken))
        assert user is not None and user.email_verified_at is None
        assert token is not None
        assert token.token_hash == hash_token(raw_token)
        assert raw_token not in token.token_hash


def test_account_locale_is_persisted_and_controls_account_email_copy(
    client: TestClient,
    database: Database,
    sender: DevelopmentEmailSender,
) -> None:
    response = client.post(
        "/api/auth/register",
        headers={"Origin": ORIGIN},
        json={
            "email": "english@example.com",
            "display_name": "English player",
            "password": PASSWORD,
            "preferred_locale": "en",
        },
    )

    assert response.status_code == 201
    assert response.json()["preferred_locale"] == "en"
    message = sender.messages[-1]
    assert message.locale.value == "en"
    assert message.subject == "Verify your email — KIBA"
    assert "Verify your email address" in message.body
    with database.session() as session:
        user = session.scalar(select(User).where(User.email == "english@example.com"))
        assert user is not None and user.preferred_locale == "en"

    updated = client.patch(
        "/api/profile",
        headers={"Origin": ORIGIN},
        json={"preferred_locale": "ru"},
    )
    assert updated.status_code == 200
    assert updated.json()["preferred_locale"] == "ru"

    resent = client.post("/api/auth/verification/send", headers={"Origin": ORIGIN})
    assert resent.status_code == 200
    assert sender.messages[-1].locale.value == "ru"
    assert sender.messages[-1].subject == "Подтвердите email — KIBA"


def test_account_locale_rejects_unsupported_values(client: TestClient) -> None:
    response = client.post(
        "/api/auth/register",
        headers={"Origin": ORIGIN},
        json={
            "email": "unsupported@example.com",
            "display_name": "Player",
            "password": PASSWORD,
            "preferred_locale": "de",
        },
    )
    assert response.status_code == 422


def test_password_reset_uses_the_stored_account_locale(
    client: TestClient,
    sender: DevelopmentEmailSender,
) -> None:
    response = client.post(
        "/api/auth/register",
        headers={"Origin": ORIGIN},
        json={
            "email": "english-reset@example.com",
            "display_name": "English player",
            "password": PASSWORD,
            "preferred_locale": "en",
        },
    )
    assert response.status_code == 201
    verify(client, sender)

    requested = client.post(
        "/api/auth/password/forgot",
        headers={"Origin": ORIGIN, "Accept-Language": "ru"},
        json={"email": "english-reset@example.com"},
    )

    assert requested.status_code == 200
    message = sender.messages[-1]
    assert message.kind == "PASSWORD_RESET"
    assert message.locale.value == "en"
    assert message.subject == "Reset your password — KIBA"


def test_verification_is_one_use_and_resend_revokes_previous_token(
    client: TestClient,
    database: Database,
    sender: DevelopmentEmailSender,
) -> None:
    assert register(client).status_code == 201
    first = delivered_token(sender, "EMAIL_VERIFICATION")
    assert client.post("/api/auth/verification/send", headers={"Origin": ORIGIN}).status_code == 200
    second = delivered_token(sender, "EMAIL_VERIFICATION")

    rejected = client.post(
        "/api/auth/verification/confirm",
        headers={"Origin": ORIGIN},
        json={"token": first},
    )
    accepted = client.post(
        "/api/auth/verification/confirm",
        headers={"Origin": ORIGIN},
        json={"token": second},
    )
    repeated = client.post(
        "/api/auth/verification/confirm",
        headers={"Origin": ORIGIN},
        json={"token": second},
    )

    assert rejected.status_code == 400
    assert accepted.status_code == repeated.status_code == 200
    assert accepted.json()["email_verified"] is True
    with database.session() as session:
        tokens = session.scalars(select(AccountToken).order_by(AccountToken.created_at)).all()
        assert len(tokens) == 2
        assert all(value.consumed_at is not None for value in tokens)


def test_expired_verification_token_is_rejected(
    client: TestClient,
    database: Database,
    sender: DevelopmentEmailSender,
) -> None:
    assert register(client).status_code == 201
    token = delivered_token(sender, "EMAIL_VERIFICATION")
    with database.session() as session:
        session.execute(update(AccountToken).values(expires_at=utc_now() - timedelta(seconds=1)))
        session.commit()

    response = client.post(
        "/api/auth/verification/confirm",
        headers={"Origin": ORIGIN},
        json={"token": token},
    )
    assert response.status_code == 400


def test_forgot_is_generic_and_reset_revokes_all_sessions(
    client: TestClient,
    database: Database,
    sender: DevelopmentEmailSender,
) -> None:
    assert register(client).status_code == 201
    first_cookie = client.cookies.get("kiba_session")
    verify(client, sender)
    client.cookies.clear()
    assert (
        client.post(
            "/api/auth/login",
            headers={"Origin": ORIGIN},
            json={"email": "player@example.com", "password": PASSWORD},
        ).status_code
        == 200
    )
    second_cookie = client.cookies.get("kiba_session")

    known = client.post(
        "/api/auth/password/forgot",
        headers={"Origin": ORIGIN},
        json={"email": "player@example.com"},
    )
    unknown = client.post(
        "/api/auth/password/forgot",
        headers={"Origin": ORIGIN},
        json={"email": "unknown@example.com"},
    )
    assert known.status_code == unknown.status_code == 200
    assert known.json() == unknown.json() == {"message": "password_reset_requested"}

    token = delivered_token(sender, "PASSWORD_RESET")
    reset = client.post(
        "/api/auth/password/reset",
        headers={"Origin": ORIGIN},
        json={"token": token, "new_password": "new secure password"},
    )
    repeated = client.post(
        "/api/auth/password/reset",
        headers={"Origin": ORIGIN},
        json={"token": token, "new_password": "another secure password"},
    )
    assert reset.status_code == 200
    assert repeated.status_code == 400
    with database.session() as session:
        assert all(value.revoked_at is not None for value in session.scalars(select(AuthSession)))

    for cookie in (first_cookie, second_cookie):
        client.cookies.set("kiba_session", cookie)
        assert client.get("/api/auth/me").status_code == 401
    client.cookies.clear()
    assert (
        client.post(
            "/api/auth/login",
            headers={"Origin": ORIGIN},
            json={"email": "player@example.com", "password": PASSWORD},
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/auth/login",
            headers={"Origin": ORIGIN},
            json={"email": "player@example.com", "password": "new secure password"},
        ).status_code
        == 200
    )


def test_unverified_account_gets_generic_forgot_response_without_reset_delivery(
    client: TestClient,
    sender: DevelopmentEmailSender,
) -> None:
    assert register(client).status_code == 201
    before = len(sender.messages)
    response = client.post(
        "/api/auth/password/forgot",
        headers={"Origin": ORIGIN},
        json={"email": "player@example.com"},
    )
    assert response.status_code == 200
    assert len(sender.messages) == before


def test_expired_password_reset_is_rejected_and_raw_value_is_not_stored(
    client: TestClient,
    database: Database,
    sender: DevelopmentEmailSender,
) -> None:
    assert register(client).status_code == 201
    verify(client, sender)
    assert (
        client.post(
            "/api/auth/password/forgot",
            headers={"Origin": ORIGIN},
            json={"email": "player@example.com"},
        ).status_code
        == 200
    )
    raw_token = delivered_token(sender, "PASSWORD_RESET")
    with database.session() as session:
        token = session.scalar(
            select(AccountToken).where(AccountToken.token_type == "PASSWORD_RESET")
        )
        assert token is not None
        assert token.token_hash == hash_token(raw_token)
        assert raw_token not in token.token_hash
        token.expires_at = utc_now() - timedelta(seconds=1)
        session.commit()

    response = client.post(
        "/api/auth/password/reset",
        headers={"Origin": ORIGIN},
        json={"token": raw_token, "new_password": "new secure password"},
    )
    assert response.status_code == 400


def test_verification_resend_is_rate_limited(database: Database) -> None:
    sender = DevelopmentEmailSender()
    settings = Settings(
        app_env="test",
        database_url="sqlite://",
        public_base_url="http://testserver",
        csrf_trusted_origins=(ORIGIN,),
        account_token_rate_limit_attempts=1,
    )
    client = TestClient(create_app(database=database, settings=settings, email_sender=sender))
    assert register(client, "limited@example.com").status_code == 201

    first = client.post("/api/auth/verification/send", headers={"Origin": ORIGIN})
    second = client.post("/api/auth/verification/send", headers={"Origin": ORIGIN})

    assert first.status_code == 200
    assert second.status_code == 429


def test_logout_all_revokes_all_sessions(client: TestClient, database: Database) -> None:
    assert register(client).status_code == 201
    assert (
        client.post(
            "/api/auth/login",
            headers={"Origin": ORIGIN},
            json={"email": "player@example.com", "password": PASSWORD},
        ).status_code
        == 200
    )
    assert client.post("/api/auth/logout-all", headers={"Origin": ORIGIN}).status_code == 204
    with database.session() as session:
        assert all(value.revoked_at is not None for value in session.scalars(select(AuthSession)))


def test_idle_session_expires_without_waiting_for_cleanup(
    client: TestClient, database: Database
) -> None:
    assert register(client).status_code == 201
    with database.session() as session:
        session.execute(update(AuthSession).values(last_seen_at=utc_now() - timedelta(days=15)))
        session.commit()

    assert client.get("/api/auth/me").status_code == 401


class FailingEmailSender:
    def send_verification(self, _recipient: str, _link: str, _locale: object = None) -> None:
        raise EmailDeliveryError("unavailable")

    def send_password_reset(self, _recipient: str, _link: str, _locale: object = None) -> None:
        raise EmailDeliveryError("unavailable")


def test_registration_survives_email_delivery_failure(database: Database) -> None:
    settings = Settings(
        app_env="test",
        database_url="sqlite://",
        public_base_url="http://testserver",
        csrf_trusted_origins=(ORIGIN,),
    )
    client = TestClient(
        create_app(database=database, settings=settings, email_sender=FailingEmailSender())
    )
    response = register(client, "delivery@example.com")
    assert response.status_code == 201
    assert response.json()["verification_email_sent"] is False
    assert client.get("/api/auth/me").status_code == 200
