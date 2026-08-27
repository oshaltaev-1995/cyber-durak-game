"""Create completed match history.

Revision ID: 20260827_0002
Revises: 20260827_0001
Create Date: 2026-08-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260827_0002"
down_revision: str | None = "20260827_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "completed_matches",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("game_session_id", sa.String(length=64), nullable=False),
        sa.Column("opponent_type", sa.String(length=16), nullable=False),
        sa.Column("outcome", sa.String(length=8), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_seconds", sa.Integer(), nullable=False),
        sa.Column("user_seat", sa.String(length=8), nullable=False),
        sa.Column("initial_attacker", sa.String(length=8), nullable=False),
        sa.Column("final_human_card_count", sa.Integer(), nullable=False),
        sa.Column("final_bot_card_count", sa.Integer(), nullable=False),
        sa.Column("human_action_count", sa.Integer(), nullable=False),
        sa.Column("human_transfer_count", sa.Integer(), nullable=False),
        sa.Column("human_take_count", sa.Integer(), nullable=False),
        sa.Column("human_throw_in_count", sa.Integer(), nullable=False),
        sa.Column("max_transfer_target", sa.Integer(), nullable=False),
        sa.Column("arithmetic_mean_throw_in_count", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "opponent_type = 'BOT'", name=op.f("ck_completed_matches_opponent_type_bot")
        ),
        sa.CheckConstraint(
            "outcome IN ('WIN', 'LOSS', 'DRAW')",
            name=op.f("ck_completed_matches_valid_outcome"),
        ),
        sa.CheckConstraint(
            "user_seat IN ('one', 'two')",
            name=op.f("ck_completed_matches_valid_user_seat"),
        ),
        sa.CheckConstraint(
            "initial_attacker IN ('one', 'two')",
            name=op.f("ck_completed_matches_valid_initial_attacker"),
        ),
        sa.CheckConstraint(
            "duration_seconds >= 0", name=op.f("ck_completed_matches_non_negative_duration")
        ),
        sa.CheckConstraint(
            "final_human_card_count >= 0",
            name=op.f("ck_completed_matches_non_negative_human_cards"),
        ),
        sa.CheckConstraint(
            "final_bot_card_count >= 0", name=op.f("ck_completed_matches_non_negative_bot_cards")
        ),
        sa.CheckConstraint(
            "human_action_count >= 0", name=op.f("ck_completed_matches_non_negative_actions")
        ),
        sa.CheckConstraint(
            "human_transfer_count >= 0", name=op.f("ck_completed_matches_non_negative_transfers")
        ),
        sa.CheckConstraint(
            "human_take_count >= 0", name=op.f("ck_completed_matches_non_negative_takes")
        ),
        sa.CheckConstraint(
            "human_throw_in_count >= 0", name=op.f("ck_completed_matches_non_negative_throw_ins")
        ),
        sa.CheckConstraint(
            "max_transfer_target >= 0",
            name=op.f("ck_completed_matches_non_negative_transfer_target"),
        ),
        sa.CheckConstraint(
            "arithmetic_mean_throw_in_count >= 0",
            name=op.f("ck_completed_matches_non_negative_mean_throw_ins"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_completed_matches_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_completed_matches")),
        sa.UniqueConstraint(
            "game_session_id",
            name=op.f("uq_completed_matches_game_session_id"),
        ),
    )
    op.create_index(
        "ix_completed_matches_user_completed_at",
        "completed_matches",
        ["user_id", "completed_at"],
        unique=False,
    )
    op.create_index(
        "ix_completed_matches_user_id",
        "completed_matches",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_completed_matches_user_id", table_name="completed_matches")
    op.drop_index(
        "ix_completed_matches_user_completed_at",
        table_name="completed_matches",
    )
    op.drop_table("completed_matches")
