"""add metadata override flag
Revision ID: d64acdf446e5
Revises: d9f4b6e2c1a
Create Date: 2026-06-03 11:30:12.953934
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd64acdf446e5'
down_revision = 'd9f4b6e2c1a'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "archive_entries",
        sa.Column(
            "metadata_override",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade():
    op.drop_column(
        "archive_entries",
        "metadata_override",
    )