"""Exact arithmetic and combinatorics primitives for Kiba cards."""

from collections.abc import Iterable
from dataclasses import dataclass
from fractions import Fraction
from itertools import combinations

from kiba_api.game.cards import Card, TrumpState
from kiba_api.game.scoring import get_cards_value


@dataclass(frozen=True, slots=True)
class TableArithmeticSummary:
    """Exact mathematical facts derived from physical table cards."""

    total_effective_value: int
    physical_card_count: int
    arithmetic_mean: Fraction | None


def matches_exact_value(
    cards: Iterable[Card],
    target: int | Fraction,
    trump_state: TrumpState,
) -> bool:
    """Return whether the cards' total effective value equals the target exactly."""
    return get_cards_value(cards, trump_state) == target


def find_exact_value_subsets(
    cards: Iterable[Card],
    target: int | Fraction,
    trump_state: TrumpState,
    *,
    first_only: bool = False,
) -> tuple[tuple[Card, ...], ...]:
    """Find unique exact-value subsets in stable size and input-position order.

    Input positions identify physical cards during the search. Equal result tuples
    are returned only once, while distinct cards with equal values remain distinct.
    """
    available_cards = tuple(cards)
    results: list[tuple[Card, ...]] = []
    seen_results: set[tuple[Card, ...]] = set()

    for subset_size in range(len(available_cards) + 1):
        for candidate in combinations(available_cards, subset_size):
            if candidate in seen_results:
                continue
            if not matches_exact_value(candidate, target, trump_state):
                continue

            seen_results.add(candidate)
            results.append(candidate)
            if first_only:
                return tuple(results)

    return tuple(results)


def cards_have_same_rank(cards: Iterable[Card]) -> bool:
    """Return whether at least two cards all have the same constrained rank."""
    card_group = tuple(cards)
    if len(card_group) < 2:
        return False

    first_rank = card_group[0].rank
    return all(card.rank is first_rank for card in card_group[1:])


def get_arithmetic_mean(
    cards: Iterable[Card],
    trump_state: TrumpState,
) -> Fraction | None:
    """Return the exact mean effective value, or None for no physical cards."""
    card_group = tuple(cards)
    return _mean(get_cards_value(card_group, trump_state), len(card_group))


def summarize_table_arithmetic(
    cards: Iterable[Card],
    trump_state: TrumpState,
) -> TableArithmeticSummary:
    """Derive exact arithmetic facts for physical table cards."""
    table_cards = tuple(cards)
    total = get_cards_value(table_cards, trump_state)
    card_count = len(table_cards)
    return TableArithmeticSummary(
        total_effective_value=total,
        physical_card_count=card_count,
        arithmetic_mean=_mean(total, card_count),
    )


def _mean(total: int, card_count: int) -> Fraction | None:
    if card_count == 0:
        return None
    return Fraction(total, card_count)
