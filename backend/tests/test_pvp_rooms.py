from __future__ import annotations

import random
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from kiba_api.game import GamePhase, Seat, create_new_game
from kiba_api.pvp import (
    PvPActionError,
    PvPError,
    PvPErrorCode,
    PvPRoomPhase,
    PvPRoomService,
    RoomTTLPolicy,
    normalize_guest_nickname,
)
from kiba_api.sessions import HumanActionType, acting_seat


class TokenFactory:
    def __init__(self) -> None:
        self.index = 0

    def __call__(self, length: int) -> str:
        self.index += 1
        return f"opaque-{length}-{self.index}"


def service_for_seed(seed: int = 42, **kwargs) -> PvPRoomService:
    return PvPRoomService(
        game_factory=lambda: create_new_game(random.Random(seed)),
        token_factory=TokenFactory(),
        **kwargs,
    )


def create_started_room(service: PvPRoomService):
    room, creator = service.create_room("Creator")
    room, joiner = service.join_room(room.invite_code, "Friend")
    return room, creator, joiner


def test_room_lifecycle_assigns_seats_and_starts_one_authoritative_game() -> None:
    service = service_for_seed()

    waiting, creator = service.create_room("Creator")

    assert waiting.phase is PvPRoomPhase.WAITING_FOR_OPPONENT
    assert waiting.state is None
    assert waiting.version == 0
    assert creator.seat is Seat.ONE
    assert creator.reconnect_token not in waiting.invite_code

    active, joiner = service.join_room(waiting.invite_code, "Friend")

    assert joiner.seat is Seat.TWO
    assert active.phase is PvPRoomPhase.GAME_ACTIVE
    assert active.state is not None
    assert active.state.phase is GamePhase.BOUT_ACTIVE
    assert active.state.active_bout is not None
    assert active.version == 0
    assert service.get_room(active.invite_code) is active


def test_default_invite_participant_and_reconnect_tokens_are_opaque_url_safe_values() -> None:
    service = PvPRoomService(game_factory=lambda: create_new_game(random.Random(42)))

    room, creator = service.create_room("Creator")

    assert re.fullmatch(r"[A-Za-z0-9_-]+", room.invite_code)
    assert re.fullmatch(r"[A-Za-z0-9_-]+", creator.participant_id)
    assert re.fullmatch(r"[A-Za-z0-9_-]+", creator.reconnect_token)
    assert len(creator.reconnect_token) >= 40
    assert len({room.invite_code, creator.participant_id, creator.reconnect_token}) == 3


def test_room_is_guest_friendly_and_supports_all_account_combinations() -> None:
    combinations = (
        (None, None),
        (uuid4(), None),
        (None, uuid4()),
        (uuid4(), uuid4()),
    )

    for creator_user_id, joiner_user_id in combinations:
        service = service_for_seed()
        room, creator = service.create_room("Creator", user_id=creator_user_id)
        room, joiner = service.join_room(
            room.invite_code,
            "Friend",
            user_id=joiner_user_id,
        )

        assert creator.user_id == creator_user_id
        assert joiner.user_id == joiner_user_id
        assert room.state is not None


@pytest.mark.parametrize("nickname", [None, "", "   ", "x" * 25, "bad\nname", "bad\u200bname"])
def test_guest_nickname_validation_rejects_missing_blank_long_or_control_text(
    nickname: str | None,
) -> None:
    with pytest.raises(PvPError) as caught:
        normalize_guest_nickname(nickname)

    assert caught.value.code is PvPErrorCode.INVALID_NICKNAME


def test_guest_nickname_is_trimmed_and_accepts_unicode() -> None:
    assert normalize_guest_nickname("  Игрок 🤝  ") == "Игрок 🤝"


def test_room_full_and_unknown_room_fail_explicitly() -> None:
    service = service_for_seed()
    room, _creator, _joiner = create_started_room(service)

    with pytest.raises(PvPError) as full:
        service.join_room(room.invite_code, "Third")
    with pytest.raises(PvPError) as missing:
        service.get_room("not-a-room")

    assert full.value.code is PvPErrorCode.ROOM_FULL
    assert missing.value.code is PvPErrorCode.ROOM_NOT_FOUND


def test_two_concurrent_joins_can_only_claim_seat_two_once() -> None:
    service = service_for_seed()
    room, _creator = service.create_room("Creator")

    def join(name: str) -> str:
        try:
            service.join_room(room.invite_code, name)
        except PvPError as error:
            return error.code.value
        return "accepted"

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = tuple(executor.map(join, ("Friend A", "Friend B")))

    assert results.count("accepted") == 1
    assert results.count(PvPErrorCode.ROOM_FULL.value) == 1
    assert len(service.get_room(room.invite_code).participants) == 2


def test_action_versions_are_monotonic_and_concurrent_submission_commits_once() -> None:
    service = service_for_seed()
    room, creator, joiner = create_started_room(service)
    assert room.state is not None
    actor = acting_seat(room.state)
    participant = creator if actor is Seat.ONE else joiner
    selected = (room.state.hand(participant.seat)[0],)

    def submit() -> str:
        try:
            service.play_action(
                room.invite_code,
                participant.reconnect_token,
                HumanActionType.INITIAL_ATTACK,
                selected,
                expected_version=0,
            )
        except PvPActionError as error:
            return error.code.value
        return "accepted"

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = tuple(executor.map(lambda _index: submit(), range(2)))

    updated = service.get_room(room.invite_code)
    assert results.count("accepted") == 1
    assert results.count(PvPErrorCode.STALE_VERSION.value) == 1
    assert updated.version == 1
    assert len(updated.state.hand(participant.seat)) == 6


def test_wrong_turn_illegal_action_and_stale_version_do_not_mutate_room() -> None:
    service = service_for_seed()
    room, creator, joiner = create_started_room(service)
    assert room.state is not None
    actor = acting_seat(room.state)
    wrong = joiner if actor is Seat.ONE else creator
    right = creator if actor is Seat.ONE else joiner

    with pytest.raises(PvPActionError) as wrong_turn:
        service.play_action(
            room.invite_code,
            wrong.reconnect_token,
            HumanActionType.INITIAL_ATTACK,
            (room.state.hand(wrong.seat)[0],),
            expected_version=0,
        )
    with pytest.raises(PvPActionError) as illegal:
        service.play_action(
            room.invite_code,
            right.reconnect_token,
            HumanActionType.INITIAL_ATTACK,
            (),
            expected_version=0,
        )

    assert wrong_turn.value.code is PvPErrorCode.WRONG_TURN
    assert illegal.value.code is PvPErrorCode.ILLEGAL_ACTION
    assert service.get_room(room.invite_code) is room


def test_disconnect_and_reconnect_preserve_version_and_authoritative_state() -> None:
    service = service_for_seed()
    room, creator, _joiner = create_started_room(service)
    connected = service.connect(room.invite_code, creator.reconnect_token, "socket-one")
    original_state = connected.room.state

    disconnected = service.disconnect(room.invite_code, creator.participant_id, "socket-one")
    reconnected = service.connect(room.invite_code, creator.reconnect_token, "socket-two")

    assert disconnected.participant(Seat.ONE).connected is False
    assert reconnected.participant.connected is True
    assert reconnected.room.state is original_state
    assert reconnected.room.version == 0


def test_current_actor_can_continue_while_opponent_is_disconnected() -> None:
    service = service_for_seed()
    room, creator, joiner = create_started_room(service)
    assert room.state is not None
    actor = acting_seat(room.state)
    participant = creator if actor is Seat.ONE else joiner
    opponent = joiner if actor is Seat.ONE else creator
    service.connect(room.invite_code, participant.reconnect_token, "actor-socket")
    service.connect(room.invite_code, opponent.reconnect_token, "opponent-socket")
    service.disconnect(room.invite_code, opponent.participant_id, "opponent-socket")

    updated = service.play_action(
        room.invite_code,
        participant.reconnect_token,
        HumanActionType.INITIAL_ATTACK,
        (room.state.hand(participant.seat)[0],),
        expected_version=0,
    )

    assert updated.version == 1
    assert updated.participant(opponent.seat).connected is False


def test_new_connection_replaces_old_identity_without_old_disconnect_winning() -> None:
    service = service_for_seed()
    room, creator, _joiner = create_started_room(service)
    service.connect(room.invite_code, creator.reconnect_token, "old")

    replacement = service.connect(room.invite_code, creator.reconnect_token, "new")
    after_old_disconnect = service.disconnect(room.invite_code, creator.participant_id, "old")

    assert replacement.replaced_connection_id == "old"
    assert after_old_disconnect.participant(Seat.ONE).connection_id == "new"


def test_waiting_room_expiry_is_lazy_and_connected_room_is_preserved() -> None:
    current = [datetime(2026, 8, 27, tzinfo=UTC)]
    service = service_for_seed(
        clock=lambda: current[0],
        ttl=RoomTTLPolicy(
            waiting=timedelta(minutes=5),
            complete=timedelta(minutes=5),
            disconnected_active=timedelta(minutes=5),
        ),
    )
    room, creator = service.create_room("Creator")
    service.connect(room.invite_code, creator.reconnect_token, "socket")
    current[0] += timedelta(hours=1)

    assert service.get_room(room.invite_code).phase is PvPRoomPhase.WAITING_FOR_OPPONENT

    service.disconnect(room.invite_code, creator.participant_id, "socket")
    current[0] += timedelta(minutes=6)
    with pytest.raises(PvPError) as expired:
        service.get_room(room.invite_code)

    assert expired.value.code is PvPErrorCode.INVITE_EXPIRED
