"""Stable display codes and exact physical references for the public API."""

from enum import StrEnum

from kiba_api.game import (
    DEFAULT_DECK_CONFIG,
    Card,
    DeckConfig,
    DeckProfile,
    JokerColor,
    Rank,
    Suit,
    create_36_card_deck,
    create_deck,
)

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
    INVALID_CARD_ID = "invalid_card_id"
    DUPLICATE_CARD_ID = "duplicate_card_id"
    LEGACY_CARD_REFERENCE_NOT_AVAILABLE = "legacy_card_reference_not_available"


class CardCodeError(ValueError):
    """A rejected external card reference with a stable error code."""

    def __init__(self, code: CardCodeErrorCode) -> None:
        self.code = code
        super().__init__(code.value)


def card_to_code(card: Card) -> str:
    """Serialize one display identity without encoding its physical deck copy."""
    if card.rank is Rank.JOKER:
        if card.joker_color is JokerColor.RED:
            return "RJ"
        if card.joker_color is JokerColor.BLACK:
            return "BJ"
        raise ValueError("a Joker code requires a Joker color")
    if card.suit is None:
        raise ValueError("a normal card code requires a suit")
    return f"{card.rank.value}{_SUIT_CODES[card.suit]}"


_CARDS_BY_CODE = {card_to_code(card): card for card in create_36_card_deck()}
_CARDS_BY_PHYSICAL_ID = {
    card.physical_id: card
    for card in create_deck(DeckConfig(profile=DeckProfile.EXTENDED, deck_count=2))
}


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


def parse_card_ids(card_ids: list[str]) -> tuple[Card, ...]:
    """Parse unique exact physical IDs without inferring ownership."""
    if len(set(card_ids)) != len(card_ids):
        raise CardCodeError(CardCodeErrorCode.DUPLICATE_CARD_ID)

    cards: list[Card] = []
    for card_id in card_ids:
        card = _CARDS_BY_PHYSICAL_ID.get(card_id)
        if card is None:
            raise CardCodeError(CardCodeErrorCode.INVALID_CARD_ID)
        cards.append(card)
    return tuple(cards)


def parse_card_references(
    *,
    deck_config: DeckConfig,
    codes: list[str] | None,
    card_ids: list[str] | None,
) -> tuple[Card, ...]:
    """Normalize one mutually-exclusive legacy or exact card-reference list."""
    if card_ids is not None:
        return parse_card_ids(card_ids)
    if not codes:
        return ()
    if deck_config != DEFAULT_DECK_CONFIG:
        raise CardCodeError(CardCodeErrorCode.LEGACY_CARD_REFERENCE_NOT_AVAILABLE)
    return parse_card_codes(codes)
