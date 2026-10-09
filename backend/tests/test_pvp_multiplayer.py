from __future__ import annotations

import json
import random
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from kiba_api.api.pvp_serialization import serialize_pvp_state
from kiba_api.config import Settings
from kiba_api.game import (
    BoutPhase,
    Card,
    GamePhase,
    GameState,
    Rank,
    Seat,
    Suit,
    choose_bot_action,
    create_36_card_deck,
    create_new_game,
)
from kiba_api.main import create_app
from kiba_api.persistence import Base, Database
from kiba_api.pvp import (
    PvPActionError,
    PvPError,
    PvPErrorCode,
    PvPRoomPhase,
    PvPRoomService,
    RoomTTLPolicy,
)
from kiba_api.sessions import HumanActionType, acting_seat

ORIGIN = "http://testserver"


def card(rank: Rank, suit: Suit = Suit.CLUBS) -> Card:
    return Card(rank, suit)


def multiplayer_service(*, game_factory=None, completion_recorder=None) -> PvPRoomService:
    return PvPRoomService(
        game_factory=lambda: create_new_game(random.Random(2)),
        multiplayer_game_factory=(
            game_factory
            if game_factory is not None
            else lambda count: create_new_game(random.Random(100 + count), player_count=count)
        ),
        completion_recorder=completion_recorder,
    )


def fill_room(service: PvPRoomService, capacity: int):
    room, creator = service.create_room("A", capacity=capacity)
    participants = [creator]
    for name in ("B", "C", "D")[: capacity - 1]:
        room, participant = service.join_room(room.invite_code, name)
        participants.append(participant)
    return room, participants


def test_capacity_defaults_to_two_and_accepts_only_two_through_four() -> None:
    service = multiplayer_service()

    default, _creator = service.create_room("A")
    assert default.capacity == 2
    for capacity in (2, 3, 4):
        room, _participant = service.create_room(f"A{capacity}", capacity=capacity)
        assert room.capacity == capacity
    for capacity in (1, 5):
        with pytest.raises(PvPError) as caught:
            service.create_room("invalid", capacity=capacity)
        assert caught.value.code is PvPErrorCode.INVALID_CAPACITY


def test_multiplayer_room_waits_for_capacity_and_assigns_stable_lowest_seats() -> None:
    service = multiplayer_service()
    room, a = service.create_room("A", capacity=4)
    room, b = service.join_room(room.invite_code, "B")
    room, c = service.join_room(room.invite_code, "C")

    assert room.phase is PvPRoomPhase.WAITING_FOR_OPPONENT
    assert room.state is None
    assert [participant.seat for participant in room.participants] == [
        Seat.ONE,
        Seat.TWO,
        Seat.THREE,
    ]

    service.connect(room.invite_code, b.reconnect_token, "b-connection")
    room = service.leave_room(room.invite_code, b.reconnect_token, "b-connection")
    room, replacement = service.join_room(room.invite_code, "B2")
    assert replacement.seat is Seat.TWO
    assert a.seat is Seat.ONE
    assert c.seat is Seat.THREE
    assert room.phase is PvPRoomPhase.WAITING_FOR_OPPONENT

    room, d = service.join_room(room.invite_code, "D")
    assert d.seat is Seat.FOUR
    assert room.phase is PvPRoomPhase.GAME_ACTIVE
    assert room.state is not None
    assert room.state.seat_order == (Seat.ONE, Seat.TWO, Seat.THREE, Seat.FOUR)


def test_concurrent_final_join_claims_exactly_one_fourth_seat() -> None:
    service = multiplayer_service()
    room, _a = service.create_room("A", capacity=4)
    room, _b = service.join_room(room.invite_code, "B")
    room, _c = service.join_room(room.invite_code, "C")

    def join(name: str) -> str:
        try:
            _room, participant = service.join_room(room.invite_code, name)
            return participant.seat.value
        except PvPError as error:
            return error.code.value

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = tuple(executor.map(join, ("D1", "D2")))

    assert results.count(Seat.FOUR.value) == 1
    assert results.count(PvPErrorCode.ROOM_FULL.value) == 1
    assert len(service.get_room(room.invite_code).participants) == 4


def test_authenticated_identity_cannot_claim_two_seats() -> None:
    service = multiplayer_service()
    user_id = uuid4()
    room, _creator = service.create_room("A", capacity=3, user_id=user_id)

    with pytest.raises(PvPError) as duplicate:
        service.join_room(room.invite_code, "A again", user_id=user_id)

    assert duplicate.value.code is PvPErrorCode.PARTICIPANT_ALREADY_JOINED
    assert len(service.get_room(room.invite_code).participants) == 1


@pytest.mark.parametrize("capacity", [3, 4])
def test_private_projection_exposes_only_viewer_hand_and_public_card_data(capacity: int) -> None:
    service = multiplayer_service()
    room, participants = fill_room(service, capacity)
    assert room.state is not None

    for viewer in participants:
        payload = serialize_pvp_state(room, viewer).model_dump(mode="json")
        encoded = json.dumps(payload)
        serialized_codes = _card_codes_in(payload)
        visible_codes = {value["code"] for value in payload["hand"]}
        expected_codes = {_card_code(value) for value in room.state.hand(viewer.seat)}
        assert visible_codes == expected_codes
        for opponent in participants:
            if opponent.seat is viewer.seat:
                continue
            for hidden in room.state.hand(opponent.seat):
                assert _card_code(hidden) not in serialized_codes
        for hidden in room.state.draw_pile[1:]:
            assert _card_code(hidden) not in serialized_codes
        assert viewer.reconnect_token not in encoded
        assert all(opponent.reconnect_token not in encoded for opponent in participants)
        assert payload["capacity"] == capacity
        assert payload["joined_count"] == capacity
        assert [player["seat"] for player in payload["players"]] == [
            participant.seat.value for participant in participants
        ]
        assert [player["hand_count"] for player in payload["players"]] == [
            len(room.state.hand(participant.seat)) for participant in participants
        ]


def test_four_seats_disconnect_and_reconnect_independently() -> None:
    service = multiplayer_service()
    room, participants = fill_room(service, 4)
    for index, participant in enumerate(participants):
        registration = service.connect(room.invite_code, participant.reconnect_token, f"c{index}")
        assert registration.participant.seat is participant.seat

    room = service.disconnect(room.invite_code, participants[1].participant_id, "c1")
    room = service.disconnect(room.invite_code, participants[3].participant_id, "c3")
    assert [participant.connected for participant in room.participants] == [
        True,
        False,
        True,
        False,
    ]
    assert [participant.seat for participant in room.participants] == [
        Seat.ONE,
        Seat.TWO,
        Seat.THREE,
        Seat.FOUR,
    ]

    for index in (1, 3):
        registration = service.connect(
            room.invite_code,
            participants[index].reconnect_token,
            f"replacement-{index}",
        )
        assert registration.participant.seat is participants[index].seat
        assert (
            serialize_pvp_state(registration.room, registration.participant).version == room.version
        )


def test_multiplayer_hints_and_rematch_are_explicitly_unsupported() -> None:
    service = multiplayer_service()
    room, participants = fill_room(service, 3)

    with pytest.raises(PvPActionError) as hints:
        service.get_hints(
            room.invite_code,
            participants[0].reconnect_token,
            (),
            expected_version=room.version,
        )
    assert hints.value.code is PvPErrorCode.FEATURE_NOT_AVAILABLE

    with pytest.raises(PvPActionError) as rematch:
        service.request_rematch(
            room.invite_code,
            participants[0].reconnect_token,
            match_id=room.match_id or "missing",
            expected_version=room.version,
        )
    assert rematch.value.code is PvPErrorCode.REMATCH_NOT_AVAILABLE


def test_three_player_transfer_routes_roles_and_rejects_waiting_attacker() -> None:
    king = card(Rank.KING)
    nines = (card(Rank.NINE), card(Rank.NINE, Suit.DIAMONDS))
    aces = (card(Rank.ACE), card(Rank.ACE, Suit.DIAMONDS))

    def factory(_count: int) -> GameState:
        return GameState(
            hands=(
                (king, card(Rank.SIX)),
                (*nines, card(Rank.SEVEN)),
                (*aces, card(Rank.EIGHT)),
            ),
            current_attacker=Seat.ONE,
        )

    service = multiplayer_service(game_factory=factory)
    room, participants = fill_room(service, 3)
    room = service.play_action(
        room.invite_code,
        participants[0].reconnect_token,
        HumanActionType.INITIAL_ATTACK,
        (king,),
        expected_version=room.version,
    )
    with pytest.raises(PvPActionError) as wrong_actor:
        service.play_action(
            room.invite_code,
            participants[2].reconnect_token,
            HumanActionType.DEFEND,
            aces,
            expected_version=room.version,
        )
    assert wrong_actor.value.code is PvPErrorCode.WRONG_TURN

    room = service.play_action(
        room.invite_code,
        participants[1].reconnect_token,
        HumanActionType.TRANSFER,
        nines,
        expected_version=room.version,
    )
    assert room.state is not None and room.state.active_bout is not None
    assert room.state.active_bout.defender is Seat.THREE
    assert room.state.active_bout.lead_attacker is Seat.ONE
    for participant in participants:
        projection = serialize_pvp_state(room, participant)
        assert projection.defender == Seat.THREE.value
        assert projection.lead_attacker == Seat.ONE.value
        assert projection.required_seat == Seat.THREE.value


def test_wrapped_four_player_transfer_is_broadcastable_without_changing_refill_order() -> None:
    selected = {
        Seat.ONE: (card(Rank.KING),),
        Seat.TWO: (card(Rank.NINE), card(Rank.NINE, Suit.DIAMONDS)),
        Seat.THREE: (
            card(Rank.JACK),
            card(Rank.JACK, Suit.DIAMONDS),
            card(Rank.SIX),
            card(Rank.SIX, Suit.DIAMONDS),
        ),
        Seat.FOUR: (
            card(Rank.ACE),
            card(Rank.ACE, Suit.DIAMONDS),
            card(Rank.KING, Suit.DIAMONDS),
            card(Rank.SEVEN),
            card(Rank.SEVEN, Suit.DIAMONDS),
        ),
    }
    used = {value for values in selected.values() for value in values}
    fillers = iter(value for value in create_36_card_deck() if value not in used)
    hands = tuple(
        selected[seat] + tuple(next(fillers) for _ in range(13 - len(selected[seat])))
        if seat is Seat.ONE
        else selected[seat] + tuple(next(fillers) for _ in range(7 - len(selected[seat])))
        for seat in (Seat.ONE, Seat.TWO, Seat.THREE, Seat.FOUR)
    )

    service = multiplayer_service(
        game_factory=lambda _count: GameState(hands=hands, current_attacker=Seat.ONE)
    )
    room, participants = fill_room(service, 4)
    for seat, action in (
        (Seat.ONE, HumanActionType.INITIAL_ATTACK),
        (Seat.TWO, HumanActionType.TRANSFER),
        (Seat.THREE, HumanActionType.TRANSFER),
        (Seat.FOUR, HumanActionType.TRANSFER),
    ):
        participant = next(value for value in participants if value.seat is seat)
        room = service.play_action(
            room.invite_code,
            participant.reconnect_token,
            action,
            selected[seat],
            expected_version=room.version,
        )

    assert room.state is not None and room.state.active_bout is not None
    assert room.state.active_bout.defender is Seat.ONE
    assert room.state.active_bout.lead_attacker is Seat.FOUR
    assert room.state.active_bout.refill_order == (
        Seat.ONE,
        Seat.THREE,
        Seat.FOUR,
        Seat.TWO,
    )
    assert all(
        serialize_pvp_state(room, participant).required_seat == Seat.ONE.value
        for participant in participants
    )
    for index, participant in enumerate(participants):
        service.connect(room.invite_code, participant.reconnect_token, f"transfer-{index}")
    room = service.disconnect(
        room.invite_code,
        participants[3].participant_id,
        "transfer-3",
    )
    room = service.disconnect(
        room.invite_code,
        participants[2].participant_id,
        "transfer-2",
    )
    registration = service.connect(
        room.invite_code,
        participants[2].reconnect_token,
        "transfer-2-reconnected",
    )
    assert registration.participant.seat is Seat.THREE
    assert not registration.room.participant(Seat.FOUR).connected
    assert (
        serialize_pvp_state(registration.room, registration.participant).defender == Seat.ONE.value
    )


def test_noncycling_attacker_priority_moves_one_to_three_to_four() -> None:
    hands = (
        (
            card(Rank.SIX),
            card(Rank.SEVEN, Suit.DIAMONDS),
            card(Rank.EIGHT, Suit.DIAMONDS),
            card(Rank.NINE, Suit.HEARTS),
            card(Rank.KING),
        ),
        (
            card(Rank.SEVEN),
            card(Rank.EIGHT),
            card(Rank.NINE),
            card(Rank.TEN),
            card(Rank.ACE),
        ),
        (card(Rank.NINE, Suit.DIAMONDS), card(Rank.TEN, Suit.HEARTS)),
        (card(Rank.TEN, Suit.DIAMONDS), card(Rank.QUEEN)),
    )
    service = multiplayer_service(
        game_factory=lambda _count: GameState(hands=hands, current_attacker=Seat.ONE)
    )
    room, participants = fill_room(service, 4)

    def act(seat: Seat, action: HumanActionType, *cards: Card) -> None:
        nonlocal room
        participant = next(value for value in participants if value.seat is seat)
        room = service.play_action(
            room.invite_code,
            participant.reconnect_token,
            action,
            cards,
            expected_version=room.version,
        )

    act(Seat.ONE, HumanActionType.INITIAL_ATTACK, card(Rank.SIX))
    act(Seat.TWO, HumanActionType.DEFEND, card(Rank.SEVEN))
    act(Seat.ONE, HumanActionType.THROW_IN, card(Rank.SEVEN, Suit.DIAMONDS))
    act(Seat.TWO, HumanActionType.DEFEND, card(Rank.EIGHT))
    act(Seat.ONE, HumanActionType.THROW_IN, card(Rank.EIGHT, Suit.DIAMONDS))
    act(Seat.TWO, HumanActionType.DEFEND, card(Rank.NINE))
    act(Seat.ONE, HumanActionType.BITO)
    assert room.state is not None and room.state.active_bout is not None
    assert room.state.active_bout.attacker is Seat.THREE

    with pytest.raises(PvPActionError) as closed_attacker:
        service.play_action(
            room.invite_code,
            participants[0].reconnect_token,
            HumanActionType.THROW_IN,
            (card(Rank.KING),),
            expected_version=room.version,
        )
    assert closed_attacker.value.code is PvPErrorCode.WRONG_TURN

    act(Seat.THREE, HumanActionType.THROW_IN, card(Rank.NINE, Suit.DIAMONDS))
    act(Seat.TWO, HumanActionType.DEFEND, card(Rank.TEN))
    act(Seat.THREE, HumanActionType.BITO)
    assert room.state is not None and room.state.active_bout is not None
    assert room.state.active_bout.attacker is Seat.FOUR
    assert serialize_pvp_state(room, participants[3]).required_seat == Seat.FOUR.value


def test_take_ends_four_player_bout_and_stale_throw_in_cannot_commit() -> None:
    six = card(Rank.SIX)

    def factory(_count: int) -> GameState:
        return GameState(
            hands=(
                (six, card(Rank.KING)),
                (card(Rank.SEVEN), card(Rank.ACE)),
                (card(Rank.EIGHT), card(Rank.QUEEN)),
                (card(Rank.NINE), card(Rank.TEN)),
            ),
            current_attacker=Seat.ONE,
        )

    service = multiplayer_service(game_factory=factory)
    room, participants = fill_room(service, 4)
    room = service.play_action(
        room.invite_code,
        participants[0].reconnect_token,
        HumanActionType.INITIAL_ATTACK,
        (six,),
        expected_version=room.version,
    )
    stale_version = room.version
    room = service.play_action(
        room.invite_code,
        participants[1].reconnect_token,
        HumanActionType.TAKE,
        expected_version=room.version,
    )
    assert room.state is not None and room.state.active_bout is not None
    assert room.state.active_bout.attacker is Seat.THREE
    assert acting_seat(room.state) is Seat.THREE
    with pytest.raises(PvPActionError) as stale:
        service.play_action(
            room.invite_code,
            participants[2].reconnect_token,
            HumanActionType.INITIAL_ATTACK,
            (card(Rank.EIGHT),),
            expected_version=stale_version,
        )
    assert stale.value.code is PvPErrorCode.STALE_VERSION


def test_finished_participant_remains_observer_and_multiplayer_result_is_not_persisted() -> None:
    persisted: list[str] = []

    def factory(_count: int) -> GameState:
        return GameState(
            hands=(
                (card(Rank.JACK),),
                (
                    card(Rank.KING),
                    card(Rank.JACK, Suit.DIAMONDS),
                    card(Rank.KING, Suit.HEARTS),
                    card(Rank.SIX, Suit.DIAMONDS),
                ),
                (card(Rank.ACE, Suit.DIAMONDS),),
                (card(Rank.JACK, Suit.SPADES),),
            ),
            current_attacker=Seat.ONE,
        )

    service = multiplayer_service(
        game_factory=factory,
        completion_recorder=lambda room: persisted.append(room.room_id) or (),
    )
    room, participants = fill_room(service, 4)

    def act(seat: Seat, action: HumanActionType, *cards: Card) -> None:
        nonlocal room
        participant = next(value for value in participants if value.seat is seat)
        room = service.play_action(
            room.invite_code,
            participant.reconnect_token,
            action,
            cards,
            expected_version=room.version,
        )

    act(Seat.ONE, HumanActionType.INITIAL_ATTACK, card(Rank.JACK))
    act(Seat.TWO, HumanActionType.DEFEND, card(Rank.KING))
    assert room.state is not None
    assert room.state.finished_seats == (Seat.ONE,)
    assert room.last_bout is not None and room.last_bout.phase is BoutPhase.COMPLETE
    assert len(room.participants) == 4
    assert serialize_pvp_state(room, participants[0]).players[0].finished
    registration = service.connect(room.invite_code, participants[0].reconnect_token, "finished-a")
    assert registration.participant.seat is Seat.ONE
    assert serialize_pvp_state(registration.room, registration.participant).players[0].finished
    with pytest.raises(PvPActionError) as finished:
        service.play_action(
            room.invite_code,
            participants[0].reconnect_token,
            HumanActionType.INITIAL_ATTACK,
            (),
            expected_version=room.version,
        )
    assert finished.value.code is PvPErrorCode.WRONG_TURN

    act(Seat.TWO, HumanActionType.INITIAL_ATTACK, card(Rank.JACK, Suit.DIAMONDS))
    act(Seat.THREE, HumanActionType.DEFEND, card(Rank.ACE, Suit.DIAMONDS))
    assert room.state is not None and room.state.active_seats == (Seat.TWO, Seat.FOUR)
    act(Seat.FOUR, HumanActionType.INITIAL_ATTACK, card(Rank.JACK, Suit.SPADES))
    act(Seat.TWO, HumanActionType.DEFEND, card(Rank.KING, Suit.HEARTS))
    act(Seat.FOUR, HumanActionType.BITO)

    assert room.phase is PvPRoomPhase.COMPLETE
    assert room.state is not None and room.state.result is None
    assert room.state.finish_groups == (
        (Seat.ONE,),
        (Seat.THREE,),
        (Seat.FOUR,),
        (Seat.TWO,),
    )
    assert serialize_pvp_state(room, participants[0]).finish_groups == [
        [Seat.ONE.value],
        [Seat.THREE.value],
        [Seat.FOUR.value],
        [Seat.TWO.value],
    ]
    assert persisted == []


def test_simultaneous_finish_groups_are_projected_without_binary_result() -> None:
    def factory(_count: int) -> GameState:
        return GameState(
            hands=(
                (card(Rank.JACK),),
                (card(Rank.KING),),
                (card(Rank.SIX, Suit.HEARTS),),
                (card(Rank.SEVEN, Suit.HEARTS),),
            ),
            current_attacker=Seat.ONE,
        )

    service = multiplayer_service(game_factory=factory)
    room, participants = fill_room(service, 4)

    def act(seat: Seat, action: HumanActionType, chosen: Card) -> None:
        nonlocal room
        participant = next(value for value in participants if value.seat is seat)
        room = service.play_action(
            room.invite_code,
            participant.reconnect_token,
            action,
            (chosen,),
            expected_version=room.version,
        )

    act(Seat.ONE, HumanActionType.INITIAL_ATTACK, card(Rank.JACK))
    act(Seat.TWO, HumanActionType.DEFEND, card(Rank.KING))
    act(Seat.THREE, HumanActionType.INITIAL_ATTACK, card(Rank.SIX, Suit.HEARTS))
    act(Seat.FOUR, HumanActionType.DEFEND, card(Rank.SEVEN, Suit.HEARTS))

    assert room.phase is PvPRoomPhase.COMPLETE
    assert room.state is not None and room.state.result is None
    assert room.state.finish_groups == ((Seat.ONE, Seat.TWO), (Seat.THREE, Seat.FOUR))
    for participant in participants:
        projection = serialize_pvp_state(room, participant)
        assert projection.result is None
        assert projection.finish_groups == [
            [Seat.ONE.value, Seat.TWO.value],
            [Seat.THREE.value, Seat.FOUR.value],
        ]


@pytest.mark.parametrize("capacity", [3, 4])
def test_rest_and_websocket_flow_starts_at_capacity_and_broadcasts_private_state(
    capacity: int,
) -> None:
    service = multiplayer_service()
    database = Database("sqlite://")
    Base.metadata.create_all(database.engine)
    settings = Settings(database_url="sqlite://", csrf_trusted_origins=(ORIGIN,))
    try:
        with TestClient(
            create_app(database=database, settings=settings, pvp_service=service)
        ) as client:
            created = client.post(
                "/api/pvp/rooms",
                json={"nickname": "A", "capacity": capacity},
            )
            assert created.status_code == 201
            payloads = [created.json()]
            for index in range(1, capacity):
                response = client.post(
                    f"/api/pvp/rooms/{payloads[0]['invite_code']}/join",
                    json={"nickname": chr(ord("A") + index)},
                )
                assert response.status_code == 200
                payloads.append(response.json())
                expected = "GAME_ACTIVE" if index + 1 == capacity else "WAITING_FOR_OPPONENT"
                assert response.json()["state"]["room_phase"] == expected

            with ExitStack() as stack:
                sockets = []
                latest_states = []
                for payload in payloads:
                    socket = stack.enter_context(
                        client.websocket_connect(
                            f"/api/pvp/rooms/{payload['invite_code']}/ws",
                            headers={"Origin": ORIGIN},
                        )
                    )
                    socket.send_json(
                        {
                            "type": "AUTH",
                            "credential": payload["credential"]["reconnect_token"],
                        }
                    )
                    first = socket.receive_json()
                    assert first["type"] == "STATE"
                    latest_states.append(first["state"])
                    for previous in sockets:
                        assert previous.receive_json()["type"] == "OPPONENT_CONNECTED"
                        assert previous.receive_json()["type"] == "STATE"
                    sockets.append(socket)

                actor_seat = latest_states[-1]["required_seat"]
                actor_index = next(
                    index
                    for index, payload in enumerate(payloads)
                    if payload["credential"]["seat"] == actor_seat
                )
                actor_state = serialize_pvp_state(
                    service.get_room(payloads[0]["invite_code"]),
                    service.get_room(payloads[0]["invite_code"]).participants[actor_index],
                )
                sockets[actor_index].send_json(
                    {
                        "type": "ACTION",
                        "version": actor_state.version,
                        "action": "INITIAL_ATTACK",
                        "cards": [actor_state.hand[0].code],
                    }
                )
                broadcasts = [socket.receive_json() for socket in sockets]
                assert all(message["type"] == "STATE" for message in broadcasts)
                assert {message["state"]["version"] for message in broadcasts} == {1}
                assert len(broadcasts[actor_index]["state"]["hand"]) == 6
                assert all(len(message["state"]["players"]) == capacity for message in broadcasts)

                authoritative = service.get_room(payloads[0]["invite_code"])
                assert authoritative.state is not None
                responder_seat = acting_seat(authoritative.state)
                assert responder_seat is not None
                response = choose_bot_action(authoritative.state, responder_seat)
                responder_index = next(
                    index
                    for index, payload in enumerate(payloads)
                    if payload["credential"]["seat"] == responder_seat.value
                )
                sockets[responder_index].send_json(
                    {
                        "type": "ACTION",
                        "version": authoritative.version,
                        "action": response.action_type.name,
                        "cards": [_card_code(value) for value in response.cards],
                    }
                )
                response_broadcasts = [socket.receive_json() for socket in sockets]
                assert all(message["type"] == "STATE" for message in response_broadcasts)
                assert {message["state"]["version"] for message in response_broadcasts} == {2}
                assert all(
                    message["state"]["required_seat"]
                    == response_broadcasts[0]["state"]["required_seat"]
                    for message in response_broadcasts
                )
    finally:
        database.dispose()


def test_prestart_websocket_exit_releases_seat_with_distinct_left_event() -> None:
    service = multiplayer_service()
    database = Database("sqlite://")
    Base.metadata.create_all(database.engine)
    settings = Settings(database_url="sqlite://", csrf_trusted_origins=(ORIGIN,))
    try:
        with TestClient(
            create_app(database=database, settings=settings, pvp_service=service)
        ) as client:
            creator = client.post(
                "/api/pvp/rooms",
                json={"nickname": "A", "capacity": 3},
            ).json()
            joiner = client.post(
                f"/api/pvp/rooms/{creator['invite_code']}/join",
                json={"nickname": "B"},
            ).json()
            path = f"/api/pvp/rooms/{creator['invite_code']}/ws"
            with client.websocket_connect(path, headers={"Origin": ORIGIN}) as one:
                one.send_json(
                    {"type": "AUTH", "credential": creator["credential"]["reconnect_token"]}
                )
                assert one.receive_json()["type"] == "STATE"
                with client.websocket_connect(path, headers={"Origin": ORIGIN}) as two:
                    two.send_json(
                        {"type": "AUTH", "credential": joiner["credential"]["reconnect_token"]}
                    )
                    assert two.receive_json()["type"] == "STATE"
                    assert one.receive_json()["type"] == "OPPONENT_CONNECTED"
                    assert one.receive_json()["type"] == "STATE"
                    two.send_json({"type": "LEAVE"})
                    left = one.receive_json()
                    state = one.receive_json()

            assert left["type"] == "PARTICIPANT_LEFT"
            assert left["participant_id"] == joiner["credential"]["participant_id"]
            assert left["seat"] == Seat.TWO.value
            assert state["type"] == "STATE"
            assert state["state"]["room_phase"] == "WAITING_FOR_OPPONENT"
            assert state["state"]["joined_count"] == 1
            assert [player["seat"] for player in state["state"]["players"]] == [Seat.ONE.value]
    finally:
        database.dispose()


def test_active_multiplayer_exit_closes_neutrally_without_finish_group() -> None:
    service = multiplayer_service()
    room, participants = fill_room(service, 3)
    service.connect(room.invite_code, participants[1].reconnect_token, "leaving")

    room = service.leave_room(room.invite_code, participants[1].reconnect_token, "leaving")

    assert room.phase is PvPRoomPhase.CLOSED
    assert room.state is not None and room.state.phase is GamePhase.BOUT_ACTIVE
    assert room.state.finish_groups == ()
    assert room.completion_results == ()


def test_multiplayer_cleanup_waits_for_every_connection_then_expires_active_room() -> None:
    now = [datetime(2026, 10, 9, tzinfo=UTC)]
    service = PvPRoomService(
        multiplayer_game_factory=lambda count: create_new_game(
            random.Random(100 + count), player_count=count
        ),
        clock=lambda: now[0],
        ttl=RoomTTLPolicy(disconnected_active=timedelta(seconds=1)),
    )
    room, participants = fill_room(service, 4)
    service.connect(room.invite_code, participants[0].reconnect_token, "connected")
    now[0] += timedelta(seconds=2)
    assert service.get_room(room.invite_code).phase is PvPRoomPhase.GAME_ACTIVE

    service.disconnect(room.invite_code, participants[0].participant_id, "connected")
    now[0] += timedelta(seconds=2)
    with pytest.raises(PvPError) as expired:
        service.get_room(room.invite_code)
    assert expired.value.code is PvPErrorCode.INVITE_EXPIRED


def _card_code(value: Card) -> str:
    suit = {
        Suit.CLUBS: "C",
        Suit.DIAMONDS: "D",
        Suit.HEARTS: "H",
        Suit.SPADES: "S",
    }[value.suit]
    return f"{value.rank.value}{suit}"


def _card_codes_in(value: object) -> set[str]:
    codes: set[str] = set()
    if isinstance(value, dict):
        code = value.get("code")
        if isinstance(code, str):
            codes.add(code)
        for child in value.values():
            codes.update(_card_codes_in(child))
    elif isinstance(value, list):
        for child in value:
            codes.update(_card_codes_in(child))
    return codes
