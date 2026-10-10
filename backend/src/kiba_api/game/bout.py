"""Immutable 2–4 participant orchestration for one Kiba bout."""

from collections.abc import Iterable
from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Self

from kiba_api.game.attack import analyze_initial_attack
from kiba_api.game.cards import Card, DeckProfile, TrumpState
from kiba_api.game.moves import analyze_defense, analyze_throw_in, is_legal_defense
from kiba_api.game.scoring import get_cards_value
from kiba_api.game.transfer import analyze_packet_transfer


class Seat(StrEnum):
    """One stable position in the canonical clockwise seat ring."""

    ONE = "one"
    TWO = "two"
    THREE = "three"
    FOUR = "four"

    @property
    def other(self) -> "Seat":
        """Return the legacy two-player opponent.

        Multiplayer traversal must use :func:`next_active_clockwise`; this property remains only
        for existing two-player application adapters and tests.
        """
        if self is Seat.ONE:
            return Seat.TWO
        if self is Seat.TWO:
            return Seat.ONE
        raise ValueError("other is defined only for the legacy two-player seats")


SUPPORTED_SEATS = (Seat.ONE, Seat.TWO, Seat.THREE, Seat.FOUR)


def seats_for_player_count(player_count: int) -> tuple[Seat, ...]:
    """Return the fixed canonical ring for a supported player count."""
    if isinstance(player_count, bool) or not isinstance(player_count, int):
        raise TypeError("player_count must be an int")
    if not 2 <= player_count <= 4:
        raise ValueError("player_count must be between 2 and 4")
    return SUPPORTED_SEATS[:player_count]


def clockwise_after(seat_order: tuple[Seat, ...], seat: Seat) -> tuple[Seat, ...]:
    """Return every other seated position clockwise, with stable wraparound."""
    _validate_seat_order(seat_order)
    if seat not in seat_order:
        raise ValueError("seat must belong to seat_order")
    start = seat_order.index(seat)
    return tuple(
        seat_order[(start + offset) % len(seat_order)] for offset in range(1, len(seat_order))
    )


def next_active_clockwise(
    seat_order: tuple[Seat, ...],
    active_seats: Iterable[Seat],
    seat: Seat,
) -> Seat:
    """Return the next active seat clockwise, skipping finished positions."""
    active = frozenset(active_seats)
    if seat not in seat_order:
        raise ValueError("seat must belong to seat_order")
    if not active.issubset(seat_order):
        raise ValueError("active seats must belong to seat_order")
    for candidate in clockwise_after(seat_order, seat):
        if candidate in active:
            return candidate
    raise ValueError("no other active seat exists")


def _ordered_active_seats(
    seat_order: tuple[Seat, ...], active_seats: Iterable[Seat]
) -> tuple[Seat, ...]:
    active = frozenset(active_seats)
    if not active.issubset(seat_order):
        raise ValueError("active seats must belong to seat_order")
    return tuple(seat for seat in seat_order if seat in active)


def _attacker_order(
    seat_order: tuple[Seat, ...],
    active_seats: tuple[Seat, ...],
    lead_attacker: Seat,
    defender: Seat,
) -> tuple[Seat, ...]:
    return (
        lead_attacker,
        *(
            seat
            for seat in clockwise_after(seat_order, lead_attacker)
            if seat in active_seats and seat is not defender
        ),
    )


def _refill_order(
    seat_order: tuple[Seat, ...],
    active_seats: tuple[Seat, ...],
    bout_starter: Seat,
    initial_defender: Seat,
) -> tuple[Seat, ...]:
    return (
        bout_starter,
        *(
            seat
            for seat in clockwise_after(seat_order, bout_starter)
            if seat in active_seats and seat is not initial_defender
        ),
        initial_defender,
    )


class BoutPhase(StrEnum):
    """The constrained action phase of one bout snapshot."""

    WAITING_FOR_INITIAL_ATTACK = "waiting_for_initial_attack"
    WAITING_FOR_DEFENDER_RESPONSE = "waiting_for_defender_response"
    WAITING_FOR_ATTACKER_DECISION = "waiting_for_attacker_decision"
    COMPLETE = "complete"


class BoutOutcome(StrEnum):
    """A terminal resolution without applying game-level card movement."""

    BITO = "bito"
    TAKE = "take"


class BoutErrorCode(StrEnum):
    """Machine-readable causes for rejected bout actions."""

    WRONG_PHASE = "wrong_phase"
    WRONG_ACTOR = "wrong_actor"
    NOT_ENOUGH_CARDS = "not_enough_cards"
    ILLEGAL_INITIAL_ATTACK = "illegal_initial_attack"
    ILLEGAL_DEFENSE = "illegal_defense"
    REDUNDANT_DEFENSE = "redundant_defense"
    ILLEGAL_TRANSFER = "illegal_transfer"
    TRANSFER_CLOSED = "transfer_closed"
    ATTACK_CARD_LIMIT_EXCEEDED = "attack_card_limit_exceeded"
    ILLEGAL_THROW_IN = "illegal_throw_in"
    BOUT_COMPLETE = "bout_complete"


class BoutActionError(ValueError):
    """A deterministic rejection carrying a stable domain error code."""

    def __init__(self, code: BoutErrorCode) -> None:
        self.code = code
        super().__init__(code.value)


@dataclass(frozen=True, slots=True)
class AttackPacket:
    """One unresolved or covered attack requirement within a bout."""

    attack_cards: tuple[Card, ...]
    attack_value: int
    defense_cards: tuple[Card, ...] | None = None
    defense_value: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.attack_cards, tuple) or not all(
            isinstance(card, Card) for card in self.attack_cards
        ):
            raise TypeError("attack_cards must be a tuple of Card values")
        if not self.attack_cards:
            raise ValueError("an attack packet must contain attack cards")
        if isinstance(self.attack_value, bool) or not isinstance(self.attack_value, int):
            raise TypeError("attack_value must be an int")
        if self.attack_value <= 0:
            raise ValueError("attack_value must be positive")

        if self.defense_cards is None:
            if self.defense_value is not None:
                raise ValueError("an open packet cannot have a defense value")
            return

        if not isinstance(self.defense_cards, tuple) or not all(
            isinstance(card, Card) for card in self.defense_cards
        ):
            raise TypeError("defense_cards must be a tuple of Card values")
        if not self.defense_cards:
            raise ValueError("a closed packet must contain defense cards")
        if isinstance(self.defense_value, bool) or not isinstance(self.defense_value, int):
            raise TypeError("defense_value must be an int for a closed packet")
        if self.defense_value <= self.attack_value:
            raise ValueError("a closed packet's defense value must exceed its attack value")

    @property
    def closed(self) -> bool:
        """Return whether a successful defense has closed this packet."""
        return self.defense_cards is not None


@dataclass(frozen=True, slots=True, init=False)
class BoutState:
    """A complete immutable snapshot of one 2–4 player bout."""

    seat_order: tuple[Seat, ...]
    active_seats: tuple[Seat, ...]
    hand_counts: tuple[int, ...]
    bout_starter: Seat
    initial_defender: Seat
    refill_order: tuple[Seat, ...]
    lead_attacker: Seat
    attacker: Seat
    defender: Seat
    attacker_order: tuple[Seat, ...]
    closed_attackers: tuple[Seat, ...]
    trump_state: TrumpState
    deck_profile: DeckProfile
    phase: BoutPhase
    packets: tuple[AttackPacket, ...]
    transfer_open: bool
    attack_card_limit: int
    total_attack_card_count: int
    outcome: BoutOutcome | None
    next_attacker: Seat | None
    taker: Seat | None

    def __init__(
        self,
        *,
        attacker: Seat,
        trump_state: TrumpState,
        deck_profile: DeckProfile = DeckProfile.CLASSIC,
        phase: BoutPhase,
        packets: tuple[AttackPacket, ...],
        transfer_open: bool,
        attack_card_limit: int,
        total_attack_card_count: int,
        defender: Seat | None = None,
        seat_one_hand_count: int | None = None,
        seat_two_hand_count: int | None = None,
        seat_order: tuple[Seat, ...] | None = None,
        active_seats: tuple[Seat, ...] | None = None,
        hand_counts: tuple[int, ...] | None = None,
        bout_starter: Seat | None = None,
        initial_defender: Seat | None = None,
        refill_order: tuple[Seat, ...] | None = None,
        lead_attacker: Seat | None = None,
        attacker_order: tuple[Seat, ...] | None = None,
        closed_attackers: tuple[Seat, ...] = (),
        outcome: BoutOutcome | None = None,
        next_attacker: Seat | None = None,
        taker: Seat | None = None,
    ) -> None:
        if hand_counts is None:
            if seat_one_hand_count is None or seat_two_hand_count is None:
                raise TypeError("legacy construction requires both two-player hand counts")
            seat_order = seats_for_player_count(2) if seat_order is None else seat_order
            hand_counts = (seat_one_hand_count, seat_two_hand_count)
        elif seat_one_hand_count is not None or seat_two_hand_count is not None:
            raise TypeError("use hand_counts or legacy hand-count arguments, not both")

        seat_order = seats_for_player_count(len(hand_counts)) if seat_order is None else seat_order
        active_seats = seat_order if active_seats is None else active_seats
        active_seats = _ordered_active_seats(seat_order, active_seats)
        if defender is None:
            defender = next_active_clockwise(seat_order, active_seats, attacker)
        bout_starter = attacker if bout_starter is None else bout_starter
        initial_defender = defender if initial_defender is None else initial_defender
        lead_attacker = attacker if lead_attacker is None else lead_attacker
        refill_order = (
            _refill_order(seat_order, active_seats, bout_starter, initial_defender)
            if refill_order is None
            else refill_order
        )
        attacker_order = (
            _attacker_order(seat_order, active_seats, lead_attacker, defender)
            if attacker_order is None
            else attacker_order
        )

        for name, value in (
            ("seat_order", seat_order),
            ("active_seats", active_seats),
            ("hand_counts", hand_counts),
            ("bout_starter", bout_starter),
            ("initial_defender", initial_defender),
            ("refill_order", refill_order),
            ("lead_attacker", lead_attacker),
            ("attacker", attacker),
            ("defender", defender),
            ("attacker_order", attacker_order),
            ("closed_attackers", closed_attackers),
            ("trump_state", trump_state),
            ("deck_profile", deck_profile),
            ("phase", phase),
            ("packets", packets),
            ("transfer_open", transfer_open),
            ("attack_card_limit", attack_card_limit),
            ("total_attack_card_count", total_attack_card_count),
            ("outcome", outcome),
            ("next_attacker", next_attacker),
            ("taker", taker),
        ):
            object.__setattr__(self, name, value)
        self.__post_init__()

    def __post_init__(self) -> None:
        _validate_seat_order(self.seat_order)
        if len(self.hand_counts) != len(self.seat_order):
            raise ValueError("hand_counts must align with seat_order")
        for count in self.hand_counts:
            _validate_hand_count("hand_count", count)
        if self.active_seats != _ordered_active_seats(self.seat_order, self.active_seats):
            raise ValueError("active_seats must retain stable seat order")
        if not 2 <= len(self.active_seats) <= len(self.seat_order):
            raise ValueError("an active bout requires at least two active seats")

        role_seats = (
            self.bout_starter,
            self.initial_defender,
            self.lead_attacker,
            self.attacker,
            self.defender,
        )
        if not all(isinstance(seat, Seat) for seat in role_seats):
            raise TypeError("bout roles must be Seat values")
        if any(seat not in self.active_seats for seat in role_seats):
            raise ValueError("bout roles must belong to active seats")
        if self.lead_attacker is self.defender or self.attacker is self.defender:
            raise ValueError("attacker roles and defender must be different seats")
        expected_refill = _refill_order(
            self.seat_order,
            self.active_seats,
            self.bout_starter,
            self.initial_defender,
        )
        if self.refill_order != expected_refill:
            raise ValueError("refill_order must be the immutable bout-start snapshot")
        expected_attackers = _attacker_order(
            self.seat_order,
            self.active_seats,
            self.lead_attacker,
            self.defender,
        )
        if self.attacker_order != expected_attackers:
            raise ValueError("attacker_order must follow the current lead and defender")
        if len(set(self.closed_attackers)) != len(self.closed_attackers) or any(
            seat not in self.attacker_order for seat in self.closed_attackers
        ):
            raise ValueError("closed_attackers must be unique members of attacker_order")

        if not isinstance(self.trump_state, TrumpState):
            raise TypeError("trump_state must be a TrumpState")
        if not isinstance(self.deck_profile, DeckProfile):
            raise TypeError("deck_profile must be a DeckProfile")
        if not isinstance(self.phase, BoutPhase):
            raise TypeError("phase must be a BoutPhase")
        if not isinstance(self.transfer_open, bool):
            raise TypeError("transfer_open must be a bool")
        if not isinstance(self.packets, tuple) or not all(
            isinstance(packet, AttackPacket) for packet in self.packets
        ):
            raise TypeError("packets must be a tuple of AttackPacket values")
        if self.outcome is not None and not isinstance(self.outcome, BoutOutcome):
            raise TypeError("outcome must be a BoutOutcome or None")
        if self.next_attacker is not None and not isinstance(self.next_attacker, Seat):
            raise TypeError("next_attacker must be a Seat or None")
        if self.taker is not None and not isinstance(self.taker, Seat):
            raise TypeError("taker must be a Seat or None")
        _validate_non_negative_int("attack_card_limit", self.attack_card_limit)
        _validate_non_negative_int("total_attack_card_count", self.total_attack_card_count)
        if self.total_attack_card_count != sum(len(packet.attack_cards) for packet in self.packets):
            raise ValueError("total_attack_card_count must match packet attack cards")
        if self.total_attack_card_count > self.attack_card_limit:
            raise ValueError("total attack cards cannot exceed the current attack-card limit")
        if self.transfer_open and any(packet.closed for packet in self.packets):
            raise ValueError("transfer cannot remain open after a successful defense")

        self._validate_packets()
        self._validate_phase_roles()
        self._validate_terminal_metadata()

    @classmethod
    def start(
        cls,
        *,
        attacker: Seat,
        trump_state: TrumpState,
        deck_profile: DeckProfile = DeckProfile.CLASSIC,
        seat_one_hand_count: int | None = None,
        seat_two_hand_count: int | None = None,
        seat_order: tuple[Seat, ...] | None = None,
        active_seats: tuple[Seat, ...] | None = None,
        hand_counts: tuple[int, ...] | None = None,
    ) -> Self:
        """Create an empty bout with fixed seats, roles, and refill order."""
        if hand_counts is None:
            if seat_one_hand_count is None or seat_two_hand_count is None:
                raise TypeError("legacy construction requires both two-player hand counts")
            hand_counts = (seat_one_hand_count, seat_two_hand_count)
        elif seat_one_hand_count is not None or seat_two_hand_count is not None:
            raise TypeError("use hand_counts or legacy hand-count arguments, not both")
        seat_order = seats_for_player_count(len(hand_counts)) if seat_order is None else seat_order
        active_seats = seat_order if active_seats is None else active_seats
        active_seats = _ordered_active_seats(seat_order, active_seats)
        defender = next_active_clockwise(seat_order, active_seats, attacker)
        defender_count = hand_counts[seat_order.index(defender)]
        return cls(
            seat_order=seat_order,
            active_seats=active_seats,
            hand_counts=hand_counts,
            bout_starter=attacker,
            initial_defender=defender,
            refill_order=_refill_order(seat_order, active_seats, attacker, defender),
            lead_attacker=attacker,
            attacker=attacker,
            defender=defender,
            attacker_order=_attacker_order(seat_order, active_seats, attacker, defender),
            closed_attackers=(),
            trump_state=trump_state,
            deck_profile=deck_profile,
            phase=BoutPhase.WAITING_FOR_INITIAL_ATTACK,
            packets=(),
            transfer_open=True,
            attack_card_limit=defender_count,
            total_attack_card_count=0,
        )

    @property
    def seat_one_hand_count(self) -> int:
        """Legacy two-player view of Seat ONE's count."""
        return self.hand_count(Seat.ONE)

    @property
    def seat_two_hand_count(self) -> int:
        """Legacy two-player view of Seat TWO's count."""
        return self.hand_count(Seat.TWO)

    def hand_count(self, seat: Seat) -> int:
        """Return a seated player's numeric remaining-card count."""
        if not isinstance(seat, Seat):
            raise TypeError("seat must be a Seat")
        if seat not in self.seat_order:
            raise ValueError("seat is not seated in this match")
        return self.hand_counts[self.seat_order.index(seat)]

    @property
    def active_packet(self) -> AttackPacket | None:
        """Return the single unresolved packet, if one exists."""
        if not self.packets or self.packets[-1].closed:
            return None
        return self.packets[-1]

    @property
    def direct_anchor_cards(self) -> tuple[Card, ...]:
        """Return only the defense cards that most recently closed a packet."""
        for packet in reversed(self.packets):
            if packet.defense_cards is not None:
                return packet.defense_cards
        return ()

    @property
    def table_cards(self) -> tuple[Card, ...]:
        """Return every physical card in chronological packet order."""
        return tuple(
            card
            for packet in self.packets
            for card_group in (packet.attack_cards, packet.defense_cards or ())
            for card in card_group
        )

    @property
    def transfer_target(self) -> int | None:
        """Return the active snowball target only while transfer remains available."""
        packet = self.active_packet
        if not self.transfer_open or packet is None:
            return None
        return packet.attack_value

    @property
    def remaining_bout_capacity(self) -> int:
        """Return unused attacking-card capacity in the current defender context."""
        return self.attack_card_limit - self.total_attack_card_count

    @property
    def max_attack_card_addition(self) -> int:
        """Return how many attacking cards may be added by one action right now."""
        return min(self.remaining_bout_capacity, self.hand_count(self.defender))

    def _validate_packets(self) -> None:
        for packet in self.packets:
            if get_cards_value(packet.attack_cards, self.trump_state) != packet.attack_value:
                raise ValueError("packet attack value must match its effective card total")
            if (
                packet.defense_cards is not None
                and get_cards_value(packet.defense_cards, self.trump_state) != packet.defense_value
            ):
                raise ValueError("packet defense value must match its effective card total")
            if packet.defense_cards is not None and not is_legal_defense(
                packet.defense_cards,
                packet.attack_value,
                self.trump_state,
            ):
                raise ValueError("packet defense cards must be sufficient and irredundant")

        if any(not packet.closed for packet in self.packets[:-1]):
            raise ValueError("only the latest packet may be unresolved")

        if self.phase is BoutPhase.WAITING_FOR_INITIAL_ATTACK:
            if self.packets:
                raise ValueError("the initial-attack phase cannot contain packets")
        elif self.phase is BoutPhase.WAITING_FOR_DEFENDER_RESPONSE:
            if self.active_packet is None:
                raise ValueError("the defender-response phase requires an active packet")
        elif self.phase is BoutPhase.WAITING_FOR_ATTACKER_DECISION:
            if not self.packets or not self.packets[-1].closed:
                raise ValueError("the attacker-decision phase requires a closed packet")
            if self.transfer_open:
                raise ValueError("transfer must be closed after a successful defense")
            if self.hand_count(self.defender) == 0:
                raise ValueError("a zero-card defender must finish the bout as bito")

    def _validate_phase_roles(self) -> None:
        if self.phase is BoutPhase.WAITING_FOR_INITIAL_ATTACK:
            if (
                self.attacker is not self.bout_starter
                or self.lead_attacker is not self.bout_starter
            ):
                raise ValueError("only the bout starter owns the initial attack")
        elif self.phase is BoutPhase.WAITING_FOR_ATTACKER_DECISION:
            remaining = tuple(
                seat for seat in self.attacker_order if seat not in self.closed_attackers
            )
            if not remaining or self.attacker is not remaining[0]:
                raise ValueError("current attacker must be the first open attacking phase")

    def _validate_terminal_metadata(self) -> None:
        if self.phase is not BoutPhase.COMPLETE:
            if any(value is not None for value in (self.outcome, self.next_attacker, self.taker)):
                raise ValueError("non-terminal states cannot have terminal metadata")
            return

        if self.outcome is None or self.next_attacker is None:
            raise ValueError("a complete bout requires outcome and next_attacker")
        if self.transfer_open:
            raise ValueError("a complete bout cannot leave transfer open")
        if self.outcome is BoutOutcome.BITO:
            if not self.packets or self.active_packet is not None or self.taker is not None:
                raise ValueError("bito requires a closed packet and no taker")
            if self.next_attacker is not self.defender:
                raise ValueError("the defender must lead next after bito")
        elif self.outcome is BoutOutcome.TAKE:
            if self.active_packet is None or self.taker is not self.defender:
                raise ValueError("take requires the active defender as taker")
            expected = next_active_clockwise(self.seat_order, self.active_seats, self.defender)
            if self.next_attacker is not expected:
                raise ValueError("the next active seat after the defender must lead after take")


def play_initial_attack(
    state: BoutState,
    actor: Seat,
    cards: Iterable[Card],
) -> BoutState:
    """Play the lead attacker's atomic first packet of a bout."""
    _require_phase(state, BoutPhase.WAITING_FOR_INITIAL_ATTACK)
    _require_actor(actor, state.attacker)
    selected = tuple(cards)
    _require_cards_available(state, actor, len(selected))
    _require_attack_limit(state, len(selected))
    if not analyze_initial_attack(selected, state.trump_state, state.deck_profile).legal:
        raise BoutActionError(BoutErrorCode.ILLEGAL_INITIAL_ATTACK)

    packet = AttackPacket(
        attack_cards=selected,
        attack_value=get_cards_value(selected, state.trump_state),
    )
    return replace(
        state,
        hand_counts=_spend_hand_count(state, actor, len(selected)),
        packets=(packet,),
        phase=BoutPhase.WAITING_FOR_DEFENDER_RESPONSE,
        total_attack_card_count=len(selected),
    )


def play_transfer(
    state: BoutState,
    actor: Seat,
    cards: Iterable[Card],
) -> BoutState:
    """Extend the unresolved packet and move defense clockwise."""
    _require_not_complete(state)
    if not state.transfer_open:
        raise BoutActionError(BoutErrorCode.TRANSFER_CLOSED)
    _require_phase(state, BoutPhase.WAITING_FOR_DEFENDER_RESPONSE)
    _require_actor(actor, state.defender)
    selected = tuple(cards)
    _require_cards_available(state, actor, len(selected))

    packet = _get_active_packet(state)
    analysis = analyze_packet_transfer(
        selected,
        packet.attack_cards,
        packet.attack_value,
        state.trump_state,
    )
    if not analysis.legal or analysis.next_target is None:
        raise BoutActionError(BoutErrorCode.ILLEGAL_TRANSFER)

    total_attack_card_count = state.total_attack_card_count + len(selected)
    new_defender = next_active_clockwise(state.seat_order, state.active_seats, state.defender)
    new_lead = actor if new_defender is state.lead_attacker else state.lead_attacker
    new_limit = state.hand_count(new_defender)
    if total_attack_card_count > new_limit:
        raise BoutActionError(BoutErrorCode.ATTACK_CARD_LIMIT_EXCEEDED)

    extended_packet = replace(
        packet,
        attack_cards=packet.attack_cards + selected,
        attack_value=analysis.next_target,
    )
    return replace(
        state,
        hand_counts=_spend_hand_count(state, actor, len(selected)),
        packets=(*state.packets[:-1], extended_packet),
        lead_attacker=new_lead,
        attacker=actor,
        defender=new_defender,
        attacker_order=_attacker_order(
            state.seat_order,
            state.active_seats,
            new_lead,
            new_defender,
        ),
        attack_card_limit=new_limit,
        total_attack_card_count=total_attack_card_count,
    )


def play_defense(
    state: BoutState,
    actor: Seat,
    cards: Iterable[Card],
) -> BoutState:
    """Close only the current packet with a strictly higher irredundant total."""
    _require_phase(state, BoutPhase.WAITING_FOR_DEFENDER_RESPONSE)
    _require_actor(actor, state.defender)
    selected = tuple(cards)
    _require_cards_available(state, actor, len(selected))
    packet = _get_active_packet(state)
    analysis = analyze_defense(selected, packet.attack_value, state.trump_state)
    if not analysis.sufficient:
        raise BoutActionError(BoutErrorCode.ILLEGAL_DEFENSE)
    if not analysis.irredundant:
        raise BoutActionError(BoutErrorCode.REDUNDANT_DEFENSE)

    closed_packet = replace(
        packet,
        defense_cards=selected,
        defense_value=analysis.selected_value,
    )
    defender_is_empty = state.hand_count(actor) == len(selected)
    first_successful_defense = state.transfer_open
    phase_order = (
        _attacker_order(
            state.seat_order,
            state.active_seats,
            state.lead_attacker,
            state.defender,
        )
        if first_successful_defense
        else state.attacker_order
    )
    next_phase_attacker = phase_order[0] if first_successful_defense else state.attacker
    return replace(
        state,
        hand_counts=_spend_hand_count(state, actor, len(selected)),
        packets=(*state.packets[:-1], closed_packet),
        attacker=(state.attacker if defender_is_empty else next_phase_attacker),
        attacker_order=phase_order,
        closed_attackers=(() if first_successful_defense else state.closed_attackers),
        phase=(
            BoutPhase.COMPLETE if defender_is_empty else BoutPhase.WAITING_FOR_ATTACKER_DECISION
        ),
        transfer_open=False,
        outcome=(BoutOutcome.BITO if defender_is_empty else None),
        next_attacker=(state.defender if defender_is_empty else None),
    )


def play_throw_in(
    state: BoutState,
    actor: Seat,
    cards: Iterable[Card],
) -> BoutState:
    """Create a new atomic post-defense packet in the current attacker's phase."""
    _require_phase(state, BoutPhase.WAITING_FOR_ATTACKER_DECISION)
    _require_actor(actor, state.attacker)
    selected = tuple(cards)
    _require_cards_available(state, actor, len(selected))
    _require_attack_limit(state, len(selected))
    analysis = analyze_throw_in(
        selected,
        state.table_cards,
        state.direct_anchor_cards,
        state.trump_state,
        state.deck_profile,
    )
    if not analysis.legal:
        raise BoutActionError(BoutErrorCode.ILLEGAL_THROW_IN)

    packet = AttackPacket(
        attack_cards=selected,
        attack_value=analysis.selected_value,
    )
    return replace(
        state,
        hand_counts=_spend_hand_count(state, actor, len(selected)),
        packets=(*state.packets, packet),
        phase=BoutPhase.WAITING_FOR_DEFENDER_RESPONSE,
        total_attack_card_count=state.total_attack_card_count + len(selected),
    )


def pass_attacker_phase(state: BoutState, actor: Seat) -> BoutState:
    """Close one attacking phase, advancing once or completing ordinary bito."""
    _require_phase(state, BoutPhase.WAITING_FOR_ATTACKER_DECISION)
    _require_actor(actor, state.attacker)
    closed = (*state.closed_attackers, actor)
    remaining = tuple(seat for seat in state.attacker_order if seat not in closed)
    if remaining:
        return replace(state, attacker=remaining[0], closed_attackers=closed)
    return replace(
        state,
        closed_attackers=closed,
        phase=BoutPhase.COMPLETE,
        transfer_open=False,
        outcome=BoutOutcome.BITO,
        next_attacker=state.defender,
    )


def finish_bout(state: BoutState, actor: Seat) -> BoutState:
    """Legacy name for passing the current non-cycling attacking phase."""
    return pass_attacker_phase(state, actor)


def take(state: BoutState, actor: Seat) -> BoutState:
    """End the bout immediately with the active defender taking its table."""
    _require_phase(state, BoutPhase.WAITING_FOR_DEFENDER_RESPONSE)
    _require_actor(actor, state.defender)
    return replace(
        state,
        phase=BoutPhase.COMPLETE,
        transfer_open=False,
        outcome=BoutOutcome.TAKE,
        next_attacker=next_active_clockwise(state.seat_order, state.active_seats, state.defender),
        taker=state.defender,
    )


def _spend_hand_count(state: BoutState, actor: Seat, card_count: int) -> tuple[int, ...]:
    hand_counts = list(state.hand_counts)
    hand_counts[state.seat_order.index(actor)] -= card_count
    return tuple(hand_counts)


def _require_not_complete(state: BoutState) -> None:
    if state.phase is BoutPhase.COMPLETE:
        raise BoutActionError(BoutErrorCode.BOUT_COMPLETE)


def _require_phase(state: BoutState, required: BoutPhase) -> None:
    _require_not_complete(state)
    if state.phase is not required:
        raise BoutActionError(BoutErrorCode.WRONG_PHASE)


def _require_actor(actor: Seat, required: Seat) -> None:
    if actor is not required:
        raise BoutActionError(BoutErrorCode.WRONG_ACTOR)


def _require_cards_available(state: BoutState, actor: Seat, card_count: int) -> None:
    if card_count > state.hand_count(actor):
        raise BoutActionError(BoutErrorCode.NOT_ENOUGH_CARDS)


def _require_attack_limit(state: BoutState, added_card_count: int) -> None:
    if added_card_count > state.max_attack_card_addition:
        raise BoutActionError(BoutErrorCode.ATTACK_CARD_LIMIT_EXCEEDED)


def _get_active_packet(state: BoutState) -> AttackPacket:
    packet = state.active_packet
    if packet is None:
        raise BoutActionError(BoutErrorCode.WRONG_PHASE)
    return packet


def _validate_seat_order(seat_order: tuple[Seat, ...]) -> None:
    if not isinstance(seat_order, tuple) or not all(isinstance(seat, Seat) for seat in seat_order):
        raise TypeError("seat_order must be a tuple of Seat values")
    if seat_order != seats_for_player_count(len(seat_order)):
        raise ValueError("seat_order must be the canonical stable ring for 2–4 players")


def _validate_hand_count(name: str, value: int) -> None:
    _validate_non_negative_int(name, value)


def _validate_non_negative_int(name: str, value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an int")
    if value < 0:
        raise ValueError(f"{name} must not be negative")
