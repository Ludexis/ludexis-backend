"""edge_devices
Revision ID: c6d1f8a2e940
Revises: a3c9e5f17b42
Create Date: 2026-10-19 10:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = 'c6d1f8a2e940'
down_revision = 'a3c9e5f17b42'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'edge_devices',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('token_hash', sa.String(length=64), nullable=False),
        sa.Column('autoscan', sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column('match_metadata', sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('version', sa.String(length=32), nullable=True),
        sa.Column('hostname', sa.String(length=256), nullable=True),
        sa.Column('os', sa.String(length=16), nullable=True),
        sa.Column('drives', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
        sa.UniqueConstraint('token_hash'),
    )
    op.add_column('libraries', sa.Column('edge_id', sa.String(length=36), nullable=True))
    op.add_column('libraries', sa.Column('drive_id', sa.String(length=64), nullable=True))
    op.add_column('libraries', sa.Column('drive_subpath', sa.Text(), nullable=True))
    op.add_column('libraries', sa.Column('drive_mount', sa.Text(), nullable=True))
    op.create_foreign_key('libraries_edge_id_fkey', 'libraries', 'edge_devices', ['edge_id'], ['id'], ondelete='SET NULL')
    op.create_index('ix_libraries_edge_id', 'libraries', ['edge_id'])
    # A path is unique per machine instead of across all of them.
    op.drop_constraint('libraries_path_key', 'libraries', type_='unique')
    op.create_index('uq_libraries_location_path', 'libraries', [sa.text("coalesce(edge_id, '')"), 'path'], unique=True)
    op.add_column('job_history', sa.Column('library_id', sa.String(length=36), nullable=True))
    op.create_foreign_key('job_history_library_id_fkey', 'job_history', 'libraries', ['library_id'], ['id'], ondelete='SET NULL')
    op.add_column('job_history', sa.Column('edge_id', sa.String(length=36), nullable=True))
    op.create_foreign_key('job_history_edge_id_fkey', 'job_history', 'edge_devices', ['edge_id'], ['id'], ondelete='SET NULL')
    op.create_index('ix_job_history_edge_id', 'job_history', ['edge_id'])


def downgrade() -> None:
    op.drop_index('ix_job_history_edge_id', table_name='job_history')
    op.drop_constraint('job_history_edge_id_fkey', 'job_history', type_='foreignkey')
    op.drop_column('job_history', 'edge_id')
    op.drop_constraint('job_history_library_id_fkey', 'job_history', type_='foreignkey')
    op.drop_column('job_history', 'library_id')
    op.drop_index('uq_libraries_location_path', table_name='libraries')
    op.create_unique_constraint('libraries_path_key', 'libraries', ['path'])
    op.drop_index('ix_libraries_edge_id', table_name='libraries')
    op.drop_constraint('libraries_edge_id_fkey', 'libraries', type_='foreignkey')
    op.drop_column('libraries', 'drive_mount')
    op.drop_column('libraries', 'drive_subpath')
    op.drop_column('libraries', 'drive_id')
    op.drop_column('libraries', 'edge_id')
    op.drop_table('edge_devices')
