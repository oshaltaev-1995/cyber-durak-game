"""Create cosmetic unlock and loadout tables.

Revision ID: 20260827_0004
Revises: 20260827_0003
Create Date: 2026-08-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260827_0004"
down_revision: str | None = "20260827_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_cosmetic_unlocks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("cosmetic_code", sa.String(length=64), nullable=False),
        sa.Column("unlocked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_type", sa.String(length=16), nullable=False),
        sa.Column("source_key", sa.String(length=128), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "source_type IN ('LEVEL', 'ACHIEVEMENT')",
            name=op.f("ck_user_cosmetic_unlocks_valid_source_type"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_user_cosmetic_unlocks_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_cosmetic_unlocks")),
    )
    op.create_index(
        "ix_user_cosmetic_unlocks_user_id",
        "user_cosmetic_unlocks",
        ["user_id"],
    )
    op.create_index(
        "uq_user_cosmetic_unlocks_user_code",
        "user_cosmetic_unlocks",
        ["user_id", "cosmetic_code"],
        unique=True,
    )

    op.create_table(
        "user_cosmetic_loadout",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("card_back_code", sa.String(length=64), nullable=False),
        sa.Column("table_theme_code", sa.String(length=64), nullable=False),
        sa.Column("profile_frame_code", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_user_cosmetic_loadout_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_user_cosmetic_loadout")),
    )


def downgrade() -> None:
    op.drop_table("user_cosmetic_loadout")
    op.drop_index(
        "uq_user_cosmetic_unlocks_user_code",
        table_name="user_cosmetic_unlocks",
    )
    op.drop_index("ix_user_cosmetic_unlocks_user_id", table_name="user_cosmetic_unlocks")
    op.drop_table("user_cosmetic_unlocks")
