from __future__ import annotations

import json
import random
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from starlette.websockets import WebSocketDisconnect

from kiba_api.api.cards import card_to_code
from kiba_api.config import Settings
from kiba_api.game import BotActionType, GamePhase, Seat, choose_bot_action, create_new_game
from kiba_api.main import create_app
from kiba_api.persistence import Base, CompletedMatch, Database, XPLedgerEntry
from kiba_api.pvp import PvPRoomService, RoomTTLPolicy
from kiba_api.sessions import acting_seat

ORIGIN = "http://testserver"


@pytest.fixture
def database() -> Database:
    value = Database("sqlite://")
    Base.metadata.create_all(value.engine)
    yield value
    value.dispose()


@pytest.fixture
def pvp_service() -> PvPRoomService:
    return PvPRoomService(game_factory=lambda: create_new_game(random.Random(42)))


@pytest.fixture
def client(database: Database, pvp_service: PvPRoomService) -> TestClient:
    settings = Settings(database_url="sqlite://", csrf_trusted_origins=(ORIGIN,))
    return TestClient(create_app(database=database, settings=settings, pvp_service=pvp_service))


def create_and_join(client: TestClient):
    created = client.post("/api/pvp/rooms", json={"nickname": "Creator"})
    assert created.status_code == 201
    creator = created.json()
    joined = client.post(
        f"/api/pvp/rooms/{creator['invite_code']}/join",
        json={"nickname": "Friend"},
    )
    assert joined.status_code == 200
    return creator, joined.json()


def websocket_path(payload: dict) -> str:
    return f"/api/pvp/rooms/{payload['invite_code']}/ws"


def authenticate(socket, payload: dict) -> dict:
    socket.send_json(
        {
            "type": "AUTH",
            "credential": payload["credential"]["reconnect_token"],
        }
    )
    message = socket.receive_json()
    assert message["type"] == "STATE"
    return message["state"]


def card_codes_in(value: object) -> set[str]:
    codes: set[str] = set()
    if isinstance(value, dict):
        code = value.get("code")
        if isinstance(code, str):
            codes.add(code)
        for child in value.values():
            codes.update(card_codes_in(child))
    elif isinstance(value, list):
        for child in value:
            codes.update(card_codes_in(child))
    return codes


def test_rest_create_join_status_and_room_full_are_explicit(client: TestClient) -> None:
    creator, joiner = create_and_join(client)

    status = client.get(f"/api/pvp/rooms/{creator['invite_code']}")
    full = client.post(
        f"/api/pvp/rooms/{creator['invite_code']}/join",
        json={"nickname": "Third"},
    )

    assert creator["credential"]["seat"] == Seat.ONE.value
    assert joiner["credential"]["seat"] == Seat.TWO.value
    assert creator["state"]["room_phase"] == "WAITING_FOR_OPPONENT"
    assert joiner["state"]["room_phase"] == "GAME_ACTIVE"
    assert status.status_code == 200
    assert len(status.json()["participants"]) == 2
    assert "reconnect_token" not in status.text
    assert full.status_code == 409
    assert full.json() == {"detail": {"code": "ROOM_FULL"}}


def test_waiting_creator_can_recover_state_ping_and_get_game_not_ready(client: TestClient) -> None:
    creator = client.post("/api/pvp/rooms", json={"nickname": "Creator"}).json()

    with client.websocket_connect(websocket_path(creator), headers={"Origin": ORIGIN}) as socket:
        state = authenticate(socket, creator)
        socket.send_json({"type": "PING"})
        pong = socket.receive_json()
        socket.send_json(
            {
                "type": "ACTION",
                "version": 0,
                "action": "INITIAL_ATTACK",
                "cards": ["6C"],
            }
        )
        rejected = socket.receive_json()

    assert state["room_phase"] == "WAITING_FOR_OPPONENT"
    assert pong == {"type": "PONG", "version": 0}
    assert rejected["error"]["code"] == "GAME_NOT_READY"


def test_join_broadcasts_active_state_to_an_already_connected_creator(client: TestClient) -> None:
    creator = client.post("/api/pvp/rooms", json={"nickname": "Creator"}).json()

    with client.websocket_connect(websocket_path(creator), headers={"Origin": ORIGIN}) as socket:
        waiting = authenticate(socket, creator)
        joined = client.post(
            f"/api/pvp/rooms/{creator['invite_code']}/join",
            json={"nickname": "Friend"},
        )
        connected = socket.receive_json()
        active = socket.receive_json()

    assert waiting["room_phase"] == "WAITING_FOR_OPPONENT"
    assert joined.status_code == 200
    assert connected["type"] == "OPPONENT_CONNECTED"
    assert active["type"] == "STATE"
    assert active["state"]["room_phase"] == "GAME_ACTIVE"


def test_invalid_reconnect_credential_is_rejected(client: TestClient) -> None:
    creator, _joiner = create_and_join(client)

    with client.websocket_connect(websocket_path(creator), headers={"Origin": ORIGIN}) as socket:
        socket.send_json({"type": "AUTH", "credential": "not-valid"})
        message = socket.receive_json()
        with pytest.raises(WebSocketDisconnect) as closed:
            socket.receive_json()

    assert message["error"]["code"] == "INVALID_CREDENTIAL"
    assert closed.value.code == 4401


def test_expired_room_auth_is_terminal_and_distinct_from_invalid_credential(
    database: Database,
) -> None:
    now = [datetime(2026, 8, 27, tzinfo=UTC)]
    service = PvPRoomService(
        game_factory=lambda: create_new_game(random.Random(42)),
        clock=lambda: now[0],
        ttl=RoomTTLPolicy(
            waiting=timedelta(seconds=1),
            complete=timedelta(seconds=1),
            disconnected_active=timedelta(seconds=1),
        ),
    )
    settings = Settings(database_url="sqlite://", csrf_trusted_origins=(ORIGIN,))
    expiring_client = TestClient(
        create_app(database=database, settings=settings, pvp_service=service)
    )
    creator = expiring_client.post("/api/pvp/rooms", json={"nickname": "Creator"}).json()
    now[0] += timedelta(seconds=2)

    with expiring_client.websocket_connect(
        websocket_path(creator), headers={"Origin": ORIGIN}
    ) as socket:
        socket.send_json(
            {
                "type": "AUTH",
                "credential": creator["credential"]["reconnect_token"],
            }
        )
        message = socket.receive_json()
        with pytest.raises(WebSocketDisconnect) as closed:
            socket.receive_json()

    assert message["error"]["code"] == "INVITE_EXPIRED"
    assert closed.value.code == 4404


@pytest.mark.parametrize("nickname", [None, "", "   ", "x" * 25, "bad\nname"])
def test_guest_room_requires_a_valid_nickname(client: TestClient, nickname: str | None) -> None:
    response = client.post("/api/pvp/rooms", json={"nickname": nickname})

    assert response.status_code == 422
    assert response.json() == {"detail": {"code": "INVALID_NICKNAME"}}


def test_authenticated_creator_uses_account_display_name_and_guest_can_join(
    client: TestClient,
) -> None:
    registered = client.post(
        "/api/auth/register",
        headers={"Origin": ORIGIN},
        json={
            "email": "creator@example.com",
            "display_name": "Account Creator",
            "password": "correct horse battery staple",
        },
    )
    created = client.post("/api/pvp/rooms", json={})
    guest_client = TestClient(client.app)
    joined = guest_client.post(
        f"/api/pvp/rooms/{created.json()['invite_code']}/join",
        json={"nickname": "Guest Friend"},
    )

    assert registered.status_code == 201
    assert created.status_code == 201
    assert created.json()["state"]["you"]["display_name"] == "Account Creator"
    assert created.json()["state"]["you"]["authenticated"] is True
    assert joined.status_code == 200
    assert joined.json()["state"]["you"]["display_name"] == "Guest Friend"
    assert joined.json()["state"]["you"]["authenticated"] is False


def test_participant_specific_state_never_leaks_opponent_or_future_draw_cards(
    client: TestClient,
    pvp_service: PvPRoomService,
) -> None:
    creator, joiner = create_and_join(client)
    room = pvp_service.get_room(creator["invite_code"])
    assert room.state is not None

    with client.websocket_connect(websocket_path(creator), headers={"Origin": ORIGIN}) as one:
        state_one = authenticate(one, creator)
        with client.websocket_connect(websocket_path(joiner), headers={"Origin": ORIGIN}) as two:
            state_two = authenticate(two, joiner)
            assert one.receive_json()["type"] == "OPPONENT_CONNECTED"
            state_one = one.receive_json()["state"]

            seat_one_codes = {card_to_code(card) for card in room.state.seat_one_hand}
            seat_two_codes = {card_to_code(card) for card in room.state.seat_two_hand}
            hidden_draw_codes = {card_to_code(card) for card in room.state.draw_pile[1:]}

            assert card_codes_in(state_one).isdisjoint(seat_two_codes)
            assert card_codes_in(state_two).isdisjoint(seat_one_codes)
            assert card_codes_in(state_one).isdisjoint(hidden_draw_codes)
            assert card_codes_in(state_two).isdisjoint(hidden_draw_codes)
            assert {card["code"] for card in state_one["hand"]} == seat_one_codes
            assert {card["code"] for card in state_two["hand"]} == seat_two_codes
            assert state_one["opponent_hand_count"] == 7
            assert state_two["opponent_hand_count"] == 7
            serialized = json.dumps((state_one, state_two))
            assert creator["credential"]["reconnect_token"] not in serialized
            assert joiner["credential"]["reconnect_token"] not in serialized
            assert "draw_pile" not in state_one
            assert "draw_pile" not in state_two
            assert "opponent_hand" not in state_one
            assert "opponent_hand" not in state_two


def test_websocket_rejects_wrong_actor_then_broadcasts_accepted_state(
    client: TestClient,
    pvp_service: PvPRoomService,
) -> None:
    creator, joiner = create_and_join(client)
    room = pvp_service.get_room(creator["invite_code"])
    assert room.state is not None
    actor = acting_seat(room.state)
    actor_payload = creator if actor is Seat.ONE else joiner
    wrong_payload = joiner if actor is Seat.ONE else creator
    card_code = card_to_code(room.state.hand(actor or Seat.ONE)[0])

    with client.websocket_connect(websocket_path(creator), headers={"Origin": ORIGIN}) as one:
        authenticate(one, creator)
        with client.websocket_connect(websocket_path(joiner), headers={"Origin": ORIGIN}) as two:
            authenticate(two, joiner)
            one.receive_json()
            one.receive_json()
            sockets = {Seat.ONE: one, Seat.TWO: two}

            sockets[Seat(wrong_payload["credential"]["seat"])].send_json(
                {
                    "type": "ACTION",
                    "version": 0,
                    "action": "INITIAL_ATTACK",
                    "cards": [card_code],
                }
            )
            rejected = sockets[Seat(wrong_payload["credential"]["seat"])].receive_json()
            assert rejected == {
                "type": "ACTION_REJECTED",
                "error": {"code": "WRONG_TURN", "domain_code": None},
            }

            sockets[Seat(actor_payload["credential"]["seat"])].send_json(
                {
                    "type": "ACTION",
                    "version": 0,
                    "action": "INITIAL_ATTACK",
                    "cards": [card_code],
                }
            )
            states = (one.receive_json(), two.receive_json())

            assert all(message["type"] == "STATE" for message in states)
            assert all(message["state"]["version"] == 1 for message in states)
            assert pvp_service.get_room(creator["invite_code"]).version == 1


def test_stale_websocket_action_returns_latest_state_without_mutation(
    client: TestClient,
    pvp_service: PvPRoomService,
) -> None:
    creator, joiner = create_and_join(client)
    room = pvp_service.get_room(creator["invite_code"])
    assert room.state is not None
    actor = acting_seat(room.state)
    assert actor is not None
    actor_payload = creator if actor is Seat.ONE else joiner
    card_code = card_to_code(room.state.hand(actor)[0])

    with client.websocket_connect(
        websocket_path(actor_payload), headers={"Origin": ORIGIN}
    ) as socket:
        authenticate(socket, actor_payload)
        action = {
            "type": "ACTION",
            "version": 0,
            "action": "INITIAL_ATTACK",
            "cards": [card_code],
        }
        socket.send_json(action)
        accepted = socket.receive_json()
        socket.send_json(action)
        rejected = socket.receive_json()
        latest = socket.receive_json()

    assert accepted["type"] == "STATE"
    assert accepted["state"]["version"] == 1
    assert rejected == {
        "type": "ACTION_REJECTED",
        "error": {"code": "STALE_VERSION", "domain_code": None},
    }
    assert latest["type"] == "STATE"
    assert latest["state"]["version"] == 1
    assert pvp_service.get_room(creator["invite_code"]).version == 1


def test_malformed_messages_are_rejected_without_mutating_room(
    client: TestClient,
    pvp_service: PvPRoomService,
) -> None:
    creator, _joiner = create_and_join(client)

    with client.websocket_connect(websocket_path(creator), headers={"Origin": ORIGIN}) as socket:
        authenticate(socket, creator)
        socket.send_text("not-json")
        invalid_json = socket.receive_json()
        socket.send_json({"type": "UNKNOWN"})
        unsupported = socket.receive_json()
        socket.send_json(
            {
                "type": "ACTION",
                "version": 0,
                "action": "DEFEND",
                "cards": ["not-a-card"],
            }
        )
        malformed_card = socket.receive_json()

    assert invalid_json["error"]["domain_code"] == "invalid_json"
    assert unsupported["error"]["domain_code"] == "invalid_message"
    assert malformed_card["type"] == "ACTION_REJECTED"
    assert pvp_service.get_room(creator["invite_code"]).version == 0


def test_disconnect_and_same_credential_reconnect_restore_latest_state(
    client: TestClient,
    pvp_service: PvPRoomService,
) -> None:
    creator, _joiner = create_and_join(client)
    path = websocket_path(creator)

    with client.websocket_connect(path, headers={"Origin": ORIGIN}) as socket:
        first = authenticate(socket, creator)
        assert first["version"] == 0

    disconnected = pvp_service.get_room(creator["invite_code"])
    assert disconnected.participant(Seat.ONE).connected is False

    with client.websocket_connect(path, headers={"Origin": ORIGIN}) as socket:
        restored = authenticate(socket, creator)
        assert restored["version"] == 0
        assert restored["game_phase"] == GamePhase.BOUT_ACTIVE.value


def test_untrusted_websocket_origin_is_rejected(client: TestClient) -> None:
    creator, _joiner = create_and_join(client)

    with (
        pytest.raises(WebSocketDisconnect) as caught,
        client.websocket_connect(
            websocket_path(creator),
            headers={"Origin": "https://evil.example"},
        ),
    ):
        pass

    assert caught.value.code == 4403


def test_websocket_rejects_oversized_frames_without_changing_room(
    client: TestClient,
    pvp_service: PvPRoomService,
) -> None:
    creator, _joiner = create_and_join(client)

    with client.websocket_connect(websocket_path(creator), headers={"Origin": ORIGIN}) as socket:
        authenticate(socket, creator)
        socket.send_text(json.dumps({"type": "PING", "padding": "x" * 17_000}))
        response = socket.receive_json()

    assert response == {
        "type": "ERROR",
        "error": {"code": "MESSAGE_TOO_LARGE", "domain_code": None},
    }
    assert pvp_service.get_room(creator["invite_code"]).version == 0


def test_websocket_action_rate_limit_is_machine_readable(database: Database) -> None:
    service = PvPRoomService(game_factory=lambda: create_new_game(random.Random(42)))
    settings = Settings(
        database_url="sqlite://",
        csrf_trusted_origins=(ORIGIN,),
        pvp_action_rate_limit_attempts=1,
        pvp_action_rate_limit_window_seconds=60,
    )
    client = TestClient(create_app(database=database, settings=settings, pvp_service=service))
    creator, joiner = create_and_join(client)
    room = service.get_room(creator["invite_code"])
    assert room.state is not None
    actor = acting_seat(room.state)
    wrong = joiner if actor is Seat.ONE else creator
    wrong_seat = Seat(wrong["credential"]["seat"])
    card_code = card_to_code(room.state.hand(wrong_seat)[0])

    with client.websocket_connect(websocket_path(wrong), headers={"Origin": ORIGIN}) as socket:
        authenticate(socket, wrong)
        message = {
            "type": "ACTION",
            "version": 0,
            "action": "INITIAL_ATTACK",
            "cards": [card_code],
        }
        socket.send_json(message)
        assert socket.receive_json()["error"]["code"] == "WRONG_TURN"
        socket.send_json(message)
        assert socket.receive_json()["error"]["code"] == "RATE_LIMITED"


def test_full_two_client_match_completes_through_websocket_actions(
    client: TestClient,
    pvp_service: PvPRoomService,
    database: Database,
) -> None:
    creator, joiner = create_and_join(client)
    mapping = {
        BotActionType.INITIAL_ATTACK: "INITIAL_ATTACK",
        BotActionType.DEFEND: "DEFEND",
        BotActionType.TRANSFER: "TRANSFER",
        BotActionType.THROW_IN: "THROW_IN",
        BotActionType.TAKE: "TAKE",
        BotActionType.BITO: "BITO",
    }

    with client.websocket_connect(websocket_path(creator), headers={"Origin": ORIGIN}) as one:
        authenticate(one, creator)
        with client.websocket_connect(websocket_path(joiner), headers={"Origin": ORIGIN}) as two:
            authenticate(two, joiner)
            one.receive_json()
            one.receive_json()
            sockets = {Seat.ONE: one, Seat.TWO: two}

            for _action_count in range(1000):
                room = pvp_service.get_room(creator["invite_code"])
                assert room.state is not None
                if room.state.phase is GamePhase.COMPLETE:
                    break
                actor = acting_seat(room.state)
                assert actor is not None
                action = choose_bot_action(room.state, actor)
                assert action.action_type is not BotActionType.START_BOUT
                sockets[actor].send_json(
                    {
                        "type": "ACTION",
                        "version": room.version,
                        "action": mapping[action.action_type],
                        "cards": [card_to_code(card) for card in action.cards],
                    }
                )
                updates = (one.receive_json(), two.receive_json())
                assert all(message["type"] == "STATE" for message in updates)
                assert updates[0]["state"]["version"] == room.version + 1
                if updates[0]["state"]["game_phase"] == GamePhase.COMPLETE.value:
                    assert one.receive_json()["type"] == "GAME_COMPLETE"
                    assert two.receive_json()["type"] == "GAME_COMPLETE"
                    one.send_json(
                        {
                            "type": "ACTION",
                            "version": room.version + 1,
                            "action": "BITO",
                            "cards": [],
                        }
                    )
                    assert one.receive_json()["error"]["code"] == "GAME_COMPLETE"
                    break
            else:
                pytest.fail("PvP transport match exceeded the defensive action bound")

    completed = pvp_service.get_room(creator["invite_code"])
    assert completed.phase.value == "COMPLETE"
    assert completed.state is not None
    assert completed.state.phase is GamePhase.COMPLETE
    assert completed.state.result is not None
    with database.session() as session:
        assert session.scalar(select(func.count()).select_from(CompletedMatch)) == 0


def test_authenticated_pvp_completion_persists_private_progression_once(
    database: Database,
) -> None:
    settings = Settings(
        database_url="sqlite://",
        csrf_trusted_origins=(ORIGIN,),
        pvp_action_rate_limit_attempts=2000,
    )
    application = create_app(database=database, settings=settings)
    client = TestClient(application)
    assert (
        client.post(
            "/api/auth/register",
            headers={"Origin": ORIGIN},
            json={
                "email": "alice@example.com",
                "display_name": "Alice",
                "password": "correct horse battery staple",
            },
        ).status_code
        == 201
    )
    creator = client.post("/api/pvp/rooms", json={}).json()
    assert client.post("/api/auth/logout", headers={"Origin": ORIGIN}).status_code == 204
    assert (
        client.post(
            "/api/auth/register",
            headers={"Origin": ORIGIN},
            json={
                "email": "bob@example.com",
                "display_name": "Bob",
                "password": "correct horse battery staple",
            },
        ).status_code
        == 201
    )
    joiner = client.post(f"/api/pvp/rooms/{creator['invite_code']}/join", json={}).json()
    service = application.state.pvp_service
    mapping = {
        BotActionType.INITIAL_ATTACK: "INITIAL_ATTACK",
        BotActionType.DEFEND: "DEFEND",
        BotActionType.TRANSFER: "TRANSFER",
        BotActionType.THROW_IN: "THROW_IN",
        BotActionType.TAKE: "TAKE",
        BotActionType.BITO: "BITO",
    }

    complete_states = {}
    with client.websocket_connect(websocket_path(creator), headers={"Origin": ORIGIN}) as one:
        authenticate(one, creator)
        with client.websocket_connect(websocket_path(joiner), headers={"Origin": ORIGIN}) as two:
            authenticate(two, joiner)
            one.receive_json()
            one.receive_json()
            sockets = {Seat.ONE: one, Seat.TWO: two}
            for _action_count in range(1000):
                room = service.get_room(creator["invite_code"])
                assert room.state is not None
                if room.state.phase is GamePhase.COMPLETE:
                    break
                actor = acting_seat(room.state)
                assert actor is not None
                action = choose_bot_action(room.state, actor)
                sockets[actor].send_json(
                    {
                        "type": "ACTION",
                        "version": room.version,
                        "action": mapping[action.action_type],
                        "cards": [card_to_code(card) for card in action.cards],
                    }
                )
                updates = (one.receive_json(), two.receive_json())
                if updates[0]["state"]["game_phase"] == GamePhase.COMPLETE.value:
                    complete_states[Seat.ONE] = updates[0]["state"]
                    complete_states[Seat.TWO] = updates[1]["state"]
                    assert one.receive_json()["type"] == "GAME_COMPLETE"
                    assert two.receive_json()["type"] == "GAME_COMPLETE"
                    break
            else:
                pytest.fail("authenticated PvP match exceeded the action bound")

    assert complete_states[Seat.ONE]["result_saved"] is True
    assert complete_states[Seat.TWO]["result_saved"] is True
    assert complete_states[Seat.ONE]["progression_award"] is not None
    assert complete_states[Seat.TWO]["progression_award"] is not None
    assert {
        complete_states[Seat.ONE]["progression_award"]["base_xp"],
        complete_states[Seat.TWO]["progression_award"]["base_xp"],
    } <= {25, 50, 100}

    with client.websocket_connect(websocket_path(creator), headers={"Origin": ORIGIN}) as socket:
        reconnected = authenticate(socket, creator)
    assert reconnected["progression_award"] == complete_states[Seat.ONE]["progression_award"]
    with database.session() as session:
        rows = list(session.scalars(select(CompletedMatch)))
        assert len(rows) == 2
        assert len({row.pvp_match_id for row in rows}) == 1
        ledger_count = session.scalar(select(func.count()).select_from(XPLedgerEntry))
    service.get_room(creator["invite_code"])
    with database.session() as session:
        assert session.scalar(select(func.count()).select_from(CompletedMatch)) == 2
        assert session.scalar(select(func.count()).select_from(XPLedgerEntry)) == ledger_count
