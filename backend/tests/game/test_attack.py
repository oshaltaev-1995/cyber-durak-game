from dataclasses import FrozenInstanceError

import pytest

from kiba_api.game import (
    Card,
    InitialAttackAnalysis,
    InitialAttackReason,
    JokerColor,
    Rank,
    Suit,
    TrumpState,
    analyze_initial_attack,
    is_legal_initial_attack,
)

NO_TRUMP = TrumpState.no_trump()


def card(rank: Rank, suit: Suit = Suit.CLUBS) -> Card:
    return Card(rank=rank, suit=suit)


def joker(color: JokerColor) -> Card:
    return Card(rank=Rank.JOKER, joker_color=color)


def hearts_trump() -> TrumpState:
    return TrumpState.from_source_card(card(Rank.ACE, Suit.HEARTS))


def test_single_card_is_legal() -> None:
    analysis = analyze_initial_attack([card(Rank.KING)], NO_TRUMP)

    assert analysis == InitialAttackAnalysis(
        effective_values=(18,),
        reason=InitialAttackReason.SINGLE_CARD,
    )
    assert analysis.legal is True


def test_empty_initial_attack_is_illegal() -> None:
    analysis = analyze_initial_attack([], NO_TRUMP)

    assert analysis == InitialAttackAnalysis(effective_values=(), reason=None)
    assert analysis.legal is False


def test_rank_run_does_not_bootstrap_initial_attack_legality() -> None:
    analysis = analyze_initial_attack(
        [
            card(Rank.TEN),
            card(Rank.JACK),
            card(Rank.QUEEN),
            card(Rank.KING),
            card(Rank.ACE),
        ],
        NO_TRUMP,
    )

    assert analysis.legal is False


@pytest.mark.parametrize("card_count", [2, 3])
def test_same_rank_attack_is_legal(card_count: int) -> None:
    cards = [card(Rank.NINE, suit) for suit in list(Suit)[:card_count]]

    assert analyze_initial_attack(cards, NO_TRUMP).reason is InitialAttackReason.SAME_RANK


@pytest.mark.parametrize(
    "cards",
    [
        [card(Rank.NINE), card(Rank.SEVEN)],
        [card(Rank.NINE), card(Rank.KING)],
    ],
)
def test_unrelated_cards_are_illegal(cards: list[Card]) -> None:
    assert is_legal_initial_attack(cards, NO_TRUMP) is False


@pytest.mark.parametrize(
    "cards",
    [
        [card(Rank.KING), card(Rank.NINE), card(Rank.NINE, Suit.DIAMONDS)],
        [card(Rank.KING), card(Rank.JACK), card(Rank.SIX)],
        [card(Rank.KING), card(Rank.TEN), card(Rank.EIGHT)],
        [card(Rank.JACK), card(Rank.SIX), card(Rank.SIX, Suit.DIAMONDS)],
        [card(Rank.TEN), card(Rank.EIGHT), card(Rank.JACK), card(Rank.SIX)],
    ],
)
def test_equal_value_groups_are_legal(cards: list[Card]) -> None:
    analysis = analyze_initial_attack(cards, NO_TRUMP)

    assert analysis.legal is True
    assert analysis.reason is InitialAttackReason.EQUAL_VALUE_GROUPS


def test_multiple_equal_value_groups_form_one_structure() -> None:
    cards = [
        card(Rank.KING),
        card(Rank.NINE),
        card(Rank.NINE, Suit.DIAMONDS),
        card(Rank.JACK),
        card(Rank.SIX),
    ]

    assert analyze_initial_attack(cards, NO_TRUMP).reason is InitialAttackReason.EQUAL_VALUE_GROUPS


@pytest.mark.parametrize("nine_count", [2, 3, 4])
def test_same_rank_cards_extend_arithmetic_structure(nine_count: int) -> None:
    cards = [card(Rank.KING)] + [card(Rank.NINE, suit) for suit in list(Suit)[:nine_count]]

    analysis = analyze_initial_attack(cards, NO_TRUMP)

    assert analysis.legal is True
    expected_reason = {
        2: InitialAttackReason.EQUAL_VALUE_GROUPS,
        3: InitialAttackReason.CONNECTED_COMBINATION,
        4: InitialAttackReason.EQUAL_VALUE_GROUPS,
    }[nine_count]
    assert analysis.reason is expected_reason


def test_unrelated_same_rank_clusters_are_not_globally_connected() -> None:
    cards = [
        card(Rank.NINE),
        card(Rank.NINE, Suit.DIAMONDS),
        card(Rank.SEVEN),
        card(Rank.SEVEN, Suit.DIAMONDS),
    ]

    assert is_legal_initial_attack(cards, NO_TRUMP) is False


def test_arithmetic_equality_can_connect_same_rank_clusters() -> None:
    cards = [
        card(Rank.NINE),
        card(Rank.NINE, Suit.DIAMONDS),
        card(Rank.SIX),
        card(Rank.SIX, Suit.DIAMONDS),
        card(Rank.JACK),
    ]

    assert analyze_initial_attack(cards, NO_TRUMP).reason is InitialAttackReason.EQUAL_VALUE_GROUPS


def test_trump_adjusted_equal_cards_are_legal() -> None:
    analysis = analyze_initial_attack(
        [card(Rank.KING), card(Rank.NINE, Suit.HEARTS)],
        hearts_trump(),
    )

    assert analysis.effective_values == (18, 18)
    assert analysis.reason is InitialAttackReason.EQUAL_VALUE_GROUPS


def test_trump_breaks_old_base_value_relation() -> None:
    kings_trump = TrumpState.from_source_card(card(Rank.KING, Suit.SPADES))
    cards = [
        card(Rank.KING, Suit.HEARTS),
        card(Rank.NINE),
        card(Rank.NINE, Suit.DIAMONDS),
    ]

    analysis = analyze_initial_attack(cards, kings_trump)

    assert analysis.effective_values == (36, 9, 9)
    assert analysis.legal is False


def test_trump_adjusted_multi_card_equality_is_legal() -> None:
    analysis = analyze_initial_attack(
        [card(Rank.NINE, Suit.HEARTS), card(Rank.JACK), card(Rank.SIX)],
        hearts_trump(),
    )

    assert analysis.effective_values == (18, 12, 6)
    assert analysis.legal is True


def test_arithmetic_mean_does_not_extend_initial_attack() -> None:
    cards = [
        card(Rank.KING),
        card(Rank.NINE),
        card(Rank.NINE, Suit.DIAMONDS),
        card(Rank.JACK),
    ]

    assert is_legal_initial_attack(cards, NO_TRUMP) is False


def test_initial_attack_does_not_expose_a_growing_table_total() -> None:
    cards = [
        card(Rank.KING),
        card(Rank.NINE),
        card(Rank.NINE, Suit.DIAMONDS),
        card(Rank.QUEEN),
    ]

    analysis = analyze_initial_attack(cards, NO_TRUMP)

    assert analysis.effective_values == (18, 9, 9, 15)
    assert analysis.legal is False


def test_two_jokers_form_same_rank_attack() -> None:
    analysis = analyze_initial_attack(
        [joker(JokerColor.RED), joker(JokerColor.BLACK)],
        NO_TRUMP,
    )

    assert analysis.effective_values == (25, 25)
    assert analysis.reason is InitialAttackReason.SAME_RANK


def test_joker_uses_base_value_in_arithmetic_relation() -> None:
    cards = [
        joker(JokerColor.RED),
        card(Rank.TEN),
        card(Rank.NINE),
        card(Rank.SIX),
    ]

    assert analyze_initial_attack(cards, NO_TRUMP).reason is InitialAttackReason.EQUAL_VALUE_GROUPS


def test_trump_joker_uses_effective_value_in_arithmetic_relation() -> None:
    joker_trump = TrumpState.from_source_card(joker(JokerColor.RED))
    cards = [
        joker(JokerColor.BLACK),
        card(Rank.ACE),
        card(Rank.KING),
        card(Rank.JACK),
    ]

    analysis = analyze_initial_attack(cards, joker_trump)

    assert analysis.effective_values == (50, 20, 18, 12)
    assert analysis.reason is InitialAttackReason.EQUAL_VALUE_GROUPS


def test_joker_has_no_additional_attack_power() -> None:
    assert (
        is_legal_initial_attack(
            [joker(JokerColor.RED), card(Rank.ACE)],
            NO_TRUMP,
        )
        is False
    )


def test_boolean_helper_delegates_to_analysis() -> None:
    cards = [card(Rank.KING), card(Rank.JACK), card(Rank.SIX)]

    assert (
        is_legal_initial_attack(cards, NO_TRUMP)
        is analyze_initial_attack(
            cards,
            NO_TRUMP,
        ).legal
    )


def test_initial_attack_analysis_is_immutable() -> None:
    analysis = analyze_initial_attack([card(Rank.KING)], NO_TRUMP)

    with pytest.raises(FrozenInstanceError):
        analysis.reason = None  # type: ignore[misc]


def test_initial_attack_analysis_does_not_mutate_input() -> None:
    selected = [card(Rank.KING), card(Rank.JACK), card(Rank.SIX)]
    original = selected.copy()

    analyze_initial_attack(selected, NO_TRUMP)

    assert selected == original


def test_initial_attack_analysis_is_deterministic() -> None:
    cards = [card(Rank.TEN), card(Rank.EIGHT), card(Rank.JACK), card(Rank.SIX)]

    assert analyze_initial_attack(cards, NO_TRUMP) == analyze_initial_attack(cards, NO_TRUMP)


def test_initial_attack_legality_is_independent_of_input_order() -> None:
    cards = [card(Rank.KING), card(Rank.NINE), card(Rank.NINE, Suit.DIAMONDS)]

    forward = analyze_initial_attack(cards, NO_TRUMP)
    reversed_order = analyze_initial_attack(reversed(cards), NO_TRUMP)

    assert forward.legal is reversed_order.legal is True
    assert forward.reason is reversed_order.reason
