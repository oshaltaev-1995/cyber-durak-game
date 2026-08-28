from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select

from kiba_api.api.pvp_serialization import serialize_pvp_state
from kiba_api.game import Card, GameOutcome, GamePhase, GameResult, GameState, Rank, Seat, Suit
from kiba_api.persistence import (
    Base,
    CompletedMatch,
    CosmeticService,
    Database,
    MatchHistoryService,
    ProgressionService,
    User,
    XPLedgerEntry,
)
from kiba_api.pvp import (
    PvPParticipant,
    PvPParticipantCompletion,
    PvPRoom,
    PvPRoomPhase,
    PvPSeatActionSummary,
)
from kiba_api.sessions import ActionCounters


@pytest.fixture
def database() -> Database:
    value = Database("sqlite://")
    Base.metadata.create_all(value.engine)
    yield value
    value.dispose()


def add_user(database: Database, display_name: str) -> UUID:
    user_id = uuid4()
    email = f"{display_name.lower()}@example.com"
    with database.session() as session:
        session.add(
            User(
                id=user_id,
                email=email,
                normalized_email=email,
                display_name=display_name,
                password_hash="test",
                is_active=True,
            )
        )
        session.commit()
    return user_id


def participant(seat: Seat, name: str, user_id: UUID | None) -> PvPParticipant:
    return PvPParticipant(
        participant_id=f"participant-{seat.value}",
        seat=seat,
        display_name=name,
        user_id=user_id,
        reconnect_token=f"secret-{seat.value}",
    )


def completed_room(
    one: PvPParticipant,
    two: PvPParticipant,
    *,
    outcome: GameOutcome = GameOutcome.WIN,
    winner: Seat | None = Seat.ONE,
) -> PvPRoom:
    six = Card(Rank.SIX, Suit.CLUBS)
    hands = ((), (six,)) if winner is Seat.ONE else ((six,), ())
    if outcome is GameOutcome.DRAW:
        hands = ((), ())
        winner = None
    state = GameState(
        seat_one_hand=hands[0],
        seat_two_hand=hands[1],
        draw_pile=(),
        discard_pile=(),
        current_attacker=None,
        phase=GamePhase.COMPLETE,
        result=GameResult(outcome, winner),
    )
    started = datetime(2026, 8, 28, 10, tzinfo=UTC)
    return PvPRoom(
        room_id="shared-pvp-match",
        invite_code="INVITE",
        phase=PvPRoomPhase.COMPLETE,
        participants=(one, two),
        state=state,
        last_bout=None,
        game_started_at=started,
        initial_attacker=Seat.TWO,
        action_summaries=(
            PvPSeatActionSummary(
                Seat.ONE,
                ActionCounters(
                    action_count=9,
                    transfer_count=2,
                    throw_in_count=1,
                    max_transfer_target=72,
                    arithmetic_mean_throw_in_count=1,
                ),
            ),
            PvPSeatActionSummary(Seat.TWO, ActionCounters(action_count=7, take_count=1)),
        ),
        completion_results=(),
        version=14,
        created_at=started - timedelta(minutes=1),
        updated_at=started + timedelta(minutes=4),
    )


def test_authenticated_pvp_perspectives_are_atomic_idempotent_and_snapshotted(
    database: Database,
) -> None:
    alice_id = add_user(database, "Alice")
    bob_id = add_user(database, "Bob")
    room = completed_room(
        participant(Seat.ONE, "Alice", alice_id),
        participant(Seat.TWO, "Bob", bob_id),
    )
    service = MatchHistoryService(database)

    first = service.record_completed_pvp_room(room)
    second = service.record_completed_pvp_room(room)
    with database.session() as session:
        bob_user = session.get(User, bob_id)
        assert bob_user is not None
        bob_user.display_name = "Renamed Bob"
        session.commit()

    assert set(first) == {"participant-one", "participant-two"}
    assert first["participant-one"].id == second["participant-one"].id
    with database.session() as session:
        rows = list(session.scalars(select(CompletedMatch).order_by(CompletedMatch.user_seat)))
        assert len(rows) == 2
        alice, bob = rows
        assert alice.pvp_match_id == bob.pvp_match_id == room.room_id
        assert (alice.outcome, bob.outcome) == ("WIN", "LOSS")
        assert (alice.opponent_display_name, bob.opponent_display_name) == ("Bob", "Alice")
        assert (alice.opponent_user_id, bob.opponent_user_id) == (bob_id, alice_id)
        assert (alice.human_action_count, bob.human_action_count) == (9, 7)
        assert (alice.human_transfer_count, bob.human_transfer_count) == (2, 0)
        assert alice.max_transfer_target == 72
        assert alice.arithmetic_mean_throw_in_count == 1


@pytest.mark.parametrize(("authenticated_seat", "expected_rows"), [(Seat.ONE, 1), (None, 0)])
def test_guest_pvp_is_not_persisted(
    database: Database,
    authenticated_seat: Seat | None,
    expected_rows: int,
) -> None:
    user_id = add_user(database, "Alice") if authenticated_seat is not None else None
    room = completed_room(
        participant(Seat.ONE, "Alice", user_id if authenticated_seat is Seat.ONE else None),
        participant(Seat.TWO, "Guest", None),
    )

    MatchHistoryService(database).record_completed_pvp_room(room)

    with database.session() as session:
        assert session.scalar(select(func.count()).select_from(CompletedMatch)) == expected_rows


def test_pvp_draw_and_progression_are_exactly_once(database: Database) -> None:
    alice_id = add_user(database, "Alice")
    bob_id = add_user(database, "Bob")
    room = completed_room(
        participant(Seat.ONE, "Alice", alice_id),
        participant(Seat.TWO, "Bob", bob_id),
        outcome=GameOutcome.DRAW,
        winner=None,
    )
    history = MatchHistoryService(database)
    progression = ProgressionService(database)
    rows = history.record_completed_pvp_room(room)

    for participant_id, user_id in (("participant-one", alice_id), ("participant-two", bob_id)):
        first = progression.synchronize_for_match(user_id, rows[participant_id].id)
        second = progression.synchronize_for_match(user_id, rows[participant_id].id)
        assert first.base_xp == 50
        assert second.total_awarded_xp == first.total_awarded_xp
        if participant_id == "participant-one":
            assert {achievement.code.value for achievement in first.new_achievements} >= {
                "SNOWBALL_36",
                "AVALANCHE_72",
                "ARITHMETIC_MEAN",
            }
    cosmetic_sync = CosmeticService(database, progression).synchronize(alice_id)
    assert {definition.code.value for definition in cosmetic_sync.new_unlocks} >= {
        "SNOWBALL_BACK",
        "AVALANCHE_BACK",
        "MATHEMATICIAN_TABLE",
    }

    history.record_completed_pvp_room(room)
    with database.session() as session:
        assert session.scalar(select(func.count()).select_from(CompletedMatch)) == 2
        assert session.scalar(select(func.count()).select_from(XPLedgerEntry)) == 7


def test_statistics_combine_bot_and_pvp_with_mode_splits(database: Database) -> None:
    alice_id = add_user(database, "Alice")
    bob_id = add_user(database, "Bob")
    history = MatchHistoryService(database)
    history.record_completed_pvp_room(
        completed_room(
            participant(Seat.ONE, "Alice", alice_id),
            participant(Seat.TWO, "Bob", bob_id),
        )
    )
    with database.session() as session:
        session.add(
            CompletedMatch(
                user_id=alice_id,
                game_session_id="bot-match",
                opponent_type="BOT",
                outcome="LOSS",
                started_at=datetime(2026, 8, 28, 8, tzinfo=UTC),
                completed_at=datetime(2026, 8, 28, 9, tzinfo=UTC),
                duration_seconds=3600,
                user_seat="one",
                initial_attacker="one",
                final_human_card_count=2,
                final_bot_card_count=0,
                human_action_count=3,
                human_transfer_count=0,
                human_take_count=1,
                human_throw_in_count=0,
                max_transfer_target=0,
                arithmetic_mean_throw_in_count=0,
            )
        )
        session.commit()
    pvp_stats = history.get_statistics(alice_id)

    assert (pvp_stats.games_played, pvp_stats.wins, pvp_stats.losses) == (2, 1, 1)
    assert (pvp_stats.bot_games, pvp_stats.bot_wins) == (1, 0)
    assert (pvp_stats.pvp_games, pvp_stats.pvp_wins) == (1, 1)
    assert (pvp_stats.current_win_streak, pvp_stats.best_win_streak) == (1, 1)
    assert len(history.list_matches(alice_id, limit=10, offset=0)) == 2


def test_pvp_complete_payload_is_participant_private(database: Database) -> None:
    alice_id = add_user(database, "Alice")
    bob_id = add_user(database, "Bob")
    alice = participant(Seat.ONE, "Alice", alice_id)
    bob = participant(Seat.TWO, "Bob", bob_id)
    room = completed_room(alice, bob)
    history = MatchHistoryService(database)
    progression = ProgressionService(database)
    matches = history.record_completed_pvp_room(room)
    alice_award = progression.synchronize_for_match(alice_id, matches[alice.participant_id].id)
    bob_award = progression.synchronize_for_match(bob_id, matches[bob.participant_id].id)
    room = replace(
        room,
        completion_results=(
            PvPParticipantCompletion(alice.participant_id, True, alice_award),
            PvPParticipantCompletion(bob.participant_id, True, bob_award),
        ),
    )

    alice_payload = serialize_pvp_state(room, alice).model_dump()
    bob_payload = serialize_pvp_state(room, bob).model_dump()

    assert alice_payload["result_saved"] is True
    assert bob_payload["result_saved"] is True
    assert alice_payload["progression_award"]["base_xp"] == 100
    assert bob_payload["progression_award"]["base_xp"] == 25
    assert alice_payload["progression_award"] != bob_payload["progression_award"]
