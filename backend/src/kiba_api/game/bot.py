"""Deterministic baseline bot policy composed from authoritative game transitions."""

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from enum import StrEnum
from itertools import combinations

from kiba_api.game.bout import BoutActionError, BoutPhase, Seat
from kiba_api.game.cards import Card, JokerColor, Rank, Suit, TrumpState
from kiba_api.game.game import (
    GameActionError,
    GamePhase,
    GameState,
    finish_game_bout,
    play_game_defense,
    play_game_initial_attack,
    play_game_throw_in,
    play_game_transfer,
    start_game_bout,
    take_game_bout,
)
from kiba_api.game.scoring import get_cards_value, is_trump


class BotActionType(StrEnum):
    """One explicit action the baseline bot can request."""

    START_BOUT = "start_bout"
    INITIAL_ATTACK = "initial_attack"
    TRANSFER = "transfer"
    DEFEND = "defend"
    THROW_IN = "throw_in"
    TAKE = "take"
    BITO = "bito"


_CARD_ACTION_TYPES = frozenset(
    {
        BotActionType.INITIAL_ATTACK,
        BotActionType.TRANSFER,
        BotActionType.DEFEND,
        BotActionType.THROW_IN,
    }
)


@dataclass(frozen=True, slots=True)
class BotAction:
    """An immutable bot intent without UI or transport concerns."""

    action_type: BotActionType
    cards: tuple[Card, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.action_type, BotActionType):
            raise TypeError("action_type must be a BotActionType")
        if not isinstance(self.cards, tuple) or not all(
            isinstance(card, Card) for card in self.cards
        ):
            raise TypeError("cards must be a tuple of Card values")
        if self.action_type in _CARD_ACTION_TYPES:
            if not self.cards:
                raise ValueError("a card action requires at least one card")
        elif self.cards:
            raise ValueError("a non-card action cannot contain cards")


class BotErrorCode(StrEnum):
    """Machine-readable causes for an unavailable bot decision."""

    NOT_BOT_TURN = "not_bot_turn"
    GAME_COMPLETE = "game_complete"
    NO_LEGAL_ACTION = "no_legal_action"


class BotActionError(ValueError):
    """A deterministic bot-policy rejection carrying a stable error code."""

    def __init__(self, code: BotErrorCode) -> None:
        self.code = code
        super().__init__(code.value)


def choose_bot_action(state: GameState, bot_seat: Seat) -> BotAction:
    """Choose exactly one deterministic baseline action for the acting bot seat."""
    if not isinstance(state, GameState):
        raise TypeError("state must be a GameState")
    if not isinstance(bot_seat, Seat):
        raise TypeError("bot_seat must be a Seat")
    if state.phase is GamePhase.COMPLETE:
        raise BotActionError(BotErrorCode.GAME_COMPLETE)

    if state.phase is GamePhase.READY_FOR_BOUT:
        _require_bot_turn(bot_seat, state.current_attacker)
        return BotAction(BotActionType.START_BOUT)

    bout = state.active_bout
    if bout is None:
        raise ValueError("an active game requires an active bout")

    if bout.phase is BoutPhase.WAITING_FOR_INITIAL_ATTACK:
        _require_bot_turn(bot_seat, bout.attacker)
        return _choose_initial_attack(state, bot_seat)
    if bout.phase is BoutPhase.WAITING_FOR_DEFENDER_RESPONSE:
        _require_bot_turn(bot_seat, bout.defender)
        return _choose_defender_response(state, bot_seat)
    if bout.phase is BoutPhase.WAITING_FOR_ATTACKER_DECISION:
        _require_bot_turn(bot_seat, bout.attacker)
        return _choose_throw_in_or_bito(state, bot_seat)

    raise BotActionError(BotErrorCode.GAME_COMPLETE)


def play_bot_turn(state: GameState, bot_seat: Seat) -> GameState:
    """Choose and apply exactly one action through the authoritative game API."""
    action = choose_bot_action(state, bot_seat)

    if action.action_type is BotActionType.START_BOUT:
        return start_game_bout(state)
    if action.action_type is BotActionType.INITIAL_ATTACK:
        return play_game_initial_attack(state, bot_seat, action.cards)
    if action.action_type is BotActionType.TRANSFER:
        return play_game_transfer(state, bot_seat, action.cards)
    if action.action_type is BotActionType.DEFEND:
        return play_game_defense(state, bot_seat, action.cards)
    if action.action_type is BotActionType.THROW_IN:
        return play_game_throw_in(state, bot_seat, action.cards)
    if action.action_type is BotActionType.TAKE:
        return take_game_bout(state, bot_seat)
    return finish_game_bout(state, bot_seat)


def _choose_initial_attack(state: GameState, bot_seat: Seat) -> BotAction:
    trump_state = state.current_trump_state
    candidates = ((card,) for card in state.hand(bot_seat))
    for candidate in sorted(candidates, key=lambda cards: _selection_key(cards, trump_state)):
        if _is_legal_card_action(play_game_initial_attack, state, bot_seat, candidate):
            return BotAction(BotActionType.INITIAL_ATTACK, candidate)
    raise BotActionError(BotErrorCode.NO_LEGAL_ACTION)


def _choose_defender_response(state: GameState, bot_seat: Seat) -> BotAction:
    bout = state.active_bout
    if bout is None or bout.active_packet is None:
        raise ValueError("a defender response requires an active packet")

    trump_state = bout.trump_state
    subsets = _best_subsets_by_total(
        state.hand(bot_seat),
        trump_state,
        prefer_non_trumps=True,
    )
    defense_candidates = (
        cards for total, cards in subsets.items() if total > bout.active_packet.attack_value
    )
    for candidate in sorted(
        defense_candidates,
        key=lambda cards: _selection_key(cards, trump_state, prefer_non_trumps=True),
    ):
        if _is_legal_card_action(play_game_defense, state, bot_seat, candidate):
            return BotAction(BotActionType.DEFEND, candidate)

    transfer_target = bout.transfer_target
    if transfer_target is not None:
        for candidate in _packet_transfer_candidates(state, bot_seat, subsets):
            if _is_legal_card_action(play_game_transfer, state, bot_seat, candidate):
                return BotAction(BotActionType.TRANSFER, candidate)

    return BotAction(BotActionType.TAKE)


def _choose_throw_in_or_bito(state: GameState, bot_seat: Seat) -> BotAction:
    bout = state.active_bout
    if bout is None:
        raise ValueError("a throw-in decision requires an active bout")

    trump_state = bout.trump_state
    subsets = _best_subsets_by_total(state.hand(bot_seat), trump_state)
    candidates = {*subsets.values(), *_rank_run_candidates(state, bot_seat)}
    for candidate in sorted(candidates, key=lambda cards: _selection_key(cards, trump_state)):
        if not candidate:
            continue
        if _is_legal_card_action(play_game_throw_in, state, bot_seat, candidate):
            return BotAction(BotActionType.THROW_IN, candidate)

    return BotAction(BotActionType.BITO)


def _packet_transfer_candidates(
    state: GameState,
    bot_seat: Seat,
    subsets: dict[int, tuple[Card, ...]],
) -> tuple[tuple[Card, ...], ...]:
    """Return deterministic exact and possible same-rank-extension selections."""
    bout = state.active_bout
    if bout is None or bout.active_packet is None or bout.transfer_target is None:
        return ()

    candidates: set[tuple[Card, ...]] = set()
    exact = subsets.get(bout.transfer_target)
    if exact:
        candidates.add(exact)

    attack_cards = bout.active_packet.attack_cards
    if attack_cards and all(card.rank is attack_cards[0].rank for card in attack_cards):
        matching = tuple(
            sorted(
                (card for card in state.hand(bot_seat) if card.rank is attack_cards[0].rank),
                key=_card_order_key,
            )
        )
        for size in range(1, len(matching) + 1):
            candidates.update(combinations(matching, size))

    return tuple(sorted(candidates, key=lambda cards: _selection_key(cards, bout.trump_state)))


def _rank_run_candidates(state: GameState, bot_seat: Seat) -> tuple[tuple[Card, ...], ...]:
    """Build a bounded rank-focused set for authoritative throw-in validation."""
    bout = state.active_bout
    if bout is None:
        return ()

    cards_by_rank: dict[Rank, list[Card]] = {}
    for card in state.hand(bot_seat):
        if card.rank is not Rank.JOKER:
            cards_by_rank.setdefault(card.rank, []).append(card)
    cheapest_by_rank = {
        rank: min(
            cards,
            key=lambda card: (
                get_cards_value((card,), bout.trump_state),
                _card_order_key(card),
            ),
        )
        for rank, cards in cards_by_rank.items()
    }
    distinct_cards = tuple(cheapest_by_rank.values())
    max_size = min(len(distinct_cards), bout.attack_card_limit - bout.total_attack_card_count)
    candidates: list[tuple[Card, ...]] = []
    for size in range(1, max_size + 1):
        candidates.extend(combinations(distinct_cards, size))
    return tuple(candidates)


_GameCardAction = Callable[[GameState, Seat, Iterable[Card]], GameState]


def _is_legal_card_action(
    action: _GameCardAction,
    state: GameState,
    actor: Seat,
    cards: tuple[Card, ...],
) -> bool:
    try:
        action(state, actor, cards)
    except (BoutActionError, GameActionError):
        return False
    return True


def _best_subsets_by_total(
    cards: Iterable[Card],
    trump_state: TrumpState,
    *,
    prefer_non_trumps: bool = False,
) -> dict[int, tuple[Card, ...]]:
    """Retain one deterministic preferred subset for every reachable total."""
    ordered_cards = tuple(sorted(cards, key=_card_order_key))
    best: dict[int, tuple[Card, ...]] = {0: ()}

    for card in ordered_cards:
        card_value = get_cards_value((card,), trump_state)
        for total, subset in tuple(best.items()):
            candidate = (*subset, card)
            candidate_total = total + card_value
            existing = best.get(candidate_total)
            if existing is None or _selection_key(
                candidate,
                trump_state,
                prefer_non_trumps=prefer_non_trumps,
            ) < _selection_key(
                existing,
                trump_state,
                prefer_non_trumps=prefer_non_trumps,
            ):
                best[candidate_total] = candidate

    return best


def _selection_key(
    cards: tuple[Card, ...],
    trump_state: TrumpState,
    *,
    prefer_non_trumps: bool = False,
) -> tuple[int, int, int, tuple[tuple[int, int, int], ...]]:
    trump_count = sum(is_trump(card, trump_state) for card in cards) if prefer_non_trumps else 0
    return (
        get_cards_value(cards, trump_state),
        len(cards),
        trump_count,
        tuple(_card_order_key(card) for card in cards),
    )


_RANK_ORDER = {rank: index for index, rank in enumerate(Rank)}
_SUIT_ORDER = {suit: index for index, suit in enumerate(Suit)}
_JOKER_COLOR_ORDER = {color: index for index, color in enumerate(JokerColor)}


def _card_order_key(card: Card) -> tuple[int, int, int]:
    suit_order = len(_SUIT_ORDER) if card.suit is None else _SUIT_ORDER[card.suit]
    joker_order = (
        len(_JOKER_COLOR_ORDER)
        if card.joker_color is None
        else _JOKER_COLOR_ORDER[card.joker_color]
    )
    return _RANK_ORDER[card.rank], suit_order, joker_order


def _require_bot_turn(bot_seat: Seat, acting_seat: Seat | None) -> None:
    if bot_seat is not acting_seat:
        raise BotActionError(BotErrorCode.NOT_BOT_TURN)
