from collections.abc import Callable
from dataclasses import FrozenInstanceError

import pytest

from kiba_api.game import (
    BoutActionError,
    BoutErrorCode,
    BoutPhase,
    BoutState,
    Card,
    GameActionError,
    GameErrorCode,
    GameOutcome,
    GamePhase,
    GameResult,
    GameState,
    Rank,
    Seat,
    Suit,
    TrumpState,
    create_36_card_deck,
    finish_game_bout,
    play_game_defense,
    play_game_initial_attack,
    play_game_throw_in,
    play_game_transfer,
    start_game_bout,
    take_game_bout,
)


def card(rank: Rank, suit: Suit = Suit.CLUBS) -> Card:
    return Card(rank=rank, suit=suit)


def ready_game(
    seat_one_hand: tuple[Card, ...],
    seat_two_hand: tuple[Card, ...],
    *,
    draw_pile: tuple[Card, ...] = (),
    discard_pile: tuple[Card, ...] = (),
    attacker: Seat = Seat.ONE,
) -> GameState:
    return GameState(
        seat_one_hand=seat_one_hand,
        seat_two_hand=seat_two_hand,
        draw_pile=draw_pile,
        discard_pile=discard_pile,
        current_attacker=attacker,
    )


def assert_game_error(
    code: GameErrorCode,
    action: Callable[..., object],
    *args: object,
    **kwargs: object,
) -> None:
    with pytest.raises(GameActionError) as caught:
        action(*args, **kwargs)
    assert caught.value.code is code


def test_standard_deck_has_every_normal_card_once_in_canonical_order() -> None:
    deck = create_36_card_deck()
    expected = tuple(
        card(rank, suit)
        for suit in Suit
        for rank in (
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
    )

    assert len(deck) == 36
    assert len(set(deck)) == 36
    assert deck == expected
    assert all(value.rank is not Rank.JOKER for value in deck)
    assert create_36_card_deck() == deck


def test_initial_deal_is_round_robin_and_leaves_exposed_top_in_draw_pile() -> None:
    deck = create_36_card_deck()

    state = GameState.deal(deck, initial_attacker=Seat.TWO)

    assert state.seat_one_hand == deck[:14:2]
    assert state.seat_two_hand == deck[1:14:2]
    assert state.draw_pile == deck[14:]
    assert len(state.draw_pile) == 22
    assert state.draw_pile[0] == deck[14]
    assert state.current_attacker is Seat.TWO
    assert state.discard_pile == ()
    assert state.phase is GamePhase.READY_FOR_BOUT


def test_initial_deal_rejects_a_nonstandard_or_duplicate_deck() -> None:
    deck = create_36_card_deck()

    assert_game_error(
        GameErrorCode.INVALID_DECK, GameState.deal, deck[:-1], initial_attacker=Seat.ONE
    )
    duplicate = (*deck[:-1], deck[0])
    assert_game_error(
        GameErrorCode.INVALID_DECK, GameState.deal, duplicate, initial_attacker=Seat.ONE
    )


def test_start_bout_uses_real_counts_top_card_and_original_attacker() -> None:
    top = card(Rank.KING, Suit.SPADES)
    state = ready_game(
        (card(Rank.SIX), card(Rank.SEVEN)),
        (card(Rank.EIGHT), card(Rank.NINE), card(Rank.TEN)),
        draw_pile=(top, card(Rank.NINE, Suit.HEARTS)),
        attacker=Seat.TWO,
    )

    started = start_game_bout(state)

    assert started.phase is GamePhase.BOUT_ACTIVE
    assert started.bout_starting_attacker is Seat.TWO
    assert started.active_bout is not None
    assert started.active_bout.attacker is Seat.TWO
    assert started.active_bout.defender is Seat.ONE
    assert started.active_bout.hand_count(Seat.ONE) == 2
    assert started.active_bout.hand_count(Seat.TWO) == 3
    assert started.active_bout.trump_state == TrumpState.from_source_card(top)
    assert started.current_trump_state == TrumpState.from_source_card(top)
    assert started.draw_pile == state.draw_pile


def test_start_bout_uses_no_trump_when_draw_pile_is_empty() -> None:
    state = ready_game((card(Rank.SIX),), (card(Rank.SEVEN),))

    started = start_game_bout(state)

    assert started.active_bout is not None
    assert started.active_bout.trump_state == TrumpState.no_trump()


def test_start_bout_rejects_an_active_game() -> None:
    ready = ready_game((card(Rank.SIX),), (card(Rank.SEVEN),))
    assert_game_error(GameErrorCode.BOUT_ALREADY_ACTIVE, start_game_bout, start_game_bout(ready))


@pytest.mark.parametrize(
    ("seat_one_hand", "seat_two_hand"),
    [((), (card(Rank.SEVEN),)), ((card(Rank.SIX),), ()), ((), ())],
)
def test_ready_state_rejects_empty_hands_that_require_a_terminal_result(
    seat_one_hand: tuple[Card, ...],
    seat_two_hand: tuple[Card, ...],
) -> None:
    with pytest.raises(ValueError, match="ready game cannot have an empty hand"):
        ready_game(seat_one_hand, seat_two_hand)


def test_owned_initial_attack_removes_exact_card_and_preserves_hand_order() -> None:
    six = card(Rank.SIX)
    king = card(Rank.KING)
    seven = card(Rank.SEVEN)
    state = start_game_bout(ready_game((six, king, seven), (card(Rank.ACE),)))

    updated = play_game_initial_attack(state, Seat.ONE, [king])

    assert updated.seat_one_hand == (six, seven)
    assert updated.active_bout is not None
    assert updated.active_bout.hand_count(Seat.ONE) == len(updated.seat_one_hand)
    assert state.seat_one_hand == (six, king, seven)


def test_ownership_rejects_unowned_and_excess_equivalent_cards_without_mutation() -> None:
    king = card(Rank.KING)
    state = start_game_bout(ready_game((king, card(Rank.SIX)), (card(Rank.ACE),)))

    assert_game_error(
        GameErrorCode.CARD_NOT_OWNED,
        play_game_initial_attack,
        state,
        Seat.ONE,
        [card(Rank.QUEEN)],
    )
    assert_game_error(
        GameErrorCode.TOO_MANY_EQUIVALENT_CARDS,
        play_game_initial_attack,
        state,
        Seat.ONE,
        [king, king],
    )
    assert state.seat_one_hand == (king, card(Rank.SIX))
    assert state.active_bout is not None
    assert state.active_bout.phase is BoutPhase.WAITING_FOR_INITIAL_ATTACK


def test_rejected_bout_action_leaves_game_snapshot_unchanged() -> None:
    nine = card(Rank.NINE)
    seven = card(Rank.SEVEN)
    state = start_game_bout(ready_game((nine, seven), (card(Rank.ACE), card(Rank.KING))))

    with pytest.raises(BoutActionError) as caught:
        play_game_initial_attack(state, Seat.ONE, [nine, seven])

    assert caught.value.code is BoutErrorCode.ILLEGAL_INITIAL_ATTACK
    assert state.seat_one_hand == (nine, seven)
    assert state.active_bout is not None
    assert state.active_bout.packets == ()


def test_transfer_removes_cards_from_current_defender_and_honors_role_swap() -> None:
    king = card(Rank.KING)
    nines = (card(Rank.NINE), card(Rank.NINE, Suit.DIAMONDS))
    state = start_game_bout(
        ready_game(
            (king, card(Rank.SIX), card(Rank.SEVEN), card(Rank.EIGHT)),
            (*nines, card(Rank.EIGHT), card(Rank.TEN)),
        )
    )
    state = play_game_initial_attack(state, Seat.ONE, [king])

    transferred = play_game_transfer(state, Seat.TWO, nines)

    assert transferred.seat_two_hand == (card(Rank.EIGHT), card(Rank.TEN))
    assert transferred.active_bout is not None
    assert transferred.active_bout.attacker is Seat.TWO
    assert transferred.active_bout.defender is Seat.ONE
    assert transferred.active_bout.hand_count(Seat.TWO) == len(transferred.seat_two_hand)
    assert transferred.active_bout.transfer_target == 36


def test_defense_routes_ownership_and_failed_defense_does_not_spend_cards() -> None:
    jack = card(Rank.JACK)
    king = card(Rank.KING)
    ten = card(Rank.TEN)
    state = start_game_bout(ready_game((jack, card(Rank.SIX)), (ten, king, card(Rank.ACE))))
    state = play_game_initial_attack(state, Seat.ONE, [jack])

    with pytest.raises(BoutActionError) as caught:
        play_game_defense(state, Seat.TWO, [ten])
    assert caught.value.code is BoutErrorCode.ILLEGAL_DEFENSE
    assert state.seat_two_hand == (ten, king, card(Rank.ACE))

    defended = play_game_defense(state, Seat.TWO, [king])
    assert defended.seat_two_hand == (ten, card(Rank.ACE))
    assert defended.active_bout is not None
    assert defended.active_bout.hand_count(Seat.TWO) == len(defended.seat_two_hand)


def test_throw_in_routes_current_attacker_and_removes_only_accepted_cards() -> None:
    jack = card(Rank.JACK)
    king = card(Rank.KING)
    ten = card(Rank.TEN)
    eight = card(Rank.EIGHT)
    state = start_game_bout(
        ready_game(
            (jack, ten, eight, card(Rank.SIX)),
            (king, card(Rank.ACE), card(Rank.SEVEN), card(Rank.NINE)),
        )
    )
    state = play_game_initial_attack(state, Seat.ONE, [jack])
    state = play_game_defense(state, Seat.TWO, [king])

    thrown = play_game_throw_in(state, Seat.ONE, [ten, eight])

    assert thrown.seat_one_hand == (card(Rank.SIX),)
    assert thrown.active_bout is not None
    assert thrown.active_bout.active_packet is not None
    assert thrown.active_bout.active_packet.attack_cards == (ten, eight)
    assert thrown.active_bout.hand_count(Seat.ONE) == len(thrown.seat_one_hand)


def test_game_card_actions_require_an_active_bout() -> None:
    state = ready_game((card(Rank.KING),), (card(Rank.ACE),))

    assert_game_error(
        GameErrorCode.NO_ACTIVE_BOUT,
        play_game_initial_attack,
        state,
        Seat.ONE,
        [card(Rank.KING)],
    )
    assert_game_error(GameErrorCode.NO_ACTIVE_BOUT, finish_game_bout, state, Seat.ONE)
    assert_game_error(GameErrorCode.NO_ACTIVE_BOUT, take_game_bout, state, Seat.TWO)


def test_bito_discards_table_refills_in_starting_order_and_routes_next_attacker() -> None:
    jack = card(Rank.JACK)
    king = card(Rank.KING)
    old_discard = (card(Rank.SIX, Suit.SPADES),)
    draw = (
        card(Rank.ACE, Suit.SPADES),
        card(Rank.SIX, Suit.HEARTS),
        card(Rank.SEVEN, Suit.HEARTS),
        card(Rank.EIGHT, Suit.HEARTS),
        card(Rank.NINE, Suit.HEARTS),
        card(Rank.TEN, Suit.HEARTS),
        card(Rank.JACK, Suit.HEARTS),
        card(Rank.QUEEN, Suit.HEARTS),
    )
    state = ready_game(
        (jack, card(Rank.SIX), card(Rank.SEVEN), card(Rank.EIGHT)),
        (king, card(Rank.NINE), card(Rank.TEN), card(Rank.QUEEN), card(Rank.ACE)),
        draw_pile=draw,
        discard_pile=old_discard,
    )
    state = start_game_bout(state)
    state = play_game_initial_attack(state, Seat.ONE, [jack])
    state = play_game_defense(state, Seat.TWO, [king])

    resolved = finish_game_bout(state, Seat.ONE)

    assert resolved.discard_pile == (*old_discard, jack, king)
    assert resolved.seat_one_hand[-4:] == draw[:4]
    assert resolved.seat_two_hand[-3:] == draw[4:7]
    assert resolved.draw_pile == draw[7:]
    assert resolved.current_attacker is Seat.TWO
    assert resolved.phase is GamePhase.READY_FOR_BOUT
    assert resolved.active_bout is None
    assert resolved.bout_starting_attacker is None


def test_take_returns_complete_transferred_table_before_refill() -> None:
    king = card(Rank.KING)
    nines = (card(Rank.NINE), card(Rank.NINE, Suit.DIAMONDS))
    draw = (
        card(Rank.ACE, Suit.SPADES),
        card(Rank.SIX, Suit.HEARTS),
        card(Rank.SEVEN, Suit.HEARTS),
    )
    one_hand = (
        king,
        card(Rank.SIX),
        card(Rank.SEVEN),
        card(Rank.EIGHT),
        card(Rank.TEN),
        card(Rank.JACK),
        card(Rank.QUEEN),
    )
    two_hand = (*nines, card(Rank.SIX, Suit.DIAMONDS), card(Rank.SEVEN, Suit.DIAMONDS))
    state = start_game_bout(ready_game(one_hand, two_hand, draw_pile=draw))
    state = play_game_initial_attack(state, Seat.ONE, [king])
    state = play_game_transfer(state, Seat.TWO, nines)

    resolved = take_game_bout(state, Seat.ONE)

    assert resolved.seat_one_hand == (*one_hand[1:], king, *nines)
    assert len(resolved.seat_one_hand) == 9
    assert resolved.seat_two_hand == (*two_hand[2:], *draw)
    assert resolved.draw_pile == ()
    assert resolved.discard_pile == ()
    assert resolved.current_attacker is Seat.TWO
    assert resolved.phase is GamePhase.READY_FOR_BOUT


def test_insufficient_refill_pile_is_consumed_by_original_attacker_first() -> None:
    jack = card(Rank.JACK)
    king = card(Rank.KING)
    draw = (
        card(Rank.ACE, Suit.SPADES),
        card(Rank.SIX, Suit.HEARTS),
        card(Rank.SEVEN, Suit.HEARTS),
        card(Rank.EIGHT, Suit.HEARTS),
        card(Rank.NINE, Suit.HEARTS),
    )
    state = start_game_bout(
        ready_game(
            (jack, card(Rank.SIX), card(Rank.SEVEN), card(Rank.EIGHT)),
            (king, card(Rank.NINE), card(Rank.TEN), card(Rank.QUEEN), card(Rank.ACE)),
            draw_pile=draw,
        )
    )
    state = play_game_initial_attack(state, Seat.ONE, [jack])
    state = play_game_defense(state, Seat.TWO, [king])

    resolved = finish_game_bout(state, Seat.ONE)

    assert resolved.seat_one_hand[-4:] == draw[:4]
    assert len(resolved.seat_one_hand) == 7
    assert resolved.seat_two_hand[-1:] == draw[4:]
    assert len(resolved.seat_two_hand) == 5
    assert resolved.draw_pile == ()


def test_exposed_top_is_drawn_and_new_top_defines_next_bout_trump() -> None:
    jack = card(Rank.JACK)
    queen = card(Rank.QUEEN)
    old_top = card(Rank.KING, Suit.SPADES)
    new_top = card(Rank.NINE, Suit.HEARTS)
    one_hand = (
        jack,
        card(Rank.SIX),
        card(Rank.SEVEN),
        card(Rank.EIGHT),
        card(Rank.TEN),
        card(Rank.QUEEN, Suit.DIAMONDS),
        card(Rank.ACE),
    )
    two_hand = (
        queen,
        card(Rank.SIX, Suit.DIAMONDS),
        card(Rank.SEVEN, Suit.DIAMONDS),
        card(Rank.EIGHT, Suit.DIAMONDS),
        card(Rank.TEN, Suit.DIAMONDS),
        card(Rank.JACK, Suit.DIAMONDS),
        card(Rank.KING, Suit.DIAMONDS),
        card(Rank.ACE, Suit.DIAMONDS),
    )
    state = start_game_bout(ready_game(one_hand, two_hand, draw_pile=(old_top, new_top)))
    assert state.active_bout is not None
    assert state.active_bout.trump_state == TrumpState.from_source_card(old_top)
    state = play_game_initial_attack(state, Seat.ONE, [jack])
    state = play_game_defense(state, Seat.TWO, [queen])

    resolved = finish_game_bout(state, Seat.ONE)

    assert resolved.seat_one_hand[-1] == old_top
    assert resolved.draw_pile == (new_top,)
    assert resolved.current_trump_state == TrumpState.from_source_card(new_top)
    next_bout = start_game_bout(resolved)
    assert next_bout.active_bout is not None
    assert next_bout.active_bout.trump_state == TrumpState.from_source_card(new_top)


def test_exhausted_refill_pile_makes_next_bout_no_trump() -> None:
    jack = card(Rank.JACK)
    queen = card(Rank.QUEEN)
    top = card(Rank.KING, Suit.SPADES)
    state = start_game_bout(
        ready_game(
            (
                jack,
                card(Rank.SIX),
                card(Rank.SEVEN),
                card(Rank.EIGHT),
                card(Rank.TEN),
                card(Rank.QUEEN, Suit.DIAMONDS),
                card(Rank.ACE),
            ),
            (
                queen,
                card(Rank.SIX, Suit.DIAMONDS),
                card(Rank.SEVEN, Suit.DIAMONDS),
                card(Rank.EIGHT, Suit.DIAMONDS),
                card(Rank.TEN, Suit.DIAMONDS),
                card(Rank.JACK, Suit.DIAMONDS),
                card(Rank.KING, Suit.DIAMONDS),
                card(Rank.ACE, Suit.DIAMONDS),
            ),
            draw_pile=(top,),
        )
    )
    state = play_game_initial_attack(state, Seat.ONE, [jack])
    state = play_game_defense(state, Seat.TWO, [queen])

    resolved = finish_game_bout(state, Seat.ONE)

    assert resolved.draw_pile == ()
    assert resolved.current_trump_state == TrumpState.no_trump()


def test_transfers_do_not_change_original_attacker_refill_priority() -> None:
    king = card(Rank.KING)
    nines = (card(Rank.NINE), card(Rank.NINE, Suit.DIAMONDS))
    defense = (card(Rank.QUEEN), card(Rank.QUEEN, Suit.DIAMONDS), card(Rank.TEN))
    one_hand = (king, *defense, card(Rank.SIX), card(Rank.SEVEN), card(Rank.EIGHT))
    two_hand = (
        *nines,
        card(Rank.SIX, Suit.DIAMONDS),
        card(Rank.SEVEN, Suit.DIAMONDS),
        card(Rank.EIGHT, Suit.DIAMONDS),
        card(Rank.TEN, Suit.DIAMONDS),
        card(Rank.JACK, Suit.DIAMONDS),
    )
    draw = (
        card(Rank.ACE, Suit.SPADES),
        card(Rank.SIX, Suit.HEARTS),
        card(Rank.SEVEN, Suit.HEARTS),
        card(Rank.EIGHT, Suit.HEARTS),
        card(Rank.NINE, Suit.HEARTS),
        card(Rank.TEN, Suit.HEARTS),
        card(Rank.JACK, Suit.HEARTS),
    )
    state = start_game_bout(ready_game(one_hand, two_hand, draw_pile=draw))
    state = play_game_initial_attack(state, Seat.ONE, [king])
    state = play_game_transfer(state, Seat.TWO, nines)
    state = play_game_defense(state, Seat.ONE, defense)
    assert state.active_bout is not None
    assert state.active_bout.attacker is Seat.TWO

    resolved = finish_game_bout(state, Seat.TWO)

    assert resolved.seat_one_hand[-4:] == draw[:4]
    assert resolved.seat_two_hand[-2:] == draw[4:6]
    assert resolved.draw_pile == draw[6:]
    assert resolved.current_attacker is Seat.ONE


def test_game_state_and_prior_snapshots_are_immutable() -> None:
    state = ready_game((card(Rank.KING), card(Rank.SIX)), (card(Rank.ACE),))
    started = start_game_bout(state)
    selected = [card(Rank.KING)]
    updated = play_game_initial_attack(started, Seat.ONE, selected)

    with pytest.raises(FrozenInstanceError):
        state.current_attacker = Seat.TWO  # type: ignore[misc]
    assert state.phase is GamePhase.READY_FOR_BOUT
    assert started.seat_one_hand == (card(Rank.KING), card(Rank.SIX))
    assert updated.seat_one_hand == (card(Rank.SIX),)
    assert selected == [card(Rank.KING)]


def test_active_game_rejects_bout_hand_count_mismatch() -> None:
    bout = BoutState.start(
        attacker=Seat.ONE,
        seat_one_hand_count=2,
        seat_two_hand_count=1,
        trump_state=TrumpState.no_trump(),
    )

    with pytest.raises(GameActionError) as caught:
        GameState(
            seat_one_hand=(card(Rank.KING),),
            seat_two_hand=(card(Rank.ACE),),
            draw_pile=(),
            discard_pile=(),
            current_attacker=Seat.ONE,
            phase=GamePhase.BOUT_ACTIVE,
            active_bout=bout,
            bout_starting_attacker=Seat.ONE,
        )

    assert caught.value.code is GameErrorCode.HAND_COUNT_MISMATCH


@pytest.mark.parametrize(
    ("seat_one_hand", "seat_two_hand", "expected_winner"),
    [
        ((card(Rank.JACK),), (card(Rank.KING), card(Rank.SIX)), Seat.ONE),
        ((card(Rank.JACK), card(Rank.SIX)), (card(Rank.KING),), Seat.TWO),
    ],
)
def test_bito_resolves_the_only_empty_hand_as_winner(
    seat_one_hand: tuple[Card, ...],
    seat_two_hand: tuple[Card, ...],
    expected_winner: Seat,
) -> None:
    state = start_game_bout(ready_game(seat_one_hand, seat_two_hand))
    state = play_game_initial_attack(state, Seat.ONE, [card(Rank.JACK)])
    state = play_game_defense(state, Seat.TWO, [card(Rank.KING)])

    resolved = finish_game_bout(state, Seat.ONE)

    assert resolved.phase is GamePhase.COMPLETE
    assert resolved.result == GameResult(GameOutcome.WIN, expected_winner)
    assert resolved.current_attacker is None
    assert resolved.draw_pile == ()


@pytest.mark.parametrize("initial_attacker", [Seat.ONE, Seat.TWO])
def test_bito_with_both_hands_empty_is_a_draw_without_attacker_tiebreak(
    initial_attacker: Seat,
) -> None:
    attacking_card = card(Rank.JACK)
    defending_card = card(Rank.KING)
    hands = {
        initial_attacker: (attacking_card,),
        initial_attacker.other: (defending_card,),
    }
    state = start_game_bout(
        ready_game(
            hands[Seat.ONE],
            hands[Seat.TWO],
            attacker=initial_attacker,
        )
    )
    state = play_game_initial_attack(state, initial_attacker, [attacking_card])
    state = play_game_defense(state, initial_attacker.other, [defending_card])

    resolved = finish_game_bout(state, initial_attacker)

    assert resolved.phase is GamePhase.COMPLETE
    assert resolved.result == GameResult(GameOutcome.DRAW, None)
    assert resolved.result.winner is None
    assert resolved.current_attacker is None


def test_no_result_exists_while_a_bout_is_unresolved_even_when_hands_are_empty() -> None:
    state = start_game_bout(ready_game((card(Rank.JACK),), (card(Rank.KING),)))

    attacked = play_game_initial_attack(state, Seat.ONE, [card(Rank.JACK)])
    defended = play_game_defense(attacked, Seat.TWO, [card(Rank.KING)])

    assert attacked.seat_one_hand == ()
    assert attacked.phase is GamePhase.BOUT_ACTIVE
    assert attacked.result is None
    assert defended.seat_one_hand == ()
    assert defended.seat_two_hand == ()
    assert defended.phase is GamePhase.BOUT_ACTIVE
    assert defended.result is None


def test_temporary_empty_hand_refills_before_result_and_game_continues() -> None:
    draw = tuple(
        card(rank, suit)
        for suit in (Suit.HEARTS, Suit.DIAMONDS)
        for rank in (
            Rank.SIX,
            Rank.SEVEN,
            Rank.EIGHT,
            Rank.NINE,
            Rank.TEN,
            Rank.JACK,
            Rank.QUEEN,
            Rank.KING,
        )
    )
    state = start_game_bout(
        ready_game(
            (card(Rank.JACK),),
            (card(Rank.KING),),
            draw_pile=draw,
        )
    )
    state = play_game_initial_attack(state, Seat.ONE, [card(Rank.JACK)])
    assert state.seat_one_hand == ()
    assert state.result is None
    state = play_game_defense(state, Seat.TWO, [card(Rank.KING)])

    resolved = finish_game_bout(state, Seat.ONE)

    assert len(resolved.seat_one_hand) == 7
    assert len(resolved.seat_two_hand) == 7
    assert len(resolved.draw_pile) == 2
    assert resolved.phase is GamePhase.READY_FOR_BOUT
    assert resolved.result is None


@pytest.mark.parametrize(
    ("initial_attacker", "expected_winner"),
    [(Seat.ONE, Seat.TWO), (Seat.TWO, Seat.ONE)],
)
def test_single_refill_card_goes_to_bout_starter_before_winner_evaluation(
    initial_attacker: Seat,
    expected_winner: Seat,
) -> None:
    attacking_card = card(Rank.JACK)
    defending_card = card(Rank.KING)
    hands = {
        initial_attacker: (attacking_card,),
        initial_attacker.other: (defending_card,),
    }
    state = start_game_bout(
        ready_game(
            hands[Seat.ONE],
            hands[Seat.TWO],
            draw_pile=(card(Rank.SIX, Suit.HEARTS),),
            attacker=initial_attacker,
        )
    )
    state = play_game_initial_attack(state, initial_attacker, [attacking_card])
    state = play_game_defense(state, initial_attacker.other, [defending_card])

    resolved = finish_game_bout(state, initial_attacker)

    assert resolved.hand(initial_attacker) == (card(Rank.SIX, Suit.HEARTS),)
    assert resolved.hand(initial_attacker.other) == ()
    assert resolved.result == GameResult(GameOutcome.WIN, expected_winner)


def test_empty_deck_with_neither_hand_empty_continues() -> None:
    state = start_game_bout(
        ready_game(
            (card(Rank.JACK), card(Rank.SIX)),
            (card(Rank.KING), card(Rank.SEVEN)),
        )
    )
    state = play_game_initial_attack(state, Seat.ONE, [card(Rank.JACK)])
    state = play_game_defense(state, Seat.TWO, [card(Rank.KING)])

    resolved = finish_game_bout(state, Seat.ONE)

    assert resolved.draw_pile == ()
    assert resolved.seat_one_hand == (card(Rank.SIX),)
    assert resolved.seat_two_hand == (card(Rank.SEVEN),)
    assert resolved.phase is GamePhase.READY_FOR_BOUT
    assert resolved.result is None


def test_attacker_wins_only_after_take_moves_the_table_and_refill_finishes() -> None:
    king = card(Rank.KING)
    six = card(Rank.SIX)
    state = start_game_bout(ready_game((king,), (six,)))
    state = play_game_initial_attack(state, Seat.ONE, [king])

    resolved = take_game_bout(state, Seat.TWO)

    assert resolved.seat_one_hand == ()
    assert resolved.seat_two_hand == (six, king)
    assert resolved.result == GameResult(GameOutcome.WIN, Seat.ONE)
    assert resolved.phase is GamePhase.COMPLETE


def test_take_refills_the_temporarily_empty_attacker_before_result_evaluation() -> None:
    king = card(Rank.KING)
    six = card(Rank.SIX)
    refill_card = card(Rank.SEVEN, Suit.HEARTS)
    state = start_game_bout(
        ready_game(
            (king,),
            (six,),
            draw_pile=(refill_card,),
        )
    )
    state = play_game_initial_attack(state, Seat.ONE, [king])
    assert state.seat_one_hand == ()
    assert state.result is None

    resolved = take_game_bout(state, Seat.TWO)

    assert resolved.seat_one_hand == (refill_card,)
    assert resolved.seat_two_hand == (six, king)
    assert resolved.draw_pile == ()
    assert resolved.phase is GamePhase.READY_FOR_BOUT
    assert resolved.result is None


def test_transfer_history_does_not_change_simultaneous_empty_draw() -> None:
    king = card(Rank.KING)
    nines = (card(Rank.NINE), card(Rank.NINE, Suit.DIAMONDS))
    defense = (card(Rank.QUEEN), card(Rank.QUEEN, Suit.DIAMONDS), card(Rank.TEN))
    state = start_game_bout(ready_game((king, *defense), nines))
    state = play_game_initial_attack(state, Seat.ONE, [king])
    state = play_game_transfer(state, Seat.TWO, nines)
    state = play_game_defense(state, Seat.ONE, defense)

    resolved = finish_game_bout(state, Seat.TWO)

    assert resolved.seat_one_hand == ()
    assert resolved.seat_two_hand == ()
    assert resolved.result == GameResult(GameOutcome.DRAW, None)


def completed_draw_game() -> GameState:
    state = start_game_bout(ready_game((card(Rank.JACK),), (card(Rank.KING),)))
    state = play_game_initial_attack(state, Seat.ONE, [card(Rank.JACK)])
    state = play_game_defense(state, Seat.TWO, [card(Rank.KING)])
    return finish_game_bout(state, Seat.ONE)


def completed_win_game() -> GameState:
    state = start_game_bout(ready_game((card(Rank.JACK),), (card(Rank.KING), card(Rank.SIX))))
    state = play_game_initial_attack(state, Seat.ONE, [card(Rank.JACK)])
    state = play_game_defense(state, Seat.TWO, [card(Rank.KING)])
    return finish_game_bout(state, Seat.ONE)


@pytest.mark.parametrize("completed_state", [completed_win_game, completed_draw_game])
def test_completed_games_reject_start_and_all_gameplay_actions(
    completed_state: Callable[[], GameState],
) -> None:
    state = completed_state()
    actions: tuple[Callable[[], object], ...] = (
        lambda: start_game_bout(state),
        lambda: play_game_initial_attack(state, Seat.ONE, [card(Rank.SIX)]),
        lambda: play_game_transfer(state, Seat.ONE, [card(Rank.SIX)]),
        lambda: play_game_defense(state, Seat.ONE, [card(Rank.SIX)]),
        lambda: play_game_throw_in(state, Seat.ONE, [card(Rank.SIX)]),
        lambda: finish_game_bout(state, Seat.ONE),
        lambda: take_game_bout(state, Seat.ONE),
    )

    for action in actions:
        assert_game_error(GameErrorCode.GAME_COMPLETE, action)


def test_completed_game_and_result_are_immutable() -> None:
    state = completed_draw_game()
    assert state.result is not None

    with pytest.raises(FrozenInstanceError):
        state.phase = GamePhase.READY_FOR_BOUT  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        state.result.winner = Seat.ONE  # type: ignore[misc]


def test_game_result_requires_winner_only_for_win() -> None:
    with pytest.raises(ValueError, match="win result requires a winner"):
        GameResult(GameOutcome.WIN, None)
    with pytest.raises(ValueError, match="draw result cannot have a winner"):
        GameResult(GameOutcome.DRAW, Seat.ONE)


def test_non_complete_game_cannot_have_a_result() -> None:
    with pytest.raises(ValueError, match="non-complete game cannot have a result"):
        GameState(
            seat_one_hand=(card(Rank.SIX),),
            seat_two_hand=(card(Rank.SEVEN),),
            draw_pile=(),
            discard_pile=(),
            current_attacker=Seat.ONE,
            result=GameResult(GameOutcome.WIN, Seat.ONE),
        )


def test_complete_game_requires_result_and_empty_draw_pile() -> None:
    with pytest.raises(ValueError, match="complete game requires a result"):
        GameState(
            seat_one_hand=(),
            seat_two_hand=(card(Rank.SEVEN),),
            draw_pile=(),
            discard_pile=(),
            current_attacker=None,
            phase=GamePhase.COMPLETE,
        )
    with pytest.raises(ValueError, match="empty draw pile"):
        GameState(
            seat_one_hand=(),
            seat_two_hand=(card(Rank.SEVEN),),
            draw_pile=(card(Rank.SIX),),
            discard_pile=(),
            current_attacker=None,
            phase=GamePhase.COMPLETE,
            result=GameResult(GameOutcome.WIN, Seat.ONE),
        )


def test_complete_result_must_match_final_hands() -> None:
    with pytest.raises(ValueError, match="draw requires both hands"):
        GameState(
            seat_one_hand=(),
            seat_two_hand=(card(Rank.SEVEN),),
            draw_pile=(),
            discard_pile=(),
            current_attacker=None,
            phase=GamePhase.COMPLETE,
            result=GameResult(GameOutcome.DRAW, None),
        )
    with pytest.raises(ValueError, match="reported winner"):
        GameState(
            seat_one_hand=(),
            seat_two_hand=(card(Rank.SEVEN),),
            draw_pile=(),
            discard_pile=(),
            current_attacker=None,
            phase=GamePhase.COMPLETE,
            result=GameResult(GameOutcome.WIN, Seat.TWO),
        )
