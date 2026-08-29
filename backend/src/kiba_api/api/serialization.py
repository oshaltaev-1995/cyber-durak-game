"""Explicit translation from domain/session snapshots to public REST state."""

from __future__ import annotations

from fractions import Fraction
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kiba_api.persistence import ProgressionAward

from kiba_api.api.cards import card_to_code
from kiba_api.api.schemas import (
    AchievementAwardResponse,
    BotPresentationEventResponse,
    CardResponse,
    CosmeticAwardResponse,
    CosmeticLoadoutResponse,
    GameResponse,
    PacketResponse,
    ProgressionAwardResponse,
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
from kiba_api.sessions import GameSession, acting_seat, available_actions_for

_SUIT_ORDER = {suit: index for index, suit in enumerate(Suit)}
_RANK_ORDER = {rank: index for index, rank in enumerate(Rank)}
_THROW_IN_REASON_ORDER = (
    ThrowInReason.SAME_RANK,
    ThrowInReason.EXISTING_VALUE,
    ThrowInReason.DEFENSE_TOTAL,
    ThrowInReason.TABLE_TOTAL,
    ThrowInReason.ARITHMETIC_MEAN,
    ThrowInReason.RANK_RUN,
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
    actor = acting_seat(state)

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
        account_associated=session.user_id is not None,
        result_saved=session.completion_persisted,
        progression_award=serialize_progression_award(session.progression_award),
        cosmetics=CosmeticLoadoutResponse(
            card_back_code=session.appearance.card_back_code,
            table_theme_code=session.appearance.table_theme_code,
            profile_frame_code=session.appearance.profile_frame_code,
        ),
        recent_events=[
            BotPresentationEventResponse(
                type=event.type.value,
                card_count=event.card_count,
                value=event.value,
                target=event.target,
            )
            for event in session.recent_events
        ],
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
        available_actions=list(available_actions_for(state, session.human_seat)),
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
        run_start: str | None = None
        run_end: str | None = None
        run_length: int | None = None
        run_ranks: list[str] | None = None
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
        elif reason is ThrowInReason.DEFENSE_TOTAL:
            defense_values = [
                get_effective_value(card, trump_state) for card in direct_anchor_cards
            ]
            expression = f"{' + '.join(map(str, defense_values))} = {analysis.selected_value}"
        elif reason is ThrowInReason.TABLE_TOTAL:
            expression = f"{' + '.join(map(str, table_values))} = {analysis.selected_value}"
        elif reason is ThrowInReason.ARITHMETIC_MEAN:
            expression = (
                f"{summary.total_effective_value} / {summary.physical_card_count}"
                f" = {analysis.selected_value}"
            )
        elif reason is ThrowInReason.RANK_RUN:
            target_value = None
            if analysis.rank_run is None:
                raise ValueError("rank_run reason requires rank-run metadata")
            run_start = analysis.rank_run.start.value
            run_end = analysis.rank_run.end.value
            run_length = analysis.rank_run.length
            run_ranks = [rank.value for rank in analysis.rank_run.ranks]
            expression = f"{run_start}–{run_end}"
        responses.append(
            ThrowInReasonResponse(
                type=reason.value,
                target_value=target_value,
                expression=expression,
                run_start=run_start,
                run_end=run_end,
                run_length=run_length,
                run_ranks=run_ranks,
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


def serialize_progression_award(award: ProgressionAward | None) -> ProgressionAwardResponse | None:
    """Translate one participant's private progression delta for HTTP delivery."""
    if award is None:
        return None
    return ProgressionAwardResponse(
        base_xp=award.base_xp,
        achievement_bonus_xp=award.achievement_bonus_xp,
        total_awarded_xp=award.total_awarded_xp,
        new_achievements=[
            AchievementAwardResponse(
                code=achievement.code.value,
                title=achievement.title,
                description=achievement.description,
                bonus_xp=achievement.bonus_xp,
            )
            for achievement in award.new_achievements
        ],
        total_xp=award.summary.total_xp,
        level=award.summary.level,
        next_level_xp=award.summary.next_level_xp,
        xp_needed_for_next_level=award.summary.xp_needed_for_next_level,
        new_cosmetics=[
            CosmeticAwardResponse(
                code=cosmetic.code,
                category=cosmetic.category,
                title=cosmetic.title,
            )
            for cosmetic in award.new_cosmetics
        ],
    )


def _actor_label(actor: Seat | None, session: GameSession) -> str | None:
    if actor is None:
        return None
    return "HUMAN" if actor is session.human_seat else "BOT"


def _format_fraction(value: Fraction | None) -> str | None:
    if value is None:
        return None
    if value.denominator == 1:
        return str(value.numerator)
    return f"{value.numerator}/{value.denominator}"


def _presentation_card_key(card: Card) -> tuple[int, int]:
    suit_index = len(_SUIT_ORDER) if card.suit is None else _SUIT_ORDER[card.suit]
    return suit_index, _RANK_ORDER[card.rank]
