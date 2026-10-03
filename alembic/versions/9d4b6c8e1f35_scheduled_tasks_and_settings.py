"""scheduled_tasks_and_settings
Revision ID: 9d4b6c8e1f35
Revises: 7a1f3d5e9c22
Create Date: 2026-10-06 15:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = '9d4b6c8e1f35'
down_revision = '7a1f3d5e9c22'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Default rows are created by SchedulerService on first use, so code and database never disagree.
    op.create_table('system_settings',
    sa.Column('key', sa.String(length=64), nullable=False),
    sa.Column('value', sa.JSON(), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('key')
    )
    op.create_table('scheduled_tasks',
    sa.Column('key', sa.String(length=64), nullable=False),
    sa.Column('job_type', sa.String(length=32), nullable=False),
    sa.Column('enabled', sa.Boolean(), nullable=False),
    sa.Column('hour', sa.Integer(), nullable=False),
    sa.Column('minute', sa.Integer(), nullable=False),
    sa.Column('day_of_week', sa.Integer(), nullable=True),
    sa.Column('last_run_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('last_job_id', sa.String(length=36), nullable=True),
    sa.PrimaryKeyConstraint('key')
    )


def downgrade() -> None:
    op.drop_table('scheduled_tasks')
    op.drop_table('system_settings')
