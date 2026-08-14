"""Add GitHub webhook delivery idempotency.

Revision ID: a1b2c3d4e5f6
Revises: 467aceff9ba0
Create Date: 2026-08-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "467aceff9ba0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "review_sessions",
        sa.Column("source_delivery_id", sa.String(length=100), nullable=True),
    )
    op.create_index(
        op.f("ix_review_sessions_source_delivery_id"),
        "review_sessions",
        ["source_delivery_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_review_sessions_source_delivery_id"), table_name="review_sessions")
    op.drop_column("review_sessions", "source_delivery_id")
