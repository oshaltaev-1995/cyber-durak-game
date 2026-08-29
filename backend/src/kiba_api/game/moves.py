"""Pure defense and throw-in rule primitives."""

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from fractions import Fraction

from kiba_api.game.arithmetic import (
    matches_exact_value,
    summarize_table_arithmetic,
)
from kiba_api.game.cards import Card, Rank, TrumpState
from kiba_api.game.scoring import get_cards_value, get_effective_value


class ThrowInReason(StrEnum):
    """A confirmed rule that independently permits a throw-in selection."""

    SAME_RANK = "same_rank"
    EXISTING_VALUE = "existing_value"
    DEFENSE_TOTAL = "defense_total"
    TABLE_TOTAL = "table_total"
    ARITHMETIC_MEAN = "arithmetic_mean"
    RANK_RUN = "rank_run"


@dataclass(frozen=True, slots=True)
class RankRun:
    """One server-confirmed contiguous normal-rank run."""

    start: Rank
    end: Rank
    length: int
    ranks: tuple[Rank, ...]


@dataclass(frozen=True, slots=True)
class ThrowInTargets:
    """Direct-anchor values and arithmetic targets from the physical table."""

    represented_effective_values: frozenset[int]
    defense_total: int | None
    table_total: int | None
    arithmetic_mean: Fraction | None


@dataclass(frozen=True, slots=True)
class ThrowInAnalysis:
    """The exact value and all confirmed reasons for a throw-in selection."""

    selected_value: int
    reasons: frozenset[ThrowInReason]
    rank_run: RankRun | None = None

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
    direct_anchor_cards: Iterable[Card],
    trump_state: TrumpState,
) -> ThrowInTargets:
    """Derive direct targets and physical-table arithmetic before an action."""
    table = tuple(table_cards)
    direct_anchors = tuple(direct_anchor_cards)
    _validate_direct_anchors(table, direct_anchors)

    if not table:
        return ThrowInTargets(
            represented_effective_values=frozenset(),
            defense_total=None,
            table_total=None,
            arithmetic_mean=None,
        )

    summary = summarize_table_arithmetic(table, trump_state)
    return ThrowInTargets(
        represented_effective_values=frozenset(
            get_effective_value(card, trump_state) for card in direct_anchors
        ),
        defense_total=(
            get_cards_value(direct_anchors, trump_state) if len(direct_anchors) > 1 else None
        ),
        table_total=summary.total_effective_value,
        arithmetic_mean=summary.arithmetic_mean,
    )


def analyze_throw_in(
    selected_cards: Iterable[Card],
    table_cards: Iterable[Card],
    direct_anchor_cards: Iterable[Card],
    trump_state: TrumpState,
) -> ThrowInAnalysis:
    """Evaluate a selection against supplied table arithmetic and direct anchors."""
    selected = tuple(selected_cards)
    table = tuple(table_cards)
    direct_anchors = tuple(direct_anchor_cards)
    selected_value = get_cards_value(selected, trump_state)
    targets = get_throw_in_targets(table, direct_anchors, trump_state)

    if not selected or not table:
        return ThrowInAnalysis(selected_value=selected_value, reasons=frozenset())

    reasons: set[ThrowInReason] = set()

    if _has_represented_same_rank(selected, direct_anchors):
        reasons.add(ThrowInReason.SAME_RANK)

    if any(
        matches_exact_value(selected, target, trump_state)
        for target in targets.represented_effective_values
    ):
        reasons.add(ThrowInReason.EXISTING_VALUE)

    if targets.defense_total is not None and matches_exact_value(
        selected,
        targets.defense_total,
        trump_state,
    ):
        reasons.add(ThrowInReason.DEFENSE_TOTAL)

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

    rank_run = analyze_rank_run_throw_in(table, selected)
    if rank_run is not None:
        reasons.add(ThrowInReason.RANK_RUN)

    return ThrowInAnalysis(
        selected_value=selected_value,
        reasons=frozenset(reasons),
        rank_run=rank_run,
    )


_RUN_RANKS = (
    Rank.SIX,
    Rank.SEVEN,
    Rank.EIGHT,
    Rank.NINE,
    Rank.TEN,
    Rank.JACK,
    Rank.QUEEN,
    Rank.KING,
    Rank.ACE,
)


def analyze_rank_run_throw_in(
    table_cards: Iterable[Card],
    selected_cards: Iterable[Card],
) -> RankRun | None:
    """Find the maximal five-plus rank run containing every selected rank."""
    table = tuple(table_cards)
    selected = tuple(selected_cards)
    selected_ranks = {card.rank for card in selected}
    if not selected or not table or Rank.JOKER in selected_ranks:
        return None

    represented_ranks = {card.rank for card in (*table, *selected)}
    block: list[Rank] = []
    for rank in (*_RUN_RANKS, None):
        if rank is not None and rank in represented_ranks:
            block.append(rank)
            continue
        if len(block) >= 5 and selected_ranks <= set(block):
            ranks = tuple(block)
            return RankRun(
                start=ranks[0],
                end=ranks[-1],
                length=len(ranks),
                ranks=ranks,
            )
        block = []
    return None


def _has_represented_same_rank(
    selected: tuple[Card, ...],
    direct_anchors: tuple[Card, ...],
) -> bool:
    direct_anchor_ranks = {card.rank for card in direct_anchors}
    return bool(selected) and all(card.rank in direct_anchor_ranks for card in selected)


def _validate_direct_anchors(
    table: tuple[Card, ...],
    direct_anchors: tuple[Card, ...],
) -> None:
    if not Counter(direct_anchors) <= Counter(table):
        raise ValueError("direct_anchor_cards must be a multiset subset of table_cards")
