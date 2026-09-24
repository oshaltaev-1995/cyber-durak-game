from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from kiba_api.config import Settings
from kiba_api.main import create_app
from kiba_api.persistence import (
    AccountDataService,
    AccountToken,
    AuthSession,
    Base,
    CompletedMatch,
    Database,
    User,
    UserAchievement,
    UserCosmeticLoadout,
    UserCosmeticUnlock,
    XPLedgerEntry,
)

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
    settings = Settings(app_env="test", database_url="sqlite://", csrf_trusted_origins=(ORIGIN,))
    return TestClient(create_app(database=database, settings=settings))


def register(client: TestClient, email: str = "alice@example.com"):
    return client.post(
        "/api/auth/register",
        headers={"Origin": ORIGIN},
        json={"email": email, "display_name": "Alice", "password": PASSWORD},
    )


def completed_match(user_id, *, session_id: str, opponent_user_id=None, opponent_name=None):
    now = datetime.now(UTC)
    return CompletedMatch(
        user_id=user_id,
        game_session_id=session_id,
        pvp_match_id="shared-pvp" if opponent_name else None,
        opponent_type="PVP" if opponent_name else "BOT",
        opponent_user_id=opponent_user_id,
        opponent_display_name=opponent_name,
        outcome="WIN",
        started_at=now - timedelta(minutes=4),
        completed_at=now,
        duration_seconds=240,
        user_seat="one",
        initial_attacker="one",
        final_human_card_count=0,
        final_bot_card_count=3,
        human_action_count=8,
        human_transfer_count=1,
        human_take_count=0,
        human_throw_in_count=2,
        max_transfer_target=36,
        arithmetic_mean_throw_in_count=1,
    )


def test_export_requires_authentication(client: TestClient) -> None:
    assert client.get("/api/account/export").status_code == 401
    assert (
        client.post(
            "/api/account/delete",
            headers={"Origin": ORIGIN},
            json={"password": PASSWORD, "confirmation": "DELETE"},
        ).status_code
        == 401
    )


def test_export_contains_owned_data_and_excludes_credentials_and_other_users(
    client: TestClient,
    database: Database,
) -> None:
    assert register(client).status_code == 201
    with database.session() as session:
        alice = session.scalar(select(User).where(User.email == "alice@example.com"))
        assert alice is not None
        other = User(
            email="bob-private@example.com",
            normalized_email="bob-private@example.com",
            display_name="Bob",
            password_hash="not-exported",
            preferred_locale="en",
        )
        session.add(other)
        session.flush()
        other_id = other.id
        match = completed_match(
            alice.id,
            session_id="export-match",
            opponent_user_id=other.id,
            opponent_name="Bob",
        )
        session.add(match)
        session.flush()
        session.add_all(
            [
                XPLedgerEntry(
                    user_id=alice.id,
                    amount=100,
                    source_type="MATCH",
                    source_key=f"match:{match.id}:base",
                    source_match_id=match.id,
                ),
                UserAchievement(
                    user_id=alice.id,
                    achievement_code="FIRST_MATCH",
                    unlocked_at=datetime.now(UTC),
                    unlocked_match_id=match.id,
                ),
                UserCosmeticUnlock(
                    user_id=alice.id,
                    cosmetic_code="LEVEL_2_FRAME",
                    unlocked_at=datetime.now(UTC),
                    source_type="LEVEL",
                    source_key="level:2",
                ),
                UserCosmeticLoadout(
                    user_id=alice.id,
                    card_back_code="CLASSIC",
                    table_theme_code="CLASSIC_TABLE",
                    profile_frame_code="LEVEL_2_FRAME",
                ),
            ]
        )
        session.commit()

    response = client.get("/api/account/export")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert "kiba-data-export-" in response.headers["content-disposition"]
    payload = response.json()
    assert payload["export_version"] == "1.0"
    assert payload["account"]["email"] == "alice@example.com"
    assert payload["completed_matches"][0]["game_session_id"] == "export-match"
    assert payload["completed_matches"][0]["opponent_display_name"] == "Bob"
    assert payload["xp_ledger"][0]["amount"] == 100
    assert payload["achievements"][0]["code"] == "FIRST_MATCH"
    assert payload["cosmetics"]["loadout"]["profile_frame_code"] == "LEVEL_2_FRAME"
    serialized = response.text
    for forbidden in (
        "password_hash",
        "token_hash",
        "auth_sessions",
        "account_tokens",
        "bob-private@example.com",
        "not-exported",
        str(other_id),
    ):
        assert forbidden not in serialized


def test_deletion_requires_password_removes_owned_data_and_anonymizes_opponent_history(
    client: TestClient,
    database: Database,
) -> None:
    assert register(client).status_code == 201
    with database.session() as session:
        alice = session.scalar(select(User).where(User.email == "alice@example.com"))
        assert alice is not None
        alice_id = alice.id
        bob = User(
            email="bob@example.com",
            normalized_email="bob@example.com",
            display_name="Bob",
            password_hash="hash",
            preferred_locale="en",
        )
        session.add(bob)
        session.flush()
        alice_match = completed_match(alice.id, session_id="alice-row")
        bob_match = completed_match(
            bob.id,
            session_id="bob-row",
            opponent_user_id=alice.id,
            opponent_name="Alice",
        )
        session.add_all([alice_match, bob_match])
        session.flush()
        session.add_all(
            [
                XPLedgerEntry(
                    user_id=alice.id,
                    amount=100,
                    source_type="MATCH",
                    source_key="delete-match",
                    source_match_id=alice_match.id,
                ),
                UserAchievement(
                    user_id=alice.id,
                    achievement_code="FIRST_MATCH",
                    unlocked_at=datetime.now(UTC),
                ),
                UserCosmeticUnlock(
                    user_id=alice.id,
                    cosmetic_code="LEVEL_2_FRAME",
                    unlocked_at=datetime.now(UTC),
                    source_type="LEVEL",
                    source_key="level:2",
                ),
                UserCosmeticLoadout(
                    user_id=alice.id,
                    card_back_code="CLASSIC",
                    table_theme_code="CLASSIC_TABLE",
                    profile_frame_code="LEVEL_2_FRAME",
                ),
            ]
        )
        session.commit()

    wrong = client.post(
        "/api/account/delete",
        headers={"Origin": ORIGIN},
        json={"password": "wrong password", "confirmation": "DELETE"},
    )
    assert wrong.status_code == 401
    assert client.get("/api/auth/me").status_code == 200

    response = client.post(
        "/api/account/delete",
        headers={"Origin": ORIGIN},
        json={"password": PASSWORD, "confirmation": "DELETE"},
    )

    assert response.status_code == 204
    assert "kiba_session=" in response.headers["set-cookie"]
    assert client.get("/api/auth/me").status_code == 401
    with database.session() as session:
        assert session.get(User, alice_id) is None
        for model in (
            AuthSession,
            AccountToken,
            CompletedMatch,
            XPLedgerEntry,
            UserAchievement,
            UserCosmeticUnlock,
            UserCosmeticLoadout,
        ):
            assert (
                session.scalar(
                    select(func.count()).select_from(model).where(model.user_id == alice_id)
                )
                == 0
            )
        retained = session.scalar(
            select(CompletedMatch).where(CompletedMatch.game_session_id == "bob-row")
        )
        assert retained is not None
        assert retained.opponent_user_id is None
        assert retained.opponent_display_name is None

    client.cookies.clear()
    assert (
        client.post(
            "/api/auth/login",
            headers={"Origin": ORIGIN},
            json={"email": "alice@example.com", "password": PASSWORD},
        ).status_code
        == 401
    )
    assert register(client).status_code == 201


def test_deletion_detaches_process_local_bot_and_pvp_sessions(
    client: TestClient,
    database: Database,
) -> None:
    assert register(client).status_code == 201
    with database.session() as session:
        user = session.scalar(select(User).where(User.email == "alice@example.com"))
        assert user is not None
        user_id = user.id
    game_id = client.post("/api/games").json()["game_id"]
    room, participant = client.app.state.pvp_service.create_room("Alice", user_id=user_id)

    response = client.post(
        "/api/account/delete",
        headers={"Origin": ORIGIN},
        json={"password": PASSWORD, "confirmation": "DELETE"},
    )

    assert response.status_code == 204
    assert client.app.state.game_service.get_game(game_id).user_id is None
    detached_room = client.app.state.pvp_service.get_room(room.invite_code)
    assert detached_room.participant_by_id(participant.participant_id).user_id is None


def test_transaction_failure_rolls_back_account_and_opponent_anonymization(
    database: Database,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with database.session() as session:
        alice = User(
            email="alice@example.com",
            normalized_email="alice@example.com",
            display_name="Alice",
            password_hash="hash",
            preferred_locale="en",
        )
        bob = User(
            email="bob@example.com",
            normalized_email="bob@example.com",
            display_name="Bob",
            password_hash="hash",
            preferred_locale="en",
        )
        session.add_all([alice, bob])
        session.flush()
        alice_id = alice.id
        retained = completed_match(
            bob.id,
            session_id="rollback-row",
            opponent_user_id=alice.id,
            opponent_name="Alice",
        )
        session.add(retained)
        session.commit()

    original_factory = database._session_factory
    failing_session = original_factory()

    def fail_commit() -> None:
        raise RuntimeError("simulated commit failure")

    monkeypatch.setattr(failing_session, "commit", fail_commit)
    monkeypatch.setattr(database, "_session_factory", lambda: failing_session)
    with pytest.raises(RuntimeError, match="simulated commit failure"):
        AccountDataService(database).delete(alice_id)
    monkeypatch.setattr(database, "_session_factory", original_factory)

    with database.session() as session:
        assert session.get(User, alice_id) is not None
        row = session.scalar(
            select(CompletedMatch).where(CompletedMatch.game_session_id == "rollback-row")
        )
        assert row is not None
        assert row.opponent_user_id == alice_id
        assert row.opponent_display_name == "Alice"
