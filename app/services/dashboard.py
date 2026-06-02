from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.models.backup import Backup, BackupStatus
from app.models.backup_job import BackupJob
from app.models.device import Device
from app.models.diff import Diff


class DashboardService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def metrics(self) -> dict[str, object]:
        now = datetime.now(ZoneInfo("America/Sao_Paulo"))
        today_start = datetime.combine(now.date(), time.min, tzinfo=now.tzinfo)
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
        files_today = int(
            self.db.scalar(
                select(func.count())
                .select_from(Backup)
                .where(
                    Backup.status == BackupStatus.success.value,
                    Backup.finished_at >= today_start,
                )
            )
            or 0
        )
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
        latest_devices = self._latest_devices()
        history = self.db.scalars(
            select(Backup).order_by(desc(Backup.created_at), desc(Backup.id)).limit(5)
        ).all()
        recent_diffs = self.db.scalars(
            select(Diff).order_by(desc(Diff.created_at), desc(Diff.id)).limit(3)
        ).all()
        latest_jobs = self.db.scalars(
            select(BackupJob).order_by(desc(BackupJob.created_at), desc(BackupJob.id)).limit(3)
        ).all()
        return {
            "total_devices": total_devices,
            "backup_success": success,
            "backup_failed": failed,
            "last_backup": last_backup,
            "files_today": files_today,
            "changes_detected": changes,
            "failures_by_vendor": [{"label": vendor, "value": total} for vendor, total in failures_by_vendor],
            "changes_by_day": [{"label": str(day), "value": total} for day, total in changes_by_day],
            "backups_by_day": [
                {"label": str(day), "status": status, "value": total}
                for day, status, total in backups_by_day
            ],
            "latest_devices": latest_devices,
            "history": [
                {
                    "id": backup.id,
                    "device": backup.device.hostname if backup.device else "-",
                    "created_at": backup.created_at.strftime("%d/%m/%Y %H:%M:%S"),
                    "status": backup.status,
                    "file_path": backup.file_path,
                    "error_message": backup.error_message,
                }
                for backup in history
            ],
            "recent_diffs": [
                {
                    "id": diff.id,
                    "device": diff.device.hostname if diff.device else "-",
                    "created_at": diff.created_at.strftime("%d/%m/%Y %H:%M:%S"),
                    "added_lines": diff.added_lines,
                    "removed_lines": diff.removed_lines,
                }
                for diff in recent_diffs
            ],
            "latest_jobs": [
                {
                    "id": job.id,
                    "created_at": job.created_at.strftime("%d/%m/%Y %H:%M:%S"),
                    "status": job.status,
                    "total": job.total,
                    "success": job.success,
                    "failed": job.failed,
                }
                for job in latest_jobs
            ],
            "current_time": now.strftime("%H:%M:%S"),
            "current_date": now.strftime("%d/%m/%Y"),
        }

    def _latest_devices(self) -> list[dict[str, object]]:
        devices = self.db.scalars(select(Device).order_by(Device.hostname).limit(8)).all()
        rows: list[dict[str, object]] = []
        for device in devices:
            latest_backup = self.db.scalars(
                select(Backup)
                .where(Backup.device_id == device.id)
                .order_by(desc(Backup.created_at), desc(Backup.id))
                .limit(1)
            ).first()
            rows.append(
                {
                    "id": device.id,
                    "hostname": device.hostname,
                    "ip": device.ip,
                    "vendor": device.vendor,
                    "platform": device.platform,
                    "enabled": device.enabled,
                    "backup_id": latest_backup.id if latest_backup else None,
                    "backup_status": latest_backup.status if latest_backup else "never",
                    "last_backup": latest_backup.created_at.strftime("%d/%m/%Y %H:%M:%S")
                    if latest_backup
                    else "Nunca executado",
                    "error_message": latest_backup.error_message if latest_backup else None,
                    "file_path": latest_backup.file_path if latest_backup else None,
                }
            )
        return rows
