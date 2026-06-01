"""library and archive entry library fk

Revision ID: c3a6f21b9d4e
Revises: af0a5327185f
Create Date: 2026-06-01 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c3a6f21b9d4e"
down_revision = "af0a5327185f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "libraries",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False, unique=True),
        sa.Column("path", sa.Text(), nullable=False, unique=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("archive_entries", sa.Column("library_id", sa.String(length=36), nullable=True))
    op.create_foreign_key(
        "fk_archive_entries_library_id_libraries",
        "archive_entries",
        "libraries",
        ["library_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_archive_entries_library_id_libraries", "archive_entries", type_="foreignkey")
    op.drop_column("archive_entries", "library_id")
    op.drop_table("libraries")