"""Authenticated account export and hard-deletion operations."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import delete, select, update

from kiba_api.persistence.database import Database
from kiba_api.persistence.models import (
    AccountToken,
    AuthSession,
    CompletedMatch,
    User,
    UserAchievement,
    UserCosmeticLoadout,
    UserCosmeticUnlock,
    XPLedgerEntry,
)

ACCOUNT_EXPORT_VERSION = "1.0"


class AccountDataService:
    """Read or remove one account's live persistent data."""

    def __init__(self, database: Database, *, clock=lambda: datetime.now(UTC)) -> None:
        self._database = database
        self._clock = clock

    def user_exists(self, user_id: UUID) -> bool:
        """Return whether a live account still owns this identifier."""
        with self._database.session() as session:
            return session.get(User, user_id) is not None

    def export(self, user_id: UUID) -> dict[str, Any]:
        """Return a versioned in-memory export without security credentials."""
        with self._database.session() as session:
            user = session.get(User, user_id)
            if user is None:
                raise LookupError(user_id)
            matches = list(
                session.scalars(
                    select(CompletedMatch)
                    .where(CompletedMatch.user_id == user_id)
                    .order_by(CompletedMatch.completed_at, CompletedMatch.id)
                )
            )
            ledger = list(
                session.scalars(
                    select(XPLedgerEntry)
                    .where(XPLedgerEntry.user_id == user_id)
                    .order_by(XPLedgerEntry.created_at, XPLedgerEntry.id)
                )
            )
            achievements = list(
                session.scalars(
                    select(UserAchievement)
                    .where(UserAchievement.user_id == user_id)
                    .order_by(UserAchievement.unlocked_at, UserAchievement.id)
                )
            )
            unlocks = list(
                session.scalars(
                    select(UserCosmeticUnlock)
                    .where(UserCosmeticUnlock.user_id == user_id)
                    .order_by(UserCosmeticUnlock.unlocked_at, UserCosmeticUnlock.id)
                )
            )
            loadout = session.get(UserCosmeticLoadout, user_id)

            return {
                "export_version": ACCOUNT_EXPORT_VERSION,
                "exported_at": _iso(self._clock()),
                "account": {
                    "id": str(user.id),
                    "email": user.email,
                    "normalized_email": user.normalized_email,
                    "display_name": user.display_name,
                    "preferred_locale": user.preferred_locale,
                    "created_at": _iso(user.created_at),
                    "updated_at": _iso(user.updated_at),
                    "last_login_at": _iso(user.last_login_at),
                    "email_verified_at": _iso(user.email_verified_at),
                    "is_active": user.is_active,
                },
                "completed_matches": [_match_export(row) for row in matches],
                "xp_ledger": [
                    {
                        "id": str(row.id),
                        "amount": row.amount,
                        "source_type": row.source_type,
                        "source_key": row.source_key,
                        "source_match_id": _uuid(row.source_match_id),
                        "achievement_code": row.achievement_code,
                        "created_at": _iso(row.created_at),
                    }
                    for row in ledger
                ],
                "achievements": [
                    {
                        "code": row.achievement_code,
                        "unlocked_at": _iso(row.unlocked_at),
                        "unlocked_match_id": _uuid(row.unlocked_match_id),
                    }
                    for row in achievements
                ],
                "cosmetics": {
                    "unlocks": [
                        {
                            "code": row.cosmetic_code,
                            "unlocked_at": _iso(row.unlocked_at),
                            "source_type": row.source_type,
                            "source_key": row.source_key,
                        }
                        for row in unlocks
                    ],
                    "loadout": (
                        {
                            "card_back_code": loadout.card_back_code,
                            "table_theme_code": loadout.table_theme_code,
                            "profile_frame_code": loadout.profile_frame_code,
                            "created_at": _iso(loadout.created_at),
                            "updated_at": _iso(loadout.updated_at),
                        }
                        if loadout is not None
                        else None
                    ),
                },
            }

    def delete(self, user_id: UUID) -> None:
        """Delete one live account atomically and anonymize retained opponent history."""
        with self._database.session() as session:
            user = session.get(User, user_id)
            if user is None:
                raise LookupError(user_id)
            try:
                session.execute(
                    update(CompletedMatch)
                    .where(CompletedMatch.opponent_user_id == user_id)
                    .values(opponent_user_id=None, opponent_display_name=None)
                )
                # Explicit ordering keeps hard deletion reliable even in SQLite tests where
                # foreign-key cascade enforcement can differ from PostgreSQL.
                for model in (
                    UserCosmeticLoadout,
                    UserCosmeticUnlock,
                    UserAchievement,
                    XPLedgerEntry,
                    CompletedMatch,
                    AccountToken,
                    AuthSession,
                ):
                    session.execute(delete(model).where(model.user_id == user_id))
                session.delete(user)
                session.commit()
            except Exception:
                session.rollback()
                raise


def _match_export(row: CompletedMatch) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "game_session_id": row.game_session_id,
        "shared_pvp_match_id": row.pvp_match_id,
        "opponent_type": row.opponent_type,
        "opponent_display_name": row.opponent_display_name,
        "outcome": row.outcome,
        "started_at": _iso(row.started_at),
        "completed_at": _iso(row.completed_at),
        "duration_seconds": row.duration_seconds,
        "user_seat": row.user_seat,
        "initial_attacker": row.initial_attacker,
        "final_user_card_count": row.final_human_card_count,
        "final_opponent_card_count": row.final_bot_card_count,
        "action_count": row.human_action_count,
        "transfer_count": row.human_transfer_count,
        "take_count": row.human_take_count,
        "throw_in_count": row.human_throw_in_count,
        "max_transfer_target": row.max_transfer_target,
        "arithmetic_mean_throw_in_count": row.arithmetic_mean_throw_in_count,
    }


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _uuid(value: UUID | None) -> str | None:
    return str(value) if value is not None else None
