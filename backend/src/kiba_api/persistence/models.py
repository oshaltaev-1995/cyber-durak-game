"""Account, match, progression, and cosmetic persistence models."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from kiba_api.persistence.database import Base


class User(Base):
    """Persistent identity without gameplay progression fields."""

    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    normalized_email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(50), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(512), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    auth_sessions: Mapped[list[AuthSession]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    completed_matches: Mapped[list[CompletedMatch]] = relationship(
        back_populates="user",
        foreign_keys="CompletedMatch.user_id",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    xp_ledger_entries: Mapped[list[XPLedgerEntry]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    achievements: Mapped[list[UserAchievement]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    cosmetic_unlocks: Mapped[list[UserCosmeticUnlock]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    cosmetic_loadout: Mapped[UserCosmeticLoadout | None] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class AuthSession(Base):
    """Revocable server-side session containing only a token digest."""

    __tablename__ = "auth_sessions"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(back_populates="auth_sessions")


Index("ix_auth_sessions_user_id", AuthSession.user_id)
Index("ix_auth_sessions_expires_at", AuthSession.expires_at)


class CompletedMatch(Base):
    """Compact authoritative summary of one completed authenticated game."""

    __tablename__ = "completed_matches"
    __table_args__ = (
        CheckConstraint("opponent_type IN ('BOT', 'PVP')", name="valid_opponent_type"),
        CheckConstraint("outcome IN ('WIN', 'LOSS', 'DRAW')", name="valid_outcome"),
        CheckConstraint("user_seat IN ('one', 'two')", name="valid_user_seat"),
        CheckConstraint("initial_attacker IN ('one', 'two')", name="valid_initial_attacker"),
        CheckConstraint("duration_seconds >= 0", name="non_negative_duration"),
        CheckConstraint("final_human_card_count >= 0", name="non_negative_human_cards"),
        CheckConstraint("final_bot_card_count >= 0", name="non_negative_bot_cards"),
        CheckConstraint("human_action_count >= 0", name="non_negative_actions"),
        CheckConstraint("human_transfer_count >= 0", name="non_negative_transfers"),
        CheckConstraint("human_take_count >= 0", name="non_negative_takes"),
        CheckConstraint("human_throw_in_count >= 0", name="non_negative_throw_ins"),
        CheckConstraint("max_transfer_target >= 0", name="non_negative_transfer_target"),
        CheckConstraint(
            "arithmetic_mean_throw_in_count >= 0",
            name="non_negative_mean_throw_ins",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    game_session_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    pvp_match_id: Mapped[str | None] = mapped_column(String(64))
    opponent_type: Mapped[str] = mapped_column(String(16), nullable=False)
    opponent_user_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    opponent_display_name: Mapped[str | None] = mapped_column(String(50))
    outcome: Mapped[str] = mapped_column(String(8), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    user_seat: Mapped[str] = mapped_column(String(8), nullable=False)
    initial_attacker: Mapped[str] = mapped_column(String(8), nullable=False)
    final_human_card_count: Mapped[int] = mapped_column(Integer, nullable=False)
    final_bot_card_count: Mapped[int] = mapped_column(Integer, nullable=False)
    human_action_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    human_transfer_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    human_take_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    human_throw_in_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_transfer_target: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    arithmetic_mean_throw_in_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    user: Mapped[User] = relationship(
        back_populates="completed_matches",
        foreign_keys=[user_id],
    )


Index("ix_completed_matches_user_id", CompletedMatch.user_id)
Index("ix_completed_matches_pvp_match_id", CompletedMatch.pvp_match_id)
Index("ix_completed_matches_opponent_user_id", CompletedMatch.opponent_user_id)
Index(
    "uq_completed_matches_user_pvp_match",
    CompletedMatch.user_id,
    CompletedMatch.pvp_match_id,
    unique=True,
)
Index(
    "ix_completed_matches_user_completed_at",
    CompletedMatch.user_id,
    CompletedMatch.completed_at,
)


class XPLedgerEntry(Base):
    """Append-only XP award protected by a stable per-user source key."""

    __tablename__ = "xp_ledger"
    __table_args__ = (
        CheckConstraint("amount > 0", name="positive_amount"),
        CheckConstraint(
            "source_type IN ('MATCH', 'ACHIEVEMENT')",
            name="valid_source_type",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    source_type: Mapped[str] = mapped_column(String(16), nullable=False)
    source_key: Mapped[str] = mapped_column(String(128), nullable=False)
    source_match_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("completed_matches.id", ondelete="SET NULL"),
    )
    achievement_code: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    user: Mapped[User] = relationship(back_populates="xp_ledger_entries")


Index("ix_xp_ledger_user_id", XPLedgerEntry.user_id)
Index("ix_xp_ledger_source_match_id", XPLedgerEntry.source_match_id)
Index(
    "uq_xp_ledger_user_source_key",
    XPLedgerEntry.user_id,
    XPLedgerEntry.source_key,
    unique=True,
)


class UserAchievement(Base):
    """One exactly-once achievement unlock for an account."""

    __tablename__ = "user_achievements"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    achievement_code: Mapped[str] = mapped_column(String(64), nullable=False)
    unlocked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    unlocked_match_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("completed_matches.id", ondelete="SET NULL"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    user: Mapped[User] = relationship(back_populates="achievements")


Index("ix_user_achievements_user_id", UserAchievement.user_id)
Index("ix_user_achievements_unlocked_match_id", UserAchievement.unlocked_match_id)
Index(
    "uq_user_achievements_user_code",
    UserAchievement.user_id,
    UserAchievement.achievement_code,
    unique=True,
)


class UserCosmeticUnlock(Base):
    """One permanent progression-earned cosmetic unlock for an account."""

    __tablename__ = "user_cosmetic_unlocks"
    __table_args__ = (
        CheckConstraint(
            "source_type IN ('LEVEL', 'ACHIEVEMENT')",
            name="valid_source_type",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    cosmetic_code: Mapped[str] = mapped_column(String(64), nullable=False)
    unlocked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source_type: Mapped[str] = mapped_column(String(16), nullable=False)
    source_key: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    user: Mapped[User] = relationship(back_populates="cosmetic_unlocks")


Index("ix_user_cosmetic_unlocks_user_id", UserCosmeticUnlock.user_id)
Index(
    "uq_user_cosmetic_unlocks_user_code",
    UserCosmeticUnlock.user_id,
    UserCosmeticUnlock.cosmetic_code,
    unique=True,
)


class UserCosmeticLoadout(Base):
    """One account's currently equipped presentation-only cosmetics."""

    __tablename__ = "user_cosmetic_loadout"

    user_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    card_back_code: Mapped[str] = mapped_column(String(64), nullable=False)
    table_theme_code: Mapped[str] = mapped_column(String(64), nullable=False)
    profile_frame_code: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    user: Mapped[User] = relationship(back_populates="cosmetic_loadout")
