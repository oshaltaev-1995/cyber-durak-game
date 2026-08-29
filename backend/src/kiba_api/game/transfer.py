"""Pure numeric transfer and snowball-target rules."""

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from kiba_api.game.arithmetic import find_exact_value_subsets, matches_exact_value
from kiba_api.game.cards import Card, TrumpState
from kiba_api.game.scoring import get_cards_value


class PacketTransferMode(StrEnum):
    """The packet rule that accepted a transfer selection."""

    EXACT = "exact"
    SAME_RANK_EXTENDED = "same_rank_extended"


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


@dataclass(frozen=True, slots=True)
class PacketTransferAnalysis:
    """Packet-aware transfer result preserving the ordinary exact primitive."""

    current_target: int
    selected_value: int
    next_target: int | None
    mode: PacketTransferMode | None

    @property
    def legal(self) -> bool:
        """Return whether an exact or same-rank-extended transfer applies."""
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


def analyze_packet_transfer(
    selected_cards: Iterable[Card],
    current_attack_cards: Iterable[Card],
    current_target: int,
    trump_state: TrumpState,
) -> PacketTransferAnalysis:
    """Analyze a transfer in the context of one unresolved attack packet.

    Ordinary exact transfers remain authoritative. A larger selection is accepted
    only when the packet and every selected card share one rank and a non-empty
    subset of the selection exactly satisfies the current target.
    """
    selected = tuple(selected_cards)
    attack_cards = tuple(current_attack_cards)
    exact = analyze_transfer(selected, current_target, trump_state)
    if exact.legal:
        return PacketTransferAnalysis(
            current_target=current_target,
            selected_value=exact.selected_value,
            next_target=exact.next_target,
            mode=PacketTransferMode.EXACT,
        )

    packet_rank = attack_cards[0].rank if attack_cards else None
    rank_homogeneous = packet_rank is not None and all(
        card.rank is packet_rank for card in attack_cards
    )
    selected_matches_rank = bool(selected) and all(card.rank is packet_rank for card in selected)
    has_exact_core = (
        rank_homogeneous
        and selected_matches_rank
        and bool(
            find_exact_value_subsets(
                selected,
                current_target,
                trump_state,
                first_only=True,
            )
        )
    )
    if rank_homogeneous and selected_matches_rank and has_exact_core:
        return PacketTransferAnalysis(
            current_target=current_target,
            selected_value=exact.selected_value,
            next_target=current_target + exact.selected_value,
            mode=PacketTransferMode.SAME_RANK_EXTENDED,
        )

    return PacketTransferAnalysis(
        current_target=current_target,
        selected_value=exact.selected_value,
        next_target=None,
        mode=None,
    )
