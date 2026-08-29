"""Add persisted account locale.

Revision ID: 20260829_0007
Revises: 20260828_0006
Create Date: 2026-08-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260829_0007"
down_revision: str | None = "20260828_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(
            sa.Column(
                "preferred_locale",
                sa.String(length=2),
                server_default="ru",
                nullable=False,
            )
        )
        batch.create_check_constraint(
            "valid_preferred_locale",
            "preferred_locale IN ('ru', 'en')",
        )

    with op.batch_alter_table("users") as batch:
        batch.alter_column("preferred_locale", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_constraint("valid_preferred_locale", type_="check")
        batch.drop_column("preferred_locale")
