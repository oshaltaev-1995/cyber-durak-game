import random

import pytest

from kiba_api.game import (
    GamePhase,
    Seat,
    create_36_card_deck,
    create_new_game,
    start_game_bout,
)


def test_new_game_is_ready_with_canonical_card_locations() -> None:
    state = create_new_game(random.Random(20260825))

    assert state.phase is GamePhase.READY_FOR_BOUT
    assert len(state.seat_one_hand) == 7
    assert len(state.seat_two_hand) == 7
    assert len(state.draw_pile) == 22
    assert state.discard_pile == ()
    assert state.active_bout is None
    assert state.bout_starting_attacker is None
    assert state.result is None


def test_new_game_conserves_every_standard_card_exactly_once() -> None:
    state = create_new_game(random.Random(20260825))
    all_cards = (*state.seat_one_hand, *state.seat_two_hand, *state.draw_pile)

    assert len(all_cards) == 36
    assert len(set(all_cards)) == 36
    assert set(all_cards) == set(create_36_card_deck())


def test_seeded_new_game_is_fully_reproducible() -> None:
    first = create_new_game(random.Random(314159))
    second = create_new_game(random.Random(314159))

    assert first == second
    assert first.seat_one_hand == second.seat_one_hand
    assert first.seat_two_hand == second.seat_two_hand
    assert first.draw_pile == second.draw_pile
    assert first.current_attacker is second.current_attacker


def test_known_different_seeds_produce_different_bootstrap_states() -> None:
    first = create_new_game(random.Random(1))
    second = create_new_game(random.Random(2))

    assert first != second
    assert (
        first.seat_one_hand,
        first.seat_two_hand,
        first.draw_pile,
        first.current_attacker,
    ) != (
        second.seat_one_hand,
        second.seat_two_hand,
        second.draw_pile,
        second.current_attacker,
    )


@pytest.mark.parametrize(
    ("seed", "expected_attacker"),
    [(1, Seat.ONE), (0, Seat.TWO)],
)
def test_known_seeds_can_select_either_initial_attacker(
    seed: int,
    expected_attacker: Seat,
) -> None:
    state = create_new_game(random.Random(seed))

    assert state.current_attacker is expected_attacker


def test_bootstrap_preserves_deal_and_exposed_top_conventions() -> None:
    seed = 314159
    expected_rng = random.Random(seed)
    shuffled_deck = list(create_36_card_deck())
    expected_rng.shuffle(shuffled_deck)
    expected_attacker = expected_rng.choice((Seat.ONE, Seat.TWO))

    state = create_new_game(random.Random(seed))

    assert state.seat_one_hand == tuple(shuffled_deck[:14:2])
    assert state.seat_two_hand == tuple(shuffled_deck[1:14:2])
    assert state.draw_pile == tuple(shuffled_deck[14:])
    assert state.draw_pile[0] == shuffled_deck[14]
    assert state.current_attacker is expected_attacker


def test_bootstrapped_game_starts_first_bout_with_selected_attacker() -> None:
    ready = create_new_game(random.Random(314159))

    started = start_game_bout(ready)

    assert ready.phase is GamePhase.READY_FOR_BOUT
    assert ready.active_bout is None
    assert started.phase is GamePhase.BOUT_ACTIVE
    assert started.active_bout is not None
    assert started.active_bout.attacker is ready.current_attacker
    assert started.active_bout.trump_state == ready.current_trump_state
