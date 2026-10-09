"""user_access_and_flags
Revision ID: f5b8d3e1a472
Revises: e4a7c2b9d358
Create Date: 2026-10-09 12:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = 'f5b8d3e1a472'
down_revision = 'e4a7c2b9d358'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column('allow_restricted', sa.Boolean(), server_default=sa.false(), nullable=False))
    op.add_column('users', sa.Column('blocked_collection_ids', sa.JSON(), server_default='[]', nullable=False))
    op.add_column('archive_entries', sa.Column('restricted', sa.Boolean(), server_default=sa.false(), nullable=False))
    op.add_column('archive_entries', sa.Column('restricted_locked', sa.Boolean(), server_default=sa.false(), nullable=False))
    op.create_index('ix_archive_entries_restricted', 'archive_entries', ['restricted'])
    op.create_table(
        'user_entry_flags',
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('archive_entry_id', sa.String(36), sa.ForeignKey('archive_entries.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('favorite', sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column('completed', sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    # The server-wide switches become per-user access: administrators keep what they could see, and the
    # hidden collections become blocked collections for everyone else.
    op.execute("UPDATE users SET allow_restricted = true WHERE is_superuser")
    op.execute(
        "UPDATE users SET blocked_collection_ids = s.value FROM system_settings s "
        "WHERE s.key = 'hidden_collections' AND NOT users.is_superuser"
    )
    op.execute("DELETE FROM system_settings WHERE key IN ('vn_sources', 'hidden_collections')")


def downgrade() -> None:
    op.drop_table('user_entry_flags')
    op.drop_index('ix_archive_entries_restricted', table_name='archive_entries')
    op.drop_column('archive_entries', 'restricted_locked')
    op.drop_column('archive_entries', 'restricted')
    op.drop_column('users', 'blocked_collection_ids')
    op.drop_column('users', 'allow_restricted')
