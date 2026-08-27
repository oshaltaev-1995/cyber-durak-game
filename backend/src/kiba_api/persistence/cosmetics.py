"""Static cosmetic catalogue, permanent unlocks, and account loadouts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from kiba_api.persistence.database import Database
from kiba_api.persistence.models import (
    UserAchievement,
    UserCosmeticLoadout,
    UserCosmeticUnlock,
)
from kiba_api.persistence.progression import AchievementCode, ProgressionService


class CosmeticCategory(StrEnum):
    CARD_BACK = "CARD_BACK"
    TABLE_THEME = "TABLE_THEME"
    PROFILE_FRAME = "PROFILE_FRAME"


class CosmeticUnlockType(StrEnum):
    DEFAULT = "DEFAULT"
    LEVEL = "LEVEL"
    ACHIEVEMENT = "ACHIEVEMENT"


class CosmeticCode(StrEnum):
    CLASSIC = "CLASSIC"
    LEVEL_3_BACK = "LEVEL_3_BACK"
    SNOWBALL_BACK = "SNOWBALL_BACK"
    AVALANCHE_BACK = "AVALANCHE_BACK"
    CLASSIC_TABLE = "CLASSIC_TABLE"
    NIGHT_TABLE = "NIGHT_TABLE"
    MATHEMATICIAN_TABLE = "MATHEMATICIAN_TABLE"
    NO_FRAME = "NO_FRAME"
    LEVEL_2_FRAME = "LEVEL_2_FRAME"
    WINNER_FRAME = "WINNER_FRAME"


@dataclass(frozen=True, slots=True)
class CosmeticDefinition:
    code: CosmeticCode
    category: CosmeticCategory
    title: str
    description: str
    unlock_type: CosmeticUnlockType
    unlock_requirement: int | AchievementCode | None = None


COSMETICS: tuple[CosmeticDefinition, ...] = (
    CosmeticDefinition(
        CosmeticCode.CLASSIC,
        CosmeticCategory.CARD_BACK,
        "Классика",
        "Стандартная рубашка Kiba.",
        CosmeticUnlockType.DEFAULT,
    ),
    CosmeticDefinition(
        CosmeticCode.LEVEL_3_BACK,
        CosmeticCategory.CARD_BACK,
        "Тёмная",
        "Спокойная тёмная рубашка.",
        CosmeticUnlockType.LEVEL,
        3,
    ),
    CosmeticDefinition(
        CosmeticCode.SNOWBALL_BACK,
        CosmeticCategory.CARD_BACK,
        "Снежный ком",
        "Награда за большой перевод.",
        CosmeticUnlockType.ACHIEVEMENT,
        AchievementCode.SNOWBALL_36,
    ),
    CosmeticDefinition(
        CosmeticCode.AVALANCHE_BACK,
        CosmeticCategory.CARD_BACK,
        "Лавина",
        "Для тех, кто довёл перевод до 72.",
        CosmeticUnlockType.ACHIEVEMENT,
        AchievementCode.AVALANCHE_72,
    ),
    CosmeticDefinition(
        CosmeticCode.CLASSIC_TABLE,
        CosmeticCategory.TABLE_THEME,
        "Классический стол",
        "Знакомый зелёный стол Kiba.",
        CosmeticUnlockType.DEFAULT,
    ),
    CosmeticDefinition(
        CosmeticCode.NIGHT_TABLE,
        CosmeticCategory.TABLE_THEME,
        "Ночной стол",
        "Более тёмный вариант игрового стола.",
        CosmeticUnlockType.LEVEL,
        4,
    ),
    CosmeticDefinition(
        CosmeticCode.MATHEMATICIAN_TABLE,
        CosmeticCategory.TABLE_THEME,
        "Математик",
        "Стол для любителей арифметики Kiba.",
        CosmeticUnlockType.ACHIEVEMENT,
        AchievementCode.ARITHMETIC_MEAN,
    ),
    CosmeticDefinition(
        CosmeticCode.NO_FRAME,
        CosmeticCategory.PROFILE_FRAME,
        "Без рамки",
        "Чистое оформление профиля.",
        CosmeticUnlockType.DEFAULT,
    ),
    CosmeticDefinition(
        CosmeticCode.LEVEL_2_FRAME,
        CosmeticCategory.PROFILE_FRAME,
        "Новичок",
        "Первая рамка постоянного игрока.",
        CosmeticUnlockType.LEVEL,
        2,
    ),
    CosmeticDefinition(
        CosmeticCode.WINNER_FRAME,
        CosmeticCategory.PROFILE_FRAME,
        "Победитель",
        "Рамка за десять побед.",
        CosmeticUnlockType.ACHIEVEMENT,
        AchievementCode.TEN_WINS,
    ),
)

_DEFINITIONS = {definition.code.value: definition for definition in COSMETICS}


@dataclass(frozen=True, slots=True)
class CosmeticLoadout:
    card_back_code: str = CosmeticCode.CLASSIC.value
    table_theme_code: str = CosmeticCode.CLASSIC_TABLE.value
    profile_frame_code: str = CosmeticCode.NO_FRAME.value


DEFAULT_COSMETIC_LOADOUT = CosmeticLoadout()


@dataclass(frozen=True, slots=True)
class CosmeticState:
    definition: CosmeticDefinition
    unlocked: bool
    equipped: bool
    unlocked_at: datetime | None


@dataclass(frozen=True, slots=True)
class CosmeticCatalogueState:
    items: tuple[CosmeticState, ...]
    loadout: CosmeticLoadout


@dataclass(frozen=True, slots=True)
class CosmeticSyncResult:
    new_unlocks: tuple[CosmeticDefinition, ...]
    loadout: CosmeticLoadout


class CosmeticErrorCode(StrEnum):
    NOT_FOUND = "cosmetic_not_found"
    WRONG_CATEGORY = "cosmetic_wrong_category"
    LOCKED = "cosmetic_locked"
    EMPTY_UPDATE = "cosmetic_empty_update"


class CosmeticError(ValueError):
    def __init__(self, code: CosmeticErrorCode) -> None:
        self.code = code
        super().__init__(code.value)


class CosmeticService:
    """Synchronize progression rewards and persist an account's visual loadout."""

    def __init__(
        self,
        database: Database,
        progression_service: ProgressionService | None = None,
    ) -> None:
        self._database = database
        self._progression = progression_service or ProgressionService(database)

    def synchronize(self, user_id: UUID) -> CosmeticSyncResult:
        """Grant every currently qualified cosmetic exactly once."""
        summary = self._progression.synchronize(user_id)
        for attempt in range(2):
            try:
                return self._synchronize_once(user_id, summary.level)
            except IntegrityError:
                if attempt == 1:
                    raise
        raise AssertionError("cosmetic synchronization retry loop did not return")

    def get_catalogue(self, user_id: UUID) -> CosmeticCatalogueState:
        """Return authoritative catalogue metadata joined to this account."""
        sync = self.synchronize(user_id)
        with self._database.session() as session:
            unlocks = {
                row.cosmetic_code: row
                for row in session.scalars(
                    select(UserCosmeticUnlock).where(UserCosmeticUnlock.user_id == user_id)
                )
            }
        equipped_codes = {
            sync.loadout.card_back_code,
            sync.loadout.table_theme_code,
            sync.loadout.profile_frame_code,
        }
        return CosmeticCatalogueState(
            items=tuple(
                CosmeticState(
                    definition=definition,
                    unlocked=(
                        definition.unlock_type is CosmeticUnlockType.DEFAULT
                        or definition.code.value in unlocks
                    ),
                    equipped=definition.code.value in equipped_codes,
                    unlocked_at=(
                        unlocks[definition.code.value].unlocked_at
                        if definition.code.value in unlocks
                        else None
                    ),
                )
                for definition in COSMETICS
            ),
            loadout=sync.loadout,
        )

    def get_loadout(self, user_id: UUID) -> CosmeticLoadout:
        return self.synchronize(user_id).loadout

    def equip(
        self,
        user_id: UUID,
        *,
        card_back_code: str | None = None,
        table_theme_code: str | None = None,
        profile_frame_code: str | None = None,
    ) -> CosmeticCatalogueState:
        """Equip supplied unlocked items, leaving omitted categories unchanged."""
        updates = {
            CosmeticCategory.CARD_BACK: card_back_code,
            CosmeticCategory.TABLE_THEME: table_theme_code,
            CosmeticCategory.PROFILE_FRAME: profile_frame_code,
        }
        if all(value is None for value in updates.values()):
            raise CosmeticError(CosmeticErrorCode.EMPTY_UPDATE)
        self.synchronize(user_id)
        with self._database.session() as session:
            unlocked = set(
                session.scalars(
                    select(UserCosmeticUnlock.cosmetic_code).where(
                        UserCosmeticUnlock.user_id == user_id
                    )
                )
            )
            loadout = session.get(UserCosmeticLoadout, user_id)
            if loadout is None:
                loadout = _new_default_loadout(user_id)
                session.add(loadout)
            for category, code in updates.items():
                if code is None:
                    continue
                definition = _DEFINITIONS.get(code)
                if definition is None:
                    raise CosmeticError(CosmeticErrorCode.NOT_FOUND)
                if definition.category is not category:
                    raise CosmeticError(CosmeticErrorCode.WRONG_CATEGORY)
                if (
                    definition.unlock_type is not CosmeticUnlockType.DEFAULT
                    and code not in unlocked
                ):
                    raise CosmeticError(CosmeticErrorCode.LOCKED)
                setattr(loadout, _LOADOUT_FIELDS[category], code)
            loadout.updated_at = datetime.now(UTC)
            session.commit()
        return self.get_catalogue(user_id)

    def _synchronize_once(self, user_id: UUID, level: int) -> CosmeticSyncResult:
        now = datetime.now(UTC)
        with self._database.session() as session:
            achievement_rows = {
                row.achievement_code: row
                for row in session.scalars(
                    select(UserAchievement).where(UserAchievement.user_id == user_id)
                )
            }
            existing_codes = set(
                session.scalars(
                    select(UserCosmeticUnlock.cosmetic_code).where(
                        UserCosmeticUnlock.user_id == user_id
                    )
                )
            )
            new_unlocks: list[CosmeticDefinition] = []
            for definition in COSMETICS:
                if (
                    definition.unlock_type is CosmeticUnlockType.DEFAULT
                    or definition.code.value in existing_codes
                    or not _qualifies(definition, level, set(achievement_rows))
                ):
                    continue
                achievement = (
                    achievement_rows.get(definition.unlock_requirement.value)
                    if isinstance(definition.unlock_requirement, AchievementCode)
                    else None
                )
                session.add(
                    UserCosmeticUnlock(
                        user_id=user_id,
                        cosmetic_code=definition.code.value,
                        unlocked_at=achievement.unlocked_at if achievement is not None else now,
                        source_type=definition.unlock_type.value,
                        source_key=_source_key(definition),
                    )
                )
                existing_codes.add(definition.code.value)
                new_unlocks.append(definition)

            row = session.get(UserCosmeticLoadout, user_id)
            if row is None:
                row = _new_default_loadout(user_id)
                session.add(row)
            session.commit()
            return CosmeticSyncResult(tuple(new_unlocks), _loadout_from_row(row))


_LOADOUT_FIELDS = {
    CosmeticCategory.CARD_BACK: "card_back_code",
    CosmeticCategory.TABLE_THEME: "table_theme_code",
    CosmeticCategory.PROFILE_FRAME: "profile_frame_code",
}


def _qualifies(
    definition: CosmeticDefinition,
    level: int,
    achievement_codes: set[str],
) -> bool:
    if definition.unlock_type is CosmeticUnlockType.LEVEL:
        return (
            isinstance(definition.unlock_requirement, int)
            and level >= definition.unlock_requirement
        )
    if definition.unlock_type is CosmeticUnlockType.ACHIEVEMENT:
        return (
            isinstance(definition.unlock_requirement, AchievementCode)
            and definition.unlock_requirement.value in achievement_codes
        )
    return True


def _source_key(definition: CosmeticDefinition) -> str:
    requirement = definition.unlock_requirement
    value = requirement.value if isinstance(requirement, AchievementCode) else requirement
    return f"{definition.unlock_type.value.lower()}:{value}"


def _new_default_loadout(user_id: UUID) -> UserCosmeticLoadout:
    return UserCosmeticLoadout(
        user_id=user_id,
        card_back_code=DEFAULT_COSMETIC_LOADOUT.card_back_code,
        table_theme_code=DEFAULT_COSMETIC_LOADOUT.table_theme_code,
        profile_frame_code=DEFAULT_COSMETIC_LOADOUT.profile_frame_code,
    )


def _loadout_from_row(row: UserCosmeticLoadout) -> CosmeticLoadout:
    return CosmeticLoadout(
        card_back_code=row.card_back_code,
        table_theme_code=row.table_theme_code,
        profile_frame_code=row.profile_frame_code,
    )
