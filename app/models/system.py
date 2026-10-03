import sqlalchemy as sa
from sqlalchemy.orm import mapped_column

from app.db.base import Base


class SystemSetting(Base):
    __tablename__ = "system_settings"
    __allow_unmapped__ = True

    key: str = mapped_column(sa.String(64), primary_key=True)
    value = mapped_column(sa.JSON, nullable=True)
    updated_at = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)


class ScheduledTask(Base):
    __tablename__ = "scheduled_tasks"
    __allow_unmapped__ = True

    key: str = mapped_column(sa.String(64), primary_key=True)
    job_type: str = mapped_column(sa.String(32), nullable=False)
    enabled: bool = mapped_column(sa.Boolean, nullable=False, default=True)
    hour: int = mapped_column(sa.Integer, nullable=False)
    minute: int = mapped_column(sa.Integer, nullable=False, default=0)
    # 0 = Monday ... 6 = Sunday; empty means every day.
    day_of_week: int = mapped_column(sa.Integer, nullable=True)
    last_run_at = mapped_column(sa.DateTime(timezone=True), nullable=True)
    last_job_id: str = mapped_column(sa.String(36), nullable=True)
