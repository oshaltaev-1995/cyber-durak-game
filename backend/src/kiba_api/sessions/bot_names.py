"""Curated synthetic bot identities for process-local bot sessions."""

import random
from collections.abc import Iterable, Sequence

BOT_NAME_POOL: tuple[str, ...] = (
    "Ari",
    "Beni",
    "Cleo",
    "Dara",
    "Eli",
    "Felix",
    "Gabi",
    "Hugo",
    "Iris",
    "Juno",
    "Kira",
    "Leo",
    "Lina",
    "Luna",
    "Max",
    "Mika",
    "Milo",
    "Mira",
    "Nika",
    "Niko",
    "Nora",
    "Olli",
    "Otto",
    "Pia",
    "Ravi",
    "Remi",
    "Riko",
    "Rina",
    "Sami",
    "Sena",
    "Tali",
    "Timo",
    "Una",
    "Vera",
    "Vito",
    "Yara",
    "Yuki",
    "Zara",
    "Zeno",
    "Zoya",
)


def assign_bot_names(
    count: int,
    *,
    human_display_name: str | None,
    rng: random.Random,
    pool: Sequence[str] = BOT_NAME_POOL,
    excluded_display_names: Iterable[str] = (),
) -> tuple[str, ...]:
    """Choose unique names, excluding the human name under normalized comparison."""
    if isinstance(count, bool) or not isinstance(count, int):
        raise TypeError("count must be an int")
    if count < 1:
        raise ValueError("count must be positive")
    if not isinstance(rng, random.Random):
        raise TypeError("rng must be random.Random")

    excluded = {
        _normalized_name(name)
        for name in excluded_display_names
        if isinstance(name, str) and name.strip()
    }
    if human_display_name:
        excluded.add(_normalized_name(human_display_name))
    candidates: list[str] = []
    normalized: set[str] = set()
    for name in pool:
        if not isinstance(name, str) or not name.strip():
            raise ValueError("bot name pool must contain non-empty strings")
        key = _normalized_name(name)
        if key in excluded or key in normalized:
            continue
        normalized.add(key)
        candidates.append(name.strip())
    if len(candidates) < count:
        raise ValueError("bot name pool has too few unique non-colliding names")
    return tuple(rng.sample(candidates, count))


def _normalized_name(name: str) -> str:
    return " ".join(name.split()).casefold()
