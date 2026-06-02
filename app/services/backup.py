from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.logging import backup_logger
from app.database.session import SessionLocal
from app.models.backup import Backup, BackupStatus
from app.models.backup_job import BackupJob
from app.models.device import Device
from app.repositories.backup import BackupJobRepository, BackupRepository
from app.repositories.device import DeviceRepository
from app.services.credential import CredentialService
from app.services.diff import DiffService
from app.services.drivers import DRIVER_REGISTRY
from app.services.notification import BackupSummary, NotificationService
from app.services.settings import AppSettingsService


@dataclass(frozen=True)
class BackupResult:
    device_id: int
    hostname: str
    status: BackupStatus
    file_path: str | None = None
    error_message: str | None = None


class BackupService:
    def __init__(self, db: Session, settings: Settings | None = None) -> None:
        self.db = db
        self.settings = settings or get_settings()
        self.devices = DeviceRepository(db)
        self.backups = BackupRepository(db)
        self.jobs = BackupJobRepository(db)
        self.credentials = CredentialService(db)
        self.notifications = NotificationService.from_db(AppSettingsService(db))

    def run(self, device_ids: list[int] | None = None, triggered_by: str | None = None) -> BackupJob:
        selected_devices = self._select_devices(device_ids)
        job = self.jobs.create(
            {
                "status": "running",
                "total": len(selected_devices),
                "running": len(selected_devices),
                "triggered_by": triggered_by,
            }
        )
        return self.run_existing_job(job.id, [device.id for device in selected_devices])

    def create_job(self, device_ids: list[int] | None = None, triggered_by: str | None = None) -> BackupJob:
        selected_devices = self._select_devices(device_ids)
        return self.jobs.create(
            {
                "status": "queued",
                "total": len(selected_devices),
                "running": 0,
                "triggered_by": triggered_by,
            }
        )

    def run_existing_job(self, job_id: int, device_ids: list[int] | None = None) -> BackupJob:
        job = self.jobs.get(job_id)
        if job is None:
            raise RuntimeError(f"Backup job {job_id} not found")
        selected_devices = self._select_devices(device_ids)
        job.status = "running"
        job.total = len(selected_devices)
        job.running = len(selected_devices)
        self.db.commit()
        results: list[BackupResult] = []
        with ThreadPoolExecutor(max_workers=self.settings.backup_workers) as executor:
            futures = [executor.submit(self._run_device_backup, device.id, job.id) for device in selected_devices]
            for future in as_completed(futures):
                try:
                    results.append(future.result())
                except Exception as exc:
                    backup_logger.exception("backup_worker_unhandled")
                    results.append(
                        BackupResult(
                            device_id=0,
                            hostname="unknown",
                            status=BackupStatus.failed,
                            error_message=str(exc),
                        )
                    )

        job.success = sum(1 for result in results if result.status == BackupStatus.success)
        job.failed = sum(1 for result in results if result.status == BackupStatus.failed)
        job.running = 0
        job.status = "success" if job.failed == 0 else "partial_failed"
        job.finished_at = datetime.now(timezone.utc)
        if job.total == 0:
            job.status = "empty"
        self.db.commit()
        self.db.refresh(job)
        self.notifications.send_backup_summary(
            BackupSummary(
                total=job.total,
                success=job.success,
                failed=job.failed,
                failed_devices=[result.hostname for result in results if result.status == BackupStatus.failed],
            )
        )
        return job

    def _select_devices(self, device_ids: list[int] | None) -> list[Device]:
        if device_ids:
            return [device for id_ in device_ids if (device := self.devices.get(id_)) and device.enabled]
        return self.devices.list_enabled()

    def _run_device_backup(self, device_id: int, job_id: int) -> BackupResult:
        db = SessionLocal()
        device = db.get(Device, device_id)
        if device is None:
            db.close()
            return BackupResult(device_id, f"device-{device_id}", BackupStatus.failed, error_message="Not found")
        credentials = CredentialService(db)
        backup = Backup(
            device_id=device.id,
            job_id=job_id,
            status=BackupStatus.running.value,
            started_at=datetime.now(timezone.utc),
        )
        db.add(backup)
        db.commit()
        db.refresh(backup)
        try:
            output_dir = self._device_output_dir(device)
            output_dir.mkdir(parents=True, exist_ok=True)
            credential = device.credential
            password, enable_secret = credentials.reveal(credential)
            driver_cls = DRIVER_REGISTRY[device.vendor]
            driver = driver_cls(
                host=device.ip,
                username=credential.username,
                password=password,
                enable_secret=enable_secret,
                output_dir=output_dir,
            )
            try:
                driver.connect()
                config = driver.backup()
            finally:
                driver.disconnect()
            file_path = output_dir / "running-config.txt"
            file_path.write_text(config, encoding="utf-8")
            backup.status = BackupStatus.success.value
            backup.file_path = str(file_path)
            backup.finished_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(backup)
            DiffService(db).create_for_backup(backup)
            backup_logger.info("backup_success", extra={"device": device.hostname, "backup_id": backup.id})
            return BackupResult(device.id, device.hostname, BackupStatus.success, str(file_path))
        except Exception as exc:
            backup.status = BackupStatus.failed.value
            backup.error_message = str(exc)
            backup.finished_at = datetime.now(timezone.utc)
            db.commit()
            backup_logger.exception("backup_failed", extra={"device": device.hostname})
            return BackupResult(device.id, device.hostname, BackupStatus.failed, error_message=str(exc))
        finally:
            db.close()

    def _device_output_dir(self, device: Device) -> Path:
        now = datetime.now(timezone.utc)
        safe_name = device.hostname.replace("/", "_").replace(" ", "_")
        return self.settings.backup_root / f"{now:%Y}" / f"{now:%m}" / f"{now:%d}" / safe_name


def run_backup_job(job_id: int, device_ids: list[int] | None = None) -> None:
    db = SessionLocal()
    try:
        BackupService(db).run_existing_job(job_id, device_ids)
    except Exception as exc:
        job = BackupJobRepository(db).get(job_id)
        if job is not None:
            job.status = "failed"
            job.error_message = str(exc)
            job.running = 0
            job.finished_at = datetime.now(timezone.utc)
            db.commit()
        backup_logger.exception("backup_job_failed", extra={"job_id": job_id})
    finally:
        db.close()
