import random
from collections.abc import Callable
from dataclasses import FrozenInstanceError

import pytest

from kiba_api.game import (
    BotAction,
    BotActionError,
    BotActionType,
    BotErrorCode,
    BoutPhase,
    Card,
    GameOutcome,
    GamePhase,
    GameState,
    Rank,
    Seat,
    Suit,
    choose_bot_action,
    create_new_game,
    play_bot_turn,
    play_game_defense,
    play_game_initial_attack,
    play_game_throw_in,
    start_game_bout,
)


def card(rank: Rank, suit: Suit = Suit.CLUBS) -> Card:
    return Card(rank=rank, suit=suit)


def ready_game(
    seat_one_hand: tuple[Card, ...],
    seat_two_hand: tuple[Card, ...],
    *,
    attacker: Seat = Seat.ONE,
    draw_pile: tuple[Card, ...] = (),
) -> GameState:
    return GameState(
        seat_one_hand=seat_one_hand,
        seat_two_hand=seat_two_hand,
        draw_pile=draw_pile,
        discard_pile=(),
        current_attacker=attacker,
    )


def active_game(
    seat_one_hand: tuple[Card, ...],
    seat_two_hand: tuple[Card, ...],
    *,
    attacker: Seat = Seat.ONE,
    draw_pile: tuple[Card, ...] = (),
) -> GameState:
    return start_game_bout(
        ready_game(
            seat_one_hand,
            seat_two_hand,
            attacker=attacker,
            draw_pile=draw_pile,
        )
    )


def covered_jack(attacker_cards: tuple[Card, ...]) -> GameState:
    jack = card(Rank.JACK)
    king = card(Rank.KING)
    state = active_game(
        (jack, *attacker_cards),
        (
            king,
            card(Rank.SIX, Suit.DIAMONDS),
            card(Rank.SEVEN, Suit.DIAMONDS),
            card(Rank.EIGHT, Suit.DIAMONDS),
        ),
    )
    state = play_game_initial_attack(state, Seat.ONE, (jack,))
    return play_game_defense(state, Seat.TWO, (king,))


def assert_bot_error(
    code: BotErrorCode,
    action: Callable[..., object],
    *args: object,
) -> None:
    with pytest.raises(BotActionError) as caught:
        action(*args)
    assert caught.value.code is code


def test_bot_starts_ready_bout_only_for_current_attacker() -> None:
    state = ready_game((card(Rank.SIX),), (card(Rank.SEVEN),))

    assert choose_bot_action(state, Seat.ONE) == BotAction(BotActionType.START_BOUT)
    assert_bot_error(BotErrorCode.NOT_BOT_TURN, choose_bot_action, state, Seat.TWO)


def test_initial_attack_prefers_lowest_effective_single_card() -> None:
    trump_source = card(Rank.KING, Suit.SPADES)
    six = card(Rank.SIX, Suit.DIAMONDS)
    ace = card(Rank.ACE, Suit.CLUBS)
    trump_king = card(Rank.KING, Suit.HEARTS)
    state = active_game(
        (trump_king, ace, six),
        (card(Rank.SEVEN), card(Rank.EIGHT), card(Rank.NINE)),
        draw_pile=(trump_source,),
    )

    action = choose_bot_action(state, Seat.ONE)

    assert action == BotAction(BotActionType.INITIAL_ATTACK, (six,))
    assert len(action.cards) <= state.active_bout.attack_card_limit  # type: ignore[union-attr]


def test_initial_attack_uses_canonical_card_order_for_equal_cost() -> None:
    six_of_diamonds = card(Rank.SIX, Suit.DIAMONDS)
    six_of_clubs = card(Rank.SIX, Suit.CLUBS)
    state = active_game(
        (six_of_diamonds, six_of_clubs),
        (card(Rank.ACE), card(Rank.KING)),
    )

    first = choose_bot_action(state, Seat.ONE)
    second = choose_bot_action(state, Seat.ONE)

    assert first == second == BotAction(BotActionType.INITIAL_ATTACK, (six_of_clubs,))


def test_defense_prefers_cheapest_legal_total_and_supports_multiple_cards() -> None:
    king = card(Rank.KING)
    seven = card(Rank.SEVEN)
    jack = card(Rank.JACK)
    ace = card(Rank.ACE)
    equal_king = card(Rank.KING, Suit.DIAMONDS)
    state = active_game(
        (king, card(Rank.SIX), card(Rank.EIGHT)),
        (ace, equal_king, jack, seven),
    )
    state = play_game_initial_attack(state, Seat.ONE, (king,))

    action = choose_bot_action(state, Seat.TWO)

    assert action == BotAction(BotActionType.DEFEND, (seven, jack))


def test_defense_uses_effective_values_and_avoids_costlier_trump() -> None:
    trump_source = card(Rank.KING, Suit.SPADES)
    jack = card(Rank.JACK, Suit.DIAMONDS)
    ace = card(Rank.ACE, Suit.CLUBS)
    trump_king = card(Rank.KING, Suit.HEARTS)
    state = active_game(
        (jack, card(Rank.SIX), card(Rank.SEVEN)),
        (trump_king, ace, card(Rank.EIGHT)),
        draw_pile=(trump_source,),
    )
    state = play_game_initial_attack(state, Seat.ONE, (jack,))

    action = choose_bot_action(state, Seat.TWO)

    assert action == BotAction(BotActionType.DEFEND, (ace,))


def test_equal_cost_defense_prefers_non_trump_card() -> None:
    trump_source = card(Rank.SIX, Suit.HEARTS)
    attack = card(Rank.TEN, Suit.CLUBS)
    trump_six = card(Rank.SIX, Suit.SPADES)
    non_trump_jack = card(Rank.JACK, Suit.CLUBS)
    state = active_game(
        (attack, card(Rank.SEVEN)),
        (trump_six, non_trump_jack),
        draw_pile=(trump_source,),
    )
    state = play_game_initial_attack(state, Seat.ONE, (attack,))

    action = choose_bot_action(state, Seat.TWO)

    assert action == BotAction(BotActionType.DEFEND, (non_trump_jack,))


def test_defender_takes_when_no_defense_or_transfer_exists() -> None:
    ace = card(Rank.ACE)
    state = active_game(
        (ace, card(Rank.SEVEN)),
        (card(Rank.SIX),),
    )
    state = play_game_initial_attack(state, Seat.ONE, (ace,))

    assert choose_bot_action(state, Seat.TWO) == BotAction(BotActionType.TAKE)


def test_defender_transfers_exactly_only_when_no_defense_exists() -> None:
    king = card(Rank.KING)
    nines = (card(Rank.NINE), card(Rank.NINE, Suit.DIAMONDS))
    state = active_game(
        (king, card(Rank.SIX), card(Rank.SEVEN), card(Rank.EIGHT)),
        nines,
    )
    state = play_game_initial_attack(state, Seat.ONE, (king,))

    action = choose_bot_action(state, Seat.TWO)

    assert action == BotAction(BotActionType.TRANSFER, nines)


def test_approximate_transfer_is_rejected_in_favor_of_take() -> None:
    king = card(Rank.KING)
    state = active_game(
        (king, card(Rank.SIX), card(Rank.SEVEN)),
        (card(Rank.NINE), card(Rank.EIGHT)),
    )
    state = play_game_initial_attack(state, Seat.ONE, (king,))

    assert choose_bot_action(state, Seat.TWO) == BotAction(BotActionType.TAKE)


def test_transfer_is_not_considered_after_first_successful_defense() -> None:
    queen = card(Rank.QUEEN)
    king = card(Rank.KING)
    state = active_game(
        (card(Rank.JACK), queen, card(Rank.SIX)),
        (king, card(Rank.QUEEN, Suit.DIAMONDS), card(Rank.SEVEN)),
    )
    state = play_game_initial_attack(state, Seat.ONE, (card(Rank.JACK),))
    state = play_game_defense(state, Seat.TWO, (king,))
    state = play_game_throw_in(state, Seat.ONE, (queen,))

    assert state.active_bout is not None
    assert state.active_bout.transfer_open is False
    assert choose_bot_action(state, Seat.TWO).action_type is not BotActionType.TRANSFER


@pytest.mark.parametrize(
    ("attacker_cards", "expected_cards"),
    [
        ((card(Rank.KING, Suit.DIAMONDS),), (card(Rank.KING, Suit.DIAMONDS),)),
        (
            (card(Rank.TEN), card(Rank.EIGHT)),
            (card(Rank.EIGHT), card(Rank.TEN)),
        ),
        (
            (card(Rank.ACE), card(Rank.TEN)),
            (card(Rank.TEN), card(Rank.ACE)),
        ),
        ((card(Rank.QUEEN),), (card(Rank.QUEEN),)),
    ],
)
def test_throw_in_supports_same_rank_existing_value_total_and_mean(
    attacker_cards: tuple[Card, ...],
    expected_cards: tuple[Card, ...],
) -> None:
    state = covered_jack(attacker_cards)

    action = choose_bot_action(state, Seat.ONE)

    assert action == BotAction(BotActionType.THROW_IN, expected_cards)


def test_bot_discovers_a_multi_card_rank_run_throw_in() -> None:
    attack_six = card(Rank.SIX)
    attack_nine = card(Rank.NINE, Suit.DIAMONDS)
    seven = card(Rank.SEVEN)
    eight = card(Rank.EIGHT)
    ten = card(Rank.TEN)
    state = active_game(
        (attack_six, attack_nine, seven, eight, ten),
        (
            card(Rank.NINE),
            card(Rank.JACK),
            card(Rank.QUEEN),
            card(Rank.KING),
            card(Rank.ACE),
        ),
    )
    state = play_game_initial_attack(state, Seat.ONE, (attack_six,))
    state = play_game_defense(state, Seat.TWO, (card(Rank.NINE),))
    state = play_game_throw_in(state, Seat.ONE, (attack_nine,))
    state = play_game_defense(state, Seat.TWO, (card(Rank.JACK),))

    action = choose_bot_action(state, Seat.ONE)

    assert action == BotAction(BotActionType.THROW_IN, (seven, eight, ten))


def test_throw_in_prefers_lower_effective_legal_candidate() -> None:
    queen = card(Rank.QUEEN)
    state = covered_jack((card(Rank.TEN), card(Rank.EIGHT), queen))

    action = choose_bot_action(state, Seat.ONE)

    assert action == BotAction(BotActionType.THROW_IN, (queen,))


def test_bot_finishes_bito_when_no_throw_in_exists() -> None:
    state = covered_jack((card(Rank.ACE),))

    assert choose_bot_action(state, Seat.ONE) == BotAction(BotActionType.BITO)


def test_bot_action_and_turn_are_immutable_and_one_step_only() -> None:
    ready = ready_game((card(Rank.SIX),), (card(Rank.SEVEN),))
    action = choose_bot_action(ready, Seat.ONE)

    with pytest.raises(FrozenInstanceError):
        action.action_type = BotActionType.TAKE  # type: ignore[misc]

    started = play_bot_turn(ready, Seat.ONE)

    assert ready.phase is GamePhase.READY_FOR_BOUT
    assert started.phase is GamePhase.BOUT_ACTIVE
    assert started.active_bout is not None
    assert started.active_bout.phase is BoutPhase.WAITING_FOR_INITIAL_ATTACK


def acting_seat(state: GameState) -> Seat:
    if state.phase is GamePhase.READY_FOR_BOUT:
        assert state.current_attacker is not None
        return state.current_attacker
    assert state.active_bout is not None
    if state.active_bout.phase is BoutPhase.WAITING_FOR_DEFENDER_RESPONSE:
        return state.active_bout.defender
    return state.active_bout.attacker


def assert_card_conservation(state: GameState) -> None:
    cards = [
        *state.seat_one_hand,
        *state.seat_two_hand,
        *state.draw_pile,
        *state.discard_pile,
    ]
    if state.active_bout is not None:
        cards.extend(state.active_bout.table_cards)

    assert len(cards) == 36
    assert len(set(cards)) == 36


@pytest.mark.parametrize("seed", [0, 1, 2, 42, 12345])
def test_two_baseline_bots_complete_seeded_games(seed: int) -> None:
    state = create_new_game(random.Random(seed))
    action_count = 0

    while state.phase is not GamePhase.COMPLETE and action_count < 2_000:
        assert_card_conservation(state)
        state = play_bot_turn(state, acting_seat(state))
        action_count += 1

    assert action_count < 2_000
    assert state.phase is GamePhase.COMPLETE
    assert state.result is not None
    assert state.result.outcome in {GameOutcome.WIN, GameOutcome.DRAW}
    assert_card_conservation(state)
