"""Add per-user checklist checkbox state."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "checklist_states",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("page_id", sa.Uuid(), nullable=False),
        sa.Column("item_key", sa.String(length=64), nullable=False),
        sa.Column("item_label", sa.Text(), nullable=False),
        sa.Column("checked", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["page_id"], ["pages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_checklist_states"),
        sa.UniqueConstraint("user_id", "page_id", "item_key", name="uq_checklist_states_item"),
    )
    op.create_index("ix_checklist_states_user_id", "checklist_states", ["user_id"])
    op.create_index("ix_checklist_states_page_id", "checklist_states", ["page_id"])


def downgrade() -> None:
    op.drop_index("ix_checklist_states_page_id", table_name="checklist_states")
    op.drop_index("ix_checklist_states_user_id", table_name="checklist_states")
    op.drop_table("checklist_states")
