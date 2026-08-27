from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from kiba_api.auth import hash_session_token
from kiba_api.config import Settings
from kiba_api.main import create_app
from kiba_api.persistence import AuthSession, Base, Database, User

ORIGIN = "http://testserver"
PASSWORD = "correct horse battery staple"


@pytest.fixture
def database() -> Database:
    value = Database("sqlite://")
    Base.metadata.create_all(value.engine)
    yield value
    value.dispose()


@pytest.fixture
def client(database: Database) -> TestClient:
    settings = Settings(database_url="sqlite://", csrf_trusted_origins=(ORIGIN,))
    return TestClient(create_app(database=database, settings=settings))


def register(
    client: TestClient,
    *,
    email: str = "Player@Example.com",
    display_name: str = "Игрок",
    password: str = PASSWORD,
):
    return client.post(
        "/api/auth/register",
        headers={"Origin": ORIGIN},
        json={"email": email, "display_name": display_name, "password": password},
    )


def test_registration_normalizes_email_hashes_password_and_creates_cookie_session(
    client: TestClient,
    database: Database,
) -> None:
    response = register(client)

    assert response.status_code == 201
    assert response.json()["email"] == "Player@example.com"
    assert response.json()["display_name"] == "Игрок"
    assert "password" not in response.text
    cookie = client.cookies.get("kiba_session")
    assert cookie is not None
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "SameSite=lax" in response.headers["set-cookie"]

    with database.session() as session:
        user = session.scalar(select(User))
        auth_session = session.scalar(select(AuthSession))
        assert user is not None
        assert auth_session is not None
        assert user.normalized_email == "player@example.com"
        assert user.password_hash != PASSWORD
        assert user.password_hash.startswith("$argon2id$")
        assert auth_session.token_hash == hash_session_token(cookie)
        assert auth_session.token_hash != cookie
        assert len(auth_session.token_hash) == 64


def test_duplicate_email_is_case_insensitive(client: TestClient) -> None:
    assert register(client).status_code == 201

    duplicate = register(client, email="  PLAYER@example.COM ")

    assert duplicate.status_code == 409
    assert duplicate.json() == {"detail": {"code": "email_already_registered"}}


def test_login_uses_generic_errors_updates_last_login_and_rotates_session(
    client: TestClient,
    database: Database,
) -> None:
    assert register(client).status_code == 201
    first_cookie = client.cookies.get("kiba_session")
    client.cookies.clear()

    invalid = client.post(
        "/api/auth/login",
        headers={"Origin": ORIGIN},
        json={"email": "player@example.com", "password": "wrong password"},
    )
    unknown = client.post(
        "/api/auth/login",
        headers={"Origin": ORIGIN},
        json={"email": "unknown@example.com", "password": "wrong password"},
    )
    valid = client.post(
        "/api/auth/login",
        headers={"Origin": ORIGIN},
        json={"email": "PLAYER@example.com", "password": PASSWORD},
    )

    assert invalid.status_code == unknown.status_code == 401
    assert invalid.json() == unknown.json() == {"detail": {"code": "invalid_credentials"}}
    assert valid.status_code == 200
    assert client.cookies.get("kiba_session") != first_cookie
    with database.session() as session:
        user = session.scalar(select(User))
        assert user is not None
        assert user.last_login_at is not None
        assert len(session.scalars(select(AuthSession)).all()) == 2


def test_me_logout_and_revoked_session(client: TestClient) -> None:
    assert client.get("/api/auth/me").status_code == 401
    assert register(client).status_code == 201
    cookie = client.cookies.get("kiba_session")

    me = client.get("/api/auth/me")
    logout = client.post("/api/auth/logout", headers={"Origin": ORIGIN})

    assert me.status_code == 200
    assert me.json()["display_name"] == "Игрок"
    assert logout.status_code == 204
    assert client.get("/api/auth/me").status_code == 401
    client.cookies.set("kiba_session", cookie)
    assert client.get("/api/auth/me").status_code == 401


def test_secure_cookie_is_configurable_for_https(database: Database) -> None:
    settings = Settings(
        database_url="sqlite://",
        auth_cookie_secure=True,
        csrf_trusted_origins=(ORIGIN,),
    )
    client = TestClient(create_app(database=database, settings=settings))

    response = register(client, email="secure@example.com")

    assert response.status_code == 201
    assert "Secure" in response.headers["set-cookie"]


def test_logout_is_safe_for_guest(client: TestClient) -> None:
    assert client.post("/api/auth/logout", headers={"Origin": ORIGIN}).status_code == 204


def test_profile_display_name_update_requires_authentication(client: TestClient) -> None:
    guest = client.patch(
        "/api/profile",
        headers={"Origin": ORIGIN},
        json={"display_name": "Новое имя"},
    )
    assert guest.status_code == 401
    assert register(client).status_code == 201

    updated = client.patch(
        "/api/profile",
        headers={"Origin": ORIGIN},
        json={"display_name": "  Новое имя  "},
    )

    assert updated.status_code == 200
    assert updated.json()["display_name"] == "Новое имя"
    assert client.get("/api/auth/me").json()["display_name"] == "Новое имя"


def test_password_policy_and_blank_display_name_are_validated(client: TestClient) -> None:
    assert register(client, password="short").status_code == 422
    assert register(client, email="second@example.com", display_name="   ").status_code == 422


def test_cross_site_origin_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/api/auth/login",
        headers={"Origin": "https://evil.example"},
        json={"email": "player@example.com", "password": PASSWORD},
    )
    assert response.status_code == 403
    assert response.json() == {"detail": {"code": "invalid_csrf_origin"}}


def test_local_http_lan_frontend_origin_is_allowed(client: TestClient) -> None:
    response = client.post(
        "/api/auth/login",
        headers={"Origin": "http://192.168.1.50:14200"},
        json={"email": "unknown@example.com", "password": PASSWORD},
    )
    assert response.status_code == 401
    assert response.json() == {"detail": {"code": "invalid_credentials"}}


def test_login_rate_limit_is_process_local_and_bounded(database: Database) -> None:
    settings = Settings(
        database_url="sqlite://",
        csrf_trusted_origins=(ORIGIN,),
        auth_rate_limit_attempts=2,
        auth_rate_limit_window_seconds=60,
    )
    client = TestClient(create_app(database=database, settings=settings))

    for _ in range(2):
        response = client.post(
            "/api/auth/login",
            headers={"Origin": ORIGIN},
            json={"email": "none@example.com", "password": "incorrect"},
        )
        assert response.status_code == 401
    limited = client.post(
        "/api/auth/login",
        headers={"Origin": ORIGIN},
        json={"email": "none@example.com", "password": "incorrect"},
    )

    assert limited.status_code == 429
    assert limited.json() == {"detail": {"code": "rate_limited"}}


def test_authenticated_and_guest_games_record_only_optional_user_id(
    client: TestClient,
    database: Database,
) -> None:
    guest_game = client.post("/api/games")
    assert guest_game.status_code == 201
    game_service = client.app.state.game_service
    assert game_service.get_game(guest_game.json()["game_id"]).user_id is None

    assert register(client).status_code == 201
    authenticated_game = client.post("/api/games")
    with database.session() as session:
        user = session.scalar(select(User))
        assert user is not None
        assert game_service.get_game(authenticated_game.json()["game_id"]).user_id == user.id
