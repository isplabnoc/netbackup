from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.backup import Backup, BackupStatus
from app.models.device import Device
from app.models.diff import Diff

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("")
def reports(db: Session = Depends(get_db)) -> dict[str, object]:
    since = datetime.now(timezone.utc) - timedelta(days=30)
    total_devices = int(db.scalar(select(func.count()).select_from(Device)) or 0)
    backup_success = int(
        db.scalar(select(func.count()).select_from(Backup).where(Backup.status == BackupStatus.success.value)) or 0
    )
    backup_failed = int(
        db.scalar(select(func.count()).select_from(Backup).where(Backup.status == BackupStatus.failed.value)) or 0
    )
    changes = int(db.scalar(select(func.count()).select_from(Diff).where(Diff.created_at >= since)) or 0)
    failures_by_vendor = db.execute(
        select(Device.vendor, func.count(Backup.id))
        .join(Backup, Backup.device_id == Device.id)
        .where(Backup.status == BackupStatus.failed.value)
        .group_by(Device.vendor)
    ).all()
    return {
        "total_devices": total_devices,
        "backup_success": backup_success,
        "backup_failed": backup_failed,
        "changes_detected": changes,
        "failures_by_vendor": [{"vendor": vendor, "total": total} for vendor, total in failures_by_vendor],
    }
