import json
import random
from collections.abc import Iterable

from fastapi.testclient import TestClient

from kiba_api.api.cards import card_to_code
from kiba_api.game import (
    Card,
    GameOutcome,
    GamePhase,
    GameResult,
    GameState,
    Rank,
    Seat,
    Suit,
    create_new_game,
    play_game_defense,
    play_game_initial_attack,
    play_game_throw_in,
    start_game_bout,
)
from kiba_api.main import create_app
from kiba_api.sessions import GameSessionService, InMemoryGameSessionStore


def card(rank: Rank, suit: Suit = Suit.CLUBS) -> Card:
    return Card(rank=rank, suit=suit)


def game(
    seat_one_hand: Iterable[Card],
    seat_two_hand: Iterable[Card],
    *,
    attacker: Seat = Seat.ONE,
    draw_pile: Iterable[Card] = (),
) -> GameState:
    return GameState(
        seat_one_hand=tuple(seat_one_hand),
        seat_two_hand=tuple(seat_two_hand),
        draw_pile=tuple(draw_pile),
        discard_pile=(),
        current_attacker=attacker,
    )


def client_for_state(state: GameState) -> tuple[TestClient, str]:
    store = InMemoryGameSessionStore(id_factory=lambda: "test-game")
    session = store.create(state)
    service = GameSessionService(store=store)
    return TestClient(create_app(service)), session.game_id


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


def test_create_game_returns_public_human_vs_bot_state() -> None:
    service = GameSessionService(game_factory=lambda: create_new_game(random.Random(42)))
    client = TestClient(create_app(service))

    response = client.post("/api/games")

    assert response.status_code == 201
    body = response.json()
    assert body["phase"] == GamePhase.BOUT_ACTIVE.value
    assert body["human_seat"] == Seat.ONE.value
    assert body["bot_seat"] == Seat.TWO.value
    assert len(body["human_hand"]) <= 7
    assert body["bot_hand_count"] <= 7
    assert body["draw_pile_count"] == 22
    assert body["discard_count"] == 0
    assert body["result"] is None
    assert body["bout_phase"] is not None
    assert body["required_actor"] == "HUMAN"
    assert body["available_actions"]


def test_get_game_returns_same_current_public_snapshot() -> None:
    service = GameSessionService(game_factory=lambda: create_new_game(random.Random(7)))
    client = TestClient(create_app(service))
    created = client.post("/api/games").json()

    fetched = client.get(f"/api/games/{created['game_id']}")

    assert fetched.status_code == 200
    expected = dict(created)
    expected["recent_events"] = []
    assert fetched.json() == expected


def test_action_response_contains_transient_safe_bot_take_event() -> None:
    initial = game(
        (card(Rank.KING), card(Rank.ACE)),
        (card(Rank.SIX), card(Rank.SEVEN)),
    )
    service = GameSessionService(game_factory=lambda: initial)
    client = TestClient(create_app(service))
    game_id = client.post("/api/games").json()["game_id"]

    response = client.post(
        f"/api/games/{game_id}/actions",
        json={"action": "INITIAL_ATTACK", "cards": ["KC"]},
    )
    fetched = client.get(f"/api/games/{game_id}")

    assert response.status_code == 200
    assert response.json()["recent_events"] == [
        {
            "type": "BOT_TAKE",
            "actor": "BOT",
            "card_count": 1,
            "value": None,
            "target": 18,
        }
    ]
    assert fetched.json()["recent_events"] == []
    event_json = json.dumps(response.json()["recent_events"])
    assert "6C" not in event_json
    assert "7C" not in event_json


def test_public_response_hides_bot_hand_and_future_draw_order() -> None:
    initial = create_new_game(random.Random(42))
    service = GameSessionService(game_factory=lambda: initial)
    client = TestClient(create_app(service))

    body = client.post("/api/games").json()
    current = service.get_game(body["game_id"]).state
    bot_codes = {card_to_code(value) for value in current.seat_two_hand}
    hidden_draw_codes = {card_to_code(value) for value in current.draw_pile[1:]}
    exposed_codes = card_codes_in(body)

    assert exposed_codes.isdisjoint(bot_codes)
    assert exposed_codes.isdisjoint(hidden_draw_codes)
    assert body["bot_hand_count"] == len(current.seat_two_hand)
    assert body["draw_pile_count"] == len(current.draw_pile)
    assert body["exposed_top_card"]["code"] == card_to_code(current.draw_pile[0])
    assert "draw_pile" not in body
    assert "bot_hand" not in body
    serialized = json.dumps(body)
    assert "rng" not in serialized.lower()


def test_unknown_game_returns_machine_readable_404() -> None:
    client = TestClient(create_app(GameSessionService()))

    response = client.get("/api/games/unknown")

    assert response.status_code == 404
    assert response.json() == {"detail": {"code": "game_not_found"}}


def test_legal_and_illegal_initial_attack_use_domain_authority() -> None:
    nine = card(Rank.NINE)
    seven = card(Rank.SEVEN)
    initial = game((nine, seven), (card(Rank.ACE), card(Rank.KING)))
    service = GameSessionService(game_factory=lambda: initial)
    client = TestClient(create_app(service))
    created = client.post("/api/games").json()
    game_id = created["game_id"]

    illegal = client.post(
        f"/api/games/{game_id}/actions",
        json={"action": "INITIAL_ATTACK", "cards": ["9C", "7C"]},
    )
    legal = client.post(
        f"/api/games/{game_id}/actions",
        json={"action": "INITIAL_ATTACK", "cards": ["7C"]},
    )

    assert illegal.status_code == 409
    assert illegal.json() == {"detail": {"code": "illegal_initial_attack"}}
    assert legal.status_code == 200


def test_unowned_duplicate_and_malformed_card_codes_are_rejected() -> None:
    initial = game(
        (card(Rank.SIX), card(Rank.SEVEN)),
        (card(Rank.ACE), card(Rank.KING)),
    )
    service = GameSessionService(game_factory=lambda: initial)
    client = TestClient(create_app(service))
    game_id = client.post("/api/games").json()["game_id"]

    unowned = client.post(
        f"/api/games/{game_id}/actions",
        json={"action": "INITIAL_ATTACK", "cards": ["AC"]},
    )
    duplicate = client.post(
        f"/api/games/{game_id}/actions",
        json={"action": "INITIAL_ATTACK", "cards": ["6C", "6C"]},
    )
    malformed = client.post(
        f"/api/games/{game_id}/actions",
        json={"action": "INITIAL_ATTACK", "cards": ["clubs-six"]},
    )

    assert unowned.status_code == 409
    assert unowned.json() == {"detail": {"code": "card_not_owned"}}
    assert duplicate.status_code == 422
    assert duplicate.json() == {"detail": {"code": "duplicate_card_code"}}
    assert malformed.status_code == 422
    assert malformed.json() == {"detail": {"code": "invalid_card_code"}}


def test_action_schema_is_discriminated_and_forbids_wrong_card_shape() -> None:
    service = GameSessionService(
        game_factory=lambda: game(
            (card(Rank.SIX),),
            (card(Rank.ACE),),
        )
    )
    client = TestClient(create_app(service))
    game_id = client.post("/api/games").json()["game_id"]

    missing_cards = client.post(
        f"/api/games/{game_id}/actions",
        json={"action": "INITIAL_ATTACK"},
    )
    cards_on_take = client.post(
        f"/api/games/{game_id}/actions",
        json={"action": "TAKE", "cards": ["6C"]},
    )

    assert missing_cards.status_code == 422
    assert missing_cards.json()["detail"]["code"] == "invalid_request"
    assert cards_on_take.status_code == 422
    assert cards_on_take.json()["detail"]["code"] == "invalid_request"


def test_human_defense_transfer_take_throw_in_and_bito_routes() -> None:
    king = card(Rank.KING)
    jack = card(Rank.JACK)

    defense_state = start_game_bout(
        game(
            (card(Rank.ACE), card(Rank.SIX)),
            (jack, card(Rank.SEVEN), card(Rank.EIGHT)),
            attacker=Seat.TWO,
        )
    )
    defense_state = play_game_initial_attack(defense_state, Seat.TWO, (jack,))
    client, game_id = client_for_state(defense_state)
    defense = client.post(
        f"/api/games/{game_id}/actions",
        json={"action": "DEFEND", "cards": ["AC"]},
    )
    assert defense.status_code == 200

    transfer_state = start_game_bout(
        game(
            (card(Rank.NINE), card(Rank.NINE, Suit.DIAMONDS)),
            (king, card(Rank.SIX), card(Rank.SEVEN), card(Rank.EIGHT)),
            attacker=Seat.TWO,
        )
    )
    transfer_state = play_game_initial_attack(transfer_state, Seat.TWO, (king,))
    client, game_id = client_for_state(transfer_state)
    transfer = client.post(
        f"/api/games/{game_id}/actions",
        json={"action": "TRANSFER", "cards": ["9C", "9D"]},
    )
    assert transfer.status_code == 200

    take_state = start_game_bout(
        game(
            (card(Rank.SIX),),
            (king, card(Rank.SEVEN)),
            attacker=Seat.TWO,
        )
    )
    take_state = play_game_initial_attack(take_state, Seat.TWO, (king,))
    client, game_id = client_for_state(take_state)
    take = client.post(
        f"/api/games/{game_id}/actions",
        json={"action": "TAKE"},
    )
    assert take.status_code == 200

    throw_state = start_game_bout(
        game(
            (jack, card(Rank.QUEEN), card(Rank.SIX)),
            (king, card(Rank.ACE), card(Rank.SEVEN)),
        )
    )
    throw_state = play_game_initial_attack(throw_state, Seat.ONE, (jack,))
    throw_state = play_game_defense(throw_state, Seat.TWO, (king,))

    throw_client, throw_id = client_for_state(throw_state)
    throw_in = throw_client.post(
        f"/api/games/{throw_id}/actions",
        json={"action": "THROW_IN", "cards": ["QC"]},
    )
    assert throw_in.status_code == 200

    bito_client, bito_id = client_for_state(throw_state)
    bito = bito_client.post(
        f"/api/games/{bito_id}/actions",
        json={"action": "BITO"},
    )
    assert bito.status_code == 200


def test_table_response_preserves_packets_anchors_total_and_exact_mean() -> None:
    jack = card(Rank.JACK)
    king = card(Rank.KING)
    state = start_game_bout(
        game(
            (jack, card(Rank.QUEEN), card(Rank.SIX)),
            (king, card(Rank.ACE), card(Rank.SEVEN)),
        )
    )
    state = play_game_initial_attack(state, Seat.ONE, (jack,))
    state = play_game_defense(state, Seat.TWO, (king,))
    client, game_id = client_for_state(state)

    body = client.get(f"/api/games/{game_id}").json()

    assert [value["code"] for value in body["table_cards"]] == ["JC", "KC"]
    assert [value["code"] for value in body["direct_anchor_cards"]] == ["KC"]
    assert body["table_arithmetic"] == {
        "total_effective_value": 30,
        "physical_card_count": 2,
        "arithmetic_mean": "15",
    }
    assert body["packets"] == [
        {
            "attack_cards": [body["table_cards"][0]],
            "attack_value": 12,
            "defense_cards": [body["table_cards"][1]],
            "defense_value": 18,
            "closed": True,
            "throw_in_reasons": [],
        }
    ]
    assert body["active_packet"] is None
    assert body["available_actions"] == ["THROW_IN", "BITO"]


def test_throw_in_packet_exposes_server_confirmed_mean_explanation() -> None:
    jack = card(Rank.JACK)
    queen = card(Rank.QUEEN)
    king = card(Rank.KING)
    state = start_game_bout(
        game(
            (jack, queen, card(Rank.SIX)),
            (king, card(Rank.ACE), card(Rank.SEVEN)),
        )
    )
    state = play_game_initial_attack(state, Seat.ONE, (jack,))
    state = play_game_defense(state, Seat.TWO, (king,))
    state = play_game_throw_in(state, Seat.ONE, (queen,))
    client, game_id = client_for_state(state)

    body = client.get(f"/api/games/{game_id}").json()

    assert body["packets"][1]["throw_in_reasons"] == [
        {
            "type": "arithmetic_mean",
            "target_value": 15,
            "expression": "30 / 2 = 15",
        }
    ]


def test_throw_in_packet_exposes_server_confirmed_latest_defense_total() -> None:
    jack = card(Rank.JACK)
    queen = card(Rank.QUEEN)
    ace = card(Rank.ACE)
    defense_jack = card(Rank.JACK, Suit.DIAMONDS)
    eight = card(Rank.EIGHT)
    state = start_game_bout(
        game(
            (jack, queen, ace, card(Rank.SIX), card(Rank.SEVEN)),
            (
                card(Rank.KING),
                defense_jack,
                eight,
                card(Rank.NINE),
                card(Rank.TEN),
                card(Rank.ACE, Suit.DIAMONDS),
            ),
        )
    )
    state = play_game_initial_attack(state, Seat.ONE, (jack,))
    state = play_game_defense(state, Seat.TWO, (card(Rank.KING),))
    state = play_game_throw_in(state, Seat.ONE, (queen,))
    state = play_game_defense(state, Seat.TWO, (defense_jack, eight))
    state = play_game_throw_in(state, Seat.ONE, (ace,))
    client, game_id = client_for_state(state)

    body = client.get(f"/api/games/{game_id}").json()

    assert body["packets"][2]["throw_in_reasons"] == [
        {
            "type": "defense_total",
            "target_value": 20,
            "expression": "12 + 8 = 20",
        }
    ]


def test_completed_response_preserves_the_decisive_bout_context() -> None:
    jack = card(Rank.JACK)
    ace = card(Rank.ACE)
    state = start_game_bout(game((ace,), (jack,), attacker=Seat.TWO))
    state = play_game_initial_attack(state, Seat.TWO, (jack,))
    client, game_id = client_for_state(state)

    response = client.post(
        f"/api/games/{game_id}/actions",
        json={"action": "DEFEND", "cards": ["AC"]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["phase"] == "complete"
    assert body["result"] == {"outcome": "DRAW", "winner": None, "winner_seat": None}
    assert [value["code"] for value in body["table_cards"]] == ["JC", "AC"]
    assert body["table_arithmetic"] == {
        "total_effective_value": 32,
        "physical_card_count": 2,
        "arithmetic_mean": "16",
    }
    assert body["bout_phase"] == "complete"
    assert len(body["packets"]) == 1
    assert body["available_actions"] == []


def test_illegal_defense_and_wrong_turn_return_conflicts_without_mutation() -> None:
    jack = card(Rank.JACK)
    ten = card(Rank.TEN)
    state = start_game_bout(
        game(
            (ten, card(Rank.SIX)),
            (jack, card(Rank.SEVEN)),
            attacker=Seat.TWO,
        )
    )
    state = play_game_initial_attack(state, Seat.TWO, (jack,))
    client, game_id = client_for_state(state)

    illegal = client.post(
        f"/api/games/{game_id}/actions",
        json={"action": "DEFEND", "cards": ["10C"]},
    )
    after = client.get(f"/api/games/{game_id}")

    assert illegal.status_code == 409
    assert illegal.json() == {"detail": {"code": "illegal_defense"}}
    assert after.json()["human_hand"][1]["code"] == "10C"

    bot_turn_client, bot_turn_id = client_for_state(
        game((card(Rank.SIX),), (jack,), attacker=Seat.TWO)
    )
    wrong_turn = bot_turn_client.post(
        f"/api/games/{bot_turn_id}/actions",
        json={"action": "INITIAL_ATTACK", "cards": ["6C"]},
    )
    assert wrong_turn.status_code == 409
    assert wrong_turn.json() == {"detail": {"code": "not_human_turn"}}


def test_completed_api_result_uses_human_bot_semantics_and_rejects_actions() -> None:
    completed = GameState(
        seat_one_hand=(),
        seat_two_hand=(card(Rank.SIX),),
        draw_pile=(),
        discard_pile=(),
        current_attacker=None,
        phase=GamePhase.COMPLETE,
        result=GameResult(GameOutcome.WIN, Seat.ONE),
    )
    client, game_id = client_for_state(completed)

    fetched = client.get(f"/api/games/{game_id}")
    action = client.post(f"/api/games/{game_id}/actions", json={"action": "BITO"})

    assert fetched.json()["result"] == {
        "outcome": "WIN",
        "winner": "HUMAN",
        "winner_seat": "one",
    }
    assert fetched.json()["available_actions"] == []
    assert action.status_code == 409
    assert action.json() == {"detail": {"code": "game_complete"}}


def test_complete_game_can_be_played_only_through_rest_actions() -> None:
    service = GameSessionService(game_factory=lambda: create_new_game(random.Random(42)))
    client = TestClient(create_app(service))
    response = client.post("/api/games")
    action_count = 0

    while response.json()["phase"] != GamePhase.COMPLETE.value and action_count < 500:
        state = response.json()
        game_id = state["game_id"]
        available = state["available_actions"]
        if "INITIAL_ATTACK" in available:
            payload = {
                "action": "INITIAL_ATTACK",
                "cards": [state["human_hand"][0]["code"]],
            }
        elif "TAKE" in available:
            payload = {"action": "TAKE"}
        else:
            assert "BITO" in available
            payload = {"action": "BITO"}

        response = client.post(f"/api/games/{game_id}/actions", json=payload)
        assert response.status_code == 200
        action_count += 1

    assert action_count < 500
    final = response.json()
    assert final["phase"] == GamePhase.COMPLETE.value
    assert final["result"]["outcome"] in {"WIN", "DRAW"}
    assert final["packets"]
    assert final["table_cards"]
