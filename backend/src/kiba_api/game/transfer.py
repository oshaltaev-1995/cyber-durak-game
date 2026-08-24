"""Pure numeric transfer and snowball-target rules."""

from collections.abc import Iterable
from dataclasses import dataclass

from kiba_api.game.arithmetic import matches_exact_value
from kiba_api.game.cards import Card, TrumpState
from kiba_api.game.scoring import get_cards_value


@dataclass(frozen=True, slots=True)
class TransferAnalysis:
    """Numeric transfer result without bout, player, or card-count constraints."""

    current_target: int
    selected_value: int
    next_target: int | None

    @property
    def legal(self) -> bool:
        """Return whether the selection exactly satisfies the transfer target."""
        return self.next_target is not None


def analyze_transfer(
    selected_cards: Iterable[Card],
    current_target: int,
    trump_state: TrumpState,
) -> TransferAnalysis:
    """Analyze an exact-value transfer and derive its next snowball target."""
    if isinstance(current_target, bool) or not isinstance(current_target, int):
        raise TypeError("current_target must be an int")
    if current_target <= 0:
        raise ValueError("current_target must be positive")

    selected = tuple(selected_cards)
    selected_value = get_cards_value(selected, trump_state)
    legal = bool(selected) and matches_exact_value(selected, current_target, trump_state)
    next_target = current_target + selected_value if legal else None

    return TransferAnalysis(
        current_target=current_target,
        selected_value=selected_value,
        next_target=next_target,
    )
