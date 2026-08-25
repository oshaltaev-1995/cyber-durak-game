"""Immutable two-participant game orchestration around the bout rules."""

import random
from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Self

from kiba_api.game.bout import (
    BoutOutcome,
    BoutPhase,
    BoutState,
    Seat,
    finish_bout,
    play_defense,
    play_initial_attack,
    play_throw_in,
    play_transfer,
    take,
)
from kiba_api.game.cards import Card, Rank, Suit, TrumpState
from kiba_api.game.scoring import get_effective_value, is_trump

_STANDARD_36_RANKS = (
    Rank.SIX,
    Rank.SEVEN,
    Rank.EIGHT,
    Rank.NINE,
    Rank.TEN,
    Rank.JACK,
    Rank.QUEEN,
    Rank.KING,
    Rank.ACE,
)


class GamePhase(StrEnum):
    """The constrained lifecycle phase of a two-participant game."""

    READY_FOR_BOUT = "ready_for_bout"
    BOUT_ACTIVE = "bout_active"
    COMPLETE = "complete"


class GameOutcome(StrEnum):
    """A canonical completed-game outcome."""

    WIN = "win"
    DRAW = "draw"


@dataclass(frozen=True, slots=True)
class GameResult:
    """An explicit win or draw result for a completed game."""

    outcome: GameOutcome
    winner: Seat | None

    def __post_init__(self) -> None:
        if not isinstance(self.outcome, GameOutcome):
            raise TypeError("outcome must be a GameOutcome")
        if self.winner is not None and not isinstance(self.winner, Seat):
            raise TypeError("winner must be a Seat or None")
        if self.outcome is GameOutcome.WIN and self.winner is None:
            raise ValueError("a win result requires a winner")
        if self.outcome is GameOutcome.DRAW and self.winner is not None:
            raise ValueError("a draw result cannot have a winner")


class GameErrorCode(StrEnum):
    """Machine-readable causes for rejected game-level transitions."""

    INVALID_DECK = "invalid_deck"
    BOUT_ALREADY_ACTIVE = "bout_already_active"
    NO_ACTIVE_BOUT = "no_active_bout"
    CARD_NOT_OWNED = "card_not_owned"
    TOO_MANY_EQUIVALENT_CARDS = "too_many_equivalent_cards"
    HAND_COUNT_MISMATCH = "hand_count_mismatch"
    GAME_COMPLETE = "game_complete"


class GameActionError(ValueError):
    """A deterministic game-level rejection with a stable error code."""

    def __init__(self, code: GameErrorCode) -> None:
        self.code = code
        super().__init__(code.value)


@dataclass(frozen=True, slots=True)
class GameState:
    """An immutable two-seat game snapshot with real card ownership."""

    seat_one_hand: tuple[Card, ...]
    seat_two_hand: tuple[Card, ...]
    draw_pile: tuple[Card, ...]
    discard_pile: tuple[Card, ...]
    current_attacker: Seat | None
    phase: GamePhase = GamePhase.READY_FOR_BOUT
    active_bout: BoutState | None = None
    bout_starting_attacker: Seat | None = None
    result: GameResult | None = None

    def __post_init__(self) -> None:
        _validate_card_tuple("seat_one_hand", self.seat_one_hand)
        _validate_card_tuple("seat_two_hand", self.seat_two_hand)
        _validate_card_tuple("draw_pile", self.draw_pile)
        _validate_card_tuple("discard_pile", self.discard_pile)
        if self.current_attacker is not None and not isinstance(self.current_attacker, Seat):
            raise TypeError("current_attacker must be a Seat or None")
        if not isinstance(self.phase, GamePhase):
            raise TypeError("phase must be a GamePhase")
        if self.active_bout is not None and not isinstance(self.active_bout, BoutState):
            raise TypeError("active_bout must be a BoutState or None")
        if self.bout_starting_attacker is not None and not isinstance(
            self.bout_starting_attacker,
            Seat,
        ):
            raise TypeError("bout_starting_attacker must be a Seat or None")
        if self.result is not None and not isinstance(self.result, GameResult):
            raise TypeError("result must be a GameResult or None")

        if self.phase is GamePhase.COMPLETE:
            self._validate_complete_result()
            return

        if self.result is not None:
            raise ValueError("a non-complete game cannot have a result")
        if self.current_attacker is None:
            raise ValueError("a non-complete game requires a current attacker")

        if self.phase is GamePhase.READY_FOR_BOUT:
            if self.active_bout is not None or self.bout_starting_attacker is not None:
                raise ValueError("a ready game cannot retain active-bout state")
            if not self.seat_one_hand or not self.seat_two_hand:
                raise ValueError("a ready game cannot have an empty hand")
            return

        if self.active_bout is None or self.bout_starting_attacker is None:
            raise ValueError("an active game requires a bout and its starting attacker")
        if self.current_attacker is not self.bout_starting_attacker:
            raise ValueError("current_attacker must retain the active bout's starting attacker")
        if self.active_bout.phase is BoutPhase.COMPLETE:
            raise ValueError("a completed bout must be resolved before storing GameState")
        _require_hand_count_invariant(self, self.active_bout)

    def _validate_complete_result(self) -> None:
        if self.active_bout is not None or self.bout_starting_attacker is not None:
            raise ValueError("a complete game cannot retain active-bout state")
        if self.current_attacker is not None:
            raise ValueError("a complete game cannot have a next attacker")
        if self.result is None:
            raise ValueError("a complete game requires a result")
        if self.draw_pile:
            raise ValueError("a complete game requires an empty draw pile")

        seat_one_empty = not self.seat_one_hand
        seat_two_empty = not self.seat_two_hand
        if self.result.outcome is GameOutcome.DRAW:
            if not seat_one_empty or not seat_two_empty:
                raise ValueError("a draw requires both hands to be empty")
            return

        expected_winner: Seat | None = None
        if seat_one_empty and not seat_two_empty:
            expected_winner = Seat.ONE
        elif seat_two_empty and not seat_one_empty:
            expected_winner = Seat.TWO
        if self.result.winner is not expected_winner:
            raise ValueError("a win requires exactly the reported winner's hand to be empty")

    @classmethod
    def deal(cls, draw_pile: Iterable[Card], *, initial_attacker: Seat) -> Self:
        """Deal seven cards per seat, round-robin, from an ordered standard deck."""
        if not isinstance(initial_attacker, Seat):
            raise TypeError("initial_attacker must be a Seat")
        ordered_deck = tuple(draw_pile)
        _validate_standard_deck(ordered_deck)
        return cls(
            seat_one_hand=ordered_deck[:14:2],
            seat_two_hand=ordered_deck[1:14:2],
            draw_pile=ordered_deck[14:],
            discard_pile=(),
            current_attacker=initial_attacker,
        )

    def hand(self, seat: Seat) -> tuple[Card, ...]:
        """Return the immutable hand for one seat."""
        if not isinstance(seat, Seat):
            raise TypeError("seat must be a Seat")
        return self.seat_one_hand if seat is Seat.ONE else self.seat_two_hand

    @property
    def current_trump_state(self) -> TrumpState:
        """Return the active bout snapshot or trump derived from the current top card."""
        if self.active_bout is not None:
            return self.active_bout.trump_state
        if self.draw_pile:
            return TrumpState.from_source_card(self.draw_pile[0])
        return TrumpState.no_trump()


def create_36_card_deck() -> tuple[Card, ...]:
    """Create clubs through spades, each ordered from Six through Ace."""
    return tuple(Card(rank=rank, suit=suit) for suit in Suit for rank in _STANDARD_36_RANKS)


def create_new_game(rng: random.Random | None = None) -> GameState:
    """Shuffle and deal a fresh 36-card MVP game under the lowest-trump rule."""
    random_source = rng if rng is not None else random.Random()
    shuffled_deck = list(create_36_card_deck())
    random_source.shuffle(shuffled_deck)
    dealt_state = GameState.deal(shuffled_deck, initial_attacker=Seat.ONE)
    initial_attacker = _determine_initial_attacker(
        dealt_state.seat_one_hand,
        dealt_state.seat_two_hand,
        dealt_state.current_trump_state,
        random_source,
    )
    return replace(dealt_state, current_attacker=initial_attacker)


def _determine_initial_attacker(
    seat_one_hand: Iterable[Card],
    seat_two_hand: Iterable[Card],
    trump_state: TrumpState,
    rng: random.Random,
) -> Seat:
    """Choose the lowest-trump owner, randomizing only a tie or absent trumps."""
    lowest_one = _get_lowest_trump_value(seat_one_hand, trump_state)
    lowest_two = _get_lowest_trump_value(seat_two_hand, trump_state)

    if lowest_one is None:
        return Seat.TWO if lowest_two is not None else rng.choice((Seat.ONE, Seat.TWO))
    if lowest_two is None or lowest_one < lowest_two:
        return Seat.ONE
    if lowest_two < lowest_one:
        return Seat.TWO
    return rng.choice((Seat.ONE, Seat.TWO))


def _get_lowest_trump_value(cards: Iterable[Card], trump_state: TrumpState) -> int | None:
    return min(
        (get_effective_value(card, trump_state) for card in cards if is_trump(card, trump_state)),
        default=None,
    )


def start_game_bout(state: GameState) -> GameState:
    """Start an empty bout using real hand lengths and the exposed top card."""
    if state.phase is GamePhase.COMPLETE:
        raise GameActionError(GameErrorCode.GAME_COMPLETE)
    if state.phase is GamePhase.BOUT_ACTIVE:
        raise GameActionError(GameErrorCode.BOUT_ALREADY_ACTIVE)
    if state.current_attacker is None:
        raise ValueError("a ready game requires a current attacker")

    bout = BoutState.start(
        attacker=state.current_attacker,
        seat_one_hand_count=len(state.seat_one_hand),
        seat_two_hand_count=len(state.seat_two_hand),
        trump_state=state.current_trump_state,
    )
    return replace(
        state,
        phase=GamePhase.BOUT_ACTIVE,
        active_bout=bout,
        bout_starting_attacker=state.current_attacker,
    )


def play_game_initial_attack(
    state: GameState,
    actor: Seat,
    cards: Iterable[Card],
) -> GameState:
    """Validate ownership, then delegate an initial attack to BoutState."""
    return _play_cards(state, actor, cards, play_initial_attack)


def play_game_transfer(
    state: GameState,
    actor: Seat,
    cards: Iterable[Card],
) -> GameState:
    """Validate ownership, then delegate a transfer to BoutState."""
    return _play_cards(state, actor, cards, play_transfer)


def play_game_defense(
    state: GameState,
    actor: Seat,
    cards: Iterable[Card],
) -> GameState:
    """Validate ownership, then delegate a defense to BoutState."""
    return _play_cards(state, actor, cards, play_defense)


def play_game_throw_in(
    state: GameState,
    actor: Seat,
    cards: Iterable[Card],
) -> GameState:
    """Validate ownership, then delegate a post-defense throw-in to BoutState."""
    return _play_cards(state, actor, cards, play_throw_in)


def finish_game_bout(state: GameState, actor: Seat) -> GameState:
    """Finish as bito, discard the table, refill, and return to ready."""
    bout = _require_active_bout(state)
    return _resolve_completed_bout(state, finish_bout(bout, actor))


def take_game_bout(state: GameState, actor: Seat) -> GameState:
    """Take the table, refill, and return to ready without inferring a winner."""
    bout = _require_active_bout(state)
    return _resolve_completed_bout(state, take(bout, actor))


_BoutCardAction = Callable[[BoutState, Seat, tuple[Card, ...]], BoutState]


def _play_cards(
    state: GameState,
    actor: Seat,
    cards: Iterable[Card],
    bout_action: _BoutCardAction,
) -> GameState:
    bout = _require_active_bout(state)
    selected = _coerce_cards(cards)
    current_hand = state.hand(actor)
    _validate_ownership(current_hand, selected)
    updated_bout = bout_action(bout, actor, selected)
    updated_hand = _remove_cards(current_hand, selected)

    changes: dict[str, object] = {"active_bout": updated_bout}
    if actor is Seat.ONE:
        changes["seat_one_hand"] = updated_hand
    else:
        changes["seat_two_hand"] = updated_hand
    updated_state = replace(state, **changes)
    _require_hand_count_invariant(updated_state, updated_bout)
    return updated_state


def _resolve_completed_bout(state: GameState, bout: BoutState) -> GameState:
    if bout.phase is not BoutPhase.COMPLETE or bout.outcome is None or bout.next_attacker is None:
        raise ValueError("BoutState must be complete before game-level resolution")
    if state.bout_starting_attacker is None:
        raise GameActionError(GameErrorCode.NO_ACTIVE_BOUT)

    seat_one_hand = state.seat_one_hand
    seat_two_hand = state.seat_two_hand
    discard_pile = state.discard_pile
    table_cards = bout.table_cards

    if bout.outcome is BoutOutcome.BITO:
        discard_pile += table_cards
    else:
        if bout.taker is Seat.ONE:
            seat_one_hand += table_cards
        elif bout.taker is Seat.TWO:
            seat_two_hand += table_cards
        else:
            raise ValueError("a take outcome requires a taker")

    seat_one_hand, seat_two_hand, draw_pile = _refill_hands(
        seat_one_hand,
        seat_two_hand,
        state.draw_pile,
        state.bout_starting_attacker,
    )
    result = _evaluate_game_result(seat_one_hand, seat_two_hand, draw_pile)
    return GameState(
        seat_one_hand=seat_one_hand,
        seat_two_hand=seat_two_hand,
        draw_pile=draw_pile,
        discard_pile=discard_pile,
        current_attacker=None if result is not None else bout.next_attacker,
        phase=GamePhase.COMPLETE if result is not None else GamePhase.READY_FOR_BOUT,
        result=result,
    )


def _refill_hands(
    seat_one_hand: tuple[Card, ...],
    seat_two_hand: tuple[Card, ...],
    draw_pile: tuple[Card, ...],
    starting_attacker: Seat,
) -> tuple[tuple[Card, ...], tuple[Card, ...], tuple[Card, ...]]:
    hands = {Seat.ONE: seat_one_hand, Seat.TWO: seat_two_hand}
    remaining = draw_pile
    for seat in (starting_attacker, starting_attacker.other):
        needed = max(0, 7 - len(hands[seat]))
        drawn = remaining[:needed]
        hands[seat] += drawn
        remaining = remaining[len(drawn) :]
    return hands[Seat.ONE], hands[Seat.TWO], remaining


def _require_active_bout(state: GameState) -> BoutState:
    if state.phase is GamePhase.COMPLETE:
        raise GameActionError(GameErrorCode.GAME_COMPLETE)
    if state.phase is not GamePhase.BOUT_ACTIVE or state.active_bout is None:
        raise GameActionError(GameErrorCode.NO_ACTIVE_BOUT)
    _require_hand_count_invariant(state, state.active_bout)
    return state.active_bout


def _evaluate_game_result(
    seat_one_hand: tuple[Card, ...],
    seat_two_hand: tuple[Card, ...],
    draw_pile: tuple[Card, ...],
) -> GameResult | None:
    if draw_pile:
        return None
    if not seat_one_hand and not seat_two_hand:
        return GameResult(outcome=GameOutcome.DRAW, winner=None)
    if not seat_one_hand:
        return GameResult(outcome=GameOutcome.WIN, winner=Seat.ONE)
    if not seat_two_hand:
        return GameResult(outcome=GameOutcome.WIN, winner=Seat.TWO)
    return None


def _require_hand_count_invariant(state: GameState, bout: BoutState) -> None:
    if bout.hand_count(Seat.ONE) != len(state.seat_one_hand) or bout.hand_count(Seat.TWO) != len(
        state.seat_two_hand
    ):
        raise GameActionError(GameErrorCode.HAND_COUNT_MISMATCH)


def _coerce_cards(cards: Iterable[Card]) -> tuple[Card, ...]:
    selected = tuple(cards)
    if not all(isinstance(card, Card) for card in selected):
        raise TypeError("cards must contain only Card values")
    return selected


def _validate_ownership(hand: tuple[Card, ...], selected: tuple[Card, ...]) -> None:
    hand_counts = Counter(hand)
    selected_counts = Counter(selected)
    if any(card not in hand_counts for card in selected_counts):
        raise GameActionError(GameErrorCode.CARD_NOT_OWNED)
    if any(count > hand_counts[card] for card, count in selected_counts.items()):
        raise GameActionError(GameErrorCode.TOO_MANY_EQUIVALENT_CARDS)


def _remove_cards(hand: tuple[Card, ...], selected: tuple[Card, ...]) -> tuple[Card, ...]:
    remaining_to_remove = Counter(selected)
    remaining_hand: list[Card] = []
    for card in hand:
        if remaining_to_remove[card]:
            remaining_to_remove[card] -= 1
        else:
            remaining_hand.append(card)
    return tuple(remaining_hand)


def _validate_standard_deck(deck: tuple[Card, ...]) -> None:
    standard_deck = create_36_card_deck()
    if len(deck) != len(standard_deck) or Counter(deck) != Counter(standard_deck):
        raise GameActionError(GameErrorCode.INVALID_DECK)


def _validate_card_tuple(name: str, value: tuple[Card, ...]) -> None:
    if not isinstance(value, tuple) or not all(isinstance(card, Card) for card in value):
        raise TypeError(f"{name} must be a tuple of Card values")
