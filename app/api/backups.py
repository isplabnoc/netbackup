from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import require_role
from app.core.rbac import Role
from app.database.session import get_db
from app.repositories.backup import BackupRepository
from app.schemas.backup import BackupJobRead, BackupRead, BackupRunRequest
from app.services.backup import BackupService, run_backup_job

router = APIRouter(prefix="/api/backups", tags=["backups"])


@router.get("", response_model=list[BackupRead])
def list_backups(db: Session = Depends(get_db)) -> list[BackupRead]:
    return [BackupRead.model_validate(backup) for backup in BackupRepository(db).list(limit=500)]


@router.post("/run", response_model=BackupJobRead)
def run_backups(
    payload: BackupRunRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user=Depends(require_role(Role.operator)),
) -> BackupJobRead:
    job = BackupService(db).create_job(payload.device_ids, triggered_by=user.email)
    background_tasks.add_task(run_backup_job, job.id, payload.device_ids)
    return BackupJobRead.model_validate(job)


@router.get("/{backup_id}/download")
def download_backup(
    backup_id: int,
    db: Session = Depends(get_db),
    _user=Depends(require_role(Role.viewer)),
) -> FileResponse:
    backup = BackupRepository(db).get(backup_id)
    if backup is None or not backup.file_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Backup file not found")
    path = Path(backup.file_path)
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Backup file missing on disk")
    return FileResponse(path, filename=path.name, media_type="text/plain")
