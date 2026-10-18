"""library pending_changes, no edge metadata lookups
Revision ID: d2f7a9c41b63
Revises: c6d1f8a2e940
Create Date: 2026-10-19 12:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = 'd2f7a9c41b63'
down_revision = 'c6d1f8a2e940'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('libraries', sa.Column('pending_changes', sa.Integer(), server_default='0', nullable=False))
    # Metadata is always looked up by the server.
    op.drop_column('edge_devices', 'match_metadata')


def downgrade() -> None:
    op.add_column('edge_devices', sa.Column('match_metadata', sa.Boolean(), server_default=sa.false(), nullable=False))
    op.drop_column('libraries', 'pending_changes')
