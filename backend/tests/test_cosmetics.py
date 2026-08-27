from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from random import Random
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from kiba_api.api.serialization import serialize_game_session
from kiba_api.config import Settings
from kiba_api.game import Card, GameState, Rank, Seat, Suit, create_new_game
from kiba_api.main import create_app
from kiba_api.persistence import (
    ACHIEVEMENTS,
    COSMETICS,
    Base,
    CompletedMatch,
    CosmeticAward,
    CosmeticCategory,
    CosmeticCode,
    CosmeticError,
    CosmeticErrorCode,
    CosmeticService,
    CosmeticUnlockType,
    Database,
    MatchOutcome,
    ProgressionAward,
    User,
    UserAchievement,
    UserCosmeticLoadout,
    UserCosmeticUnlock,
    XPLedgerEntry,
    progression_from_total_xp,
)
from kiba_api.sessions import GameAppearance, GameSessionService, HumanActionType

ORIGIN = "http://testserver"


@pytest.fixture
def database() -> Database:
    value = Database("sqlite://")
    Base.metadata.create_all(value.engine)
    yield value
    value.dispose()


def add_user(database: Database, email: str = "cosmetic@example.com") -> UUID:
    user_id = uuid4()
    with database.session() as session:
        session.add(
            User(
                id=user_id,
                email=email,
                normalized_email=email,
                display_name="Оформление",
                password_hash="unused",
                is_active=True,
            )
        )
        session.commit()
    return user_id


def add_xp(database: Database, user_id: UUID, amount: int) -> None:
    with database.session() as session:
        session.add(
            XPLedgerEntry(
                user_id=user_id,
                amount=amount,
                source_type="MATCH",
                source_key=f"test:{uuid4()}",
            )
        )
        session.commit()


def add_achievement(database: Database, user_id: UUID, code: str) -> None:
    with database.session() as session:
        session.add(
            UserAchievement(
                user_id=user_id,
                achievement_code=code,
                unlocked_at=datetime.now(UTC),
            )
        )
        session.commit()


def add_match(
    database: Database,
    user_id: UUID,
    index: int,
    *,
    outcome: MatchOutcome = MatchOutcome.WIN,
    max_transfer_target: int = 0,
    mean_throw_ins: int = 0,
) -> CompletedMatch:
    moment = datetime(2026, 8, 1, tzinfo=UTC) + timedelta(days=index)
    match = CompletedMatch(
        user_id=user_id,
        game_session_id=f"cosmetic-{user_id}-{index}",
        opponent_type="BOT",
        outcome=outcome.value,
        started_at=moment - timedelta(minutes=2),
        completed_at=moment,
        duration_seconds=120,
        user_seat="one",
        initial_attacker="one",
        final_human_card_count=0,
        final_bot_card_count=2,
        human_action_count=3,
        human_transfer_count=int(max_transfer_target > 0),
        human_take_count=0,
        human_throw_in_count=mean_throw_ins,
        max_transfer_target=max_transfer_target,
        arithmetic_mean_throw_in_count=mean_throw_ins,
    )
    with database.session() as session:
        session.add(match)
        session.commit()
    return match


def test_static_catalogue_is_stable_and_references_real_achievements() -> None:
    codes = [definition.code.value for definition in COSMETICS]
    achievement_codes = {definition.code for definition in ACHIEVEMENTS}

    assert len(codes) == len(set(codes)) == 10
    assert {definition.category for definition in COSMETICS} == set(CosmeticCategory)
    assert {
        definition.code
        for definition in COSMETICS
        if definition.unlock_type is CosmeticUnlockType.DEFAULT
    } == {
        CosmeticCode.CLASSIC,
        CosmeticCode.CLASSIC_TABLE,
        CosmeticCode.NO_FRAME,
    }
    for definition in COSMETICS:
        if definition.unlock_type is CosmeticUnlockType.LEVEL:
            assert isinstance(definition.unlock_requirement, int)
            assert definition.unlock_requirement >= 2
        if definition.unlock_type is CosmeticUnlockType.ACHIEVEMENT:
            assert definition.unlock_requirement in achievement_codes


def test_new_account_gets_default_loadout_without_unlock_rows(database: Database) -> None:
    user_id = add_user(database)
    state = CosmeticService(database).get_catalogue(user_id)

    assert state.loadout.card_back_code == "CLASSIC"
    assert state.loadout.table_theme_code == "CLASSIC_TABLE"
    assert state.loadout.profile_frame_code == "NO_FRAME"
    assert {item.definition.code.value for item in state.items if item.unlocked} == {
        "CLASSIC",
        "CLASSIC_TABLE",
        "NO_FRAME",
    }
    with database.session() as session:
        assert session.scalar(select(func.count()).select_from(UserCosmeticUnlock)) == 0
        assert session.get(UserCosmeticLoadout, user_id) is not None


@pytest.mark.parametrize(
    ("xp", "expected"),
    [
        (50, {"LEVEL_2_FRAME"}),
        (200, {"LEVEL_2_FRAME", "LEVEL_3_BACK"}),
        (450, {"LEVEL_2_FRAME", "LEVEL_3_BACK", "NIGHT_TABLE"}),
    ],
)
def test_level_cosmetics_unlock_retroactively_and_idempotently(
    database: Database,
    xp: int,
    expected: set[str],
) -> None:
    user_id = add_user(database, f"level-{xp}@example.com")
    add_xp(database, user_id, xp)
    service = CosmeticService(database)

    first = service.synchronize(user_id)
    second = service.synchronize(user_id)

    assert {definition.code.value for definition in first.new_unlocks} == expected
    assert second.new_unlocks == ()
    with database.session() as session:
        assert session.scalar(select(func.count()).select_from(UserCosmeticUnlock)) == len(expected)


@pytest.mark.parametrize(
    ("achievement", "cosmetic"),
    [
        ("SNOWBALL_36", "SNOWBALL_BACK"),
        ("AVALANCHE_72", "AVALANCHE_BACK"),
        ("ARITHMETIC_MEAN", "MATHEMATICIAN_TABLE"),
        ("TEN_WINS", "WINNER_FRAME"),
    ],
)
def test_achievement_cosmetics_reuse_canonical_codes(
    database: Database,
    achievement: str,
    cosmetic: str,
) -> None:
    user_id = add_user(database, f"{achievement.lower()}@example.com")
    add_achievement(database, user_id, achievement)

    result = CosmeticService(database).synchronize(user_id)

    assert cosmetic in {definition.code.value for definition in result.new_unlocks}


def test_historical_matches_backfill_level_and_achievement_rewards(database: Database) -> None:
    user_id = add_user(database)
    add_match(database, user_id, 0, max_transfer_target=72, mean_throw_ins=1)

    state = CosmeticService(database).get_catalogue(user_id)

    unlocked = {item.definition.code.value for item in state.items if item.unlocked}
    assert {
        "LEVEL_2_FRAME",
        "SNOWBALL_BACK",
        "AVALANCHE_BACK",
        "MATHEMATICIAN_TABLE",
    }.issubset(unlocked)


def test_equip_validates_ownership_category_and_partial_updates(database: Database) -> None:
    user_id = add_user(database)
    add_xp(database, user_id, 450)
    service = CosmeticService(database)

    changed = service.equip(user_id, card_back_code="LEVEL_3_BACK")
    assert changed.loadout.card_back_code == "LEVEL_3_BACK"
    assert changed.loadout.table_theme_code == "CLASSIC_TABLE"

    changed = service.equip(user_id, table_theme_code="NIGHT_TABLE")
    assert changed.loadout.card_back_code == "LEVEL_3_BACK"
    assert changed.loadout.table_theme_code == "NIGHT_TABLE"

    with pytest.raises(CosmeticError, match="cosmetic_not_found"):
        service.equip(user_id, card_back_code="UNKNOWN")
    with pytest.raises(CosmeticError, match="cosmetic_wrong_category"):
        service.equip(user_id, card_back_code="CLASSIC_TABLE")

    locked_user = add_user(database, "locked@example.com")
    with pytest.raises(CosmeticError, match="cosmetic_locked"):
        service.equip(locked_user, table_theme_code="NIGHT_TABLE")

    defaulted = service.equip(user_id, card_back_code="CLASSIC")
    assert defaulted.loadout.card_back_code == "CLASSIC"


def test_one_users_unlocks_never_authorize_another_user(database: Database) -> None:
    owner = add_user(database, "owner@example.com")
    other = add_user(database, "other@example.com")
    add_achievement(database, owner, "TEN_WINS")
    service = CosmeticService(database)
    service.synchronize(owner)

    with pytest.raises(CosmeticError) as error:
        service.equip(other, profile_frame_code="WINNER_FRAME")
    assert error.value.code is CosmeticErrorCode.LOCKED


def register(client: TestClient, email: str = "api-cosmetic@example.com") -> UUID:
    response = client.post(
        "/api/auth/register",
        headers={"Origin": ORIGIN},
        json={"email": email, "display_name": "Игрок", "password": "password123"},
    )
    assert response.status_code == 201
    return UUID(response.json()["id"])


def test_cosmetic_apis_protect_guests_and_return_unlock_metadata(database: Database) -> None:
    client = TestClient(
        create_app(
            database=database,
            settings=Settings(database_url="sqlite://", csrf_trusted_origins=(ORIGIN,)),
        )
    )
    assert client.get("/api/cosmetics").status_code == 401
    assert (
        client.patch(
            "/api/profile/cosmetics",
            headers={"Origin": ORIGIN},
            json={"card_back_code": "CLASSIC"},
        ).status_code
        == 401
    )
    register(client)

    response = client.get("/api/cosmetics")

    assert response.status_code == 200
    payload = response.json()
    assert payload["loadout"] == {
        "card_back_code": "CLASSIC",
        "table_theme_code": "CLASSIC_TABLE",
        "profile_frame_code": "NO_FRAME",
    }
    night = next(item for item in payload["items"] if item["code"] == "NIGHT_TABLE")
    assert night["unlocked"] is False
    assert night["unlock"] == {
        "type": "LEVEL",
        "requirement": 4,
        "achievement_title": None,
    }
    avalanche = next(item for item in payload["items"] if item["code"] == "AVALANCHE_BACK")
    assert avalanche["unlock"]["achievement_title"] == "Лавина"
    assert "source_key" not in response.text


def test_equip_api_returns_machine_readable_errors_and_updated_loadout(
    database: Database,
) -> None:
    client = TestClient(
        create_app(
            database=database,
            settings=Settings(database_url="sqlite://", csrf_trusted_origins=(ORIGIN,)),
        )
    )
    user_id = register(client)
    add_xp(database, user_id, 450)

    changed = client.patch(
        "/api/profile/cosmetics",
        headers={"Origin": ORIGIN},
        json={"card_back_code": "LEVEL_3_BACK", "table_theme_code": "NIGHT_TABLE"},
    )
    locked = client.patch(
        "/api/profile/cosmetics",
        headers={"Origin": ORIGIN},
        json={"profile_frame_code": "WINNER_FRAME"},
    )
    wrong_category = client.patch(
        "/api/profile/cosmetics",
        headers={"Origin": ORIGIN},
        json={"card_back_code": "NIGHT_TABLE"},
    )

    assert changed.status_code == 200
    assert changed.json()["loadout"]["card_back_code"] == "LEVEL_3_BACK"
    assert changed.json()["loadout"]["table_theme_code"] == "NIGHT_TABLE"
    assert locked.status_code == 409
    assert locked.json()["detail"]["code"] == "cosmetic_locked"
    assert wrong_category.status_code == 409
    assert wrong_category.json()["detail"]["code"] == "cosmetic_wrong_category"


def test_authenticated_games_capture_loadout_and_guest_games_use_defaults(
    database: Database,
) -> None:
    client = TestClient(
        create_app(
            database=database,
            settings=Settings(database_url="sqlite://", csrf_trusted_origins=(ORIGIN,)),
        )
    )
    user_id = register(client)
    add_xp(database, user_id, 450)
    cosmetic_service = CosmeticService(database)
    cosmetic_service.equip(
        user_id,
        card_back_code="LEVEL_3_BACK",
        table_theme_code="NIGHT_TABLE",
        profile_frame_code="LEVEL_2_FRAME",
    )

    authenticated_game = client.post("/api/games")
    client.post("/api/auth/logout", headers={"Origin": ORIGIN})
    guest_game = client.post("/api/games")

    assert authenticated_game.json()["cosmetics"] == {
        "card_back_code": "LEVEL_3_BACK",
        "table_theme_code": "NIGHT_TABLE",
        "profile_frame_code": "LEVEL_2_FRAME",
    }
    assert guest_game.json()["cosmetics"] == {
        "card_back_code": "CLASSIC",
        "table_theme_code": "CLASSIC_TABLE",
        "profile_frame_code": "NO_FRAME",
    }


def test_cosmetic_appearance_never_enters_or_changes_gameplay_state() -> None:
    state_one = create_new_game(rng=Random(42))
    state_two = create_new_game(rng=Random(42))
    service_one = GameSessionService(game_factory=lambda: state_one)
    service_two = GameSessionService(game_factory=lambda: state_two)

    classic = service_one.create_game(appearance=GameAppearance())
    themed = service_two.create_game(
        appearance=GameAppearance("AVALANCHE_BACK", "NIGHT_TABLE", "WINNER_FRAME")
    )

    assert classic.state == themed.state
    assert classic.appearance != themed.appearance
    assert "appearance" not in classic.state.__dataclass_fields__


def test_progression_award_can_report_server_confirmed_cosmetic_unlocks() -> None:
    award = ProgressionAward(
        base_xp=100,
        achievement_bonus_xp=75,
        total_awarded_xp=175,
        new_achievements=(),
        summary=progression_from_total_xp(175),
    )
    updated = replace(
        award,
        new_cosmetics=(CosmeticAward("SNOWBALL_BACK", "CARD_BACK", "Снежный ком"),),
    )
    state = GameState(
        seat_one_hand=(Card(Rank.ACE, Suit.CLUBS),),
        seat_two_hand=(Card(Rank.SIX, Suit.CLUBS),),
        draw_pile=(),
        discard_pile=(),
        current_attacker=Seat.ONE,
    )
    service = GameSessionService(game_factory=lambda: state)
    created = service.create_game()
    completed = service.play_human_action(
        created.game_id,
        HumanActionType.INITIAL_ATTACK,
        (Card(Rank.ACE, Suit.CLUBS),),
    )

    response = serialize_game_session(replace(completed, progression_award=updated))

    assert response.progression_award is not None
    assert response.progression_award.new_cosmetics[0].code == "SNOWBALL_BACK"
