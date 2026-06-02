from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base


class BackupStatus(StrEnum):
    pending = "pending"
    running = "running"
    success = "success"
    failed = "failed"


class Backup(Base):
    __tablename__ = "backups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id"), index=True)
    job_id: Mapped[int | None] = mapped_column(ForeignKey("backup_jobs.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default=BackupStatus.pending.value, index=True)
    file_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    device = relationship("Device", back_populates="backups")
    job = relationship("BackupJob", back_populates="backups")
    diffs = relationship(
        "Diff",
        back_populates="backup",
        foreign_keys="Diff.backup_id",
        cascade="all, delete-orphan",
    )
