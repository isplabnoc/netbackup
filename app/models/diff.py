from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base


class Diff(Base):
    __tablename__ = "diffs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id"), index=True)
    backup_id: Mapped[int] = mapped_column(ForeignKey("backups.id"), index=True)
    previous_backup_id: Mapped[int | None] = mapped_column(ForeignKey("backups.id"), nullable=True)
    added_lines: Mapped[int] = mapped_column(Integer, default=0)
    removed_lines: Mapped[int] = mapped_column(Integer, default=0)
    html: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    device = relationship("Device", back_populates="diffs")
    backup = relationship("Backup", foreign_keys=[backup_id], back_populates="diffs")
    previous_backup = relationship("Backup", foreign_keys=[previous_backup_id])
