from __future__ import annotations

import random
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from kiba_api.api.pvp_serialization import serialize_pvp_state
from kiba_api.game import (
    BotActionType,
    Card,
    GamePhase,
    GameState,
    Rank,
    Seat,
    Suit,
    choose_bot_action,
    create_new_game,
)
from kiba_api.pvp import (
    PvPActionError,
    PvPError,
    PvPErrorCode,
    PvPParticipantCompletion,
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


def tiny_game() -> GameState:
    return GameState(
        seat_one_hand=(Card(Rank.ACE, Suit.CLUBS),),
        seat_two_hand=(Card(Rank.SIX, Suit.CLUBS),),
        draw_pile=(),
        discard_pile=(),
        current_attacker=Seat.ONE,
    )


def complete_tiny_room(service: PvPRoomService):
    room, creator, joiner = create_started_room(service)
    attacked = service.play_action(
        room.invite_code,
        creator.reconnect_token,
        HumanActionType.INITIAL_ATTACK,
        (Card(Rank.ACE, Suit.CLUBS),),
        expected_version=room.version,
    )
    complete = service.play_action(
        room.invite_code,
        joiner.reconnect_token,
        HumanActionType.TAKE,
        expected_version=attacked.version,
    )
    return complete, creator, joiner


def complete_room_with_policy(service: PvPRoomService, invite_code: str) -> PvPRoomPhase:
    mapping = {
        BotActionType.INITIAL_ATTACK: HumanActionType.INITIAL_ATTACK,
        BotActionType.DEFEND: HumanActionType.DEFEND,
        BotActionType.TRANSFER: HumanActionType.TRANSFER,
        BotActionType.THROW_IN: HumanActionType.THROW_IN,
        BotActionType.TAKE: HumanActionType.TAKE,
        BotActionType.BITO: HumanActionType.BITO,
    }
    for _action_count in range(1000):
        room = service.get_room(invite_code)
        assert room.state is not None
        if room.state.phase is GamePhase.COMPLETE:
            return room.phase
        actor = acting_seat(room.state)
        assert actor is not None
        action = choose_bot_action(room.state, actor)
        service.play_action(
            invite_code,
            room.participant(actor).reconnect_token,
            mapping[action.action_type],
            action.cards,
            expected_version=room.version,
        )
    pytest.fail("PvP match exceeded the defensive action bound")


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


def test_private_pvp_routes_same_rank_extended_transfer_authoritatively() -> None:
    seven_one = Card(Rank.SEVEN, Suit.CLUBS)
    seven_two = Card(Rank.SEVEN, Suit.DIAMONDS)
    attack_seven = Card(Rank.SEVEN, Suit.HEARTS)

    def transfer_game() -> GameState:
        return GameState(
            seat_one_hand=(seven_one, seven_two, Card(Rank.SIX, Suit.CLUBS)),
            seat_two_hand=(
                attack_seven,
                Card(Rank.EIGHT, Suit.CLUBS),
                Card(Rank.NINE, Suit.CLUBS),
                Card(Rank.TEN, Suit.CLUBS),
                Card(Rank.JACK, Suit.CLUBS),
            ),
            draw_pile=(),
            discard_pile=(),
            current_attacker=Seat.TWO,
        )

    service = PvPRoomService(game_factory=transfer_game, token_factory=TokenFactory())
    room, creator, joiner = create_started_room(service)
    attacked = service.play_action(
        room.invite_code,
        joiner.reconnect_token,
        HumanActionType.INITIAL_ATTACK,
        (attack_seven,),
        expected_version=0,
    )
    transferred = service.play_action(
        room.invite_code,
        creator.reconnect_token,
        HumanActionType.TRANSFER,
        (seven_one, seven_two),
        expected_version=attacked.version,
    )

    assert transferred.state is not None
    assert transferred.state.active_bout is not None
    assert transferred.state.active_bout.active_packet is not None
    assert transferred.state.active_bout.active_packet.attack_value == 21
    assert transferred.state.active_bout.attacker is Seat.ONE


def test_authoritative_completion_records_once_and_reconnect_reuses_result() -> None:
    completions = []

    def tiny_game() -> GameState:
        return GameState(
            seat_one_hand=(Card(Rank.ACE, Suit.CLUBS),),
            seat_two_hand=(Card(Rank.SIX, Suit.CLUBS),),
            draw_pile=(),
            discard_pile=(),
            current_attacker=Seat.ONE,
        )

    def record(room):
        completions.append(room.room_id)
        return tuple(
            PvPParticipantCompletion(value.participant_id, False) for value in room.participants
        )

    service = PvPRoomService(
        game_factory=tiny_game,
        token_factory=TokenFactory(),
        completion_recorder=record,
    )
    room, creator, _joiner = create_started_room(service)

    attacked = service.play_action(
        room.invite_code,
        creator.reconnect_token,
        HumanActionType.INITIAL_ATTACK,
        (Card(Rank.ACE, Suit.CLUBS),),
        expected_version=0,
    )
    complete = service.play_action(
        room.invite_code,
        _joiner.reconnect_token,
        HumanActionType.TAKE,
        expected_version=attacked.version,
    )
    service.get_room(room.invite_code)
    service.authenticate(room.invite_code, creator.reconnect_token)

    assert complete.phase is PvPRoomPhase.COMPLETE
    assert completions == [room.room_id]
    assert complete.action_summary(Seat.ONE).action_count == 1
    assert complete.action_summary(Seat.TWO).take_count == 1


def test_rematch_consent_is_relative_and_starts_fresh_game_in_same_room() -> None:
    completions: list[str] = []

    def record(room):
        assert room.match_id is not None
        completions.append(room.match_id)
        return tuple(
            PvPParticipantCompletion(value.participant_id, False) for value in room.participants
        )

    service = PvPRoomService(
        game_factory=tiny_game,
        token_factory=TokenFactory(),
        completion_recorder=record,
    )
    complete, creator, joiner = complete_tiny_room(service)
    old_match_id = complete.match_id
    old_result = complete.state.result if complete.state is not None else None
    requested = service.request_rematch(
        complete.invite_code,
        creator.reconnect_token,
        match_id=old_match_id or "",
        expected_version=complete.version,
    )

    assert serialize_pvp_state(requested, creator).rematch_status == "WAITING"
    assert serialize_pvp_state(requested, joiner).rematch_status == "INCOMING"
    assert requested.state is not None and requested.state.result == old_result
    assert completions == [old_match_id]

    started = service.request_rematch(
        requested.invite_code,
        joiner.reconnect_token,
        match_id=old_match_id or "",
        expected_version=requested.version,
    )

    assert started.room_id == complete.room_id
    assert started.invite_code == complete.invite_code
    assert started.participants == complete.participants
    assert started.match_id is not None and started.match_id != old_match_id
    assert started.phase is PvPRoomPhase.GAME_ACTIVE
    assert started.state is not None
    assert started.state.phase is GamePhase.BOUT_ACTIVE
    assert started.state.result is None
    assert started.last_bout is None
    assert started.completion_results == ()
    assert started.rematch_acceptances == ()
    assert started.action_summary(Seat.ONE).action_count == 0
    assert started.action_summary(Seat.TWO).action_count == 0
    assert completions == [old_match_id]


def test_classic_rematch_waits_only_while_required_completion_is_pending() -> None:
    persistence_settled = False
    persistence_attempts: list[str | None] = []

    def record(room):
        persistence_attempts.append(room.match_id)
        if not persistence_settled:
            return ()
        return tuple(
            PvPParticipantCompletion(participant.participant_id, False)
            for participant in room.participants
        )

    service = PvPRoomService(
        game_factory=tiny_game,
        token_factory=TokenFactory(),
        completion_recorder=record,
    )
    complete, creator, joiner = complete_tiny_room(service)
    assert complete.match_id is not None
    assert complete.completion_results == ()

    with pytest.raises(PvPActionError) as pending:
        service.request_rematch(
            complete.invite_code,
            creator.reconnect_token,
            match_id=complete.match_id,
            expected_version=complete.version,
        )

    assert pending.value.code is PvPErrorCode.REMATCH_NOT_AVAILABLE
    assert pending.value.domain_code == "completion_pending"
    assert service.get_room(complete.invite_code).rematch_acceptances == ()

    persistence_settled = True
    requested = service.request_rematch(
        complete.invite_code,
        creator.reconnect_token,
        match_id=complete.match_id,
        expected_version=complete.version,
    )
    restarted = service.request_rematch(
        complete.invite_code,
        joiner.reconnect_token,
        match_id=complete.match_id,
        expected_version=requested.version,
    )

    assert requested.completion_results
    assert restarted.phase is PvPRoomPhase.GAME_ACTIVE
    assert restarted.match_id != complete.match_id
    assert persistence_attempts.count(complete.match_id) >= 2


def test_rematch_uses_the_canonical_fresh_36_card_bootstrap() -> None:
    rng = random.Random(90210)
    created: list[GameState] = []

    def fresh_game() -> GameState:
        state = create_new_game(rng)
        created.append(state)
        return state

    service = PvPRoomService(game_factory=fresh_game, token_factory=TokenFactory())
    room, creator, joiner = create_started_room(service)
    assert complete_room_with_policy(service, room.invite_code) is PvPRoomPhase.COMPLETE
    complete = service.get_room(room.invite_code)
    assert complete.match_id is not None
    requested = service.request_rematch(
        room.invite_code,
        creator.reconnect_token,
        match_id=complete.match_id,
        expected_version=complete.version,
    )
    started = service.request_rematch(
        room.invite_code,
        joiner.reconnect_token,
        match_id=complete.match_id,
        expected_version=requested.version,
    )

    assert len(created) == 2
    assert created[0].seat_one_hand + created[0].seat_two_hand + created[0].draw_pile != (
        created[1].seat_one_hand + created[1].seat_two_hand + created[1].draw_pile
    )
    assert started.state is not None and started.state.active_bout is not None
    assert len(started.state.seat_one_hand) == 7
    assert len(started.state.seat_two_hand) == 7
    assert len(started.state.draw_pile) == 22
    assert started.state.draw_pile[0] == created[1].draw_pile[0]
    assert started.state.current_trump_state == created[1].current_trump_state
    assert started.initial_attacker == created[1].current_attacker
    assert started.state.active_bout.attacker == created[1].current_attacker
    assert started.state.active_bout.table_cards == ()
    assert started.state.discard_pile == ()
    assert started.state.result is None


def test_simultaneous_rematch_requests_start_exactly_one_new_match() -> None:
    game_count = 0

    def counted_game() -> GameState:
        nonlocal game_count
        game_count += 1
        return tiny_game()

    service = PvPRoomService(game_factory=counted_game, token_factory=TokenFactory())
    complete, creator, joiner = complete_tiny_room(service)
    assert complete.match_id is not None

    def request(token: str):
        return service.request_rematch(
            complete.invite_code,
            token,
            match_id=complete.match_id or "",
            expected_version=complete.version,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = tuple(executor.map(request, (creator.reconnect_token, joiner.reconnect_token)))

    final = service.get_room(complete.invite_code)
    assert game_count == 2
    assert sum(value.phase is PvPRoomPhase.GAME_ACTIVE for value in results) == 1
    assert final.phase is PvPRoomPhase.GAME_ACTIVE
    assert final.match_id != complete.match_id
    assert final.version == complete.version + 2


def test_duplicate_rematch_request_is_idempotent_and_old_match_cannot_restart() -> None:
    service = PvPRoomService(game_factory=tiny_game, token_factory=TokenFactory())
    complete, creator, joiner = complete_tiny_room(service)
    assert complete.match_id is not None
    requested = service.request_rematch(
        complete.invite_code,
        creator.reconnect_token,
        match_id=complete.match_id,
        expected_version=complete.version,
    )
    duplicate = service.request_rematch(
        complete.invite_code,
        creator.reconnect_token,
        match_id=complete.match_id,
        expected_version=complete.version,
    )

    assert duplicate is requested
    assert duplicate.version == requested.version
    started = service.request_rematch(
        complete.invite_code,
        joiner.reconnect_token,
        match_id=complete.match_id,
        expected_version=requested.version,
    )
    with pytest.raises(PvPActionError) as stale_match:
        service.request_rematch(
            complete.invite_code,
            creator.reconnect_token,
            match_id=complete.match_id,
            expected_version=started.version,
        )

    assert stale_match.value.code is PvPErrorCode.REMATCH_NOT_AVAILABLE


def test_rematch_decline_cancel_reconnect_and_completed_exit_are_explicit() -> None:
    service = PvPRoomService(game_factory=tiny_game, token_factory=TokenFactory())
    complete, creator, joiner = complete_tiny_room(service)
    assert complete.match_id is not None
    service.connect(complete.invite_code, creator.reconnect_token, "creator-socket")
    service.connect(complete.invite_code, joiner.reconnect_token, "joiner-socket")
    requested = service.request_rematch(
        complete.invite_code,
        creator.reconnect_token,
        match_id=complete.match_id,
        expected_version=complete.version,
    )
    disconnected = service.disconnect(
        complete.invite_code,
        creator.participant_id,
        "creator-socket",
    )
    reconnected = service.connect(
        complete.invite_code,
        creator.reconnect_token,
        "creator-reconnected",
    )

    assert disconnected.rematch_acceptances == requested.rematch_acceptances
    assert reconnected.room.rematch_acceptances == requested.rematch_acceptances
    cancelled = service.cancel_rematch(
        complete.invite_code,
        creator.reconnect_token,
        match_id=complete.match_id,
        expected_version=requested.version,
    )
    assert cancelled.rematch_acceptances == ()

    requested_again = service.request_rematch(
        complete.invite_code,
        creator.reconnect_token,
        match_id=complete.match_id,
        expected_version=cancelled.version,
    )
    declined = service.decline_rematch(
        complete.invite_code,
        joiner.reconnect_token,
        match_id=complete.match_id,
        expected_version=requested_again.version,
    )
    assert serialize_pvp_state(declined, creator).rematch_status == "DECLINED"
    assert serialize_pvp_state(declined, joiner).rematch_status == "NONE"
    assert declined.state is not None and declined.state.result is not None

    closed = service.leave_room(
        complete.invite_code,
        creator.reconnect_token,
        "creator-reconnected",
    )
    assert closed.phase is PvPRoomPhase.CLOSED
    assert closed.rematch_acceptances == ()
    assert closed.rematch_declined_by is None


def test_rematch_rejects_active_game_wrong_match_and_outsider() -> None:
    service = PvPRoomService(game_factory=tiny_game, token_factory=TokenFactory())
    room, creator, _joiner = create_started_room(service)
    assert room.match_id is not None
    with pytest.raises(PvPActionError) as active:
        service.request_rematch(
            room.invite_code,
            creator.reconnect_token,
            match_id=room.match_id,
            expected_version=room.version,
        )
    with pytest.raises(PvPError) as outsider:
        service.request_rematch(
            room.invite_code,
            "not-a-participant",
            match_id=room.match_id,
            expected_version=room.version,
        )

    assert active.value.code is PvPErrorCode.REMATCH_NOT_AVAILABLE
    assert outsider.value.code is PvPErrorCode.INVALID_CREDENTIAL


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


def test_explicit_leave_closes_room_without_result_and_revokes_reconnect() -> None:
    completions: list[str] = []

    def record(room):
        completions.append(room.room_id)
        return ()

    service = service_for_seed(completion_recorder=record)
    room, creator, joiner = create_started_room(service)
    service.connect(room.invite_code, creator.reconnect_token, "creator-socket")
    service.connect(room.invite_code, joiner.reconnect_token, "joiner-socket")

    closed = service.leave_room(
        room.invite_code,
        creator.reconnect_token,
        "creator-socket",
    )

    assert closed.phase is PvPRoomPhase.CLOSED
    assert closed.version == room.version + 1
    assert closed.state is room.state
    assert closed.completion_results == ()
    assert all(not participant.connected for participant in closed.participants)
    assert completions == []
    with pytest.raises(PvPError) as creator_reconnect:
        service.connect(room.invite_code, creator.reconnect_token, "new-socket")
    with pytest.raises(PvPError) as joiner_reconnect:
        service.connect(room.invite_code, joiner.reconnect_token, "new-socket")
    assert creator_reconnect.value.code is PvPErrorCode.ROOM_CLOSED
    assert joiner_reconnect.value.code is PvPErrorCode.ROOM_CLOSED


def test_stale_replaced_socket_cannot_close_room() -> None:
    service = service_for_seed()
    room, creator, _joiner = create_started_room(service)
    service.connect(room.invite_code, creator.reconnect_token, "old-socket")
    service.connect(room.invite_code, creator.reconnect_token, "current-socket")

    with pytest.raises(PvPError) as caught:
        service.leave_room(room.invite_code, creator.reconnect_token, "old-socket")

    assert caught.value.code is PvPErrorCode.INVALID_CREDENTIAL
    assert service.get_room(room.invite_code).phase is PvPRoomPhase.GAME_ACTIVE


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
