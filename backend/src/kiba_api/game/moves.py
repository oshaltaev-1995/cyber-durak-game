"""Pure defense and throw-in rule primitives."""

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from fractions import Fraction

from kiba_api.game.arithmetic import (
    cards_have_same_rank,
    matches_exact_value,
    summarize_table_arithmetic,
)
from kiba_api.game.cards import Card, TrumpState
from kiba_api.game.scoring import get_cards_value, get_effective_value


class ThrowInReason(StrEnum):
    """A confirmed rule that independently permits a throw-in selection."""

    SAME_RANK = "same_rank"
    EXISTING_VALUE = "existing_value"
    TABLE_TOTAL = "table_total"
    ARITHMETIC_MEAN = "arithmetic_mean"


@dataclass(frozen=True, slots=True)
class ThrowInTargets:
    """Arithmetic targets exposed by the current physical table cards."""

    represented_effective_values: frozenset[int]
    table_total: int | None
    arithmetic_mean: Fraction | None


@dataclass(frozen=True, slots=True)
class ThrowInAnalysis:
    """The exact value and all confirmed reasons for a throw-in selection."""

    selected_value: int
    reasons: frozenset[ThrowInReason]

    @property
    def legal(self) -> bool:
        """Return whether at least one confirmed throw-in rule applies."""
        return bool(self.reasons)


def is_legal_defense(
    cards: Iterable[Card],
    attack_value: int,
    trump_state: TrumpState,
) -> bool:
    """Return whether non-empty defense cards strictly exceed the attack value."""
    if isinstance(attack_value, bool) or not isinstance(attack_value, int):
        raise TypeError("attack_value must be an int")
    if attack_value < 0:
        raise ValueError("attack_value must not be negative")

    defense_cards = tuple(cards)
    return bool(defense_cards) and get_cards_value(defense_cards, trump_state) > attack_value


def get_throw_in_targets(
    table_cards: Iterable[Card],
    trump_state: TrumpState,
) -> ThrowInTargets:
    """Derive immutable arithmetic targets from the pre-action table."""
    table = tuple(table_cards)
    if not table:
        return ThrowInTargets(
            represented_effective_values=frozenset(),
            table_total=None,
            arithmetic_mean=None,
        )

    summary = summarize_table_arithmetic(table, trump_state)
    return ThrowInTargets(
        represented_effective_values=frozenset(
            get_effective_value(card, trump_state) for card in table
        ),
        table_total=summary.total_effective_value,
        arithmetic_mean=summary.arithmetic_mean,
    )


def analyze_throw_in(
    selected_cards: Iterable[Card],
    table_cards: Iterable[Card],
    trump_state: TrumpState,
) -> ThrowInAnalysis:
    """Evaluate one selection against only the supplied pre-action table."""
    selected = tuple(selected_cards)
    table = tuple(table_cards)
    selected_value = get_cards_value(selected, trump_state)

    if not selected or not table:
        return ThrowInAnalysis(selected_value=selected_value, reasons=frozenset())

    reasons: set[ThrowInReason] = set()
    targets = get_throw_in_targets(table, trump_state)

    if _has_represented_same_rank(selected, table):
        reasons.add(ThrowInReason.SAME_RANK)

    if any(
        matches_exact_value(selected, target, trump_state)
        for target in targets.represented_effective_values
    ):
        reasons.add(ThrowInReason.EXISTING_VALUE)

    if targets.table_total is not None and matches_exact_value(
        selected,
        targets.table_total,
        trump_state,
    ):
        reasons.add(ThrowInReason.TABLE_TOTAL)

    if targets.arithmetic_mean is not None and matches_exact_value(
        selected,
        targets.arithmetic_mean,
        trump_state,
    ):
        reasons.add(ThrowInReason.ARITHMETIC_MEAN)

    return ThrowInAnalysis(selected_value=selected_value, reasons=frozenset(reasons))


def _has_represented_same_rank(selected: tuple[Card, ...], table: tuple[Card, ...]) -> bool:
    selection_shares_rank = len(selected) == 1 or cards_have_same_rank(selected)
    if not selection_shares_rank:
        return False
    selected_rank = selected[0].rank
    return any(card.rank is selected_rank for card in table)
