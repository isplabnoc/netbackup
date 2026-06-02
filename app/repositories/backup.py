from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.models.backup import Backup, BackupStatus
from app.models.backup_job import BackupJob
from app.repositories.base import BaseRepository


class BackupRepository(BaseRepository[Backup]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, Backup)

    def latest_success_for_device(self, device_id: int, exclude_backup_id: int | None = None) -> Backup | None:
        stmt = select(Backup).where(
            Backup.device_id == device_id,
            Backup.status == BackupStatus.success.value,
        )
        if exclude_backup_id is not None:
            stmt = stmt.where(Backup.id != exclude_backup_id)
        stmt = stmt.order_by(desc(Backup.finished_at), desc(Backup.id)).limit(1)
        return self.db.scalars(stmt).first()

    def count_by_status(self, status: BackupStatus) -> int:
        stmt = select(func.count()).select_from(Backup).where(Backup.status == status.value)
        return int(self.db.scalar(stmt) or 0)


class BackupJobRepository(BaseRepository[BackupJob]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, BackupJob)

    def running_jobs(self) -> list[BackupJob]:
        stmt = select(BackupJob).where(BackupJob.status.in_(["queued", "running"]))
        return list(self.db.scalars(stmt).all())
