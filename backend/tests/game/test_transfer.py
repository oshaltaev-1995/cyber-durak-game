from dataclasses import FrozenInstanceError

import pytest

from kiba_api.game import (
    Card,
    Rank,
    Suit,
    TransferAnalysis,
    TrumpState,
    analyze_transfer,
)

NO_TRUMP = TrumpState.no_trump()


def card(rank: Rank, suit: Suit = Suit.CLUBS) -> Card:
    return Card(rank=rank, suit=suit)


def hearts_trump() -> TrumpState:
    return TrumpState.from_source_card(card(Rank.ACE, Suit.HEARTS))


@pytest.mark.parametrize(
    "selection",
    [
        [card(Rank.KING)],
        [card(Rank.NINE), card(Rank.NINE, Suit.DIAMONDS)],
        [card(Rank.JACK), card(Rank.SIX)],
        [card(Rank.TEN), card(Rank.EIGHT)],
    ],
)
def test_exact_value_transfer_is_legal(selection: list[Card]) -> None:
    analysis = analyze_transfer(selection, 18, NO_TRUMP)

    assert analysis == TransferAnalysis(
        current_target=18,
        selected_value=18,
        next_target=36,
    )
    assert analysis.legal is True


def test_transfer_below_target_is_illegal() -> None:
    analysis = analyze_transfer([card(Rank.NINE), card(Rank.EIGHT)], 18, NO_TRUMP)

    assert analysis == TransferAnalysis(
        current_target=18,
        selected_value=17,
        next_target=None,
    )
    assert analysis.legal is False


def test_transfer_above_target_is_illegal() -> None:
    analysis = analyze_transfer([card(Rank.JACK), card(Rank.SEVEN)], 18, NO_TRUMP)

    assert analysis == TransferAnalysis(
        current_target=18,
        selected_value=19,
        next_target=None,
    )
    assert analysis.legal is False


def test_snowball_chain_uses_each_analysis_next_target() -> None:
    first_transfer = analyze_transfer([card(Rank.KING)], 18, NO_TRUMP)

    assert first_transfer.next_target == 36
    assert first_transfer.next_target is not None

    second_transfer = analyze_transfer(
        [card(Rank.KING), card(Rank.KING, Suit.DIAMONDS)],
        first_transfer.next_target,
        NO_TRUMP,
    )

    assert second_transfer.legal is True
    assert second_transfer.current_target == 36
    assert second_transfer.selected_value == 36
    assert second_transfer.next_target == 72


def test_trump_adjusted_single_card_transfer() -> None:
    analysis = analyze_transfer(
        [card(Rank.NINE, Suit.HEARTS)],
        18,
        hearts_trump(),
    )

    assert analysis.legal is True
    assert analysis.selected_value == 18
    assert analysis.next_target == 36


def test_trump_adjusted_multi_card_transfer() -> None:
    analysis = analyze_transfer(
        [card(Rank.NINE, Suit.HEARTS), card(Rank.KING)],
        36,
        hearts_trump(),
    )

    assert analysis.legal is True
    assert analysis.selected_value == 36
    assert analysis.next_target == 72


def test_trump_card_matches_effective_value_not_base_value() -> None:
    kings_trump = TrumpState.from_source_card(card(Rank.KING, Suit.SPADES))
    trump_king = card(Rank.KING, Suit.HEARTS)

    base_target_analysis = analyze_transfer([trump_king], 18, kings_trump)
    effective_target_analysis = analyze_transfer([trump_king], 36, kings_trump)

    assert base_target_analysis.legal is False
    assert base_target_analysis.selected_value == 36
    assert base_target_analysis.next_target is None
    assert effective_target_analysis.legal is True
    assert effective_target_analysis.next_target == 72


def test_empty_transfer_selection_is_illegal() -> None:
    analysis = analyze_transfer([], 18, NO_TRUMP)

    assert analysis == TransferAnalysis(
        current_target=18,
        selected_value=0,
        next_target=None,
    )
    assert analysis.legal is False


@pytest.mark.parametrize("current_target", [0, -1])
def test_non_positive_transfer_target_is_rejected(current_target: int) -> None:
    with pytest.raises(ValueError, match="must be positive"):
        analyze_transfer([card(Rank.SIX)], current_target, NO_TRUMP)


def test_float_transfer_target_is_rejected() -> None:
    with pytest.raises(TypeError, match="must be an int"):
        analyze_transfer([card(Rank.SIX)], 6.0, NO_TRUMP)  # type: ignore[arg-type]


def test_transfer_analysis_is_immutable() -> None:
    analysis = analyze_transfer([card(Rank.KING)], 18, NO_TRUMP)

    with pytest.raises(FrozenInstanceError):
        analysis.next_target = 72  # type: ignore[misc]


def test_transfer_analysis_does_not_mutate_input() -> None:
    selected = [card(Rank.JACK), card(Rank.SIX)]
    original = selected.copy()

    analyze_transfer(selected, 18, NO_TRUMP)

    assert selected == original
