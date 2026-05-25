import uuid

import sqlalchemy as sa
from sqlalchemy.orm import mapped_column, relationship

from app.db.base import Base
from app.utils.enums import JobStatus, JobType


class JobHistory(Base):
    __tablename__ = "job_history"
    __allow_unmapped__ = True

    id: str = mapped_column(sa.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_type: JobType = mapped_column(sa.Enum(JobType, name="job_type"), nullable=False)
    status: JobStatus = mapped_column(sa.Enum(JobStatus, name="job_status"), nullable=False, default=JobStatus.PENDING)
    progress: int = mapped_column(sa.Integer, default=0, nullable=False)
    details: str = mapped_column(sa.Text, nullable=True)
    result: str = mapped_column(sa.Text, nullable=True)
    task_id: str = mapped_column(sa.String(255), nullable=True)
    started_at = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    completed_at = mapped_column(sa.DateTime(timezone=True), nullable=True)
    user_id = mapped_column(sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    user = relationship("User")
