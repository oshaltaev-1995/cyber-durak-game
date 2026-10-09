from collections import Counter
from dataclasses import FrozenInstanceError, replace

import pytest

from kiba_api.game import (
    AttackPacket,
    BoutActionError,
    BoutErrorCode,
    BoutOutcome,
    BoutPhase,
    BoutState,
    Card,
    GameActionError,
    GameErrorCode,
    GamePhase,
    GameState,
    Rank,
    Seat,
    Suit,
    TrumpState,
    allocate_balanced_refill_quotas,
    create_36_card_deck,
    finish_bout,
    finish_game_bout,
    next_active_clockwise,
    play_defense,
    play_game_defense,
    play_game_initial_attack,
    play_game_throw_in,
    play_game_transfer,
    play_initial_attack,
    play_throw_in,
    play_transfer,
    refill_hands,
    seats_for_player_count,
    start_game_bout,
    take,
    take_game_bout,
)
from kiba_api.game.game import _determine_initial_attacker

NO_TRUMP = TrumpState.no_trump()
SEATS_3 = seats_for_player_count(3)
SEATS_4 = seats_for_player_count(4)


def card(rank: Rank, suit: Suit = Suit.CLUBS) -> Card:
    return Card(rank=rank, suit=suit)


class ChooseSeat:
    def __init__(self, seat: Seat) -> None:
        self.seat = seat

    def choice(self, seats: tuple[Seat, ...]) -> Seat:
        assert self.seat in seats
        return self.seat


def game(
    hands: tuple[tuple[Card, ...], ...],
    attacker: Seat,
    *,
    draw_pile: tuple[Card, ...] = (),
    finished_seats: tuple[Seat, ...] = (),
    finish_groups: tuple[tuple[Seat, ...], ...] = (),
) -> GameState:
    return GameState(
        seat_order=seats_for_player_count(len(hands)),
        hands=hands,
        draw_pile=draw_pile,
        discard_pile=(),
        current_attacker=attacker,
        finished_seats=finished_seats,
        finish_groups=finish_groups,
    )


M1_SCENARIO_TRACEABILITY = {
    **{f"S{number:02d}": "test_s01_s04_starting_order" for number in range(1, 5)},
    **{f"S{number:02d}": "test_s05_s07_initial_window" for number in range(5, 8)},
    **{f"S{number:02d}": "test_s08_s13_noncycling_atomic_phases" for number in (8, 9, 11, 12, 13)},
    "S10": "test_s10_no_legal_move_advances_automatically",
    **{f"S{number:02d}": "test_s14_s17_shared_dynamic_cap" for number in range(14, 17)},
    "S17": "test_s17_exhausted_cap_closes_later_phases_automatically",
    "S18": "test_s18_one_transfer",
    "S19": "test_s19_three_defender_chain",
    "S20": "test_s20_wrapped_four_player_transfer",
    "S21": "test_s21_transfer_rejects_new_defender_overflow",
    "S22": "test_s22_attacker_order_after_transfer",
    **{f"S{number:02d}": "test_s23_s26_take_and_bito" for number in range(23, 27)},
    **{f"S{number:02d}": "test_s27_s31_shared_table_arithmetic" for number in range(27, 32)},
    **{f"S{number:02d}": "test_s32_s37_balanced_refill" for number in range(32, 38)},
    **{
        f"S{number:02d}": "test_s38_s47_finish_groups_and_reduction"
        for number in (*range(38, 44), *range(45, 48))
    },
    "S44": "test_s44_empty_mid_bout_refills_without_finishing",
    "S48": "test_s48_two_player_transfer_keeps_refill_snapshot",
}


def test_m1_scenario_traceability_is_complete() -> None:
    expected = {f"S{number:02d}" for number in range(1, 49)}

    assert set(M1_SCENARIO_TRACEABILITY) == expected
    assert all(name in globals() for name in M1_SCENARIO_TRACEABILITY.values())


def test_stable_clockwise_ring_wraps_and_skips_finished_seats() -> None:
    assert next_active_clockwise(SEATS_4, SEATS_4, Seat.FOUR) is Seat.ONE
    assert next_active_clockwise(SEATS_4, (Seat.ONE, Seat.TWO, Seat.FOUR), Seat.TWO) is Seat.FOUR
    assert next_active_clockwise(SEATS_4, (Seat.ONE, Seat.FOUR), Seat.FOUR) is Seat.ONE
    assert next_active_clockwise(SEATS_4, (Seat.TWO, Seat.FOUR), Seat.TWO) is Seat.FOUR


def test_domain_supports_only_two_to_four_players() -> None:
    deck = create_36_card_deck()
    for count in (2, 3, 4):
        state = GameState.deal(deck, initial_attacker=Seat.ONE, player_count=count)
        assert state.seat_order == seats_for_player_count(count)
        assert all(len(hand) == 7 for hand in state.hands)
        assert state.draw_pile == deck[7 * count :]
        for index, hand in enumerate(state.hands):
            assert hand == deck[index : 7 * count : count]

    for count in (1, 5):
        with pytest.raises(GameActionError) as caught:
            GameState.deal(deck, initial_attacker=Seat.ONE, player_count=count)
        assert caught.value.code is GameErrorCode.INVALID_PLAYER_COUNT


def test_s01_s04_starting_order() -> None:
    ten_spades = TrumpState.from_source_card(card(Rank.TEN, Suit.SPADES))
    three_hands = (
        (card(Rank.EIGHT, Suit.SPADES),),
        (card(Rank.SIX, Suit.SPADES),),
        (card(Rank.TEN, Suit.HEARTS),),
    )
    assert (
        _determine_initial_attacker(three_hands, SEATS_3, ten_spades, ChooseSeat(Seat.ONE))
        is Seat.TWO
    )

    queen_diamonds = TrumpState.from_source_card(card(Rank.QUEEN, Suit.DIAMONDS))
    four_hands = (
        (card(Rank.EIGHT, Suit.DIAMONDS),),
        (card(Rank.QUEEN, Suit.CLUBS),),
        (card(Rank.SIX, Suit.DIAMONDS),),
        (card(Rank.NINE, Suit.CLUBS),),
    )
    assert (
        _determine_initial_attacker(four_hands, SEATS_4, queen_diamonds, ChooseSeat(Seat.ONE))
        is Seat.THREE
    )

    seven_hearts = TrumpState.from_source_card(card(Rank.SEVEN, Suit.HEARTS))
    tied_hands = (
        (card(Rank.SEVEN, Suit.CLUBS),),
        (card(Rank.EIGHT, Suit.HEARTS),),
        (card(Rank.SEVEN, Suit.DIAMONDS),),
        (card(Rank.NINE, Suit.CLUBS),),
    )
    assert (
        _determine_initial_attacker(tied_hands, SEATS_4, seven_hearts, ChooseSeat(Seat.THREE))
        is Seat.THREE
    )

    no_trumps = (
        (card(Rank.SIX, Suit.CLUBS),),
        (card(Rank.SEVEN, Suit.DIAMONDS),),
        (card(Rank.EIGHT, Suit.HEARTS),),
        (card(Rank.NINE, Suit.CLUBS),),
    )
    king_spades = TrumpState.from_source_card(card(Rank.KING, Suit.SPADES))
    assert (
        _determine_initial_attacker(no_trumps, SEATS_4, king_spades, ChooseSeat(Seat.FOUR))
        is Seat.FOUR
    )


def test_s05_s07_initial_window() -> None:
    state = BoutState.start(
        attacker=Seat.ONE,
        seat_order=SEATS_4,
        active_seats=SEATS_4,
        hand_counts=(7, 7, 7, 7),
        trump_state=NO_TRUMP,
    )
    assert state.bout_starter is Seat.ONE
    assert state.initial_defender is Seat.TWO
    assert state.refill_order == (Seat.ONE, Seat.THREE, Seat.FOUR, Seat.TWO)
    with pytest.raises(BoutActionError) as caught:
        play_initial_attack(state, Seat.THREE, (card(Rank.SIX),))
    assert caught.value.code is BoutErrorCode.WRONG_ACTOR

    initial = (card(Rank.NINE), card(Rank.NINE, Suit.DIAMONDS), card(Rank.KING))
    state = play_initial_attack(state, Seat.ONE, initial)
    state = play_defense(state, Seat.TWO, (card(Rank.ACE), card(Rank.ACE, Suit.DIAMONDS)))
    with pytest.raises(BoutActionError) as caught:
        play_throw_in(state, Seat.ONE, (card(Rank.KING, Suit.DIAMONDS),))
    assert caught.value.code is BoutErrorCode.ILLEGAL_THROW_IN

    reopened = BoutState.start(
        attacker=Seat.ONE,
        seat_order=SEATS_3,
        active_seats=SEATS_3,
        hand_counts=(7, 7, 7),
        trump_state=NO_TRUMP,
    )
    reopened = play_initial_attack(reopened, Seat.ONE, initial)
    reopened = play_defense(reopened, Seat.TWO, (card(Rank.ACE), card(Rank.KING)))
    reopened = play_throw_in(reopened, Seat.ONE, (card(Rank.KING, Suit.DIAMONDS),))
    assert reopened.active_packet is not None
    assert reopened.active_packet.attack_cards == (card(Rank.KING, Suit.DIAMONDS),)


def test_s08_s13_noncycling_atomic_phases() -> None:
    state = BoutState.start(
        attacker=Seat.ONE,
        seat_order=SEATS_4,
        active_seats=SEATS_4,
        hand_counts=(7, 7, 7, 7),
        trump_state=NO_TRUMP,
    )
    state = play_initial_attack(state, Seat.ONE, (card(Rank.SIX),))
    state = play_defense(state, Seat.TWO, (card(Rank.SEVEN),))
    state = play_throw_in(state, Seat.ONE, (card(Rank.SEVEN, Suit.DIAMONDS),))
    state = play_defense(state, Seat.TWO, (card(Rank.EIGHT),))
    state = play_throw_in(state, Seat.ONE, (card(Rank.EIGHT, Suit.DIAMONDS),))
    state = play_defense(state, Seat.TWO, (card(Rank.NINE),))
    state = finish_bout(state, Seat.ONE)
    assert state.phase is BoutPhase.WAITING_FOR_ATTACKER_DECISION
    assert state.attacker is Seat.THREE
    assert state.closed_attackers == (Seat.ONE,)

    with pytest.raises(BoutActionError) as caught:
        play_throw_in(state, Seat.ONE, (card(Rank.NINE, Suit.DIAMONDS),))
    assert caught.value.code is BoutErrorCode.WRONG_ACTOR

    state = play_throw_in(state, Seat.THREE, (card(Rank.NINE, Suit.DIAMONDS),))
    state = play_defense(state, Seat.TWO, (card(Rank.TEN),))
    state = finish_bout(state, Seat.THREE)
    assert state.attacker is Seat.FOUR
    state = finish_bout(state, Seat.FOUR)
    assert state.phase is BoutPhase.COMPLETE
    assert state.outcome is BoutOutcome.BITO


def test_s10_no_legal_move_advances_automatically() -> None:
    six = card(Rank.SIX)
    seven = card(Rank.SEVEN)
    state = game(
        (
            (six, card(Rank.KING)),
            (seven, card(Rank.ACE)),
            (card(Rank.SEVEN, Suit.DIAMONDS), card(Rank.SIX, Suit.SPADES)),
        ),
        Seat.ONE,
    )
    state = start_game_bout(state)
    state = play_game_initial_attack(state, Seat.ONE, (six,))
    state = play_game_defense(state, Seat.TWO, (seven,))

    assert state.active_bout is not None
    assert state.active_bout.attacker is Seat.THREE
    assert state.active_bout.closed_attackers == (Seat.ONE,)


def test_invalid_multiplayer_actors_are_rejected_atomically() -> None:
    state = BoutState.start(
        attacker=Seat.ONE,
        seat_order=SEATS_4,
        active_seats=SEATS_4,
        hand_counts=(7, 7, 7, 7),
        trump_state=NO_TRUMP,
    )
    state = play_initial_attack(state, Seat.ONE, (card(Rank.SIX),))
    transfer_snapshot = state
    with pytest.raises(BoutActionError) as caught:
        play_transfer(state, Seat.THREE, (card(Rank.SIX, Suit.DIAMONDS),))
    assert caught.value.code is BoutErrorCode.WRONG_ACTOR
    assert state == transfer_snapshot

    with pytest.raises(BoutActionError) as caught:
        play_throw_in(state, Seat.ONE, (card(Rank.SIX, Suit.DIAMONDS),))
    assert caught.value.code is BoutErrorCode.WRONG_PHASE

    state = play_defense(state, Seat.TWO, (card(Rank.SEVEN),))
    decision_snapshot = state
    with pytest.raises(BoutActionError) as caught:
        play_throw_in(state, Seat.THREE, (card(Rank.SEVEN, Suit.DIAMONDS),))
    assert caught.value.code is BoutErrorCode.WRONG_ACTOR
    assert state == decision_snapshot

    three_player = BoutState.start(
        attacker=Seat.ONE,
        seat_order=SEATS_3,
        active_seats=SEATS_3,
        hand_counts=(7, 7, 7),
        trump_state=NO_TRUMP,
    )
    with pytest.raises(BoutActionError) as caught:
        play_initial_attack(three_player, Seat.FOUR, (card(Rank.SIX),))
    assert caught.value.code is BoutErrorCode.WRONG_ACTOR

    reduced = BoutState.start(
        attacker=Seat.TWO,
        seat_order=SEATS_4,
        active_seats=(Seat.TWO, Seat.FOUR),
        hand_counts=(0, 7, 0, 7),
        trump_state=NO_TRUMP,
    )
    with pytest.raises(BoutActionError) as caught:
        play_initial_attack(reduced, Seat.ONE, (card(Rank.SIX),))
    assert caught.value.code is BoutErrorCode.WRONG_ACTOR


def test_s14_s17_shared_dynamic_cap() -> None:
    state = BoutState.start(
        attacker=Seat.ONE,
        seat_order=SEATS_4,
        active_seats=SEATS_4,
        hand_counts=(7, 7, 7, 7),
        trump_state=NO_TRUMP,
    )
    state = play_initial_attack(
        state,
        Seat.ONE,
        (card(Rank.JACK), card(Rank.SIX), card(Rank.KING)),
    )
    state = play_defense(state, Seat.TWO, (card(Rank.ACE), card(Rank.ACE, Suit.DIAMONDS)))
    state = finish_bout(state, Seat.ONE)
    state = play_throw_in(
        state,
        Seat.THREE,
        (card(Rank.ACE, Suit.HEARTS), card(Rank.ACE, Suit.SPADES)),
    )
    state = play_defense(
        state,
        Seat.TWO,
        (card(Rank.QUEEN), card(Rank.QUEEN, Suit.DIAMONDS), card(Rank.QUEEN, Suit.HEARTS)),
    )
    state = finish_bout(state, Seat.THREE)
    assert state.attacker is Seat.FOUR
    assert state.total_attack_card_count == 5
    assert state.remaining_bout_capacity == 2
    assert state.max_attack_card_addition == 2

    limited_by_hand = BoutState(
        seat_order=SEATS_3,
        active_seats=SEATS_3,
        hand_counts=(3, 1, 7),
        bout_starter=Seat.ONE,
        initial_defender=Seat.TWO,
        refill_order=(Seat.ONE, Seat.THREE, Seat.TWO),
        lead_attacker=Seat.ONE,
        attacker=Seat.THREE,
        defender=Seat.TWO,
        attacker_order=(Seat.ONE, Seat.THREE),
        closed_attackers=(Seat.ONE,),
        trump_state=NO_TRUMP,
        phase=BoutPhase.WAITING_FOR_ATTACKER_DECISION,
        packets=(
            AttackPacket(
                (card(Rank.ACE),) * 4,
                80,
                (
                    card(Rank.QUEEN),
                    card(Rank.QUEEN, Suit.DIAMONDS),
                    card(Rank.QUEEN, Suit.HEARTS),
                    card(Rank.QUEEN, Suit.SPADES),
                    card(Rank.JACK),
                    card(Rank.JACK, Suit.DIAMONDS),
                ),
                84,
            ),
        ),
        transfer_open=False,
        attack_card_limit=7,
        total_attack_card_count=4,
    )
    assert limited_by_hand.max_attack_card_addition == 1
    with pytest.raises(BoutActionError) as caught:
        play_throw_in(
            limited_by_hand,
            Seat.THREE,
            (card(Rank.QUEEN), card(Rank.JACK)),
        )
    assert caught.value.code is BoutErrorCode.ATTACK_CARD_LIMIT_EXCEEDED

    exhausted = replace(
        limited_by_hand,
        hand_counts=(2, 2, 7),
        packets=(
            AttackPacket(
                (card(Rank.SIX),) * 5,
                30,
                (card(Rank.ACE), card(Rank.JACK)),
                32,
            ),
        ),
        attack_card_limit=5,
        total_attack_card_count=5,
    )
    assert exhausted.max_attack_card_addition == 0


def test_s17_exhausted_cap_closes_later_phases_automatically() -> None:
    closed_packet = AttackPacket(
        (card(Rank.SIX),) * 5,
        30,
        (card(Rank.ACE), card(Rank.ACE, Suit.DIAMONDS)),
        40,
    )
    bout = BoutState(
        seat_order=SEATS_4,
        active_seats=SEATS_4,
        hand_counts=(2, 2, 2, 2),
        bout_starter=Seat.ONE,
        initial_defender=Seat.TWO,
        refill_order=(Seat.ONE, Seat.THREE, Seat.FOUR, Seat.TWO),
        lead_attacker=Seat.ONE,
        attacker=Seat.ONE,
        defender=Seat.TWO,
        attacker_order=(Seat.ONE, Seat.THREE, Seat.FOUR),
        trump_state=NO_TRUMP,
        phase=BoutPhase.WAITING_FOR_ATTACKER_DECISION,
        packets=(closed_packet,),
        transfer_open=False,
        attack_card_limit=5,
        total_attack_card_count=5,
    )
    hands = tuple((card(Rank.KING, suit), card(Rank.QUEEN, suit)) for suit in Suit)
    state = GameState(
        seat_order=SEATS_4,
        hands=hands,
        current_attacker=Seat.ONE,
        phase=GamePhase.BOUT_ACTIVE,
        active_bout=bout,
        bout_starting_attacker=Seat.ONE,
    )

    state = finish_game_bout(state, Seat.ONE)

    assert state.phase is GamePhase.READY_FOR_BOUT
    assert state.current_attacker is Seat.TWO
    assert state.active_bout is None


def test_s18_one_transfer() -> None:
    state = BoutState.start(
        attacker=Seat.ONE,
        seat_order=SEATS_3,
        active_seats=SEATS_3,
        hand_counts=(7, 7, 5),
        trump_state=NO_TRUMP,
    )
    state = play_initial_attack(state, Seat.ONE, (card(Rank.KING),))
    state = play_transfer(
        state,
        Seat.TWO,
        (card(Rank.NINE), card(Rank.NINE, Suit.DIAMONDS)),
    )
    state = play_defense(state, Seat.THREE, (card(Rank.ACE), card(Rank.ACE, Suit.DIAMONDS)))
    assert state.defender is Seat.THREE
    assert state.lead_attacker is Seat.ONE
    assert state.attacker_order == (Seat.ONE, Seat.TWO)
    assert state.refill_order == (Seat.ONE, Seat.THREE, Seat.TWO)


def test_s19_three_defender_chain() -> None:
    state = BoutState.start(
        attacker=Seat.ONE,
        seat_order=SEATS_4,
        active_seats=SEATS_4,
        hand_counts=(7, 7, 7, 7),
        trump_state=NO_TRUMP,
    )
    state = play_initial_attack(state, Seat.ONE, (card(Rank.SIX),))
    state = play_transfer(state, Seat.TWO, (card(Rank.SIX, Suit.DIAMONDS),))
    state = play_transfer(
        state,
        Seat.THREE,
        (card(Rank.SIX, Suit.HEARTS), card(Rank.SIX, Suit.SPADES)),
    )
    state = play_defense(state, Seat.FOUR, (card(Rank.QUEEN), card(Rank.TEN)))
    assert state.defender is Seat.FOUR
    assert state.lead_attacker is Seat.ONE
    assert state.attacker_order == (Seat.ONE, Seat.TWO, Seat.THREE)
    assert state.refill_order == (Seat.ONE, Seat.THREE, Seat.FOUR, Seat.TWO)


def test_s20_wrapped_four_player_transfer() -> None:
    state = BoutState.start(
        attacker=Seat.ONE,
        seat_order=SEATS_4,
        active_seats=SEATS_4,
        hand_counts=(13, 7, 7, 7),
        trump_state=NO_TRUMP,
    )
    state = play_initial_attack(state, Seat.ONE, (card(Rank.KING),))
    state = play_transfer(
        state,
        Seat.TWO,
        (card(Rank.NINE), card(Rank.NINE, Suit.DIAMONDS)),
    )
    state = play_transfer(
        state,
        Seat.THREE,
        (
            card(Rank.JACK),
            card(Rank.JACK, Suit.DIAMONDS),
            card(Rank.SIX),
            card(Rank.SIX, Suit.DIAMONDS),
        ),
    )
    state = play_transfer(
        state,
        Seat.FOUR,
        (
            card(Rank.ACE),
            card(Rank.ACE, Suit.DIAMONDS),
            card(Rank.KING, Suit.DIAMONDS),
            card(Rank.SEVEN),
            card(Rank.SEVEN, Suit.DIAMONDS),
        ),
    )
    assert state.defender is Seat.ONE
    assert state.lead_attacker is Seat.FOUR
    assert state.bout_starter is Seat.ONE
    assert state.initial_defender is Seat.TWO
    assert state.refill_order == (Seat.ONE, Seat.THREE, Seat.FOUR, Seat.TWO)
    assert state.attack_card_limit == 12
    assert state.total_attack_card_count == 12

    state = play_defense(
        state,
        Seat.ONE,
        (
            card(Rank.QUEEN),
            card(Rank.QUEEN, Suit.DIAMONDS),
            card(Rank.QUEEN, Suit.HEARTS),
            card(Rank.QUEEN, Suit.SPADES),
            card(Rank.KING),
            card(Rank.KING, Suit.DIAMONDS),
            card(Rank.ACE),
            card(Rank.ACE, Suit.DIAMONDS),
            card(Rank.SEVEN),
            card(Rank.SEVEN, Suit.DIAMONDS),
        ),
    )
    assert state.attacker_order == (Seat.FOUR, Seat.TWO, Seat.THREE)
    assert state.attacker is Seat.FOUR


def test_s21_transfer_rejects_new_defender_overflow() -> None:
    state = BoutState.start(
        attacker=Seat.ONE,
        seat_order=SEATS_3,
        active_seats=SEATS_3,
        hand_counts=(7, 7, 2),
        trump_state=NO_TRUMP,
    )
    state = play_initial_attack(state, Seat.ONE, (card(Rank.KING),))
    with pytest.raises(BoutActionError) as caught:
        play_transfer(
            state,
            Seat.TWO,
            (card(Rank.NINE), card(Rank.NINE, Suit.DIAMONDS)),
        )
    assert caught.value.code is BoutErrorCode.ATTACK_CARD_LIMIT_EXCEEDED
    assert state.defender is Seat.TWO
    assert state.hand_count(Seat.TWO) == 7


def test_s22_attacker_order_after_transfer() -> None:
    state = BoutState.start(
        attacker=Seat.ONE,
        seat_order=SEATS_4,
        active_seats=SEATS_4,
        hand_counts=(7, 7, 7, 7),
        trump_state=NO_TRUMP,
    )
    state = play_initial_attack(state, Seat.ONE, (card(Rank.KING),))
    state = play_transfer(
        state,
        Seat.TWO,
        (card(Rank.NINE), card(Rank.NINE, Suit.DIAMONDS)),
    )
    state = play_defense(state, Seat.THREE, (card(Rank.ACE), card(Rank.ACE, Suit.DIAMONDS)))
    assert state.attacker_order == (Seat.ONE, Seat.TWO, Seat.FOUR)
    assert state.refill_order == (Seat.ONE, Seat.THREE, Seat.FOUR, Seat.TWO)


def test_s23_s26_take_and_bito() -> None:
    take_state = BoutState.start(
        attacker=Seat.ONE,
        seat_order=SEATS_4,
        active_seats=SEATS_4,
        hand_counts=(7, 7, 7, 7),
        trump_state=NO_TRUMP,
    )
    take_state = play_initial_attack(take_state, Seat.ONE, (card(Rank.SIX),))
    taken = take(take_state, Seat.TWO)
    assert taken.phase is BoutPhase.COMPLETE
    assert taken.outcome is BoutOutcome.TAKE
    assert taken.next_attacker is Seat.THREE

    bito = BoutState.start(
        attacker=Seat.ONE,
        seat_order=SEATS_4,
        active_seats=SEATS_4,
        hand_counts=(7, 7, 7, 7),
        trump_state=NO_TRUMP,
    )
    bito = play_initial_attack(bito, Seat.ONE, (card(Rank.SIX),))
    bito = play_defense(bito, Seat.TWO, (card(Rank.SEVEN),))
    bito = finish_bout(bito, Seat.ONE)
    bito = finish_bout(bito, Seat.THREE)
    bito = finish_bout(bito, Seat.FOUR)
    assert bito.outcome is BoutOutcome.BITO
    assert bito.next_attacker is Seat.TWO

    final_card = BoutState.start(
        attacker=Seat.ONE,
        seat_order=SEATS_4,
        active_seats=SEATS_4,
        hand_counts=(7, 1, 7, 7),
        trump_state=NO_TRUMP,
    )
    final_card = play_initial_attack(final_card, Seat.ONE, (card(Rank.JACK),))
    final_card = play_defense(final_card, Seat.TWO, (card(Rank.KING),))
    assert final_card.phase is BoutPhase.COMPLETE
    assert final_card.outcome is BoutOutcome.BITO


def test_s27_s31_shared_table_arithmetic() -> None:
    latest_rank = BoutState.start(
        attacker=Seat.ONE,
        seat_order=SEATS_3,
        active_seats=SEATS_3,
        hand_counts=(7, 7, 7),
        trump_state=NO_TRUMP,
    )
    latest_rank = play_initial_attack(latest_rank, Seat.ONE, (card(Rank.SIX),))
    latest_rank = play_defense(latest_rank, Seat.TWO, (card(Rank.SEVEN),))
    latest_rank = finish_bout(latest_rank, Seat.ONE)
    latest_rank = play_throw_in(latest_rank, Seat.THREE, (card(Rank.SEVEN, Suit.DIAMONDS),))
    assert latest_rank.active_packet is not None

    defense_total = BoutState.start(
        attacker=Seat.ONE,
        seat_order=SEATS_3,
        active_seats=SEATS_3,
        hand_counts=(7, 7, 7),
        trump_state=NO_TRUMP,
    )
    defense_total = play_initial_attack(defense_total, Seat.ONE, (card(Rank.KING),))
    defense_total = play_defense(
        defense_total,
        Seat.TWO,
        (card(Rank.JACK), card(Rank.EIGHT)),
    )
    defense_total = finish_bout(defense_total, Seat.ONE)
    defense_total = play_throw_in(defense_total, Seat.THREE, (card(Rank.ACE),))
    assert defense_total.active_packet is not None

    table_math = BoutState.start(
        attacker=Seat.ONE,
        seat_order=SEATS_3,
        active_seats=SEATS_3,
        hand_counts=(7, 7, 7),
        trump_state=NO_TRUMP,
    )
    table_math = play_initial_attack(table_math, Seat.ONE, (card(Rank.JACK),))
    table_math = play_defense(table_math, Seat.TWO, (card(Rank.KING),))
    table_math = finish_bout(table_math, Seat.ONE)
    assert (
        play_throw_in(
            table_math,
            Seat.THREE,
            (card(Rank.QUEEN), card(Rank.QUEEN, Suit.DIAMONDS)),
        ).active_packet
        is not None
    )
    assert play_throw_in(table_math, Seat.THREE, (card(Rank.QUEEN),)).active_packet is not None

    rank_run = BoutState(
        seat_order=SEATS_3,
        active_seats=SEATS_3,
        hand_counts=(4, 4, 7),
        bout_starter=Seat.ONE,
        initial_defender=Seat.TWO,
        refill_order=(Seat.ONE, Seat.THREE, Seat.TWO),
        lead_attacker=Seat.ONE,
        attacker=Seat.THREE,
        defender=Seat.TWO,
        attacker_order=(Seat.ONE, Seat.THREE),
        closed_attackers=(Seat.ONE,),
        trump_state=NO_TRUMP,
        phase=BoutPhase.WAITING_FOR_ATTACKER_DECISION,
        packets=(
            AttackPacket((card(Rank.TEN),), 10, (card(Rank.JACK),), 12),
            AttackPacket((card(Rank.JACK, Suit.DIAMONDS),), 12, (card(Rank.KING),), 18),
            AttackPacket((card(Rank.KING, Suit.DIAMONDS),), 18, (card(Rank.ACE),), 20),
        ),
        transfer_open=False,
        attack_card_limit=7,
        total_attack_card_count=3,
    )
    rank_run = play_throw_in(rank_run, Seat.THREE, (card(Rank.QUEEN),))
    assert rank_run.active_packet is not None


def test_s32_s37_balanced_refill() -> None:
    refill_order = (Seat.ONE, Seat.THREE, Seat.TWO)
    source = tuple(card(rank, Suit.HEARTS) for rank in Rank if rank is not Rank.JOKER)
    hands = (
        (card(Rank.SIX),) * 4,
        (card(Rank.SEVEN),) * 3,
        (card(Rank.EIGHT),) * 6,
    )
    refilled, remaining = refill_hands(hands, source, SEATS_3, refill_order)
    assert tuple(map(len, refilled)) == (7, 7, 7)
    assert refilled[0][-3:] == source[:3]
    assert refilled[2][-1:] == source[3:4]
    assert refilled[1][-4:] == source[4:8]
    assert remaining == source[8:]

    quotas = allocate_balanced_refill_quotas(
        {Seat.ONE: 3, Seat.THREE: 4, Seat.TWO: 5},
        4,
        refill_order,
    )
    assert quotas == {Seat.ONE: 3, Seat.THREE: 1, Seat.TWO: 0}

    four_order = (Seat.THREE, Seat.ONE, Seat.TWO, Seat.FOUR)
    four_quotas = allocate_balanced_refill_quotas(
        {Seat.THREE: 2, Seat.ONE: 3, Seat.TWO: 5, Seat.FOUR: 6},
        8,
        four_order,
    )
    assert four_quotas == {Seat.THREE: 4, Seat.ONE: 3, Seat.TWO: 1, Seat.FOUR: 0}

    examples = (
        ({Seat.ONE: 3, Seat.TWO: 5}, 4, {Seat.ONE: 3, Seat.TWO: 1}),
        ({Seat.ONE: 4, Seat.TWO: 5}, 4, {Seat.ONE: 3, Seat.TWO: 1}),
        ({Seat.ONE: 6, Seat.TWO: 3}, 3, {Seat.ONE: 0, Seat.TWO: 3}),
    )
    for counts, available, expected in examples:
        assert (
            allocate_balanced_refill_quotas(
                counts,
                available,
                (Seat.ONE, Seat.TWO),
            )
            == expected
        )


def test_s38_s47_finish_groups_and_reduction() -> None:
    state = game(
        (
            (card(Rank.JACK),),
            (
                card(Rank.KING),
                card(Rank.JACK, Suit.DIAMONDS),
                card(Rank.KING, Suit.HEARTS),
                card(Rank.SIX, Suit.DIAMONDS),
            ),
            (card(Rank.ACE, Suit.DIAMONDS),),
            (card(Rank.JACK, Suit.SPADES),),
        ),
        Seat.ONE,
    )
    state = start_game_bout(state)
    state = play_game_initial_attack(state, Seat.ONE, (card(Rank.JACK),))
    state = play_game_defense(state, Seat.TWO, (card(Rank.KING),))
    assert state.finish_groups == ((Seat.ONE,),)
    assert state.finished_seats == (Seat.ONE,)
    assert state.active_seats == (Seat.TWO, Seat.THREE, Seat.FOUR)
    assert state.current_attacker is Seat.TWO

    state = start_game_bout(state)
    state = play_game_initial_attack(state, Seat.TWO, (card(Rank.JACK, Suit.DIAMONDS),))
    state = play_game_defense(state, Seat.THREE, (card(Rank.ACE, Suit.DIAMONDS),))
    assert state.finish_groups == ((Seat.ONE,), (Seat.THREE,))
    assert state.active_seats == (Seat.TWO, Seat.FOUR)
    assert state.current_attacker is Seat.FOUR

    state = start_game_bout(state)
    assert state.active_bout is not None
    assert state.active_bout.defender is Seat.TWO
    state = play_game_initial_attack(state, Seat.FOUR, (card(Rank.JACK, Suit.SPADES),))
    state = play_game_defense(state, Seat.TWO, (card(Rank.KING, Suit.HEARTS),))
    state = finish_game_bout(state, Seat.FOUR)
    assert state.phase is GamePhase.COMPLETE
    assert state.finish_groups == (
        (Seat.ONE,),
        (Seat.THREE,),
        (Seat.FOUR,),
        (Seat.TWO,),
    )
    assert state.hand(Seat.TWO) == (card(Rank.SIX, Suit.DIAMONDS),)
    assert state.result is None

    early_tie = game(
        (
            (card(Rank.JACK),),
            (card(Rank.KING),),
            (card(Rank.SIX, Suit.HEARTS),),
            (card(Rank.SEVEN, Suit.HEARTS),),
        ),
        Seat.ONE,
    )
    early_tie = start_game_bout(early_tie)
    early_tie = play_game_initial_attack(early_tie, Seat.ONE, (card(Rank.JACK),))
    early_tie = play_game_defense(early_tie, Seat.TWO, (card(Rank.KING),))
    assert early_tie.finish_groups == ((Seat.ONE, Seat.TWO),)
    assert early_tie.active_seats == (Seat.THREE, Seat.FOUR)

    final_tie = game(
        (
            (),
            (),
            (card(Rank.JACK),),
            (card(Rank.KING),),
        ),
        Seat.THREE,
        finished_seats=(Seat.ONE, Seat.TWO),
        finish_groups=((Seat.ONE,), (Seat.TWO,)),
    )
    final_tie = start_game_bout(final_tie)
    final_tie = play_game_initial_attack(final_tie, Seat.THREE, (card(Rank.JACK),))
    final_tie = play_game_defense(final_tie, Seat.FOUR, (card(Rank.KING),))
    assert final_tie.phase is GamePhase.COMPLETE
    assert final_tie.finish_groups == ((Seat.ONE,), (Seat.TWO,), (Seat.THREE, Seat.FOUR))

    all_remaining = game(
        (
            (),
            (card(Rank.SIX),),
            (card(Rank.SEVEN), card(Rank.EIGHT)),
            (card(Rank.SEVEN, Suit.DIAMONDS),),
        ),
        Seat.TWO,
        finished_seats=(Seat.ONE,),
        finish_groups=((Seat.ONE,),),
    )
    all_remaining = start_game_bout(all_remaining)
    all_remaining = play_game_initial_attack(all_remaining, Seat.TWO, (card(Rank.SIX),))
    all_remaining = play_game_defense(all_remaining, Seat.THREE, (card(Rank.SEVEN),))
    all_remaining = play_game_throw_in(
        all_remaining,
        Seat.FOUR,
        (card(Rank.SEVEN, Suit.DIAMONDS),),
    )
    all_remaining = play_game_defense(all_remaining, Seat.THREE, (card(Rank.EIGHT),))
    assert all_remaining.phase is GamePhase.COMPLETE
    assert all_remaining.finish_groups == ((Seat.ONE,), (Seat.TWO, Seat.THREE, Seat.FOUR))


def test_s44_empty_mid_bout_refills_without_finishing() -> None:
    six = card(Rank.SIX)
    seven = card(Rank.SEVEN)
    refill = tuple(create_36_card_deck()[:20])
    state = game(
        (
            (six,),
            (seven, card(Rank.ACE)),
            (card(Rank.KING),),
        ),
        Seat.ONE,
        draw_pile=refill,
    )
    state = start_game_bout(state)
    state = play_game_initial_attack(state, Seat.ONE, (six,))
    assert state.hand(Seat.ONE) == ()
    assert state.finished_seats == ()

    state = play_game_defense(state, Seat.TWO, (seven,))

    assert state.phase is GamePhase.READY_FOR_BOUT
    assert len(state.hand(Seat.ONE)) == 7
    assert Seat.ONE not in state.finished_seats


def test_s48_two_player_transfer_keeps_refill_snapshot() -> None:
    king = card(Rank.KING)
    nines = (card(Rank.NINE), card(Rank.NINE, Suit.DIAMONDS))
    aces = (card(Rank.ACE), card(Rank.ACE, Suit.DIAMONDS))
    draw = (
        *(card(rank, Suit.HEARTS) for rank in _normal_ranks()),
        card(Rank.EIGHT, Suit.DIAMONDS),
        card(Rank.TEN, Suit.DIAMONDS),
    )
    state = game(
        ((king, *aces, card(Rank.SIX)), (*nines, card(Rank.SIX, Suit.DIAMONDS), card(Rank.SEVEN))),
        Seat.ONE,
        draw_pile=draw,
    )
    state = start_game_bout(state)
    assert state.active_bout is not None
    assert state.active_bout.refill_order == (Seat.ONE, Seat.TWO)
    state = play_game_initial_attack(state, Seat.ONE, (king,))
    state = play_game_transfer(state, Seat.TWO, nines)
    state = play_game_defense(state, Seat.ONE, aces)
    assert state.active_bout is not None
    assert state.active_bout.lead_attacker is Seat.TWO
    assert state.active_bout.defender is Seat.ONE
    assert state.active_bout.refill_order == (Seat.ONE, Seat.TWO)
    state = finish_game_bout(state, Seat.TWO)
    assert state.hand(Seat.ONE)[-6:] == draw[:6]
    assert state.hand(Seat.TWO)[-5:] == draw[6:11]


def test_card_conservation_and_snapshot_immutability() -> None:
    deck = create_36_card_deck()
    state = GameState.deal(deck, initial_attacker=Seat.ONE, player_count=4)
    started = start_game_bout(state)
    first_card = started.hand(Seat.ONE)[0]
    attacked = play_game_initial_attack(started, Seat.ONE, (first_card,))

    assert Counter(state.all_cards) == Counter(deck)
    assert Counter(started.all_cards) == Counter(deck)
    assert Counter(attacked.all_cards) == Counter(deck)
    with pytest.raises(FrozenInstanceError):
        attacked.current_attacker = Seat.TWO  # type: ignore[misc]

    taken = take_game_bout(attacked, Seat.TWO)
    assert Counter(taken.all_cards) == Counter(deck)


def _normal_ranks() -> tuple[Rank, ...]:
    return tuple(rank for rank in Rank if rank is not Rank.JOKER)
