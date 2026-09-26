"""Process-local authoritative orchestration for private two-seat rooms."""

from __future__ import annotations

import logging
import secrets
import unicodedata
from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from threading import RLock
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from kiba_api.persistence.progression import ProgressionAward

from kiba_api.game import (
    BoutActionError,
    BoutState,
    Card,
    GameActionError,
    GamePhase,
    GameState,
    Seat,
    create_new_game,
    start_game_bout,
)
from kiba_api.locale import Locale
from kiba_api.sessions import (
    ActionCounters,
    HumanActionType,
    acting_seat,
    apply_game_action,
    record_accepted_action,
    remember_resolved_bout,
)

logger = logging.getLogger(__name__)


class PvPRoomPhase(StrEnum):
    """Process-local lifecycle of one private room."""

    WAITING_FOR_OPPONENT = "WAITING_FOR_OPPONENT"
    GAME_ACTIVE = "GAME_ACTIVE"
    COMPLETE = "COMPLETE"
    CLOSED = "CLOSED"


class PvPErrorCode(StrEnum):
    """Stable application errors for REST and WebSocket clients."""

    ROOM_NOT_FOUND = "ROOM_NOT_FOUND"
    ROOM_FULL = "ROOM_FULL"
    INVITE_EXPIRED = "INVITE_EXPIRED"
    ROOM_CLOSED = "ROOM_CLOSED"
    INVALID_NICKNAME = "INVALID_NICKNAME"
    INVALID_CREDENTIAL = "INVALID_CREDENTIAL"
    GAME_NOT_READY = "GAME_NOT_READY"
    GAME_COMPLETE = "GAME_COMPLETE"
    WRONG_TURN = "WRONG_TURN"
    ILLEGAL_ACTION = "ILLEGAL_ACTION"
    STALE_VERSION = "STALE_VERSION"
    RATE_LIMITED = "RATE_LIMITED"
    MESSAGE_TOO_LARGE = "MESSAGE_TOO_LARGE"


class PvPError(ValueError):
    """A room failure carrying a stable client-facing code."""

    def __init__(self, code: PvPErrorCode) -> None:
        self.code = code
        super().__init__(code.value)


class PvPActionError(PvPError):
    """A rejected gameplay action with its optional underlying domain code."""

    def __init__(self, code: PvPErrorCode, domain_code: str | None = None) -> None:
        self.domain_code = domain_code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class RoomTTLPolicy:
    """Configurable lazy-cleanup windows for process-local room records."""

    waiting: timedelta = timedelta(minutes=30)
    complete: timedelta = timedelta(minutes=15)
    disconnected_active: timedelta = timedelta(hours=2)

    def __post_init__(self) -> None:
        if self.waiting <= timedelta(0):
            raise ValueError("waiting TTL must be positive")
        if self.complete <= timedelta(0):
            raise ValueError("complete TTL must be positive")
        if self.disconnected_active <= timedelta(0):
            raise ValueError("disconnected_active TTL must be positive")


@dataclass(frozen=True, slots=True)
class PvPParticipant:
    """One room participant and their private reconnect identity."""

    participant_id: str
    seat: Seat
    display_name: str
    user_id: UUID | None
    reconnect_token: str
    preferred_locale: Locale = Locale.RU
    connection_id: str | None = None

    def __post_init__(self) -> None:
        if not self.participant_id or not self.display_name or not self.reconnect_token:
            raise ValueError("participant identity fields must not be empty")
        if not isinstance(self.seat, Seat):
            raise TypeError("participant seat must be a Seat")
        if self.user_id is not None and not isinstance(self.user_id, UUID):
            raise TypeError("participant user_id must be a UUID or None")
        if not isinstance(self.preferred_locale, Locale):
            raise TypeError("participant preferred_locale must be a Locale")
        if self.connection_id is not None and not self.connection_id:
            raise ValueError("connection_id must be non-empty or None")

    @property
    def connected(self) -> bool:
        return self.connection_id is not None


@dataclass(frozen=True, slots=True)
class PvPSeatActionSummary:
    """Accepted action counters for one room seat."""

    seat: Seat
    counters: ActionCounters = ActionCounters()


@dataclass(frozen=True, slots=True)
class PvPParticipantCompletion:
    """One participant's private persisted-completion presentation."""

    participant_id: str
    saved: bool
    progression_award: ProgressionAward | None = None


@dataclass(frozen=True, slots=True)
class PvPRoom:
    """An immutable public snapshot of one private friend room."""

    room_id: str
    invite_code: str
    phase: PvPRoomPhase
    participants: tuple[PvPParticipant, ...]
    state: GameState | None
    last_bout: BoutState | None
    game_started_at: datetime | None
    initial_attacker: Seat | None
    action_summaries: tuple[PvPSeatActionSummary, ...]
    completion_results: tuple[PvPParticipantCompletion, ...]
    version: int
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        if not self.room_id or not self.invite_code:
            raise ValueError("room identifiers must not be empty")
        if not isinstance(self.phase, PvPRoomPhase):
            raise TypeError("phase must be a PvPRoomPhase")
        if not isinstance(self.participants, tuple) or not 1 <= len(self.participants) <= 2:
            raise ValueError("a private room requires one or two participants")
        if not all(isinstance(value, PvPParticipant) for value in self.participants):
            raise TypeError("participants must contain PvPParticipant values")
        if len({value.seat for value in self.participants}) != len(self.participants):
            raise ValueError("room participant seats must be unique")
        if len({value.participant_id for value in self.participants}) != len(self.participants):
            raise ValueError("room participant ids must be unique")
        if len({value.reconnect_token for value in self.participants}) != len(self.participants):
            raise ValueError("room reconnect credentials must be unique")
        if self.participants[0].seat is not Seat.ONE:
            raise ValueError("the room creator must occupy Seat.ONE")
        if isinstance(self.version, bool) or not isinstance(self.version, int) or self.version < 0:
            raise ValueError("room version must be a non-negative integer")
        if self.created_at.tzinfo is None or self.updated_at.tzinfo is None:
            raise ValueError("room timestamps must be timezone-aware")
        if self.last_bout is not None and not isinstance(self.last_bout, BoutState):
            raise TypeError("last_bout must be a BoutState or None")
        if self.game_started_at is not None and self.game_started_at.tzinfo is None:
            raise ValueError("game_started_at must be timezone-aware")
        if self.initial_attacker is not None and not isinstance(self.initial_attacker, Seat):
            raise TypeError("initial_attacker must be a Seat or None")
        if len({summary.seat for summary in self.action_summaries}) != len(self.action_summaries):
            raise ValueError("action summary seats must be unique")
        participant_ids = {participant.participant_id for participant in self.participants}
        completion_ids = {result.participant_id for result in self.completion_results}
        if len(completion_ids) != len(self.completion_results):
            raise ValueError("participant completion results must be unique")
        if not completion_ids.issubset(participant_ids):
            raise ValueError("completion results must belong to room participants")
        if self.completion_results and self.phase is not PvPRoomPhase.COMPLETE:
            raise ValueError("completion results require a complete room")

        if self.phase is PvPRoomPhase.WAITING_FOR_OPPONENT:
            if len(self.participants) != 1 or self.state is not None:
                raise ValueError("a waiting room must have one participant and no game")
        elif self.phase is PvPRoomPhase.GAME_ACTIVE:
            if len(self.participants) != 2 or self.state is None:
                raise ValueError("an active room must have two participants and one game")
            if self.state.phase is not GamePhase.BOUT_ACTIVE:
                raise ValueError("an active room must expose a started bout")
            if self.game_started_at is None or self.initial_attacker is None:
                raise ValueError("an active room requires game start metadata")
        elif self.phase is PvPRoomPhase.COMPLETE and (
            self.state is None or self.state.phase is not GamePhase.COMPLETE
        ):
            raise ValueError("a complete room requires a complete game")

    def participant(self, seat: Seat) -> PvPParticipant:
        for participant in self.participants:
            if participant.seat is seat:
                return participant
        raise PvPError(PvPErrorCode.GAME_NOT_READY)

    def participant_by_id(self, participant_id: str) -> PvPParticipant:
        for participant in self.participants:
            if secrets.compare_digest(participant.participant_id, participant_id):
                return participant
        raise PvPError(PvPErrorCode.INVALID_CREDENTIAL)

    def participant_by_token(self, reconnect_token: str) -> PvPParticipant:
        for participant in self.participants:
            if secrets.compare_digest(participant.reconnect_token, reconnect_token):
                return participant
        raise PvPError(PvPErrorCode.INVALID_CREDENTIAL)

    def action_summary(self, seat: Seat) -> ActionCounters:
        for summary in self.action_summaries:
            if summary.seat is seat:
                return summary.counters
        return ActionCounters()

    def completion_for(self, participant_id: str) -> PvPParticipantCompletion | None:
        return next(
            (
                result
                for result in self.completion_results
                if secrets.compare_digest(result.participant_id, participant_id)
            ),
            None,
        )


@dataclass(frozen=True, slots=True)
class RoomConnection:
    """Connection registration metadata used by the WebSocket boundary."""

    room: PvPRoom
    participant: PvPParticipant
    replaced_connection_id: str | None


@dataclass(slots=True)
class _RoomRecord:
    room: PvPRoom
    lock: RLock = field(default_factory=RLock)


class InMemoryPvPRoomStore:
    """Concurrency-safe process-local storage for private rooms."""

    def __init__(self) -> None:
        self._records: dict[str, _RoomRecord] = {}
        self._lock = RLock()

    def create(self, room: PvPRoom) -> None:
        with self._lock:
            if room.invite_code in self._records:
                raise ValueError("invite code must be unique")
            self._records[room.invite_code] = _RoomRecord(room=room)

    def contains(self, invite_code: str) -> bool:
        with self._lock:
            return invite_code in self._records

    @contextmanager
    def locked_record(self, invite_code: str) -> Iterator[_RoomRecord]:
        with self._lock:
            record = self._records.get(invite_code)
        if record is None:
            raise PvPError(PvPErrorCode.ROOM_NOT_FOUND)
        with record.lock:
            yield record

    def cleanup(
        self,
        now: datetime,
        ttl: RoomTTLPolicy,
        *,
        exclude: str | None = None,
    ) -> None:
        """Lazily remove inactive expired records without touching connected rooms."""
        expired: list[str] = []
        with self._lock:
            records = tuple(self._records.items())
            for invite_code, record in records:
                if invite_code == exclude:
                    continue
                with record.lock:
                    room = record.room
                    if any(participant.connected for participant in room.participants):
                        continue
                    age = now - room.updated_at
                    if room.phase in {PvPRoomPhase.WAITING_FOR_OPPONENT, PvPRoomPhase.CLOSED}:
                        is_expired = age >= ttl.waiting
                    elif room.phase is PvPRoomPhase.COMPLETE:
                        is_expired = age >= ttl.complete
                    else:
                        is_expired = age >= ttl.disconnected_active
                    if is_expired:
                        expired.append(invite_code)
            for invite_code in expired:
                self._records.pop(invite_code, None)

    def detach_user(self, user_id: UUID, now: datetime) -> int:
        """Detach account persistence while retaining safe guest room continuity."""
        detached = 0
        with self._lock:
            records = tuple(self._records.values())
        for record in records:
            with record.lock:
                matching_ids = {
                    participant.participant_id
                    for participant in record.room.participants
                    if participant.user_id == user_id
                }
                if not matching_ids:
                    continue
                participants = tuple(
                    replace(participant, user_id=None)
                    if participant.participant_id in matching_ids
                    else participant
                    for participant in record.room.participants
                )
                completions = tuple(
                    replace(result, saved=False, progression_award=None)
                    if result.participant_id in matching_ids
                    else result
                    for result in record.room.completion_results
                )
                record.room = replace(
                    record.room,
                    participants=participants,
                    completion_results=completions,
                    updated_at=now,
                )
                detached += len(matching_ids)
        return detached


_Clock = Callable[[], datetime]
_GameFactory = Callable[[], GameState]
_TokenFactory = Callable[[int], str]
_CompletionRecorder = Callable[[PvPRoom], tuple[PvPParticipantCompletion, ...]]


class PvPRoomService:
    """Create, join, reconnect, and transition private authoritative games."""

    def __init__(
        self,
        *,
        store: InMemoryPvPRoomStore | None = None,
        game_factory: _GameFactory = create_new_game,
        clock: _Clock = lambda: datetime.now(UTC),
        token_factory: _TokenFactory = secrets.token_urlsafe,
        ttl: RoomTTLPolicy | None = None,
        completion_recorder: _CompletionRecorder | None = None,
    ) -> None:
        self._store = store or InMemoryPvPRoomStore()
        self._game_factory = game_factory
        self._clock = clock
        self._token_factory = token_factory
        self._ttl = ttl or RoomTTLPolicy()
        self._completion_recorder = completion_recorder

    def create_room(
        self,
        display_name: str,
        *,
        user_id: UUID | None = None,
        preferred_locale: Locale = Locale.RU,
    ) -> tuple[PvPRoom, PvPParticipant]:
        """Create a waiting room and assign its creator to Seat.ONE."""
        now = self._now()
        self._store.cleanup(now, self._ttl)
        invite_code = self._unique_invite_code()
        creator = self._new_participant(Seat.ONE, display_name, user_id, preferred_locale)
        room = PvPRoom(
            room_id=self._token_factory(18),
            invite_code=invite_code,
            phase=PvPRoomPhase.WAITING_FOR_OPPONENT,
            participants=(creator,),
            state=None,
            last_bout=None,
            game_started_at=None,
            initial_attacker=None,
            action_summaries=(),
            completion_results=(),
            version=0,
            created_at=now,
            updated_at=now,
        )
        self._store.create(room)
        return room, creator

    def join_room(
        self,
        invite_code: str,
        display_name: str,
        *,
        user_id: UUID | None = None,
        preferred_locale: Locale = Locale.RU,
    ) -> tuple[PvPRoom, PvPParticipant]:
        """Assign Seat.TWO and start the authoritative game exactly once."""
        now = self._now()
        self._store.cleanup(now, self._ttl, exclude=invite_code)
        with self._store.locked_record(invite_code) as record:
            self._raise_if_expired(record, now)
            if len(record.room.participants) >= 2:
                raise PvPError(PvPErrorCode.ROOM_FULL)
            participant = self._new_participant(
                Seat.TWO,
                display_name,
                user_id,
                preferred_locale,
            )
            state = self._game_factory()
            if state.phase is not GamePhase.READY_FOR_BOUT:
                raise ValueError("PvP game factory must return READY_FOR_BOUT")
            initial_attacker = state.current_attacker
            state = start_game_bout(state)
            record.room = replace(
                record.room,
                phase=PvPRoomPhase.GAME_ACTIVE,
                participants=record.room.participants + (participant,),
                state=state,
                game_started_at=now,
                initial_attacker=initial_attacker,
                action_summaries=(
                    PvPSeatActionSummary(Seat.ONE),
                    PvPSeatActionSummary(Seat.TWO),
                ),
                updated_at=now,
            )
            return record.room, participant

    def get_room(self, invite_code: str) -> PvPRoom:
        """Return the latest room snapshot for public status or tests."""
        now = self._now()
        self._store.cleanup(now, self._ttl, exclude=invite_code)
        with self._store.locked_record(invite_code) as record:
            self._raise_if_expired(record, now)
            self._persist_completed_room(record)
            return record.room

    def detach_user(self, user_id: UUID) -> int:
        """Keep current rooms playable but stop deleted-account persistence."""
        return self._store.detach_user(user_id, self._now())

    def authenticate(
        self,
        invite_code: str,
        reconnect_token: str,
    ) -> tuple[PvPRoom, PvPParticipant]:
        """Resolve an opaque credential without exposing it in public state."""
        room = self.get_room(invite_code)
        return room, room.participant_by_token(reconnect_token)

    def connect(
        self,
        invite_code: str,
        reconnect_token: str,
        connection_id: str,
    ) -> RoomConnection:
        """Register or replace the active connection for one participant."""
        now = self._now()
        self._store.cleanup(now, self._ttl, exclude=invite_code)
        with self._store.locked_record(invite_code) as record:
            self._raise_if_expired(record, now)
            participant = record.room.participant_by_token(reconnect_token)
            replacement = participant.connection_id
            updated = replace(participant, connection_id=connection_id)
            record.room = replace(
                record.room,
                participants=_replace_participant(record.room.participants, updated),
                updated_at=now,
            )
            return RoomConnection(record.room, updated, replacement)

    def disconnect(self, invite_code: str, participant_id: str, connection_id: str) -> PvPRoom:
        """Mark a participant disconnected only if this is their current socket."""
        now = self._now()
        with self._store.locked_record(invite_code) as record:
            participant = record.room.participant_by_id(participant_id)
            if participant.connection_id != connection_id:
                return record.room
            updated = replace(participant, connection_id=None)
            record.room = replace(
                record.room,
                participants=_replace_participant(record.room.participants, updated),
                updated_at=now,
            )
            return record.room

    def leave_room(
        self,
        invite_code: str,
        reconnect_token: str,
        connection_id: str,
    ) -> PvPRoom:
        """Intentionally close a room without creating a competitive result."""
        now = self._now()
        with self._store.locked_record(invite_code) as record:
            self._raise_if_expired(record, now)
            room = record.room
            participant = room.participant_by_token(reconnect_token)
            if participant.connection_id != connection_id:
                raise PvPError(PvPErrorCode.INVALID_CREDENTIAL)
            if room.phase is PvPRoomPhase.COMPLETE:
                raise PvPError(PvPErrorCode.GAME_COMPLETE)
            disconnected = tuple(replace(value, connection_id=None) for value in room.participants)
            record.room = replace(
                room,
                phase=PvPRoomPhase.CLOSED,
                participants=disconnected,
                completion_results=(),
                version=room.version + 1,
                updated_at=now,
            )
            return record.room

    def play_action(
        self,
        invite_code: str,
        reconnect_token: str,
        action_type: HumanActionType,
        cards: Iterable[Card] = (),
        *,
        expected_version: int,
    ) -> PvPRoom:
        """Apply one versioned participant action and commit exactly one new snapshot."""
        selected = tuple(cards)
        now = self._now()
        self._store.cleanup(now, self._ttl, exclude=invite_code)
        with self._store.locked_record(invite_code) as record:
            room = record.room
            participant = room.participant_by_token(reconnect_token)
            if room.phase is PvPRoomPhase.CLOSED:
                raise PvPActionError(PvPErrorCode.ROOM_CLOSED)
            if room.state is None or room.phase is PvPRoomPhase.WAITING_FOR_OPPONENT:
                raise PvPActionError(PvPErrorCode.GAME_NOT_READY)
            if room.phase is PvPRoomPhase.COMPLETE or room.state.phase is GamePhase.COMPLETE:
                raise PvPActionError(PvPErrorCode.GAME_COMPLETE)
            if expected_version != room.version:
                raise PvPActionError(PvPErrorCode.STALE_VERSION)
            if acting_seat(room.state) is not participant.seat:
                raise PvPActionError(PvPErrorCode.WRONG_TURN)

            previous_state = room.state
            try:
                state = apply_game_action(previous_state, participant.seat, action_type, selected)
            except (BoutActionError, GameActionError) as error:
                raise PvPActionError(PvPErrorCode.ILLEGAL_ACTION, error.code.value) from error
            last_bout = remember_resolved_bout(previous_state, state, room.last_bout)
            counters = record_accepted_action(
                room.action_summary(participant.seat),
                previous_state,
                action_type,
                selected,
            )
            if state.phase is GamePhase.READY_FOR_BOUT:
                state = start_game_bout(state)
            phase = (
                PvPRoomPhase.COMPLETE
                if state.phase is GamePhase.COMPLETE
                else PvPRoomPhase.GAME_ACTIVE
            )
            record.room = replace(
                room,
                phase=phase,
                state=state,
                last_bout=last_bout,
                action_summaries=_replace_action_summary(
                    room.action_summaries,
                    PvPSeatActionSummary(participant.seat, counters),
                ),
                version=room.version + 1,
                updated_at=now,
            )
            self._persist_completed_room(record)
            return record.room

    def _persist_completed_room(self, record: _RoomRecord) -> None:
        room = record.room
        if (
            room.phase is not PvPRoomPhase.COMPLETE
            or room.completion_results
            or self._completion_recorder is None
        ):
            return
        try:
            completion_results = self._completion_recorder(room)
        except Exception:
            logger.exception("PvP completion persistence failed for room %s", room.room_id)
            return
        record.room = replace(room, completion_results=completion_results)

    def _new_participant(
        self,
        seat: Seat,
        display_name: str,
        user_id: UUID | None,
        preferred_locale: Locale,
    ) -> PvPParticipant:
        if not display_name:
            raise PvPError(PvPErrorCode.INVALID_NICKNAME)
        return PvPParticipant(
            participant_id=self._token_factory(18),
            seat=seat,
            display_name=display_name,
            user_id=user_id,
            reconnect_token=self._token_factory(32),
            preferred_locale=preferred_locale,
        )

    def _unique_invite_code(self) -> str:
        for _attempt in range(20):
            invite_code = self._token_factory(9)
            if invite_code and not self._store.contains(invite_code):
                return invite_code
        raise RuntimeError("could not allocate a unique invite code")

    def _raise_if_expired(self, record: _RoomRecord, now: datetime) -> None:
        room = record.room
        if room.phase is PvPRoomPhase.CLOSED:
            raise PvPError(PvPErrorCode.ROOM_CLOSED)
        if any(participant.connected for participant in room.participants):
            return
        age = now - room.updated_at
        if room.phase is PvPRoomPhase.WAITING_FOR_OPPONENT:
            expired = age >= self._ttl.waiting
        elif room.phase is PvPRoomPhase.COMPLETE:
            expired = age >= self._ttl.complete
        elif room.phase is PvPRoomPhase.GAME_ACTIVE:
            expired = age >= self._ttl.disconnected_active
        else:
            expired = True
        if expired:
            record.room = replace(room, phase=PvPRoomPhase.CLOSED, updated_at=now)
            raise PvPError(PvPErrorCode.INVITE_EXPIRED)

    def _now(self) -> datetime:
        now = self._clock()
        if now.tzinfo is None:
            raise ValueError("PvP clock must return a timezone-aware datetime")
        return now


def normalize_guest_nickname(value: str | None) -> str:
    """Validate and normalize a guest's short visible room nickname."""
    if value is None:
        raise PvPError(PvPErrorCode.INVALID_NICKNAME)
    normalized = value.strip()
    if not 1 <= len(normalized) <= 24:
        raise PvPError(PvPErrorCode.INVALID_NICKNAME)
    if any(unicodedata.category(character).startswith("C") for character in normalized):
        raise PvPError(PvPErrorCode.INVALID_NICKNAME)
    return normalized


def _replace_participant(
    participants: tuple[PvPParticipant, ...],
    updated: PvPParticipant,
) -> tuple[PvPParticipant, ...]:
    return tuple(updated if item.seat is updated.seat else item for item in participants)


def _replace_action_summary(
    summaries: tuple[PvPSeatActionSummary, ...],
    updated: PvPSeatActionSummary,
) -> tuple[PvPSeatActionSummary, ...]:
    return tuple(updated if item.seat is updated.seat else item for item in summaries)
