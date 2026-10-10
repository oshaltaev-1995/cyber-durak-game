"""Immutable deck configuration, card, and trump domain values."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Final


class DeckProfile(StrEnum):
    """The suited-rank population and linear street order for a Kiba deck."""

    CLASSIC = "classic"
    EXTENDED = "extended"


class Rank(StrEnum):
    """A supported Kiba card rank."""

    TWO = "2"
    THREE = "3"
    FOUR = "4"
    FIVE = "5"
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


CLASSIC_RANKS: Final[tuple[Rank, ...]] = (
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
EXTENDED_SUITED_RANKS: Final[tuple[Rank, ...]] = (
    Rank.TWO,
    Rank.THREE,
    Rank.FOUR,
    Rank.FIVE,
    *CLASSIC_RANKS,
)


def ranks_for_profile(profile: DeckProfile) -> tuple[Rank, ...]:
    """Return the suited ranks present in one physical deck copy."""
    if not isinstance(profile, DeckProfile):
        raise TypeError("profile must be a DeckProfile")
    return CLASSIC_RANKS if profile is DeckProfile.CLASSIC else EXTENDED_SUITED_RANKS


def street_ranks_for_profile(profile: DeckProfile) -> tuple[Rank, ...]:
    """Return the authoritative non-wrapping logical street order."""
    ranks = ranks_for_profile(profile)
    return ranks if profile is DeckProfile.CLASSIC else (*ranks, Rank.JOKER)


@dataclass(frozen=True, slots=True)
class DeckConfig:
    """The two independent dimensions of one canonical deck configuration."""

    profile: DeckProfile = DeckProfile.CLASSIC
    deck_count: int = 1

    def __post_init__(self) -> None:
        if not isinstance(self.profile, DeckProfile):
            raise TypeError("profile must be a DeckProfile")
        if isinstance(self.deck_count, bool) or not isinstance(self.deck_count, int):
            raise TypeError("deck_count must be an int")
        if self.deck_count not in {1, 2}:
            raise ValueError("deck_count must be 1 or 2")

    @property
    def card_count(self) -> int:
        """Return the exact physical population derived from profile and copies."""
        return (36 if self.profile is DeckProfile.CLASSIC else 54) * self.deck_count


DEFAULT_DECK_CONFIG: Final = DeckConfig()


@dataclass(frozen=True, slots=True)
class Card:
    """A valid normal card or colored Joker."""

    rank: Rank
    suit: Suit | None = None
    joker_color: JokerColor | None = None
    deck_copy: int = 1

    def __post_init__(self) -> None:
        if not isinstance(self.rank, Rank):
            raise TypeError("rank must be a Rank")
        if self.suit is not None and not isinstance(self.suit, Suit):
            raise TypeError("suit must be a Suit or None")
        if self.joker_color is not None and not isinstance(self.joker_color, JokerColor):
            raise TypeError("joker_color must be a JokerColor or None")
        if isinstance(self.deck_copy, bool) or not isinstance(self.deck_copy, int):
            raise TypeError("deck_copy must be an int")
        if self.deck_copy not in {1, 2}:
            raise ValueError("deck_copy must be 1 or 2")

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

    @property
    def display_identity(self) -> tuple[Rank, Suit | None, JokerColor | None]:
        """Return the ordinary face identity, intentionally excluding copy number."""
        return self.rank, self.suit, self.joker_color

    @property
    def physical_id(self) -> str:
        """Return a deterministic identity that separates exact visual duplicates."""
        if self.rank is Rank.JOKER:
            assert self.joker_color is not None
            face = f"joker:{self.joker_color.value}"
        else:
            assert self.suit is not None
            face = f"{self.rank.value}:{self.suit.value}"
        return f"deck-{self.deck_copy}:{face}"


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
