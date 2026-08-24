from dataclasses import FrozenInstanceError

import pytest

from kiba_api.game import Card, JokerColor, Rank, Suit, TrumpState


def test_normal_card_is_valid() -> None:
    card = Card(rank=Rank.KING, suit=Suit.SPADES)

    assert card.rank is Rank.KING
    assert card.suit is Suit.SPADES
    assert card.joker_color is None


@pytest.mark.parametrize("joker_color", list(JokerColor))
def test_colored_joker_is_valid(joker_color: JokerColor) -> None:
    card = Card(rank=Rank.JOKER, joker_color=joker_color)

    assert card.rank is Rank.JOKER
    assert card.suit is None
    assert card.joker_color is joker_color


def test_card_is_immutable() -> None:
    card = Card(rank=Rank.ACE, suit=Suit.CLUBS)

    with pytest.raises(FrozenInstanceError):
        card.suit = Suit.HEARTS  # type: ignore[misc]


def test_normal_card_requires_suit() -> None:
    with pytest.raises(ValueError, match="normal card must have a suit"):
        Card(rank=Rank.ACE)


def test_normal_card_rejects_joker_color() -> None:
    with pytest.raises(ValueError, match="normal card cannot have a Joker color"):
        Card(rank=Rank.ACE, suit=Suit.CLUBS, joker_color=JokerColor.BLACK)


def test_joker_rejects_suit() -> None:
    with pytest.raises(ValueError, match="Joker cannot have a suit"):
        Card(rank=Rank.JOKER, suit=Suit.HEARTS, joker_color=JokerColor.RED)


def test_joker_requires_color() -> None:
    with pytest.raises(ValueError, match="Joker must have a Joker color"):
        Card(rank=Rank.JOKER)


@pytest.mark.parametrize(
    ("field", "value", "expected_message"),
    [
        ("rank", "K", "rank must be a Rank"),
        ("suit", "spades", "suit must be a Suit or None"),
        ("joker_color", "red", "joker_color must be a JokerColor or None"),
    ],
)
def test_card_rejects_unconstrained_values(
    field: str,
    value: str,
    expected_message: str,
) -> None:
    arguments: dict[str, object] = {"rank": Rank.KING, "suit": Suit.SPADES}
    arguments[field] = value

    with pytest.raises(TypeError, match=expected_message):
        Card(**arguments)  # type: ignore[arg-type]


def test_trump_state_from_normal_source_card() -> None:
    state = TrumpState.from_source_card(Card(rank=Rank.KING, suit=Suit.SPADES))

    assert state.active is True
    assert state.trump_rank is Rank.KING
    assert state.trump_suit is Suit.SPADES
    assert state.joker_color is None


@pytest.mark.parametrize("joker_color", list(JokerColor))
def test_trump_state_from_joker_source_card(joker_color: JokerColor) -> None:
    state = TrumpState.from_source_card(Card(rank=Rank.JOKER, joker_color=joker_color))

    assert state.active is True
    assert state.trump_rank is None
    assert state.trump_suit is None
    assert state.joker_color is joker_color


def test_no_trump_state_is_inactive() -> None:
    assert TrumpState.no_trump() == TrumpState(active=False)


def test_trump_state_is_immutable() -> None:
    state = TrumpState.no_trump()

    with pytest.raises(FrozenInstanceError):
        state.active = True  # type: ignore[misc]


@pytest.mark.parametrize(
    "arguments",
    [
        {"active": True},
        {"active": True, "trump_rank": Rank.JOKER, "trump_suit": Suit.SPADES},
        {"active": True, "trump_rank": Rank.KING},
        {"active": True, "trump_suit": Suit.SPADES},
        {"active": True, "trump_rank": Rank.KING, "joker_color": JokerColor.RED},
        {"active": False, "trump_rank": Rank.KING, "trump_suit": Suit.SPADES},
    ],
)
def test_trump_state_rejects_invalid_selector_combinations(
    arguments: dict[str, object],
) -> None:
    with pytest.raises(ValueError):
        TrumpState(**arguments)  # type: ignore[arg-type]
