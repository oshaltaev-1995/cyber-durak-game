import pytest

from kiba_api.game import (
    Card,
    JokerColor,
    Rank,
    Suit,
    TrumpState,
    get_base_value,
    get_cards_value,
    get_effective_value,
    is_trump,
)


def normal_card(rank: Rank, suit: Suit = Suit.CLUBS) -> Card:
    return Card(rank=rank, suit=suit)


def joker(color: JokerColor) -> Card:
    return Card(rank=Rank.JOKER, joker_color=color)


@pytest.mark.parametrize(
    ("rank", "expected_value"),
    [
        (Rank.SIX, 6),
        (Rank.SEVEN, 7),
        (Rank.EIGHT, 8),
        (Rank.NINE, 9),
        (Rank.TEN, 10),
        (Rank.JACK, 12),
        (Rank.QUEEN, 15),
        (Rank.KING, 18),
        (Rank.ACE, 20),
        (Rank.JOKER, 25),
    ],
)
def test_base_value_for_every_rank(rank: Rank, expected_value: int) -> None:
    card = joker(JokerColor.RED) if rank is Rank.JOKER else normal_card(rank)

    assert get_base_value(card) == expected_value


@pytest.fixture
def king_of_spades_trump() -> TrumpState:
    return TrumpState.from_source_card(normal_card(Rank.KING, Suit.SPADES))


@pytest.mark.parametrize(
    ("card", "expected"),
    [
        (normal_card(Rank.KING, Suit.HEARTS), True),
        (normal_card(Rank.NINE, Suit.SPADES), True),
        (normal_card(Rank.KING, Suit.SPADES), True),
        (normal_card(Rank.NINE, Suit.HEARTS), False),
        (joker(JokerColor.RED), False),
        (joker(JokerColor.BLACK), False),
    ],
)
def test_normal_source_trump_detection(
    card: Card,
    expected: bool,
    king_of_spades_trump: TrumpState,
) -> None:
    assert is_trump(card, king_of_spades_trump) is expected


@pytest.mark.parametrize(
    ("card", "expected"),
    [
        (normal_card(Rank.SIX, Suit.HEARTS), True),
        (normal_card(Rank.SIX, Suit.DIAMONDS), True),
        (normal_card(Rank.SIX, Suit.CLUBS), False),
        (normal_card(Rank.SIX, Suit.SPADES), False),
        (joker(JokerColor.RED), True),
        (joker(JokerColor.BLACK), True),
    ],
)
def test_red_joker_trump_detection(card: Card, expected: bool) -> None:
    state = TrumpState.from_source_card(joker(JokerColor.RED))

    assert is_trump(card, state) is expected


@pytest.mark.parametrize(
    ("card", "expected"),
    [
        (normal_card(Rank.SIX, Suit.CLUBS), True),
        (normal_card(Rank.SIX, Suit.SPADES), True),
        (normal_card(Rank.SIX, Suit.HEARTS), False),
        (normal_card(Rank.SIX, Suit.DIAMONDS), False),
        (joker(JokerColor.RED), True),
        (joker(JokerColor.BLACK), True),
    ],
)
def test_black_joker_trump_detection(card: Card, expected: bool) -> None:
    state = TrumpState.from_source_card(joker(JokerColor.BLACK))

    assert is_trump(card, state) is expected


@pytest.mark.parametrize(
    "card",
    [
        normal_card(Rank.KING, Suit.SPADES),
        normal_card(Rank.NINE, Suit.HEARTS),
        joker(JokerColor.RED),
        joker(JokerColor.BLACK),
    ],
)
def test_inactive_state_has_no_trumps(card: Card) -> None:
    assert is_trump(card, TrumpState.no_trump()) is False


@pytest.mark.parametrize(
    ("card", "state", "expected_value"),
    [
        (normal_card(Rank.KING), TrumpState.no_trump(), 18),
        (
            normal_card(Rank.KING, Suit.HEARTS),
            TrumpState.from_source_card(normal_card(Rank.KING, Suit.SPADES)),
            36,
        ),
        (
            normal_card(Rank.NINE, Suit.SPADES),
            TrumpState.from_source_card(normal_card(Rank.KING, Suit.SPADES)),
            18,
        ),
        (
            normal_card(Rank.NINE, Suit.HEARTS),
            TrumpState.from_source_card(normal_card(Rank.KING, Suit.SPADES)),
            9,
        ),
        (joker(JokerColor.RED), TrumpState.no_trump(), 25),
        (
            joker(JokerColor.BLACK),
            TrumpState.from_source_card(joker(JokerColor.RED)),
            50,
        ),
    ],
)
def test_effective_value(card: Card, state: TrumpState, expected_value: int) -> None:
    assert get_effective_value(card, state) == expected_value


def test_cards_value_sums_ordinary_cards() -> None:
    cards = [normal_card(Rank.SIX), normal_card(Rank.JACK), normal_card(Rank.ACE)]

    assert get_cards_value(cards, TrumpState.no_trump()) == 38


def test_cards_value_sums_mixed_trump_and_non_trump_cards(
    king_of_spades_trump: TrumpState,
) -> None:
    cards = [
        normal_card(Rank.KING, Suit.HEARTS),
        normal_card(Rank.NINE, Suit.SPADES),
        normal_card(Rank.SIX, Suit.HEARTS),
    ]

    assert get_cards_value(cards, king_of_spades_trump) == 60


def test_cards_value_of_empty_collection_is_zero() -> None:
    assert get_cards_value([], TrumpState.no_trump()) == 0
