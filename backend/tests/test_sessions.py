import random
from concurrent.futures import ThreadPoolExecutor

import pytest

from kiba_api.game import (
    BoutActionError,
    BoutPhase,
    Card,
    GameActionError,
    GameOutcome,
    GamePhase,
    GameResult,
    GameState,
    Rank,
    Seat,
    Suit,
    create_new_game,
)
from kiba_api.sessions import (
    GameSessionService,
    HumanActionType,
    InMemoryGameSessionStore,
    SessionActionError,
    SessionErrorCode,
    SessionNotFoundError,
)


def card(rank: Rank, suit: Suit = Suit.CLUBS) -> Card:
    return Card(rank=rank, suit=suit)


def ready_game(*, attacker: Seat) -> GameState:
    return GameState(
        seat_one_hand=(card(Rank.SIX), card(Rank.SEVEN), card(Rank.EIGHT)),
        seat_two_hand=(card(Rank.NINE), card(Rank.TEN), card(Rank.JACK)),
        draw_pile=(),
        discard_pile=(),
        current_attacker=attacker,
    )


def test_session_creation_assigns_fixed_seats_and_starts_human_bout() -> None:
    service = GameSessionService(game_factory=lambda: ready_game(attacker=Seat.ONE))

    session = service.create_game()

    assert session.human_seat is Seat.ONE
    assert session.bot_seat is Seat.TWO
    assert session.state.phase is GamePhase.BOUT_ACTIVE
    assert session.state.active_bout is not None
    assert session.state.active_bout.phase is BoutPhase.WAITING_FOR_INITIAL_ATTACK
    assert session.state.active_bout.attacker is Seat.ONE


def test_bot_starts_and_attacks_before_session_returns_to_human() -> None:
    service = GameSessionService(game_factory=lambda: ready_game(attacker=Seat.TWO))

    session = service.create_game()

    assert session.state.active_bout is not None
    assert session.state.active_bout.phase is BoutPhase.WAITING_FOR_DEFENDER_RESPONSE
    assert session.state.active_bout.defender is Seat.ONE
    assert len(session.state.active_bout.table_cards) == 1
    assert len(session.state.seat_two_hand) == 2


def test_human_action_replaces_immutable_state_then_auto_advances_bot() -> None:
    service = GameSessionService(game_factory=lambda: ready_game(attacker=Seat.ONE))
    created = service.create_game()
    original_state = created.state

    updated = service.play_human_action(
        created.game_id,
        HumanActionType.INITIAL_ATTACK,
        (card(Rank.SIX),),
    )

    assert updated.state is not original_state
    assert original_state.seat_one_hand == (
        card(Rank.SIX),
        card(Rank.SEVEN),
        card(Rank.EIGHT),
    )
    assert updated.state != original_state
    assert service.get_game(created.game_id) == updated


def test_session_lookup_has_explicit_not_found_behavior() -> None:
    service = GameSessionService()

    with pytest.raises(SessionNotFoundError) as caught:
        service.get_game("missing")

    assert caught.value.code == "game_not_found"
    assert caught.value.game_id == "missing"


def test_human_action_is_rejected_when_bot_owns_decision() -> None:
    store = InMemoryGameSessionStore(id_factory=lambda: "bot-turn")
    session = store.create(ready_game(attacker=Seat.TWO))
    service = GameSessionService(store=store)

    with pytest.raises(SessionActionError) as caught:
        service.play_human_action(
            session.game_id,
            HumanActionType.INITIAL_ATTACK,
            (card(Rank.SIX),),
        )

    assert caught.value.code is SessionErrorCode.NOT_HUMAN_TURN


def test_completed_session_rejects_human_actions() -> None:
    completed = GameState(
        seat_one_hand=(),
        seat_two_hand=(card(Rank.SIX),),
        draw_pile=(),
        discard_pile=(),
        current_attacker=None,
        phase=GamePhase.COMPLETE,
        result=GameResult(GameOutcome.WIN, Seat.ONE),
    )
    service = GameSessionService(game_factory=lambda: completed)
    session = service.create_game()

    with pytest.raises(SessionActionError) as caught:
        service.play_human_action(session.game_id, HumanActionType.BITO)

    assert caught.value.code is SessionErrorCode.GAME_COMPLETE
    assert service.get_game(session.game_id).state is completed


def test_bot_auto_advance_has_a_defensive_action_bound() -> None:
    service = GameSessionService(
        game_factory=lambda: ready_game(attacker=Seat.TWO),
        bot_turn=lambda state, _seat: state,
        bot_action_limit=2,
    )

    with pytest.raises(SessionActionError) as caught:
        service.create_game()

    assert caught.value.code is SessionErrorCode.BOT_AUTO_ADVANCE_LIMIT


def test_concurrent_human_actions_are_serialized_against_one_snapshot() -> None:
    service = GameSessionService(game_factory=lambda: ready_game(attacker=Seat.ONE))
    session = service.create_game()

    def submit() -> str:
        try:
            service.play_human_action(
                session.game_id,
                HumanActionType.INITIAL_ATTACK,
                (card(Rank.SIX),),
            )
        except (BoutActionError, GameActionError, SessionActionError) as error:
            return error.code.value
        return "accepted"

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = tuple(executor.map(lambda _index: submit(), range(2)))

    assert results.count("accepted") == 1
    assert len(results) == 2
    assert service.get_game(session.game_id).state is not session.state


def test_seeded_real_game_session_stops_only_for_human_or_completion() -> None:
    service = GameSessionService(game_factory=lambda: create_new_game(random.Random(42)))

    session = service.create_game()

    assert session.state.phase in {GamePhase.BOUT_ACTIVE, GamePhase.COMPLETE}
    if session.state.phase is GamePhase.BOUT_ACTIVE:
        bout = session.state.active_bout
        assert bout is not None
        actor = (
            bout.defender
            if bout.phase is BoutPhase.WAITING_FOR_DEFENDER_RESPONSE
            else bout.attacker
        )
        assert actor is Seat.ONE
