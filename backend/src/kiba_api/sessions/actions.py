"""Shared application helpers for routing participant actions into GameState."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum

from kiba_api.game import (
    BoutPhase,
    BoutState,
    Card,
    GamePhase,
    GameState,
    Seat,
    ThrowInReason,
    analyze_throw_in,
    finish_bout,
    finish_game_bout,
    get_cards_value,
    play_defense,
    play_game_defense,
    play_game_initial_attack,
    play_game_throw_in,
    play_game_transfer,
    take,
    take_game_bout,
)


class HumanActionType(StrEnum):
    """One participant intent accepted by an application session."""

    INITIAL_ATTACK = "INITIAL_ATTACK"
    DEFEND = "DEFEND"
    TRANSFER = "TRANSFER"
    THROW_IN = "THROW_IN"
    TAKE = "TAKE"
    BITO = "BITO"


@dataclass(frozen=True, slots=True)
class ActionCounters:
    """Accepted action summary for one seat in one authoritative match."""

    action_count: int = 0
    transfer_count: int = 0
    take_count: int = 0
    throw_in_count: int = 0
    max_transfer_target: int = 0
    arithmetic_mean_throw_in_count: int = 0

    def __post_init__(self) -> None:
        for field_name in (
            "action_count",
            "transfer_count",
            "take_count",
            "throw_in_count",
            "max_transfer_target",
            "arithmetic_mean_throw_in_count",
        ):
            value = getattr(self, field_name)
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"{field_name} must be an int")
            if value < 0:
                raise ValueError(f"{field_name} must not be negative")


def record_accepted_action(
    counters: ActionCounters,
    previous_state: GameState,
    action_type: HumanActionType,
    selected: tuple[Card, ...],
) -> ActionCounters:
    """Return counters including one already-accepted authoritative action."""
    transfer_count = counters.transfer_count
    take_count = counters.take_count
    throw_in_count = counters.throw_in_count
    max_transfer_target = counters.max_transfer_target
    mean_throw_in_count = counters.arithmetic_mean_throw_in_count
    bout = previous_state.active_bout

    if action_type is HumanActionType.TRANSFER:
        transfer_count += 1
        if bout is not None and bout.transfer_target is not None:
            resulting_target = bout.transfer_target + get_cards_value(selected, bout.trump_state)
            max_transfer_target = max(max_transfer_target, resulting_target)
    elif action_type is HumanActionType.TAKE:
        take_count += 1
    elif action_type is HumanActionType.THROW_IN:
        throw_in_count += 1
        if bout is not None:
            analysis = analyze_throw_in(
                selected,
                bout.table_cards,
                bout.direct_anchor_cards,
                bout.trump_state,
                bout.deck_profile,
            )
            if ThrowInReason.ARITHMETIC_MEAN in analysis.reasons:
                mean_throw_in_count += 1

    return replace(
        counters,
        action_count=counters.action_count + 1,
        transfer_count=transfer_count,
        take_count=take_count,
        throw_in_count=throw_in_count,
        max_transfer_target=max_transfer_target,
        arithmetic_mean_throw_in_count=mean_throw_in_count,
    )


def acting_seat(state: GameState) -> Seat | None:
    """Return the seat that owns the next authoritative game decision."""
    if state.phase is GamePhase.COMPLETE:
        return None
    if state.phase is GamePhase.READY_FOR_BOUT:
        return state.current_attacker

    bout = state.active_bout
    if bout is None:
        raise ValueError("an active game requires an active bout")
    if bout.phase is BoutPhase.WAITING_FOR_DEFENDER_RESPONSE:
        return bout.defender
    if bout.phase in {
        BoutPhase.WAITING_FOR_INITIAL_ATTACK,
        BoutPhase.WAITING_FOR_ATTACKER_DECISION,
    }:
        return bout.attacker
    raise ValueError("GameState cannot retain a complete active bout")


def available_actions_for(state: GameState, seat: Seat) -> tuple[HumanActionType, ...]:
    """Return high-level actions available to one seat without enumerating cards."""
    if acting_seat(state) is not seat:
        return ()
    bout = state.active_bout
    if bout is None or bout.phase is BoutPhase.WAITING_FOR_INITIAL_ATTACK:
        return (HumanActionType.INITIAL_ATTACK,)
    if bout.phase is BoutPhase.WAITING_FOR_DEFENDER_RESPONSE:
        actions = [HumanActionType.DEFEND]
        if bout.transfer_open:
            actions.append(HumanActionType.TRANSFER)
        actions.append(HumanActionType.TAKE)
        return tuple(actions)
    if bout.phase is BoutPhase.WAITING_FOR_ATTACKER_DECISION:
        return (HumanActionType.THROW_IN, HumanActionType.BITO)
    return ()


def apply_game_action(
    state: GameState,
    actor: Seat,
    action_type: HumanActionType,
    cards: tuple[Card, ...],
) -> GameState:
    """Delegate a participant intent to the authoritative immutable game API."""
    if action_type is HumanActionType.INITIAL_ATTACK:
        return play_game_initial_attack(state, actor, cards)
    if action_type is HumanActionType.DEFEND:
        return play_game_defense(state, actor, cards)
    if action_type is HumanActionType.TRANSFER:
        return play_game_transfer(state, actor, cards)
    if action_type is HumanActionType.THROW_IN:
        return play_game_throw_in(state, actor, cards)
    if action_type is HumanActionType.TAKE:
        return take_game_bout(state, actor)
    if action_type is HumanActionType.BITO:
        return finish_game_bout(state, actor)
    raise TypeError("action_type must be a HumanActionType")


def remember_resolved_bout(
    previous_state: GameState,
    updated_state: GameState,
    current_last_bout: BoutState | None,
) -> BoutState | None:
    """Retain the latest public bout after GameState applies its terminal movement."""
    previous_bout = previous_state.active_bout
    if previous_bout is not None and updated_state.active_bout is None:
        if previous_bout.phase is BoutPhase.WAITING_FOR_DEFENDER_RESPONSE and len(
            updated_state.discard_pile
        ) > len(previous_state.discard_pile):
            discarded_table = updated_state.discard_pile[len(previous_state.discard_pile) :]
            defense_cards = discarded_table[len(previous_bout.table_cards) :]
            if defense_cards:
                return _finish_reconstructed_bout(
                    play_defense(previous_bout, previous_bout.defender, defense_cards)
                )
        if len(updated_state.discard_pile) > len(previous_state.discard_pile):
            return _finish_reconstructed_bout(finish_bout(previous_bout, previous_bout.attacker))
        return take(previous_bout, previous_bout.defender)
    return current_last_bout


def _finish_reconstructed_bout(bout: BoutState) -> BoutState:
    """Mirror automatic unplayable-attacker passes in the retained public bout."""
    while bout.phase is not BoutPhase.COMPLETE:
        bout = finish_bout(bout, bout.attacker)
    return bout
