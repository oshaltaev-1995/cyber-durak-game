"""Persistent XP and achievements derived from authoritative completed matches."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from math import isqrt
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from kiba_api.locale import Locale
from kiba_api.persistence.database import Database
from kiba_api.persistence.matches import MatchOutcome
from kiba_api.persistence.models import CompletedMatch, UserAchievement, XPLedgerEntry


class AchievementCode(StrEnum):
    FIRST_MATCH = "FIRST_MATCH"
    FIRST_WIN = "FIRST_WIN"
    TEN_GAMES = "TEN_GAMES"
    TEN_WINS = "TEN_WINS"
    WIN_STREAK_3 = "WIN_STREAK_3"
    SNOWBALL_36 = "SNOWBALL_36"
    AVALANCHE_72 = "AVALANCHE_72"
    ARITHMETIC_MEAN = "ARITHMETIC_MEAN"


@dataclass(frozen=True, slots=True)
class AchievementDefinition:
    code: AchievementCode
    title: str
    description: str
    title_en: str
    description_en: str
    bonus_xp: int

    def localized_title(self, locale: Locale) -> str:
        return self.title if locale is Locale.RU else self.title_en

    def localized_description(self, locale: Locale) -> str:
        return self.description if locale is Locale.RU else self.description_en


ACHIEVEMENTS: tuple[AchievementDefinition, ...] = (
    AchievementDefinition(
        AchievementCode.FIRST_MATCH,
        "Первая партия",
        "Сыграть первую партию.",
        "First match",
        "Play your first match.",
        25,
    ),
    AchievementDefinition(
        AchievementCode.FIRST_WIN,
        "Первая победа",
        "Выиграть первую партию.",
        "First win",
        "Win your first match.",
        50,
    ),
    AchievementDefinition(
        AchievementCode.TEN_GAMES,
        "Завсегдатай",
        "Сыграть 10 партий.",
        "Regular player",
        "Play 10 matches.",
        100,
    ),
    AchievementDefinition(
        AchievementCode.TEN_WINS,
        "Победитель",
        "Выиграть 10 партий.",
        "Winner",
        "Win 10 matches.",
        150,
    ),
    AchievementDefinition(
        AchievementCode.WIN_STREAK_3,
        "Серия",
        "Выиграть 3 партии подряд.",
        "Winning streak",
        "Win 3 matches in a row.",
        100,
    ),
    AchievementDefinition(
        AchievementCode.SNOWBALL_36,
        "Снежный ком",
        "Довести перевод до 36 очков.",
        "Snowball",
        "Build a transfer target up to 36 points.",
        75,
    ),
    AchievementDefinition(
        AchievementCode.AVALANCHE_72,
        "Лавина",
        "Довести перевод до 72 очков.",
        "Avalanche",
        "Build a transfer target up to 72 points.",
        150,
    ),
    AchievementDefinition(
        AchievementCode.ARITHMETIC_MEAN,
        "Математик",
        "Подкинуть карту или комбинацию по среднему арифметическому.",
        "Mathematician",
        "Throw in a card or combination using the arithmetic mean.",
        75,
    ),
)

_BASE_XP = {
    MatchOutcome.WIN.value: 100,
    MatchOutcome.DRAW.value: 50,
    MatchOutcome.LOSS.value: 25,
}


@dataclass(frozen=True, slots=True)
class ProgressionSummary:
    total_xp: int
    level: int
    level_start_xp: int
    next_level_xp: int
    xp_into_level: int
    xp_needed_for_next_level: int
    progress_fraction: float
    achievements_unlocked: int
    achievements_total: int


@dataclass(frozen=True, slots=True)
class AchievementState:
    definition: AchievementDefinition
    unlocked: bool
    unlocked_at: datetime | None


@dataclass(frozen=True, slots=True)
class CosmeticAward:
    code: str
    category: str
    title: str
    title_en: str = ""

    def localized_title(self, locale: Locale) -> str:
        return self.title if locale is Locale.RU or not self.title_en else self.title_en


@dataclass(frozen=True, slots=True)
class ProgressionAward:
    base_xp: int
    achievement_bonus_xp: int
    total_awarded_xp: int
    new_achievements: tuple[AchievementDefinition, ...]
    summary: ProgressionSummary
    new_cosmetics: tuple[CosmeticAward, ...] = ()


@dataclass(slots=True)
class _RunningFacts:
    games: int = 0
    wins: int = 0
    win_streak: int = 0
    max_transfer_target: int = 0
    mean_throw_ins: int = 0


def xp_threshold_for_level(level: int) -> int:
    """Return the exact cumulative XP threshold for a one-based level."""
    if isinstance(level, bool) or not isinstance(level, int):
        raise TypeError("level must be an int")
    if level < 1:
        raise ValueError("level must be positive")
    return 50 * (level - 1) ** 2


def level_from_total_xp(total_xp: int) -> int:
    """Derive level from XP without floating-point boundary calculations."""
    if isinstance(total_xp, bool) or not isinstance(total_xp, int):
        raise TypeError("total_xp must be an int")
    if total_xp < 0:
        raise ValueError("total_xp must not be negative")
    return isqrt(total_xp // 50) + 1


def progression_from_total_xp(
    total_xp: int,
    *,
    achievements_unlocked: int = 0,
) -> ProgressionSummary:
    """Build exact level progress plus the API's display fraction."""
    level = level_from_total_xp(total_xp)
    start = xp_threshold_for_level(level)
    next_threshold = xp_threshold_for_level(level + 1)
    into_level = total_xp - start
    span = next_threshold - start
    return ProgressionSummary(
        total_xp=total_xp,
        level=level,
        level_start_xp=start,
        next_level_xp=next_threshold,
        xp_into_level=into_level,
        xp_needed_for_next_level=next_threshold - total_xp,
        progress_fraction=into_level / span,
        achievements_unlocked=achievements_unlocked,
        achievements_total=len(ACHIEVEMENTS),
    )


class ProgressionService:
    """Synchronize append-only progression from completed-match history."""

    def __init__(self, database: Database) -> None:
        self._database = database

    def synchronize(self, user_id: UUID) -> ProgressionSummary:
        """Backfill all missing match XP and first qualifying achievement unlocks."""
        self._synchronize_with_retry(user_id)
        return self.get_summary(user_id)

    def synchronize_for_match(self, user_id: UUID, match_id: UUID) -> ProgressionAward:
        """Synchronize and return the replay-safe award associated with one match."""
        self._synchronize_with_retry(user_id)
        with self._database.session() as session:
            entries = list(
                session.scalars(
                    select(XPLedgerEntry).where(
                        XPLedgerEntry.user_id == user_id,
                        XPLedgerEntry.source_match_id == match_id,
                    )
                )
            )
            unlocked_codes = set(
                session.scalars(
                    select(UserAchievement.achievement_code).where(
                        UserAchievement.user_id == user_id,
                        UserAchievement.unlocked_match_id == match_id,
                    )
                )
            )
        summary = self.get_summary(user_id)
        new_achievements = tuple(
            definition for definition in ACHIEVEMENTS if definition.code.value in unlocked_codes
        )
        base_xp = sum(entry.amount for entry in entries if entry.source_type == "MATCH")
        bonus_xp = sum(entry.amount for entry in entries if entry.source_type == "ACHIEVEMENT")
        return ProgressionAward(
            base_xp=base_xp,
            achievement_bonus_xp=bonus_xp,
            total_awarded_xp=base_xp + bonus_xp,
            new_achievements=new_achievements,
            summary=summary,
        )

    def get_summary(self, user_id: UUID) -> ProgressionSummary:
        """Read total ledger XP and derived level state."""
        with self._database.session() as session:
            total_xp = (
                session.scalar(
                    select(func.coalesce(func.sum(XPLedgerEntry.amount), 0)).where(
                        XPLedgerEntry.user_id == user_id
                    )
                )
                or 0
            )
            unlock_count = (
                session.scalar(
                    select(func.count())
                    .select_from(UserAchievement)
                    .where(UserAchievement.user_id == user_id)
                )
                or 0
            )
        return progression_from_total_xp(total_xp, achievements_unlocked=unlock_count)

    def get_achievements(self, user_id: UUID) -> tuple[AchievementState, ...]:
        """Return the static catalogue joined to this user's unlock state."""
        with self._database.session() as session:
            unlocks = {
                unlock.achievement_code: unlock
                for unlock in session.scalars(
                    select(UserAchievement).where(UserAchievement.user_id == user_id)
                )
            }
        return tuple(
            AchievementState(
                definition=definition,
                unlocked=definition.code.value in unlocks,
                unlocked_at=(
                    unlocks[definition.code.value].unlocked_at
                    if definition.code.value in unlocks
                    else None
                ),
            )
            for definition in ACHIEVEMENTS
        )

    def _synchronize_with_retry(self, user_id: UUID) -> None:
        for attempt in range(2):
            try:
                self._synchronize_once(user_id)
                return
            except IntegrityError:
                if attempt == 1:
                    raise

    def _synchronize_once(self, user_id: UUID) -> None:
        with self._database.session() as session:
            matches = list(
                session.scalars(
                    select(CompletedMatch)
                    .where(CompletedMatch.user_id == user_id)
                    .order_by(
                        CompletedMatch.completed_at,
                        CompletedMatch.created_at,
                        CompletedMatch.id,
                    )
                )
            )
            ledger_keys = set(
                session.scalars(
                    select(XPLedgerEntry.source_key).where(XPLedgerEntry.user_id == user_id)
                )
            )
            unlocked_codes = set(
                session.scalars(
                    select(UserAchievement.achievement_code).where(
                        UserAchievement.user_id == user_id
                    )
                )
            )
            facts = _RunningFacts()
            for match in matches:
                match_key = f"match:{match.id}:base"
                if match_key not in ledger_keys:
                    session.add(
                        XPLedgerEntry(
                            user_id=user_id,
                            amount=_BASE_XP[match.outcome],
                            source_type="MATCH",
                            source_key=match_key,
                            source_match_id=match.id,
                        )
                    )
                    ledger_keys.add(match_key)

                _incorporate_match(facts, match)
                for definition in ACHIEVEMENTS:
                    code = definition.code.value
                    if code in unlocked_codes or not _qualifies(definition.code, facts):
                        continue
                    session.add(
                        UserAchievement(
                            user_id=user_id,
                            achievement_code=code,
                            unlocked_at=match.completed_at,
                            unlocked_match_id=match.id,
                        )
                    )
                    bonus_key = f"achievement:{code}"
                    if bonus_key not in ledger_keys:
                        session.add(
                            XPLedgerEntry(
                                user_id=user_id,
                                amount=definition.bonus_xp,
                                source_type="ACHIEVEMENT",
                                source_key=bonus_key,
                                source_match_id=match.id,
                                achievement_code=code,
                            )
                        )
                        ledger_keys.add(bonus_key)
                    unlocked_codes.add(code)
            session.commit()


def _incorporate_match(facts: _RunningFacts, match: CompletedMatch) -> None:
    facts.games += 1
    if match.outcome == MatchOutcome.WIN.value:
        facts.wins += 1
        facts.win_streak += 1
    else:
        facts.win_streak = 0
    facts.max_transfer_target = max(facts.max_transfer_target, match.max_transfer_target)
    facts.mean_throw_ins += match.arithmetic_mean_throw_in_count


def _qualifies(code: AchievementCode, facts: _RunningFacts) -> bool:
    conditions = {
        AchievementCode.FIRST_MATCH: facts.games >= 1,
        AchievementCode.FIRST_WIN: facts.wins >= 1,
        AchievementCode.TEN_GAMES: facts.games >= 10,
        AchievementCode.TEN_WINS: facts.wins >= 10,
        AchievementCode.WIN_STREAK_3: facts.win_streak >= 3,
        AchievementCode.SNOWBALL_36: facts.max_transfer_target >= 36,
        AchievementCode.AVALANCHE_72: facts.max_transfer_target >= 72,
        AchievementCode.ARITHMETIC_MEAN: facts.mean_throw_ins >= 1,
    }
    return conditions[code]
