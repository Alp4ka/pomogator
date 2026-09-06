"""Add pdf_exports forensic audit table."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "pdf_exports",
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("page_id", sa.Uuid(), nullable=False),
        sa.Column("country_id", sa.Uuid(), nullable=False),
        sa.Column("entitled", sa.Boolean(), nullable=False),
        sa.Column("seal", sa.Text(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["country_id"], ["countries.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["page_id"], ["pages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_pdf_exports"),
    )
    op.create_index("ix_pdf_exports_telegram_id", "pdf_exports", ["telegram_id"])
    op.create_index("ix_pdf_exports_user_id", "pdf_exports", ["user_id"])
    op.create_index("ix_pdf_exports_page_id", "pdf_exports", ["page_id"])
    op.create_index("ix_pdf_exports_seal", "pdf_exports", ["seal"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_pdf_exports_seal", table_name="pdf_exports")
    op.drop_index("ix_pdf_exports_page_id", table_name="pdf_exports")
    op.drop_index("ix_pdf_exports_user_id", table_name="pdf_exports")
    op.drop_index("ix_pdf_exports_telegram_id", table_name="pdf_exports")
    op.drop_table("pdf_exports")
