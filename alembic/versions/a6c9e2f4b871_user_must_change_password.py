"""user_must_change_password
Revision ID: a6c9e2f4b871
Revises: f5b8d3e1a472
Create Date: 2026-10-11 10:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = 'a6c9e2f4b871'
down_revision = 'f5b8d3e1a472'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column('must_change_password', sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column('users', 'must_change_password')
