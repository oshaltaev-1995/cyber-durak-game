from collections.abc import Callable
from dataclasses import FrozenInstanceError
from fractions import Fraction

import pytest

from kiba_api.game import (
    AttackPacket,
    BoutActionError,
    BoutErrorCode,
    BoutOutcome,
    BoutPhase,
    BoutState,
    Card,
    Rank,
    Seat,
    Suit,
    ThrowInReason,
    TrumpState,
    analyze_throw_in,
    finish_bout,
    get_throw_in_targets,
    play_defense,
    play_initial_attack,
    play_throw_in,
    play_transfer,
    summarize_table_arithmetic,
    take,
)

NO_TRUMP = TrumpState.no_trump()


def card(rank: Rank, suit: Suit = Suit.CLUBS) -> Card:
    return Card(rank=rank, suit=suit)


def start_bout(
    *,
    attacker: Seat = Seat.ONE,
    seat_one_hand_count: int = 7,
    seat_two_hand_count: int = 7,
    trump_state: TrumpState = NO_TRUMP,
) -> BoutState:
    return BoutState.start(
        attacker=attacker,
        seat_one_hand_count=seat_one_hand_count,
        seat_two_hand_count=seat_two_hand_count,
        trump_state=trump_state,
    )


def covered_jack() -> BoutState:
    state = play_initial_attack(start_bout(), Seat.ONE, [card(Rank.JACK)])
    return play_defense(state, Seat.TWO, [card(Rank.KING)])


def assert_bout_error(
    code: BoutErrorCode,
    action: Callable[..., BoutState],
    *args: object,
) -> None:
    with pytest.raises(BoutActionError) as caught:
        action(*args)
    assert caught.value.code is code


def test_bout_creation_assigns_two_seats_and_initial_state() -> None:
    trump_state = TrumpState.from_source_card(card(Rank.NINE, Suit.HEARTS))

    state = start_bout(
        attacker=Seat.TWO,
        seat_one_hand_count=5,
        seat_two_hand_count=6,
        trump_state=trump_state,
    )

    assert state.attacker is Seat.TWO
    assert state.defender is Seat.ONE
    assert state.hand_count(Seat.ONE) == 5
    assert state.hand_count(Seat.TWO) == 6
    assert state.trump_state is trump_state
    assert state.phase is BoutPhase.WAITING_FOR_INITIAL_ATTACK
    assert state.packets == ()
    assert state.active_packet is None
    assert state.table_cards == ()
    assert state.direct_anchor_cards == ()
    assert state.attack_card_limit == 5
    assert state.max_attack_card_addition == 5
    assert state.total_attack_card_count == 0
    assert state.transfer_open is True
    assert state.outcome is None


@pytest.mark.parametrize("hand_count", [-1, 1.5, True])
def test_bout_creation_rejects_invalid_hand_counts(hand_count: object) -> None:
    error = TypeError if isinstance(hand_count, (float, bool)) else ValueError
    with pytest.raises(error):
        start_bout(seat_one_hand_count=hand_count)  # type: ignore[arg-type]


def test_legal_initial_attack_creates_active_packet_and_spends_cards() -> None:
    selected = [card(Rank.KING), card(Rank.NINE), card(Rank.NINE, Suit.DIAMONDS)]

    state = play_initial_attack(start_bout(), Seat.ONE, selected)

    assert state.phase is BoutPhase.WAITING_FOR_DEFENDER_RESPONSE
    assert state.hand_count(Seat.ONE) == 4
    assert state.hand_count(Seat.TWO) == 7
    assert state.total_attack_card_count == 3
    assert state.table_cards == tuple(selected)
    assert state.active_packet == AttackPacket(tuple(selected), 36)
    assert state.transfer_target == 36


def test_illegal_initial_attack_is_rejected() -> None:
    state = start_bout()

    assert_bout_error(
        BoutErrorCode.ILLEGAL_INITIAL_ATTACK,
        play_initial_attack,
        state,
        Seat.ONE,
        [card(Rank.NINE), card(Rank.SEVEN)],
    )


def test_initial_attack_rejects_wrong_actor() -> None:
    assert_bout_error(
        BoutErrorCode.WRONG_ACTOR,
        play_initial_attack,
        start_bout(),
        Seat.TWO,
        [card(Rank.KING)],
    )


def test_initial_attack_rejects_more_cards_than_actor_count() -> None:
    state = start_bout(seat_one_hand_count=1)

    assert_bout_error(
        BoutErrorCode.NOT_ENOUGH_CARDS,
        play_initial_attack,
        state,
        Seat.ONE,
        [card(Rank.NINE), card(Rank.NINE, Suit.DIAMONDS)],
    )


def test_initial_attack_obeys_starting_defender_card_limit() -> None:
    state = start_bout(seat_two_hand_count=2)

    assert_bout_error(
        BoutErrorCode.ATTACK_CARD_LIMIT_EXCEEDED,
        play_initial_attack,
        state,
        Seat.ONE,
        [card(Rank.KING), card(Rank.NINE), card(Rank.NINE, Suit.DIAMONDS)],
    )


def test_exact_transfer_extends_same_packet_swaps_roles_and_resets_limit() -> None:
    state = play_initial_attack(start_bout(), Seat.ONE, [card(Rank.KING)])
    transfer_cards = [card(Rank.NINE), card(Rank.NINE, Suit.DIAMONDS)]

    transferred = play_transfer(state, Seat.TWO, transfer_cards)

    assert len(transferred.packets) == 1
    assert transferred.active_packet == AttackPacket(
        (card(Rank.KING), *transfer_cards),
        36,
    )
    assert transferred.attacker is Seat.TWO
    assert transferred.defender is Seat.ONE
    assert transferred.hand_count(Seat.ONE) == 6
    assert transferred.hand_count(Seat.TWO) == 5
    assert transferred.total_attack_card_count == 3
    assert transferred.attack_card_limit == 6
    assert transferred.transfer_target == 36
    assert transferred.transfer_open is True


def test_same_rank_extended_transfer_adds_every_selected_card_to_packet() -> None:
    attack = card(Rank.SEVEN)
    transfer_cards = (card(Rank.SEVEN, Suit.DIAMONDS), card(Rank.SEVEN, Suit.HEARTS))
    state = play_initial_attack(start_bout(), Seat.ONE, [attack])

    transferred = play_transfer(state, Seat.TWO, transfer_cards)

    assert transferred.active_packet == AttackPacket((attack, *transfer_cards), 21)
    assert transferred.transfer_target == 21
    assert transferred.total_attack_card_count == 3
    assert transferred.attacker is Seat.TWO
    assert transferred.defender is Seat.ONE


def test_same_rank_extended_transfer_still_obeys_new_defender_limit() -> None:
    state = play_initial_attack(
        start_bout(seat_one_hand_count=2),
        Seat.ONE,
        [card(Rank.SEVEN)],
    )

    assert_bout_error(
        BoutErrorCode.ATTACK_CARD_LIMIT_EXCEEDED,
        play_transfer,
        state,
        Seat.TWO,
        [card(Rank.SEVEN, Suit.DIAMONDS), card(Rank.SEVEN, Suit.HEARTS)],
    )


def test_transfer_rejects_wrong_exact_value() -> None:
    state = play_initial_attack(start_bout(), Seat.ONE, [card(Rank.KING)])

    assert_bout_error(
        BoutErrorCode.ILLEGAL_TRANSFER,
        play_transfer,
        state,
        Seat.TWO,
        [card(Rank.NINE), card(Rank.EIGHT)],
    )


def test_transfer_rejects_wrong_actor() -> None:
    state = play_initial_attack(start_bout(), Seat.ONE, [card(Rank.KING)])

    assert_bout_error(
        BoutErrorCode.WRONG_ACTOR,
        play_transfer,
        state,
        Seat.ONE,
        [card(Rank.NINE), card(Rank.NINE, Suit.DIAMONDS)],
    )


def test_transfer_rejects_more_cards_than_actor_count() -> None:
    state = play_initial_attack(
        start_bout(seat_two_hand_count=1),
        Seat.ONE,
        [card(Rank.KING)],
    )

    assert_bout_error(
        BoutErrorCode.NOT_ENOUGH_CARDS,
        play_transfer,
        state,
        Seat.TWO,
        [card(Rank.NINE), card(Rank.NINE, Suit.DIAMONDS)],
    )


def test_transfer_snowballs_from_18_to_36_to_72() -> None:
    state = play_initial_attack(start_bout(), Seat.ONE, [card(Rank.KING)])
    state = play_transfer(
        state,
        Seat.TWO,
        [card(Rank.NINE), card(Rank.NINE, Suit.DIAMONDS)],
    )

    state = play_transfer(
        state,
        Seat.ONE,
        [card(Rank.KING, Suit.DIAMONDS), card(Rank.KING, Suit.HEARTS)],
    )

    assert len(state.packets) == 1
    assert state.active_packet is not None
    assert state.active_packet.attack_value == 72
    assert state.transfer_target == 72
    assert state.total_attack_card_count == 5
    assert state.attacker is Seat.ONE
    assert state.defender is Seat.TWO
    assert state.hand_count(Seat.ONE) == 4
    assert state.hand_count(Seat.TWO) == 5
    assert state.attack_card_limit == 5
    assert state.max_attack_card_addition == 0


def test_transfer_rejects_packet_larger_than_new_defender_remaining_count() -> None:
    state = play_initial_attack(
        start_bout(seat_one_hand_count=3),
        Seat.ONE,
        [card(Rank.KING)],
    )

    assert_bout_error(
        BoutErrorCode.ATTACK_CARD_LIMIT_EXCEEDED,
        play_transfer,
        state,
        Seat.TWO,
        [card(Rank.NINE), card(Rank.NINE, Suit.DIAMONDS)],
    )
    assert state.attacker is Seat.ONE
    assert state.defender is Seat.TWO
    assert state.hand_count(Seat.TWO) == 7


def test_transfer_recalculates_cap_from_new_defender_remaining_hand() -> None:
    state = play_initial_attack(
        start_bout(seat_one_hand_count=4),
        Seat.ONE,
        [card(Rank.SEVEN)],
    )

    transferred = play_transfer(
        state,
        Seat.TWO,
        [card(Rank.SEVEN, Suit.DIAMONDS)],
    )

    assert transferred.defender is Seat.ONE
    assert transferred.hand_count(Seat.ONE) == 3
    assert transferred.attack_card_limit == 3
    assert transferred.total_attack_card_count == 2
    assert transferred.max_attack_card_addition == 1


def test_legal_defense_closes_packet_and_disables_transfer() -> None:
    state = play_initial_attack(start_bout(), Seat.ONE, [card(Rank.JACK)])

    defended = play_defense(state, Seat.TWO, [card(Rank.KING)])

    assert defended.phase is BoutPhase.WAITING_FOR_ATTACKER_DECISION
    assert defended.active_packet is None
    assert defended.packets[-1] == AttackPacket(
        attack_cards=(card(Rank.JACK),),
        attack_value=12,
        defense_cards=(card(Rank.KING),),
        defense_value=18,
    )
    assert defended.hand_count(Seat.TWO) == 6
    assert defended.total_attack_card_count == 1
    assert defended.transfer_open is False
    assert defended.transfer_target is None
    assert defended.direct_anchor_cards == (card(Rank.KING),)
    assert defended.table_cards == (card(Rank.JACK), card(Rank.KING))


def test_dynamic_attack_addition_uses_cap_and_current_defender_hand() -> None:
    state = play_initial_attack(
        start_bout(),
        Seat.ONE,
        [card(Rank.ACE), card(Rank.ACE, Suit.DIAMONDS)],
    )
    state = play_defense(
        state,
        Seat.TWO,
        [card(Rank.QUEEN), card(Rank.QUEEN, Suit.DIAMONDS), card(Rank.JACK)],
    )

    assert state.attack_card_limit == 7
    assert state.total_attack_card_count == 2
    assert state.hand_count(Seat.TWO) == 4
    assert state.remaining_bout_capacity == 5
    assert state.max_attack_card_addition == 4

    state = play_throw_in(
        state,
        Seat.ONE,
        [card(Rank.QUEEN, Suit.HEARTS), card(Rank.QUEEN, Suit.SPADES)],
    )
    state = play_defense(
        state,
        Seat.TWO,
        [card(Rank.JACK, Suit.DIAMONDS), card(Rank.TEN), card(Rank.NINE)],
    )

    assert state.total_attack_card_count == 4
    assert state.hand_count(Seat.TWO) == 1
    assert state.remaining_bout_capacity == 3
    assert state.max_attack_card_addition == 1


def test_dynamic_attack_addition_uses_global_cap_when_it_is_smaller() -> None:
    attack = [
        card(Rank.SIX),
        card(Rank.SIX, Suit.DIAMONDS),
        card(Rank.JACK),
        card(Rank.SIX, Suit.HEARTS),
        card(Rank.SIX, Suit.SPADES),
        card(Rank.JACK, Suit.DIAMONDS),
    ]
    state = play_initial_attack(start_bout(), Seat.ONE, attack)
    state = play_defense(
        state,
        Seat.TWO,
        [card(Rank.ACE), card(Rank.ACE, Suit.DIAMONDS), card(Rank.TEN)],
    )

    assert state.remaining_bout_capacity == 1
    assert state.hand_count(Seat.TWO) == 4
    assert state.max_attack_card_addition == 1


def test_dynamic_attack_addition_uses_current_hand_when_it_is_smaller() -> None:
    state = play_initial_attack(
        start_bout(),
        Seat.ONE,
        [card(Rank.ACE), card(Rank.ACE, Suit.DIAMONDS)],
    )
    state = play_defense(
        state,
        Seat.TWO,
        [
            card(Rank.NINE),
            card(Rank.NINE, Suit.DIAMONDS),
            card(Rank.NINE, Suit.HEARTS),
            card(Rank.NINE, Suit.SPADES),
            card(Rank.SIX),
        ],
    )

    assert state.remaining_bout_capacity == 5
    assert state.hand_count(Seat.TWO) == 2
    assert state.max_attack_card_addition == 2

    assert_bout_error(
        BoutErrorCode.ATTACK_CARD_LIMIT_EXCEEDED,
        play_throw_in,
        state,
        Seat.ONE,
        [
            card(Rank.NINE),
            card(Rank.NINE, Suit.DIAMONDS),
            card(Rank.NINE, Suit.HEARTS),
        ],
    )
    assert state.total_attack_card_count == 2


def test_defense_cards_do_not_consume_attack_card_capacity() -> None:
    state = play_initial_attack(
        start_bout(),
        Seat.ONE,
        [card(Rank.ACE), card(Rank.ACE, Suit.DIAMONDS)],
    )

    defended = play_defense(
        state,
        Seat.TWO,
        [card(Rank.QUEEN), card(Rank.QUEEN, Suit.DIAMONDS), card(Rank.JACK)],
    )

    assert len(defended.table_cards) == 5
    assert defended.total_attack_card_count == 2
    assert defended.remaining_bout_capacity == 5


def test_redundant_defense_is_rejected_before_final_card_bito() -> None:
    state = play_initial_attack(
        start_bout(seat_two_hand_count=4),
        Seat.ONE,
        [card(Rank.ACE), card(Rank.ACE, Suit.DIAMONDS)],
    )

    assert_bout_error(
        BoutErrorCode.REDUNDANT_DEFENSE,
        play_defense,
        state,
        Seat.TWO,
        [
            card(Rank.ACE),
            card(Rank.ACE, Suit.DIAMONDS),
            card(Rank.SIX),
            card(Rank.SIX, Suit.DIAMONDS),
        ],
    )
    assert state.phase is BoutPhase.WAITING_FOR_DEFENDER_RESPONSE
    assert state.hand_count(Seat.TWO) == 4


def test_final_defense_automatically_finishes_bito_and_rejects_throw_in() -> None:
    state = play_initial_attack(
        start_bout(seat_two_hand_count=1),
        Seat.ONE,
        [card(Rank.JACK)],
    )

    defended = play_defense(state, Seat.TWO, [card(Rank.KING)])

    assert defended.hand_count(Seat.TWO) == 0
    assert defended.phase is BoutPhase.COMPLETE
    assert defended.outcome is BoutOutcome.BITO
    assert defended.next_attacker is Seat.TWO
    assert defended.active_packet is None
    assert_bout_error(
        BoutErrorCode.BOUT_COMPLETE,
        play_throw_in,
        defended,
        Seat.ONE,
        [card(Rank.QUEEN)],
    )


@pytest.mark.parametrize(
    "defense_card",
    [card(Rank.KING, Suit.DIAMONDS), card(Rank.QUEEN)],
)
def test_equal_or_lower_defense_is_rejected(defense_card: Card) -> None:
    state = play_initial_attack(start_bout(), Seat.ONE, [card(Rank.KING)])

    assert_bout_error(
        BoutErrorCode.ILLEGAL_DEFENSE,
        play_defense,
        state,
        Seat.TWO,
        [defense_card],
    )


def test_defense_rejects_wrong_actor() -> None:
    state = play_initial_attack(start_bout(), Seat.ONE, [card(Rank.JACK)])

    assert_bout_error(
        BoutErrorCode.WRONG_ACTOR,
        play_defense,
        state,
        Seat.ONE,
        [card(Rank.KING)],
    )


def test_defense_rejects_more_cards_than_defender_count() -> None:
    state = play_initial_attack(
        start_bout(seat_two_hand_count=1),
        Seat.ONE,
        [card(Rank.KING)],
    )

    assert_bout_error(
        BoutErrorCode.NOT_ENOUGH_CARDS,
        play_defense,
        state,
        Seat.TWO,
        [card(Rank.QUEEN), card(Rank.QUEEN, Suit.DIAMONDS)],
    )


def test_defense_uses_fixed_trump_snapshot() -> None:
    trump_state = TrumpState.from_source_card(card(Rank.SIX, Suit.HEARTS))
    state = play_initial_attack(
        start_bout(trump_state=trump_state),
        Seat.ONE,
        [card(Rank.KING)],
    )

    defended = play_defense(state, Seat.TWO, [card(Rank.TEN, Suit.HEARTS)])

    assert defended.packets[-1].defense_value == 20
    assert defended.trump_state is trump_state


def test_transfer_is_closed_forever_after_first_successful_defense() -> None:
    defended = covered_jack()

    assert_bout_error(
        BoutErrorCode.TRANSFER_CLOSED,
        play_transfer,
        defended,
        Seat.TWO,
        [card(Rank.KING)],
    )

    thrown = play_throw_in(defended, Seat.ONE, [card(Rank.QUEEN)])
    assert_bout_error(
        BoutErrorCode.TRANSFER_CLOSED,
        play_transfer,
        thrown,
        Seat.TWO,
        [card(Rank.QUEEN)],
    )


@pytest.mark.parametrize(
    ("selection", "expected_reason"),
    [
        ([card(Rank.KING, Suit.DIAMONDS)], ThrowInReason.SAME_RANK),
        ([card(Rank.TEN), card(Rank.EIGHT)], ThrowInReason.EXISTING_VALUE),
        (
            [card(Rank.QUEEN), card(Rank.QUEEN, Suit.DIAMONDS)],
            ThrowInReason.TABLE_TOTAL,
        ),
        ([card(Rank.QUEEN)], ThrowInReason.ARITHMETIC_MEAN),
    ],
)
def test_throw_in_composes_all_confirmed_reason_types(
    selection: list[Card],
    expected_reason: ThrowInReason,
) -> None:
    state = covered_jack()
    analysis = analyze_throw_in(
        selection,
        state.table_cards,
        state.direct_anchor_cards,
        state.trump_state,
    )

    thrown = play_throw_in(state, Seat.ONE, selection)

    assert expected_reason in analysis.reasons
    assert thrown.phase is BoutPhase.WAITING_FOR_DEFENDER_RESPONSE
    assert thrown.active_packet is not None
    assert thrown.active_packet.attack_cards == tuple(selection)
    assert thrown.active_packet.attack_value in {15, 18, 30}
    assert thrown.attacker is Seat.ONE
    assert thrown.defender is Seat.TWO
    assert thrown.transfer_open is False


def test_throw_in_may_combine_ranks_from_multiple_latest_defense_cards() -> None:
    state = play_initial_attack(
        start_bout(seat_one_hand_count=4, seat_two_hand_count=4),
        Seat.ONE,
        [card(Rank.KING)],
    )
    defended = play_defense(
        state,
        Seat.TWO,
        [card(Rank.SEVEN, Suit.CLUBS), card(Rank.JACK, Suit.CLUBS)],
    )
    selection = [
        card(Rank.SEVEN, Suit.DIAMONDS),
        card(Rank.JACK, Suit.DIAMONDS),
    ]

    analysis = analyze_throw_in(
        selection,
        defended.table_cards,
        defended.direct_anchor_cards,
        defended.trump_state,
    )
    thrown = play_throw_in(defended, Seat.ONE, selection)

    assert analysis.reasons == frozenset(
        {ThrowInReason.LATEST_DEFENSE_RANKS, ThrowInReason.DEFENSE_TOTAL}
    )
    assert thrown.phase is BoutPhase.WAITING_FOR_DEFENDER_RESPONSE
    assert thrown.active_packet is not None
    assert thrown.active_packet.attack_cards == tuple(selection)
    assert thrown.active_packet.attack_value == 19
    assert thrown.total_attack_card_count == 3


def test_illegal_throw_in_is_rejected() -> None:
    state = covered_jack()

    assert_bout_error(
        BoutErrorCode.ILLEGAL_THROW_IN,
        play_throw_in,
        state,
        Seat.ONE,
        [card(Rank.JACK, Suit.DIAMONDS)],
    )


def test_throw_in_rejects_wrong_actor() -> None:
    assert_bout_error(
        BoutErrorCode.WRONG_ACTOR,
        play_throw_in,
        covered_jack(),
        Seat.TWO,
        [card(Rank.QUEEN)],
    )


def test_throw_in_rejects_more_cards_than_attacker_count() -> None:
    state = play_initial_attack(
        start_bout(seat_one_hand_count=2),
        Seat.ONE,
        [card(Rank.JACK)],
    )
    state = play_defense(state, Seat.TWO, [card(Rank.KING)])

    assert_bout_error(
        BoutErrorCode.NOT_ENOUGH_CARDS,
        play_throw_in,
        state,
        Seat.ONE,
        [card(Rank.QUEEN), card(Rank.QUEEN, Suit.DIAMONDS)],
    )


def test_throw_in_obeys_cumulative_attack_card_limit() -> None:
    state = play_initial_attack(
        start_bout(seat_two_hand_count=2),
        Seat.ONE,
        [card(Rank.JACK)],
    )
    state = play_defense(state, Seat.TWO, [card(Rank.KING)])

    assert_bout_error(
        BoutErrorCode.ATTACK_CARD_LIMIT_EXCEEDED,
        play_throw_in,
        state,
        Seat.ONE,
        [card(Rank.QUEEN), card(Rank.QUEEN, Suit.DIAMONDS)],
    )


def test_new_throw_in_packet_has_an_independent_defense_requirement() -> None:
    first_closed = covered_jack()
    second_active = play_throw_in(first_closed, Seat.ONE, [card(Rank.QUEEN)])

    second_closed = play_defense(second_active, Seat.TWO, [card(Rank.KING, Suit.DIAMONDS)])

    assert second_active.active_packet is not None
    assert second_active.active_packet.attack_value == 15
    assert len(second_closed.packets) == 2
    assert second_closed.packets[0].attack_value == 12
    assert second_closed.packets[1].attack_value == 15
    assert second_closed.packets[1].defense_value == 18


def test_latest_defense_replaces_direct_anchors_but_preserves_table_history() -> None:
    state = covered_jack()
    state = play_throw_in(state, Seat.ONE, [card(Rank.QUEEN)])
    state = play_defense(state, Seat.TWO, [card(Rank.ACE)])

    analysis = analyze_throw_in(
        [card(Rank.KING, Suit.DIAMONDS)],
        state.table_cards,
        state.direct_anchor_cards,
        state.trump_state,
    )
    summary = summarize_table_arithmetic(state.table_cards, state.trump_state)

    assert state.direct_anchor_cards == (card(Rank.ACE),)
    assert state.table_cards == (
        card(Rank.JACK),
        card(Rank.KING),
        card(Rank.QUEEN),
        card(Rank.ACE),
    )
    assert ThrowInReason.SAME_RANK not in analysis.reasons
    assert ThrowInReason.EXISTING_VALUE not in analysis.reasons
    assert summary.total_effective_value == 65
    assert summary.arithmetic_mean == Fraction(65, 4)


def test_latest_multi_card_defense_total_creates_next_packet_target() -> None:
    state = play_initial_attack(
        start_bout(seat_one_hand_count=5, seat_two_hand_count=6),
        Seat.ONE,
        [card(Rank.JACK)],
    )
    state = play_defense(state, Seat.TWO, [card(Rank.KING)])
    state = play_throw_in(state, Seat.ONE, [card(Rank.QUEEN)])
    state = play_defense(
        state,
        Seat.TWO,
        [card(Rank.JACK, Suit.DIAMONDS), card(Rank.EIGHT)],
    )

    analysis = analyze_throw_in(
        [card(Rank.ACE)],
        state.table_cards,
        state.direct_anchor_cards,
        state.trump_state,
    )
    thrown = play_throw_in(state, Seat.ONE, [card(Rank.ACE)])

    assert state.direct_anchor_cards == (
        card(Rank.JACK, Suit.DIAMONDS),
        card(Rank.EIGHT),
    )
    assert analysis.reasons == frozenset({ThrowInReason.DEFENSE_TOTAL})
    assert thrown.active_packet is not None
    assert thrown.active_packet.attack_value == 20


def test_only_latest_defense_packet_total_is_exposed() -> None:
    state = play_initial_attack(
        start_bout(seat_one_hand_count=5, seat_two_hand_count=6),
        Seat.ONE,
        [card(Rank.KING)],
    )
    state = play_defense(
        state,
        Seat.TWO,
        [card(Rank.JACK), card(Rank.EIGHT)],
    )
    state = play_throw_in(state, Seat.ONE, [card(Rank.ACE)])
    state = play_defense(
        state,
        Seat.TWO,
        [card(Rank.QUEEN), card(Rank.SIX, Suit.DIAMONDS)],
    )

    analysis = analyze_throw_in(
        [card(Rank.TEN), card(Rank.TEN, Suit.DIAMONDS)],
        state.table_cards,
        state.direct_anchor_cards,
        state.trump_state,
    )

    assert state.direct_anchor_cards == (
        card(Rank.QUEEN),
        card(Rank.SIX, Suit.DIAMONDS),
    )
    assert ThrowInReason.DEFENSE_TOTAL not in analysis.reasons


def test_covered_value_context_uses_latest_defense_and_all_table_arithmetic() -> None:
    state = covered_jack()

    targets = get_throw_in_targets(
        state.table_cards,
        state.direct_anchor_cards,
        state.trump_state,
    )
    old_attack = analyze_throw_in(
        [card(Rank.SIX), card(Rank.SIX, Suit.DIAMONDS)],
        state.table_cards,
        state.direct_anchor_cards,
        state.trump_state,
    )

    assert targets.represented_effective_values == frozenset({18})
    assert targets.table_total == 30
    assert targets.arithmetic_mean == Fraction(15)
    assert ThrowInReason.EXISTING_VALUE not in old_attack.reasons


def test_bito_is_available_only_after_packet_closes() -> None:
    active = play_initial_attack(start_bout(), Seat.ONE, [card(Rank.JACK)])

    assert_bout_error(BoutErrorCode.WRONG_PHASE, finish_bout, active, Seat.ONE)

    closed = play_defense(active, Seat.TWO, [card(Rank.KING)])
    complete = finish_bout(closed, Seat.ONE)

    assert complete.phase is BoutPhase.COMPLETE
    assert complete.outcome is BoutOutcome.BITO
    assert complete.next_attacker is Seat.TWO
    assert complete.taker is None
    assert complete.table_cards == (card(Rank.JACK), card(Rank.KING))


def test_bito_rejects_wrong_actor() -> None:
    assert_bout_error(
        BoutErrorCode.WRONG_ACTOR,
        finish_bout,
        covered_jack(),
        Seat.TWO,
    )


def test_take_is_available_only_to_active_defender() -> None:
    active = play_initial_attack(start_bout(), Seat.ONE, [card(Rank.KING)])

    assert_bout_error(BoutErrorCode.WRONG_ACTOR, take, active, Seat.ONE)
    complete = take(active, Seat.TWO)

    assert complete.phase is BoutPhase.COMPLETE
    assert complete.outcome is BoutOutcome.TAKE
    assert complete.taker is Seat.TWO
    assert complete.next_attacker is Seat.ONE
    assert complete.table_cards == (card(Rank.KING),)
    assert complete.hand_count(Seat.TWO) == 7


def test_take_preserves_the_complete_transferred_packet_table() -> None:
    state = play_initial_attack(start_bout(), Seat.ONE, [card(Rank.KING)])
    state = play_transfer(
        state,
        Seat.TWO,
        [card(Rank.NINE), card(Rank.NINE, Suit.DIAMONDS)],
    )

    complete = take(state, Seat.ONE)

    assert complete.taker is Seat.ONE
    assert complete.next_attacker is Seat.TWO
    assert complete.table_cards == (
        card(Rank.KING),
        card(Rank.NINE),
        card(Rank.NINE, Suit.DIAMONDS),
    )


def test_take_is_rejected_after_packet_has_closed() -> None:
    assert_bout_error(BoutErrorCode.WRONG_PHASE, take, covered_jack(), Seat.TWO)


@pytest.mark.parametrize(
    ("action", "actor", "cards"),
    [
        (play_initial_attack, Seat.ONE, [card(Rank.KING)]),
        (play_transfer, Seat.TWO, [card(Rank.KING)]),
        (play_defense, Seat.TWO, [card(Rank.ACE)]),
        (play_throw_in, Seat.ONE, [card(Rank.QUEEN)]),
    ],
)
def test_card_actions_are_rejected_after_completion(
    action: Callable[..., BoutState],
    actor: Seat,
    cards: list[Card],
) -> None:
    complete = finish_bout(covered_jack(), Seat.ONE)

    assert_bout_error(BoutErrorCode.BOUT_COMPLETE, action, complete, actor, cards)


@pytest.mark.parametrize("action", [finish_bout, take])
def test_terminal_actions_are_rejected_after_completion(
    action: Callable[..., BoutState],
) -> None:
    complete = finish_bout(covered_jack(), Seat.ONE)

    assert_bout_error(BoutErrorCode.BOUT_COMPLETE, action, complete, Seat.ONE)


def test_transitions_leave_previous_state_unchanged() -> None:
    original = start_bout()
    selected = [card(Rank.KING)]
    original_selection = selected.copy()

    transitioned = play_initial_attack(original, Seat.ONE, selected)

    assert original.phase is BoutPhase.WAITING_FOR_INITIAL_ATTACK
    assert original.packets == ()
    assert original.hand_count(Seat.ONE) == 7
    assert transitioned is not original
    assert selected == original_selection


def test_bout_state_and_packets_are_immutable() -> None:
    state = play_initial_attack(start_bout(), Seat.ONE, [card(Rank.KING)])

    with pytest.raises(FrozenInstanceError):
        state.phase = BoutPhase.COMPLETE  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        state.packets[0].attack_value = 20  # type: ignore[misc]
