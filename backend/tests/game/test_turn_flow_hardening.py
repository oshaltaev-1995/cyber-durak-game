from dataclasses import dataclass

import pytest

from kiba_api.game import (
    BoutActionError,
    BoutErrorCode,
    BoutPhase,
    BoutState,
    Card,
    GameState,
    Rank,
    Seat,
    Suit,
    TrumpState,
    finish_bout,
    play_defense,
    play_game_defense,
    play_game_initial_attack,
    play_initial_attack,
    play_throw_in,
    play_transfer,
    seats_for_player_count,
    start_game_bout,
)
from kiba_api.sessions import (
    BotPresentationEventType,
    GameSessionService,
    HumanActionType,
    acting_seat,
    available_actions_for,
)


def card(rank: Rank, suit: Suit = Suit.CLUBS) -> Card:
    return Card(rank=rank, suit=suit)


@dataclass(frozen=True, slots=True)
class RoleTrace:
    event: str
    phase: BoutPhase
    lead_attacker: Seat
    current_attacker: Seat
    defender: Seat
    required_actor: Seat | None
    attack_count: int
    defender_cap: int
    passed_attackers: tuple[Seat, ...]


def trace(event: str, state: BoutState) -> RoleTrace:
    required = (
        state.defender
        if state.phase is BoutPhase.WAITING_FOR_DEFENDER_RESPONSE
        else state.attacker
        if state.phase
        in {BoutPhase.WAITING_FOR_INITIAL_ATTACK, BoutPhase.WAITING_FOR_ATTACKER_DECISION}
        else None
    )
    return RoleTrace(
        event=event,
        phase=state.phase,
        lead_attacker=state.lead_attacker,
        current_attacker=state.attacker,
        defender=state.defender,
        required_actor=required,
        attack_count=state.total_attack_card_count,
        defender_cap=state.attack_card_limit,
        passed_attackers=state.closed_attackers,
    )


@pytest.mark.parametrize("player_count", [3, 4])
def test_only_lead_can_commit_the_atomic_initial_attack(player_count: int) -> None:
    seats = seats_for_player_count(player_count)
    state = BoutState.start(
        attacker=Seat.ONE,
        seat_order=seats,
        active_seats=seats,
        hand_counts=(7,) * player_count,
        trump_state=TrumpState.no_trump(),
    )

    with pytest.raises(BoutActionError) as caught:
        play_initial_attack(state, Seat.THREE, (card(Rank.SIX),))
    assert caught.value.code is BoutErrorCode.WRONG_ACTOR

    attacked = play_initial_attack(
        state,
        Seat.ONE,
        (card(Rank.TEN, Suit.DIAMONDS), card(Rank.TEN, Suit.HEARTS)),
    )
    assert attacked.active_packet is not None
    assert attacked.active_packet.attack_cards == (
        card(Rank.TEN, Suit.DIAMONDS),
        card(Rank.TEN, Suit.HEARTS),
    )
    assert attacked.phase is BoutPhase.WAITING_FOR_DEFENDER_RESPONSE
    assert trace("initial_attack", attacked).required_actor is Seat.TWO
    assert attacked.hand_count(Seat.THREE) == 7

    with pytest.raises(BoutActionError) as second_attacker:
        play_throw_in(attacked, Seat.THREE, (card(Rank.TEN, Suit.SPADES),))
    assert second_attacker.value.code is BoutErrorCode.WRONG_PHASE


def test_screenshot_state_is_a_canonical_transfer_chain_and_cap_rejection() -> None:
    trump = TrumpState.from_source_card(card(Rank.SEVEN, Suit.CLUBS))
    started = BoutState.start(
        attacker=Seat.ONE,
        seat_order=seats_for_player_count(3),
        active_seats=seats_for_player_count(3),
        hand_counts=(7, 7, 7),
        trump_state=trump,
    )
    attacked = play_initial_attack(
        started,
        Seat.ONE,
        (card(Rank.TEN, Suit.DIAMONDS), card(Rank.TEN, Suit.HEARTS)),
    )
    transferred = play_transfer(
        attacked,
        Seat.TWO,
        (card(Rank.EIGHT, Suit.HEARTS), card(Rank.JACK, Suit.DIAMONDS)),
    )

    assert transferred.active_packet is not None
    assert transferred.active_packet.attack_value == 40
    assert transferred.total_attack_card_count == 4
    assert transferred.hand_count(Seat.ONE) == 5
    assert transferred.hand_count(Seat.TWO) == 5
    assert transferred.hand_count(Seat.THREE) == 7
    assert transferred.lead_attacker is Seat.ONE
    assert transferred.attacker is Seat.ONE
    assert transferred.defender is Seat.THREE
    assert trace("mika_transfer", transferred).required_actor is Seat.THREE

    snapshot = transferred
    with pytest.raises(BoutActionError) as caught:
        play_transfer(
            transferred,
            Seat.THREE,
            (
                card(Rank.SIX, Suit.CLUBS),
                card(Rank.SEVEN, Suit.HEARTS),
                card(Rank.SEVEN, Suit.SPADES),
            ),
        )
    assert caught.value.code is BoutErrorCode.ATTACK_CARD_LIMIT_EXCEEDED
    assert transferred == snapshot


def test_role_trace_covers_defense_continuation_pass_and_bito() -> None:
    state = BoutState.start(
        attacker=Seat.ONE,
        seat_order=seats_for_player_count(3),
        active_seats=seats_for_player_count(3),
        hand_counts=(7, 7, 7),
        trump_state=TrumpState.no_trump(),
    )
    traces = [trace("bout_start", state)]
    state = play_initial_attack(state, Seat.ONE, (card(Rank.SIX),))
    traces.append(trace("initial_attack", state))
    state = play_defense(state, Seat.TWO, (card(Rank.SEVEN),))
    traces.append(trace("successful_defense", state))
    state = play_throw_in(state, Seat.ONE, (card(Rank.SEVEN, Suit.DIAMONDS),))
    traces.append(trace("lead_continues", state))
    state = play_defense(state, Seat.TWO, (card(Rank.EIGHT),))
    traces.append(trace("second_defense", state))
    state = finish_bout(state, Seat.ONE)
    traces.append(trace("lead_passes", state))
    state = finish_bout(state, Seat.THREE)
    traces.append(trace("bito", state))

    assert [item.required_actor for item in traces] == [
        Seat.ONE,
        Seat.TWO,
        Seat.ONE,
        Seat.TWO,
        Seat.ONE,
        Seat.THREE,
        None,
    ]
    assert traces[-2].passed_attackers == (Seat.ONE,)
    assert traces[-1].passed_attackers == (Seat.ONE, Seat.THREE)


def test_transfer_role_tables_for_three_four_and_finished_seat_skip() -> None:
    three = BoutState.start(
        attacker=Seat.ONE,
        seat_order=seats_for_player_count(3),
        active_seats=seats_for_player_count(3),
        hand_counts=(7, 7, 7),
        trump_state=TrumpState.no_trump(),
    )
    three = play_initial_attack(three, Seat.ONE, (card(Rank.SIX),))
    three = play_transfer(three, Seat.TWO, (card(Rank.SIX, Suit.DIAMONDS),))
    assert (three.lead_attacker, three.attacker, three.defender, three.attacker_order) == (
        Seat.ONE,
        Seat.ONE,
        Seat.THREE,
        (Seat.ONE, Seat.TWO),
    )
    three = play_transfer(three, Seat.THREE, (card(Rank.JACK),))
    assert (three.lead_attacker, three.attacker, three.defender, three.attacker_order) == (
        Seat.THREE,
        Seat.THREE,
        Seat.ONE,
        (Seat.THREE, Seat.TWO),
    )

    four = BoutState.start(
        attacker=Seat.ONE,
        seat_order=seats_for_player_count(4),
        active_seats=seats_for_player_count(4),
        hand_counts=(7, 7, 7, 7),
        trump_state=TrumpState.no_trump(),
    )
    four = play_initial_attack(four, Seat.ONE, (card(Rank.SIX),))
    four = play_transfer(four, Seat.TWO, (card(Rank.SIX, Suit.DIAMONDS),))
    four = play_transfer(four, Seat.THREE, (card(Rank.JACK),))
    assert (four.lead_attacker, four.attacker, four.defender, four.attacker_order) == (
        Seat.ONE,
        Seat.ONE,
        Seat.FOUR,
        (Seat.ONE, Seat.TWO, Seat.THREE),
    )
    four = play_transfer(
        four,
        Seat.FOUR,
        (card(Rank.JACK, Suit.DIAMONDS), card(Rank.JACK, Suit.HEARTS)),
    )
    assert (four.lead_attacker, four.attacker, four.defender, four.attacker_order) == (
        Seat.FOUR,
        Seat.FOUR,
        Seat.ONE,
        (Seat.FOUR, Seat.TWO, Seat.THREE),
    )

    reduced = BoutState.start(
        attacker=Seat.ONE,
        seat_order=seats_for_player_count(4),
        active_seats=(Seat.ONE, Seat.TWO, Seat.FOUR),
        hand_counts=(7, 7, 0, 7),
        trump_state=TrumpState.no_trump(),
    )
    reduced = play_initial_attack(reduced, Seat.ONE, (card(Rank.SIX),))
    reduced = play_transfer(reduced, Seat.TWO, (card(Rank.SIX, Suit.DIAMONDS),))
    assert reduced.defender is Seat.FOUR
    assert reduced.attacker_order == (Seat.ONE, Seat.TWO)


@pytest.mark.parametrize("player_count,lead", [(3, Seat.THREE), (4, Seat.FOUR)])
def test_bot_initial_cascade_stops_at_human_defender(
    player_count: int,
    lead: Seat,
) -> None:
    seats = seats_for_player_count(player_count)
    hands = tuple(
        (
            card(Rank.SEVEN, tuple(Suit)[index]),
            card(Rank.EIGHT, tuple(Suit)[index]),
            card(Rank.NINE, tuple(Suit)[index]),
            card(Rank.TEN, tuple(Suit)[index]),
            card(Rank.JACK, tuple(Suit)[index]),
            card(Rank.QUEEN, tuple(Suit)[index]),
            card(Rank.KING, tuple(Suit)[index]),
        )
        for index in range(player_count)
    )
    lead_index = seats.index(lead)
    lead_hand = list(hands[lead_index])
    lead_hand[:2] = [card(Rank.SIX, Suit.CLUBS), card(Rank.SIX, Suit.DIAMONDS)]
    hands = (*hands[:lead_index], tuple(lead_hand), *hands[lead_index + 1 :])
    initial = GameState(
        seat_order=seats,
        hands=hands,
        draw_pile=(card(Rank.ACE, Suit.SPADES),),
        discard_pile=(),
        current_attacker=lead,
    )
    original_counts = tuple(len(hand) for hand in initial.hands)
    service = GameSessionService(multiplayer_game_factory=lambda _: initial)

    session = service.create_game(total_players=player_count)

    assert len(session.recent_events) == 1
    assert session.recent_events[0].type is BotPresentationEventType.INITIAL_ATTACK
    assert session.recent_events[0].actor_seat is lead
    assert acting_seat(session.state) is Seat.ONE
    assert session.state.active_bout is not None
    assert session.state.active_bout.phase is BoutPhase.WAITING_FOR_DEFENDER_RESPONSE
    assert session.state.active_bout.defender is Seat.ONE
    assert len(session.state.draw_pile) == 1
    for seat in seats:
        if seat not in {lead}:
            assert len(session.state.hand(seat)) == original_counts[seats.index(seat)]


def test_bot_cascade_stops_when_a_human_attacker_has_a_legal_phase() -> None:
    state = GameState(
        seat_order=seats_for_player_count(4),
        hands=(
            (card(Rank.KING, Suit.HEARTS), card(Rank.SIX, Suit.HEARTS)),
            (card(Rank.ACE, Suit.CLUBS),),
            (card(Rank.JACK), card(Rank.KING, Suit.DIAMONDS)),
            (card(Rank.KING, Suit.SPADES), card(Rank.SIX, Suit.SPADES)),
        ),
        draw_pile=(),
        discard_pile=(),
        current_attacker=Seat.THREE,
    )
    state = start_game_bout(state)
    state = play_game_initial_attack(state, Seat.THREE, (card(Rank.JACK),))
    state = play_game_defense(state, Seat.FOUR, (card(Rank.KING, Suit.SPADES),))
    assert acting_seat(state) is Seat.THREE

    service = GameSessionService(multiplayer_game_factory=lambda _: state)
    session = service.create_game(total_players=4)

    assert [event.actor_seat for event in session.recent_events] == [Seat.THREE]
    assert session.recent_events[0].type is BotPresentationEventType.BITO
    assert acting_seat(session.state) is Seat.ONE
    assert available_actions_for(session.state, Seat.ONE) == (
        HumanActionType.THROW_IN,
        HumanActionType.BITO,
    )
