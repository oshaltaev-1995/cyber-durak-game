"""Stable external card codes for the 36-card REST API."""

from enum import StrEnum

from kiba_api.game import Card, Rank, Suit, create_36_card_deck

_SUIT_CODES = {
    Suit.CLUBS: "C",
    Suit.DIAMONDS: "D",
    Suit.HEARTS: "H",
    Suit.SPADES: "S",
}


class CardCodeErrorCode(StrEnum):
    """Machine-readable failures while decoding submitted card references."""

    INVALID_CARD_CODE = "invalid_card_code"
    DUPLICATE_CARD_CODE = "duplicate_card_code"


class CardCodeError(ValueError):
    """A rejected external card reference with a stable error code."""

    def __init__(self, code: CardCodeErrorCode) -> None:
        self.code = code
        super().__init__(code.value)


def card_to_code(card: Card) -> str:
    """Serialize one normal MVP card as rank plus one-letter suit."""
    if card.rank is Rank.JOKER or card.suit is None:
        raise ValueError("the Phase 3C1 API supports only normal 36-card deck codes")
    return f"{card.rank.value}{_SUIT_CODES[card.suit]}"


_CARDS_BY_CODE = {card_to_code(card): card for card in create_36_card_deck()}


def parse_card_codes(codes: list[str]) -> tuple[Card, ...]:
    """Parse unique canonical card codes without inferring ownership."""
    if len(set(codes)) != len(codes):
        raise CardCodeError(CardCodeErrorCode.DUPLICATE_CARD_CODE)

    cards: list[Card] = []
    for code in codes:
        card = _CARDS_BY_CODE.get(code)
        if card is None:
            raise CardCodeError(CardCodeErrorCode.INVALID_CARD_CODE)
        cards.append(card)
    return tuple(cards)
