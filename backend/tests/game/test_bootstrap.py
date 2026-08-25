import random

import pytest

from kiba_api.game import (
    Card,
    GamePhase,
    GameState,
    Rank,
    Seat,
    Suit,
    TrumpState,
    create_36_card_deck,
    create_new_game,
    get_effective_value,
    is_trump,
    start_game_bout,
)
from kiba_api.game.game import _determine_initial_attacker


class FailOnChoiceRandom(random.Random):
    def choice(self, sequence: tuple[Seat, Seat]) -> Seat:
        raise AssertionError(f"unexpected random attacker choice from {sequence}")


def card(rank: Rank, suit: Suit = Suit.CLUBS) -> Card:
    return Card(rank=rank, suit=suit)


def exposed_hearts(rank: Rank) -> TrumpState:
    return TrumpState.from_source_card(card(rank, Suit.HEARTS))


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


def test_unique_lowest_effective_trump_attacks_first() -> None:
    attacker = _determine_initial_attacker(
        (card(Rank.SEVEN, Suit.SPADES), card(Rank.EIGHT, Suit.HEARTS)),
        (card(Rank.SIX, Suit.HEARTS),),
        exposed_hearts(Rank.SEVEN),
        FailOnChoiceRandom(),
    )

    assert attacker is Seat.TWO


def test_lower_rank_trump_beats_higher_suit_trump_by_effective_value() -> None:
    trump_state = exposed_hearts(Rank.SEVEN)
    rank_trump = card(Rank.SEVEN, Suit.SPADES)
    suit_trump = card(Rank.EIGHT, Suit.HEARTS)

    attacker = _determine_initial_attacker(
        (rank_trump,),
        (suit_trump,),
        trump_state,
        FailOnChoiceRandom(),
    )

    assert get_effective_value(rank_trump, trump_state) == 14
    assert get_effective_value(suit_trump, trump_state) == 16
    assert attacker is Seat.ONE


def test_exposed_rank_six_trump_beats_higher_suit_trump() -> None:
    attacker = _determine_initial_attacker(
        (card(Rank.SEVEN, Suit.HEARTS),),
        (card(Rank.SIX, Suit.SPADES),),
        exposed_hearts(Rank.SIX),
        FailOnChoiceRandom(),
    )

    assert attacker is Seat.TWO


def test_only_seat_with_a_trump_starts_without_random_choice() -> None:
    attacker = _determine_initial_attacker(
        (card(Rank.ACE, Suit.CLUBS),),
        (card(Rank.NINE, Suit.HEARTS),),
        exposed_hearts(Rank.SEVEN),
        FailOnChoiceRandom(),
    )

    assert attacker is Seat.TWO


@pytest.mark.parametrize(("seed", "expected"), [(1, Seat.ONE), (0, Seat.TWO)])
def test_equal_lowest_trump_uses_deterministic_random_tie_break(
    seed: int,
    expected: Seat,
) -> None:
    attacker = _determine_initial_attacker(
        (card(Rank.SEVEN, Suit.SPADES),),
        (card(Rank.SEVEN, Suit.DIAMONDS),),
        exposed_hearts(Rank.SEVEN),
        random.Random(seed),
    )

    assert attacker is expected


@pytest.mark.parametrize(("seed", "expected"), [(1, Seat.ONE), (0, Seat.TWO)])
def test_no_trumps_uses_deterministic_random_fallback(seed: int, expected: Seat) -> None:
    attacker = _determine_initial_attacker(
        (card(Rank.ACE, Suit.CLUBS),),
        (card(Rank.KING, Suit.DIAMONDS),),
        exposed_hearts(Rank.SEVEN),
        random.Random(seed),
    )

    assert attacker is expected


def test_bootstrap_preserves_deal_and_exposed_top_conventions() -> None:
    seed = 314159
    expected_rng = random.Random(seed)
    shuffled_deck = list(create_36_card_deck())
    expected_rng.shuffle(shuffled_deck)
    expected_deal = GameState.deal(shuffled_deck, initial_attacker=Seat.ONE)
    trump_state = TrumpState.from_source_card(shuffled_deck[14])

    def lowest_trump(hand: tuple[Card, ...]) -> int | None:
        return min(
            (
                get_effective_value(value, trump_state)
                for value in hand
                if is_trump(value, trump_state)
            ),
            default=None,
        )

    lowest_one = lowest_trump(expected_deal.seat_one_hand)
    lowest_two = lowest_trump(expected_deal.seat_two_hand)
    assert lowest_one is not None
    assert lowest_two is not None
    assert lowest_one != lowest_two
    expected_attacker = Seat.ONE if lowest_one < lowest_two else Seat.TWO

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
