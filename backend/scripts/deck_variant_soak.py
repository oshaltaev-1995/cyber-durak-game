"""Deterministic full-bot deck-variant soak used by the D3 acceptance gate."""

from __future__ import annotations

import argparse
import json
import random
from dataclasses import dataclass
from time import perf_counter

from kiba_api.game import (
    BotAction,
    BotActionType,
    DeckConfig,
    DeckProfile,
    GamePhase,
    JokerColor,
    Rank,
    choose_bot_action,
    create_new_game,
    finish_game_bout,
    is_trump,
    play_game_defense,
    play_game_initial_attack,
    play_game_throw_in,
    play_game_transfer,
    start_game_bout,
    take_game_bout,
)
from kiba_api.sessions import acting_seat


@dataclass(slots=True)
class Coverage:
    red_joker_in_hand: bool = False
    black_joker_in_hand: bool = False
    joker_on_table: bool = False
    joker_exposed_as_trump: bool = False
    same_color_joker_trump: bool = False
    largest_selected_card_count: int = 0

    def observe(self, state, action: BotAction | None = None) -> None:
        hand_jokers = {
            card.joker_color for hand in state.hands for card in hand if card.rank is Rank.JOKER
        }
        self.red_joker_in_hand |= JokerColor.RED in hand_jokers
        self.black_joker_in_hand |= JokerColor.BLACK in hand_jokers
        if state.active_bout is not None:
            self.joker_on_table |= any(
                card.rank is Rank.JOKER for card in state.active_bout.table_cards
            )
        source = state.draw_pile[0] if state.draw_pile else None
        if source is not None and source.rank is Rank.JOKER:
            self.joker_exposed_as_trump = True
        if source is not None and source.rank is not Rank.JOKER:
            self.same_color_joker_trump |= any(
                card.rank is Rank.JOKER and is_trump(card, state.current_trump_state)
                for card in state.all_cards
            )
        if action is not None:
            self.largest_selected_card_count = max(
                self.largest_selected_card_count,
                len(action.cards),
            )


def _apply(state, actor, action: BotAction):
    if action.action_type is BotActionType.INITIAL_ATTACK:
        return play_game_initial_attack(state, actor, action.cards)
    if action.action_type is BotActionType.DEFEND:
        return play_game_defense(state, actor, action.cards)
    if action.action_type is BotActionType.TRANSFER:
        return play_game_transfer(state, actor, action.cards)
    if action.action_type is BotActionType.THROW_IN:
        return play_game_throw_in(state, actor, action.cards)
    if action.action_type is BotActionType.TAKE:
        return take_game_bout(state, actor)
    if action.action_type is BotActionType.BITO:
        return finish_game_bout(state, actor)
    raise AssertionError(f"unexpected active-bout action: {action.action_type}")


def _assert_conservation(state, config: DeckConfig) -> None:
    cards = state.all_cards
    assert len(cards) == config.card_count
    assert len({card.physical_id for card in cards}) == config.card_count


def run_soak(games_per_cell: int, transition_limit: int) -> dict[str, object]:
    started = perf_counter()
    coverage = Coverage()
    matrix: dict[str, int] = {}
    transitions = 0
    max_match_seconds = 0.0

    for profile in DeckProfile:
        for deck_count in (1, 2):
            config = DeckConfig(profile, deck_count)
            for player_count in (2, 3, 4):
                cell = f"{profile.value}x{deck_count}/{player_count}p"
                matrix[cell] = 0
                for seed in range(games_per_cell):
                    match_started = perf_counter()
                    state = create_new_game(
                        random.Random(seed),
                        player_count=player_count,
                        deck_config=config,
                    )
                    _assert_conservation(state, config)
                    coverage.observe(state)
                    match_transitions = 0
                    while state.phase is not GamePhase.COMPLETE:
                        if match_transitions >= transition_limit:
                            raise AssertionError(f"transition limit reached: {cell} seed={seed}")
                        if state.phase is GamePhase.READY_FOR_BOUT:
                            state = start_game_bout(state)
                        else:
                            actor = acting_seat(state)
                            assert actor is not None
                            action = choose_bot_action(state, actor)
                            coverage.observe(state, action)
                            state = _apply(state, actor, action)
                        _assert_conservation(state, config)
                        coverage.observe(state)
                        match_transitions += 1
                    assert state.finish_groups
                    assert set(seat for group in state.finish_groups for seat in group) == set(
                        state.seat_order
                    )
                    matrix[cell] += 1
                    transitions += match_transitions
                    max_match_seconds = max(max_match_seconds, perf_counter() - match_started)

    required_joker_coverage = (
        coverage.red_joker_in_hand,
        coverage.black_joker_in_hand,
        coverage.joker_on_table,
        coverage.joker_exposed_as_trump,
        coverage.same_color_joker_trump,
    )
    if not all(required_joker_coverage):
        raise AssertionError(f"incomplete Joker coverage: {coverage}")
    return {
        "games_per_cell": games_per_cell,
        "total_games": sum(matrix.values()),
        "total_transitions": transitions,
        "matrix": matrix,
        "coverage": {
            "red_joker_in_hand": coverage.red_joker_in_hand,
            "black_joker_in_hand": coverage.black_joker_in_hand,
            "joker_on_table": coverage.joker_on_table,
            "joker_exposed_as_trump": coverage.joker_exposed_as_trump,
            "same_color_joker_trump": coverage.same_color_joker_trump,
        },
        "largest_selected_card_count": coverage.largest_selected_card_count,
        "max_match_seconds": round(max_match_seconds, 6),
        "elapsed_seconds": round(perf_counter() - started, 6),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--games-per-cell", type=int, default=50)
    parser.add_argument("--transition-limit", type=int, default=5_000)
    args = parser.parse_args()
    if args.games_per_cell <= 0 or args.transition_limit <= 0:
        parser.error("soak bounds must be positive")
    result = run_soak(args.games_per_cell, args.transition_limit)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
