"""Shared application helpers for routing participant actions into GameState."""

from __future__ import annotations

from enum import StrEnum

from kiba_api.game import (
    BoutPhase,
    BoutState,
    Card,
    GamePhase,
    GameState,
    Seat,
    finish_game_bout,
    play_defense,
    play_game_defense,
    play_game_initial_attack,
    play_game_throw_in,
    play_game_transfer,
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
                return play_defense(previous_bout, previous_bout.defender, defense_cards)
        return previous_bout
    return current_last_bout
