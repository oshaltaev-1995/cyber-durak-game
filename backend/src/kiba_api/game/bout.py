"""Immutable two-participant orchestration for one Kiba bout."""

from collections.abc import Iterable
from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Self

from kiba_api.game.attack import analyze_initial_attack
from kiba_api.game.cards import Card, TrumpState
from kiba_api.game.moves import analyze_defense, analyze_throw_in, is_legal_defense
from kiba_api.game.scoring import get_cards_value
from kiba_api.game.transfer import analyze_packet_transfer


class Seat(StrEnum):
    """One of the two participant positions supported by Alpha 1 bouts."""

    ONE = "one"
    TWO = "two"

    @property
    def other(self) -> "Seat":
        """Return the only other seat in a two-participant bout."""
        return Seat.TWO if self is Seat.ONE else Seat.ONE


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


@dataclass(frozen=True, slots=True)
class BoutState:
    """A complete immutable snapshot of one two-participant bout."""

    attacker: Seat
    defender: Seat
    seat_one_hand_count: int
    seat_two_hand_count: int
    trump_state: TrumpState
    phase: BoutPhase
    packets: tuple[AttackPacket, ...]
    transfer_open: bool
    attack_card_limit: int
    total_attack_card_count: int
    outcome: BoutOutcome | None = None
    next_attacker: Seat | None = None
    taker: Seat | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.attacker, Seat) or not isinstance(self.defender, Seat):
            raise TypeError("attacker and defender must be Seat values")
        if self.attacker is self.defender:
            raise ValueError("attacker and defender must be different seats")
        _validate_hand_count("seat_one_hand_count", self.seat_one_hand_count)
        _validate_hand_count("seat_two_hand_count", self.seat_two_hand_count)
        if not isinstance(self.trump_state, TrumpState):
            raise TypeError("trump_state must be a TrumpState")
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
        self._validate_terminal_metadata()

    @classmethod
    def start(
        cls,
        *,
        attacker: Seat,
        seat_one_hand_count: int,
        seat_two_hand_count: int,
        trump_state: TrumpState,
    ) -> Self:
        """Create an empty bout with a caller-selected initial attacker."""
        if not isinstance(attacker, Seat):
            raise TypeError("attacker must be a Seat")
        _validate_hand_count("seat_one_hand_count", seat_one_hand_count)
        _validate_hand_count("seat_two_hand_count", seat_two_hand_count)
        if not isinstance(trump_state, TrumpState):
            raise TypeError("trump_state must be a TrumpState")

        defender = attacker.other
        defender_count = seat_one_hand_count if defender is Seat.ONE else seat_two_hand_count
        return cls(
            attacker=attacker,
            defender=defender,
            seat_one_hand_count=seat_one_hand_count,
            seat_two_hand_count=seat_two_hand_count,
            trump_state=trump_state,
            phase=BoutPhase.WAITING_FOR_INITIAL_ATTACK,
            packets=(),
            transfer_open=True,
            attack_card_limit=defender_count,
            total_attack_card_count=0,
        )

    def hand_count(self, seat: Seat) -> int:
        """Return a seat's numeric remaining-card count."""
        if not isinstance(seat, Seat):
            raise TypeError("seat must be a Seat")
        return self.seat_one_hand_count if seat is Seat.ONE else self.seat_two_hand_count

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
                and get_cards_value(
                    packet.defense_cards,
                    self.trump_state,
                )
                != packet.defense_value
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
                raise ValueError("the defender must attack next after bito")
        elif self.outcome is BoutOutcome.TAKE:
            if self.active_packet is None or self.taker is not self.defender:
                raise ValueError("take requires the active defender as taker")
            if self.next_attacker is not self.attacker:
                raise ValueError("the attacker retains initiative after take")


def play_initial_attack(
    state: BoutState,
    actor: Seat,
    cards: Iterable[Card],
) -> BoutState:
    """Play the structurally valid first packet of a bout."""
    _require_phase(state, BoutPhase.WAITING_FOR_INITIAL_ATTACK)
    _require_actor(actor, state.attacker)
    selected = tuple(cards)
    _require_cards_available(state, actor, len(selected))
    _require_attack_limit(state, len(selected))
    if not analyze_initial_attack(selected, state.trump_state).legal:
        raise BoutActionError(BoutErrorCode.ILLEGAL_INITIAL_ATTACK)

    packet = AttackPacket(
        attack_cards=selected,
        attack_value=get_cards_value(selected, state.trump_state),
    )
    return _spend_cards(
        state,
        actor,
        len(selected),
        packets=(packet,),
        phase=BoutPhase.WAITING_FOR_DEFENDER_RESPONSE,
        total_attack_card_count=len(selected),
    )


def play_transfer(
    state: BoutState,
    actor: Seat,
    cards: Iterable[Card],
) -> BoutState:
    """Extend the unresolved packet and swap two-participant attack roles."""
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
    new_attacker = state.defender
    new_defender = state.attacker
    new_limit = state.hand_count(new_defender)
    if total_attack_card_count > new_limit:
        raise BoutActionError(BoutErrorCode.ATTACK_CARD_LIMIT_EXCEEDED)

    extended_packet = replace(
        packet,
        attack_cards=packet.attack_cards + selected,
        attack_value=analysis.next_target,
    )
    return _spend_cards(
        state,
        actor,
        len(selected),
        packets=(*state.packets[:-1], extended_packet),
        attacker=new_attacker,
        defender=new_defender,
        attack_card_limit=new_limit,
        total_attack_card_count=total_attack_card_count,
    )


def play_defense(
    state: BoutState,
    actor: Seat,
    cards: Iterable[Card],
) -> BoutState:
    """Close only the current active packet with a strictly higher total."""
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
    return _spend_cards(
        state,
        actor,
        len(selected),
        packets=(*state.packets[:-1], closed_packet),
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
    """Create a new independent packet from a legal post-defense throw-in."""
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
    )
    if not analysis.legal:
        raise BoutActionError(BoutErrorCode.ILLEGAL_THROW_IN)

    packet = AttackPacket(
        attack_cards=selected,
        attack_value=analysis.selected_value,
    )
    return _spend_cards(
        state,
        actor,
        len(selected),
        packets=(*state.packets, packet),
        phase=BoutPhase.WAITING_FOR_DEFENDER_RESPONSE,
        total_attack_card_count=state.total_attack_card_count + len(selected),
    )


def finish_bout(state: BoutState, actor: Seat) -> BoutState:
    """Finish a fully covered bout as bito without starting the next bout."""
    _require_phase(state, BoutPhase.WAITING_FOR_ATTACKER_DECISION)
    _require_actor(actor, state.attacker)
    return replace(
        state,
        phase=BoutPhase.COMPLETE,
        transfer_open=False,
        outcome=BoutOutcome.BITO,
        next_attacker=state.defender,
    )


def take(state: BoutState, actor: Seat) -> BoutState:
    """End the bout immediately with the active defender taking its table."""
    _require_phase(state, BoutPhase.WAITING_FOR_DEFENDER_RESPONSE)
    _require_actor(actor, state.defender)
    return replace(
        state,
        phase=BoutPhase.COMPLETE,
        transfer_open=False,
        outcome=BoutOutcome.TAKE,
        next_attacker=state.attacker,
        taker=state.defender,
    )


def _spend_cards(
    state: BoutState,
    actor: Seat,
    card_count: int,
    **changes: object,
) -> BoutState:
    if actor is Seat.ONE:
        changes["seat_one_hand_count"] = state.seat_one_hand_count - card_count
    else:
        changes["seat_two_hand_count"] = state.seat_two_hand_count - card_count
    return replace(state, **changes)


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


def _validate_hand_count(name: str, value: int) -> None:
    _validate_non_negative_int(name, value)


def _validate_non_negative_int(name: str, value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an int")
    if value < 0:
        raise ValueError(f"{name} must not be negative")
