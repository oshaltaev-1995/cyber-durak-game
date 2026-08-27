"""Create XP ledger and achievement unlock tables.

Revision ID: 20260827_0003
Revises: 20260827_0002
Create Date: 2026-08-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260827_0003"
down_revision: str | None = "20260827_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "xp_ledger",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("source_type", sa.String(length=16), nullable=False),
        sa.Column("source_key", sa.String(length=128), nullable=False),
        sa.Column("source_match_id", sa.Uuid(), nullable=True),
        sa.Column("achievement_code", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint("amount > 0", name=op.f("ck_xp_ledger_positive_amount")),
        sa.CheckConstraint(
            "source_type IN ('MATCH', 'ACHIEVEMENT')",
            name=op.f("ck_xp_ledger_valid_source_type"),
        ),
        sa.ForeignKeyConstraint(
            ["source_match_id"],
            ["completed_matches.id"],
            name=op.f("fk_xp_ledger_source_match_id_completed_matches"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_xp_ledger_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_xp_ledger")),
    )
    op.create_index("ix_xp_ledger_source_match_id", "xp_ledger", ["source_match_id"])
    op.create_index("ix_xp_ledger_user_id", "xp_ledger", ["user_id"])
    op.create_index(
        "uq_xp_ledger_user_source_key",
        "xp_ledger",
        ["user_id", "source_key"],
        unique=True,
    )

    op.create_table(
        "user_achievements",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("achievement_code", sa.String(length=64), nullable=False),
        sa.Column("unlocked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("unlocked_match_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["unlocked_match_id"],
            ["completed_matches.id"],
            name=op.f("fk_user_achievements_unlocked_match_id_completed_matches"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_user_achievements_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_achievements")),
    )
    op.create_index(
        "ix_user_achievements_unlocked_match_id",
        "user_achievements",
        ["unlocked_match_id"],
    )
    op.create_index("ix_user_achievements_user_id", "user_achievements", ["user_id"])
    op.create_index(
        "uq_user_achievements_user_code",
        "user_achievements",
        ["user_id", "achievement_code"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_user_achievements_user_code", table_name="user_achievements")
    op.drop_index("ix_user_achievements_user_id", table_name="user_achievements")
    op.drop_index(
        "ix_user_achievements_unlocked_match_id",
        table_name="user_achievements",
    )
    op.drop_table("user_achievements")
    op.drop_index("uq_xp_ledger_user_source_key", table_name="xp_ledger")
    op.drop_index("ix_xp_ledger_user_id", table_name="xp_ledger")
    op.drop_index("ix_xp_ledger_source_match_id", table_name="xp_ledger")
    op.drop_table("xp_ledger")
