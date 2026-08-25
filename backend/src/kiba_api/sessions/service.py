"""Process-local human-versus-bot session orchestration."""

from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from enum import StrEnum
from threading import RLock
from uuid import uuid4

from kiba_api.game import (
    BotActionError,
    BoutPhase,
    BoutState,
    Card,
    GamePhase,
    GameState,
    Seat,
    create_new_game,
    finish_game_bout,
    play_bot_turn,
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

    def create(self, state: GameState, *, last_bout: BoutState | None = None) -> GameSession:
        """Store a new human Seat.ONE versus bot Seat.TWO session."""
        with self._lock:
            game_id = self._id_factory()
            if not game_id or game_id in self._records:
                raise ValueError("session id factory must produce a unique non-empty id")
            session = GameSession(game_id=game_id, state=state, last_bout=last_bout)
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


class GameSessionService:
    """Compose immutable game transitions into a continuous human-vs-bot session."""

    def __init__(
        self,
        *,
        store: InMemoryGameSessionStore | None = None,
        game_factory: _GameFactory = create_new_game,
        bot_turn: _BotTurn = play_bot_turn,
        bot_action_limit: int = 100,
    ) -> None:
        if isinstance(bot_action_limit, bool) or not isinstance(bot_action_limit, int):
            raise TypeError("bot_action_limit must be an int")
        if bot_action_limit <= 0:
            raise ValueError("bot_action_limit must be positive")
        self._store = store or InMemoryGameSessionStore()
        self._game_factory = game_factory
        self._bot_turn = bot_turn
        self._bot_action_limit = bot_action_limit

    def create_game(self) -> GameSession:
        """Create, normalize, and store a fresh human-versus-bot game."""
        state, last_bout = self._advance_to_human_or_complete(self._game_factory())
        return self._store.create(state, last_bout=last_bout)

    def get_game(self, game_id: str) -> GameSession:
        """Return a snapshot without exposing mutable repository state."""
        return self._store.get(game_id)

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
            return record.session

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
