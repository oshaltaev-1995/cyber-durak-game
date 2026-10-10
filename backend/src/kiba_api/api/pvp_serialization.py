"""Participant-specific hidden-information-safe private room serialization."""

from kiba_api.api.pvp_schemas import (
    ParticipantCredentialResponse,
    ParticipantResponse,
    PlayerStateResponse,
    PvPResultResponse,
    PvPStateResponse,
    RoomJoinResponse,
    RoomStatusResponse,
)
from kiba_api.api.schemas import (
    BotPresentationEventResponse,
    TableArithmeticResponse,
    TrumpResponse,
)
from kiba_api.api.serialization import (
    _format_fraction,
    _presentation_card_key,
    _serialize_card,
    _serialize_last_bout_summary,
    _serialize_packets,
    serialize_progression_award,
)
from kiba_api.game import (
    BoutPhase,
    GameOutcome,
    GamePhase,
    Seat,
    seats_for_player_count,
    summarize_table_arithmetic,
)
from kiba_api.pvp import PvPParticipant, PvPRoom, PvPRoomPhase
from kiba_api.sessions import acting_seat, available_actions_for


def serialize_room_join(room: PvPRoom, participant: PvPParticipant) -> RoomJoinResponse:
    """Return the participant credential once alongside their private state view."""
    if participant.reconnect_token is None:
        raise ValueError("only human participants receive join credentials")
    return RoomJoinResponse(
        invite_code=room.invite_code,
        invite_path=f"/api/pvp/rooms/{room.invite_code}",
        credential=ParticipantCredentialResponse(
            participant_id=participant.participant_id,
            seat=participant.seat.value,
            reconnect_token=participant.reconnect_token,
        ),
        state=serialize_pvp_state(room, participant),
    )


def serialize_room_status(room: PvPRoom) -> RoomStatusResponse:
    """Return invitation metadata without any private credentials or cards."""
    return RoomStatusResponse(
        invite_code=room.invite_code,
        room_phase=room.phase.value,
        version=room.version,
        capacity=room.capacity,
        human_players=room.human_players,
        bot_count=room.bot_count,
        deck_profile=room.deck_config.profile,
        deck_count=room.deck_config.deck_count,
        joined_count=len(room.human_participants),
        human_joined_count=len(room.human_participants),
        participants=[_serialize_participant(value) for value in room.participants],
    )


def serialize_pvp_state(room: PvPRoom, viewer: PvPParticipant) -> PvPStateResponse:
    """Serialize one room strictly from the requesting participant's perspective."""
    opponent = (
        next((value for value in room.participants if value.seat is not viewer.seat), None)
        if room.capacity == 2
        else None
    )
    state = room.state
    completion = room.completion_for(viewer.participant_id)
    player_states = [_serialize_player(room, value, viewer) for value in room.participants]
    seat_order = [seat.value for seat in seats_for_player_count(room.capacity)]
    if state is None:
        return PvPStateResponse(
            invite_code=room.invite_code,
            match_id=room.match_id,
            room_phase=room.phase.value,
            version=room.version,
            capacity=room.capacity,
            human_players=room.human_players,
            bot_count=room.bot_count,
            deck_profile=room.deck_config.profile,
            deck_count=room.deck_config.deck_count,
            joined_count=len(room.human_participants),
            human_joined_count=len(room.human_participants),
            seat_order=seat_order,
            players=player_states,
            active_seats=[],
            finished_seats=[],
            finish_groups=[],
            rematch_status=_rematch_status(room, viewer),
            rematch_ready_count=len(room.rematch_acceptances),
            rematch_total_count=len(room.human_participants),
            rematch_requester_participant_id=(
                room.rematch_acceptances[0] if room.rematch_acceptances else None
            ),
            rematch_ready_participant_ids=_rematch_ready_participant_ids(room),
            you=_serialize_participant(viewer),
            opponent=_serialize_participant(opponent) if opponent else None,
            game_phase=None,
            result=None,
            result_saved=False,
            progression_award=None,
            last_bout_summary=None,
            hand=[],
            opponent_hand_count=None,
            draw_pile_count=0,
            exposed_top_card=None,
            trump=TrumpResponse(active=False, source_card=None, trump_rank=None, trump_suit=None),
            discard_count=0,
            table_cards=[],
            table_arithmetic=TableArithmeticResponse(
                total_effective_value=0,
                physical_card_count=0,
                arithmetic_mean=None,
            ),
            bout_starting_attacker=None,
            attacker=None,
            lead_attacker=None,
            defender=None,
            bout_phase=None,
            packets=[],
            active_packet=None,
            direct_anchor_cards=[],
            active_attack_value=None,
            attack_card_limit=None,
            max_attack_card_addition=None,
            total_attack_card_count=None,
            transfer_open=False,
            required_participant_id=None,
            required_seat=None,
            available_actions=[],
            recent_events=_serialize_bot_events(room),
        )

    trump_state = state.current_trump_state
    active_bout = state.active_bout
    bout = active_bout or (room.last_bout if state.phase is GamePhase.COMPLETE else None)
    table_trump = bout.trump_state if bout is not None else trump_state
    table_cards = bout.table_cards if bout is not None else ()
    summary = summarize_table_arithmetic(table_cards, table_trump)
    packets = _serialize_packets(bout, table_trump) if bout is not None else []
    active_packet = bout.active_packet if bout is not None else None
    source_card = state.draw_pile[0] if state.draw_pile else None
    room_closed = room.phase is PvPRoomPhase.CLOSED
    actor = None if room_closed else acting_seat(state)
    actor_participant = room.participant(actor) if actor is not None else None
    bout_phase = None
    if bout is not None:
        bout_phase = (
            BoutPhase.COMPLETE.value if state.phase is GamePhase.COMPLETE else bout.phase.value
        )

    return PvPStateResponse(
        invite_code=room.invite_code,
        match_id=room.match_id,
        room_phase=room.phase.value,
        version=room.version,
        capacity=room.capacity,
        human_players=room.human_players,
        bot_count=room.bot_count,
        deck_profile=room.deck_config.profile,
        deck_count=room.deck_config.deck_count,
        joined_count=len(room.human_participants),
        human_joined_count=len(room.human_participants),
        seat_order=seat_order,
        players=player_states,
        active_seats=[seat.value for seat in state.active_seats],
        finished_seats=[seat.value for seat in state.finished_seats],
        finish_groups=[[seat.value for seat in group] for group in state.finish_groups],
        rematch_status=_rematch_status(room, viewer),
        rematch_ready_count=len(room.rematch_acceptances),
        rematch_total_count=len(room.human_participants),
        rematch_requester_participant_id=(
            room.rematch_acceptances[0] if room.rematch_acceptances else None
        ),
        rematch_ready_participant_ids=_rematch_ready_participant_ids(room),
        you=_serialize_participant(viewer),
        opponent=_serialize_participant(opponent) if opponent else None,
        game_phase=state.phase.value,
        result=_serialize_result(room),
        result_saved=completion.saved if completion is not None else False,
        progression_award=(
            serialize_progression_award(
                completion.progression_award,
                viewer.preferred_locale,
            )
            if completion is not None
            else None
        ),
        last_bout_summary=_serialize_last_bout_summary(room.last_bout),
        hand=[
            _serialize_card(card, trump_state)
            for card in sorted(state.hand(viewer.seat), key=_presentation_card_key)
        ],
        opponent_hand_count=(len(state.hand(opponent.seat)) if opponent is not None else None),
        draw_pile_count=len(state.draw_pile),
        exposed_top_card=(
            _serialize_card(source_card, trump_state) if source_card is not None else None
        ),
        trump=TrumpResponse(
            active=trump_state.active,
            source_card=(
                _serialize_card(source_card, trump_state) if source_card is not None else None
            ),
            trump_rank=trump_state.trump_rank.value if trump_state.trump_rank else None,
            trump_suit=trump_state.trump_suit.value if trump_state.trump_suit else None,
        ),
        discard_count=len(state.discard_pile),
        table_cards=[_serialize_card(card, table_trump) for card in table_cards],
        table_arithmetic=TableArithmeticResponse(
            total_effective_value=summary.total_effective_value,
            physical_card_count=summary.physical_card_count,
            arithmetic_mean=_format_fraction(summary.arithmetic_mean),
        ),
        bout_starting_attacker=(
            state.bout_starting_attacker.value if state.bout_starting_attacker is not None else None
        ),
        attacker=bout.attacker.value if bout is not None else None,
        lead_attacker=bout.lead_attacker.value if bout is not None else None,
        defender=bout.defender.value if bout is not None else None,
        bout_phase=bout_phase,
        packets=packets,
        active_packet=packets[-1] if active_packet is not None and packets else None,
        direct_anchor_cards=(
            [_serialize_card(card, table_trump) for card in bout.direct_anchor_cards]
            if bout is not None
            else []
        ),
        active_attack_value=active_packet.attack_value if active_packet is not None else None,
        attack_card_limit=bout.attack_card_limit if bout is not None else None,
        max_attack_card_addition=bout.max_attack_card_addition if bout is not None else None,
        total_attack_card_count=bout.total_attack_card_count if bout is not None else None,
        transfer_open=(
            bout.transfer_open
            if active_bout is not None and state.phase is not GamePhase.COMPLETE and not room_closed
            else False
        ),
        required_participant_id=(
            actor_participant.participant_id if actor_participant is not None else None
        ),
        required_seat=actor.value if actor is not None else None,
        available_actions=([] if room_closed else list(available_actions_for(state, viewer.seat))),
        recent_events=_serialize_bot_events(room),
    )


def _serialize_participant(participant: PvPParticipant) -> ParticipantResponse:
    return ParticipantResponse(
        participant_id=participant.participant_id,
        seat=participant.seat.value,
        display_name=participant.display_name,
        connected=participant.connected,
        authenticated=participant.user_id is not None,
        is_bot=participant.is_bot,
    )


def _serialize_player(
    room: PvPRoom,
    participant: PvPParticipant,
    viewer: PvPParticipant,
) -> PlayerStateResponse:
    state = room.state
    return PlayerStateResponse(
        **_serialize_participant(participant).model_dump(),
        is_self=participant.participant_id == viewer.participant_id,
        hand_count=len(state.hand(participant.seat)) if state is not None else None,
        active=(state is not None and participant.seat in state.active_seats),
        finished=(state is not None and participant.seat in state.finished_seats),
    )


def _rematch_status(room: PvPRoom, viewer: PvPParticipant) -> str:
    """Return only the participant-relative consent state needed by the result UI."""
    if room.phase is not PvPRoomPhase.COMPLETE:
        return "NONE"
    if room.rematch_declined_by is not None and room.rematch_declined_by != viewer.participant_id:
        return "DECLINED"
    if viewer.participant_id in room.rematch_acceptances:
        return "WAITING"
    if room.rematch_acceptances:
        return "INCOMING"
    return "NONE"


def _rematch_ready_participant_ids(room: PvPRoom) -> list[str]:
    accepted = set(room.rematch_acceptances)
    return [
        participant.participant_id
        for participant in room.participants
        if participant.participant_id in accepted
    ]


def _serialize_bot_events(room: PvPRoom) -> list[BotPresentationEventResponse]:
    return [
        BotPresentationEventResponse(
            type=event.type.value,
            card_count=event.card_count,
            value=event.value,
            target=event.target,
            actor_seat=event.actor_seat.value,
        )
        for event in room.recent_events
    ]


def _serialize_result(room: PvPRoom) -> PvPResultResponse | None:
    state = room.state
    if state is None or state.result is None:
        return None
    if state.result.outcome is GameOutcome.DRAW:
        return PvPResultResponse(
            outcome="DRAW",
            winner_seat=None,
            winner_participant_id=None,
            winner_display_name=None,
        )
    winner = room.participant(state.result.winner or Seat.ONE)
    return PvPResultResponse(
        outcome="WIN",
        winner_seat=winner.seat.value,
        winner_participant_id=winner.participant_id,
        winner_display_name=winner.display_name,
    )
