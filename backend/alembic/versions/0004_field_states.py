"""Replace checklist_states with interactive field_states."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("ix_checklist_states_page_id", table_name="checklist_states")
    op.drop_index("ix_checklist_states_user_id", table_name="checklist_states")
    op.drop_table("checklist_states")

    op.create_table(
        "field_states",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("page_id", sa.Uuid(), nullable=False),
        sa.Column("field_key", sa.String(length=64), nullable=False),
        sa.Column("field_kind", sa.String(length=32), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["page_id"], ["pages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_field_states"),
        sa.UniqueConstraint("user_id", "page_id", "field_key", name="uq_field_states_item"),
    )
    op.create_index("ix_field_states_user_id", "field_states", ["user_id"])
    op.create_index("ix_field_states_page_id", "field_states", ["page_id"])


def downgrade() -> None:
    op.drop_index("ix_field_states_page_id", table_name="field_states")
    op.drop_index("ix_field_states_user_id", table_name="field_states")
    op.drop_table("field_states")

    op.create_table(
        "checklist_states",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("page_id", sa.Uuid(), nullable=False),
        sa.Column("item_key", sa.String(length=64), nullable=False),
        sa.Column("item_label", sa.Text(), nullable=False),
        sa.Column("checked", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["page_id"], ["pages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_checklist_states"),
        sa.UniqueConstraint("user_id", "page_id", "item_key", name="uq_checklist_states_item"),
    )
    op.create_index("ix_checklist_states_user_id", "checklist_states", ["user_id"])
    op.create_index("ix_checklist_states_page_id", "checklist_states", ["page_id"])
