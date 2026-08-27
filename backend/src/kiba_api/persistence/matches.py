"""Completed-match recording and statistics derived from immutable summaries."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.exc import IntegrityError

from kiba_api.game import GameOutcome, GamePhase
from kiba_api.persistence.database import Database
from kiba_api.persistence.models import CompletedMatch
from kiba_api.sessions import GameSession


class MatchOutcome(StrEnum):
    """A completed match outcome from the account owner's perspective."""

    WIN = "WIN"
    LOSS = "LOSS"
    DRAW = "DRAW"


class OpponentType(StrEnum):
    """The constrained opponent kind supported by the current Alpha."""

    BOT = "BOT"


@dataclass(frozen=True, slots=True)
class MatchStatistics:
    """Aggregates calculated from one user's completed-match rows."""

    games_played: int
    wins: int
    losses: int
    draws: int
    win_rate: float
    current_win_streak: int
    best_win_streak: int
    total_transfers: int
    total_takes: int
    total_throw_ins: int
    highest_transfer_target: int
    arithmetic_mean_throw_ins: int


class MatchHistoryService:
    """Persist terminal summaries and query private account history."""

    def __init__(self, database: Database, *, clock=lambda: datetime.now(UTC)) -> None:
        self._database = database
        self._clock = clock

    def record_completed_match(self, game_session: GameSession) -> None:
        """Insert one terminal authenticated game, treating its stable ID idempotently."""
        state = game_session.state
        if state.phase is not GamePhase.COMPLETE or state.result is None:
            raise ValueError("only a completed authoritative game can be recorded")
        if game_session.user_id is None:
            raise ValueError("guest games must not be recorded")
        if game_session.initial_attacker is None:
            raise ValueError("a recorded game requires its initial attacker")

        completed_at = self._clock()
        started_at = _as_utc(game_session.started_at)
        completed_at = _as_utc(completed_at)
        record = CompletedMatch(
            user_id=game_session.user_id,
            game_session_id=game_session.game_id,
            opponent_type=OpponentType.BOT.value,
            outcome=_outcome_for_human(game_session),
            started_at=started_at,
            completed_at=completed_at,
            duration_seconds=max(0, int((completed_at - started_at).total_seconds())),
            user_seat=game_session.human_seat.value,
            initial_attacker=game_session.initial_attacker.value,
            final_human_card_count=len(state.hand(game_session.human_seat)),
            final_bot_card_count=len(state.hand(game_session.bot_seat)),
            human_action_count=game_session.human_action_count,
            human_transfer_count=game_session.human_transfer_count,
            human_take_count=game_session.human_take_count,
            human_throw_in_count=game_session.human_throw_in_count,
            max_transfer_target=game_session.max_transfer_target,
            arithmetic_mean_throw_in_count=game_session.arithmetic_mean_throw_in_count,
        )

        with self._database.session() as database_session:
            existing = database_session.scalar(
                select(CompletedMatch.id).where(
                    CompletedMatch.game_session_id == game_session.game_id
                )
            )
            if existing is not None:
                return
            database_session.add(record)
            try:
                database_session.commit()
            except IntegrityError:
                database_session.rollback()
                duplicate = database_session.scalar(
                    select(CompletedMatch.id).where(
                        CompletedMatch.game_session_id == game_session.game_id
                    )
                )
                if duplicate is None:
                    raise

    def get_statistics(self, user_id: UUID) -> MatchStatistics:
        """Calculate aggregate and chronological streak statistics from match rows."""
        with self._database.session() as database_session:
            rows = list(
                database_session.scalars(
                    _for_user(user_id).order_by(
                        CompletedMatch.completed_at,
                        CompletedMatch.created_at,
                        CompletedMatch.id,
                    )
                )
            )

        games_played = len(rows)
        wins = sum(row.outcome == MatchOutcome.WIN.value for row in rows)
        losses = sum(row.outcome == MatchOutcome.LOSS.value for row in rows)
        draws = sum(row.outcome == MatchOutcome.DRAW.value for row in rows)
        current_streak = 0
        best_streak = 0
        for row in rows:
            if row.outcome == MatchOutcome.WIN.value:
                current_streak += 1
                best_streak = max(best_streak, current_streak)
            else:
                current_streak = 0

        return MatchStatistics(
            games_played=games_played,
            wins=wins,
            losses=losses,
            draws=draws,
            win_rate=round((wins / games_played) * 100, 2) if games_played else 0,
            current_win_streak=current_streak,
            best_win_streak=best_streak,
            total_transfers=sum(row.human_transfer_count for row in rows),
            total_takes=sum(row.human_take_count for row in rows),
            total_throw_ins=sum(row.human_throw_in_count for row in rows),
            highest_transfer_target=max((row.max_transfer_target for row in rows), default=0),
            arithmetic_mean_throw_ins=sum(row.arithmetic_mean_throw_in_count for row in rows),
        )

    def list_matches(self, user_id: UUID, *, limit: int, offset: int) -> list[CompletedMatch]:
        """Return one user's newest completed summaries with bounded pagination."""
        with self._database.session() as database_session:
            return list(
                database_session.scalars(
                    _for_user(user_id)
                    .order_by(
                        CompletedMatch.completed_at.desc(),
                        CompletedMatch.created_at.desc(),
                        CompletedMatch.id.desc(),
                    )
                    .limit(limit)
                    .offset(offset)
                )
            )

    def count_matches(self, user_id: UUID) -> int:
        """Return the total private history count for pagination metadata."""
        with self._database.session() as database_session:
            return (
                database_session.scalar(
                    select(func.count())
                    .select_from(CompletedMatch)
                    .where(CompletedMatch.user_id == user_id)
                )
                or 0
            )

    def get_match_by_game_session(self, game_session_id: str) -> CompletedMatch:
        """Return the authoritative row for a stable process-local game identifier."""
        with self._database.session() as database_session:
            match = database_session.scalar(
                select(CompletedMatch).where(CompletedMatch.game_session_id == game_session_id)
            )
        if match is None:
            raise LookupError(game_session_id)
        return match


def _for_user(user_id: UUID) -> Select[tuple[CompletedMatch]]:
    return select(CompletedMatch).where(CompletedMatch.user_id == user_id)


def _outcome_for_human(game_session: GameSession) -> str:
    result = game_session.state.result
    if result is None:
        raise ValueError("completed game requires a result")
    if result.outcome is GameOutcome.DRAW:
        return MatchOutcome.DRAW.value
    return (
        MatchOutcome.WIN.value
        if result.winner is game_session.human_seat
        else MatchOutcome.LOSS.value
    )


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
