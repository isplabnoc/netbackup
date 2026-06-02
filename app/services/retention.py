from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.backup import Backup
from app.services.settings import AppSettingsService


class RetentionService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = AppSettingsService(db)

    def retention_days(self) -> int:
        return int(self.settings.get("retention.days", "365") or 365)

    def cleanup(self) -> int:
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.retention_days())
        backups = self.db.scalars(select(Backup).where(Backup.created_at < cutoff)).all()
        removed = 0
        for backup in backups:
            if backup.file_path:
                path = Path(backup.file_path)
                if path.exists():
                    path.unlink()
            self.db.delete(backup)
            removed += 1
        self.db.commit()
        return removed
