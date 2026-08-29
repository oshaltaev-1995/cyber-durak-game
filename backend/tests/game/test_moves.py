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
    analyze_rank_run_throw_in,
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


def test_rank_run_fills_one_missing_rank_from_historical_table() -> None:
    table = [card(Rank.TEN), card(Rank.JACK), card(Rank.KING), card(Rank.ACE)]

    analysis = analyze_throw_in([card(Rank.QUEEN)], table, [], NO_TRUMP)

    assert ThrowInReason.RANK_RUN in analysis.reasons
    assert analysis.rank_run is not None
    assert analysis.rank_run.start is Rank.TEN
    assert analysis.rank_run.end is Rank.ACE
    assert analysis.rank_run.length == 5

    direct = analyze_rank_run_throw_in(table, [card(Rank.QUEEN)])
    assert direct == analysis.rank_run


def test_rank_run_selection_can_collectively_fill_multiple_gaps() -> None:
    table = [card(Rank.SIX), card(Rank.NINE), card(Rank.JACK)]
    selected = [card(Rank.SEVEN), card(Rank.EIGHT), card(Rank.TEN)]

    analysis = analyze_throw_in(selected, table, [], NO_TRUMP)

    assert analysis.reasons == frozenset({ThrowInReason.RANK_RUN})
    assert analysis.rank_run is not None
    assert analysis.rank_run.ranks == (
        Rank.SIX,
        Rank.SEVEN,
        Rank.EIGHT,
        Rank.NINE,
        Rank.TEN,
        Rank.JACK,
    )


def test_rank_run_can_extend_across_the_full_36_card_rank_order() -> None:
    table = [card(Rank.TEN), card(Rank.JACK), card(Rank.KING), card(Rank.ACE)]
    selected = [
        card(Rank.QUEEN),
        card(Rank.NINE),
        card(Rank.EIGHT),
        card(Rank.SEVEN),
        card(Rank.SIX),
    ]

    analysis = analyze_throw_in(selected, table, [], NO_TRUMP)

    assert ThrowInReason.RANK_RUN in analysis.reasons
    assert analysis.rank_run is not None
    assert analysis.rank_run.start is Rank.SIX
    assert analysis.rank_run.end is Rank.ACE
    assert analysis.rank_run.length == 9


def test_rank_run_rejects_unrelated_selected_baggage() -> None:
    table = [card(Rank.TEN), card(Rank.JACK), card(Rank.KING), card(Rank.ACE)]

    analysis = analyze_throw_in(
        [card(Rank.QUEEN), card(Rank.SIX)],
        table,
        [],
        NO_TRUMP,
    )

    assert ThrowInReason.RANK_RUN not in analysis.reasons
    assert analysis.rank_run is None


def test_rank_run_ignores_duplicates_but_allows_selected_duplicates() -> None:
    table = [
        card(Rank.TEN),
        card(Rank.JACK),
        card(Rank.KING),
        card(Rank.ACE),
        card(Rank.TEN, Suit.DIAMONDS),
    ]

    analysis = analyze_throw_in(
        [card(Rank.QUEEN), card(Rank.QUEEN, Suit.DIAMONDS)],
        table,
        [],
        NO_TRUMP,
    )

    assert ThrowInReason.RANK_RUN in analysis.reasons
    assert analysis.rank_run is not None
    assert analysis.rank_run.length == 5


def test_rank_run_requires_five_distinct_contiguous_ranks() -> None:
    table = [card(Rank.TEN), card(Rank.JACK), card(Rank.KING)]

    analysis = analyze_throw_in([card(Rank.QUEEN)], table, [], NO_TRUMP)

    assert ThrowInReason.RANK_RUN not in analysis.reasons


def test_rank_run_is_rank_based_and_can_coexist_with_other_reasons() -> None:
    table = [card(Rank.TEN), card(Rank.JACK), card(Rank.QUEEN), card(Rank.KING), card(Rank.ACE)]
    direct_anchor = table[2]
    trump_state = TrumpState.from_source_card(card(Rank.SIX, Suit.HEARTS))

    analysis = analyze_throw_in(
        [card(Rank.QUEEN, Suit.DIAMONDS)],
        table,
        [direct_anchor],
        trump_state,
    )

    assert ThrowInReason.RANK_RUN in analysis.reasons
    assert ThrowInReason.SAME_RANK in analysis.reasons
    assert ThrowInReason.EXISTING_VALUE in analysis.reasons


def test_rank_run_does_not_apply_to_empty_table_or_selection() -> None:
    assert (
        ThrowInReason.RANK_RUN not in analyze_throw_in([card(Rank.QUEEN)], [], [], NO_TRUMP).reasons
    )
    assert (
        ThrowInReason.RANK_RUN not in analyze_throw_in([], [card(Rank.TEN)], [], NO_TRUMP).reasons
    )


def test_non_integer_attack_value_is_rejected() -> None:
    with pytest.raises(TypeError, match="must be an int"):
        is_legal_defense([card(Rank.SIX)], 1.5, NO_TRUMP)  # type: ignore[arg-type]


def test_defense_does_not_mutate_input() -> None:
    defense = [card(Rank.QUEEN), card(Rank.TEN)]
    original = defense.copy()

    is_legal_defense(defense, 20, NO_TRUMP)

    assert defense == original


def test_throw_in_targets_derive_unique_arithmetic_sources() -> None:
    table = [card(Rank.SEVEN), card(Rank.SEVEN, Suit.DIAMONDS), card(Rank.KING)]
    targets = get_throw_in_targets(
        table,
        [table[0], table[2]],
        NO_TRUMP,
    )

    assert targets == ThrowInTargets(
        represented_effective_values=frozenset({7, 18}),
        defense_total=25,
        table_total=32,
        arithmetic_mean=Fraction(32, 3),
    )


def test_throw_in_targets_separate_direct_anchors_from_table_arithmetic() -> None:
    table = [card(Rank.JACK), card(Rank.KING)]

    targets = get_throw_in_targets(table, [table[1]], NO_TRUMP)

    assert targets == ThrowInTargets(
        represented_effective_values=frozenset({18}),
        defense_total=None,
        table_total=30,
        arithmetic_mean=Fraction(15),
    )


def test_empty_table_has_no_throw_in_targets() -> None:
    assert get_throw_in_targets([], [], NO_TRUMP) == ThrowInTargets(
        represented_effective_values=frozenset(),
        defense_total=None,
        table_total=None,
        arithmetic_mean=None,
    )


@pytest.mark.parametrize(
    ("table", "direct_anchors"),
    [
        ([], [card(Rank.KING)]),
        ([card(Rank.JACK)], [card(Rank.KING)]),
        ([card(Rank.KING)], [card(Rank.KING), card(Rank.KING)]),
    ],
)
def test_direct_anchors_must_be_a_multiset_subset_of_table(
    table: list[Card],
    direct_anchors: list[Card],
) -> None:
    with pytest.raises(ValueError, match="multiset subset"):
        get_throw_in_targets(table, direct_anchors, NO_TRUMP)


def test_equal_card_value_can_identify_an_anchor_in_the_table() -> None:
    table_card = card(Rank.KING)
    equivalent_anchor = card(Rank.KING)

    targets = get_throw_in_targets([table_card], [equivalent_anchor], NO_TRUMP)

    assert targets.represented_effective_values == frozenset({18})


def test_throw_in_targets_are_immutable() -> None:
    king = card(Rank.KING)
    targets = get_throw_in_targets([king], [king], NO_TRUMP)

    with pytest.raises(FrozenInstanceError):
        targets.table_total = 20  # type: ignore[misc]


def test_one_selected_card_matches_rank_represented_on_table() -> None:
    table = [card(Rank.NINE, Suit.CLUBS), card(Rank.SIX)]
    analysis = analyze_throw_in(
        [card(Rank.NINE, Suit.HEARTS)],
        table,
        [table[0]],
        NO_TRUMP,
    )

    assert analysis.legal is True
    assert ThrowInReason.SAME_RANK in analysis.reasons


def test_same_rank_selected_group_matches_rank_represented_on_table() -> None:
    table = [card(Rank.NINE, Suit.CLUBS), card(Rank.SIX)]
    analysis = analyze_throw_in(
        [card(Rank.NINE, Suit.HEARTS), card(Rank.NINE, Suit.SPADES)],
        table,
        [table[0]],
        NO_TRUMP,
    )

    assert ThrowInReason.SAME_RANK in analysis.reasons


def test_rank_mismatch_does_not_qualify_as_same_rank() -> None:
    table = [card(Rank.KING), card(Rank.SIX)]
    analysis = analyze_throw_in(
        [card(Rank.NINE)],
        table,
        table,
        NO_TRUMP,
    )

    assert ThrowInReason.SAME_RANK not in analysis.reasons


def test_mixed_rank_selection_does_not_qualify_as_same_rank() -> None:
    table = [card(Rank.NINE, Suit.HEARTS), card(Rank.SIX)]
    analysis = analyze_throw_in(
        [card(Rank.NINE), card(Rank.KING)],
        table,
        [table[0]],
        NO_TRUMP,
    )

    assert ThrowInReason.SAME_RANK not in analysis.reasons


def test_each_selected_rank_may_match_a_different_direct_anchor() -> None:
    attack = card(Rank.SIX)
    defense_seven = card(Rank.SEVEN, Suit.HEARTS)
    defense_jack = card(Rank.JACK, Suit.DIAMONDS)
    table = [attack, defense_seven, defense_jack]
    direct_anchors = [defense_seven, defense_jack]

    selected_seven = analyze_throw_in(
        [card(Rank.SEVEN, Suit.SPADES)],
        table,
        direct_anchors,
        NO_TRUMP,
    )
    selected_jack = analyze_throw_in(
        [card(Rank.JACK, Suit.HEARTS)],
        table,
        direct_anchors,
        NO_TRUMP,
    )
    selected_together = analyze_throw_in(
        [card(Rank.SEVEN, Suit.SPADES), card(Rank.JACK, Suit.HEARTS)],
        table,
        direct_anchors,
        NO_TRUMP,
    )

    assert selected_seven.reasons == frozenset(
        {ThrowInReason.SAME_RANK, ThrowInReason.EXISTING_VALUE}
    )
    assert selected_jack.reasons == frozenset(
        {ThrowInReason.SAME_RANK, ThrowInReason.EXISTING_VALUE}
    )
    assert selected_together.selected_value == 19
    assert selected_together.reasons == frozenset(
        {ThrowInReason.SAME_RANK, ThrowInReason.DEFENSE_TOTAL}
    )
    assert selected_together.legal is True


@pytest.mark.parametrize(
    "selection",
    [
        [card(Rank.SEVEN, Suit.SPADES)],
        [card(Rank.JACK, Suit.HEARTS)],
        [card(Rank.SEVEN, Suit.SPADES), card(Rank.JACK, Suit.HEARTS)],
        [card(Rank.SEVEN, Suit.SPADES), card(Rank.SEVEN, Suit.DIAMONDS)],
        [card(Rank.JACK, Suit.HEARTS), card(Rank.JACK, Suit.SPADES)],
        [
            card(Rank.SEVEN, Suit.SPADES),
            card(Rank.SEVEN, Suit.DIAMONDS),
            card(Rank.JACK, Suit.HEARTS),
        ],
        [
            card(Rank.SEVEN, Suit.SPADES),
            card(Rank.JACK, Suit.HEARTS),
            card(Rank.JACK, Suit.SPADES),
        ],
    ],
)
def test_same_rank_reason_accepts_selections_drawn_from_all_anchor_ranks(
    selection: list[Card],
) -> None:
    attack = card(Rank.SIX)
    direct_anchors = [
        card(Rank.SEVEN, Suit.HEARTS),
        card(Rank.JACK, Suit.DIAMONDS),
    ]

    analysis = analyze_throw_in(
        selection,
        [attack, *direct_anchors],
        direct_anchors,
        NO_TRUMP,
    )

    assert ThrowInReason.SAME_RANK in analysis.reasons


@pytest.mark.parametrize(
    "selection",
    [
        [card(Rank.SEVEN), card(Rank.NINE)],
        [card(Rank.JACK), card(Rank.NINE)],
        [card(Rank.NINE)],
        [card(Rank.SIX, Suit.SPADES)],
    ],
)
def test_same_rank_reason_rejects_any_rank_absent_from_direct_anchors(
    selection: list[Card],
) -> None:
    attack = card(Rank.SIX)
    direct_anchors = [
        card(Rank.SEVEN, Suit.HEARTS),
        card(Rank.JACK, Suit.DIAMONDS),
    ]

    analysis = analyze_throw_in(
        selection,
        [attack, *direct_anchors],
        direct_anchors,
        NO_TRUMP,
    )

    assert ThrowInReason.SAME_RANK not in analysis.reasons


def test_jokers_share_the_same_rank_for_throw_ins() -> None:
    table = [joker(JokerColor.RED), card(Rank.SIX)]
    analysis = analyze_throw_in(
        [joker(JokerColor.BLACK)],
        table,
        [table[0]],
        NO_TRUMP,
    )

    assert ThrowInReason.SAME_RANK in analysis.reasons


def test_trump_changes_value_but_not_same_rank_relation() -> None:
    table = [card(Rank.NINE, Suit.CLUBS)]
    analysis = analyze_throw_in(
        [card(Rank.NINE, Suit.HEARTS)],
        table,
        table,
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
    table = [card(Rank.KING), card(Rank.SIX)]
    analysis = analyze_throw_in(
        selection,
        table,
        [table[0]],
        NO_TRUMP,
    )

    assert analysis.legal is True
    assert ThrowInReason.EXISTING_VALUE in analysis.reasons


def test_unrepresented_value_has_no_existing_value_reason() -> None:
    table = [card(Rank.ACE), card(Rank.QUEEN)]
    analysis = analyze_throw_in(
        [card(Rank.JACK), card(Rank.SIX)],
        table,
        table,
        NO_TRUMP,
    )

    assert analysis.selected_value == 18
    assert ThrowInReason.EXISTING_VALUE not in analysis.reasons


def test_value_seventeen_is_illegal_when_no_table_rule_exposes_it() -> None:
    table = [card(Rank.KING), card(Rank.SIX)]
    analysis = analyze_throw_in(
        [card(Rank.NINE), card(Rank.EIGHT)],
        table,
        table,
        NO_TRUMP,
    )

    assert analysis.selected_value == 17
    assert analysis.legal is False
    assert analysis.reasons == frozenset()


@pytest.mark.parametrize(
    ("selection", "excluded_reason"),
    [
        ([card(Rank.JACK)], ThrowInReason.SAME_RANK),
        ([card(Rank.SIX), card(Rank.SIX, Suit.DIAMONDS)], ThrowInReason.EXISTING_VALUE),
    ],
)
def test_covered_attack_card_is_not_a_direct_throw_in_anchor(
    selection: list[Card],
    excluded_reason: ThrowInReason,
) -> None:
    table = [card(Rank.JACK), card(Rank.KING)]

    analysis = analyze_throw_in(selection, table, [table[1]], NO_TRUMP)

    assert excluded_reason not in analysis.reasons
    assert analysis.legal is False


def test_defense_card_exposes_same_rank_as_a_direct_anchor() -> None:
    table = [card(Rank.JACK), card(Rank.KING)]

    analysis = analyze_throw_in(
        [card(Rank.KING, Suit.DIAMONDS)],
        table,
        [table[1]],
        NO_TRUMP,
    )

    assert ThrowInReason.SAME_RANK in analysis.reasons


@pytest.mark.parametrize(
    "selection",
    [
        [card(Rank.TEN), card(Rank.EIGHT)],
        [card(Rank.JACK), card(Rank.SIX)],
    ],
)
def test_defense_card_exposes_effective_value_as_a_direct_anchor(
    selection: list[Card],
) -> None:
    table = [card(Rank.JACK), card(Rank.KING)]

    analysis = analyze_throw_in(selection, table, [table[1]], NO_TRUMP)

    assert ThrowInReason.EXISTING_VALUE in analysis.reasons


def test_covered_attack_card_remains_in_table_total() -> None:
    table = [card(Rank.JACK), card(Rank.KING)]

    analysis = analyze_throw_in(
        [card(Rank.QUEEN), card(Rank.QUEEN, Suit.DIAMONDS)],
        table,
        [table[1]],
        NO_TRUMP,
    )

    assert analysis.reasons == frozenset({ThrowInReason.TABLE_TOTAL})


@pytest.mark.parametrize(
    "selection",
    [[card(Rank.QUEEN)], [card(Rank.SEVEN), card(Rank.EIGHT)]],
)
def test_covered_attack_card_remains_in_arithmetic_mean(
    selection: list[Card],
) -> None:
    table = [card(Rank.JACK), card(Rank.KING)]

    analysis = analyze_throw_in(selection, table, [table[1]], NO_TRUMP)

    assert analysis.reasons == frozenset({ThrowInReason.ARITHMETIC_MEAN})


def test_empty_direct_anchors_disable_direct_rules_only() -> None:
    table = [card(Rank.JACK), card(Rank.KING)]

    targets = get_throw_in_targets(table, [], NO_TRUMP)
    direct_rank = analyze_throw_in([card(Rank.KING)], table, [], NO_TRUMP)
    direct_value = analyze_throw_in(
        [card(Rank.TEN), card(Rank.EIGHT)],
        table,
        [],
        NO_TRUMP,
    )
    mean = analyze_throw_in([card(Rank.QUEEN)], table, [], NO_TRUMP)
    total = analyze_throw_in(
        [card(Rank.QUEEN), card(Rank.QUEEN, Suit.DIAMONDS)],
        table,
        [],
        NO_TRUMP,
    )

    assert targets == ThrowInTargets(
        represented_effective_values=frozenset(),
        defense_total=None,
        table_total=30,
        arithmetic_mean=Fraction(15),
    )
    assert direct_rank.reasons == frozenset()
    assert direct_value.reasons == frozenset()
    assert mean.reasons == frozenset({ThrowInReason.ARITHMETIC_MEAN})
    assert total.reasons == frozenset({ThrowInReason.TABLE_TOTAL})


def test_direct_value_and_mean_reasons_are_both_preserved() -> None:
    table = [card(Rank.JACK), card(Rank.KING), card(Rank.QUEEN)]

    analysis = analyze_throw_in(
        [card(Rank.SEVEN), card(Rank.EIGHT)],
        table,
        [table[2]],
        NO_TRUMP,
    )

    assert analysis.reasons == frozenset(
        {
            ThrowInReason.EXISTING_VALUE,
            ThrowInReason.ARITHMETIC_MEAN,
        }
    )


@pytest.mark.parametrize(
    "selection",
    [
        [card(Rank.ACE)],
        [card(Rank.TEN), card(Rank.TEN, Suit.DIAMONDS)],
    ],
)
def test_latest_multi_card_defense_total_is_an_exact_throw_in_target(
    selection: list[Card],
) -> None:
    attack = card(Rank.SIX)
    defense = [card(Rank.JACK), card(Rank.EIGHT)]
    table = [attack, *defense]

    targets = get_throw_in_targets(table, defense, NO_TRUMP)
    analysis = analyze_throw_in(selection, table, defense, NO_TRUMP)

    assert targets.defense_total == 20
    assert analysis.selected_value == 20
    assert ThrowInReason.DEFENSE_TOTAL in analysis.reasons


@pytest.mark.parametrize(
    "selection",
    [
        [card(Rank.JACK), card(Rank.SEVEN)],
        [card(Rank.QUEEN), card(Rank.SIX)],
    ],
)
def test_nearby_values_do_not_match_latest_defense_total(selection: list[Card]) -> None:
    attack = card(Rank.SIX)
    defense = [card(Rank.JACK), card(Rank.EIGHT)]

    analysis = analyze_throw_in(selection, [attack, *defense], defense, NO_TRUMP)

    assert analysis.selected_value in {19, 21}
    assert ThrowInReason.DEFENSE_TOTAL not in analysis.reasons


def test_latest_defense_total_uses_trump_adjusted_values() -> None:
    trump_state = TrumpState.from_source_card(card(Rank.KING, Suit.HEARTS))
    attack = card(Rank.SIX)
    defense = [card(Rank.SIX, Suit.HEARTS), card(Rank.EIGHT)]
    selection = [card(Rank.ACE)]

    analysis = analyze_throw_in(
        selection,
        [attack, *defense],
        defense,
        trump_state,
    )

    assert analysis.selected_value == 20
    assert ThrowInReason.DEFENSE_TOTAL in analysis.reasons


def test_single_defense_card_does_not_duplicate_existing_value_reason() -> None:
    king = card(Rank.KING)

    analysis = analyze_throw_in(
        [card(Rank.TEN), card(Rank.EIGHT)],
        [card(Rank.JACK), king],
        [king],
        NO_TRUMP,
    )

    assert ThrowInReason.EXISTING_VALUE in analysis.reasons
    assert ThrowInReason.DEFENSE_TOTAL not in analysis.reasons


def test_selection_can_match_table_total() -> None:
    table = [card(Rank.SEVEN), card(Rank.SEVEN, Suit.DIAMONDS), card(Rank.KING)]
    analysis = analyze_throw_in(
        [card(Rank.ACE), card(Rank.JACK)],
        table,
        [table[2]],
        NO_TRUMP,
    )

    assert analysis.selected_value == 32
    assert ThrowInReason.TABLE_TOTAL in analysis.reasons


def test_nearby_value_does_not_match_table_total() -> None:
    table = [card(Rank.SEVEN), card(Rank.SEVEN, Suit.DIAMONDS), card(Rank.KING)]
    analysis = analyze_throw_in(
        [joker(JokerColor.RED), card(Rank.SIX)],
        table,
        [table[2]],
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
    table = [card(Rank.JACK), card(Rank.KING)]
    analysis = analyze_throw_in(
        selection,
        table,
        [table[1]],
        NO_TRUMP,
    )

    assert analysis.selected_value == 15
    assert ThrowInReason.ARITHMETIC_MEAN in analysis.reasons


def test_recalculated_mean_remains_exact() -> None:
    table = [card(Rank.JACK), card(Rank.KING), card(Rank.QUEEN)]
    targets = get_throw_in_targets(table, [table[2]], NO_TRUMP)
    analysis = analyze_throw_in(
        [card(Rank.SEVEN), card(Rank.EIGHT)],
        table,
        [table[2]],
        NO_TRUMP,
    )

    assert targets.arithmetic_mean == Fraction(15)
    assert ThrowInReason.ARITHMETIC_MEAN in analysis.reasons


def test_non_integer_mean_is_not_rounded() -> None:
    table = [card(Rank.SEVEN), card(Rank.SEVEN, Suit.DIAMONDS), card(Rank.KING)]
    targets = get_throw_in_targets(table, [table[2]], NO_TRUMP)
    analysis = analyze_throw_in([card(Rank.JACK)], table, [table[2]], NO_TRUMP)

    assert targets.arithmetic_mean == Fraction(32, 3)
    assert targets.arithmetic_mean != 11
    assert ThrowInReason.ARITHMETIC_MEAN not in analysis.reasons


def test_all_applicable_reasons_are_preserved() -> None:
    table = [card(Rank.KING)]
    analysis = analyze_throw_in(
        [card(Rank.TEN), card(Rank.EIGHT)],
        table,
        table,
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
    table = [card(Rank.KING)]
    analysis = analyze_throw_in(
        [card(Rank.TEN), card(Rank.EIGHT), card(Rank.TEN, Suit.DIAMONDS)],
        table,
        table,
        NO_TRUMP,
    )

    assert analysis.legal is False
    assert analysis.reasons == frozenset()


def test_non_empty_selection_is_illegal_on_empty_table() -> None:
    analysis = analyze_throw_in([card(Rank.KING)], [], [], NO_TRUMP)

    assert analysis == ThrowInAnalysis(selected_value=18, reasons=frozenset())
    assert analysis.legal is False


def test_empty_selection_is_illegal() -> None:
    king = card(Rank.KING)
    analysis = analyze_throw_in([], [king], [king], NO_TRUMP)

    assert analysis == ThrowInAnalysis(selected_value=0, reasons=frozenset())
    assert analysis.legal is False


def test_trump_adjusted_table_targets_and_throw_in() -> None:
    table = [
        card(Rank.NINE, Suit.HEARTS),
        card(Rank.SIX),
        card(Rank.JACK),
    ]
    targets = get_throw_in_targets(table, [table[0]], hearts_trump())
    analysis = analyze_throw_in(
        [card(Rank.TEN), card(Rank.EIGHT)],
        table,
        [table[0]],
        hearts_trump(),
    )

    assert targets.represented_effective_values == frozenset({18})
    assert targets.table_total == 36
    assert targets.arithmetic_mean == Fraction(12)
    assert analysis.selected_value == 18
    assert ThrowInReason.EXISTING_VALUE in analysis.reasons


def test_throw_in_analysis_is_immutable() -> None:
    king = card(Rank.KING)
    analysis = analyze_throw_in(
        [card(Rank.TEN), card(Rank.EIGHT)],
        [king],
        [king],
        NO_TRUMP,
    )

    with pytest.raises(FrozenInstanceError):
        analysis.selected_value = 20  # type: ignore[misc]


def test_throw_in_analysis_does_not_mutate_inputs() -> None:
    selected = [card(Rank.TEN), card(Rank.EIGHT)]
    table = [card(Rank.KING)]
    direct_anchors = table.copy()
    original_selected = selected.copy()
    original_table = table.copy()
    original_direct_anchors = direct_anchors.copy()

    analyze_throw_in(selected, table, direct_anchors, NO_TRUMP)

    assert selected == original_selected
    assert table == original_table
    assert direct_anchors == original_direct_anchors
