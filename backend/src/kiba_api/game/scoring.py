"""Pure card scoring and trump calculations."""

from collections.abc import Iterable, Mapping
from types import MappingProxyType
from typing import Final

from kiba_api.game.cards import Card, JokerColor, Rank, Suit, TrumpState

_BASE_VALUES: Final[Mapping[Rank, int]] = MappingProxyType(
    {
        Rank.TWO: 2,
        Rank.THREE: 3,
        Rank.FOUR: 4,
        Rank.FIVE: 5,
        Rank.SIX: 6,
        Rank.SEVEN: 7,
        Rank.EIGHT: 8,
        Rank.NINE: 9,
        Rank.TEN: 10,
        Rank.JACK: 12,
        Rank.QUEEN: 15,
        Rank.KING: 18,
        Rank.ACE: 20,
        Rank.JOKER: 25,
    }
)

_SUITS_BY_COLOR: Final[Mapping[JokerColor, frozenset[Suit]]] = MappingProxyType(
    {
        JokerColor.RED: frozenset({Suit.DIAMONDS, Suit.HEARTS}),
        JokerColor.BLACK: frozenset({Suit.CLUBS, Suit.SPADES}),
    }
)


def get_base_value(card: Card) -> int:
    """Return a card's authoritative value before trump multiplication."""
    return _BASE_VALUES[card.rank]


def is_trump(card: Card, trump_state: TrumpState) -> bool:
    """Return whether a card matches the active trump selectors."""
    if not trump_state.active:
        return False

    if trump_state.joker_color is not None:
        if card.rank is Rank.JOKER:
            return card.joker_color is trump_state.joker_color
        return card.suit in _SUITS_BY_COLOR[trump_state.joker_color]

    if card.rank is Rank.JOKER:
        assert trump_state.trump_suit is not None
        exposed_color = (
            JokerColor.RED
            if trump_state.trump_suit in _SUITS_BY_COLOR[JokerColor.RED]
            else JokerColor.BLACK
        )
        return card.joker_color is exposed_color

    return card.rank is trump_state.trump_rank or card.suit is trump_state.trump_suit


def get_effective_value(card: Card, trump_state: TrumpState) -> int:
    """Return a card's base value, doubled exactly when it is trump."""
    multiplier = 2 if is_trump(card, trump_state) else 1
    return get_base_value(card) * multiplier


def get_cards_value(cards: Iterable[Card], trump_state: TrumpState) -> int:
    """Return the total effective value of zero or more cards."""
    return sum(get_effective_value(card, trump_state) for card in cards)
