"""Extend completed match history for private PvP.

Revision ID: 20260828_0005
Revises: 20260827_0004
Create Date: 2026-08-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260828_0005"
down_revision: str | None = "20260827_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("completed_matches") as batch_op:
        batch_op.drop_constraint(
            op.f("ck_completed_matches_opponent_type_bot"),
            type_="check",
        )
        batch_op.create_check_constraint(
            op.f("ck_completed_matches_valid_opponent_type"),
            "opponent_type IN ('BOT', 'PVP')",
        )
        batch_op.add_column(sa.Column("pvp_match_id", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("opponent_user_id", sa.Uuid(), nullable=True))
        batch_op.add_column(sa.Column("opponent_display_name", sa.String(length=50), nullable=True))
        batch_op.create_foreign_key(
            op.f("fk_completed_matches_opponent_user_id_users"),
            "users",
            ["opponent_user_id"],
            ["id"],
            ondelete="SET NULL",
        )
    op.create_index(
        "ix_completed_matches_pvp_match_id",
        "completed_matches",
        ["pvp_match_id"],
    )
    op.create_index(
        "ix_completed_matches_opponent_user_id",
        "completed_matches",
        ["opponent_user_id"],
    )
    op.create_index(
        "uq_completed_matches_user_pvp_match",
        "completed_matches",
        ["user_id", "pvp_match_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_completed_matches_user_pvp_match", table_name="completed_matches")
    op.drop_index("ix_completed_matches_opponent_user_id", table_name="completed_matches")
    op.drop_index("ix_completed_matches_pvp_match_id", table_name="completed_matches")
    with op.batch_alter_table("completed_matches") as batch_op:
        batch_op.drop_constraint(
            op.f("fk_completed_matches_opponent_user_id_users"),
            type_="foreignkey",
        )
        batch_op.drop_column("opponent_display_name")
        batch_op.drop_column("opponent_user_id")
        batch_op.drop_column("pvp_match_id")
        batch_op.drop_constraint(
            op.f("ck_completed_matches_valid_opponent_type"),
            type_="check",
        )
        batch_op.create_check_constraint(
            op.f("ck_completed_matches_opponent_type_bot"),
            "opponent_type = 'BOT'",
        )
