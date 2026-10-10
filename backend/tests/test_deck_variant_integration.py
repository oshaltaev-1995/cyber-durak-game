from __future__ import annotations

import random
from dataclasses import replace
from time import perf_counter
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from kiba_api.api.serialization import serialize_move_hints
from kiba_api.config import Settings
from kiba_api.game import (
    DEFAULT_DECK_CONFIG,
    BotActionType,
    Card,
    DeckConfig,
    DeckProfile,
    GameOutcome,
    GamePhase,
    GameResult,
    GameState,
    JokerColor,
    Rank,
    Seat,
    Suit,
    build_bot_context,
    choose_bot_action,
    create_deck,
    create_new_game,
    play_game_defense,
    play_game_initial_attack,
    ranks_for_profile,
    start_game_bout,
)
from kiba_api.game.bot import _initial_street_candidates, _rank_run_candidates
from kiba_api.main import create_app
from kiba_api.pvp import PvPRoomPhase, PvPRoomService
from kiba_api.sessions import GameSessionService, HumanActionType, acting_seat, get_move_hints

ORIGIN = "http://testserver"
ALL_CONFIGS = tuple(DeckConfig(profile, count) for profile in DeckProfile for count in (1, 2))


def card(
    rank: Rank,
    suit: Suit = Suit.CLUBS,
    *,
    copy: int = 1,
) -> Card:
    return Card(rank, suit, deck_copy=copy)


def joker(color: JokerColor, *, copy: int = 1) -> Card:
    return Card(Rank.JOKER, joker_color=color, deck_copy=copy)


def enabled_settings() -> Settings:
    return Settings(
        database_url="sqlite://",
        csrf_trusted_origins=(ORIGIN,),
        multiplayer_3_4_enabled=True,
        deck_variants_enabled=True,
    )


def test_deck_variant_flag_defaults_off_and_composes_independently() -> None:
    with TestClient(create_app(settings=Settings(database_url="sqlite://"))) as client:
        assert client.get("/api/capabilities").json() == {
            "multiplayer_3_4_enabled": False,
            "deck_variants_enabled": False,
        }
        omitted = client.post("/api/games")
        explicit_default = client.post(
            "/api/games",
            json={"deck_profile": "classic", "deck_count": 1},
        )
        variant_bot = client.post(
            "/api/games",
            json={"deck_profile": "extended", "deck_count": 1},
        )
        variant_pvp = client.post(
            "/api/pvp/rooms",
            json={"nickname": "Creator", "deck_profile": "classic", "deck_count": 2},
        )

    assert omitted.status_code == explicit_default.status_code == 201
    assert (omitted.json()["deck_profile"], omitted.json()["deck_count"]) == ("classic", 1)
    assert variant_bot.status_code == variant_pvp.status_code == 409
    assert variant_bot.json()["detail"]["code"] == "FEATURE_NOT_AVAILABLE"

    deck_only = Settings(database_url="sqlite://", deck_variants_enabled=True)
    with TestClient(create_app(settings=deck_only)) as client:
        two_extended = client.post(
            "/api/games",
            json={"deck_profile": "extended", "deck_count": 1},
        )
        three_extended = client.post(
            "/api/games",
            json={"total_players": 3, "deck_profile": "extended", "deck_count": 1},
        )
    assert two_extended.status_code == 201
    assert three_extended.status_code == 409


@pytest.mark.parametrize(
    "payload",
    [
        {"deck_profile": "unknown", "deck_count": 1},
        {"deck_profile": "classic", "deck_count": 0},
        {"deck_profile": "classic", "deck_count": 3},
        {"deck_profile": "classic", "deck_count": -1},
        {"deck_profile": "classic", "deck_count": "2"},
        {"deck_profile": None, "deck_count": 1},
        {"deck_profile": "classic", "deck_count": None},
    ],
)
def test_invalid_deck_configuration_is_not_coerced(payload: dict[str, object]) -> None:
    with TestClient(create_app(settings=enabled_settings())) as client:
        bot = client.post("/api/games", json=payload)
        pvp = client.post("/api/pvp/rooms", json={"nickname": "Creator", **payload})

    assert bot.status_code == pvp.status_code == 422
    assert bot.json()["detail"]["code"] == pvp.json()["detail"]["code"] == "invalid_request"


@pytest.mark.parametrize("config", ALL_CONFIGS)
@pytest.mark.parametrize("player_count", [2, 3, 4])
def test_bot_api_creates_every_deck_and_player_count(
    config: DeckConfig,
    player_count: int,
) -> None:
    with TestClient(create_app(settings=enabled_settings())) as client:
        response = client.post(
            "/api/games",
            json={
                "total_players": player_count,
                "deck_profile": config.profile.value,
                "deck_count": config.deck_count,
            },
        )
        session = client.app.state.game_service.get_game(response.json()["game_id"])
        assert len(session.state.all_cards) == config.card_count
        assert len({value.physical_id for value in session.state.all_cards}) == config.card_count

    assert response.status_code == 201
    body = response.json()
    assert body["deck_profile"] == config.profile.value
    assert body["deck_count"] == config.deck_count
    assert body["total_players"] == player_count
    visible_cards = [*body["human_hand"], *body["table_cards"]]
    if body["exposed_top_card"] is not None:
        visible_cards.append(body["exposed_top_card"])
    assert all(value["id"].startswith("deck-") for value in visible_cards)


def test_bot_restart_preserves_variant_and_rechecks_live_gate() -> None:
    settings = enabled_settings()
    with TestClient(create_app(settings=settings)) as client:
        created = client.post(
            "/api/games",
            json={"deck_profile": "extended", "deck_count": 2},
        ).json()
        before = client.app.state.game_service.get_game(created["game_id"])
        restarted = client.post(f"/api/games/{created['game_id']}/restart")
        after = client.app.state.game_service.get_game(created["game_id"])
        client.app.state.settings = replace(settings, deck_variants_enabled=False)
        blocked = client.post(f"/api/games/{created['game_id']}/restart")

    assert restarted.status_code == 200
    assert (restarted.json()["deck_profile"], restarted.json()["deck_count"]) == ("extended", 2)
    assert {id(value) for value in before.state.all_cards}.isdisjoint(
        id(value) for value in after.state.all_cards
    )
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["code"] == "FEATURE_NOT_AVAILABLE"


@pytest.mark.parametrize(
    ("config", "street"),
    [
        (
            DeckConfig(DeckProfile.CLASSIC, 1),
            tuple(card(rank) for rank in (Rank.SIX, Rank.SEVEN, Rank.EIGHT, Rank.NINE, Rank.TEN)),
        ),
        (
            DeckConfig(DeckProfile.EXTENDED, 1),
            tuple(card(rank) for rank in (Rank.TWO, Rank.THREE, Rank.FOUR, Rank.FIVE, Rank.SIX)),
        ),
        (
            DeckConfig(DeckProfile.CLASSIC, 2),
            tuple(card(rank) for rank in (Rank.SIX, Rank.SEVEN, Rank.EIGHT, Rank.NINE, Rank.TEN)),
        ),
        (
            DeckConfig(DeckProfile.EXTENDED, 1),
            (
                card(Rank.TEN),
                card(Rank.JACK),
                card(Rank.QUEEN),
                card(Rank.KING),
                card(Rank.ACE),
                joker(JokerColor.RED),
            ),
        ),
    ],
)
def test_bot_can_choose_profile_aware_initial_streets(
    config: DeckConfig,
    street: tuple[Card, ...],
) -> None:
    defender = tuple(card(rank, Suit.DIAMONDS) for rank in ranks_for_profile(config.profile)[:7])
    state = start_game_bout(
        GameState(
            hands=(street, defender),
            draw_pile=(),
            current_attacker=Seat.ONE,
            deck_config=config,
        )
    )

    action = choose_bot_action(state, Seat.ONE)

    assert action.action_type is BotActionType.INITIAL_ATTACK
    assert len({value.rank for value in action.cards}) >= 5


def test_double_deck_bot_street_candidates_keep_duplicate_instances() -> None:
    config = DeckConfig(DeckProfile.CLASSIC, 2)
    cards = (
        card(Rank.SIX),
        card(Rank.SEVEN),
        card(Rank.EIGHT),
        card(Rank.NINE),
        card(Rank.TEN),
        card(Rank.TEN, copy=2),
    )

    candidates = _initial_street_candidates(cards, config, capacity=6)

    assert any(
        len(value) == 6 and value[-1].physical_id != value[-2].physical_id for value in candidates
    )


def test_bot_post_response_candidates_include_d36_duplicate_queen() -> None:
    config = DeckConfig(DeckProfile.CLASSIC, 2)
    street = tuple(
        card(rank, Suit.HEARTS) for rank in (Rank.TEN, Rank.JACK, Rank.QUEEN, Rank.KING, Rank.ACE)
    )
    extra_queen = card(Rank.QUEEN, Suit.HEARTS, copy=2)
    defense = (
        card(Rank.ACE),
        card(Rank.ACE, copy=2),
        card(Rank.KING),
        card(Rank.KING, copy=2),
    )
    state = start_game_bout(
        GameState(
            hands=(
                (*street, extra_queen),
                (*defense, card(Rank.SIX, Suit.DIAMONDS), card(Rank.SEVEN), card(Rank.EIGHT)),
            ),
            draw_pile=(),
            current_attacker=Seat.ONE,
            deck_config=config,
        )
    )
    state = play_game_initial_attack(state, Seat.ONE, street)
    state = play_game_defense(state, Seat.TWO, defense)

    candidates = _rank_run_candidates(build_bot_context(state, Seat.ONE))

    assert (extra_queen,) in candidates


@pytest.mark.parametrize(
    ("config", "selected"),
    [
        (
            DeckConfig(DeckProfile.CLASSIC, 1),
            tuple(card(rank) for rank in (Rank.SIX, Rank.SEVEN, Rank.EIGHT, Rank.NINE, Rank.TEN)),
        ),
        (
            DeckConfig(DeckProfile.EXTENDED, 1),
            tuple(card(rank) for rank in (Rank.TWO, Rank.THREE, Rank.FOUR, Rank.FIVE, Rank.SIX)),
        ),
        (
            DeckConfig(DeckProfile.EXTENDED, 2),
            (
                card(Rank.TEN),
                card(Rank.JACK),
                card(Rank.QUEEN),
                card(Rank.KING),
                card(Rank.ACE),
                joker(JokerColor.BLACK),
            ),
        ),
    ],
)
def test_two_player_hints_discover_initial_streets_with_exact_ids(
    config: DeckConfig,
    selected: tuple[Card, ...],
) -> None:
    defender = tuple(card(rank, Suit.DIAMONDS) for rank in ranks_for_profile(config.profile)[:7])
    state = start_game_bout(
        GameState(
            hands=(selected, defender),
            draw_pile=(),
            current_attacker=Seat.ONE,
            deck_config=config,
        )
    )

    response = serialize_move_hints(get_move_hints(state, Seat.ONE, selected))

    assert response.combinations[0].reason == "rank_run"
    assert response.combinations[0].physical_card_ids == [value.physical_id for value in selected]


def test_double_deck_hints_return_distinct_exact_duplicate_ids_with_bounded_runtime() -> None:
    config = DeckConfig(DeckProfile.EXTENDED, 2)
    first = card(Rank.KING, Suit.HEARTS)
    second = card(Rank.KING, Suit.HEARTS, copy=2)
    extra = tuple(
        value
        for value in create_new_game(
            random.Random(4),
            player_count=2,
            deck_config=config,
        ).all_cards
        if value not in {first, second}
    )[:18]
    defender = tuple(value for value in extra[:7])
    hand = (first, second, *extra[7:])
    state = start_game_bout(
        GameState(
            hands=(hand, defender),
            draw_pile=(),
            current_attacker=Seat.ONE,
            deck_config=config,
        )
    )

    started = perf_counter()
    response = serialize_move_hints(get_move_hints(state, Seat.ONE, (first,)))
    elapsed = perf_counter() - started

    assert second.physical_id in response.suggested_physical_ids
    assert first.physical_id != second.physical_id
    assert elapsed < 2.0


def _duplicate_ready_game(player_count: int, config: DeckConfig) -> GameState:
    assert config == DeckConfig(DeckProfile.CLASSIC, 2)
    assert player_count in {2, 4}
    one = (
        card(Rank.KING, Suit.HEARTS),
        card(Rank.KING, Suit.HEARTS, copy=2),
        card(Rank.SIX),
    )
    hands = [one]
    suits = (Suit.DIAMONDS, Suit.HEARTS, Suit.SPADES)
    for index in range(1, player_count):
        hands.append(
            (
                card(Rank.SEVEN, suits[index - 1]),
                card(Rank.EIGHT, suits[index - 1]),
                card(Rank.NINE, suits[index - 1]),
            )
        )
    return GameState(
        hands=tuple(hands),
        draw_pile=(
            card(Rank.SIX, Suit.SPADES),
            card(Rank.SEVEN, Suit.SPADES, copy=2),
        ),
        current_attacker=Seat.ONE,
        deck_config=config,
    )


def test_pvp_double_deck_websocket_selects_only_one_exact_duplicate() -> None:
    service = PvPRoomService(configured_game_factory=_duplicate_ready_game)
    with TestClient(create_app(settings=enabled_settings(), pvp_service=service)) as client:
        creator = client.post(
            "/api/pvp/rooms",
            json={
                "nickname": "Creator",
                "deck_profile": "classic",
                "deck_count": 2,
            },
        ).json()
        joiner = client.post(
            f"/api/pvp/rooms/{creator['invite_code']}/join",
            json={"nickname": "Friend"},
        ).json()
        with client.websocket_connect(
            f"/api/pvp/rooms/{creator['invite_code']}/ws",
            headers={"Origin": ORIGIN},
        ) as socket:
            socket.send_json(
                {"type": "AUTH", "credential": creator["credential"]["reconnect_token"]}
            )
            state = socket.receive_json()["state"]
            duplicates = [value for value in state["hand"] if value["code"] == "KH"]
            assert len(duplicates) == 2
            assert duplicates[0]["id"] != duplicates[1]["id"]
            assert {value["id"] for value in state["hand"]}.isdisjoint(
                {value["id"] for value in joiner["state"]["hand"]}
            )
            selected_id, remaining_id = duplicates[0]["id"], duplicates[1]["id"]
            socket.send_json(
                {
                    "type": "ACTION",
                    "version": state["version"],
                    "action": "INITIAL_ATTACK",
                    "card_ids": [selected_id],
                }
            )
            updated = socket.receive_json()["state"]

        assert selected_id not in {value["id"] for value in updated["hand"]}
        assert remaining_id in {value["id"] for value in updated["hand"]}
        assert [value["id"] for value in updated["table_cards"]] == [selected_id]


def test_variant_actions_reject_legacy_ambiguity_conflicts_and_non_owned_ids() -> None:
    service = PvPRoomService(configured_game_factory=_duplicate_ready_game)
    with TestClient(create_app(settings=enabled_settings(), pvp_service=service)) as client:
        creator = client.post(
            "/api/pvp/rooms",
            json={
                "nickname": "Creator",
                "deck_profile": "classic",
                "deck_count": 2,
            },
        ).json()
        joiner = client.post(
            f"/api/pvp/rooms/{creator['invite_code']}/join",
            json={"nickname": "Friend"},
        ).json()
        with client.websocket_connect(
            f"/api/pvp/rooms/{creator['invite_code']}/ws",
            headers={"Origin": ORIGIN},
        ) as socket:
            socket.send_json(
                {"type": "AUTH", "credential": creator["credential"]["reconnect_token"]}
            )
            state = socket.receive_json()["state"]
            owned = state["hand"][0]
            foreign = joiner["state"]["hand"][0]["id"]
            hidden_draw = card(Rank.SEVEN, Suit.SPADES, copy=2).physical_id
            payload = {
                "type": "ACTION",
                "version": 0,
                "action": "INITIAL_ATTACK",
            }
            socket.send_json({**payload, "cards": ["KH"]})
            legacy = socket.receive_json()
            socket.send_json({**payload, "cards": [owned["code"]], "card_ids": [owned["id"]]})
            conflict = socket.receive_json()
            socket.send_json({**payload, "card_ids": [foreign]})
            not_owned = socket.receive_json()
            socket.send_json({**payload, "card_ids": [hidden_draw]})
            hidden = socket.receive_json()
            socket.send_json({**payload, "card_ids": [owned["id"], owned["id"]]})
            duplicate = socket.receive_json()
            socket.send_json({**payload, "card_ids": [owned["id"]], "deck_count": 1})
            config_injection = socket.receive_json()

    assert legacy["error"]["domain_code"] == "legacy_card_reference_not_available"
    assert conflict["error"]["domain_code"] == "invalid_request"
    assert not_owned["error"]["domain_code"] == "card_not_owned"
    assert hidden["error"]["domain_code"] == "card_not_owned"
    assert duplicate["error"]["domain_code"] == "duplicate_card_id"
    assert config_injection["error"]["domain_code"] == "invalid_request"


def _extended_ready_game(player_count: int, config: DeckConfig) -> GameState:
    assert config.profile is DeckProfile.EXTENDED
    hands = [
        (card(Rank.SIX), card(Rank.ACE), card(Rank.TWO)),
        (card(Rank.SEVEN), joker(JokerColor.RED), card(Rank.THREE)),
    ]
    if player_count >= 3:
        hands.append((card(Rank.EIGHT), joker(JokerColor.BLACK), card(Rank.FOUR)))
    if player_count == 4:
        hands.append(
            (
                card(Rank.NINE),
                card(Rank.TEN),
                card(Rank.FIVE),
            )
        )
    return GameState(
        hands=tuple(hands),
        draw_pile=(),
        current_attacker=Seat.ONE,
        deck_config=config,
    )


def test_extended_pvp_action_defense_and_reconnect_preserve_joker_identity() -> None:
    service = PvPRoomService(configured_game_factory=_extended_ready_game)
    with TestClient(create_app(settings=enabled_settings(), pvp_service=service)) as client:
        creator = client.post(
            "/api/pvp/rooms",
            json={"nickname": "Creator", "deck_profile": "extended", "deck_count": 1},
        ).json()
        joiner = client.post(
            f"/api/pvp/rooms/{creator['invite_code']}/join",
            json={"nickname": "Friend"},
        ).json()
        path = f"/api/pvp/rooms/{creator['invite_code']}/ws"
        with client.websocket_connect(path, headers={"Origin": ORIGIN}) as attacker:
            attacker.send_json(
                {"type": "AUTH", "credential": creator["credential"]["reconnect_token"]}
            )
            state = attacker.receive_json()["state"]
            six = next(value for value in state["hand"] if value["code"] == "6C")
            attacker.send_json(
                {
                    "type": "ACTION",
                    "version": 0,
                    "action": "INITIAL_ATTACK",
                    "card_ids": [six["id"]],
                }
            )
            attacker.receive_json()
        with client.websocket_connect(path, headers={"Origin": ORIGIN}) as defender:
            defender.send_json(
                {"type": "AUTH", "credential": joiner["credential"]["reconnect_token"]}
            )
            state = defender.receive_json()["state"]
            red = next(value for value in state["hand"] if value["code"] == "RJ")
            seven = next(value for value in state["hand"] if value["code"] == "7C")
            assert red["joker_color"] == "red"
            defender.send_json(
                {
                    "type": "ACTION",
                    "version": state["version"],
                    "action": "DEFEND",
                    "card_ids": [seven["id"]],
                }
            )
            defended = defender.receive_json()["state"]
        with client.websocket_connect(path, headers={"Origin": ORIGIN}) as reconnected:
            reconnected.send_json(
                {"type": "AUTH", "credential": joiner["credential"]["reconnect_token"]}
            )
            restored = reconnected.receive_json()["state"]

    assert restored["deck_profile"] == "extended"
    assert restored["deck_count"] == 1
    assert {value["id"] for value in restored["hand"]} == {
        value["id"] for value in defended["hand"]
    }
    assert red["id"] in {value["id"] for value in restored["hand"]}


def _three_player_street_game(player_count: int, config: DeckConfig) -> GameState:
    assert player_count == 3
    assert config == DeckConfig(DeckProfile.EXTENDED, 1)
    street = tuple(card(rank) for rank in (Rank.TWO, Rank.THREE, Rank.FOUR, Rank.FIVE, Rank.SIX))
    return GameState(
        hands=(
            (*street, card(Rank.KING)),
            tuple(card(rank, Suit.DIAMONDS) for rank in ranks_for_profile(config.profile)[:7]),
            tuple(card(rank, Suit.HEARTS) for rank in ranks_for_profile(config.profile)[:7]),
        ),
        draw_pile=(),
        current_attacker=Seat.ONE,
        deck_config=config,
    )


def test_three_player_extended_room_street_and_take_handoff() -> None:
    config = DeckConfig(DeckProfile.EXTENDED, 1)
    service = PvPRoomService(configured_game_factory=_three_player_street_game)
    room, creator = service.create_room("Creator", capacity=3, deck_config=config)
    room, defender = service.join_room(room.invite_code, "Defender")
    room, _third = service.join_room(room.invite_code, "Third")
    street = tuple(card(rank) for rank in (Rank.TWO, Rank.THREE, Rank.FOUR, Rank.FIVE, Rank.SIX))

    room = service.play_action(
        room.invite_code,
        creator.reconnect_token,
        HumanActionType.INITIAL_ATTACK,
        street,
        expected_version=room.version,
    )
    room = service.play_action(
        room.invite_code,
        defender.reconnect_token,
        HumanActionType.TAKE,
        expected_version=room.version,
    )

    assert room.state is not None
    assert room.state.deck_config == config
    assert room.state.active_bout is not None
    assert room.state.active_bout.attacker is not Seat.ONE


def test_four_player_extended_double_room_has_108_cards_and_broadcasts_exact_action() -> None:
    def full_duplicate_game(player_count: int, config: DeckConfig) -> GameState:
        assert player_count == 4
        first = card(Rank.KING, Suit.HEARTS)
        second = card(Rank.KING, Suit.HEARTS, copy=2)
        remaining = tuple(value for value in create_deck(config) if value not in {first, second})
        hands = (
            (first, second, *remaining[:5]),
            remaining[5:12],
            remaining[12:19],
            remaining[19:26],
        )
        return GameState(
            hands=hands,
            draw_pile=remaining[26:],
            current_attacker=Seat.ONE,
            deck_config=config,
        )

    service = PvPRoomService(
        configured_game_factory=full_duplicate_game,
    )
    with TestClient(create_app(settings=enabled_settings(), pvp_service=service)) as client:
        participants = [
            client.post(
                "/api/pvp/rooms",
                json={
                    "nickname": "One",
                    "capacity": 4,
                    "deck_profile": "extended",
                    "deck_count": 2,
                },
            ).json()
        ]
        invite = participants[0]["invite_code"]
        for name in ("Two", "Three", "Four"):
            participants.append(
                client.post(
                    f"/api/pvp/rooms/{invite}/join",
                    json={"nickname": name},
                ).json()
            )
        room = service.get_room(invite)
        assert room.state is not None
        assert len(room.state.all_cards) == 108
        actor = acting_seat(room.state)
        assert actor is Seat.ONE
        participant = next(
            value for value in participants if value["credential"]["seat"] == actor.value
        )
        selected = card(Rank.KING, Suit.HEARTS)
        retained = card(Rank.KING, Suit.HEARTS, copy=2)
        with client.websocket_connect(
            f"/api/pvp/rooms/{invite}/ws",
            headers={"Origin": ORIGIN},
        ) as socket:
            socket.send_json(
                {"type": "AUTH", "credential": participant["credential"]["reconnect_token"]}
            )
            initial = socket.receive_json()["state"]
            duplicates = [value for value in initial["hand"] if value["code"] == "KH"]
            assert {value["id"] for value in duplicates} == {
                selected.physical_id,
                retained.physical_id,
            }
            socket.send_json(
                {
                    "type": "ACTION",
                    "version": initial["version"],
                    "action": "INITIAL_ATTACK",
                    "card_ids": [selected.physical_id],
                }
            )
            broadcast = socket.receive_json()

    assert broadcast["type"] == "STATE"
    assert broadcast["state"]["deck_profile"] == "extended"
    assert broadcast["state"]["deck_count"] == 2
    assert selected.physical_id in {value["id"] for value in broadcast["state"]["table_cards"]}
    assert retained.physical_id in {value["id"] for value in broadcast["state"]["hand"]}


@pytest.mark.parametrize("config", ALL_CONFIGS)
def test_two_player_pvp_rematch_preserves_deck_configuration(config: DeckConfig) -> None:
    def tiny(_count: int, actual: DeckConfig) -> GameState:
        return GameState(
            hands=((card(Rank.SIX),), (card(Rank.SEVEN),)),
            draw_pile=(),
            current_attacker=Seat.ONE,
            deck_config=actual,
        )

    service = PvPRoomService(configured_game_factory=tiny)
    if config == DEFAULT_DECK_CONFIG:
        service = PvPRoomService(game_factory=lambda: tiny(2, config))
    room, creator = service.create_room("Creator", deck_config=config)
    room, joiner = service.join_room(room.invite_code, "Friend")
    room = service.play_action(
        room.invite_code,
        creator.reconnect_token,
        HumanActionType.INITIAL_ATTACK,
        (card(Rank.SIX),),
        expected_version=room.version,
    )
    room = service.play_action(
        room.invite_code,
        joiner.reconnect_token,
        HumanActionType.TAKE,
        expected_version=room.version,
    )
    assert room.phase is PvPRoomPhase.COMPLETE
    previous_match_id = room.match_id
    room = service.request_rematch(
        room.invite_code,
        creator.reconnect_token,
        match_id=previous_match_id or "",
        expected_version=room.version,
    )
    room = service.request_rematch(
        room.invite_code,
        joiner.reconnect_token,
        match_id=previous_match_id or "",
        expected_version=room.version,
    )

    assert room.phase is PvPRoomPhase.GAME_ACTIVE
    assert room.deck_config == config
    assert room.state is not None and room.state.deck_config == config
    assert room.match_id != previous_match_id
    assert tuple(value.seat for value in room.participants) == (Seat.ONE, Seat.TWO)


def test_variant_pvp_rematch_rechecks_live_feature_gate_without_corrupting_result() -> None:
    def tiny(_count: int, actual: DeckConfig) -> GameState:
        return GameState(
            hands=((card(Rank.SIX),), (card(Rank.SEVEN),)),
            draw_pile=(),
            current_attacker=Seat.ONE,
            deck_config=actual,
        )

    service = PvPRoomService(configured_game_factory=tiny)
    settings = enabled_settings()
    with TestClient(create_app(settings=settings, pvp_service=service)) as client:
        creator = client.post(
            "/api/pvp/rooms",
            json={"nickname": "Creator", "deck_profile": "extended", "deck_count": 1},
        ).json()
        joiner = client.post(
            f"/api/pvp/rooms/{creator['invite_code']}/join",
            json={"nickname": "Friend"},
        ).json()
        room = service.get_room(creator["invite_code"])
        room = service.play_action(
            room.invite_code,
            creator["credential"]["reconnect_token"],
            HumanActionType.INITIAL_ATTACK,
            (card(Rank.SIX),),
            expected_version=room.version,
        )
        room = service.play_action(
            room.invite_code,
            joiner["credential"]["reconnect_token"],
            HumanActionType.TAKE,
            expected_version=room.version,
        )
        assert room.phase is PvPRoomPhase.COMPLETE
        completed_state = room.state
        client.app.state.settings = replace(settings, deck_variants_enabled=False)
        with client.websocket_connect(
            f"/api/pvp/rooms/{room.invite_code}/ws",
            headers={"Origin": ORIGIN},
        ) as socket:
            socket.send_json(
                {"type": "AUTH", "credential": creator["credential"]["reconnect_token"]}
            )
            state = socket.receive_json()["state"]
            socket.send_json(
                {
                    "type": "REMATCH_REQUEST",
                    "match_id": state["match_id"],
                    "version": state["version"],
                }
            )
            rejected = socket.receive_json()

    assert rejected["type"] == "REMATCH_REJECTED"
    assert rejected["error"]["code"] == "REMATCH_NOT_AVAILABLE"
    assert service.get_room(room.invite_code).state is completed_state


def test_three_player_variant_rematch_preserves_config_seats_and_fresh_card_objects() -> None:
    config = DeckConfig(DeckProfile.EXTENDED, 1)
    service = PvPRoomService(
        configured_game_factory=lambda count, actual: create_new_game(
            random.Random(27),
            player_count=count,
            deck_config=actual,
        )
    )
    room, _creator = service.create_room("One", capacity=3, deck_config=config)
    room, _two = service.join_room(room.invite_code, "Two")
    room, _three = service.join_room(room.invite_code, "Three")
    action_types = {
        BotActionType.INITIAL_ATTACK: HumanActionType.INITIAL_ATTACK,
        BotActionType.DEFEND: HumanActionType.DEFEND,
        BotActionType.TRANSFER: HumanActionType.TRANSFER,
        BotActionType.THROW_IN: HumanActionType.THROW_IN,
        BotActionType.TAKE: HumanActionType.TAKE,
        BotActionType.BITO: HumanActionType.BITO,
    }
    for _ in range(5_000):
        assert room.state is not None
        if room.state.phase is GamePhase.COMPLETE:
            break
        actor = acting_seat(room.state)
        assert actor is not None
        action = choose_bot_action(room.state, actor)
        room = service.play_action(
            room.invite_code,
            room.participant(actor).reconnect_token,
            action_types[action.action_type],
            action.cards,
            expected_version=room.version,
        )
    else:
        pytest.fail("three-player rematch fixture exceeded the transition bound")

    assert room.phase is PvPRoomPhase.COMPLETE
    assert room.state is not None
    old_card_object_ids = {id(value) for value in room.state.all_cards}
    old_match_id = room.match_id
    for participant in room.participants:
        room = service.request_rematch(
            room.invite_code,
            participant.reconnect_token,
            match_id=old_match_id or "",
            expected_version=room.version,
        )

    assert room.phase is PvPRoomPhase.GAME_ACTIVE
    assert room.deck_config == config
    assert room.match_id != old_match_id
    assert room.state is not None
    assert old_card_object_ids.isdisjoint(id(value) for value in room.state.all_cards)
    assert tuple(value.seat for value in room.participants) == (
        Seat.ONE,
        Seat.TWO,
        Seat.THREE,
    )


@pytest.mark.parametrize("config", [value for value in ALL_CONFIGS if value != DEFAULT_DECK_CONFIG])
def test_non_default_bot_and_pvp_completion_skip_persistence_callbacks(
    config: DeckConfig,
) -> None:
    bot_calls: list[object] = []
    complete = GameState(
        hands=((), (card(Rank.SIX),)),
        draw_pile=(),
        current_attacker=None,
        phase=GamePhase.COMPLETE,
        result=GameResult(GameOutcome.WIN, Seat.ONE),
        deck_config=config,
    )
    bot_service = GameSessionService(
        configured_game_factory=lambda _count, _config: complete,
        completion_recorder=lambda session: bot_calls.append(session),
    )
    session = bot_service.create_game(user_id=uuid4(), deck_config=config)

    pvp_calls: list[object] = []
    pvp_service = PvPRoomService(
        configured_game_factory=lambda _count, actual: GameState(
            hands=((card(Rank.SIX),), (card(Rank.SEVEN),)),
            draw_pile=(),
            current_attacker=Seat.ONE,
            deck_config=actual,
        ),
        completion_recorder=lambda room: pvp_calls.append(room) or (),
    )
    room, creator = pvp_service.create_room("Creator", deck_config=config)
    room, joiner = pvp_service.join_room(room.invite_code, "Friend")
    room = pvp_service.play_action(
        room.invite_code,
        creator.reconnect_token,
        HumanActionType.INITIAL_ATTACK,
        (card(Rank.SIX),),
        expected_version=room.version,
    )
    room = pvp_service.play_action(
        room.invite_code,
        joiner.reconnect_token,
        HumanActionType.TAKE,
        expected_version=room.version,
    )

    assert session.completion_persisted is False
    assert room.phase is PvPRoomPhase.COMPLETE
    assert room.completion_results == ()
    assert bot_calls == pvp_calls == []


def test_extended_double_bot_context_is_invariant_to_hidden_cards_and_draw_order() -> None:
    config = DeckConfig(DeckProfile.EXTENDED, 2)
    own = (card(Rank.TWO), card(Rank.THREE), joker(JokerColor.RED))
    exposed = card(Rank.NINE, Suit.HEARTS)
    first = GameState(
        hands=(
            (card(Rank.ACE), card(Rank.KING, copy=2)),
            own,
            (joker(JokerColor.BLACK, copy=2), card(Rank.FOUR)),
        ),
        draw_pile=(exposed, card(Rank.FIVE), joker(JokerColor.BLACK)),
        current_attacker=Seat.TWO,
        deck_config=config,
    )
    second = GameState(
        hands=(
            (card(Rank.FIVE, copy=2), joker(JokerColor.BLACK)),
            own,
            (card(Rank.ACE, copy=2), card(Rank.KING)),
        ),
        draw_pile=(exposed, joker(JokerColor.BLACK, copy=2), card(Rank.FOUR, copy=2)),
        current_attacker=Seat.TWO,
        deck_config=config,
    )
    from kiba_api.game import build_bot_context

    first = start_game_bout(first)
    second = start_game_bout(second)
    assert build_bot_context(first, Seat.TWO) == build_bot_context(second, Seat.TWO)
    assert choose_bot_action(first, Seat.TWO) == choose_bot_action(second, Seat.TWO)
