"""Immutable 2–4 player game orchestration around the bout rules."""

import random
from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from enum import StrEnum
from itertools import combinations
from typing import Protocol, Self, cast

from kiba_api.game.bout import (
    BoutOutcome,
    BoutPhase,
    BoutState,
    Seat,
    finish_bout,
    next_active_clockwise,
    play_defense,
    play_initial_attack,
    play_throw_in,
    play_transfer,
    seats_for_player_count,
    take,
)
from kiba_api.game.cards import Card, Rank, Suit, TrumpState
from kiba_api.game.moves import analyze_rank_run_throw_in, get_throw_in_targets
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


class _SeatChoiceSource(Protocol):
    def choice(self, population: tuple[Seat, ...], /) -> Seat: ...


class GamePhase(StrEnum):
    """The constrained lifecycle phase of a 2–4 player game."""

    READY_FOR_BOUT = "ready_for_bout"
    BOUT_ACTIVE = "bout_active"
    COMPLETE = "complete"


class GameOutcome(StrEnum):
    """The legacy two-player completed-game projection."""

    WIN = "win"
    DRAW = "draw"


@dataclass(frozen=True, slots=True)
class GameResult:
    """A backwards-compatible two-player win or draw result."""

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
    INVALID_PLAYER_COUNT = "invalid_player_count"
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


@dataclass(frozen=True, slots=True, init=False)
class GameState:
    """An immutable tuple-backed game snapshot with stable seat identity."""

    seat_order: tuple[Seat, ...]
    hands: tuple[tuple[Card, ...], ...]
    draw_pile: tuple[Card, ...]
    discard_pile: tuple[Card, ...]
    current_attacker: Seat | None
    phase: GamePhase
    active_bout: BoutState | None
    bout_starting_attacker: Seat | None
    finished_seats: tuple[Seat, ...]
    finish_groups: tuple[tuple[Seat, ...], ...]
    result: GameResult | None

    def __init__(
        self,
        seat_one_hand: tuple[Card, ...] | None = None,
        seat_two_hand: tuple[Card, ...] | None = None,
        draw_pile: tuple[Card, ...] = (),
        discard_pile: tuple[Card, ...] = (),
        current_attacker: Seat | None = None,
        phase: GamePhase = GamePhase.READY_FOR_BOUT,
        active_bout: BoutState | None = None,
        bout_starting_attacker: Seat | None = None,
        result: GameResult | None = None,
        *,
        seat_order: tuple[Seat, ...] | None = None,
        hands: tuple[tuple[Card, ...], ...] | None = None,
        finished_seats: tuple[Seat, ...] = (),
        finish_groups: tuple[tuple[Seat, ...], ...] = (),
    ) -> None:
        if hands is None:
            if seat_one_hand is None or seat_two_hand is None:
                raise TypeError("legacy construction requires both two-player hands")
            hands = (seat_one_hand, seat_two_hand)
        elif seat_one_hand is not None or seat_two_hand is not None:
            raise TypeError("use hands or legacy two-player hand arguments, not both")
        seat_order = seats_for_player_count(len(hands)) if seat_order is None else seat_order

        if phase is GamePhase.COMPLETE and len(seat_order) == 2 and not finish_groups:
            finish_groups, inferred_finished = _legacy_finish_state(hands, result)
            if not finished_seats:
                finished_seats = inferred_finished

        for name, value in (
            ("seat_order", seat_order),
            ("hands", hands),
            ("draw_pile", draw_pile),
            ("discard_pile", discard_pile),
            ("current_attacker", current_attacker),
            ("phase", phase),
            ("active_bout", active_bout),
            ("bout_starting_attacker", bout_starting_attacker),
            ("finished_seats", finished_seats),
            ("finish_groups", finish_groups),
            ("result", result),
        ):
            object.__setattr__(self, name, value)
        self.__post_init__()

    def __post_init__(self) -> None:
        expected_order = seats_for_player_count(len(self.seat_order))
        if self.seat_order != expected_order:
            raise ValueError("seat_order must be the canonical stable ring for 2–4 players")
        if len(self.hands) != len(self.seat_order):
            raise ValueError("hands must align with seat_order")
        for index, hand in enumerate(self.hands):
            _validate_card_tuple(f"hands[{index}]", hand)
        _validate_card_tuple("draw_pile", self.draw_pile)
        _validate_card_tuple("discard_pile", self.discard_pile)
        if self.current_attacker is not None and not isinstance(self.current_attacker, Seat):
            raise TypeError("current_attacker must be a Seat or None")
        if self.current_attacker is not None and self.current_attacker not in self.seat_order:
            raise ValueError("current_attacker must be seated")
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
        self._validate_finish_state()

        if self.phase is GamePhase.COMPLETE:
            self._validate_complete_result()
            return

        if self.result is not None:
            raise ValueError("a non-complete game cannot have a result")
        if self.current_attacker is None:
            raise ValueError("a non-complete game requires a current attacker")
        if self.current_attacker not in self.active_seats:
            raise ValueError("current_attacker must be active")
        if len(self.active_seats) < 2:
            raise ValueError("a non-complete game requires at least two active players")

        if self.phase is GamePhase.READY_FOR_BOUT:
            if self.active_bout is not None or self.bout_starting_attacker is not None:
                raise ValueError("a ready game cannot retain active-bout state")
            if any(not self.hand(seat) for seat in self.active_seats):
                raise ValueError("a ready game cannot have an empty hand")
            return

        if self.active_bout is None or self.bout_starting_attacker is None:
            raise ValueError("an active game requires a bout and its starting attacker")
        if self.current_attacker is not self.bout_starting_attacker:
            raise ValueError("current_attacker must retain the active bout's starting attacker")
        if self.active_bout.phase is BoutPhase.COMPLETE:
            raise ValueError("a completed bout must be resolved before storing GameState")
        if self.active_bout.seat_order != self.seat_order:
            raise ValueError("active bout must preserve the match seat ring")
        if self.active_bout.active_seats != self.active_seats:
            raise ValueError("active bout must preserve the active-seat snapshot")
        _require_hand_count_invariant(self, self.active_bout)

    def _validate_finish_state(self) -> None:
        if not isinstance(self.finished_seats, tuple) or not all(
            isinstance(seat, Seat) for seat in self.finished_seats
        ):
            raise TypeError("finished_seats must be a tuple of Seat values")
        if len(set(self.finished_seats)) != len(self.finished_seats) or any(
            seat not in self.seat_order for seat in self.finished_seats
        ):
            raise ValueError("finished_seats must be unique seated players")
        if any(self.hand(seat) for seat in self.finished_seats):
            raise ValueError("finished players must have empty hands")
        if not isinstance(self.finish_groups, tuple) or not all(
            isinstance(group, tuple) and group for group in self.finish_groups
        ):
            raise TypeError("finish_groups must be a tuple of non-empty seat tuples")
        flattened = tuple(seat for group in self.finish_groups for seat in group)
        if not all(isinstance(seat, Seat) for seat in flattened):
            raise TypeError("finish groups must contain Seat values")
        if len(set(flattened)) != len(flattened) or any(
            seat not in self.seat_order for seat in flattened
        ):
            raise ValueError("finish groups must contain unique seated players")
        if any(seat not in flattened for seat in self.finished_seats):
            raise ValueError("every finished seat must appear in a finish group")

    def _validate_complete_result(self) -> None:
        if self.active_bout is not None or self.bout_starting_attacker is not None:
            raise ValueError("a complete game cannot retain active-bout state")
        if self.current_attacker is not None:
            raise ValueError("a complete game cannot have a next attacker")
        if self.draw_pile:
            raise ValueError("a complete game requires an empty draw pile")
        if len(self.seat_order) == 2:
            if self.result is None:
                raise ValueError("a complete game requires a result")
            seat_one_empty = not self.seat_one_hand
            seat_two_empty = not self.seat_two_hand
            if self.result.outcome is GameOutcome.DRAW:
                if not seat_one_empty or not seat_two_empty:
                    raise ValueError("a draw requires both hands to be empty")
            else:
                expected_winner: Seat | None = None
                if seat_one_empty and not seat_two_empty:
                    expected_winner = Seat.ONE
                elif seat_two_empty and not seat_one_empty:
                    expected_winner = Seat.TWO
                if self.result.winner is not expected_winner:
                    raise ValueError(
                        "a win requires exactly the reported winner's hand to be empty"
                    )

        grouped = tuple(seat for group in self.finish_groups for seat in group)
        if set(grouped) != set(self.seat_order):
            raise ValueError("a complete game requires every seat in finish groups")
        nonempty = tuple(seat for seat in self.seat_order if self.hand(seat))
        if len(nonempty) > 1:
            raise ValueError("a complete game may have at most one terminal player with cards")
        if nonempty and self.finish_groups[-1] != nonempty:
            raise ValueError("the sole remaining player must be the terminal finish group")

        if len(self.seat_order) != 2:
            if self.result is not None:
                raise ValueError("multiplayer completion uses finish_groups, not GameResult")
            return

    @classmethod
    def deal(
        cls,
        draw_pile: Iterable[Card],
        *,
        initial_attacker: Seat,
        player_count: int = 2,
    ) -> Self:
        """Deal seven cards per seat round-robin from an ordered standard deck."""
        try:
            seat_order = seats_for_player_count(player_count)
        except (TypeError, ValueError) as error:
            raise GameActionError(GameErrorCode.INVALID_PLAYER_COUNT) from error
        if not isinstance(initial_attacker, Seat) or initial_attacker not in seat_order:
            raise TypeError("initial_attacker must be a seated Seat")
        ordered_deck = tuple(draw_pile)
        _validate_standard_deck(ordered_deck)
        dealt_count = 7 * player_count
        hands = tuple(ordered_deck[index:dealt_count:player_count] for index in range(player_count))
        return cls(
            seat_order=seat_order,
            hands=hands,
            draw_pile=ordered_deck[dealt_count:],
            discard_pile=(),
            current_attacker=initial_attacker,
        )

    @property
    def seat_one_hand(self) -> tuple[Card, ...]:
        """Legacy public view retained for current two-player callers."""
        return self.hand(Seat.ONE)

    @property
    def seat_two_hand(self) -> tuple[Card, ...]:
        """Legacy public view retained for current two-player callers."""
        return self.hand(Seat.TWO)

    @property
    def active_seats(self) -> tuple[Seat, ...]:
        """Return active seats in their original stable ring order."""
        finished = frozenset(self.finished_seats)
        return tuple(seat for seat in self.seat_order if seat not in finished)

    def hand(self, seat: Seat) -> tuple[Card, ...]:
        """Return the immutable hand for one seated player."""
        if not isinstance(seat, Seat):
            raise TypeError("seat must be a Seat")
        if seat not in self.seat_order:
            raise ValueError("seat is not seated in this match")
        return self.hands[self.seat_order.index(seat)]

    @property
    def current_trump_state(self) -> TrumpState:
        """Return the active bout snapshot or trump derived from the exposed top card."""
        if self.active_bout is not None:
            return self.active_bout.trump_state
        if self.draw_pile:
            return TrumpState.from_source_card(self.draw_pile[0])
        return TrumpState.no_trump()

    @property
    def all_cards(self) -> tuple[Card, ...]:
        """Return every physical card currently owned by the stable domain state."""
        table = self.active_bout.table_cards if self.active_bout is not None else ()
        return (
            tuple(card for hand in self.hands for card in hand)
            + self.draw_pile
            + self.discard_pile
            + table
        )


def create_36_card_deck() -> tuple[Card, ...]:
    """Create clubs through spades, each ordered from Six through Ace."""
    return tuple(Card(rank=rank, suit=suit) for suit in Suit for rank in _STANDARD_36_RANKS)


def create_new_game(rng: random.Random | None = None, *, player_count: int = 2) -> GameState:
    """Shuffle and deal a fresh canonical 2–4 player game."""
    random_source = rng if rng is not None else random.Random()
    shuffled_deck = list(create_36_card_deck())
    random_source.shuffle(shuffled_deck)
    dealt_state = GameState.deal(
        shuffled_deck,
        initial_attacker=Seat.ONE,
        player_count=player_count,
    )
    initial_attacker = _determine_initial_attacker(
        dealt_state.hands,
        dealt_state.seat_order,
        dealt_state.current_trump_state,
        random_source,
    )
    return replace(dealt_state, current_attacker=initial_attacker)


def _determine_initial_attacker(
    hands_or_seat_one: tuple[tuple[Card, ...], ...] | Iterable[Card],
    seats_or_seat_two: tuple[Seat, ...] | Iterable[Card],
    trump_state: TrumpState,
    rng: _SeatChoiceSource,
) -> Seat:
    """Choose the lowest-trump owner across all hands with deterministic RNG injection."""
    possible_seats = tuple(seats_or_seat_two)
    if possible_seats and all(isinstance(value, Seat) for value in possible_seats):
        seat_order = cast(tuple[Seat, ...], possible_seats)
        nested_hands = cast(Iterable[Iterable[Card]], hands_or_seat_one)
        hands = tuple(tuple(hand) for hand in nested_hands)
    else:
        seat_order = seats_for_player_count(2)
        seat_one = cast(Iterable[Card], hands_or_seat_one)
        seat_two = cast(tuple[Card, ...], possible_seats)
        hands = (tuple(seat_one), seat_two)
    lowest_by_seat = {
        seat: _get_lowest_trump_value(hand, trump_state)
        for seat, hand in zip(seat_order, hands, strict=True)
    }
    held_values = tuple(value for value in lowest_by_seat.values() if value is not None)
    if not held_values:
        return rng.choice(seat_order)
    lowest = min(held_values)
    candidates = tuple(seat for seat in seat_order if lowest_by_seat[seat] == lowest)
    return candidates[0] if len(candidates) == 1 else rng.choice(candidates)


def _get_lowest_trump_value(cards: Iterable[Card], trump_state: TrumpState) -> int | None:
    return min(
        (get_effective_value(card, trump_state) for card in cards if is_trump(card, trump_state)),
        default=None,
    )


def start_game_bout(state: GameState) -> GameState:
    """Start a bout from the stable active-seat ring and current hand counts."""
    if state.phase is GamePhase.COMPLETE:
        raise GameActionError(GameErrorCode.GAME_COMPLETE)
    if state.phase is GamePhase.BOUT_ACTIVE:
        raise GameActionError(GameErrorCode.BOUT_ALREADY_ACTIVE)
    if state.current_attacker is None:
        raise ValueError("a ready game requires a current attacker")

    bout = BoutState.start(
        attacker=state.current_attacker,
        seat_order=state.seat_order,
        active_seats=state.active_seats,
        hand_counts=tuple(len(hand) for hand in state.hands),
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
    """Pass one attacking phase, resolving bito only after every phase closes."""
    bout = _require_active_bout(state)
    updated_bout = finish_bout(bout, actor)
    if updated_bout.phase is not BoutPhase.COMPLETE:
        return _advance_unplayable_attacker_phases(replace(state, active_bout=updated_bout))
    return _resolve_completed_bout(state, updated_bout)


def take_game_bout(state: GameState, actor: Seat) -> GameState:
    """Take the table, refill, evaluate finish groups, and advance initiative."""
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
    updated_hands = _replace_hand(state, actor, _remove_cards(current_hand, selected))

    if updated_bout.phase is BoutPhase.COMPLETE:
        return _resolve_completed_bout(state, updated_bout, hands=updated_hands)

    updated_state = replace(state, active_bout=updated_bout, hands=updated_hands)
    _require_hand_count_invariant(updated_state, updated_bout)
    return _advance_unplayable_attacker_phases(updated_state)


def _advance_unplayable_attacker_phases(state: GameState) -> GameState:
    """Skip multiplayer attacker phases that have no possible legal addition.

    The current two-player product deliberately retains its explicit BITO action. With three or
    four active seats, canonical priority must not pause on an attacker who cannot act.
    """
    if len(state.active_seats) <= 2:
        return state

    bout = state.active_bout
    while (
        bout is not None
        and bout.phase is BoutPhase.WAITING_FOR_ATTACKER_DECISION
        and not _has_legal_throw_in(state.hand(bout.attacker), bout)
    ):
        bout = finish_bout(bout, bout.attacker)
        if bout.phase is BoutPhase.COMPLETE:
            return _resolve_completed_bout(state, bout)
        state = replace(state, active_bout=bout)
    return state


def _has_legal_throw_in(hand: tuple[Card, ...], bout: BoutState) -> bool:
    """Return whether any bounded hand selection can legally extend the shared table."""
    max_cards = min(len(hand), bout.max_attack_card_addition)
    if max_cards == 0:
        return False

    anchor_ranks = {card.rank for card in bout.direct_anchor_cards}
    if any(card.rank in anchor_ranks for card in hand):
        return True

    targets = get_throw_in_targets(
        bout.table_cards,
        bout.direct_anchor_cards,
        bout.trump_state,
    )
    exact_targets = set(targets.represented_effective_values)
    if targets.defense_total is not None:
        exact_targets.add(targets.defense_total)
    if targets.table_total is not None:
        exact_targets.add(targets.table_total)
    if targets.arithmetic_mean is not None and targets.arithmetic_mean.denominator == 1:
        exact_targets.add(targets.arithmetic_mean.numerator)

    if exact_targets:
        largest_target = max(exact_targets)
        reachable: list[set[int]] = [set() for _ in range(max_cards + 1)]
        reachable[0].add(0)
        for card in hand:
            value = get_effective_value(card, bout.trump_state)
            for size in range(max_cards, 0, -1):
                for subtotal in tuple(reachable[size - 1]):
                    total = subtotal + value
                    if total in exact_targets:
                        return True
                    if total < largest_target:
                        reachable[size].add(total)

    representative_by_rank: dict[Rank, Card] = {}
    for card in hand:
        if card.rank is not Rank.JOKER:
            representative_by_rank.setdefault(card.rank, card)
    representatives = tuple(representative_by_rank.values())
    for size in range(1, min(max_cards, len(representatives)) + 1):
        if any(
            analyze_rank_run_throw_in(bout.table_cards, selected) is not None
            for selected in combinations(representatives, size)
        ):
            return True
    return False


def _resolve_completed_bout(
    state: GameState,
    bout: BoutState,
    *,
    hands: tuple[tuple[Card, ...], ...] | None = None,
) -> GameState:
    if bout.phase is not BoutPhase.COMPLETE or bout.outcome is None or bout.next_attacker is None:
        raise ValueError("BoutState must be complete before game-level resolution")
    if state.bout_starting_attacker is None:
        raise GameActionError(GameErrorCode.NO_ACTIVE_BOUT)

    resolved_hands = list(state.hands if hands is None else hands)
    discard_pile = state.discard_pile
    table_cards = bout.table_cards

    if bout.outcome is BoutOutcome.BITO:
        discard_pile += table_cards
    else:
        if bout.taker is None:
            raise ValueError("a take outcome requires a taker")
        taker_index = state.seat_order.index(bout.taker)
        resolved_hands[taker_index] += table_cards

    refilled_hands, draw_pile = refill_hands(
        tuple(resolved_hands),
        state.draw_pile,
        state.seat_order,
        bout.refill_order,
    )
    finished_seats, finish_groups, remaining = _evaluate_finish_groups(
        state,
        refilled_hands,
        draw_pile,
    )
    complete = len(remaining) <= 1
    if complete:
        result = _project_two_player_result(state.seat_order, refilled_hands)
        return GameState(
            seat_order=state.seat_order,
            hands=refilled_hands,
            draw_pile=draw_pile,
            discard_pile=discard_pile,
            current_attacker=None,
            phase=GamePhase.COMPLETE,
            finished_seats=finished_seats,
            finish_groups=finish_groups,
            result=result,
        )

    intended_lead = bout.next_attacker
    next_lead = (
        intended_lead
        if intended_lead in remaining
        else next_active_clockwise(state.seat_order, remaining, intended_lead)
    )
    return GameState(
        seat_order=state.seat_order,
        hands=refilled_hands,
        draw_pile=draw_pile,
        discard_pile=discard_pile,
        current_attacker=next_lead,
        phase=GamePhase.READY_FOR_BOUT,
        finished_seats=finished_seats,
        finish_groups=finish_groups,
    )


def allocate_balanced_refill_quotas(
    hand_counts: dict[Seat, int],
    available: int,
    refill_order: tuple[Seat, ...],
) -> dict[Seat, int]:
    """Allocate an insufficient pile by smallest hand, then immutable refill order."""
    if isinstance(available, bool) or not isinstance(available, int):
        raise TypeError("available must be an int")
    if available < 0:
        raise ValueError("available must not be negative")
    if set(hand_counts) != set(refill_order) or len(set(refill_order)) != len(refill_order):
        raise ValueError("refill_order must contain each eligible seat exactly once")
    if any(isinstance(count, bool) or not isinstance(count, int) for count in hand_counts.values()):
        raise TypeError("hand counts must be ints")
    if any(count < 0 for count in hand_counts.values()):
        raise ValueError("hand counts must not be negative")

    quotas = {seat: 0 for seat in refill_order}
    projected = dict(hand_counts)
    remaining = min(available, sum(max(0, 7 - count) for count in projected.values()))
    priority = {seat: index for index, seat in enumerate(refill_order)}
    while remaining:
        eligible = tuple(seat for seat in refill_order if projected[seat] < 7)
        if not eligible:
            break
        smallest = min(projected[seat] for seat in eligible)
        chosen = min(
            (seat for seat in eligible if projected[seat] == smallest),
            key=priority.__getitem__,
        )
        quotas[chosen] += 1
        projected[chosen] += 1
        remaining -= 1
    return quotas


def refill_hands(
    hands: tuple[tuple[Card, ...], ...],
    draw_pile: tuple[Card, ...],
    seat_order: tuple[Seat, ...],
    refill_order: tuple[Seat, ...],
) -> tuple[tuple[tuple[Card, ...], ...], tuple[Card, ...]]:
    """Refill all bout participants in the immutable bout-start order."""
    hand_by_seat = {
        seat: hand for seat, hand in zip(seat_order, hands, strict=True) if seat in refill_order
    }
    needs = {seat: max(0, 7 - len(hand)) for seat, hand in hand_by_seat.items()}
    total_needed = sum(needs.values())
    quotas = (
        needs
        if len(draw_pile) >= total_needed
        else allocate_balanced_refill_quotas(
            {seat: len(hand) for seat, hand in hand_by_seat.items()},
            len(draw_pile),
            refill_order,
        )
    )

    remaining = draw_pile
    updated = list(hands)
    for seat in refill_order:
        drawn = remaining[: quotas[seat]]
        index = seat_order.index(seat)
        updated[index] += drawn
        remaining = remaining[len(drawn) :]
    return tuple(updated), remaining


def _evaluate_finish_groups(
    state: GameState,
    hands: tuple[tuple[Card, ...], ...],
    draw_pile: tuple[Card, ...],
) -> tuple[tuple[Seat, ...], tuple[tuple[Seat, ...], ...], tuple[Seat, ...]]:
    finished = state.finished_seats
    groups = state.finish_groups
    if draw_pile:
        return finished, groups, state.active_seats

    new_finishers = tuple(
        seat for seat in state.active_seats if not hands[state.seat_order.index(seat)]
    )
    if new_finishers:
        finished = (*finished, *new_finishers)
        groups = (*groups, new_finishers)
    remaining = tuple(seat for seat in state.seat_order if seat not in finished)
    if len(remaining) == 1:
        groups = (*groups, remaining)
    return finished, groups, remaining


def _project_two_player_result(
    seat_order: tuple[Seat, ...],
    hands: tuple[tuple[Card, ...], ...],
) -> GameResult | None:
    if len(seat_order) != 2:
        return None
    empty = tuple(seat for seat, hand in zip(seat_order, hands, strict=True) if not hand)
    if len(empty) == 2:
        return GameResult(GameOutcome.DRAW, None)
    if len(empty) == 1:
        return GameResult(GameOutcome.WIN, empty[0])
    raise ValueError("a completed two-player game requires at least one empty hand")


def _legacy_finish_state(
    hands: tuple[tuple[Card, ...], ...],
    result: GameResult | None,
) -> tuple[tuple[tuple[Seat, ...], ...], tuple[Seat, ...]]:
    if result is None:
        return (), ()
    if result.outcome is GameOutcome.DRAW:
        if not hands[0] and not hands[1]:
            return ((Seat.ONE, Seat.TWO),), (Seat.ONE, Seat.TWO)
        return (), ()
    winner = result.winner
    if winner is None:
        raise ValueError("a win result requires a winner")
    loser = winner.other
    winner_index = 0 if winner is Seat.ONE else 1
    loser_index = 1 - winner_index
    if hands[winner_index] or not hands[loser_index]:
        return (), ()
    return ((winner,), (loser,)), (winner,)


def _require_active_bout(state: GameState) -> BoutState:
    if state.phase is GamePhase.COMPLETE:
        raise GameActionError(GameErrorCode.GAME_COMPLETE)
    if state.phase is not GamePhase.BOUT_ACTIVE or state.active_bout is None:
        raise GameActionError(GameErrorCode.NO_ACTIVE_BOUT)
    _require_hand_count_invariant(state, state.active_bout)
    return state.active_bout


def _require_hand_count_invariant(state: GameState, bout: BoutState) -> None:
    if bout.hand_counts != tuple(len(hand) for hand in state.hands):
        raise GameActionError(GameErrorCode.HAND_COUNT_MISMATCH)


def _replace_hand(
    state: GameState,
    seat: Seat,
    hand: tuple[Card, ...],
) -> tuple[tuple[Card, ...], ...]:
    hands = list(state.hands)
    hands[state.seat_order.index(seat)] = hand
    return tuple(hands)


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
