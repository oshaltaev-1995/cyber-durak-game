"""Pure connectedness analysis for an initial Kiba attack."""

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from kiba_api.game.arithmetic import cards_have_same_rank
from kiba_api.game.cards import Card, TrumpState
from kiba_api.game.scoring import get_effective_value


class InitialAttackReason(StrEnum):
    """The smallest confirmed rule structure that makes an initial attack legal."""

    SINGLE_CARD = "single_card"
    SAME_RANK = "same_rank"
    EQUAL_VALUE_GROUPS = "equal_value_groups"
    CONNECTED_COMBINATION = "connected_combination"


@dataclass(frozen=True, slots=True)
class InitialAttackAnalysis:
    """Minimal deterministic result for initial-attack connectedness."""

    effective_values: tuple[int, ...]
    reason: InitialAttackReason | None

    @property
    def legal(self) -> bool:
        """Return whether every selected physical card belongs to one structure."""
        return self.reason is not None


def analyze_initial_attack(
    selected_cards: Iterable[Card],
    trump_state: TrumpState,
) -> InitialAttackAnalysis:
    """Analyze one initial attack without table-total or arithmetic-mean rules."""
    cards = tuple(selected_cards)
    values = tuple(get_effective_value(card, trump_state) for card in cards)

    if not cards:
        return InitialAttackAnalysis(effective_values=values, reason=None)
    if len(cards) == 1:
        return InitialAttackAnalysis(
            effective_values=values,
            reason=InitialAttackReason.SINGLE_CARD,
        )

    rank_relations = _get_same_rank_relations(cards)
    if _is_connected(rank_relations):
        return InitialAttackAnalysis(
            effective_values=values,
            reason=InitialAttackReason.SAME_RANK,
        )

    if _has_equal_value_partition(cards, values):
        return InitialAttackAnalysis(
            effective_values=values,
            reason=InitialAttackReason.EQUAL_VALUE_GROUPS,
        )

    arithmetic_relations = _get_equal_group_relations(cards, values)
    combined_relations = tuple(
        rank_neighbors | arithmetic_neighbors
        for rank_neighbors, arithmetic_neighbors in zip(
            rank_relations,
            arithmetic_relations,
            strict=True,
        )
    )
    reason = (
        InitialAttackReason.CONNECTED_COMBINATION if _is_connected(combined_relations) else None
    )
    return InitialAttackAnalysis(effective_values=values, reason=reason)


def is_legal_initial_attack(
    selected_cards: Iterable[Card],
    trump_state: TrumpState,
) -> bool:
    """Return initial-attack legality by delegating to the explanatory analysis."""
    return analyze_initial_attack(selected_cards, trump_state).legal


def _get_same_rank_relations(cards: tuple[Card, ...]) -> tuple[int, ...]:
    relations = [0] * len(cards)
    for left_index, left_card in enumerate(cards):
        for right_index in range(left_index + 1, len(cards)):
            if cards_have_same_rank((left_card, cards[right_index])):
                _connect(relations, left_index, right_index)
    return tuple(relations)


def _get_equal_group_relations(
    cards: tuple[Card, ...],
    values: tuple[int, ...],
) -> tuple[int, ...]:
    relations = [0] * len(cards)
    groups_by_value: defaultdict[int, list[tuple[int, tuple[str, ...]]]] = defaultdict(list)

    for mask in range(1, 1 << len(cards)):
        group_value = sum(values[index] for index in _indices(mask))
        rank_signature = tuple(sorted(cards[index].rank.value for index in _indices(mask)))
        groups_by_value[group_value].append((mask, rank_signature))

    for equal_groups in groups_by_value.values():
        for left_position, (left_mask, left_signature) in enumerate(equal_groups):
            for right_mask, right_signature in equal_groups[left_position + 1 :]:
                # Mirrored rank compositions add no relation beyond their separate
                # same-rank clusters (for example, 9 + 7 = 9 + 7).
                if left_mask & right_mask or left_signature == right_signature:
                    continue
                _connect_group(relations, left_mask | right_mask)

    return tuple(relations)


def _has_equal_value_partition(cards: tuple[Card, ...], values: tuple[int, ...]) -> bool:
    total = sum(values)
    full_mask = (1 << len(cards)) - 1

    for group_count in range(2, len(cards) + 1):
        if total % group_count:
            continue
        target = total // group_count
        candidate_groups = tuple(
            mask
            for mask in range(1, full_mask + 1)
            if sum(values[index] for index in _indices(mask)) == target
        )
        if _can_partition(
            cards,
            candidate_groups,
            full_mask,
            group_count,
            (),
        ):
            return True

    return False


def _can_partition(
    cards: tuple[Card, ...],
    candidate_groups: tuple[int, ...],
    remaining_mask: int,
    groups_needed: int,
    signatures: tuple[tuple[str, ...], ...],
) -> bool:
    if groups_needed == 0:
        return remaining_mask == 0 and len(set(signatures)) > 1

    first_remaining = remaining_mask & -remaining_mask
    for group_mask in candidate_groups:
        if not group_mask & first_remaining or group_mask & ~remaining_mask:
            continue
        signature = tuple(sorted(cards[index].rank.value for index in _indices(group_mask)))
        if _can_partition(
            cards,
            candidate_groups,
            remaining_mask ^ group_mask,
            groups_needed - 1,
            (*signatures, signature),
        ):
            return True

    return False


def _connect(relations: list[int], left_index: int, right_index: int) -> None:
    relations[left_index] |= 1 << right_index
    relations[right_index] |= 1 << left_index


def _connect_group(relations: list[int], mask: int) -> None:
    group_indices = tuple(_indices(mask))
    anchor = group_indices[0]
    for index in group_indices[1:]:
        _connect(relations, anchor, index)


def _indices(mask: int) -> Iterable[int]:
    while mask:
        least_significant_bit = mask & -mask
        yield least_significant_bit.bit_length() - 1
        mask ^= least_significant_bit


def _is_connected(relations: tuple[int, ...]) -> bool:
    if not relations:
        return False

    visited = 1
    frontier = 1
    while frontier:
        index_bit = frontier & -frontier
        frontier ^= index_bit
        index = index_bit.bit_length() - 1
        new_neighbors = relations[index] & ~visited
        visited |= new_neighbors
        frontier |= new_neighbors

    return visited == (1 << len(relations)) - 1
