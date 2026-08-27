"""Account, authentication-session, and completed-match models."""

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
        CheckConstraint("opponent_type = 'BOT'", name="opponent_type_bot"),
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
    opponent_type: Mapped[str] = mapped_column(String(16), nullable=False)
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

    user: Mapped[User] = relationship(back_populates="completed_matches")


Index("ix_completed_matches_user_id", CompletedMatch.user_id)
Index(
    "ix_completed_matches_user_completed_at",
    CompletedMatch.user_id,
    CompletedMatch.completed_at,
)
