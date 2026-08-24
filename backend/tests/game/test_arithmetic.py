from dataclasses import FrozenInstanceError
from fractions import Fraction

import pytest

from kiba_api.game import (
    Card,
    JokerColor,
    Rank,
    Suit,
    TableArithmeticSummary,
    TrumpState,
    cards_have_same_rank,
    find_exact_value_subsets,
    get_arithmetic_mean,
    matches_exact_value,
    summarize_table_arithmetic,
)

NO_TRUMP = TrumpState.no_trump()


def card(rank: Rank, suit: Suit = Suit.CLUBS) -> Card:
    return Card(rank=rank, suit=suit)


def joker(color: JokerColor) -> Card:
    return Card(rank=Rank.JOKER, joker_color=color)


def hearts_trump() -> TrumpState:
    return TrumpState.from_source_card(card(Rank.ACE, Suit.HEARTS))


@pytest.mark.parametrize(
    ("cards", "target"),
    [
        ([card(Rank.NINE), card(Rank.NINE, Suit.DIAMONDS)], 18),
        ([card(Rank.JACK), card(Rank.SIX)], 18),
        ([card(Rank.TEN), card(Rank.EIGHT)], 18),
        ([card(Rank.SEVEN), card(Rank.EIGHT)], 15),
    ],
)
def test_cards_match_exact_target(cards: list[Card], target: int) -> None:
    assert matches_exact_value(cards, target, NO_TRUMP) is True


def test_cards_reject_wrong_exact_target() -> None:
    cards = [card(Rank.SEVEN), card(Rank.NINE)]

    assert matches_exact_value(cards, 18, NO_TRUMP) is False


@pytest.mark.parametrize(("target", "expected"), [(0, True), (1, False)])
def test_empty_cards_only_match_zero(target: int, expected: bool) -> None:
    assert matches_exact_value([], target, NO_TRUMP) is expected


def test_exact_target_uses_trump_adjusted_value() -> None:
    trump_nine = card(Rank.NINE, Suit.HEARTS)

    assert matches_exact_value([trump_nine], 18, hearts_trump()) is True
    assert matches_exact_value([trump_nine], 9, hearts_trump()) is False


def test_subset_search_finds_one_card_solution() -> None:
    king = card(Rank.KING)

    assert find_exact_value_subsets([card(Rank.SEVEN), king], 18, NO_TRUMP) == ((king,),)


def test_subset_search_finds_multiple_card_solution() -> None:
    ten = card(Rank.TEN)
    eight = card(Rank.EIGHT)

    assert find_exact_value_subsets([ten, eight], 18, NO_TRUMP) == ((ten, eight),)


def test_subset_search_returns_alternative_solutions_deterministically() -> None:
    six = card(Rank.SIX)
    eight = card(Rank.EIGHT)
    nine = card(Rank.NINE)
    ten = card(Rank.TEN)
    jack = card(Rank.JACK)
    king = card(Rank.KING)
    available = [six, eight, nine, ten, jack, king]

    expected = ((king,), (six, jack), (eight, ten))

    assert find_exact_value_subsets(available, 18, NO_TRUMP) == expected
    assert find_exact_value_subsets(available, 18, NO_TRUMP) == expected


def test_subset_search_returns_no_solution() -> None:
    assert (
        find_exact_value_subsets(
            [card(Rank.SIX), card(Rank.SEVEN)],
            20,
            NO_TRUMP,
        )
        == ()
    )


def test_subset_search_distinguishes_equal_value_physical_cards() -> None:
    nine_of_clubs = card(Rank.NINE, Suit.CLUBS)
    nine_of_diamonds = card(Rank.NINE, Suit.DIAMONDS)

    assert find_exact_value_subsets(
        [nine_of_clubs, nine_of_diamonds],
        9,
        NO_TRUMP,
    ) == ((nine_of_clubs,), (nine_of_diamonds,))
    assert find_exact_value_subsets(
        [nine_of_clubs, nine_of_diamonds],
        18,
        NO_TRUMP,
    ) == ((nine_of_clubs, nine_of_diamonds),)


def test_subset_search_removes_duplicate_logical_results() -> None:
    nine = card(Rank.NINE)

    assert find_exact_value_subsets([nine, nine], 9, NO_TRUMP) == ((nine,),)
    assert find_exact_value_subsets([nine, nine], 18, NO_TRUMP) == ((nine, nine),)


def test_subset_search_uses_trump_adjusted_values() -> None:
    trump_nine = card(Rank.NINE, Suit.HEARTS)
    ten = card(Rank.TEN)
    eight = card(Rank.EIGHT, Suit.DIAMONDS)

    assert find_exact_value_subsets(
        [trump_nine, ten, eight],
        18,
        hearts_trump(),
    ) == ((trump_nine,), (ten, eight))


def test_subset_search_can_stop_after_first_solution() -> None:
    king = card(Rank.KING)
    ten = card(Rank.TEN)
    eight = card(Rank.EIGHT)

    assert find_exact_value_subsets(
        [king, ten, eight],
        18,
        NO_TRUMP,
        first_only=True,
    ) == ((king,),)


def test_subset_search_does_not_mutate_input() -> None:
    available = [card(Rank.TEN), card(Rank.EIGHT), card(Rank.SIX)]
    original = available.copy()

    find_exact_value_subsets(available, 18, NO_TRUMP)

    assert available == original


def test_zero_target_has_the_empty_subset_as_its_only_solution() -> None:
    assert find_exact_value_subsets([card(Rank.SIX)], 0, NO_TRUMP) == ((),)


def test_pair_has_same_rank() -> None:
    assert cards_have_same_rank([card(Rank.NINE, Suit.CLUBS), card(Rank.NINE, Suit.HEARTS)])


@pytest.mark.parametrize("card_count", [3, 4])
def test_three_or_four_cards_have_same_rank(card_count: int) -> None:
    suits = list(Suit)[:card_count]

    assert cards_have_same_rank([card(Rank.KING, suit) for suit in suits])


def test_mismatched_cards_do_not_have_same_rank() -> None:
    assert cards_have_same_rank([card(Rank.NINE), card(Rank.KING)]) is False


@pytest.mark.parametrize("cards", [[], [card(Rank.NINE)]])
def test_fewer_than_two_cards_do_not_establish_same_rank(cards: list[Card]) -> None:
    assert cards_have_same_rank(cards) is False


def test_both_jokers_have_same_rank() -> None:
    assert cards_have_same_rank([joker(JokerColor.RED), joker(JokerColor.BLACK)]) is True


def test_joker_and_normal_card_do_not_have_same_rank() -> None:
    assert cards_have_same_rank([joker(JokerColor.RED), card(Rank.ACE)]) is False


@pytest.mark.parametrize(
    ("cards", "expected"),
    [
        ([card(Rank.JACK), card(Rank.KING)], Fraction(15)),
        ([card(Rank.JACK), card(Rank.KING), card(Rank.QUEEN)], Fraction(15)),
        (
            [card(Rank.SEVEN), card(Rank.SEVEN, Suit.DIAMONDS), card(Rank.KING)],
            Fraction(32, 3),
        ),
    ],
)
def test_arithmetic_mean_is_exact(cards: list[Card], expected: Fraction) -> None:
    assert get_arithmetic_mean(cards, NO_TRUMP) == expected


def test_arithmetic_mean_uses_trump_adjusted_values() -> None:
    cards = [card(Rank.NINE, Suit.HEARTS), card(Rank.SIX)]

    assert get_arithmetic_mean(cards, hearts_trump()) == Fraction(12)


def test_empty_cards_have_no_arithmetic_mean() -> None:
    assert get_arithmetic_mean([], NO_TRUMP) is None


def test_table_arithmetic_summary() -> None:
    summary = summarize_table_arithmetic(
        [card(Rank.JACK), card(Rank.KING), card(Rank.QUEEN)],
        NO_TRUMP,
    )

    assert summary == TableArithmeticSummary(
        total_effective_value=45,
        physical_card_count=3,
        arithmetic_mean=Fraction(15),
    )


def test_table_arithmetic_summary_uses_mixed_trump_values() -> None:
    summary = summarize_table_arithmetic(
        [card(Rank.NINE, Suit.HEARTS), card(Rank.SIX), card(Rank.JACK)],
        hearts_trump(),
    )

    assert summary.total_effective_value == 36
    assert summary.physical_card_count == 3
    assert summary.arithmetic_mean == Fraction(12)


def test_empty_table_arithmetic_summary() -> None:
    assert summarize_table_arithmetic([], NO_TRUMP) == TableArithmeticSummary(
        total_effective_value=0,
        physical_card_count=0,
        arithmetic_mean=None,
    )


def test_table_arithmetic_summary_is_immutable() -> None:
    summary = summarize_table_arithmetic([card(Rank.SIX)], NO_TRUMP)

    with pytest.raises(FrozenInstanceError):
        summary.physical_card_count = 2  # type: ignore[misc]
