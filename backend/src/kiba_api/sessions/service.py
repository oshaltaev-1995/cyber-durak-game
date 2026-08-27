"""Process-local human-versus-bot session orchestration."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from enum import StrEnum
from threading import RLock
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

if TYPE_CHECKING:
    from kiba_api.persistence.progression import ProgressionAward

from kiba_api.game import (
    BotActionError,
    BoutPhase,
    BoutState,
    Card,
    GamePhase,
    GameState,
    Seat,
    ThrowInReason,
    analyze_throw_in,
    create_new_game,
    finish_game_bout,
    play_bot_turn,
    play_defense,
    play_game_defense,
    play_game_initial_attack,
    play_game_throw_in,
    play_game_transfer,
    start_game_bout,
    take_game_bout,
)


class HumanActionType(StrEnum):
    """One human intent accepted by the Alpha session layer."""

    INITIAL_ATTACK = "INITIAL_ATTACK"
    DEFEND = "DEFEND"
    TRANSFER = "TRANSFER"
    THROW_IN = "THROW_IN"
    TAKE = "TAKE"
    BITO = "BITO"


class SessionErrorCode(StrEnum):
    """Machine-readable application-session failure causes."""

    GAME_COMPLETE = "game_complete"
    NOT_HUMAN_TURN = "not_human_turn"
    BOT_AUTO_ADVANCE_LIMIT = "bot_auto_advance_limit"


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


@dataclass(frozen=True, slots=True)
class GameSession:
    """An immutable public snapshot of one process-local game session."""

    game_id: str
    state: GameState
    human_seat: Seat = Seat.ONE
    bot_seat: Seat = Seat.TWO
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

    def __post_init__(self) -> None:
        if not self.game_id:
            raise ValueError("game_id must not be empty")
        if not isinstance(self.state, GameState):
            raise TypeError("state must be a GameState")
        if not isinstance(self.human_seat, Seat) or not isinstance(self.bot_seat, Seat):
            raise TypeError("human_seat and bot_seat must be Seat values")
        if self.human_seat is self.bot_seat:
            raise ValueError("human and bot seats must differ")
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


@dataclass(slots=True)
class _SessionRecord:
    session: GameSession
    lock: RLock = field(default_factory=RLock)


class InMemoryGameSessionStore:
    """Concurrency-safe process-local storage for Alpha game sessions."""

    def __init__(self, id_factory: Callable[[], str] | None = None) -> None:
        self._id_factory = id_factory or (lambda: uuid4().hex)
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
    ) -> GameSession:
        """Store a new human Seat.ONE versus bot Seat.TWO session."""
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
            )
            self._records[game_id] = _SessionRecord(session=session)
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
            yield record

    def _get_record(self, game_id: str) -> _SessionRecord:
        with self._lock:
            record = self._records.get(game_id)
        if record is None:
            raise SessionNotFoundError(game_id)
        return record


_GameFactory = Callable[[], GameState]
_BotTurn = Callable[[GameState, Seat], GameState]
_CompletionRecorder = Callable[[GameSession], "ProgressionAward | None"]
_Clock = Callable[[], datetime]


class GameSessionService:
    """Compose immutable game transitions into a continuous human-vs-bot session."""

    def __init__(
        self,
        *,
        store: InMemoryGameSessionStore | None = None,
        game_factory: _GameFactory = create_new_game,
        bot_turn: _BotTurn = play_bot_turn,
        bot_action_limit: int = 100,
        completion_recorder: _CompletionRecorder | None = None,
        clock: _Clock = lambda: datetime.now(UTC),
    ) -> None:
        if isinstance(bot_action_limit, bool) or not isinstance(bot_action_limit, int):
            raise TypeError("bot_action_limit must be an int")
        if bot_action_limit <= 0:
            raise ValueError("bot_action_limit must be positive")
        self._store = store or InMemoryGameSessionStore()
        self._game_factory = game_factory
        self._bot_turn = bot_turn
        self._bot_action_limit = bot_action_limit
        self._completion_recorder = completion_recorder
        self._clock = clock

    def create_game(self, *, user_id: UUID | None = None) -> GameSession:
        """Create, normalize, and store a fresh human-versus-bot game."""
        initial_state = self._game_factory()
        initial_attacker = initial_state.current_attacker
        state, last_bout = self._advance_to_human_or_complete(initial_state)
        session = self._store.create(
            state,
            last_bout=last_bout,
            user_id=user_id,
            started_at=self._clock(),
            initial_attacker=initial_attacker,
        )
        if state.phase is GamePhase.COMPLETE:
            with self._store.locked_record(session.game_id) as record:
                self._persist_completed_match(record)
                return record.session
        return session

    def get_game(self, game_id: str) -> GameSession:
        """Return a snapshot without exposing mutable repository state."""
        with self._store.locked_record(game_id) as record:
            self._persist_completed_match(record)
            return record.session

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
            if _acting_seat(state) is not session.human_seat:
                raise SessionActionError(SessionErrorCode.NOT_HUMAN_TURN)

            updated_state = _apply_human_action(
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
            last_bout = _remember_resolved_bout(state, updated_state, session.last_bout)
            advanced_state, last_bout = self._advance_to_human_or_complete(
                updated_state,
                last_bout,
            )
            record.session = replace(
                session,
                state=advanced_state,
                last_bout=last_bout,
            )
            self._persist_completed_match(record)
            return record.session

    def _persist_completed_match(self, record: _SessionRecord) -> None:
        session = record.session
        if (
            session.state.phase is not GamePhase.COMPLETE
            or session.user_id is None
            or session.completion_persisted
            or self._completion_recorder is None
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
    ) -> tuple[GameState, BoutState | None]:
        bot_action_count = 0
        while state.phase is not GamePhase.COMPLETE:
            if state.phase is GamePhase.READY_FOR_BOUT:
                state = start_game_bout(state)
                continue

            actor = _acting_seat(state)
            if actor is Seat.ONE:
                return state, last_bout
            if actor is not Seat.TWO:
                raise ValueError("an active two-seat game must have a current actor")
            if bot_action_count >= self._bot_action_limit:
                raise SessionActionError(SessionErrorCode.BOT_AUTO_ADVANCE_LIMIT)
            try:
                previous_state = state
                state = self._bot_turn(state, Seat.TWO)
            except BotActionError as error:
                raise RuntimeError("baseline bot could not advance an owned decision") from error
            last_bout = _remember_resolved_bout(previous_state, state, last_bout)
            bot_action_count += 1

        return state, last_bout


def _remember_resolved_bout(
    previous_state: GameState,
    updated_state: GameState,
    current_last_bout: BoutState | None,
) -> BoutState | None:
    """Retain the public cards from the latest bout after game-level resolution."""
    previous_bout = previous_state.active_bout
    if previous_bout is not None and updated_state.active_bout is None:
        if previous_bout.phase is BoutPhase.WAITING_FOR_DEFENDER_RESPONSE and len(
            updated_state.discard_pile
        ) > len(previous_state.discard_pile):
            discarded_table = updated_state.discard_pile[len(previous_state.discard_pile) :]
            defense_cards = discarded_table[len(previous_bout.table_cards) :]
            if defense_cards:
                return play_defense(previous_bout, previous_bout.defender, defense_cards)
        return previous_bout
    return current_last_bout


def _apply_human_action(
    state: GameState,
    actor: Seat,
    action_type: HumanActionType,
    cards: tuple[Card, ...],
) -> GameState:
    if action_type is HumanActionType.INITIAL_ATTACK:
        return play_game_initial_attack(state, actor, cards)
    if action_type is HumanActionType.DEFEND:
        return play_game_defense(state, actor, cards)
    if action_type is HumanActionType.TRANSFER:
        return play_game_transfer(state, actor, cards)
    if action_type is HumanActionType.THROW_IN:
        return play_game_throw_in(state, actor, cards)
    if action_type is HumanActionType.TAKE:
        return take_game_bout(state, actor)
    if action_type is HumanActionType.BITO:
        return finish_game_bout(state, actor)
    raise TypeError("action_type must be a HumanActionType")


def _record_accepted_human_action(
    session: GameSession,
    previous_state: GameState,
    action_type: HumanActionType,
    selected: tuple[Card, ...],
) -> GameSession:
    transfer_count = session.human_transfer_count
    take_count = session.human_take_count
    throw_in_count = session.human_throw_in_count
    max_transfer_target = session.max_transfer_target
    mean_throw_in_count = session.arithmetic_mean_throw_in_count

    bout = previous_state.active_bout
    if action_type is HumanActionType.TRANSFER:
        transfer_count += 1
        if bout is not None and bout.transfer_target is not None:
            max_transfer_target = max(max_transfer_target, bout.transfer_target)
    elif action_type is HumanActionType.TAKE:
        take_count += 1
    elif action_type is HumanActionType.THROW_IN:
        throw_in_count += 1
        if bout is not None:
            analysis = analyze_throw_in(
                selected,
                bout.table_cards,
                bout.direct_anchor_cards,
                bout.trump_state,
            )
            if ThrowInReason.ARITHMETIC_MEAN in analysis.reasons:
                mean_throw_in_count += 1

    return replace(
        session,
        human_action_count=session.human_action_count + 1,
        human_transfer_count=transfer_count,
        human_take_count=take_count,
        human_throw_in_count=throw_in_count,
        max_transfer_target=max_transfer_target,
        arithmetic_mean_throw_in_count=mean_throw_in_count,
    )


def _acting_seat(state: GameState) -> Seat | None:
    if state.phase is GamePhase.COMPLETE:
        return None
    if state.phase is GamePhase.READY_FOR_BOUT:
        return state.current_attacker

    bout = state.active_bout
    if bout is None:
        raise ValueError("an active game requires an active bout")
    if bout.phase is BoutPhase.WAITING_FOR_DEFENDER_RESPONSE:
        return bout.defender
    if bout.phase in {
        BoutPhase.WAITING_FOR_INITIAL_ATTACK,
        BoutPhase.WAITING_FOR_ATTACKER_DECISION,
    }:
        return bout.attacker
    raise ValueError("GameState cannot retain a complete active bout")
