from dataclasses import FrozenInstanceError
from fractions import Fraction

import pytest

from kiba_api.game import (
    Card,
    JokerColor,
    Rank,
    Suit,
    ThrowInAnalysis,
    ThrowInReason,
    ThrowInTargets,
    TrumpState,
    analyze_throw_in,
    get_throw_in_targets,
    is_legal_defense,
)

NO_TRUMP = TrumpState.no_trump()


def card(rank: Rank, suit: Suit = Suit.CLUBS) -> Card:
    return Card(rank=rank, suit=suit)


def joker(color: JokerColor) -> Card:
    return Card(rank=Rank.JOKER, joker_color=color)


def hearts_trump() -> TrumpState:
    return TrumpState.from_source_card(card(Rank.ACE, Suit.HEARTS))


def test_multi_card_defense_above_attack_is_legal() -> None:
    defense = [card(Rank.QUEEN), card(Rank.QUEEN, Suit.DIAMONDS), card(Rank.TEN)]

    assert is_legal_defense(defense, 36, NO_TRUMP) is True


def test_defense_equal_to_attack_is_illegal() -> None:
    defense = [card(Rank.KING), card(Rank.KING, Suit.DIAMONDS)]

    assert is_legal_defense(defense, 36, NO_TRUMP) is False


def test_defense_below_attack_is_illegal() -> None:
    defense = [card(Rank.ACE), card(Rank.QUEEN)]

    assert is_legal_defense(defense, 36, NO_TRUMP) is False


def test_one_card_defense_can_be_legal() -> None:
    assert is_legal_defense([card(Rank.KING)], 17, NO_TRUMP) is True


def test_defense_uses_trump_adjusted_value() -> None:
    trump_nine = card(Rank.NINE, Suit.HEARTS)

    assert is_legal_defense([trump_nine], 17, hearts_trump()) is True
    assert is_legal_defense([trump_nine], 18, hearts_trump()) is False


def test_empty_defense_is_illegal() -> None:
    assert is_legal_defense([], 36, NO_TRUMP) is False


def test_zero_attack_still_requires_non_empty_strictly_greater_defense() -> None:
    assert is_legal_defense([card(Rank.SIX)], 0, NO_TRUMP) is True
    assert is_legal_defense([], 0, NO_TRUMP) is False


def test_negative_attack_value_is_rejected() -> None:
    with pytest.raises(ValueError, match="must not be negative"):
        is_legal_defense([card(Rank.SIX)], -1, NO_TRUMP)


def test_non_integer_attack_value_is_rejected() -> None:
    with pytest.raises(TypeError, match="must be an int"):
        is_legal_defense([card(Rank.SIX)], 1.5, NO_TRUMP)  # type: ignore[arg-type]


def test_defense_does_not_mutate_input() -> None:
    defense = [card(Rank.QUEEN), card(Rank.TEN)]
    original = defense.copy()

    is_legal_defense(defense, 20, NO_TRUMP)

    assert defense == original


def test_throw_in_targets_derive_unique_arithmetic_sources() -> None:
    targets = get_throw_in_targets(
        [card(Rank.SEVEN), card(Rank.SEVEN, Suit.DIAMONDS), card(Rank.KING)],
        NO_TRUMP,
    )

    assert targets == ThrowInTargets(
        represented_effective_values=frozenset({7, 18}),
        table_total=32,
        arithmetic_mean=Fraction(32, 3),
    )


def test_empty_table_has_no_throw_in_targets() -> None:
    assert get_throw_in_targets([], NO_TRUMP) == ThrowInTargets(
        represented_effective_values=frozenset(),
        table_total=None,
        arithmetic_mean=None,
    )


def test_throw_in_targets_are_immutable() -> None:
    targets = get_throw_in_targets([card(Rank.KING)], NO_TRUMP)

    with pytest.raises(FrozenInstanceError):
        targets.table_total = 20  # type: ignore[misc]


def test_one_selected_card_matches_rank_represented_on_table() -> None:
    analysis = analyze_throw_in(
        [card(Rank.NINE, Suit.HEARTS)],
        [card(Rank.NINE, Suit.CLUBS), card(Rank.SIX)],
        NO_TRUMP,
    )

    assert analysis.legal is True
    assert ThrowInReason.SAME_RANK in analysis.reasons


def test_same_rank_selected_group_matches_rank_represented_on_table() -> None:
    analysis = analyze_throw_in(
        [card(Rank.NINE, Suit.HEARTS), card(Rank.NINE, Suit.SPADES)],
        [card(Rank.NINE, Suit.CLUBS), card(Rank.SIX)],
        NO_TRUMP,
    )

    assert ThrowInReason.SAME_RANK in analysis.reasons


def test_rank_mismatch_does_not_qualify_as_same_rank() -> None:
    analysis = analyze_throw_in(
        [card(Rank.NINE)],
        [card(Rank.KING), card(Rank.SIX)],
        NO_TRUMP,
    )

    assert ThrowInReason.SAME_RANK not in analysis.reasons


def test_mixed_rank_selection_does_not_qualify_as_same_rank() -> None:
    analysis = analyze_throw_in(
        [card(Rank.NINE), card(Rank.KING)],
        [card(Rank.NINE, Suit.HEARTS), card(Rank.SIX)],
        NO_TRUMP,
    )

    assert ThrowInReason.SAME_RANK not in analysis.reasons


def test_jokers_share_the_same_rank_for_throw_ins() -> None:
    analysis = analyze_throw_in(
        [joker(JokerColor.BLACK)],
        [joker(JokerColor.RED), card(Rank.SIX)],
        NO_TRUMP,
    )

    assert ThrowInReason.SAME_RANK in analysis.reasons


def test_trump_changes_value_but_not_same_rank_relation() -> None:
    analysis = analyze_throw_in(
        [card(Rank.NINE, Suit.HEARTS)],
        [card(Rank.NINE, Suit.CLUBS)],
        hearts_trump(),
    )

    assert analysis.selected_value == 18
    assert analysis.reasons == frozenset({ThrowInReason.SAME_RANK})


@pytest.mark.parametrize(
    "selection",
    [
        [card(Rank.TEN), card(Rank.EIGHT)],
        [card(Rank.JACK), card(Rank.SIX)],
        [card(Rank.NINE), card(Rank.NINE, Suit.DIAMONDS)],
    ],
)
def test_selection_can_match_existing_effective_value(selection: list[Card]) -> None:
    analysis = analyze_throw_in(
        selection,
        [card(Rank.KING), card(Rank.SIX)],
        NO_TRUMP,
    )

    assert analysis.legal is True
    assert ThrowInReason.EXISTING_VALUE in analysis.reasons


def test_unrepresented_value_has_no_existing_value_reason() -> None:
    analysis = analyze_throw_in(
        [card(Rank.JACK), card(Rank.SIX)],
        [card(Rank.ACE), card(Rank.QUEEN)],
        NO_TRUMP,
    )

    assert analysis.selected_value == 18
    assert ThrowInReason.EXISTING_VALUE not in analysis.reasons


def test_value_seventeen_is_illegal_when_no_table_rule_exposes_it() -> None:
    analysis = analyze_throw_in(
        [card(Rank.NINE), card(Rank.EIGHT)],
        [card(Rank.KING), card(Rank.SIX)],
        NO_TRUMP,
    )

    assert analysis.selected_value == 17
    assert analysis.legal is False
    assert analysis.reasons == frozenset()


def test_selection_can_match_table_total() -> None:
    table = [card(Rank.SEVEN), card(Rank.SEVEN, Suit.DIAMONDS), card(Rank.KING)]
    analysis = analyze_throw_in([card(Rank.ACE), card(Rank.JACK)], table, NO_TRUMP)

    assert analysis.selected_value == 32
    assert ThrowInReason.TABLE_TOTAL in analysis.reasons


def test_nearby_value_does_not_match_table_total() -> None:
    table = [card(Rank.SEVEN), card(Rank.SEVEN, Suit.DIAMONDS), card(Rank.KING)]
    analysis = analyze_throw_in(
        [joker(JokerColor.RED), card(Rank.SIX)],
        table,
        NO_TRUMP,
    )

    assert analysis.selected_value == 31
    assert analysis.legal is False
    assert ThrowInReason.TABLE_TOTAL not in analysis.reasons


@pytest.mark.parametrize(
    "selection",
    [[card(Rank.QUEEN)], [card(Rank.SEVEN), card(Rank.EIGHT)]],
)
def test_selection_can_match_arithmetic_mean(selection: list[Card]) -> None:
    analysis = analyze_throw_in(
        selection,
        [card(Rank.JACK), card(Rank.KING)],
        NO_TRUMP,
    )

    assert analysis.selected_value == 15
    assert ThrowInReason.ARITHMETIC_MEAN in analysis.reasons


def test_recalculated_mean_remains_exact() -> None:
    table = [card(Rank.JACK), card(Rank.KING), card(Rank.QUEEN)]
    targets = get_throw_in_targets(table, NO_TRUMP)
    analysis = analyze_throw_in([card(Rank.SEVEN), card(Rank.EIGHT)], table, NO_TRUMP)

    assert targets.arithmetic_mean == Fraction(15)
    assert ThrowInReason.ARITHMETIC_MEAN in analysis.reasons


def test_non_integer_mean_is_not_rounded() -> None:
    table = [card(Rank.SEVEN), card(Rank.SEVEN, Suit.DIAMONDS), card(Rank.KING)]
    targets = get_throw_in_targets(table, NO_TRUMP)
    analysis = analyze_throw_in([card(Rank.JACK)], table, NO_TRUMP)

    assert targets.arithmetic_mean == Fraction(32, 3)
    assert targets.arithmetic_mean != 11
    assert ThrowInReason.ARITHMETIC_MEAN not in analysis.reasons


def test_all_applicable_reasons_are_preserved() -> None:
    analysis = analyze_throw_in(
        [card(Rank.TEN), card(Rank.EIGHT)],
        [card(Rank.KING)],
        NO_TRUMP,
    )

    assert analysis.reasons == frozenset(
        {
            ThrowInReason.EXISTING_VALUE,
            ThrowInReason.TABLE_TOTAL,
            ThrowInReason.ARITHMETIC_MEAN,
        }
    )


def test_selection_cannot_recursively_justify_more_cards_in_same_action() -> None:
    analysis = analyze_throw_in(
        [card(Rank.TEN), card(Rank.EIGHT), card(Rank.TEN, Suit.DIAMONDS)],
        [card(Rank.KING)],
        NO_TRUMP,
    )

    assert analysis.legal is False
    assert analysis.reasons == frozenset()


def test_non_empty_selection_is_illegal_on_empty_table() -> None:
    analysis = analyze_throw_in([card(Rank.KING)], [], NO_TRUMP)

    assert analysis == ThrowInAnalysis(selected_value=18, reasons=frozenset())
    assert analysis.legal is False


def test_empty_selection_is_illegal() -> None:
    analysis = analyze_throw_in([], [card(Rank.KING)], NO_TRUMP)

    assert analysis == ThrowInAnalysis(selected_value=0, reasons=frozenset())
    assert analysis.legal is False


def test_trump_adjusted_table_targets_and_throw_in() -> None:
    table = [
        card(Rank.NINE, Suit.HEARTS),
        card(Rank.SIX),
        card(Rank.JACK),
    ]
    targets = get_throw_in_targets(table, hearts_trump())
    analysis = analyze_throw_in(
        [card(Rank.TEN), card(Rank.EIGHT)],
        table,
        hearts_trump(),
    )

    assert targets.represented_effective_values == frozenset({6, 12, 18})
    assert targets.table_total == 36
    assert targets.arithmetic_mean == Fraction(12)
    assert analysis.selected_value == 18
    assert ThrowInReason.EXISTING_VALUE in analysis.reasons


def test_throw_in_analysis_is_immutable() -> None:
    analysis = analyze_throw_in([card(Rank.TEN), card(Rank.EIGHT)], [card(Rank.KING)], NO_TRUMP)

    with pytest.raises(FrozenInstanceError):
        analysis.selected_value = 20  # type: ignore[misc]


def test_throw_in_analysis_does_not_mutate_inputs() -> None:
    selected = [card(Rank.TEN), card(Rank.EIGHT)]
    table = [card(Rank.KING)]
    original_selected = selected.copy()
    original_table = table.copy()

    analyze_throw_in(selected, table, NO_TRUMP)

    assert selected == original_selected
    assert table == original_table
