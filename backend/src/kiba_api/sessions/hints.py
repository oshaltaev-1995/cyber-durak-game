"""Bounded, read-only move hints backed by authoritative game transitions."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from enum import StrEnum
from itertools import combinations

from kiba_api.game import (
    BoutActionError,
    Card,
    GameActionError,
    GamePhase,
    GameState,
    InitialAttackReason,
    PacketTransferMode,
    Seat,
    ThrowInReason,
    analyze_defense,
    analyze_initial_attack,
    analyze_packet_transfer,
    analyze_throw_in,
    get_throw_in_targets,
)
from kiba_api.sessions.actions import (
    HumanActionType,
    acting_seat,
    apply_game_action,
    available_actions_for,
)

MAX_HINT_COMBINATIONS = 3
MAX_HINT_CANDIDATE_SELECTIONS = 4096
MAX_HINT_ADDITIONAL_CARDS = 5
MAX_HINT_INITIAL_ATTACK_CARDS = 7


class HintReason(StrEnum):
    """Stable, language-neutral explanations for canonical hint candidates."""

    SINGLE_CARD = "single_card"
    SAME_RANK = "same_rank"
    LATEST_DEFENSE_RANKS = "latest_defense_ranks"
    ARITHMETIC_EQUALITY = "arithmetic_equality"
    DEFENSE_TOTAL = "defense_total"
    TRANSFER_EXACT = "transfer_exact"
    SAME_RANK_TRANSFER = "same_rank_transfer"
    EXISTING_VALUE = "existing_value"
    TABLE_TOTAL = "table_total"
    ARITHMETIC_MEAN = "arithmetic_mean"
    RANK_RUN = "rank_run"


_THROW_IN_REASON_PRIORITY = (
    ThrowInReason.SAME_RANK,
    ThrowInReason.LATEST_DEFENSE_RANKS,
    ThrowInReason.EXISTING_VALUE,
    ThrowInReason.DEFENSE_TOTAL,
    ThrowInReason.TABLE_TOTAL,
    ThrowInReason.ARITHMETIC_MEAN,
    ThrowInReason.RANK_RUN,
)


class HintErrorCode(StrEnum):
    """Stable failures for a read-only hint request."""

    GAME_COMPLETE = "game_complete"
    WRONG_TURN = "wrong_turn"
    CARD_NOT_OWNED = "card_not_owned"


class HintError(ValueError):
    """A rejected hint request that never mutates authoritative state."""

    def __init__(self, code: HintErrorCode) -> None:
        self.code = code
        super().__init__(code.value)


@dataclass(frozen=True, slots=True)
class HintCombination:
    """One compact canonical completion or extension."""

    action: HumanActionType
    cards: tuple[Card, ...]
    added_cards: tuple[Card, ...]
    reason: HintReason
    selected_value: int
    target_value: int | None


@dataclass(frozen=True, slots=True)
class MoveHints:
    """Participant-private bounded suggestions for one selection."""

    selected_cards: tuple[Card, ...]
    suggested_cards: tuple[Card, ...]
    suggested_actions: tuple[HumanActionType, ...]
    combinations: tuple[HintCombination, ...]
    candidate_selections_examined: int


def get_move_hints(
    state: GameState,
    actor: Seat,
    selected_cards: Iterable[Card],
    *,
    max_combinations: int = MAX_HINT_COMBINATIONS,
    candidate_limit: int = MAX_HINT_CANDIDATE_SELECTIONS,
) -> MoveHints:
    """Find a small deterministic set of moves using only the actor's hand.

    Every returned combination is accepted by the same immutable game transition
    used for real actions. Search is intentionally bounded for TAKE-sized hands.
    """
    selected = tuple(selected_cards)
    _validate_positive_limit("max_combinations", max_combinations)
    _validate_positive_limit("candidate_limit", candidate_limit)
    if state.phase is GamePhase.COMPLETE:
        raise HintError(HintErrorCode.GAME_COMPLETE)
    if acting_seat(state) is not actor:
        raise HintError(HintErrorCode.WRONG_TURN)

    hand = state.hand(actor)
    _require_owned(hand, selected)
    if not selected:
        return MoveHints((), (), (), (), 0)

    actions = tuple(
        action
        for action in available_actions_for(state, actor)
        if action
        in {
            HumanActionType.INITIAL_ATTACK,
            HumanActionType.DEFEND,
            HumanActionType.TRANSFER,
            HumanActionType.THROW_IN,
        }
    )
    if not actions:
        return MoveHints(selected, (), (), (), 0)

    selected_counts = Counter(selected)
    remaining: list[Card] = []
    for card in hand:
        if selected_counts[card]:
            selected_counts[card] -= 1
        else:
            remaining.append(card)

    found: list[HintCombination] = []
    examined = 0
    for added in _candidate_additions(tuple(remaining)):
        if examined >= candidate_limit or len(found) >= max_combinations:
            break
        examined += 1
        candidate = (*selected, *added)
        for action in actions:
            if len(found) >= max_combinations:
                break
            if (
                action is HumanActionType.INITIAL_ATTACK
                and len(candidate) > MAX_HINT_INITIAL_ATTACK_CARDS
            ):
                continue
            try:
                apply_game_action(state, actor, action, candidate)
            except (BoutActionError, GameActionError):
                continue
            found.append(_describe_legal_candidate(state, action, candidate, added))

    suggested_cards = _ordered_unique(
        card for combination in found for card in combination.added_cards
    )
    suggested_actions = tuple(dict.fromkeys(combination.action for combination in found))
    return MoveHints(
        selected_cards=selected,
        suggested_cards=suggested_cards,
        suggested_actions=suggested_actions,
        combinations=tuple(found),
        candidate_selections_examined=examined,
    )


def _candidate_additions(remaining: tuple[Card, ...]) -> Iterator[tuple[Card, ...]]:
    yield ()
    for size in range(1, min(len(remaining), MAX_HINT_ADDITIONAL_CARDS) + 1):
        yield from combinations(remaining, size)


def _describe_legal_candidate(
    state: GameState,
    action: HumanActionType,
    cards: tuple[Card, ...],
    added_cards: tuple[Card, ...],
) -> HintCombination:
    bout = state.active_bout
    trump = state.current_trump_state
    if action is HumanActionType.INITIAL_ATTACK:
        analysis = analyze_initial_attack(cards, trump)
        reason = {
            InitialAttackReason.SINGLE_CARD: HintReason.SINGLE_CARD,
            InitialAttackReason.SAME_RANK: HintReason.SAME_RANK,
            InitialAttackReason.EQUAL_VALUE_GROUPS: HintReason.ARITHMETIC_EQUALITY,
            InitialAttackReason.CONNECTED_COMBINATION: HintReason.ARITHMETIC_EQUALITY,
        }[analysis.reason]
        return HintCombination(
            action,
            cards,
            added_cards,
            reason,
            sum(analysis.effective_values),
            None,
        )

    if bout is None:
        raise ValueError("card actions require an active bout")
    if action is HumanActionType.THROW_IN:
        analysis = analyze_throw_in(cards, bout.table_cards, bout.direct_anchor_cards, trump)
        throw_reason = next(
            reason for reason in _THROW_IN_REASON_PRIORITY if reason in analysis.reasons
        )
        targets = get_throw_in_targets(bout.table_cards, bout.direct_anchor_cards, trump)
        target_value: int | None = None
        if throw_reason is ThrowInReason.EXISTING_VALUE:
            target_value = analysis.selected_value
        elif throw_reason is ThrowInReason.DEFENSE_TOTAL:
            target_value = targets.defense_total
        elif throw_reason is ThrowInReason.TABLE_TOTAL:
            target_value = targets.table_total
        elif throw_reason is ThrowInReason.ARITHMETIC_MEAN and targets.arithmetic_mean is not None:
            target_value = int(targets.arithmetic_mean)
        return HintCombination(
            action,
            cards,
            added_cards,
            HintReason(throw_reason.value),
            analysis.selected_value,
            target_value,
        )

    if bout.active_packet is None:
        raise ValueError("card response actions require an active packet")
    target = bout.active_packet.attack_value
    if action is HumanActionType.DEFEND:
        analysis = analyze_defense(cards, target, trump)
        return HintCombination(
            action,
            cards,
            added_cards,
            HintReason.DEFENSE_TOTAL,
            analysis.selected_value,
            target,
        )
    if action is HumanActionType.TRANSFER:
        analysis = analyze_packet_transfer(cards, bout.active_packet.attack_cards, target, trump)
        reason = (
            HintReason.SAME_RANK_TRANSFER
            if analysis.mode is PacketTransferMode.SAME_RANK_EXTENDED
            else HintReason.TRANSFER_EXACT
        )
        return HintCombination(action, cards, added_cards, reason, analysis.selected_value, target)

    raise ValueError(f"unsupported hint action: {action}")


def _require_owned(hand: tuple[Card, ...], selected: tuple[Card, ...]) -> None:
    hand_counts = Counter(hand)
    if any(count > hand_counts[card] for card, count in Counter(selected).items()):
        raise HintError(HintErrorCode.CARD_NOT_OWNED)


def _ordered_unique(cards: Iterable[Card]) -> tuple[Card, ...]:
    return tuple(dict.fromkeys(cards))


def _validate_positive_limit(name: str, value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an int")
    if value <= 0:
        raise ValueError(f"{name} must be positive")
