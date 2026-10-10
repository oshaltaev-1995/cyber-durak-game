from __future__ import annotations

import itertools
import json
import random

import pytest
from fastapi.testclient import TestClient

from kiba_api.api.pvp_serialization import serialize_pvp_state, serialize_room_status
from kiba_api.config import Settings
from kiba_api.game import (
    Card,
    DeckConfig,
    DeckProfile,
    GamePhase,
    GameState,
    Rank,
    Seat,
    Suit,
    choose_bot_action,
    create_new_game,
    play_bot_turn,
)
from kiba_api.main import create_app
from kiba_api.pvp import PvPError, PvPErrorCode, PvPRoomPhase, PvPRoomService
from kiba_api.sessions import HumanActionType, acting_seat

ORIGIN = "http://testserver"


def _service(seed: int = 1, **kwargs) -> PvPRoomService:
    sequence = itertools.count(seed)
    kwargs.setdefault("name_rng", random.Random(seed))
    return PvPRoomService(
        multiplayer_game_factory=lambda count: create_new_game(
            random.Random(next(sequence)), player_count=count
        ),
        configured_game_factory=lambda count, config: create_new_game(
            random.Random(next(sequence)), player_count=count, deck_config=config
        ),
        **kwargs,
    )


def _fill_mixed(service: PvPRoomService, capacity: int, human_players: int):
    room, creator = service.create_room("Human A", capacity=capacity, human_players=human_players)
    humans = [creator]
    for index in range(1, human_players):
        room, participant = service.join_room(room.invite_code, f"Human {index + 1}")
        humans.append(participant)
    return room, humans


def _complete(service: PvPRoomService, room, humans):
    human_by_seat = {value.seat: value for value in humans}
    for _ in range(5_000):
        if room.phase is PvPRoomPhase.COMPLETE:
            return room
        assert room.state is not None
        actor = acting_seat(room.state)
        assert actor in human_by_seat
        action = choose_bot_action(room.state, actor)
        room = service.play_action(
            room.invite_code,
            human_by_seat[actor].reconnect_token,
            HumanActionType(action.action_type.name),
            action.cards,
            expected_version=room.version,
        )
    pytest.fail("mixed room did not complete inside the transition bound")


@pytest.mark.parametrize(
    ("capacity", "human_players", "human_seats", "bot_seats"),
    [
        (3, 2, (Seat.ONE, Seat.TWO), (Seat.THREE,)),
        (4, 2, (Seat.ONE, Seat.TWO), (Seat.THREE, Seat.FOUR)),
        (4, 3, (Seat.ONE, Seat.TWO, Seat.THREE), (Seat.FOUR,)),
    ],
)
def test_mixed_room_reserves_bot_seats_and_waits_only_for_humans(
    capacity: int,
    human_players: int,
    human_seats: tuple[Seat, ...],
    bot_seats: tuple[Seat, ...],
) -> None:
    service = _service(capacity)
    waiting, creator = service.create_room(
        "Creator", capacity=capacity, human_players=human_players
    )

    assert waiting.phase is PvPRoomPhase.WAITING_FOR_OPPONENT
    assert len(waiting.human_participants) == 1
    assert tuple(value.seat for value in waiting.bot_participants) == bot_seats
    assert all(value.connected for value in waiting.bot_participants)
    assert all(value.connection_id is None for value in waiting.bot_participants)
    assert all(value.reconnect_token is None for value in waiting.bot_participants)
    assert serialize_room_status(waiting).human_joined_count == 1
    assert serialize_room_status(waiting).joined_count == 1

    room = waiting
    humans = [creator]
    for index in range(1, human_players):
        room, participant = service.join_room(room.invite_code, f"Human {index + 1}")
        humans.append(participant)
        if index < human_players - 1:
            assert room.phase is PvPRoomPhase.WAITING_FOR_OPPONENT

    assert room.phase in {PvPRoomPhase.GAME_ACTIVE, PvPRoomPhase.COMPLETE}
    assert tuple(value.seat for value in room.human_participants) == human_seats
    assert tuple(value.seat for value in room.bot_participants) == bot_seats
    assert len(room.participants) == capacity
    assert room.state is not None and room.state.seat_order == tuple(human_seats + bot_seats)

    with pytest.raises(PvPError) as full:
        service.join_room(room.invite_code, "Too late")
    assert full.value.code is PvPErrorCode.ROOM_FULL


@pytest.mark.parametrize("capacity,human_players", [(3, 1), (4, 1), (3, 4)])
def test_private_mixed_room_requires_two_humans(capacity: int, human_players: int) -> None:
    with pytest.raises(PvPError) as invalid:
        _service().create_room("Creator", capacity=capacity, human_players=human_players)
    assert invalid.value.code is PvPErrorCode.INVALID_CAPACITY


def test_bot_names_are_unique_and_rerolled_for_late_human_collision() -> None:
    service = _service(
        name_rng=random.Random(4),
        bot_name_pool=("Milo", "Nika", "Zara", "Timo"),
    )
    waiting, _creator = service.create_room("Milo", capacity=4, human_players=2)
    initial_names = tuple(value.display_name for value in waiting.bot_participants)
    assert all(name.casefold() != "milo" for name in initial_names)

    room, _joiner = service.join_room(waiting.invite_code, initial_names[0].swapcase())
    final_names = tuple(value.display_name for value in room.bot_participants)
    all_names = [value.display_name.casefold() for value in room.participants]

    assert len(all_names) == len(set(all_names))
    assert initial_names[0] not in final_names
    assert tuple(value.participant_id for value in room.bot_participants) == tuple(
        value.participant_id for value in waiting.bot_participants
    )


def test_bot_started_bout_advances_to_human_without_bot_socket() -> None:
    def factory(_count: int) -> GameState:
        return GameState(
            hands=(
                (Card(Rank.ACE, Suit.CLUBS), Card(Rank.KING, Suit.HEARTS)),
                (Card(Rank.QUEEN, Suit.CLUBS), Card(Rank.JACK, Suit.HEARTS)),
                (Card(Rank.SIX, Suit.CLUBS), Card(Rank.SEVEN, Suit.HEARTS)),
            ),
            current_attacker=Seat.THREE,
        )

    service = PvPRoomService(
        multiplayer_game_factory=factory,
        name_rng=random.Random(1),
    )
    room, humans = _fill_mixed(service, 3, 2)

    assert room.state is not None
    assert acting_seat(room.state) is Seat.ONE
    assert [event.actor_seat for event in room.recent_events] == [Seat.THREE]
    assert room.action_summary(Seat.THREE).action_count == 1
    assert serialize_pvp_state(room, humans[0]).recent_events[0].actor_seat == Seat.THREE.value


def test_human_action_runs_bot_defender_once_and_keeps_other_hands_private() -> None:
    attack = Card(Rank.SIX, Suit.CLUBS)

    def factory(_count: int) -> GameState:
        return GameState(
            hands=(
                (Card(Rank.ACE, Suit.DIAMONDS), Card(Rank.KING, Suit.SPADES)),
                (attack, Card(Rank.QUEEN, Suit.HEARTS)),
                (Card(Rank.SEVEN, Suit.CLUBS), Card(Rank.JACK, Suit.DIAMONDS)),
            ),
            current_attacker=Seat.TWO,
        )

    service = PvPRoomService(
        multiplayer_game_factory=factory,
        name_rng=random.Random(2),
    )
    room, humans = _fill_mixed(service, 3, 2)
    room = service.play_action(
        room.invite_code,
        humans[1].reconnect_token,
        HumanActionType.INITIAL_ATTACK,
        (attack,),
        expected_version=room.version,
    )

    assert room.version == 1
    assert len(room.recent_events) >= 1
    assert all(event.actor_seat is Seat.THREE for event in room.recent_events)
    assert room.recent_events[0].type.value == "BOT_DEFEND"
    assert room.action_summary(Seat.THREE).action_count == len(room.recent_events)
    assert room.state is not None and acting_seat(room.state) in {Seat.ONE, Seat.TWO}
    projection = serialize_pvp_state(room, humans[0]).model_dump(mode="json")
    encoded = json.dumps(projection)
    assert projection["players"][2]["is_bot"] is True
    assert projection["players"][2]["hand_count"] == len(room.state.hand(Seat.THREE))
    for hidden in (*room.state.hand(Seat.TWO), *room.state.hand(Seat.THREE)):
        assert hidden.physical_id not in encoded
    assert "BotDecisionContext" not in encoded


def test_bot_credentials_and_votes_do_not_exist() -> None:
    service = _service()
    room, _humans = _fill_mixed(service, 4, 2)
    bot = room.bot_participants[0]

    with pytest.raises(PvPError) as authentication:
        service.authenticate(room.invite_code, bot.participant_id)
    assert authentication.value.code is PvPErrorCode.INVALID_CREDENTIAL


def test_mixed_human_reconnect_preserves_state_and_does_not_replay_bot_events() -> None:
    service = _service(40)
    room, humans = _fill_mixed(service, 4, 2)
    registration = service.connect(room.invite_code, humans[0].reconnect_token, "original")
    state_before = registration.room.state
    names_before = tuple(value.display_name for value in room.bot_participants)

    service.disconnect(room.invite_code, humans[0].participant_id, "original")
    reconnected = service.connect(room.invite_code, humans[0].reconnect_token, "replacement")

    assert reconnected.participant.seat is Seat.ONE
    assert reconnected.room.state is state_before
    assert tuple(value.display_name for value in reconnected.room.bot_participants) == names_before
    assert reconnected.room.recent_events == ()


def test_active_mixed_human_exit_closes_neutrally_without_bot_continuation() -> None:
    service = _service(41)
    room, humans = _fill_mixed(service, 4, 2)
    service.connect(room.invite_code, humans[0].reconnect_token, "human-a")
    before = room.state

    closed = service.leave_room(room.invite_code, humans[0].reconnect_token, "human-a")

    assert closed.phase is PvPRoomPhase.CLOSED
    assert closed.state is before
    assert closed.completion_results == ()
    assert closed.recent_events == ()


def test_all_bot_remainder_completes_after_both_humans_finish() -> None:
    all_bot_remainder_seen = False

    def tracking_bot_turn(state: GameState, seat: Seat) -> GameState:
        nonlocal all_bot_remainder_seen
        if {Seat.ONE, Seat.TWO}.issubset(state.finished_seats):
            all_bot_remainder_seen = True
        return play_bot_turn(state, seat)

    service = _service(15, bot_turn=tracking_bot_turn)
    room, humans = _fill_mixed(service, 4, 2)
    completed = _complete(service, room, humans)

    assert all_bot_remainder_seen
    assert completed.phase is PvPRoomPhase.COMPLETE
    assert completed.state is not None
    assert completed.state.finish_groups[:2] == ((Seat.ONE,), (Seat.TWO,))
    assert {seat for group in completed.state.finish_groups for seat in group} == set(
        completed.state.seat_order
    )


@pytest.mark.parametrize("human_players", [2, 3])
def test_mixed_rematch_needs_humans_only_and_preserves_participants(
    human_players: int,
) -> None:
    service = _service(200 + human_players)
    room, humans = _fill_mixed(service, 4, human_players)
    completed = _complete(service, room, humans)
    old_match = completed.match_id
    old_participants = tuple(
        (value.participant_id, value.seat, value.display_name, value.reconnect_token)
        for value in completed.participants
    )

    requested = service.request_rematch(
        completed.invite_code,
        humans[0].reconnect_token,
        match_id=old_match or "",
        expected_version=completed.version,
    )
    assert requested.phase is PvPRoomPhase.COMPLETE
    assert serialize_pvp_state(requested, humans[0]).rematch_total_count == human_players

    pending = requested
    for human in humans[1:]:
        pending = service.request_rematch(
            completed.invite_code,
            human.reconnect_token,
            match_id=old_match or "",
            expected_version=pending.version,
        )
    restarted = pending
    assert restarted.phase in {PvPRoomPhase.GAME_ACTIVE, PvPRoomPhase.COMPLETE}
    assert restarted.match_id != old_match
    assert (
        tuple(
            (value.participant_id, value.seat, value.display_name, value.reconnect_token)
            for value in restarted.participants
        )
        == old_participants
    )


@pytest.mark.parametrize(
    ("capacity", "human_players", "deck_config"),
    [
        (3, 2, DeckConfig(DeckProfile.EXTENDED, 1)),
        (4, 2, DeckConfig(DeckProfile.EXTENDED, 2)),
        (4, 3, DeckConfig(DeckProfile.CLASSIC, 2)),
    ],
)
def test_mixed_room_deterministic_soak_completes_without_persistence(
    capacity: int,
    human_players: int,
    deck_config: DeckConfig,
) -> None:
    persisted: list[str] = []
    for seed in range(50):
        service = _service(
            10_000 + seed,
            completion_recorder=lambda room: persisted.append(room.room_id) or (),
        )
        room, creator = service.create_room(
            "Human A",
            capacity=capacity,
            human_players=human_players,
            deck_config=deck_config,
        )
        humans = [creator]
        for index in range(1, human_players):
            room, participant = service.join_room(room.invite_code, f"Human {index + 1}")
            humans.append(participant)
        completed = _complete(service, room, humans)
        assert completed.state is not None
        assert completed.state.phase is GamePhase.COMPLETE
        assert sum(len(group) for group in completed.state.finish_groups) == capacity
        total_cards = sum(len(completed.state.hand(seat)) for seat in completed.state.seat_order)
        total_cards += len(completed.state.draw_pile) + len(completed.state.discard_pile)
        if completed.state.active_bout is not None:
            total_cards += len(completed.state.active_bout.table_cards)
        assert total_cards == deck_config.card_count
    assert persisted == []


def test_mixed_feature_gate_and_other_gates_compose() -> None:
    base = dict(database_url="sqlite://", csrf_trusted_origins=(ORIGIN,))
    cases = (
        (Settings(**base, multiplayer_3_4_enabled=True), 409),
        (Settings(**base, mixed_rooms_enabled=True), 409),
        (
            Settings(
                **base,
                multiplayer_3_4_enabled=True,
                mixed_rooms_enabled=True,
            ),
            201,
        ),
    )
    for settings, expected in cases:
        with TestClient(create_app(settings=settings)) as client:
            response = client.post(
                "/api/pvp/rooms",
                json={"nickname": "Creator", "capacity": 3, "human_players": 2},
            )
            assert response.status_code == expected
            assert client.get("/api/capabilities").json()["mixed_rooms_enabled"] is (
                settings.mixed_rooms_enabled
            )

    settings = Settings(
        **base,
        multiplayer_3_4_enabled=True,
        mixed_rooms_enabled=True,
        deck_variants_enabled=False,
    )
    with TestClient(create_app(settings=settings)) as client:
        blocked = client.post(
            "/api/pvp/rooms",
            json={
                "nickname": "Creator",
                "capacity": 4,
                "human_players": 2,
                "deck_profile": "extended",
            },
        )
        all_human = client.post("/api/pvp/rooms", json={"nickname": "Creator", "capacity": 4})
    assert blocked.status_code == 409
    assert all_human.status_code == 201


def test_omitted_human_players_keeps_existing_all_human_contract() -> None:
    service = _service()
    room, _creator = service.create_room("Creator", capacity=4)
    assert room.human_players == 4
    assert room.bot_count == 0
    assert room.bot_participants == ()


def test_mixed_room_environment_gate_defaults_off_and_parses_true(monkeypatch) -> None:
    assert Settings().mixed_rooms_enabled is False
    monkeypatch.setenv("KIBA_MIXED_ROOMS_ENABLED", "true")
    assert Settings.from_env().mixed_rooms_enabled is True
