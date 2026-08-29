from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from kiba_api.config import Settings
from kiba_api.game import (
    Card,
    GameOutcome,
    GamePhase,
    GameResult,
    GameState,
    Rank,
    Seat,
    Suit,
    play_game_defense,
    play_game_initial_attack,
    start_game_bout,
)
from kiba_api.main import create_app
from kiba_api.persistence import (
    Base,
    CompletedMatch,
    Database,
    MatchHistoryService,
    MatchOutcome,
    User,
)
from kiba_api.sessions import GameSession, GameSessionService, HumanActionType

ORIGIN = "http://testserver"


def card(rank: Rank, suit: Suit = Suit.CLUBS) -> Card:
    return Card(rank=rank, suit=suit)


@pytest.fixture
def database() -> Database:
    value = Database("sqlite://")
    Base.metadata.create_all(value.engine)
    yield value
    value.dispose()


def add_user(database: Database, *, email: str = "player@example.com") -> UUID:
    user_id = uuid4()
    with database.session() as session:
        session.add(
            User(
                id=user_id,
                email=email,
                normalized_email=email,
                display_name="Игрок",
                password_hash="unused-test-hash",
                is_active=True,
            )
        )
        session.commit()
    return user_id


def completed_session(
    user_id: UUID | None,
    outcome: MatchOutcome,
    *,
    game_id: str = "completed-game",
    started_at: datetime | None = None,
) -> GameSession:
    if outcome is MatchOutcome.WIN:
        hands = ((), (card(Rank.SIX),))
        result = GameResult(GameOutcome.WIN, Seat.ONE)
    elif outcome is MatchOutcome.LOSS:
        hands = ((card(Rank.SIX),), ())
        result = GameResult(GameOutcome.WIN, Seat.TWO)
    else:
        hands = ((), ())
        result = GameResult(GameOutcome.DRAW, None)
    state = GameState(
        seat_one_hand=hands[0],
        seat_two_hand=hands[1],
        draw_pile=(),
        discard_pile=(),
        current_attacker=None,
        phase=GamePhase.COMPLETE,
        result=result,
    )
    return GameSession(
        game_id=game_id,
        state=state,
        user_id=user_id,
        started_at=started_at or datetime(2026, 8, 27, 10, tzinfo=UTC),
        initial_attacker=Seat.TWO,
        human_action_count=9,
        human_transfer_count=2,
        human_take_count=1,
        human_throw_in_count=3,
        max_transfer_target=72,
        arithmetic_mean_throw_in_count=1,
    )


@pytest.mark.parametrize(
    ("outcome", "stored"),
    [
        (MatchOutcome.WIN, "WIN"),
        (MatchOutcome.LOSS, "LOSS"),
        (MatchOutcome.DRAW, "DRAW"),
    ],
)
def test_completed_match_maps_human_outcome_and_summary(
    database: Database,
    outcome: MatchOutcome,
    stored: str,
) -> None:
    user_id = add_user(database, email=f"{stored.lower()}@example.com")

    def clock() -> datetime:
        return datetime(2026, 8, 27, 10, 2, 5, tzinfo=UTC)

    service = MatchHistoryService(database, clock=clock)

    service.record_completed_match(completed_session(user_id, outcome, game_id=stored))

    with database.session() as session:
        match = session.scalar(
            select(CompletedMatch).where(CompletedMatch.game_session_id == stored)
        )
        assert match is not None
        assert match.outcome == stored
        assert match.opponent_type == "BOT"
        assert match.duration_seconds == 125
        assert match.user_id == user_id
        assert match.user_seat == "one"
        assert match.initial_attacker == "two"
        assert match.final_human_card_count == (0 if outcome is not MatchOutcome.LOSS else 1)
        assert match.human_action_count == 9
        assert match.human_transfer_count == 2
        assert match.human_take_count == 1
        assert match.human_throw_in_count == 3
        assert match.max_transfer_target == 72
        assert match.arithmetic_mean_throw_in_count == 1


def test_match_recording_is_idempotent_and_database_unique(database: Database) -> None:
    user_id = add_user(database)
    history = MatchHistoryService(database)
    terminal = completed_session(user_id, MatchOutcome.WIN)

    history.record_completed_match(terminal)
    history.record_completed_match(terminal)

    with database.session() as session:
        assert session.scalar(select(func.count()).select_from(CompletedMatch)) == 1
        duplicate = CompletedMatch(
            user_id=user_id,
            game_session_id=terminal.game_id,
            opponent_type="BOT",
            outcome="WIN",
            started_at=terminal.started_at,
            completed_at=terminal.started_at,
            duration_seconds=0,
            user_seat="one",
            initial_attacker="one",
            final_human_card_count=0,
            final_bot_card_count=1,
            human_action_count=0,
            human_transfer_count=0,
            human_take_count=0,
            human_throw_in_count=0,
            max_transfer_target=0,
            arithmetic_mean_throw_in_count=0,
        )
        session.add(duplicate)
        with pytest.raises(IntegrityError):
            session.commit()


def test_authenticated_completion_is_saved_once_and_guest_completion_is_not(
    database: Database,
) -> None:
    user_id = add_user(database)
    history = MatchHistoryService(database)

    def one_move_human_win() -> GameState:
        return GameState(
            seat_one_hand=(card(Rank.ACE),),
            seat_two_hand=(card(Rank.SIX),),
            draw_pile=(),
            discard_pile=(),
            current_attacker=Seat.ONE,
        )

    authenticated = GameSessionService(
        game_factory=one_move_human_win,
        completion_recorder=history.record_completed_match,
    )
    session = authenticated.create_game(user_id=user_id)
    finished = authenticated.play_human_action(
        session.game_id,
        HumanActionType.INITIAL_ATTACK,
        (card(Rank.ACE),),
    )
    assert finished.state.phase is GamePhase.COMPLETE
    assert finished.completion_persisted
    assert authenticated.get_game(session.game_id).completion_persisted

    guest = GameSessionService(
        game_factory=one_move_human_win,
        completion_recorder=history.record_completed_match,
    )
    guest_session = guest.create_game()
    guest_finished = guest.play_human_action(
        guest_session.game_id,
        HumanActionType.INITIAL_ATTACK,
        (card(Rank.ACE),),
    )
    assert not guest_finished.completion_persisted

    with database.session() as database_session:
        assert database_session.scalar(select(func.count()).select_from(CompletedMatch)) == 1


def test_rejected_action_does_not_increment_session_summary() -> None:
    state = GameState(
        seat_one_hand=(card(Rank.NINE), card(Rank.SEVEN)),
        seat_two_hand=(card(Rank.ACE), card(Rank.KING)),
        draw_pile=(),
        discard_pile=(),
        current_attacker=Seat.ONE,
    )
    service = GameSessionService(game_factory=lambda: state)
    created = service.create_game()

    with pytest.raises(ValueError):
        service.play_human_action(
            created.game_id,
            HumanActionType.INITIAL_ATTACK,
            (card(Rank.NINE), card(Rank.SEVEN)),
        )

    current = service.get_game(created.game_id)
    assert current.human_action_count == 0
    assert current.human_transfer_count == 0
    assert current.human_take_count == 0
    assert current.human_throw_in_count == 0


def test_session_tracks_only_accepted_transfer_take_and_mean_throw_in_actions() -> None:
    king = card(Rank.KING)
    transfer_state = start_game_bout(
        GameState(
            seat_one_hand=(card(Rank.NINE), card(Rank.NINE, Suit.DIAMONDS), card(Rank.SIX)),
            seat_two_hand=(king, card(Rank.ACE), card(Rank.SEVEN), card(Rank.EIGHT)),
            draw_pile=(),
            discard_pile=(),
            current_attacker=Seat.TWO,
        )
    )
    transfer_state = play_game_initial_attack(transfer_state, Seat.TWO, (king,))
    transfer_service = GameSessionService(game_factory=lambda: transfer_state)
    transfer_session = transfer_service.create_game()
    transferred = transfer_service.play_human_action(
        transfer_session.game_id,
        HumanActionType.TRANSFER,
        (card(Rank.NINE), card(Rank.NINE, Suit.DIAMONDS)),
    )
    assert transferred.human_action_count == 1
    assert transferred.human_transfer_count == 1
    assert transferred.max_transfer_target == 36

    extended_state = start_game_bout(
        GameState(
            seat_one_hand=(
                card(Rank.SEVEN),
                card(Rank.SEVEN, Suit.DIAMONDS),
                card(Rank.SIX),
            ),
            seat_two_hand=(
                card(Rank.SEVEN, Suit.HEARTS),
                card(Rank.EIGHT),
                card(Rank.NINE),
                card(Rank.TEN),
                card(Rank.JACK),
            ),
            draw_pile=(),
            discard_pile=(),
            current_attacker=Seat.TWO,
        )
    )
    extended_state = play_game_initial_attack(
        extended_state,
        Seat.TWO,
        (card(Rank.SEVEN, Suit.HEARTS),),
    )
    extended_service = GameSessionService(game_factory=lambda: extended_state)
    extended_session = extended_service.create_game()
    extended = extended_service.play_human_action(
        extended_session.game_id,
        HumanActionType.TRANSFER,
        (card(Rank.SEVEN), card(Rank.SEVEN, Suit.DIAMONDS)),
    )
    assert extended.max_transfer_target == 21

    jack = card(Rank.JACK)
    queen = card(Rank.QUEEN)
    mean_state = start_game_bout(
        GameState(
            seat_one_hand=(jack, queen, card(Rank.SIX)),
            seat_two_hand=(king, card(Rank.ACE), card(Rank.SEVEN)),
            draw_pile=(),
            discard_pile=(),
            current_attacker=Seat.ONE,
        )
    )
    mean_state = play_game_initial_attack(mean_state, Seat.ONE, (jack,))
    mean_state = play_game_defense(mean_state, Seat.TWO, (king,))
    mean_service = GameSessionService(game_factory=lambda: mean_state)
    mean_session = mean_service.create_game()
    thrown = mean_service.play_human_action(
        mean_session.game_id,
        HumanActionType.THROW_IN,
        (queen,),
    )
    assert thrown.human_action_count == 1
    assert thrown.human_throw_in_count == 1
    assert thrown.arithmetic_mean_throw_in_count == 1

    take_state = GameState(
        seat_one_hand=(card(Rank.SIX), card(Rank.SEVEN)),
        seat_two_hand=(card(Rank.ACE), card(Rank.KING)),
        draw_pile=(),
        discard_pile=(),
        current_attacker=Seat.TWO,
    )
    take_service = GameSessionService(game_factory=lambda: take_state)
    take_session = take_service.create_game()
    taken = take_service.play_human_action(take_session.game_id, HumanActionType.TAKE)
    assert taken.human_action_count == 1
    assert taken.human_take_count == 1


def test_failed_completion_write_keeps_result_and_get_retries_without_replaying() -> None:
    attempts = 0

    def recorder(_session: GameSession) -> None:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("database unavailable")

    state = GameState(
        seat_one_hand=(card(Rank.ACE),),
        seat_two_hand=(card(Rank.SIX),),
        draw_pile=(),
        discard_pile=(),
        current_attacker=Seat.ONE,
    )
    service = GameSessionService(game_factory=lambda: state, completion_recorder=recorder)
    created = service.create_game(user_id=uuid4())

    with pytest.raises(RuntimeError, match="database unavailable"):
        service.play_human_action(
            created.game_id,
            HumanActionType.INITIAL_ATTACK,
            (card(Rank.ACE),),
        )

    recovered = service.get_game(created.game_id)
    assert recovered.state.phase is GamePhase.COMPLETE
    assert recovered.completion_persisted
    assert attempts == 2


def test_game_session_original_account_association_survives_login_and_logout(
    database: Database,
) -> None:
    history = MatchHistoryService(database)

    def one_move_human_win() -> GameState:
        return GameState(
            seat_one_hand=(card(Rank.ACE),),
            seat_two_hand=(card(Rank.SIX),),
            draw_pile=(),
            discard_pile=(),
            current_attacker=Seat.ONE,
        )

    game_service = GameSessionService(
        game_factory=one_move_human_win,
        completion_recorder=history.record_completed_match,
    )
    settings = Settings(database_url="sqlite://", csrf_trusted_origins=(ORIGIN,))
    client = TestClient(create_app(game_service, database=database, settings=settings))

    guest_game_id = client.post("/api/games").json()["game_id"]
    registration = client.post(
        "/api/auth/register",
        headers={"Origin": ORIGIN},
        json={
            "email": "association@example.com",
            "display_name": "Ассоциация",
            "password": "correct horse battery staple",
        },
    )
    user_id = UUID(registration.json()["id"])
    authenticated_game_id = client.post("/api/games").json()["game_id"]
    assert client.post("/api/auth/logout", headers={"Origin": ORIGIN}).status_code == 204

    guest_result = client.post(
        f"/api/games/{guest_game_id}/actions",
        json={"action": "INITIAL_ATTACK", "cards": ["AC"]},
    )
    authenticated_result = client.post(
        f"/api/games/{authenticated_game_id}/actions",
        json={"action": "INITIAL_ATTACK", "cards": ["AC"]},
    )

    assert guest_result.json()["account_associated"] is False
    assert guest_result.json()["result_saved"] is False
    assert authenticated_result.json()["account_associated"] is True
    assert authenticated_result.json()["result_saved"] is True
    with database.session() as session:
        rows = list(session.scalars(select(CompletedMatch)))
        assert len(rows) == 1
        assert rows[0].user_id == user_id
        assert rows[0].game_session_id == authenticated_game_id


def add_match(
    database: Database,
    user_id: UUID,
    outcome: MatchOutcome,
    completed_at: datetime,
    *,
    game_id: str,
    transfers: int = 0,
    takes: int = 0,
    throw_ins: int = 0,
    transfer_target: int = 0,
    means: int = 0,
    opponent_type: str = "BOT",
    opponent_display_name: str | None = None,
) -> None:
    with database.session() as session:
        session.add(
            CompletedMatch(
                user_id=user_id,
                game_session_id=game_id,
                opponent_type=opponent_type,
                pvp_match_id=game_id if opponent_type == "PVP" else None,
                opponent_display_name=opponent_display_name,
                outcome=outcome.value,
                started_at=completed_at - timedelta(minutes=4),
                completed_at=completed_at,
                duration_seconds=240,
                user_seat="one",
                initial_attacker="one",
                final_human_card_count=0 if outcome is not MatchOutcome.LOSS else 2,
                final_bot_card_count=0 if outcome is MatchOutcome.DRAW else 3,
                human_action_count=10,
                human_transfer_count=transfers,
                human_take_count=takes,
                human_throw_in_count=throw_ins,
                max_transfer_target=transfer_target,
                arithmetic_mean_throw_in_count=means,
            )
        )
        session.commit()


def test_statistics_derive_rates_streaks_counters_and_isolate_users(database: Database) -> None:
    user_id = add_user(database)
    other_id = add_user(database, email="other@example.com")
    service = MatchHistoryService(database)
    start = datetime(2026, 8, 20, tzinfo=UTC)
    for index, outcome in enumerate(
        [
            MatchOutcome.WIN,
            MatchOutcome.WIN,
            MatchOutcome.LOSS,
            MatchOutcome.WIN,
            MatchOutcome.DRAW,
            MatchOutcome.WIN,
        ]
    ):
        add_match(
            database,
            user_id,
            outcome,
            start + timedelta(days=index),
            game_id=f"game-{index}",
            transfers=index,
            takes=1,
            throw_ins=2,
            transfer_target=index * 18,
            means=1,
        )
    add_match(database, other_id, MatchOutcome.LOSS, start, game_id="other")

    stats = service.get_statistics(user_id)

    assert stats.games_played == 6
    assert (stats.wins, stats.losses, stats.draws) == (4, 1, 1)
    assert stats.win_rate == 66.67
    assert stats.current_win_streak == 1
    assert stats.best_win_streak == 2
    assert stats.total_transfers == 15
    assert stats.total_takes == 6
    assert stats.total_throw_ins == 12
    assert stats.highest_transfer_target == 90
    assert stats.arithmetic_mean_throw_ins == 6
    assert (stats.bot_games, stats.bot_wins) == (6, 4)
    assert (stats.pvp_games, stats.pvp_wins) == (0, 0)
    assert MatchHistoryService(database).get_statistics(uuid4()).games_played == 0


def test_stats_and_match_history_endpoints_require_auth_and_paginate_newest_first(
    database: Database,
) -> None:
    settings = Settings(database_url="sqlite://", csrf_trusted_origins=(ORIGIN,))
    client = TestClient(create_app(database=database, settings=settings))
    assert client.get("/api/stats").status_code == 401
    assert client.get("/api/matches").status_code == 401
    registration = client.post(
        "/api/auth/register",
        headers={"Origin": ORIGIN},
        json={
            "email": "history@example.com",
            "display_name": "История",
            "password": "correct horse battery staple",
        },
    )
    user_id = UUID(registration.json()["id"])
    other_id = add_user(database, email="isolated@example.com")
    start = datetime(2026, 8, 20, tzinfo=UTC)
    add_match(database, user_id, MatchOutcome.WIN, start, game_id="old")
    add_match(
        database,
        user_id,
        MatchOutcome.LOSS,
        start + timedelta(days=1),
        game_id="new",
        opponent_type="PVP",
        opponent_display_name="Bob",
    )
    add_match(database, other_id, MatchOutcome.DRAW, start + timedelta(days=2), game_id="private")

    stats = client.get("/api/stats")
    history = client.get("/api/matches?limit=1&offset=0")
    second_page = client.get("/api/matches?limit=1&offset=1")

    assert stats.status_code == 200
    assert stats.json()["games_played"] == 2
    assert stats.json()["wins"] == 1
    assert stats.json()["losses"] == 1
    assert stats.json()["bot_games"] == 1
    assert stats.json()["pvp_games"] == 1
    assert history.status_code == 200
    assert history.json()["total"] == 2
    assert history.json()["items"][0]["outcome"] == "LOSS"
    assert history.json()["items"][0]["opponent_type"] == "PVP"
    assert history.json()["items"][0]["opponent_display_name"] == "Bob"
    assert second_page.json()["items"][0]["outcome"] == "WIN"
    assert client.get("/api/matches?opponent_type=PVP").json()["total"] == 1
    assert client.get("/api/matches?opponent_type=BOT").json()["total"] == 1
    serialized = history.text
    assert "user_id" not in serialized
    assert "game_session_id" not in serialized
    assert "private" not in serialized
