"""Store Notion last_edited_time and database ids for incremental sync."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "pages",
        sa.Column("notion_last_edited_at", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "pages",
        sa.Column(
            "notion_database_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("pages", "notion_database_ids")
    op.drop_column("pages", "notion_last_edited_at")
