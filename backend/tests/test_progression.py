from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from kiba_api.config import Settings
from kiba_api.game import Card, GamePhase, GameState, Rank, Seat, Suit
from kiba_api.main import create_app
from kiba_api.persistence import (
    ACHIEVEMENTS,
    Base,
    CompletedMatch,
    Database,
    MatchHistoryService,
    MatchOutcome,
    ProgressionService,
    User,
    UserAchievement,
    XPLedgerEntry,
    level_from_total_xp,
    progression_from_total_xp,
    xp_threshold_for_level,
)
from kiba_api.sessions import GameSession, GameSessionService, HumanActionType

ORIGIN = "http://testserver"


@pytest.fixture
def database() -> Database:
    value = Database("sqlite://")
    Base.metadata.create_all(value.engine)
    yield value
    value.dispose()


def add_user(database: Database, email: str = "progress@example.com") -> UUID:
    user_id = uuid4()
    with database.session() as session:
        session.add(
            User(
                id=user_id,
                email=email,
                normalized_email=email,
                display_name="Прогресс",
                password_hash="unused",
                is_active=True,
            )
        )
        session.commit()
    return user_id


def add_match(
    database: Database,
    user_id: UUID,
    outcome: MatchOutcome,
    index: int,
    *,
    max_transfer_target: int = 0,
    mean_throw_ins: int = 0,
) -> CompletedMatch:
    moment = datetime(2026, 8, 1, tzinfo=UTC) + timedelta(days=index)
    match = CompletedMatch(
        user_id=user_id,
        game_session_id=f"game-{user_id}-{index}",
        opponent_type="BOT",
        outcome=outcome.value,
        started_at=moment - timedelta(minutes=3),
        completed_at=moment,
        duration_seconds=180,
        user_seat="one",
        initial_attacker="one",
        final_human_card_count=0 if outcome is MatchOutcome.WIN else 2,
        final_bot_card_count=0 if outcome is MatchOutcome.LOSS else 2,
        human_action_count=5,
        human_transfer_count=0,
        human_take_count=0,
        human_throw_in_count=mean_throw_ins,
        max_transfer_target=max_transfer_target,
        arithmetic_mean_throw_in_count=mean_throw_ins,
    )
    with database.session() as session:
        session.add(match)
        session.commit()
    return match


@pytest.mark.parametrize(
    ("total_xp", "level"),
    [(0, 1), (49, 1), (50, 2), (199, 2), (200, 3), (449, 3), (450, 4), (800, 5), (4050, 10)],
)
def test_level_boundaries_are_exact(total_xp: int, level: int) -> None:
    assert level_from_total_xp(total_xp) == level


def test_level_progress_fields_use_quadratic_thresholds() -> None:
    assert xp_threshold_for_level(4) == 450
    summary = progression_from_total_xp(175, achievements_unlocked=2)
    assert summary.level == 2
    assert summary.level_start_xp == 50
    assert summary.next_level_xp == 200
    assert summary.xp_into_level == 125
    assert summary.xp_needed_for_next_level == 25
    assert summary.progress_fraction == pytest.approx(5 / 6)
    assert summary.achievements_unlocked == 2


@pytest.mark.parametrize(
    ("outcome", "expected_base"),
    [(MatchOutcome.WIN, 100), (MatchOutcome.DRAW, 50), (MatchOutcome.LOSS, 25)],
)
def test_match_base_xp_and_first_match_award_once(
    database: Database,
    outcome: MatchOutcome,
    expected_base: int,
) -> None:
    user_id = add_user(database, f"{outcome.lower()}@example.com")
    match = add_match(database, user_id, outcome, 0)
    service = ProgressionService(database)

    first = service.synchronize_for_match(user_id, match.id)
    second = service.synchronize_for_match(user_id, match.id)

    expected_bonus = 25 + (50 if outcome is MatchOutcome.WIN else 0)
    assert first.base_xp == expected_base
    assert first.achievement_bonus_xp == expected_bonus
    assert first.total_awarded_xp == expected_base + expected_bonus
    assert second == first
    with database.session() as session:
        assert session.scalar(select(func.count()).select_from(XPLedgerEntry)) == (
            3 if outcome is MatchOutcome.WIN else 2
        )


def test_historical_matches_backfill_chronologically_and_idempotently(database: Database) -> None:
    user_id = add_user(database)
    outcomes = [
        MatchOutcome.WIN,
        MatchOutcome.WIN,
        MatchOutcome.LOSS,
        MatchOutcome.WIN,
        MatchOutcome.WIN,
        MatchOutcome.WIN,
        MatchOutcome.WIN,
        MatchOutcome.WIN,
        MatchOutcome.WIN,
        MatchOutcome.WIN,
    ]
    matches = [
        add_match(database, user_id, outcome, index) for index, outcome in enumerate(outcomes)
    ]
    service = ProgressionService(database)

    first = service.synchronize(user_id)
    second = service.synchronize(user_id)

    assert second == first
    assert first.achievements_unlocked == 4
    states = {state.definition.code.value: state for state in service.get_achievements(user_id)}
    assert states["FIRST_MATCH"].unlocked_at == matches[0].completed_at.replace(tzinfo=None)
    assert states["FIRST_WIN"].unlocked_at == matches[0].completed_at.replace(tzinfo=None)
    assert states["WIN_STREAK_3"].unlocked_at == matches[5].completed_at.replace(tzinfo=None)
    assert states["TEN_GAMES"].unlocked_at == matches[9].completed_at.replace(tzinfo=None)
    assert not states["TEN_WINS"].unlocked
    with database.session() as session:
        assert session.scalar(select(func.count()).select_from(UserAchievement)) == 4


def test_loss_and_draw_break_win_streak(database: Database) -> None:
    user_id = add_user(database)
    for index, outcome in enumerate(
        [MatchOutcome.WIN, MatchOutcome.WIN, MatchOutcome.DRAW, MatchOutcome.WIN, MatchOutcome.WIN]
    ):
        add_match(database, user_id, outcome, index)

    ProgressionService(database).synchronize(user_id)

    with database.session() as session:
        codes = set(session.scalars(select(UserAchievement.achievement_code)))
    assert "WIN_STREAK_3" not in codes


def test_ten_wins_unlocks_exactly_on_tenth_win(database: Database) -> None:
    user_id = add_user(database)
    for index in range(9):
        add_match(database, user_id, MatchOutcome.WIN, index)
    service = ProgressionService(database)
    service.synchronize(user_id)
    assert not next(
        state for state in service.get_achievements(user_id) if state.definition.code == "TEN_WINS"
    ).unlocked

    tenth = add_match(database, user_id, MatchOutcome.WIN, 9)
    award = service.synchronize_for_match(user_id, tenth.id)

    assert "TEN_WINS" in {definition.code.value for definition in award.new_achievements}
    with database.session() as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(UserAchievement)
                .where(UserAchievement.achievement_code == "TEN_WINS")
            )
            == 1
        )


def test_transfer_and_mean_achievements_use_persisted_authoritative_facts(
    database: Database,
) -> None:
    user_id = add_user(database)
    add_match(database, user_id, MatchOutcome.LOSS, 0, max_transfer_target=35)
    add_match(database, user_id, MatchOutcome.LOSS, 1, max_transfer_target=36)
    add_match(database, user_id, MatchOutcome.LOSS, 2, max_transfer_target=71)
    final = add_match(
        database,
        user_id,
        MatchOutcome.LOSS,
        3,
        max_transfer_target=72,
        mean_throw_ins=1,
    )
    service = ProgressionService(database)

    service.synchronize(user_id)

    with database.session() as session:
        unlocks = {
            row.achievement_code: row.unlocked_match_id
            for row in session.scalars(select(UserAchievement))
        }
    assert unlocks["SNOWBALL_36"] is not None
    assert unlocks["AVALANCHE_72"] == final.id
    assert unlocks["ARITHMETIC_MEAN"] == final.id


def _register(client: TestClient, email: str) -> UUID:
    response = client.post(
        "/api/auth/register",
        headers={"Origin": ORIGIN},
        json={"email": email, "display_name": "Игрок", "password": "password123"},
    )
    assert response.status_code == 201
    return UUID(response.json()["id"])


def test_progression_and_achievement_apis_sync_history_and_protect_guests(
    database: Database,
) -> None:
    settings = Settings(database_url="sqlite://", csrf_trusted_origins=(ORIGIN,))
    client = TestClient(create_app(database=database, settings=settings))
    assert client.get("/api/progression").status_code == 401
    assert client.get("/api/achievements").status_code == 401
    user_id = _register(client, "api-progress@example.com")

    empty = client.get("/api/progression")
    assert empty.json() == {
        "total_xp": 0,
        "level": 1,
        "level_start_xp": 0,
        "next_level_xp": 50,
        "xp_into_level": 0,
        "xp_needed_for_next_level": 50,
        "progress_fraction": 0.0,
        "achievements_unlocked": 0,
        "achievements_total": len(ACHIEVEMENTS),
    }
    add_match(database, user_id, MatchOutcome.WIN, 0)

    progression = client.get("/api/progression")
    achievements = client.get("/api/achievements")

    assert progression.json()["total_xp"] == 175
    assert progression.json()["level"] == 2
    assert [item["code"] for item in achievements.json()] == [
        definition.code.value for definition in ACHIEVEMENTS
    ]
    assert [item["code"] for item in achievements.json() if item["unlocked"]] == [
        "FIRST_MATCH",
        "FIRST_WIN",
    ]
    assert "source_key" not in progression.text + achievements.text


def test_completed_game_response_contains_server_confirmed_progression_delta(
    database: Database,
) -> None:
    user_id = add_user(database, "result@example.com")
    history = MatchHistoryService(database)
    progression = ProgressionService(database)

    def record(session: GameSession):
        history.record_completed_match(session)
        match = history.get_match_by_game_session(session.game_id)
        return progression.synchronize_for_match(user_id, match.id)

    def one_move_win() -> GameState:
        return GameState(
            seat_one_hand=(Card(Rank.ACE, Suit.CLUBS),),
            seat_two_hand=(Card(Rank.SIX, Suit.CLUBS),),
            draw_pile=(),
            discard_pile=(),
            current_attacker=Seat.ONE,
        )

    service = GameSessionService(game_factory=one_move_win, completion_recorder=record)
    session = service.create_game(user_id=user_id)
    finished = service.play_human_action(
        session.game_id,
        HumanActionType.INITIAL_ATTACK,
        (Card(Rank.ACE, Suit.CLUBS),),
    )
    assert finished.state.phase is GamePhase.COMPLETE
    app = create_app(service, database=database)
    response = TestClient(app).get(f"/api/games/{session.game_id}")

    assert response.json()["progression_award"] == {
        "base_xp": 100,
        "achievement_bonus_xp": 75,
        "total_awarded_xp": 175,
        "new_achievements": [
            {
                "code": "FIRST_MATCH",
                "title": "Первая партия",
                "description": "Сыграть первую партию.",
                "bonus_xp": 25,
            },
            {
                "code": "FIRST_WIN",
                "title": "Первая победа",
                "description": "Выиграть первую партию.",
                "bonus_xp": 50,
            },
        ],
        "total_xp": 175,
        "level": 2,
        "next_level_xp": 200,
        "xp_needed_for_next_level": 25,
    }
    service.get_game(session.game_id)
    service.get_game(session.game_id)
    with database.session() as database_session:
        assert database_session.scalar(select(func.count()).select_from(XPLedgerEntry)) == 3


def test_guest_completion_creates_no_match_or_xp_ledger(database: Database) -> None:
    history = MatchHistoryService(database)
    progression = ProgressionService(database)

    def record(session: GameSession):
        history.record_completed_match(session)
        match = history.get_match_by_game_session(session.game_id)
        if session.user_id is None:
            raise AssertionError("guest completion recorder must not run")
        return progression.synchronize_for_match(session.user_id, match.id)

    state = GameState(
        seat_one_hand=(Card(Rank.ACE, Suit.CLUBS),),
        seat_two_hand=(Card(Rank.SIX, Suit.CLUBS),),
        draw_pile=(),
        discard_pile=(),
        current_attacker=Seat.ONE,
    )
    service = GameSessionService(game_factory=lambda: state, completion_recorder=record)
    game = service.create_game()

    finished = service.play_human_action(
        game.game_id,
        HumanActionType.INITIAL_ATTACK,
        (Card(Rank.ACE, Suit.CLUBS),),
    )

    assert finished.state.phase is GamePhase.COMPLETE
    assert finished.progression_award is None
    with database.session() as session:
        assert session.scalar(select(func.count()).select_from(CompletedMatch)) == 0
        assert session.scalar(select(func.count()).select_from(XPLedgerEntry)) == 0
