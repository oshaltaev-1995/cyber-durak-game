"""Explicit translation from domain/session snapshots to public REST state."""

from fractions import Fraction

from kiba_api.api.cards import card_to_code
from kiba_api.api.schemas import (
    CardResponse,
    GameResponse,
    PacketResponse,
    ResultResponse,
    TableArithmeticResponse,
    ThrowInReasonResponse,
    TrumpResponse,
)
from kiba_api.game import (
    AttackPacket,
    BoutPhase,
    BoutState,
    Card,
    GameOutcome,
    GamePhase,
    Rank,
    Seat,
    Suit,
    ThrowInReason,
    TrumpState,
    analyze_throw_in,
    get_base_value,
    get_effective_value,
    is_trump,
    summarize_table_arithmetic,
)
from kiba_api.sessions import GameSession, HumanActionType

_SUIT_ORDER = {suit: index for index, suit in enumerate(Suit)}
_RANK_ORDER = {rank: index for index, rank in enumerate(Rank)}
_THROW_IN_REASON_ORDER = (
    ThrowInReason.SAME_RANK,
    ThrowInReason.EXISTING_VALUE,
    ThrowInReason.TABLE_TOTAL,
    ThrowInReason.ARITHMETIC_MEAN,
)


def serialize_game_session(session: GameSession) -> GameResponse:
    """Build one hidden-information-safe public state response."""
    state = session.state
    trump_state = state.current_trump_state
    active_bout = state.active_bout
    bout = active_bout or (session.last_bout if state.phase is GamePhase.COMPLETE else None)
    table_trump_state = bout.trump_state if bout is not None else trump_state
    table_cards = bout.table_cards if bout is not None else ()
    summary = summarize_table_arithmetic(table_cards, table_trump_state)
    actor = _acting_seat(session)

    packet_responses = _serialize_packets(bout, table_trump_state) if bout else []
    active_packet = bout.active_packet if bout is not None else None
    source_card = state.draw_pile[0] if state.draw_pile else None
    bout_phase = None
    if bout is not None:
        bout_phase = (
            BoutPhase.COMPLETE.value if state.phase is GamePhase.COMPLETE else bout.phase.value
        )

    return GameResponse(
        game_id=session.game_id,
        phase=state.phase.value,
        result=_serialize_result(session),
        human_seat=session.human_seat.value,
        bot_seat=session.bot_seat.value,
        human_hand=[
            _serialize_card(card, trump_state)
            for card in sorted(state.hand(session.human_seat), key=_presentation_card_key)
        ],
        bot_hand_count=len(state.hand(session.bot_seat)),
        draw_pile_count=len(state.draw_pile),
        exposed_top_card=(
            _serialize_card(source_card, trump_state) if source_card is not None else None
        ),
        trump=TrumpResponse(
            active=trump_state.active,
            source_card=(
                _serialize_card(source_card, trump_state) if source_card is not None else None
            ),
            trump_rank=(trump_state.trump_rank.value if trump_state.trump_rank else None),
            trump_suit=(trump_state.trump_suit.value if trump_state.trump_suit else None),
        ),
        discard_count=len(state.discard_pile),
        table_cards=[_serialize_card(card, table_trump_state) for card in table_cards],
        table_arithmetic=TableArithmeticResponse(
            total_effective_value=summary.total_effective_value,
            physical_card_count=summary.physical_card_count,
            arithmetic_mean=_format_fraction(summary.arithmetic_mean),
        ),
        attacker=(bout.attacker.value if bout is not None else None),
        defender=(bout.defender.value if bout is not None else None),
        bout_phase=bout_phase,
        packets=packet_responses,
        active_packet=(
            packet_responses[-1] if active_packet is not None and packet_responses else None
        ),
        direct_anchor_cards=(
            [_serialize_card(card, table_trump_state) for card in bout.direct_anchor_cards]
            if bout is not None
            else []
        ),
        active_attack_value=(active_packet.attack_value if active_packet is not None else None),
        attack_card_limit=(bout.attack_card_limit if bout is not None else None),
        total_attack_card_count=(bout.total_attack_card_count if bout is not None else None),
        transfer_open=(
            bout.transfer_open
            if active_bout is not None and state.phase is not GamePhase.COMPLETE
            else False
        ),
        required_actor=_actor_label(actor, session),
        required_seat=(actor.value if actor is not None else None),
        available_actions=_available_human_actions(session, actor),
    )


def _serialize_card(card: Card, trump_state: TrumpState) -> CardResponse:
    if card.suit is None:
        raise ValueError("Phase 3C1 public state supports only normal 36-card cards")
    return CardResponse(
        code=card_to_code(card),
        rank=card.rank.value,
        suit=card.suit.value,
        base_value=get_base_value(card),
        effective_value=get_effective_value(card, trump_state),
        is_trump=is_trump(card, trump_state),
    )


def _serialize_packets(bout: BoutState, trump_state: TrumpState) -> list[PacketResponse]:
    responses: list[PacketResponse] = []
    table_before: tuple[Card, ...] = ()
    direct_anchors: tuple[Card, ...] = ()
    for index, packet in enumerate(bout.packets):
        reasons = (
            []
            if index == 0
            else _serialize_throw_in_reasons(
                packet.attack_cards,
                table_before,
                direct_anchors,
                trump_state,
            )
        )
        responses.append(_serialize_packet(packet, trump_state, reasons))
        table_before += packet.attack_cards + (packet.defense_cards or ())
        if packet.defense_cards is not None:
            direct_anchors = packet.defense_cards
    return responses


def _serialize_packet(
    packet: AttackPacket,
    trump_state: TrumpState,
    throw_in_reasons: list[ThrowInReasonResponse],
) -> PacketResponse:
    return PacketResponse(
        attack_cards=[_serialize_card(card, trump_state) for card in packet.attack_cards],
        attack_value=packet.attack_value,
        defense_cards=[_serialize_card(card, trump_state) for card in packet.defense_cards or ()],
        defense_value=packet.defense_value,
        closed=packet.closed,
        throw_in_reasons=throw_in_reasons,
    )


def _serialize_throw_in_reasons(
    selected_cards: tuple[Card, ...],
    table_cards: tuple[Card, ...],
    direct_anchor_cards: tuple[Card, ...],
    trump_state: TrumpState,
) -> list[ThrowInReasonResponse]:
    analysis = analyze_throw_in(
        selected_cards,
        table_cards,
        direct_anchor_cards,
        trump_state,
    )
    summary = summarize_table_arithmetic(table_cards, trump_state)
    table_values = [get_effective_value(card, trump_state) for card in table_cards]

    responses: list[ThrowInReasonResponse] = []
    for reason in _THROW_IN_REASON_ORDER:
        if reason not in analysis.reasons:
            continue
        expression: str | None = None
        target_value: int | None = analysis.selected_value
        if reason is ThrowInReason.SAME_RANK:
            target_value = None
        elif reason is ThrowInReason.EXISTING_VALUE:
            matching_anchor = next(
                (
                    card
                    for card in direct_anchor_cards
                    if get_effective_value(card, trump_state) == analysis.selected_value
                ),
                None,
            )
            if matching_anchor is not None:
                expression = f"{card_to_code(matching_anchor)} = {analysis.selected_value}"
        elif reason is ThrowInReason.TABLE_TOTAL:
            expression = f"{' + '.join(map(str, table_values))} = {analysis.selected_value}"
        elif reason is ThrowInReason.ARITHMETIC_MEAN:
            expression = (
                f"{summary.total_effective_value} / {summary.physical_card_count}"
                f" = {analysis.selected_value}"
            )
        responses.append(
            ThrowInReasonResponse(
                type=reason.value,
                target_value=target_value,
                expression=expression,
            )
        )
    return responses


def _serialize_result(session: GameSession) -> ResultResponse | None:
    result = session.state.result
    if result is None:
        return None
    if result.outcome is GameOutcome.DRAW:
        return ResultResponse(outcome="DRAW", winner=None, winner_seat=None)
    return ResultResponse(
        outcome="WIN",
        winner="HUMAN" if result.winner is session.human_seat else "BOT",
        winner_seat=result.winner.value if result.winner is not None else None,
    )


def _acting_seat(session: GameSession) -> Seat | None:
    state = session.state
    if state.phase is GamePhase.COMPLETE:
        return None
    if state.phase is GamePhase.READY_FOR_BOUT:
        return state.current_attacker
    bout = state.active_bout
    if bout is None:
        raise ValueError("an active game requires an active bout")
    if bout.phase is BoutPhase.WAITING_FOR_DEFENDER_RESPONSE:
        return bout.defender
    return bout.attacker


def _actor_label(actor: Seat | None, session: GameSession) -> str | None:
    if actor is None:
        return None
    return "HUMAN" if actor is session.human_seat else "BOT"


def _available_human_actions(
    session: GameSession,
    actor: Seat | None,
) -> list[HumanActionType]:
    if actor is not session.human_seat:
        return []
    bout = session.state.active_bout
    if bout is None:
        return [HumanActionType.INITIAL_ATTACK]
    if bout.phase is BoutPhase.WAITING_FOR_INITIAL_ATTACK:
        return [HumanActionType.INITIAL_ATTACK]
    if bout.phase is BoutPhase.WAITING_FOR_DEFENDER_RESPONSE:
        actions = [HumanActionType.DEFEND]
        if bout.transfer_open:
            actions.append(HumanActionType.TRANSFER)
        actions.append(HumanActionType.TAKE)
        return actions
    if bout.phase is BoutPhase.WAITING_FOR_ATTACKER_DECISION:
        return [HumanActionType.THROW_IN, HumanActionType.BITO]
    return []


def _format_fraction(value: Fraction | None) -> str | None:
    if value is None:
        return None
    if value.denominator == 1:
        return str(value.numerator)
    return f"{value.numerator}/{value.denominator}"


def _presentation_card_key(card: Card) -> tuple[int, int]:
    suit_index = len(_SUIT_ORDER) if card.suit is None else _SUIT_ORDER[card.suit]
    return suit_index, _RANK_ORDER[card.rank]
