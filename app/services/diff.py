import difflib
from pathlib import Path

from sqlalchemy.orm import Session

from app.models.backup import Backup
from app.models.diff import Diff
from app.repositories.backup import BackupRepository
from app.repositories.diff import DiffRepository


class DiffService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.backups = BackupRepository(db)
        self.diffs = DiffRepository(db)

    def create_for_backup(self, backup: Backup) -> Diff | None:
        if not backup.file_path:
            return None
        previous = self.backups.latest_success_for_device(backup.device_id, exclude_backup_id=backup.id)
        if previous is None or not previous.file_path:
            return None

        current_lines = Path(backup.file_path).read_text(encoding="utf-8").splitlines()
        previous_lines = Path(previous.file_path).read_text(encoding="utf-8").splitlines()
        html = difflib.HtmlDiff(wrapcolumn=120).make_table(
            previous_lines,
            current_lines,
            fromdesc=f"Backup {previous.id}",
            todesc=f"Backup {backup.id}",
            context=True,
            numlines=3,
        )
        added = 0
        removed = 0
        for line in difflib.ndiff(previous_lines, current_lines):
            if line.startswith("+ "):
                added += 1
            elif line.startswith("- "):
                removed += 1
        if added == 0 and removed == 0:
            return None
        diff = Diff(
            device_id=backup.device_id,
            backup_id=backup.id,
            previous_backup_id=previous.id,
            added_lines=added,
            removed_lines=removed,
            html=html,
        )
        self.db.add(diff)
        self.db.commit()
        self.db.refresh(diff)
        return diff
