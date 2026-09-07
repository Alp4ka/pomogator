"""Add pages.nav_label for {pmg.nav.page(...)} cross-page links."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("pages", sa.Column("nav_label", sa.String(length=64), nullable=True))
    op.create_index("ix_pages_country_nav_label", "pages", ["country_id", "nav_label"])


def downgrade() -> None:
    op.drop_index("ix_pages_country_nav_label", table_name="pages")
    op.drop_column("pages", "nav_label")
