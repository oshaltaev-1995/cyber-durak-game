"""Pure game-domain primitives for Kiba."""

from kiba_api.game.arithmetic import (
    TableArithmeticSummary,
    cards_have_same_rank,
    find_exact_value_subsets,
    get_arithmetic_mean,
    matches_exact_value,
    summarize_table_arithmetic,
)
from kiba_api.game.cards import Card, JokerColor, Rank, Suit, TrumpState
from kiba_api.game.scoring import (
    get_base_value,
    get_cards_value,
    get_effective_value,
    is_trump,
)

__all__ = [
    "Card",
    "JokerColor",
    "Rank",
    "Suit",
    "TableArithmeticSummary",
    "TrumpState",
    "cards_have_same_rank",
    "find_exact_value_subsets",
    "get_arithmetic_mean",
    "get_base_value",
    "get_cards_value",
    "get_effective_value",
    "is_trump",
    "matches_exact_value",
    "summarize_table_arithmetic",
]
