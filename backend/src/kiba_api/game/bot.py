"""Seat-aware baseline bot policy composed from authoritative game transitions."""

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from enum import StrEnum
from itertools import combinations

from kiba_api.game.bout import BoutActionError, BoutPhase, Seat
from kiba_api.game.cards import Card, DeckConfig, JokerColor, Rank, Suit, TrumpState
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
from kiba_api.game.streets import analyze_rank_run


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


@dataclass(frozen=True, slots=True)
class BotBoutContext:
    """Public bout facts visible to any participant at the table."""

    phase: BoutPhase
    attacker: Seat
    defender: Seat
    lead_attacker: Seat
    active_seats: tuple[Seat, ...]
    closed_attackers: tuple[Seat, ...]
    trump_state: TrumpState
    table_cards: tuple[Card, ...]
    direct_anchor_cards: tuple[Card, ...]
    active_attack_cards: tuple[Card, ...]
    active_attack_value: int | None
    transfer_target: int | None
    transfer_open: bool
    attack_card_limit: int
    total_attack_card_count: int
    max_attack_card_addition: int


@dataclass(frozen=True, slots=True)
class BotDecisionContext:
    """Participant-safe observation consumed by strategy code.

    It deliberately contains no other exact hand, future draw order, account identity,
    reconnect credential, or random-generator state.
    """

    bot_seat: Seat
    deck_config: DeckConfig
    phase: GamePhase
    seat_order: tuple[Seat, ...]
    active_seats: tuple[Seat, ...]
    finished_seats: tuple[Seat, ...]
    current_attacker: Seat | None
    own_hand: tuple[Card, ...]
    public_hand_counts: tuple[tuple[Seat, int], ...]
    draw_pile_count: int
    exposed_top_card: Card | None
    trump_state: TrumpState
    bout: BotBoutContext | None


def build_bot_context(state: GameState, bot_seat: Seat) -> BotDecisionContext:
    """Project an authoritative state into one bot's legitimate observation."""
    if not isinstance(state, GameState):
        raise TypeError("state must be a GameState")
    if not isinstance(bot_seat, Seat):
        raise TypeError("bot_seat must be a Seat")
    if bot_seat not in state.seat_order:
        raise ValueError("bot_seat must be seated")

    bout = state.active_bout
    bout_context = None
    if bout is not None:
        packet = bout.active_packet
        bout_context = BotBoutContext(
            phase=bout.phase,
            attacker=bout.attacker,
            defender=bout.defender,
            lead_attacker=bout.lead_attacker,
            active_seats=bout.active_seats,
            closed_attackers=bout.closed_attackers,
            trump_state=bout.trump_state,
            table_cards=bout.table_cards,
            direct_anchor_cards=bout.direct_anchor_cards,
            active_attack_cards=packet.attack_cards if packet is not None else (),
            active_attack_value=packet.attack_value if packet is not None else None,
            transfer_target=bout.transfer_target,
            transfer_open=bout.transfer_open,
            attack_card_limit=bout.attack_card_limit,
            total_attack_card_count=bout.total_attack_card_count,
            max_attack_card_addition=bout.max_attack_card_addition,
        )
    return BotDecisionContext(
        bot_seat=bot_seat,
        deck_config=state.deck_config,
        phase=state.phase,
        seat_order=state.seat_order,
        active_seats=state.active_seats,
        finished_seats=state.finished_seats,
        current_attacker=state.current_attacker,
        own_hand=state.hand(bot_seat),
        public_hand_counts=tuple((seat, len(state.hand(seat))) for seat in state.seat_order),
        draw_pile_count=len(state.draw_pile),
        exposed_top_card=state.draw_pile[0] if state.draw_pile else None,
        trump_state=state.current_trump_state,
        bout=bout_context,
    )


def choose_bot_action(state: GameState, bot_seat: Seat) -> BotAction:
    """Choose one action; strategy sees context while the engine validates it."""
    context = build_bot_context(state, bot_seat)

    def is_legal(action: BotAction) -> bool:
        try:
            _apply_bot_action(state, bot_seat, action)
        except (BoutActionError, GameActionError):
            return False
        return True

    return choose_bot_action_from_context(context, is_legal)


def choose_bot_action_from_context(
    context: BotDecisionContext,
    is_legal: Callable[[BotAction], bool],
) -> BotAction:
    """Run deterministic strategy against a sanitized observation and legality oracle."""
    if not isinstance(context, BotDecisionContext):
        raise TypeError("context must be a BotDecisionContext")
    if context.phase is GamePhase.COMPLETE:
        raise BotActionError(BotErrorCode.GAME_COMPLETE)

    if context.phase is GamePhase.READY_FOR_BOUT:
        _require_bot_turn(context.bot_seat, context.current_attacker)
        return BotAction(BotActionType.START_BOUT)

    bout = context.bout
    if bout is None:
        raise ValueError("an active game requires an active bout")

    if bout.phase is BoutPhase.WAITING_FOR_INITIAL_ATTACK:
        _require_bot_turn(context.bot_seat, bout.attacker)
        return _choose_initial_attack(context, is_legal)
    if bout.phase is BoutPhase.WAITING_FOR_DEFENDER_RESPONSE:
        _require_bot_turn(context.bot_seat, bout.defender)
        return _choose_defender_response(context, is_legal)
    if bout.phase is BoutPhase.WAITING_FOR_ATTACKER_DECISION:
        _require_bot_turn(context.bot_seat, bout.attacker)
        return _choose_throw_in_or_bito(context, is_legal)

    raise BotActionError(BotErrorCode.GAME_COMPLETE)


def play_bot_turn(state: GameState, bot_seat: Seat) -> GameState:
    """Choose and apply exactly one action through the authoritative game API."""
    action = choose_bot_action(state, bot_seat)

    return _apply_bot_action(state, bot_seat, action)


def _apply_bot_action(state: GameState, bot_seat: Seat, action: BotAction) -> GameState:
    """Submit a chosen intent to the authoritative immutable game API."""
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


def _choose_initial_attack(
    context: BotDecisionContext,
    is_legal: Callable[[BotAction], bool],
) -> BotAction:
    bout = context.bout
    if bout is None:
        raise ValueError("an initial attack requires an active bout")
    candidates = {
        *_bounded_initial_candidates(context.own_hand),
        *_initial_street_candidates(
            context.own_hand,
            context.deck_config,
            bout.max_attack_card_addition,
        ),
    }
    ordered = sorted(
        candidates,
        key=lambda cards: _selection_key(cards, context.trump_state),
    )
    for candidate in ordered:
        if analyze_rank_run((), candidate, context.deck_config.profile) is not None and not any(
            is_trump(card, context.trump_state) for card in candidate
        ):
            action = BotAction(BotActionType.INITIAL_ATTACK, candidate)
            if is_legal(action):
                return action
    if len(context.seat_order) > 2:
        for candidate in ordered:
            if len(candidate) == 1:
                continue
            if any(is_trump(card, context.trump_state) for card in candidate):
                continue
            if get_cards_value(candidate, context.trump_state) > 36:
                continue
            action = BotAction(BotActionType.INITIAL_ATTACK, candidate)
            if is_legal(action):
                return action
    for candidate in ordered:
        action = BotAction(BotActionType.INITIAL_ATTACK, candidate)
        if is_legal(action):
            return action
    raise BotActionError(BotErrorCode.NO_LEGAL_ACTION)


def _choose_defender_response(
    context: BotDecisionContext,
    is_legal: Callable[[BotAction], bool],
) -> BotAction:
    bout = context.bout
    if bout is None or bout.active_attack_value is None:
        raise ValueError("a defender response requires an active packet")

    trump_state = bout.trump_state
    subsets = _best_subsets_by_total(
        context.own_hand,
        trump_state,
        prefer_non_trumps=True,
    )
    transfer_target = bout.transfer_target
    if len(context.seat_order) > 2 and transfer_target is not None:
        for candidate in _packet_transfer_candidates(context, subsets):
            action = BotAction(BotActionType.TRANSFER, candidate)
            if is_legal(action):
                return action

    defense_candidates = (
        cards for total, cards in subsets.items() if total > bout.active_attack_value
    )
    for candidate in sorted(
        defense_candidates,
        key=lambda cards: (
            get_cards_value(cards, trump_state) - bout.active_attack_value,
            sum(is_trump(card, trump_state) for card in cards),
            len(cards),
            tuple(_card_order_key(card) for card in cards),
        ),
    ):
        action = BotAction(BotActionType.DEFEND, candidate)
        if is_legal(action):
            return action

    if transfer_target is not None:
        for candidate in _packet_transfer_candidates(context, subsets):
            action = BotAction(BotActionType.TRANSFER, candidate)
            if is_legal(action):
                return action

    return BotAction(BotActionType.TAKE)


def _choose_throw_in_or_bito(
    context: BotDecisionContext,
    is_legal: Callable[[BotAction], bool],
) -> BotAction:
    bout = context.bout
    if bout is None:
        raise ValueError("a throw-in decision requires an active bout")

    trump_state = bout.trump_state
    subsets = _best_subsets_by_total(context.own_hand, trump_state)
    candidates = {*subsets.values(), *_rank_run_candidates(context)}
    for candidate in sorted(candidates, key=lambda cards: _selection_key(cards, trump_state)):
        if not candidate:
            continue
        action = BotAction(BotActionType.THROW_IN, candidate)
        if is_legal(action):
            # Preserve scarce high cards and trumps instead of mechanically exhausting
            # every legal addition. Passing permanently closes this bot's phase.
            if len(context.seat_order) > 2 and (
                any(is_trump(card, trump_state) for card in candidate)
                or (len(candidate) == 1 and get_cards_value(candidate, trump_state) >= 18)
            ):
                break
            return action

    return BotAction(BotActionType.BITO)


def _packet_transfer_candidates(
    context: BotDecisionContext,
    subsets: dict[int, tuple[Card, ...]],
) -> tuple[tuple[Card, ...], ...]:
    """Return deterministic exact and possible same-rank-extension selections."""
    bout = context.bout
    if bout is None or not bout.active_attack_cards or bout.transfer_target is None:
        return ()

    candidates: set[tuple[Card, ...]] = set()
    exact = subsets.get(bout.transfer_target)
    if exact:
        candidates.add(exact)

    attack_cards = bout.active_attack_cards
    if attack_cards and all(card.rank is attack_cards[0].rank for card in attack_cards):
        matching = tuple(
            sorted(
                (card for card in context.own_hand if card.rank is attack_cards[0].rank),
                key=_card_order_key,
            )
        )
        for size in range(1, len(matching) + 1):
            candidates.update(combinations(matching, size))

    return tuple(sorted(candidates, key=lambda cards: _selection_key(cards, bout.trump_state)))


def _rank_run_candidates(context: BotDecisionContext) -> tuple[tuple[Card, ...], ...]:
    """Build a bounded rank-focused set for authoritative throw-in validation."""
    bout = context.bout
    if bout is None:
        return ()

    cards_by_rank: dict[Rank, list[Card]] = {}
    for card in context.own_hand:
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
    max_size = min(len(distinct_cards), bout.max_attack_card_addition)
    candidates: set[tuple[Card, ...]] = set()
    for card in sorted(context.own_hand, key=_card_order_key):
        candidate = (card,)
        if analyze_rank_run(bout.table_cards, candidate, context.deck_config.profile) is not None:
            candidates.add(candidate)
    for size in range(1, min(max_size, 5) + 1):
        for candidate in combinations(distinct_cards, size):
            if (
                analyze_rank_run(
                    bout.table_cards,
                    candidate,
                    context.deck_config.profile,
                )
                is not None
            ):
                candidates.add(candidate)
    return tuple(sorted(candidates, key=lambda cards: tuple(_card_order_key(c) for c in cards)))


def _initial_street_candidates(
    cards: tuple[Card, ...],
    deck_config: DeckConfig,
    capacity: int,
) -> tuple[tuple[Card, ...], ...]:
    """Return bounded shared-helper-validated initial streets, including duplicates."""
    ordered = tuple(sorted(cards, key=_card_order_key))
    candidates: set[tuple[Card, ...]] = set()
    card_by_rank: dict[Rank, Card] = {}
    for card in ordered:
        card_by_rank.setdefault(card.rank, card)
    distinct_cards = tuple(card_by_rank.values())
    max_distinct = min(len(distinct_cards), capacity)
    for size in range(5, max_distinct + 1):
        for candidate in combinations(distinct_cards, size):
            if analyze_rank_run((), candidate, deck_config.profile) is None:
                continue
            candidates.add(candidate)
            ranks = {card.rank for card in candidate}
            with_duplicates = tuple(card for card in ordered if card.rank in ranks)
            if len(with_duplicates) <= capacity:
                candidates.add(with_duplicates)
    return tuple(candidates)


def _bounded_initial_candidates(cards: tuple[Card, ...]) -> tuple[tuple[Card, ...], ...]:
    """Enumerate representative initial structures without power-set growth."""
    ordered = tuple(sorted(cards, key=_card_order_key))
    candidates: set[tuple[Card, ...]] = {(card,) for card in ordered}
    max_size = min(4, len(ordered))
    for size in range(2, max_size + 1):
        candidates.update(combinations(ordered, size))
    return tuple(candidates)


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
) -> tuple[int, int, int, tuple[tuple[int, int, int, int], ...]]:
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


def _card_order_key(card: Card) -> tuple[int, int, int, int]:
    suit_order = len(_SUIT_ORDER) if card.suit is None else _SUIT_ORDER[card.suit]
    joker_order = (
        len(_JOKER_COLOR_ORDER)
        if card.joker_color is None
        else _JOKER_COLOR_ORDER[card.joker_color]
    )
    return _RANK_ORDER[card.rank], suit_order, joker_order, card.deck_copy


def _require_bot_turn(bot_seat: Seat, acting_seat: Seat | None) -> None:
    if bot_seat is not acting_seat:
        raise BotActionError(BotErrorCode.NOT_BOT_TURN)
