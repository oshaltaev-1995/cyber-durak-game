"""PostgreSQL persistence primitives for accounts and match history."""

from kiba_api.persistence.database import Base, Database
from kiba_api.persistence.matches import (
    MatchHistoryService,
    MatchOutcome,
    MatchStatistics,
    OpponentType,
)
from kiba_api.persistence.models import (
    AuthSession,
    CompletedMatch,
    User,
    UserAchievement,
    XPLedgerEntry,
)
from kiba_api.persistence.progression import (
    ACHIEVEMENTS,
    AchievementCode,
    AchievementDefinition,
    AchievementState,
    ProgressionAward,
    ProgressionService,
    ProgressionSummary,
    level_from_total_xp,
    progression_from_total_xp,
    xp_threshold_for_level,
)

__all__ = [
    "AuthSession",
    "Base",
    "CompletedMatch",
    "Database",
    "ACHIEVEMENTS",
    "AchievementCode",
    "AchievementDefinition",
    "AchievementState",
    "MatchHistoryService",
    "MatchOutcome",
    "MatchStatistics",
    "OpponentType",
    "ProgressionAward",
    "ProgressionService",
    "ProgressionSummary",
    "User",
    "UserAchievement",
    "XPLedgerEntry",
    "level_from_total_xp",
    "progression_from_total_xp",
    "xp_threshold_for_level",
]
