"""Process-local human-versus-bot session orchestration."""

from __future__ import annotations

import random
from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from threading import RLock
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

if TYPE_CHECKING:
    from kiba_api.persistence.progression import ProgressionAward

from kiba_api.game import (
    DEFAULT_DECK_CONFIG,
    BotAction,
    BotActionError,
    BotActionType,
    BoutState,
    Card,
    DeckConfig,
    GamePhase,
    GameState,
    Seat,
    choose_bot_action,
    create_new_game,
    get_cards_value,
    play_bot_turn,
    start_game_bout,
)
from kiba_api.sessions.actions import (
    ActionCounters,
    HumanActionType,
    acting_seat,
    apply_game_action,
    record_accepted_action,
    remember_resolved_bout,
)
from kiba_api.sessions.bot_names import BOT_NAME_POOL, assign_bot_names
from kiba_api.sessions.hints import MoveHints, get_move_hints


class SessionErrorCode(StrEnum):
    """Machine-readable application-session failure causes."""

    GAME_COMPLETE = "game_complete"
    NOT_HUMAN_TURN = "not_human_turn"
    BOT_AUTO_ADVANCE_LIMIT = "bot_auto_advance_limit"
    FEATURE_NOT_AVAILABLE = "FEATURE_NOT_AVAILABLE"


class SessionNotFoundError(LookupError):
    """Raised when an opaque game identifier has no process-local session."""

    code = "game_not_found"

    def __init__(self, game_id: str) -> None:
        self.game_id = game_id
        super().__init__(game_id)


class SessionActionError(ValueError):
    """A rejected application action carrying a stable error code."""

    def __init__(self, code: SessionErrorCode) -> None:
        self.code = code
        super().__init__(code.value)


class BotPresentationEventType(StrEnum):
    """One safe transient bot action hint for the current HTTP response."""

    INITIAL_ATTACK = "BOT_INITIAL_ATTACK"
    DEFEND = "BOT_DEFEND"
    TRANSFER = "BOT_TRANSFER"
    THROW_IN = "BOT_THROW_IN"
    TAKE = "BOT_TAKE"
    BITO = "BOT_BITO"


@dataclass(frozen=True, slots=True)
class BotPresentationEvent:
    """Public, non-authoritative metadata describing one confirmed bot action."""

    type: BotPresentationEventType
    card_count: int
    value: int | None = None
    target: int | None = None
    actor_seat: Seat = Seat.TWO


@dataclass(frozen=True, slots=True)
class SessionParticipant:
    """Stable synthetic/public identity for one canonical bot-session seat."""

    participant_id: str
    seat: Seat
    display_name: str
    is_bot: bool

    def __post_init__(self) -> None:
        if not self.participant_id:
            raise ValueError("participant_id must not be empty")
        if not isinstance(self.seat, Seat):
            raise TypeError("seat must be a Seat")
        if not self.display_name.strip():
            raise ValueError("display_name must not be empty")
        if not isinstance(self.is_bot, bool):
            raise TypeError("is_bot must be a bool")


@dataclass(frozen=True, slots=True)
class GameAppearance:
    """Presentation-only cosmetic codes captured when a session starts."""

    card_back_code: str = "CLASSIC"
    table_theme_code: str = "CLASSIC_TABLE"
    profile_frame_code: str = "NO_FRAME"


DEFAULT_GAME_APPEARANCE = GameAppearance()


@dataclass(frozen=True, slots=True)
class GameSession:
    """An immutable public snapshot of one process-local game session."""

    game_id: str
    state: GameState
    human_seat: Seat = Seat.ONE
    bot_seat: Seat = Seat.TWO
    participants: tuple[SessionParticipant, ...] = ()
    appearance: GameAppearance = DEFAULT_GAME_APPEARANCE
    last_bout: BoutState | None = None
    user_id: UUID | None = None
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    initial_attacker: Seat | None = None
    human_action_count: int = 0
    human_transfer_count: int = 0
    human_take_count: int = 0
    human_throw_in_count: int = 0
    max_transfer_target: int = 0
    arithmetic_mean_throw_in_count: int = 0
    completion_persisted: bool = False
    progression_award: ProgressionAward | None = None
    recent_events: tuple[BotPresentationEvent, ...] = ()

    def __post_init__(self) -> None:
        if not self.game_id:
            raise ValueError("game_id must not be empty")
        if not isinstance(self.state, GameState):
            raise TypeError("state must be a GameState")
        if not isinstance(self.human_seat, Seat) or not isinstance(self.bot_seat, Seat):
            raise TypeError("human_seat and bot_seat must be Seat values")
        if self.human_seat is self.bot_seat:
            raise ValueError("human and bot seats must differ")
        if not self.participants:
            object.__setattr__(
                self,
                "participants",
                (
                    SessionParticipant("human", self.human_seat, "Player", False),
                    SessionParticipant("bot", self.bot_seat, "Bot", True),
                ),
            )
        if tuple(participant.seat for participant in self.participants) != self.state.seat_order:
            raise ValueError("participants must align with the canonical seat order")
        if len({participant.participant_id for participant in self.participants}) != len(
            self.participants
        ):
            raise ValueError("participant IDs must be unique")
        humans = tuple(participant for participant in self.participants if not participant.is_bot)
        if len(humans) != 1 or humans[0].seat is not self.human_seat:
            raise ValueError("a bot session requires exactly one human participant")
        bots = tuple(participant for participant in self.participants if participant.is_bot)
        if not bots or bots[0].seat is not self.bot_seat:
            raise ValueError("bot_seat must identify the first bot participant")
        if not isinstance(self.appearance, GameAppearance):
            raise TypeError("appearance must be a GameAppearance")
        if self.last_bout is not None and not isinstance(self.last_bout, BoutState):
            raise TypeError("last_bout must be a BoutState or None")
        if self.user_id is not None and not isinstance(self.user_id, UUID):
            raise TypeError("user_id must be a UUID or None")
        if self.started_at.tzinfo is None:
            raise ValueError("started_at must be timezone-aware")
        if self.initial_attacker is not None and not isinstance(self.initial_attacker, Seat):
            raise TypeError("initial_attacker must be a Seat or None")
        for name in (
            "human_action_count",
            "human_transfer_count",
            "human_take_count",
            "human_throw_in_count",
            "max_transfer_target",
            "arithmetic_mean_throw_in_count",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"{name} must be an int")
            if value < 0:
                raise ValueError(f"{name} must not be negative")
        if not isinstance(self.completion_persisted, bool):
            raise TypeError("completion_persisted must be a bool")
        if not isinstance(self.recent_events, tuple) or not all(
            isinstance(event, BotPresentationEvent) for event in self.recent_events
        ):
            raise TypeError("recent_events must be a tuple of BotPresentationEvent values")

    @property
    def bot_seats(self) -> tuple[Seat, ...]:
        return tuple(participant.seat for participant in self.participants if participant.is_bot)

    @property
    def total_players(self) -> int:
        return len(self.participants)


@dataclass(slots=True)
class _SessionRecord:
    session: GameSession
    updated_at: datetime
    lock: RLock = field(default_factory=RLock)


class InMemoryGameSessionStore:
    """Concurrency-safe process-local storage for Alpha game sessions."""

    def __init__(
        self,
        id_factory: Callable[[], str] | None = None,
        *,
        active_ttl: timedelta = timedelta(hours=6),
        complete_ttl: timedelta = timedelta(minutes=30),
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        if active_ttl <= timedelta(0) or complete_ttl <= timedelta(0):
            raise ValueError("session TTLs must be positive")
        self._id_factory = id_factory or (lambda: uuid4().hex)
        self._active_ttl = active_ttl
        self._complete_ttl = complete_ttl
        self._clock = clock
        self._records: dict[str, _SessionRecord] = {}
        self._lock = RLock()

    def create(
        self,
        state: GameState,
        *,
        last_bout: BoutState | None = None,
        user_id: UUID | None = None,
        started_at: datetime | None = None,
        initial_attacker: Seat | None = None,
        appearance: GameAppearance = DEFAULT_GAME_APPEARANCE,
        participants: tuple[SessionParticipant, ...] | None = None,
    ) -> GameSession:
        """Store a new human Seat.ONE versus bot Seat.TWO session."""
        self.cleanup()
        with self._lock:
            game_id = self._id_factory()
            if not game_id or game_id in self._records:
                raise ValueError("session id factory must produce a unique non-empty id")
            session = GameSession(
                game_id=game_id,
                state=state,
                last_bout=last_bout,
                user_id=user_id,
                started_at=started_at or datetime.now(UTC),
                initial_attacker=initial_attacker,
                appearance=appearance,
                participants=participants or (),
            )
            self._records[game_id] = _SessionRecord(session=session, updated_at=self._clock())
            return session

    def get(self, game_id: str) -> GameSession:
        """Return the current immutable session snapshot."""
        record = self._get_record(game_id)
        with record.lock:
            return record.session

    @contextmanager
    def locked_record(self, game_id: str) -> Iterator[_SessionRecord]:
        """Serialize one session transition against its current snapshot."""
        record = self._get_record(game_id)
        with record.lock:
            try:
                yield record
            finally:
                record.updated_at = self._clock()

    def cleanup(self) -> int:
        """Remove inactive process-local games without touching a locked active transition."""
        now = self._clock()
        expired: list[str] = []
        with self._lock:
            for game_id, record in tuple(self._records.items()):
                if not record.lock.acquire(blocking=False):
                    continue
                try:
                    ttl = (
                        self._complete_ttl
                        if record.session.state.phase is GamePhase.COMPLETE
                        else self._active_ttl
                    )
                    if now - record.updated_at >= ttl:
                        expired.append(game_id)
                finally:
                    record.lock.release()
            for game_id in expired:
                self._records.pop(game_id, None)
        return len(expired)

    def detach_user(self, user_id: UUID) -> int:
        """Turn every matching process-local game into a guest-associated session."""
        detached = 0
        with self._lock:
            records = tuple(self._records.values())
        for record in records:
            with record.lock:
                if record.session.user_id != user_id:
                    continue
                record.session = replace(
                    record.session,
                    user_id=None,
                    completion_persisted=False,
                    progression_award=None,
                )
                record.updated_at = self._clock()
                detached += 1
        return detached

    def _get_record(self, game_id: str) -> _SessionRecord:
        self.cleanup()
        with self._lock:
            record = self._records.get(game_id)
        if record is None:
            raise SessionNotFoundError(game_id)
        return record


_GameFactory = Callable[[], GameState]
_BotTurn = Callable[[GameState, Seat], GameState]
_CompletionRecorder = Callable[[GameSession], "ProgressionAward | None"]
_Clock = Callable[[], datetime]
_MultiplayerGameFactory = Callable[[int], GameState]
_ConfiguredGameFactory = Callable[[int, DeckConfig], GameState]


class GameSessionService:
    """Compose immutable game transitions into a continuous human-vs-bot session."""

    def __init__(
        self,
        *,
        store: InMemoryGameSessionStore | None = None,
        game_factory: _GameFactory = create_new_game,
        multiplayer_game_factory: _MultiplayerGameFactory | None = None,
        configured_game_factory: _ConfiguredGameFactory | None = None,
        bot_turn: _BotTurn = play_bot_turn,
        bot_action_limit: int = 5_000,
        completion_recorder: _CompletionRecorder | None = None,
        clock: _Clock = lambda: datetime.now(UTC),
        name_rng: random.Random | None = None,
        bot_name_pool: tuple[str, ...] = BOT_NAME_POOL,
        participant_id_factory: Callable[[], str] | None = None,
    ) -> None:
        if isinstance(bot_action_limit, bool) or not isinstance(bot_action_limit, int):
            raise TypeError("bot_action_limit must be an int")
        if bot_action_limit <= 0:
            raise ValueError("bot_action_limit must be positive")
        self._store = store or InMemoryGameSessionStore()
        self._game_factory = game_factory
        self._multiplayer_game_factory = multiplayer_game_factory or (
            lambda player_count: create_new_game(player_count=player_count)
        )
        self._configured_game_factory = configured_game_factory or (
            lambda player_count, deck_config: create_new_game(
                player_count=player_count,
                deck_config=deck_config,
            )
        )
        self._bot_turn = bot_turn
        self._bot_action_limit = bot_action_limit
        self._completion_recorder = completion_recorder
        self._clock = clock
        self._name_rng = name_rng or random.Random()
        self._bot_name_pool = bot_name_pool
        self._participant_id_factory = participant_id_factory or (lambda: uuid4().hex)
        self._identity_lock = RLock()

    def create_game(
        self,
        *,
        user_id: UUID | None = None,
        appearance: GameAppearance = DEFAULT_GAME_APPEARANCE,
        total_players: int = 2,
        human_display_name: str | None = None,
        deck_config: DeckConfig = DEFAULT_DECK_CONFIG,
    ) -> GameSession:
        """Create one human plus one-to-three canonical bot participants."""
        if isinstance(total_players, bool) or not isinstance(total_players, int):
            raise TypeError("total_players must be an int")
        if not 2 <= total_players <= 4:
            raise ValueError("total_players must be between 2 and 4")
        initial_state = self._create_game_state(total_players, deck_config)
        participants = self._create_participants(
            initial_state.seat_order,
            human_display_name=human_display_name,
        )
        bot_seats = tuple(p.seat for p in participants if p.is_bot)
        initial_attacker = initial_state.current_attacker
        state, last_bout, recent_events = self._advance_to_human_or_complete(
            initial_state,
            bot_seats=bot_seats,
        )
        session = self._store.create(
            state,
            last_bout=last_bout,
            user_id=user_id,
            started_at=self._clock(),
            initial_attacker=initial_attacker,
            appearance=appearance,
            participants=participants,
        )
        if state.phase is GamePhase.COMPLETE:
            with self._store.locked_record(session.game_id) as record:
                self._persist_completed_match(record)
                return replace(record.session, recent_events=recent_events)
        return replace(session, recent_events=recent_events)

    def get_game(self, game_id: str) -> GameSession:
        """Return a snapshot without exposing mutable repository state."""
        with self._store.locked_record(game_id) as record:
            self._persist_completed_match(record)
            return record.session

    def get_hints(self, game_id: str, selected_cards: Iterable[Card]) -> MoveHints:
        """Return read-only canonical hints for the human participant."""
        selected = tuple(selected_cards)
        with self._store.locked_record(game_id) as record:
            session = record.session
            if session.total_players > 2:
                raise SessionActionError(SessionErrorCode.FEATURE_NOT_AVAILABLE)
            return get_move_hints(session.state, session.human_seat, selected)

    def restart_game(self, game_id: str) -> GameSession:
        """Start a fresh same-session match while retaining participant identities."""
        with self._store.locked_record(game_id) as record:
            previous = record.session
            initial_state = self._create_game_state(
                previous.total_players,
                previous.state.deck_config,
            )
            initial_attacker = initial_state.current_attacker
            state, last_bout, recent_events = self._advance_to_human_or_complete(
                initial_state,
                bot_seats=previous.bot_seats,
            )
            record.session = GameSession(
                game_id=previous.game_id,
                state=state,
                human_seat=previous.human_seat,
                bot_seat=previous.bot_seat,
                participants=previous.participants,
                appearance=previous.appearance,
                last_bout=last_bout,
                user_id=previous.user_id,
                started_at=self._clock(),
                initial_attacker=initial_attacker,
            )
            self._persist_completed_match(record)
            return replace(record.session, recent_events=recent_events)

    def detach_user(self, user_id: UUID) -> int:
        """Prevent deleted accounts from receiving later session persistence."""
        return self._store.detach_user(user_id)

    def play_human_action(
        self,
        game_id: str,
        action_type: HumanActionType,
        cards: Iterable[Card] = (),
    ) -> GameSession:
        """Apply one human intent, then advance bot-owned decisions."""
        selected = tuple(cards)
        with self._store.locked_record(game_id) as record:
            session = record.session
            state = session.state
            if state.phase is GamePhase.COMPLETE:
                raise SessionActionError(SessionErrorCode.GAME_COMPLETE)
            if acting_seat(state) is not session.human_seat:
                raise SessionActionError(SessionErrorCode.NOT_HUMAN_TURN)

            updated_state = apply_game_action(
                state,
                session.human_seat,
                action_type,
                selected,
            )
            session = _record_accepted_human_action(
                session,
                state,
                action_type,
                selected,
            )
            last_bout = remember_resolved_bout(state, updated_state, session.last_bout)
            advanced_state, last_bout, recent_events = self._advance_to_human_or_complete(
                updated_state,
                last_bout,
                bot_seats=session.bot_seats,
            )
            record.session = replace(
                session,
                state=advanced_state,
                last_bout=last_bout,
            )
            self._persist_completed_match(record)
            return replace(record.session, recent_events=recent_events)

    def _persist_completed_match(self, record: _SessionRecord) -> None:
        session = record.session
        if (
            session.state.phase is not GamePhase.COMPLETE
            or session.user_id is None
            or session.completion_persisted
            or self._completion_recorder is None
            or session.total_players != 2
            or session.state.deck_config != DEFAULT_DECK_CONFIG
        ):
            return
        progression_award = self._completion_recorder(session)
        record.session = replace(
            session,
            completion_persisted=True,
            progression_award=progression_award,
        )

    def _advance_to_human_or_complete(
        self,
        state: GameState,
        last_bout: BoutState | None = None,
        *,
        bot_seats: tuple[Seat, ...] = (Seat.TWO,),
    ) -> tuple[GameState, BoutState | None, tuple[BotPresentationEvent, ...]]:
        bot_action_count = 0
        recent_events: list[BotPresentationEvent] = []
        while state.phase is not GamePhase.COMPLETE:
            if state.phase is GamePhase.READY_FOR_BOUT:
                state = start_game_bout(state)
                continue

            actor = acting_seat(state)
            if actor is Seat.ONE:
                return state, last_bout, tuple(recent_events)
            if actor not in bot_seats:
                raise ValueError("the current actor is not owned by this bot session")
            if bot_action_count >= self._bot_action_limit:
                raise SessionActionError(SessionErrorCode.BOT_AUTO_ADVANCE_LIMIT)
            try:
                previous_state = state
                action = choose_bot_action(previous_state, actor)
                state = self._bot_turn(state, actor)
            except BotActionError as error:
                raise RuntimeError("baseline bot could not advance an owned decision") from error
            last_bout = remember_resolved_bout(previous_state, state, last_bout)
            recent_events.append(_bot_presentation_event(previous_state, action, actor))
            bot_action_count += 1

        return state, last_bout, tuple(recent_events)

    def _create_game_state(self, total_players: int, deck_config: DeckConfig) -> GameState:
        if not isinstance(deck_config, DeckConfig):
            raise TypeError("deck_config must be a DeckConfig")
        if deck_config != DEFAULT_DECK_CONFIG:
            state = self._configured_game_factory(total_players, deck_config)
        elif total_players == 2:
            state = self._game_factory()
        else:
            state = self._multiplayer_game_factory(total_players)
        if len(state.seat_order) != total_players:
            raise ValueError("game factory returned the wrong player count")
        if state.deck_config != deck_config:
            raise ValueError("game factory returned the wrong deck configuration")
        return state

    def _create_participants(
        self,
        seat_order: tuple[Seat, ...],
        *,
        human_display_name: str | None,
    ) -> tuple[SessionParticipant, ...]:
        display_name = (human_display_name or "Player").strip() or "Player"
        with self._identity_lock:
            bot_names = assign_bot_names(
                len(seat_order) - 1,
                human_display_name=display_name,
                rng=self._name_rng,
                pool=self._bot_name_pool,
            )
            ids = tuple(self._participant_id_factory() for _ in seat_order)
        return (
            SessionParticipant(ids[0], seat_order[0], display_name, False),
            *(
                SessionParticipant(participant_id, seat, bot_name, True)
                for participant_id, seat, bot_name in zip(
                    ids[1:], seat_order[1:], bot_names, strict=True
                )
            ),
        )


_BOT_EVENT_TYPES = {
    BotActionType.INITIAL_ATTACK: BotPresentationEventType.INITIAL_ATTACK,
    BotActionType.DEFEND: BotPresentationEventType.DEFEND,
    BotActionType.TRANSFER: BotPresentationEventType.TRANSFER,
    BotActionType.THROW_IN: BotPresentationEventType.THROW_IN,
    BotActionType.TAKE: BotPresentationEventType.TAKE,
    BotActionType.BITO: BotPresentationEventType.BITO,
}


def _bot_presentation_event(
    previous_state: GameState,
    action: BotAction,
    actor: Seat,
) -> BotPresentationEvent:
    event_type = _BOT_EVENT_TYPES.get(action.action_type)
    if event_type is None:
        raise ValueError("bout start is not a presentation event")
    bout = previous_state.active_bout
    trump_state = bout.trump_state if bout is not None else previous_state.current_trump_state
    value = get_cards_value(action.cards, trump_state) if action.cards else None
    target = None
    if (
        bout is not None
        and bout.active_packet is not None
        and action.action_type
        in {
            BotActionType.DEFEND,
            BotActionType.TRANSFER,
            BotActionType.TAKE,
        }
    ):
        target = bout.active_packet.attack_value
    card_count = len(action.cards)
    if action.action_type is BotActionType.TAKE and bout is not None:
        card_count = len(bout.table_cards)
    return BotPresentationEvent(
        type=event_type,
        card_count=card_count,
        value=value,
        target=target,
        actor_seat=actor,
    )


def _record_accepted_human_action(
    session: GameSession,
    previous_state: GameState,
    action_type: HumanActionType,
    selected: tuple[Card, ...],
) -> GameSession:
    counters = record_accepted_action(
        ActionCounters(
            action_count=session.human_action_count,
            transfer_count=session.human_transfer_count,
            take_count=session.human_take_count,
            throw_in_count=session.human_throw_in_count,
            max_transfer_target=session.max_transfer_target,
            arithmetic_mean_throw_in_count=session.arithmetic_mean_throw_in_count,
        ),
        previous_state,
        action_type,
        selected,
    )

    return replace(
        session,
        human_action_count=counters.action_count,
        human_transfer_count=counters.transfer_count,
        human_take_count=counters.take_count,
        human_throw_in_count=counters.throw_in_count,
        max_transfer_target=counters.max_transfer_target,
        arithmetic_mean_throw_in_count=counters.arithmetic_mean_throw_in_count,
    )
