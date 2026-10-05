from __future__ import annotations

from collections.abc import Iterable

import pytest

from kiba_api.api.cards import card_to_code
from kiba_api.game import (
    AttackPacket,
    BoutPhase,
    BoutState,
    Card,
    GameOutcome,
    GamePhase,
    GameResult,
    GameState,
    Rank,
    Seat,
    Suit,
    TrumpState,
    play_game_defense,
    play_game_initial_attack,
    start_game_bout,
)
from kiba_api.sessions import (
    HintError,
    HintErrorCode,
    HintReason,
    HumanActionType,
    get_move_hints,
)
from kiba_api.sessions.hints import MAX_HINT_CANDIDATE_SELECTIONS


def card(rank: Rank, suit: Suit = Suit.CLUBS) -> Card:
    return Card(rank=rank, suit=suit)


def game(
    seat_one_hand: Iterable[Card],
    seat_two_hand: Iterable[Card],
    *,
    attacker: Seat = Seat.ONE,
    draw_pile: Iterable[Card] = (),
) -> GameState:
    return GameState(
        seat_one_hand=tuple(seat_one_hand),
        seat_two_hand=tuple(seat_two_hand),
        draw_pile=tuple(draw_pile),
        discard_pile=(),
        current_attacker=attacker,
    )


def after_attack(
    attacker_hand: Iterable[Card],
    defender_hand: Iterable[Card],
    attack: Iterable[Card],
    *,
    trump_state: TrumpState | None = None,
) -> GameState:
    trump_state = trump_state or TrumpState.no_trump()
    initial = game(attacker_hand, defender_hand)
    if trump_state.active:
        bout = BoutState.start(
            attacker=Seat.ONE,
            seat_one_hand_count=len(initial.seat_one_hand),
            seat_two_hand_count=len(initial.seat_two_hand),
            trump_state=trump_state,
        )
        initial = GameState(
            seat_one_hand=initial.seat_one_hand,
            seat_two_hand=initial.seat_two_hand,
            draw_pile=(),
            discard_pile=(),
            current_attacker=Seat.ONE,
            phase=GamePhase.BOUT_ACTIVE,
            active_bout=bout,
            bout_starting_attacker=Seat.ONE,
        )
    else:
        initial = start_game_bout(initial)
    return play_game_initial_attack(initial, Seat.ONE, tuple(attack))


def after_defense(
    attacker_hand: Iterable[Card],
    defender_hand: Iterable[Card],
    attack: Iterable[Card],
    defense: Iterable[Card],
) -> GameState:
    state = after_attack(attacker_hand, defender_hand, attack)
    return play_game_defense(state, Seat.TWO, tuple(defense))


def codes(cards: Iterable[Card]) -> set[str]:
    return {card_to_code(value) for value in cards}


def test_initial_attack_hints_use_same_rank_and_connected_arithmetic() -> None:
    first_nine = card(Rank.NINE)
    second_nine = card(Rank.NINE, Suit.DIAMONDS)
    king = card(Rank.KING)
    state = start_game_bout(
        game(
            (first_nine, second_nine, king, card(Rank.SEVEN)),
            (card(Rank.ACE), card(Rank.SIX), card(Rank.EIGHT)),
        )
    )

    same_rank = get_move_hints(state, Seat.ONE, (first_nine,))
    arithmetic = get_move_hints(state, Seat.ONE, (first_nine, second_nine))

    assert card_to_code(second_nine) in codes(same_rank.suggested_cards)
    assert card_to_code(card(Rank.SEVEN)) not in codes(same_rank.suggested_cards)
    assert card_to_code(king) in codes(arithmetic.suggested_cards)
    assert any(
        hint.reason is HintReason.ARITHMETIC_EQUALITY and king in hint.added_cards
        for hint in arithmetic.combinations
    )


def test_empty_selection_is_quiet_and_does_not_scan_the_hand() -> None:
    state = start_game_bout(game((card(Rank.NINE), card(Rank.KING)), (card(Rank.ACE),)))

    hints = get_move_hints(state, Seat.ONE, ())

    assert hints.suggested_cards == ()
    assert hints.combinations == ()
    assert hints.candidate_selections_examined == 0


def test_defense_completion_respects_sufficiency_and_irredundancy() -> None:
    jack = card(Rank.JACK)
    seven = card(Rank.SEVEN)
    six = card(Rank.SIX)
    attack = card(Rank.KING)
    state = after_attack((attack,), (jack, seven, six), (attack,))

    hints = get_move_hints(state, Seat.TWO, (jack,))
    complete = get_move_hints(state, Seat.TWO, (jack, seven))

    assert hints.suggested_cards == (seven,)
    assert hints.combinations[0].selected_value == 19
    assert hints.combinations[0].target_value == 18
    assert complete.suggested_cards == ()
    assert all(six not in hint.added_cards for hint in complete.combinations)


def test_defense_hint_uses_trump_effective_values() -> None:
    source = card(Rank.ACE, Suit.HEARTS)
    trump = TrumpState.from_source_card(source)
    attack = card(Rank.KING)
    six = card(Rank.SIX)
    trump_seven = card(Rank.SEVEN, Suit.HEARTS)
    state = after_attack((attack,), (six, trump_seven), (attack,), trump_state=trump)

    hints = get_move_hints(state, Seat.TWO, (six,))

    assert hints.suggested_cards == (trump_seven,)
    assert hints.combinations[0].selected_value == 20


def test_transfer_hints_cover_exact_and_same_rank_extension() -> None:
    king = card(Rank.KING)
    nine_one = card(Rank.NINE)
    nine_two = card(Rank.NINE, Suit.DIAMONDS)
    exact_state = after_attack(
        (king, card(Rank.SIX), card(Rank.EIGHT), card(Rank.TEN)),
        (nine_one, nine_two),
        (king,),
    )

    exact = get_move_hints(exact_state, Seat.TWO, (nine_one,))

    assert nine_two in exact.suggested_cards
    assert any(hint.reason is HintReason.TRANSFER_EXACT for hint in exact.combinations)

    seven_attack = card(Rank.SEVEN)
    seven_one = card(Rank.SEVEN, Suit.DIAMONDS)
    seven_two = card(Rank.SEVEN, Suit.HEARTS)
    extended_state = after_attack(
        (seven_attack, card(Rank.SIX), card(Rank.EIGHT), card(Rank.TEN)),
        (seven_one, seven_two),
        (seven_attack,),
    )

    extended = get_move_hints(extended_state, Seat.TWO, (seven_one,))

    assert seven_two in extended.suggested_cards
    assert any(hint.reason is HintReason.SAME_RANK_TRANSFER for hint in extended.combinations)


def test_transfer_hint_respects_receiving_defender_limit() -> None:
    attack = card(Rank.SEVEN)
    extra_attacker_card = card(Rank.SIX)
    first = card(Rank.SEVEN, Suit.DIAMONDS)
    second = card(Rank.SEVEN, Suit.HEARTS)
    state = after_attack((attack, extra_attacker_card), (first, second), (attack,))

    hints = get_move_hints(state, Seat.TWO, (first,))

    assert not any(hint.action is HumanActionType.TRANSFER for hint in hints.combinations)


def test_transfer_is_not_suggested_after_first_defense() -> None:
    attack = card(Rank.SIX)
    defense = card(Rank.SEVEN)
    state = after_defense(
        (attack, card(Rank.SEVEN, Suit.DIAMONDS)),
        (defense, card(Rank.ACE)),
        (attack,),
        (defense,),
    )

    hints = get_move_hints(state, Seat.ONE, (card(Rank.SEVEN, Suit.DIAMONDS),))

    assert HumanActionType.TRANSFER not in hints.suggested_actions


@pytest.mark.parametrize(
    ("state", "selected", "suggested", "reason"),
    [
        (
            after_defense(
                (card(Rank.SIX), card(Rank.SEVEN, Suit.DIAMONDS), card(Rank.SEVEN, Suit.HEARTS)),
                (card(Rank.SEVEN), card(Rank.ACE), card(Rank.NINE), card(Rank.TEN)),
                (card(Rank.SIX),),
                (card(Rank.SEVEN),),
            ),
            card(Rank.SEVEN, Suit.DIAMONDS),
            card(Rank.SEVEN, Suit.HEARTS),
            HintReason.SAME_RANK,
        ),
        (
            after_defense(
                (card(Rank.JACK), card(Rank.TEN), card(Rank.EIGHT)),
                (card(Rank.KING), card(Rank.ACE), card(Rank.NINE), card(Rank.TEN)),
                (card(Rank.JACK),),
                (card(Rank.KING),),
            ),
            card(Rank.TEN),
            card(Rank.EIGHT),
            HintReason.EXISTING_VALUE,
        ),
        (
            after_defense(
                (card(Rank.KING), card(Rank.TEN), card(Rank.TEN, Suit.DIAMONDS)),
                (
                    card(Rank.JACK),
                    card(Rank.EIGHT),
                    card(Rank.ACE),
                    card(Rank.SIX),
                ),
                (card(Rank.KING),),
                (card(Rank.JACK), card(Rank.EIGHT)),
            ),
            card(Rank.TEN),
            card(Rank.TEN, Suit.DIAMONDS),
            HintReason.DEFENSE_TOTAL,
        ),
        (
            after_defense(
                (card(Rank.SIX), card(Rank.SIX, Suit.DIAMONDS), card(Rank.SEVEN, Suit.DIAMONDS)),
                (card(Rank.SEVEN), card(Rank.ACE), card(Rank.NINE), card(Rank.TEN)),
                (card(Rank.SIX),),
                (card(Rank.SEVEN),),
            ),
            card(Rank.SIX, Suit.DIAMONDS),
            card(Rank.SEVEN, Suit.DIAMONDS),
            HintReason.TABLE_TOTAL,
        ),
        (
            after_defense(
                (card(Rank.JACK), card(Rank.SEVEN), card(Rank.EIGHT)),
                (card(Rank.KING), card(Rank.ACE), card(Rank.NINE), card(Rank.TEN)),
                (card(Rank.JACK),),
                (card(Rank.KING),),
            ),
            card(Rank.SEVEN),
            card(Rank.EIGHT),
            HintReason.ARITHMETIC_MEAN,
        ),
    ],
)
def test_throw_in_hint_reasons(
    state: GameState,
    selected: Card,
    suggested: Card,
    reason: HintReason,
) -> None:
    hints = get_move_hints(state, Seat.ONE, (selected,))

    assert suggested in hints.suggested_cards
    assert any(
        hint.reason is reason and suggested in hint.added_cards for hint in hints.combinations
    )


def test_mixed_latest_defense_rank_hint_uses_the_specific_true_reason() -> None:
    attack = card(Rank.KING)
    defense_jack = card(Rank.JACK, Suit.CLUBS)
    defense_king = card(Rank.KING, Suit.CLUBS)
    selected_jack = card(Rank.JACK, Suit.DIAMONDS)
    suggested_king = card(Rank.KING, Suit.SPADES)
    state = after_defense(
        (attack, selected_jack, suggested_king, card(Rank.SIX)),
        (defense_jack, defense_king, card(Rank.ACE), card(Rank.NINE)),
        (attack,),
        (defense_jack, defense_king),
    )

    hints = get_move_hints(state, Seat.ONE, (selected_jack,))
    mixed = next(hint for hint in hints.combinations if suggested_king in hint.added_cards)

    assert mixed.cards == (selected_jack, suggested_king)
    assert mixed.reason is HintReason.LATEST_DEFENSE_RANKS
    assert mixed.reason is not HintReason.SAME_RANK


def test_actual_same_rank_hint_keeps_same_rank_reason() -> None:
    attack = card(Rank.SIX)
    defense_seven = card(Rank.SEVEN, Suit.CLUBS)
    selected_seven = card(Rank.SEVEN, Suit.DIAMONDS)
    suggested_seven = card(Rank.SEVEN, Suit.HEARTS)
    state = after_defense(
        (attack, selected_seven, suggested_seven),
        (defense_seven, card(Rank.ACE), card(Rank.NINE)),
        (attack,),
        (defense_seven,),
    )

    hints = get_move_hints(state, Seat.ONE, (selected_seven,))
    same_rank = next(hint for hint in hints.combinations if suggested_seven in hint.added_cards)

    assert same_rank.reason is HintReason.SAME_RANK


def test_rank_run_hint_and_dynamic_attack_limit() -> None:
    ten = card(Rank.TEN)
    jack = card(Rank.JACK)
    queen = card(Rank.QUEEN)
    king = card(Rank.KING)
    selected_ten = card(Rank.TEN, Suit.DIAMONDS)
    ace = card(Rank.ACE, Suit.DIAMONDS)
    attacker_hand = (selected_ten, ace)
    defender_hand = (card(Rank.SIX, Suit.SPADES), card(Rank.SEVEN, Suit.SPADES))
    bout = BoutState(
        attacker=Seat.ONE,
        defender=Seat.TWO,
        seat_one_hand_count=len(attacker_hand),
        seat_two_hand_count=len(defender_hand),
        trump_state=TrumpState.no_trump(),
        phase=BoutPhase.WAITING_FOR_ATTACKER_DECISION,
        packets=(
            AttackPacket((ten,), 10, (jack,), 12),
            AttackPacket((queen,), 15, (king,), 18),
        ),
        transfer_open=False,
        attack_card_limit=7,
        total_attack_card_count=2,
    )
    state = GameState(
        seat_one_hand=attacker_hand,
        seat_two_hand=defender_hand,
        draw_pile=(),
        discard_pile=(),
        current_attacker=Seat.ONE,
        phase=GamePhase.BOUT_ACTIVE,
        active_bout=bout,
        bout_starting_attacker=Seat.ONE,
    )

    run = get_move_hints(state, Seat.ONE, (selected_ten,))

    assert ace in run.suggested_cards
    assert any(hint.reason is HintReason.RANK_RUN for hint in run.combinations)

    limited_bout = BoutState(
        attacker=Seat.ONE,
        defender=Seat.TWO,
        seat_one_hand_count=2,
        seat_two_hand_count=1,
        trump_state=TrumpState.no_trump(),
        phase=BoutPhase.WAITING_FOR_ATTACKER_DECISION,
        packets=(AttackPacket((card(Rank.SIX),), 6, (card(Rank.SEVEN),), 7),),
        transfer_open=False,
        attack_card_limit=7,
        total_attack_card_count=1,
    )
    limited_state = GameState(
        seat_one_hand=(card(Rank.SEVEN, Suit.DIAMONDS), card(Rank.SEVEN, Suit.HEARTS)),
        seat_two_hand=(card(Rank.ACE),),
        draw_pile=(),
        discard_pile=(),
        current_attacker=Seat.ONE,
        phase=GamePhase.BOUT_ACTIVE,
        active_bout=limited_bout,
        bout_starting_attacker=Seat.ONE,
    )

    limited = get_move_hints(limited_state, Seat.ONE, (card(Rank.SEVEN, Suit.DIAMONDS),))

    assert limited_bout.max_attack_card_addition == 1
    assert card(Rank.SEVEN, Suit.HEARTS) not in limited.suggested_cards


@pytest.mark.parametrize("hand_size", [7, 14, 18])
def test_hint_search_is_bounded_for_take_sized_hands(hand_size: int) -> None:
    hand = tuple(
        card(rank, suit)
        for suit in Suit
        for rank in (Rank.SIX, Rank.SEVEN, Rank.EIGHT, Rank.NINE, Rank.TEN)
    )[:hand_size]
    state = start_game_bout(game(hand, (card(Rank.ACE),)))

    hints = get_move_hints(
        state,
        Seat.ONE,
        (hand[0],),
        max_combinations=100,
        candidate_limit=MAX_HINT_CANDIDATE_SELECTIONS,
    )

    assert hints.candidate_selections_examined <= MAX_HINT_CANDIDATE_SELECTIONS


def test_hint_failures_reject_wrong_turn_unknown_cards_and_complete_games() -> None:
    state = start_game_bout(game((card(Rank.SIX),), (card(Rank.SEVEN),)))

    with pytest.raises(HintError, match=HintErrorCode.WRONG_TURN.value):
        get_move_hints(state, Seat.TWO, (card(Rank.SEVEN),))
    with pytest.raises(HintError, match=HintErrorCode.CARD_NOT_OWNED.value):
        get_move_hints(state, Seat.ONE, (card(Rank.ACE),))

    complete = GameState(
        seat_one_hand=(),
        seat_two_hand=(card(Rank.SEVEN),),
        draw_pile=(),
        discard_pile=(),
        current_attacker=None,
        phase=GamePhase.COMPLETE,
        result=GameResult(GameOutcome.WIN, Seat.ONE),
    )
    with pytest.raises(HintError, match=HintErrorCode.GAME_COMPLETE.value):
        get_move_hints(complete, Seat.ONE, ())
