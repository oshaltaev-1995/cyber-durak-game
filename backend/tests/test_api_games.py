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
    assert body["bout_starting_attacker"] in {Seat.ONE.value, Seat.TWO.value}
    assert body["max_attack_card_addition"] is not None
    assert body["required_actor"] == "HUMAN"
    assert body["available_actions"]


def test_action_api_rejects_redundant_defense_without_mutating_state() -> None:
    attack = (card(Rank.ACE), card(Rank.ACE, Suit.DIAMONDS))
    defense = (
        card(Rank.ACE, Suit.HEARTS),
        card(Rank.ACE, Suit.SPADES),
        card(Rank.SIX),
        card(Rank.SIX, Suit.DIAMONDS),
    )
    state = start_game_bout(game(defense, (*attack, card(Rank.SEVEN)), attacker=Seat.TWO))
    state = play_game_initial_attack(state, Seat.TWO, attack)
    client, game_id = client_for_state(state)
    before = client.get(f"/api/games/{game_id}").json()

    response = client.post(
        f"/api/games/{game_id}/actions",
        json={"action": "DEFEND", "cards": [card_to_code(value) for value in defense]},
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "redundant_defense"
    assert client.get(f"/api/games/{game_id}").json() == before


def test_action_api_rejects_addition_above_current_defender_hand_limit() -> None:
    attack = (card(Rank.ACE), card(Rank.ACE, Suit.DIAMONDS))
    human_throw = (
        card(Rank.NINE, Suit.DIAMONDS),
        card(Rank.NINE, Suit.HEARTS),
        card(Rank.NINE, Suit.SPADES),
    )
    bot_defense = (
        card(Rank.SIX),
        card(Rank.SEVEN),
        card(Rank.EIGHT),
        card(Rank.NINE),
        card(Rank.JACK),
    )
    state = start_game_bout(
        game((*attack, *human_throw), (*bot_defense, card(Rank.KING), card(Rank.QUEEN)))
    )
    state = play_game_initial_attack(state, Seat.ONE, attack)
    state = play_game_defense(state, Seat.TWO, bot_defense)
    client, game_id = client_for_state(state)
    before = client.get(f"/api/games/{game_id}").json()

    assert before["attack_card_limit"] == 7
    assert before["total_attack_card_count"] == 2
    assert before["max_attack_card_addition"] == 2

    response = client.post(
        f"/api/games/{game_id}/actions",
        json={"action": "THROW_IN", "cards": [card_to_code(value) for value in human_throw]},
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "attack_card_limit_exceeded"
    assert client.get(f"/api/games/{game_id}").json() == before


def test_get_game_returns_same_current_public_snapshot() -> None:
    service = GameSessionService(game_factory=lambda: create_new_game(random.Random(7)))
    client = TestClient(create_app(service))
    created = client.post("/api/games").json()

    fetched = client.get(f"/api/games/{created['game_id']}")

    assert fetched.status_code == 200
    expected = dict(created)
    expected["recent_events"] = []
    assert fetched.json() == expected

    fetched_again = client.get(f"/api/games/{created['game_id']}")
    assert fetched_again.status_code == 200
    assert fetched_again.json() == expected


def test_completed_game_remains_retrievable_without_exposing_hidden_state() -> None:
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
    client = TestClient(create_app(service))
    created = client.post("/api/games").json()

    recovered = client.get(f"/api/games/{created['game_id']}")

    assert recovered.status_code == 200
    body = recovered.json()
    assert body["game_id"] == created["game_id"]
    assert body["phase"] == GamePhase.COMPLETE.value
    assert body["result"] == {
        "outcome": "WIN",
        "winner": "HUMAN",
        "winner_seat": Seat.ONE.value,
    }
    assert "bot_hand" not in body
    assert "draw_pile" not in body


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
    assert response.json()["last_bout_summary"] == {
        "outcome": "TAKE",
        "actor_seat": Seat.TWO.value,
        "table_card_count": 1,
    }
    assert fetched.json()["recent_events"] == []
    assert fetched.json()["last_bout_summary"] == response.json()["last_bout_summary"]
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


def test_hint_api_returns_canonical_read_only_suggestions_without_hidden_cards() -> None:
    nine = card(Rank.NINE)
    second_nine = card(Rank.NINE, Suit.DIAMONDS)
    king = card(Rank.KING)
    hidden = (card(Rank.ACE), card(Rank.SIX), card(Rank.EIGHT))
    draw_pile = (card(Rank.SEVEN, Suit.HEARTS), card(Rank.TEN, Suit.SPADES))
    state = start_game_bout(game((nine, second_nine, king), hidden, draw_pile=draw_pile))
    client, game_id = client_for_state(state)
    before = client.get(f"/api/games/{game_id}").json()

    response = client.post(
        f"/api/games/{game_id}/hints",
        json={"selected_card_ids": [card_to_code(nine)]},
    )

    assert response.status_code == 200
    body = response.json()
    assert card_to_code(second_nine) in body["suggested_card_ids"]
    assert body["combinations"]
    assert client.get(f"/api/games/{game_id}").json() == before
    hint_codes = {
        *body["selected_card_ids"],
        *body["suggested_card_ids"],
        *(code for combination in body["combinations"] for code in combination["card_ids"]),
        *(code for combination in body["combinations"] for code in combination["added_card_ids"]),
    }
    for hidden_card in (*hidden, *draw_pile[1:]):
        assert card_to_code(hidden_card) not in hint_codes


def test_hint_api_handles_empty_invalid_wrong_turn_complete_and_unknown_requests() -> None:
    human_state = start_game_bout(
        game((card(Rank.SIX), card(Rank.SEVEN)), (card(Rank.ACE), card(Rank.KING)))
    )
    client, game_id = client_for_state(human_state)

    empty = client.post(f"/api/games/{game_id}/hints", json={"selected_card_ids": []})
    foreign = client.post(f"/api/games/{game_id}/hints", json={"selected_card_ids": ["AC"]})
    duplicate = client.post(f"/api/games/{game_id}/hints", json={"selected_card_ids": ["6C", "6C"]})
    unknown = client.post("/api/games/unknown/hints", json={"selected_card_ids": ["6C"]})

    assert empty.status_code == 200
    assert empty.json()["combinations"] == []
    assert foreign.status_code == 409
    assert foreign.json() == {"detail": {"code": "card_not_owned"}}
    assert duplicate.status_code == 422
    assert duplicate.json() == {"detail": {"code": "duplicate_card_code"}}
    assert unknown.status_code == 404

    bot_turn = start_game_bout(
        game(
            (card(Rank.SIX), card(Rank.SEVEN)),
            (card(Rank.ACE), card(Rank.KING)),
            attacker=Seat.TWO,
        )
    )
    bot_client, bot_id = client_for_state(bot_turn)
    wrong_turn = bot_client.post(f"/api/games/{bot_id}/hints", json={"selected_card_ids": ["6C"]})
    assert wrong_turn.status_code == 409
    assert wrong_turn.json() == {"detail": {"code": "wrong_turn"}}

    complete = GameState(
        seat_one_hand=(),
        seat_two_hand=(card(Rank.SEVEN),),
        draw_pile=(),
        discard_pile=(),
        current_attacker=None,
        phase=GamePhase.COMPLETE,
        result=GameResult(GameOutcome.WIN, Seat.ONE),
    )
    complete_client, complete_id = client_for_state(complete)
    terminal = complete_client.post(
        f"/api/games/{complete_id}/hints", json={"selected_card_ids": []}
    )
    assert terminal.status_code == 409
    assert terminal.json() == {"detail": {"code": "game_complete"}}


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

    extended_transfer_state = start_game_bout(
        game(
            (card(Rank.SEVEN), card(Rank.SEVEN, Suit.DIAMONDS), card(Rank.SIX)),
            (
                card(Rank.SEVEN, Suit.HEARTS),
                card(Rank.EIGHT),
                card(Rank.NINE),
                card(Rank.TEN),
                card(Rank.JACK),
            ),
            attacker=Seat.TWO,
        )
    )
    extended_transfer_state = play_game_initial_attack(
        extended_transfer_state,
        Seat.TWO,
        (card(Rank.SEVEN, Suit.HEARTS),),
    )
    client, game_id = client_for_state(extended_transfer_state)
    extended_transfer = client.post(
        f"/api/games/{game_id}/actions",
        json={"action": "TRANSFER", "cards": ["7C", "7D"]},
    )
    assert extended_transfer.status_code == 200
    assert extended_transfer.json()["packets"][0]["attack_value"] == 21

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


def test_existing_value_reason_exposes_structured_public_source_card() -> None:
    six = card(Rank.SIX)
    attacking_queen = card(Rank.QUEEN, Suit.DIAMONDS)
    defending_queen = card(Rank.QUEEN)
    state = start_game_bout(
        game(
            (six, attacking_queen, card(Rank.SEVEN)),
            (defending_queen, card(Rank.ACE), card(Rank.EIGHT)),
        )
    )
    state = play_game_initial_attack(state, Seat.ONE, (six,))
    state = play_game_defense(state, Seat.TWO, (defending_queen,))
    state = play_game_throw_in(state, Seat.ONE, (attacking_queen,))
    client, game_id = client_for_state(state)

    reasons = client.get(f"/api/games/{game_id}").json()["packets"][1]["throw_in_reasons"]
    existing_value = next(reason for reason in reasons if reason["type"] == "existing_value")

    assert existing_value["expression"] is None
    assert existing_value["source_cards"] == [
        {
            "id": "deck-1:Q:clubs",
            "code": "QC",
            "rank": "Q",
            "suit": "clubs",
            "joker_color": None,
            "base_value": 15,
            "effective_value": 15,
            "is_trump": False,
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


def test_throw_in_packet_exposes_server_confirmed_rank_run_metadata() -> None:
    ten = card(Rank.TEN)
    attack_jack = card(Rank.JACK, Suit.DIAMONDS)
    attack_king = card(Rank.KING, Suit.DIAMONDS)
    queen = card(Rank.QUEEN)
    defense_jack = card(Rank.JACK)
    defense_king = card(Rank.KING)
    ace = card(Rank.ACE)
    state = start_game_bout(
        game(
            (ten, attack_jack, attack_king, queen, card(Rank.SIX)),
            (defense_jack, defense_king, ace, card(Rank.SEVEN)),
        )
    )
    state = play_game_initial_attack(state, Seat.ONE, (ten,))
    state = play_game_defense(state, Seat.TWO, (defense_jack,))
    state = play_game_throw_in(state, Seat.ONE, (attack_jack,))
    state = play_game_defense(state, Seat.TWO, (defense_king,))
    state = play_game_throw_in(state, Seat.ONE, (attack_king,))
    state = play_game_defense(state, Seat.TWO, (ace,))
    state = play_game_throw_in(state, Seat.ONE, (queen,))
    client, game_id = client_for_state(state)

    body = client.get(f"/api/games/{game_id}").json()

    assert body["packets"][3]["throw_in_reasons"] == [
        {
            "type": "arithmetic_mean",
            "target_value": 15,
            "expression": "90 / 6 = 15",
        },
        {
            "type": "rank_run",
            "target_value": None,
            "expression": "10–A",
            "run_start": "10",
            "run_end": "A",
            "run_length": 5,
            "run_ranks": ["10", "J", "Q", "K", "A"],
        },
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
