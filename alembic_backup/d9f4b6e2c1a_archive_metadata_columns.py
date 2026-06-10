"""archive metadata columns

Revision ID: d9f4b6e2c1a
Revises: c3a6f21b9d4e
"""

from alembic import op
import sqlalchemy as sa

revision = "d9f4b6e2c1a"
down_revision = "c3a6f21b9d4e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "archive_entries",
        sa.Column(
            "file_size",
            sa.BigInteger(),
            nullable=True,
        ),
    )

    op.add_column(
        "archive_entries",
        sa.Column(
            "modified_time",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    op.add_column(
        "archive_entries",
        sa.Column(
            "file_hash",
            sa.String(length=64),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("archive_entries", "file_hash")
    op.drop_column("archive_entries", "modified_time")
    op.drop_column("archive_entries", "file_size")