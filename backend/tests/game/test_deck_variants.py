"""Executable traceability for canonical deck scenarios D01-D40."""

import random
from collections import Counter
from collections.abc import Callable
from fractions import Fraction

import pytest

from kiba_api.game import (
    BoutActionError,
    BoutErrorCode,
    BoutPhase,
    BoutState,
    Card,
    DeckConfig,
    DeckProfile,
    GameActionError,
    GameErrorCode,
    GameOutcome,
    GamePhase,
    GameState,
    InitialAttackReason,
    JokerColor,
    PacketTransferMode,
    Rank,
    Seat,
    Suit,
    ThrowInReason,
    TrumpState,
    analyze_defense,
    analyze_initial_attack,
    analyze_packet_transfer,
    analyze_rank_run,
    analyze_rank_run_throw_in,
    analyze_throw_in,
    analyze_transfer,
    cards_have_same_rank,
    create_deck,
    create_new_game,
    finish_game_bout,
    get_base_value,
    get_effective_value,
    is_trump,
    play_game_defense,
    play_game_initial_attack,
    play_initial_attack,
    refill_hands,
    start_game_bout,
    summarize_table_arithmetic,
    take_game_bout,
)
from kiba_api.game.game import _determine_initial_attacker

CLASSIC_1 = DeckConfig(DeckProfile.CLASSIC, 1)
EXTENDED_1 = DeckConfig(DeckProfile.EXTENDED, 1)
CLASSIC_2 = DeckConfig(DeckProfile.CLASSIC, 2)
EXTENDED_2 = DeckConfig(DeckProfile.EXTENDED, 2)
NO_TRUMP = TrumpState.no_trump()


class ChooseSeat:
    def __init__(self, seat: Seat) -> None:
        self.seat = seat

    def choice(self, population: tuple[Seat, ...]) -> Seat:
        assert self.seat in population
        return self.seat


def card(
    rank: Rank,
    suit: Suit = Suit.CLUBS,
    *,
    deck_copy: int = 1,
) -> Card:
    return Card(rank, suit, deck_copy=deck_copy)


def joker(color: JokerColor, *, deck_copy: int = 1) -> Card:
    return Card(Rank.JOKER, joker_color=color, deck_copy=deck_copy)


def selected_ranks(*ranks: Rank) -> tuple[Card, ...]:
    return tuple(card(rank, list(Suit)[index % 4]) for index, rank in enumerate(ranks))


def test_d01_single_classic_population() -> None:
    deck = create_deck(CLASSIC_1)
    assert len(deck) == len({value.physical_id for value in deck}) == 36
    assert all(value.rank is not Rank.JOKER and value.deck_copy == 1 for value in deck)


def test_d02_single_extended_population() -> None:
    deck = create_deck(EXTENDED_1)
    assert len(deck) == len({value.physical_id for value in deck}) == 54
    assert Counter(value.joker_color for value in deck if value.rank is Rank.JOKER) == {
        JokerColor.RED: 1,
        JokerColor.BLACK: 1,
    }


def test_d03_double_classic_identity_and_conservation() -> None:
    deck = create_deck(CLASSIC_2)
    identity = card(Rank.KING, Suit.HEARTS).display_identity
    kings = tuple(value for value in deck if value.display_identity == identity)
    assert len(deck) == len({value.physical_id for value in deck}) == 72
    assert len(kings) == 2 and kings[0].display_identity == kings[1].display_identity
    assert kings[0].physical_id != kings[1].physical_id


def test_d04_double_extended_joker_population() -> None:
    deck = create_deck(EXTENDED_2)
    jokers = tuple(value for value in deck if value.rank is Rank.JOKER)
    assert len(deck) == len({value.physical_id for value in deck}) == 108
    assert Counter(value.joker_color for value in jokers) == {
        JokerColor.RED: 2,
        JokerColor.BLACK: 2,
    }


def test_d05_exact_duplicates_form_same_rank_batch() -> None:
    kings = (card(Rank.KING, Suit.HEARTS), card(Rank.KING, Suit.HEARTS, deck_copy=2))
    analysis = analyze_initial_attack(kings, TrumpState.from_source_card(card(Rank.SIX)))
    assert analysis.reason is InitialAttackReason.SAME_RANK
    assert len({value.physical_id for value in kings}) == 2


def test_d06_duplicate_identity_survives_table_take_and_refill() -> None:
    kings = (card(Rank.KING, Suit.HEARTS), card(Rank.KING, Suit.HEARTS, deck_copy=2))
    refill = (card(Rank.EIGHT), card(Rank.NINE))
    game = GameState(
        seat_one_hand=(*kings, card(Rank.SIX)),
        seat_two_hand=(card(Rank.SEVEN), card(Rank.EIGHT, Suit.DIAMONDS)),
        draw_pile=refill,
        current_attacker=Seat.ONE,
        deck_config=CLASSIC_2,
    )
    game = play_game_initial_attack(start_game_bout(game), Seat.ONE, kings)
    assert game.active_bout is not None
    assert game.active_bout.table_cards == kings
    game = take_game_bout(game, Seat.TWO)
    held_kings = tuple(value for value in game.seat_two_hand if value.rank is Rank.KING)
    assert {value.physical_id for value in held_kings} == {value.physical_id for value in kings}
    assert len(game.all_cards) == 7
    assert not any(value.rank is Rank.KING for value in game.seat_one_hand)


def test_d07_classic_ordinary_suit_trump() -> None:
    trump = TrumpState.from_source_card(card(Rank.SEVEN, Suit.HEARTS))
    assert get_effective_value(card(Rank.EIGHT, Suit.HEARTS), trump) == 16
    assert get_effective_value(card(Rank.EIGHT, Suit.SPADES), trump) == 8


def test_d08_classic_ordinary_rank_trump() -> None:
    trump = TrumpState.from_source_card(card(Rank.SEVEN, Suit.HEARTS))
    assert get_effective_value(card(Rank.SEVEN, Suit.SPADES), trump) == 14
    assert get_effective_value(card(Rank.EIGHT, Suit.SPADES), trump) == 8


@pytest.mark.parametrize(
    ("suit", "top_rank", "ordinary", "ordinary_value"),
    [
        pytest.param(
            Suit.HEARTS,
            Rank.SEVEN,
            card(Rank.EIGHT, Suit.HEARTS),
            16,
            id="D09",
        ),
        pytest.param(
            Suit.DIAMONDS,
            Rank.FOUR,
            card(Rank.FOUR, Suit.CLUBS),
            8,
            id="D10",
        ),
    ],
)
def test_d09_d10_red_suit_top_trumps_only_red_joker(
    suit: Suit,
    top_rank: Rank,
    ordinary: Card,
    ordinary_value: int,
) -> None:
    trump = TrumpState.from_source_card(card(top_rank, suit))
    assert get_effective_value(joker(JokerColor.RED), trump) == 50
    assert get_effective_value(joker(JokerColor.BLACK), trump) == 25
    assert get_effective_value(ordinary, trump) == ordinary_value


@pytest.mark.parametrize(
    ("suit", "top_rank", "ordinary", "ordinary_value"),
    [
        pytest.param(
            Suit.SPADES,
            Rank.TEN,
            card(Rank.THREE, Suit.SPADES),
            6,
            id="D11",
        ),
        pytest.param(
            Suit.CLUBS,
            Rank.QUEEN,
            card(Rank.QUEEN, Suit.HEARTS),
            30,
            id="D12",
        ),
    ],
)
def test_d11_d12_black_suit_top_trumps_only_black_joker(
    suit: Suit,
    top_rank: Rank,
    ordinary: Card,
    ordinary_value: int,
) -> None:
    trump = TrumpState.from_source_card(card(top_rank, suit))
    assert get_effective_value(joker(JokerColor.BLACK), trump) == 50
    assert get_effective_value(joker(JokerColor.RED), trump) == 25
    assert get_effective_value(ordinary, trump) == ordinary_value


def test_d13_ordinary_top_affects_both_same_color_joker_copies() -> None:
    trump = TrumpState.from_source_card(card(Rank.NINE, Suit.DIAMONDS))
    assert [
        get_effective_value(joker(JokerColor.RED, deck_copy=copy), trump) for copy in (1, 2)
    ] == [50, 50]
    assert [
        get_effective_value(joker(JokerColor.BLACK, deck_copy=copy), trump) for copy in (1, 2)
    ] == [25, 25]


def test_d14_exposed_red_joker_trumps_red_suits() -> None:
    trump = TrumpState.from_source_card(joker(JokerColor.RED))
    assert get_effective_value(card(Rank.FIVE, Suit.HEARTS), trump) == 10
    assert get_effective_value(card(Rank.SIX, Suit.DIAMONDS), trump) == 12
    assert get_effective_value(card(Rank.FIVE, Suit.CLUBS), trump) == 5


def test_d15_exposed_red_joker_trumps_all_red_copies() -> None:
    trump = TrumpState.from_source_card(joker(JokerColor.RED))
    assert all(is_trump(joker(JokerColor.RED, deck_copy=copy), trump) for copy in (1, 2))


def test_d16_exposed_red_joker_leaves_black_jokers_normal() -> None:
    trump = TrumpState.from_source_card(joker(JokerColor.RED, deck_copy=2))
    assert [
        get_effective_value(joker(JokerColor.BLACK, deck_copy=copy), trump) for copy in (1, 2)
    ] == [25, 25]


def test_d17_exposed_black_joker_trumps_black_suits() -> None:
    trump = TrumpState.from_source_card(joker(JokerColor.BLACK))
    assert get_effective_value(card(Rank.FIVE, Suit.CLUBS), trump) == 10
    assert get_effective_value(card(Rank.SIX, Suit.SPADES), trump) == 12
    assert get_effective_value(card(Rank.FIVE, Suit.HEARTS), trump) == 5


def test_d18_exposed_black_joker_affects_only_black_jokers() -> None:
    trump = TrumpState.from_source_card(joker(JokerColor.BLACK))
    assert [
        get_effective_value(joker(JokerColor.BLACK, deck_copy=copy), trump) for copy in (1, 2)
    ] == [50, 50]
    assert [
        get_effective_value(joker(JokerColor.RED, deck_copy=copy), trump) for copy in (1, 2)
    ] == [25, 25]


def test_d19_empty_pile_removes_every_trump() -> None:
    selected = (
        joker(JokerColor.RED),
        joker(JokerColor.BLACK),
        card(Rank.ACE, Suit.HEARTS),
        card(Rank.SEVEN, Suit.HEARTS),
    )
    assert [get_effective_value(value, NO_TRUMP) for value in selected] == [25, 25, 20, 7]


def test_d20_exact_duplicate_matching_rank_and_suit_doubles_once() -> None:
    trump = TrumpState.from_source_card(card(Rank.KING, Suit.HEARTS))
    assert get_effective_value(card(Rank.KING, Suit.HEARTS, deck_copy=2), trump) == 36


@pytest.mark.parametrize(
    ("rank", "expected"),
    [(Rank.TWO, 2), (Rank.THREE, 3), (Rank.FOUR, 4), (Rank.FIVE, 5), (Rank.JOKER, 25)],
)
def test_extended_base_values(rank: Rank, expected: int) -> None:
    value = joker(JokerColor.RED) if rank is Rank.JOKER else card(rank)
    assert get_base_value(value) == expected


def test_d21_classic_low_initial_street() -> None:
    selected = selected_ranks(Rank.SIX, Rank.SEVEN, Rank.EIGHT, Rank.NINE, Rank.TEN)
    assert analyze_rank_run((), selected, DeckProfile.CLASSIC) is not None
    assert analyze_initial_attack(selected, NO_TRUMP).legal


def test_d22_classic_high_initial_street() -> None:
    selected = selected_ranks(Rank.TEN, Rank.JACK, Rank.QUEEN, Rank.KING, Rank.ACE)
    assert analyze_initial_attack(selected, NO_TRUMP).reason is InitialAttackReason.RANK_RUN


def test_d23_classic_wrap_is_invalid_only_as_street_basis() -> None:
    selected = selected_ranks(Rank.KING, Rank.ACE, Rank.SIX, Rank.SEVEN, Rank.EIGHT)
    assert analyze_rank_run((), selected, DeckProfile.CLASSIC) is None


def test_d24_classic_street_allows_duplicate_physical_ranks() -> None:
    selected = (
        *selected_ranks(Rank.TEN, Rank.JACK, Rank.QUEEN, Rank.KING, Rank.ACE),
        card(Rank.JACK, deck_copy=2),
        card(Rank.QUEEN, deck_copy=2),
    )
    assert analyze_rank_run((), selected, DeckProfile.CLASSIC) is not None
    assert analyze_initial_attack(selected, NO_TRUMP).legal


def test_d25_duplicate_does_not_create_fifth_classic_position() -> None:
    selected = (
        *selected_ranks(Rank.TEN, Rank.JACK, Rank.QUEEN, Rank.KING),
        card(Rank.QUEEN, deck_copy=2),
    )
    assert analyze_rank_run((), selected, DeckProfile.CLASSIC) is None


def test_d26_extended_low_initial_street() -> None:
    selected = selected_ranks(Rank.TWO, Rank.THREE, Rank.FOUR, Rank.FIVE, Rank.SIX)
    assert analyze_rank_run((), selected, DeckProfile.EXTENDED) is not None
    assert analyze_initial_attack(selected, NO_TRUMP, DeckProfile.EXTENDED).legal


def test_d27_extended_ace_high_initial_street() -> None:
    selected = selected_ranks(Rank.TEN, Rank.JACK, Rank.QUEEN, Rank.KING, Rank.ACE)
    analysis = analyze_initial_attack(selected, NO_TRUMP, DeckProfile.EXTENDED)
    assert analysis.reason is InitialAttackReason.RANK_RUN


def test_d28_extended_street_reaches_joker() -> None:
    selected = (
        *selected_ranks(Rank.TEN, Rank.JACK, Rank.QUEEN, Rank.KING, Rank.ACE),
        joker(JokerColor.RED),
    )
    assert analyze_rank_run((), selected, DeckProfile.EXTENDED) is not None
    assert analyze_initial_attack(selected, NO_TRUMP, DeckProfile.EXTENDED).legal


def test_d29_extended_wrap_is_invalid_only_as_street_basis() -> None:
    selected = (
        card(Rank.ACE, Suit.HEARTS),
        joker(JokerColor.RED),
        card(Rank.TWO, Suit.HEARTS),
        card(Rank.THREE, Suit.DIAMONDS),
        card(Rank.FOUR, Suit.SPADES),
    )
    trump = TrumpState.from_source_card(card(Rank.TEN, Suit.CLUBS))
    assert analyze_rank_run((), selected, DeckProfile.EXTENDED) is None
    assert [get_effective_value(value, trump) for value in selected] == [20, 25, 2, 3, 4]
    assert analyze_initial_attack(selected, trump, DeckProfile.EXTENDED).legal


def test_d30_two_jokers_create_one_street_position() -> None:
    selected = (
        card(Rank.QUEEN),
        card(Rank.KING),
        card(Rank.ACE),
        joker(JokerColor.RED),
        joker(JokerColor.BLACK),
    )
    assert analyze_rank_run((), selected, DeckProfile.EXTENDED) is None


def test_d31_both_joker_colors_share_terminal_run_rank() -> None:
    selected = (
        *selected_ranks(Rank.TEN, Rank.JACK, Rank.QUEEN, Rank.KING, Rank.ACE),
        joker(JokerColor.RED),
        joker(JokerColor.BLACK),
    )
    run = analyze_rank_run((), selected, DeckProfile.EXTENDED)
    assert run is not None and run.length == 6 and run.end is Rank.JOKER


def test_d32_seven_card_street_fills_seven_card_cap() -> None:
    selected = (
        *selected_ranks(Rank.TEN, Rank.JACK, Rank.QUEEN, Rank.KING, Rank.ACE),
        card(Rank.JACK, deck_copy=2),
        card(Rank.QUEEN, deck_copy=2),
    )
    bout = BoutState.start(
        attacker=Seat.ONE,
        hand_counts=(7, 7),
        trump_state=NO_TRUMP,
        deck_profile=DeckProfile.CLASSIC,
    )
    played = play_initial_attack(bout, Seat.ONE, selected)
    assert played.total_attack_card_count == played.attack_card_limit == 7


def test_d33_eight_card_street_exceeds_seven_card_cap_atomically() -> None:
    selected = (
        *selected_ranks(Rank.TEN, Rank.JACK, Rank.QUEEN, Rank.KING, Rank.ACE),
        card(Rank.JACK, deck_copy=2),
        card(Rank.QUEEN, deck_copy=2),
        card(Rank.KING, deck_copy=2),
    )
    bout = BoutState.start(
        attacker=Seat.ONE,
        hand_counts=(8, 7),
        trump_state=NO_TRUMP,
        deck_profile=DeckProfile.CLASSIC,
    )
    with pytest.raises(BoutActionError) as caught:
        play_initial_attack(bout, Seat.ONE, selected)
    assert caught.value.code is BoutErrorCode.ATTACK_CARD_LIMIT_EXCEEDED
    assert bout.packets == ()


def test_d34_ten_card_street_fits_ten_card_defender() -> None:
    selected = tuple(
        card(rank, deck_copy=copy)
        for rank in (Rank.TEN, Rank.JACK, Rank.QUEEN, Rank.KING, Rank.ACE)
        for copy in (1, 2)
    )
    bout = BoutState.start(
        attacker=Seat.ONE,
        hand_counts=(10, 10),
        trump_state=NO_TRUMP,
        deck_profile=DeckProfile.CLASSIC,
    )
    assert play_initial_attack(bout, Seat.ONE, selected).total_attack_card_count == 10


def test_d35_extended_post_response_street_uses_table_history() -> None:
    table = selected_ranks(Rank.TEN, Rank.JACK, Rank.KING, Rank.ACE)
    selected = (card(Rank.QUEEN), joker(JokerColor.RED))
    analysis = analyze_throw_in(selected, table, (), NO_TRUMP, DeckProfile.EXTENDED)
    assert analysis.rank_run is not None
    assert analysis.rank_run.ranks == (
        Rank.TEN,
        Rank.JACK,
        Rank.QUEEN,
        Rank.KING,
        Rank.ACE,
        Rank.JOKER,
    )


def test_d36_omitted_duplicate_gets_new_current_street_basis() -> None:
    table = selected_ranks(Rank.TEN, Rank.JACK, Rank.QUEEN, Rank.KING, Rank.ACE)
    selected = (card(Rank.QUEEN, deck_copy=2),)
    analysis = analyze_throw_in(selected, table, (), NO_TRUMP, DeckProfile.CLASSIC)
    assert ThrowInReason.RANK_RUN in analysis.reasons
    assert analysis.rank_run is not None and analysis.rank_run.length == 5


def test_d37_red_and_black_jokers_share_same_rank() -> None:
    trump = TrumpState.from_source_card(card(Rank.TWO, Suit.HEARTS))
    selected = (joker(JokerColor.RED), joker(JokerColor.BLACK))
    assert [get_effective_value(value, trump) for value in selected] == [50, 25]
    assert cards_have_same_rank(selected)
    analysis = analyze_initial_attack(selected, trump, DeckProfile.EXTENDED)
    assert analysis.reason is InitialAttackReason.SAME_RANK


def test_d38_joker_is_normal_value_bearing_transfer_target() -> None:
    trump = TrumpState.from_source_card(card(Rank.TWO, Suit.CLUBS))
    selected = (card(Rank.TEN, Suit.HEARTS), card(Rank.QUEEN, Suit.HEARTS))
    analysis = analyze_transfer(selected, 25, trump)
    assert analysis.legal and analysis.next_target == 50


def test_d39_single_classic_two_player_compatibility() -> None:
    trump = TrumpState.from_source_card(card(Rank.SEVEN, Suit.HEARTS))
    analysis = analyze_defense((card(Rank.JACK), card(Rank.SEVEN)), 18, trump)
    assert analysis.selected_value == 26 and analysis.legal


def test_d40_extended_deck_keeps_multiplayer_state_machine() -> None:
    selected = (
        *selected_ranks(Rank.TEN, Rank.JACK, Rank.QUEEN, Rank.KING, Rank.ACE),
        joker(JokerColor.RED, deck_copy=2),
    )
    bout = BoutState.start(
        attacker=Seat.ONE,
        seat_order=(Seat.ONE, Seat.TWO, Seat.THREE, Seat.FOUR),
        hand_counts=(7, 7, 7, 7),
        trump_state=TrumpState.from_source_card(joker(JokerColor.RED)),
        deck_profile=DeckProfile.EXTENDED,
    )
    played = play_initial_attack(bout, Seat.ONE, selected)
    assert played.phase is BoutPhase.WAITING_FOR_DEFENDER_RESPONSE
    assert played.defender is Seat.TWO
    assert played.attacker_order == (Seat.ONE, Seat.THREE, Seat.FOUR)
    assert played.refill_order == (Seat.ONE, Seat.THREE, Seat.FOUR, Seat.TWO)


@pytest.mark.parametrize(
    ("profile", "ranks", "expected"),
    [
        pytest.param(
            DeckProfile.CLASSIC,
            (Rank.NINE, Rank.TEN, Rank.JACK, Rank.QUEEN, Rank.KING),
            True,
            id="classic-9-through-king",
        ),
        pytest.param(
            DeckProfile.EXTENDED,
            (Rank.EIGHT, Rank.NINE, Rank.TEN, Rank.JACK, Rank.QUEEN),
            True,
            id="extended-8-through-queen",
        ),
        pytest.param(
            DeckProfile.EXTENDED,
            (Rank.TWO, Rank.THREE, Rank.FOUR, Rank.SIX, Rank.SEVEN),
            False,
            id="extended-gap",
        ),
    ],
)
def test_additional_initial_street_matrix(
    profile: DeckProfile,
    ranks: tuple[Rank, ...],
    expected: bool,
) -> None:
    assert (analyze_rank_run((), selected_ranks(*ranks), profile) is not None) is expected


def test_seven_card_street_is_rejected_against_six_card_capacity() -> None:
    selected = (
        *selected_ranks(Rank.TEN, Rank.JACK, Rank.QUEEN, Rank.KING, Rank.ACE),
        card(Rank.JACK, deck_copy=2),
        card(Rank.QUEEN, deck_copy=2),
    )
    bout = BoutState.start(
        attacker=Seat.ONE,
        hand_counts=(7, 6),
        trump_state=NO_TRUMP,
        deck_profile=DeckProfile.CLASSIC,
    )
    with pytest.raises(BoutActionError) as caught:
        play_initial_attack(bout, Seat.ONE, selected)
    assert caught.value.code is BoutErrorCode.ATTACK_CARD_LIMIT_EXCEEDED


def test_low_extended_ranks_and_joker_copies_work_in_transfer() -> None:
    low = analyze_transfer((card(Rank.TWO), card(Rank.THREE)), 5, NO_TRUMP)
    assert low.legal and low.next_target == 10

    trump = TrumpState.from_source_card(card(Rank.SEVEN, Suit.HEARTS))
    red = joker(JokerColor.RED)
    black = joker(JokerColor.BLACK, deck_copy=2)
    extended = analyze_packet_transfer(
        (red, black),
        (joker(JokerColor.BLACK),),
        25,
        trump,
    )
    assert extended.mode is PacketTransferMode.SAME_RANK_EXTENDED
    assert extended.selected_value == 75 and extended.next_target == 100


def test_extended_four_player_deal_bout_defense_phases_and_refill() -> None:
    deck = list(create_deck(EXTENDED_1))
    attack = tuple(card(rank) for rank in (Rank.TEN, Rank.JACK, Rank.QUEEN, Rank.KING, Rank.ACE))
    defense = (
        joker(JokerColor.BLACK),
        card(Rank.ACE, Suit.SPADES),
        card(Rank.KING, Suit.SPADES),
        card(Rank.QUEEN, Suit.SPADES),
    )
    attacker_fillers = (card(Rank.SIX, Suit.DIAMONDS), card(Rank.SEVEN, Suit.DIAMONDS))
    defender_fillers = (
        card(Rank.TWO, Suit.SPADES),
        card(Rank.THREE, Suit.SPADES),
        card(Rank.FOUR, Suit.SPADES),
    )
    top = joker(JokerColor.RED)
    reserved = {*attack, *defense, *attacker_fillers, *defender_fillers, top}
    available = tuple(value for value in deck if value not in reserved)
    hands = (
        (*attack, *attacker_fillers),
        (*defense, *defender_fillers),
        available[:7],
        available[7:14],
    )
    used = {value for hand in hands for value in hand}
    remaining = [value for value in deck if value not in used and value != top]
    ordered = tuple(hand[index] for index in range(7) for hand in hands) + (top, *remaining)
    game = GameState.deal(
        ordered,
        initial_attacker=Seat.ONE,
        player_count=4,
        deck_config=EXTENDED_1,
    )
    game = start_game_bout(game)
    assert game.current_trump_state == TrumpState.from_source_card(top)
    game = play_game_initial_attack(game, Seat.ONE, attack)
    game = play_game_defense(game, Seat.TWO, defense)
    while game.phase is GamePhase.BOUT_ACTIVE:
        assert game.active_bout is not None
        game = finish_game_bout(game, game.active_bout.attacker)
    assert game.phase is GamePhase.READY_FOR_BOUT
    assert game.deck_config == EXTENDED_1 and len(game.all_cards) == 54
    assert all(len(hand) == 7 for hand in game.hands)


def test_extended_double_duplicate_fragment_removes_only_selected_instance() -> None:
    first = card(Rank.KING, Suit.HEARTS)
    second = card(Rank.KING, Suit.HEARTS, deck_copy=2)
    game = GameState(
        seat_one_hand=(first, second, card(Rank.SIX)),
        seat_two_hand=(card(Rank.ACE), card(Rank.SEVEN)),
        current_attacker=Seat.ONE,
        deck_config=EXTENDED_2,
    )
    played = play_game_initial_attack(start_game_bout(game), Seat.ONE, (first,))
    assert played.seat_one_hand == (second, card(Rank.SIX))
    assert played.active_bout is not None and played.active_bout.table_cards == (first,)


def test_physical_duplicates_count_twice_in_math_but_once_in_run_length() -> None:
    tens = (card(Rank.TEN, Suit.HEARTS), card(Rank.TEN, Suit.HEARTS, deck_copy=2))
    summary = summarize_table_arithmetic(tens, NO_TRUMP)
    run = analyze_rank_run_throw_in(
        (*tens, card(Rank.JACK), card(Rank.QUEEN), card(Rank.KING)),
        (card(Rank.ACE),),
    )
    assert summary.total_effective_value == 20
    assert summary.physical_card_count == 2
    assert summary.arithmetic_mean == Fraction(10, 1)
    assert run is not None and run.length == 5


@pytest.mark.parametrize("deck_config", [EXTENDED_1, CLASSIC_2, EXTENDED_2])
def test_configured_endgame_depletes_without_36_card_assumption(
    deck_config: DeckConfig,
) -> None:
    deck = create_deck(deck_config)
    attack = next(value for value in deck if value.rank is Rank.SIX and value.suit is Suit.CLUBS)
    defense = next(value for value in deck if value.rank is Rank.SEVEN and value.suit is Suit.CLUBS)
    discard = tuple(value for value in deck if value not in {attack, defense})
    game = GameState(
        seat_one_hand=(attack,),
        seat_two_hand=(defense,),
        discard_pile=discard,
        current_attacker=Seat.ONE,
        deck_config=deck_config,
    )
    game = play_game_initial_attack(start_game_bout(game), Seat.ONE, (attack,))
    game = play_game_defense(game, Seat.TWO, (defense,))
    assert game.phase is GamePhase.COMPLETE
    assert game.result is not None and game.result.outcome is GameOutcome.DRAW
    assert game.deck_config == deck_config
    assert len(game.all_cards) == deck_config.card_count
    assert game.current_trump_state == TrumpState.no_trump()


@pytest.mark.parametrize("deck_config", [CLASSIC_1, EXTENDED_1, CLASSIC_2, EXTENDED_2])
@pytest.mark.parametrize("player_count", [2, 3, 4])
def test_configured_deal_keeps_seven_cards_and_conserves_physical_instances(
    deck_config: DeckConfig,
    player_count: int,
) -> None:
    deck = create_deck(deck_config)
    state = GameState.deal(
        deck,
        initial_attacker=Seat.ONE,
        player_count=player_count,
        deck_config=deck_config,
    )
    assert all(len(hand) == 7 for hand in state.hands)
    assert len(state.draw_pile) == deck_config.card_count - (7 * player_count)
    assert Counter(state.all_cards) == Counter(deck)
    assert len({value.physical_id for value in state.all_cards}) == deck_config.card_count


@pytest.mark.parametrize("deck_config", [CLASSIC_1, EXTENDED_1, CLASSIC_2, EXTENDED_2])
def test_new_game_factory_retains_authoritative_configuration(deck_config: DeckConfig) -> None:
    state = create_new_game(
        random.Random(20261010),
        player_count=4,
        deck_config=deck_config,
    )
    assert state.deck_config == deck_config
    assert len(state.all_cards) == deck_config.card_count
    assert all(len(hand) == 7 for hand in state.hands)


@pytest.mark.parametrize("deck_config", [EXTENDED_1, CLASSIC_2, EXTENDED_2])
def test_balanced_insufficient_refill_is_deck_size_agnostic(
    deck_config: DeckConfig,
) -> None:
    deck = create_deck(deck_config)
    hands = (deck[:5], deck[5:10])
    source = deck[10:13]
    refilled, remaining = refill_hands(
        hands,
        source,
        (Seat.ONE, Seat.TWO),
        (Seat.ONE, Seat.TWO),
    )
    assert tuple(map(len, refilled)) == (7, 6)
    assert remaining == ()
    assert Counter((*refilled[0], *refilled[1])) == Counter(deck[:13])


def test_joker_trump_selection_uses_lowest_effective_value() -> None:
    trump = TrumpState.from_source_card(joker(JokerColor.RED))
    hands = (
        (joker(JokerColor.RED, deck_copy=2),),
        (card(Rank.TWO, Suit.HEARTS),),
        (card(Rank.THREE, Suit.CLUBS),),
    )
    attacker = _determine_initial_attacker(
        hands,
        (Seat.ONE, Seat.TWO, Seat.THREE),
        trump,
        ChooseSeat(Seat.THREE),
    )
    assert get_effective_value(hands[0][0], trump) == 50
    assert get_effective_value(hands[1][0], trump) == 4
    assert attacker is Seat.TWO


def test_double_deck_equal_trumps_use_existing_tie_break() -> None:
    trump = TrumpState.from_source_card(card(Rank.SIX, Suit.HEARTS))
    hands = (
        (card(Rank.SIX, Suit.SPADES),),
        (card(Rank.SIX, Suit.SPADES, deck_copy=2),),
    )
    assert (
        _determine_initial_attacker(
            hands,
            (Seat.ONE, Seat.TWO),
            trump,
            ChooseSeat(Seat.TWO),
        )
        is Seat.TWO
    )


def test_double_deck_bito_discards_both_duplicate_faces_independently() -> None:
    kings = (card(Rank.KING, Suit.HEARTS), card(Rank.KING, Suit.HEARTS, deck_copy=2))
    aces = (card(Rank.ACE, Suit.SPADES), card(Rank.ACE, Suit.SPADES, deck_copy=2))
    game = GameState(
        seat_one_hand=(*kings, card(Rank.SIX)),
        seat_two_hand=(*aces, card(Rank.SEVEN)),
        current_attacker=Seat.ONE,
        deck_config=CLASSIC_2,
    )
    game = play_game_initial_attack(start_game_bout(game), Seat.ONE, kings)
    game = play_game_defense(game, Seat.TWO, aces)
    game = finish_game_bout(game, Seat.ONE)
    assert {value.physical_id for value in game.discard_pile if value.rank is Rank.KING} == {
        value.physical_id for value in kings
    }
    assert Counter(game.all_cards) == Counter((*kings, *aces, card(Rank.SIX), card(Rank.SEVEN)))


def test_action_reference_selects_exact_duplicate_and_rejects_unknown_copy_atomically() -> None:
    first = card(Rank.KING, Suit.HEARTS)
    second = card(Rank.KING, Suit.HEARTS, deck_copy=2)
    game = GameState(
        seat_one_hand=(first, card(Rank.SIX)),
        seat_two_hand=(card(Rank.SEVEN), card(Rank.EIGHT)),
        current_attacker=Seat.ONE,
        deck_config=CLASSIC_2,
    )
    active = start_game_bout(game)
    with pytest.raises(GameActionError) as caught:
        play_game_initial_attack(active, Seat.ONE, (second,))
    assert caught.value.code is GameErrorCode.CARD_NOT_OWNED
    assert active.seat_one_hand == game.seat_one_hand
    assert active.active_bout is not None and active.active_bout.table_cards == ()


@pytest.mark.parametrize(
    "factory",
    [
        pytest.param(lambda: DeckConfig("classic", 1), id="profile-type"),
        pytest.param(lambda: DeckConfig(DeckProfile.CLASSIC, 0), id="zero-copies"),
        pytest.param(lambda: DeckConfig(DeckProfile.CLASSIC, 3), id="three-copies"),
        pytest.param(lambda: DeckConfig(DeckProfile.CLASSIC, True), id="bool-copies"),
    ],
)
def test_invalid_deck_configuration_fails_explicitly(
    factory: Callable[[], DeckConfig],
) -> None:
    with pytest.raises((TypeError, ValueError)):
        factory()


def test_configured_deal_rejects_wrong_profile_population() -> None:
    with pytest.raises(GameActionError) as caught:
        GameState.deal(
            create_deck(EXTENDED_1),
            initial_attacker=Seat.ONE,
            deck_config=CLASSIC_1,
        )
    assert caught.value.code is GameErrorCode.INVALID_DECK
