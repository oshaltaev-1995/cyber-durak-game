import random

import pytest
from fastapi.testclient import TestClient

from kiba_api.config import Settings
from kiba_api.game import (
    BotAction,
    BotActionType,
    Card,
    GamePhase,
    GameState,
    Rank,
    Seat,
    Suit,
    build_bot_context,
    choose_bot_action,
    create_new_game,
    play_bot_turn,
    play_game_defense,
    play_game_initial_attack,
    play_game_transfer,
    start_game_bout,
)
from kiba_api.main import create_app
from kiba_api.sessions import (
    BOT_NAME_POOL,
    GameSession,
    GameSessionService,
    HumanActionType,
    acting_seat,
    assign_bot_names,
)


def card(rank: Rank, suit: Suit = Suit.CLUBS) -> Card:
    return Card(rank=rank, suit=suit)


def multiplayer_state(
    hands: tuple[tuple[Card, ...], ...],
    *,
    attacker: Seat,
    draw_pile: tuple[Card, ...] = (),
) -> GameState:
    return GameState(
        hands=hands,
        draw_pile=draw_pile,
        discard_pile=(),
        current_attacker=attacker,
    )


_HUMAN_ACTIONS = {
    BotActionType.INITIAL_ATTACK: HumanActionType.INITIAL_ATTACK,
    BotActionType.DEFEND: HumanActionType.DEFEND,
    BotActionType.TRANSFER: HumanActionType.TRANSFER,
    BotActionType.THROW_IN: HumanActionType.THROW_IN,
    BotActionType.TAKE: HumanActionType.TAKE,
    BotActionType.BITO: HumanActionType.BITO,
}


def play_human_with_baseline(service: GameSessionService, session: GameSession) -> GameSession:
    action = choose_bot_action(session.state, session.human_seat)
    return service.play_human_action(
        session.game_id,
        _HUMAN_ACTIONS[action.action_type],
        action.cards,
    )


def complete_session(service: GameSessionService, session: GameSession) -> GameSession:
    human_actions = 0
    while session.state.phase is not GamePhase.COMPLETE:
        session = play_human_with_baseline(service, session)
        human_actions += 1
        assert human_actions < 500
    return session


def assert_card_conservation(state: GameState) -> None:
    assert len(state.all_cards) == 36
    assert len(set(state.all_cards)) == 36


def test_curated_names_are_unique_safe_and_sized_for_product_use() -> None:
    assert 30 <= len(BOT_NAME_POOL) <= 50
    assert len({name.casefold() for name in BOT_NAME_POOL}) == len(BOT_NAME_POOL)
    assert all(name.strip() == name and name.isalpha() for name in BOT_NAME_POOL)


@pytest.mark.parametrize("count", [1, 2, 3])
def test_seeded_bot_name_assignment_is_unique_and_deterministic(count: int) -> None:
    first = assign_bot_names(
        count,
        human_display_name="Milo",
        rng=random.Random(42),
    )
    second = assign_bot_names(
        count,
        human_display_name="  MILO  ",
        rng=random.Random(42),
    )

    assert first == second
    assert len({name.casefold() for name in first}) == count
    assert "milo" not in {name.casefold() for name in first}


def test_bot_name_assignment_rejects_an_insufficient_normalized_pool() -> None:
    with pytest.raises(ValueError, match="too few"):
        assign_bot_names(
            2,
            human_display_name="MILO",
            rng=random.Random(1),
            pool=("Milo", "milo", "Nika"),
        )


def test_multi_bot_session_has_stable_normal_participants_and_names_on_restart() -> None:
    ids = iter(f"participant-{index}" for index in range(4))
    game_rng = random.Random(7)
    service = GameSessionService(
        multiplayer_game_factory=lambda count: create_new_game(game_rng, player_count=count),
        name_rng=random.Random(9),
        participant_id_factory=ids.__next__,
    )

    session = service.create_game(total_players=4, human_display_name="Milo")
    restarted = service.restart_game(session.game_id)

    assert tuple(participant.seat for participant in session.participants) == (
        Seat.ONE,
        Seat.TWO,
        Seat.THREE,
        Seat.FOUR,
    )
    assert session.bot_seats == (Seat.TWO, Seat.THREE, Seat.FOUR)
    assert [participant.is_bot for participant in session.participants] == [False, True, True, True]
    assert len({participant.display_name.casefold() for participant in session.participants}) == 4
    assert restarted.participants == session.participants
    assert restarted.state is not session.state
    assert restarted.state != session.state
    assert restarted.state.finish_groups == ()


def test_bot_context_contains_only_own_hand_and_public_information() -> None:
    own = (card(Rank.SIX), card(Rank.SEVEN))
    exposed = card(Rank.EIGHT, Suit.HEARTS)
    first = multiplayer_state(
        (
            (card(Rank.ACE), card(Rank.KING)),
            own,
            (card(Rank.NINE), card(Rank.TEN)),
        ),
        attacker=Seat.TWO,
        draw_pile=(exposed, card(Rank.JACK), card(Rank.QUEEN)),
    )
    second = multiplayer_state(
        (
            (card(Rank.NINE, Suit.DIAMONDS), card(Rank.TEN, Suit.DIAMONDS)),
            own,
            (card(Rank.ACE, Suit.SPADES), card(Rank.KING, Suit.SPADES)),
        ),
        attacker=Seat.TWO,
        draw_pile=(exposed, card(Rank.SIX, Suit.SPADES), card(Rank.SEVEN, Suit.SPADES)),
    )

    first_context = build_bot_context(first, Seat.TWO)
    second_context = build_bot_context(second, Seat.TWO)

    assert first_context == second_context
    assert choose_bot_action(first, Seat.TWO) == choose_bot_action(second, Seat.TWO)
    debug = repr(first_context)
    assert "ACE" not in debug
    assert "KING" not in debug
    assert "JACK" not in debug
    assert "QUEEN" not in debug


@pytest.mark.parametrize("bot_seat", [Seat.ONE, Seat.TWO, Seat.THREE, Seat.FOUR])
def test_bot_can_act_from_every_canonical_seat(bot_seat: Seat) -> None:
    state = multiplayer_state(
        (
            (card(Rank.ACE),),
            (card(Rank.SIX),),
            (card(Rank.SEVEN),),
            (card(Rank.EIGHT),),
        ),
        attacker=bot_seat,
    )

    started = play_bot_turn(state, bot_seat)
    attacked = play_bot_turn(started, bot_seat)

    assert attacked.active_bout is not None
    assert attacked.active_bout.defender is not bot_seat


@pytest.mark.parametrize(
    "bot_hand",
    [
        (card(Rank.SIX), card(Rank.SIX, Suit.DIAMONDS), card(Rank.ACE)),
        (card(Rank.SIX), card(Rank.JACK), card(Rank.KING), card(Rank.ACE)),
    ],
)
def test_multiplayer_bot_can_choose_canonical_multi_card_initial_structures(
    bot_hand: tuple[Card, ...],
) -> None:
    state = start_game_bout(
        multiplayer_state(
            (
                (card(Rank.SEVEN),),
                bot_hand,
                (
                    card(Rank.EIGHT),
                    card(Rank.NINE),
                    card(Rank.TEN),
                    card(Rank.QUEEN),
                ),
            ),
            attacker=Seat.TWO,
        )
    )

    action = choose_bot_action(state, Seat.TWO)
    applied = play_bot_turn(state, Seat.TWO)

    assert len(action.cards) > 1
    assert applied.active_bout is not None
    assert applied.active_bout.total_attack_card_count == len(action.cards)


def test_three_player_bot_transfers_to_next_clockwise_seat() -> None:
    king = card(Rank.KING)
    nines = (card(Rank.NINE), card(Rank.NINE, Suit.DIAMONDS))
    state = start_game_bout(
        multiplayer_state(
            (
                (king, card(Rank.SIX)),
                nines,
                (card(Rank.EIGHT), card(Rank.TEN), card(Rank.JACK)),
            ),
            attacker=Seat.ONE,
        )
    )
    state = play_game_initial_attack(state, Seat.ONE, (king,))

    action = choose_bot_action(state, Seat.TWO)
    transferred = play_bot_turn(state, Seat.TWO)

    assert action == BotAction(BotActionType.TRANSFER, nines)
    assert transferred.active_bout is not None
    assert transferred.active_bout.defender is Seat.THREE


def test_four_player_bot_transfer_chain_can_wrap_to_human() -> None:
    initial_king = card(Rank.KING)
    b_transfer = (card(Rank.NINE), card(Rank.NINE, Suit.DIAMONDS))
    c_transfer = (
        card(Rank.JACK),
        card(Rank.JACK, Suit.DIAMONDS),
        card(Rank.SIX),
        card(Rank.SIX, Suit.DIAMONDS),
    )
    d_transfer = (
        card(Rank.ACE),
        card(Rank.ACE, Suit.DIAMONDS),
        card(Rank.KING, Suit.HEARTS),
        card(Rank.SEVEN),
        card(Rank.SEVEN, Suit.DIAMONDS),
    )
    state = start_game_bout(
        multiplayer_state(
            (
                (
                    initial_king,
                    *(card(Rank.QUEEN, suit) for suit in Suit),
                    card(Rank.ACE, Suit.HEARTS),
                    card(Rank.ACE, Suit.SPADES),
                    card(Rank.KING, Suit.DIAMONDS),
                    card(Rank.KING, Suit.SPADES),
                    *(card(Rank.TEN, suit) for suit in Suit),
                ),
                b_transfer,
                c_transfer,
                (*d_transfer, card(Rank.EIGHT), card(Rank.EIGHT, Suit.DIAMONDS)),
            ),
            attacker=Seat.ONE,
        )
    )
    state = play_game_initial_attack(state, Seat.ONE, (initial_king,))
    state = play_game_transfer(state, Seat.TWO, b_transfer)
    state = play_game_transfer(state, Seat.THREE, c_transfer)

    action = choose_bot_action(state, Seat.FOUR)
    wrapped = play_bot_turn(state, Seat.FOUR)

    assert action.action_type is BotActionType.TRANSFER
    assert wrapped.active_bout is not None
    assert wrapped.active_bout.defender is Seat.ONE
    assert wrapped.active_bout.lead_attacker is Seat.FOUR
    assert wrapped.active_bout.refill_order == (Seat.ONE, Seat.THREE, Seat.FOUR, Seat.TWO)


def test_multiplayer_bot_voluntarily_passes_an_expensive_legal_throw_in() -> None:
    jack = card(Rank.JACK)
    king = card(Rank.KING)
    second_king = card(Rank.KING, Suit.DIAMONDS)
    state = start_game_bout(
        multiplayer_state(
            (
                (card(Rank.SIX),),
                (jack, second_king),
                (king, card(Rank.ACE)),
            ),
            attacker=Seat.TWO,
        )
    )
    state = play_game_initial_attack(state, Seat.TWO, (jack,))
    state = play_game_defense(state, Seat.THREE, (king,))

    action = choose_bot_action(state, Seat.TWO)
    advanced = play_bot_turn(state, Seat.TWO)

    assert action == BotAction(BotActionType.BITO)
    assert second_king in advanced.hand(Seat.TWO)
    assert advanced.phase is GamePhase.READY_FOR_BOUT
    assert advanced.current_attacker is Seat.THREE


@pytest.mark.parametrize(
    ("attack", "defense", "later_hand", "expected"),
    [
        (
            (card(Rank.NINE),),
            (card(Rank.TEN),),
            (card(Rank.TEN, Suit.DIAMONDS),),
            (card(Rank.TEN, Suit.DIAMONDS),),
        ),
        (
            (card(Rank.SIX),),
            (card(Rank.SIX, Suit.DIAMONDS), card(Rank.SIX, Suit.HEARTS)),
            (card(Rank.JACK),),
            (card(Rank.JACK),),
        ),
        (
            (card(Rank.SIX),),
            (card(Rank.NINE),),
            (card(Rank.QUEEN),),
            (card(Rank.QUEEN),),
        ),
        (
            (card(Rank.SIX),),
            (card(Rank.KING),),
            (card(Rank.JACK),),
            (card(Rank.JACK),),
        ),
        (
            (card(Rank.SIX),),
            (card(Rank.NINE),),
            (card(Rank.SEVEN), card(Rank.EIGHT), card(Rank.TEN)),
            (card(Rank.SEVEN), card(Rank.EIGHT)),
        ),
    ],
)
def test_bot_table_math_candidates_survive_attacker_handoff(
    attack: tuple[Card, ...],
    defense: tuple[Card, ...],
    later_hand: tuple[Card, ...],
    expected: tuple[Card, ...],
) -> None:
    state = start_game_bout(
        multiplayer_state(
            (
                (*attack, card(Rank.ACE, Suit.SPADES)),
                (
                    *defense,
                    card(Rank.SEVEN, Suit.DIAMONDS),
                    card(Rank.EIGHT, Suit.DIAMONDS),
                    card(Rank.QUEEN, Suit.DIAMONDS),
                ),
                later_hand,
            ),
            attacker=Seat.ONE,
        )
    )
    state = play_game_initial_attack(state, Seat.ONE, attack)
    state = play_game_defense(state, Seat.TWO, defense)

    assert state.active_bout is not None
    assert state.active_bout.attacker is Seat.THREE
    assert choose_bot_action(state, Seat.THREE) == BotAction(BotActionType.THROW_IN, expected)


@pytest.mark.parametrize("player_count", [3, 4])
def test_bot_started_session_auto_advances_to_human_with_consecutive_bot_actors(
    player_count: int,
) -> None:
    service = GameSessionService(
        multiplayer_game_factory=lambda count: create_new_game(random.Random(0), player_count=count)
    )

    session = service.create_game(total_players=player_count)
    traces = [session.recent_events]
    while session.state.phase is not GamePhase.COMPLETE and not any(
        len({event.actor_seat for event in trace}) >= min(2, player_count - 1) for trace in traces
    ):
        session = play_human_with_baseline(service, session)
        traces.append(session.recent_events)

    assert session.initial_attacker is not Seat.ONE
    if session.state.phase is not GamePhase.COMPLETE:
        assert acting_seat(session.state) is Seat.ONE
    assert any(
        len({event.actor_seat for event in trace}) >= min(2, player_count - 1) for trace in traces
    )


@pytest.mark.parametrize("player_count,seed", [(3, 12), (4, 2)])
def test_real_multi_bot_session_completes_after_human_actions_and_bot_cascades(
    player_count: int,
    seed: int,
) -> None:
    recorder_calls: list[GameSession] = []
    service = GameSessionService(
        multiplayer_game_factory=lambda count: create_new_game(
            random.Random(seed), player_count=count
        ),
        name_rng=random.Random(seed),
        completion_recorder=lambda session: recorder_calls.append(session),
    )

    session = service.create_game(total_players=player_count)
    session = complete_session(service, session)

    assert session.state.phase is GamePhase.COMPLETE
    assert {seat for group in session.state.finish_groups for seat in group} == set(
        session.state.seat_order
    )
    assert session.human_seat in session.state.finish_groups[0]
    assert recorder_calls == []
    assert session.completion_persisted is False
    assert_card_conservation(session.state)


@pytest.mark.parametrize("player_count", [3, 4])
@pytest.mark.parametrize("seed", range(10))
def test_representative_seeded_multi_bot_matches_terminate_with_invariants(
    player_count: int,
    seed: int,
) -> None:
    state = create_new_game(random.Random(seed), player_count=player_count)
    transitions = 0
    seen: set[GameState] = set()

    while state.phase is not GamePhase.COMPLETE:
        assert state not in seen
        seen.add(state)
        assert_card_conservation(state)
        actor = acting_seat(state)
        assert actor is not None
        state = play_bot_turn(state, actor)
        transitions += 1
        assert transitions < 500

    assert_card_conservation(state)
    assert {seat for group in state.finish_groups for seat in group} == set(state.seat_order)


@pytest.mark.parametrize(
    ("player_count", "seed", "expected_groups"),
    [
        (3, 1, ((Seat.ONE, Seat.TWO), (Seat.THREE,))),
        (3, 3, ((Seat.THREE,), (Seat.ONE, Seat.TWO))),
        (4, 2, ((Seat.ONE,), (Seat.FOUR,), (Seat.TWO,), (Seat.THREE,))),
        (4, 10, ((Seat.ONE, Seat.FOUR), (Seat.TWO, Seat.THREE))),
    ],
)
def test_seeded_bot_finishes_cover_early_finish_unique_loser_and_ties(
    player_count: int,
    seed: int,
    expected_groups: tuple[tuple[Seat, ...], ...],
) -> None:
    state = create_new_game(random.Random(seed), player_count=player_count)
    while state.phase is not GamePhase.COMPLETE:
        actor = acting_seat(state)
        assert actor is not None
        state = play_bot_turn(state, actor)

    assert state.finish_groups == expected_groups


def test_multi_bot_api_feature_gate_contract_and_security() -> None:
    disabled = TestClient(create_app(settings=Settings(multiplayer_3_4_enabled=False)))

    legacy = disabled.post(
        "/api/games",
        content="null",
        headers={"content-type": "application/json"},
    )
    three_disabled = disabled.post("/api/games", json={"total_players": 3})
    four_disabled = disabled.post("/api/games", json={"total_players": 4})

    assert legacy.status_code == 201
    assert legacy.json()["total_players"] == 2
    assert three_disabled.status_code == 409
    assert three_disabled.json() == {"detail": {"code": "FEATURE_NOT_AVAILABLE"}}
    assert four_disabled.status_code == 409

    enabled = TestClient(create_app(settings=Settings(multiplayer_3_4_enabled=True)))
    for count in (2, 3, 4):
        response = enabled.post(
            "/api/games",
            json={"total_players": count, "human_display_name": "Milo"},
        )
        assert response.status_code == 201
        body = response.json()
        assert body["total_players"] == count
        assert len(body["participants"]) == count
        assert [participant["seat"] for participant in body["participants"]] == [
            seat.value for seat in (Seat.ONE, Seat.TWO, Seat.THREE, Seat.FOUR)[:count]
        ]
        assert body["participants"][0]["is_bot"] is False
        assert all(participant["is_bot"] for participant in body["participants"][1:])
        assert len({p["display_name"].casefold() for p in body["participants"]}) == count

    for invalid_count in (1, 5):
        assert enabled.post("/api/games", json={"total_players": invalid_count}).status_code == 422
    assert (
        enabled.post("/api/games", json={"total_players": 3, "bot_names": ["Alice"]}).status_code
        == 422
    )

    created = enabled.post("/api/games", json={"total_players": 3}).json()
    game_id = created["game_id"]
    impersonation = enabled.post(
        f"/api/games/{game_id}/actions",
        json={"action": "TAKE", "actor_seat": "two"},
    )
    assert impersonation.status_code == 422


def test_multi_bot_same_session_replay_preserves_roster_and_respects_live_gate() -> None:
    application = create_app(settings=Settings(multiplayer_3_4_enabled=True))
    client = TestClient(application)
    created = client.post("/api/games", json={"total_players": 4}).json()

    replay = client.post(f"/api/games/{created['game_id']}/restart")

    assert replay.status_code == 200
    body = replay.json()
    assert body["game_id"] == created["game_id"]
    assert body["total_players"] == 4
    identity_fields = ("participant_id", "seat", "display_name", "is_bot")
    assert [
        tuple(participant[field] for field in identity_fields)
        for participant in body["participants"]
    ] == [
        tuple(participant[field] for field in identity_fields)
        for participant in created["participants"]
    ]
    assert all(
        participant["active"] and not participant["finished"]
        for participant in body["participants"]
    )
    assert body["finish_groups"] == []
    assert (
        client.post(
            f"/api/games/{created['game_id']}/restart",
            json={"actor_seat": "two"},
        ).status_code
        == 422
    )

    application.state.settings = Settings(multiplayer_3_4_enabled=False)
    disabled_replay = client.post(f"/api/games/{created['game_id']}/restart")
    assert disabled_replay.status_code == 409
    assert disabled_replay.json() == {"detail": {"code": "FEATURE_NOT_AVAILABLE"}}


def test_multiplayer_api_projection_hides_every_bot_hand_and_future_deck_card() -> None:
    captured: list[GameSession] = []

    class CapturingService(GameSessionService):
        def create_game(self, **kwargs) -> GameSession:  # type: ignore[no-untyped-def]
            session = super().create_game(**kwargs)
            captured.append(session)
            return session

    service = CapturingService(
        multiplayer_game_factory=lambda count: create_new_game(
            random.Random(42), player_count=count
        )
    )
    client = TestClient(create_app(service, settings=Settings(multiplayer_3_4_enabled=True)))

    body = client.post("/api/games", json={"total_players": 4}).json()
    state = captured[0].state
    from kiba_api.api.cards import card_to_code

    def card_codes_in(value: object) -> set[str]:
        codes: set[str] = set()
        if isinstance(value, dict):
            code = value.get("code")
            if isinstance(code, str):
                codes.add(code)
            for child in value.values():
                codes.update(card_codes_in(child))
        elif isinstance(value, list):
            for child in value:
                codes.update(card_codes_in(child))
        return codes

    hidden = [
        *(card_to_code(value) for seat in captured[0].bot_seats for value in state.hand(seat)),
        *(card_to_code(value) for value in state.draw_pile[1:]),
    ]
    assert card_codes_in(body).isdisjoint(hidden)
    assert "draw_pile" not in body
    assert "bot_hand" not in body
