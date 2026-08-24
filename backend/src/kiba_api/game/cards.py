"""Immutable card and trump domain values."""

from dataclasses import dataclass
from enum import StrEnum


class Rank(StrEnum):
    """A supported Kiba card rank."""

    SIX = "6"
    SEVEN = "7"
    EIGHT = "8"
    NINE = "9"
    TEN = "10"
    JACK = "J"
    QUEEN = "Q"
    KING = "K"
    ACE = "A"
    JOKER = "JOKER"


class Suit(StrEnum):
    """A normal playing-card suit."""

    CLUBS = "clubs"
    DIAMONDS = "diamonds"
    HEARTS = "hearts"
    SPADES = "spades"


class JokerColor(StrEnum):
    """A Joker's printed color."""

    RED = "red"
    BLACK = "black"


@dataclass(frozen=True, slots=True)
class Card:
    """A valid normal card or colored Joker."""

    rank: Rank
    suit: Suit | None = None
    joker_color: JokerColor | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.rank, Rank):
            raise TypeError("rank must be a Rank")
        if self.suit is not None and not isinstance(self.suit, Suit):
            raise TypeError("suit must be a Suit or None")
        if self.joker_color is not None and not isinstance(self.joker_color, JokerColor):
            raise TypeError("joker_color must be a JokerColor or None")

        if self.rank is Rank.JOKER:
            if self.suit is not None:
                raise ValueError("a Joker cannot have a suit")
            if self.joker_color is None:
                raise ValueError("a Joker must have a Joker color")
            return

        if self.suit is None:
            raise ValueError("a normal card must have a suit")
        if self.joker_color is not None:
            raise ValueError("a normal card cannot have a Joker color")


@dataclass(frozen=True, slots=True)
class TrumpState:
    """The immutable trump selectors active for a scoring context."""

    active: bool
    trump_rank: Rank | None = None
    trump_suit: Suit | None = None
    joker_color: JokerColor | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.active, bool):
            raise TypeError("active must be a bool")
        if self.trump_rank is not None and not isinstance(self.trump_rank, Rank):
            raise TypeError("trump_rank must be a Rank or None")
        if self.trump_suit is not None and not isinstance(self.trump_suit, Suit):
            raise TypeError("trump_suit must be a Suit or None")
        if self.joker_color is not None and not isinstance(self.joker_color, JokerColor):
            raise TypeError("joker_color must be a JokerColor or None")

        if not self.active:
            if any(
                selector is not None
                for selector in (self.trump_rank, self.trump_suit, self.joker_color)
            ):
                raise ValueError("an inactive trump state cannot have trump selectors")
            return

        normal_trump = (
            self.trump_rank is not None
            and self.trump_rank is not Rank.JOKER
            and self.trump_suit is not None
            and self.joker_color is None
        )
        joker_trump = (
            self.trump_rank is None and self.trump_suit is None and self.joker_color is not None
        )
        if not (normal_trump or joker_trump):
            raise ValueError("an active trump state must describe a normal card or a Joker")

    @classmethod
    def from_source_card(cls, source_card: Card) -> "TrumpState":
        """Create active trump selectors from the exposed deck card."""
        if not isinstance(source_card, Card):
            raise TypeError("source_card must be a Card")
        if source_card.rank is Rank.JOKER:
            return cls(active=True, joker_color=source_card.joker_color)
        return cls(
            active=True,
            trump_rank=source_card.rank,
            trump_suit=source_card.suit,
        )

    @classmethod
    def no_trump(cls) -> "TrumpState":
        """Create the inactive state used after the draw pile is exhausted."""
        return cls(active=False)
