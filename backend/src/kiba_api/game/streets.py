"""Profile-aware, non-wrapping street analysis shared by attack phases."""

from collections.abc import Iterable
from dataclasses import dataclass

from kiba_api.game.cards import Card, DeckProfile, Rank, street_ranks_for_profile


@dataclass(frozen=True, slots=True)
class RankRun:
    """One server-confirmed contiguous logical-rank run."""

    start: Rank
    end: Rank
    length: int
    ranks: tuple[Rank, ...]


def analyze_rank_run(
    represented_cards: Iterable[Card],
    selected_cards: Iterable[Card],
    profile: DeckProfile = DeckProfile.CLASSIC,
) -> RankRun | None:
    """Find a five-plus linear block containing every selected logical rank."""
    represented = tuple(represented_cards)
    selected = tuple(selected_cards)
    if not selected:
        return None
    selected_ranks = {card.rank for card in selected}
    available_ranks = {card.rank for card in (*represented, *selected)}
    block: list[Rank] = []
    for rank in (*street_ranks_for_profile(profile), None):
        if rank is not None and rank in available_ranks:
            block.append(rank)
            continue
        if len(block) >= 5 and selected_ranks <= set(block):
            ranks = tuple(block)
            return RankRun(ranks[0], ranks[-1], len(ranks), ranks)
        block = []
    return None
