from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.backup import Backup, BackupStatus
from app.models.device import Device
from app.models.diff import Diff


class DashboardService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def metrics(self) -> dict[str, object]:
        since = datetime.now(timezone.utc) - timedelta(days=30)
        total_devices = int(self.db.scalar(select(func.count()).select_from(Device)) or 0)
        success = int(
            self.db.scalar(select(func.count()).select_from(Backup).where(Backup.status == BackupStatus.success.value))
            or 0
        )
        failed = int(
            self.db.scalar(select(func.count()).select_from(Backup).where(Backup.status == BackupStatus.failed.value))
            or 0
        )
        last_backup_raw = self.db.scalar(select(func.max(Backup.finished_at)).select_from(Backup))
        last_backup = last_backup_raw.strftime("%H:%M:%S") if last_backup_raw else None
        changes = int(self.db.scalar(select(func.count()).select_from(Diff).where(Diff.created_at >= since)) or 0)
        failures_by_vendor = self.db.execute(
            select(Device.vendor, func.count(Backup.id))
            .join(Backup, Backup.device_id == Device.id)
            .where(Backup.status == BackupStatus.failed.value)
            .group_by(Device.vendor)
        ).all()
        changes_by_day = self.db.execute(
            select(func.date(Diff.created_at), func.count(Diff.id))
            .where(Diff.created_at >= since)
            .group_by(func.date(Diff.created_at))
            .order_by(func.date(Diff.created_at))
        ).all()
        backups_by_day = self.db.execute(
            select(func.date(Backup.created_at), Backup.status, func.count(Backup.id))
            .where(Backup.created_at >= since)
            .group_by(func.date(Backup.created_at), Backup.status)
            .order_by(func.date(Backup.created_at))
        ).all()
        return {
            "total_devices": total_devices,
            "backup_success": success,
            "backup_failed": failed,
            "last_backup": last_backup,
            "changes_detected": changes,
            "failures_by_vendor": [{"label": vendor, "value": total} for vendor, total in failures_by_vendor],
            "changes_by_day": [{"label": str(day), "value": total} for day, total in changes_by_day],
            "backups_by_day": [
                {"label": str(day), "status": status, "value": total}
                for day, status, total in backups_by_day
            ],
        }
