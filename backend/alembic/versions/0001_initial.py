"""Initial immutable schema."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

access_level = postgresql.ENUM("FREE", "PAID", name="access_level", create_type=False)


def id_and_timestamps() -> list[sa.Column]:
    return [
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    ]


def upgrade() -> None:
    access_level.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "users",
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(64)),
        sa.Column("first_name", sa.String(255), nullable=False),
        *id_and_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("telegram_id", name="uq_users_telegram_id"),
    )
    op.create_index("ix_users_telegram_id", "users", ["telegram_id"])
    op.create_table(
        "countries",
        sa.Column("notion_page_id", sa.String(64), nullable=False),
        sa.Column("slug", sa.String(80), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("flag", sa.String(16), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("content_version", sa.Integer(), nullable=False),
        *id_and_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_countries"),
        sa.UniqueConstraint("notion_page_id", name="uq_countries_notion_page_id"),
        sa.UniqueConstraint("slug", name="uq_countries_slug"),
    )
    op.create_table(
        "images",
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("data", sa.LargeBinary(), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        *id_and_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_images"),
        sa.UniqueConstraint("sha256", name="uq_images_sha256"),
    )
    op.create_table(
        "pages",
        sa.Column("country_id", sa.Uuid(), nullable=False),
        sa.Column("parent_id", sa.Uuid()),
        sa.Column("notion_page_id", sa.String(64), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("access_level", access_level, nullable=False),
        sa.Column("document", postgresql.JSONB(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("archived", sa.Boolean(), nullable=False),
        *id_and_timestamps(),
        sa.ForeignKeyConstraint(
            ["country_id"],
            ["countries.id"],
            ondelete="CASCADE",
            name="fk_pages_country_id_countries",
        ),
        sa.ForeignKeyConstraint(
            ["parent_id"], ["pages.id"], ondelete="CASCADE", name="fk_pages_parent_id_pages"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_pages"),
        sa.UniqueConstraint("country_id", "notion_page_id", name="uq_pages_country_id"),
    )
    op.create_index("ix_pages_country_parent", "pages", ["country_id", "parent_id"])
    op.create_table(
        "page_images",
        sa.Column("page_id", sa.Uuid(), nullable=False),
        sa.Column("image_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["page_id"], ["pages.id"], ondelete="CASCADE", name="fk_page_images_page_id_pages"
        ),
        sa.ForeignKeyConstraint(
            ["image_id"], ["images.id"], ondelete="CASCADE", name="fk_page_images_image_id_images"
        ),
        sa.PrimaryKeyConstraint("page_id", "image_id", name="pk_page_images"),
    )
    op.create_table(
        "entitlements",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("country_id", sa.Uuid(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        *id_and_timestamps(),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE", name="fk_entitlements_user_id_users"
        ),
        sa.ForeignKeyConstraint(
            ["country_id"],
            ["countries.id"],
            ondelete="CASCADE",
            name="fk_entitlements_country_id_countries",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_entitlements"),
        sa.UniqueConstraint("user_id", "country_id", name="uq_entitlements_user_id"),
    )
    op.create_table(
        "payments",
        sa.Column("idempotency_key", sa.String(100), nullable=False),
        sa.Column("external_id", sa.String(255), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("country_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        *id_and_timestamps(),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_payments_user_id_users"),
        sa.ForeignKeyConstraint(
            ["country_id"], ["countries.id"], name="fk_payments_country_id_countries"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_payments"),
        sa.UniqueConstraint("idempotency_key", name="uq_payments_idempotency_key"),
        sa.UniqueConstraint("external_id", name="uq_payments_external_id"),
    )
    op.create_table(
        "sync_runs",
        sa.Column("country_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("error", sa.Text()),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["country_id"],
            ["countries.id"],
            ondelete="CASCADE",
            name="fk_sync_runs_country_id_countries",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_sync_runs"),
    )


def downgrade() -> None:
    for table in (
        "sync_runs",
        "payments",
        "entitlements",
        "page_images",
        "pages",
        "images",
        "countries",
        "users",
    ):
        op.drop_table(table)
    access_level.drop(op.get_bind(), checkfirst=True)
