from apscheduler.schedulers.background import BackgroundScheduler

from app.core.config import get_settings
from app.core.logging import app_logger
from app.database.session import SessionLocal
from app.services.backup import BackupService
from app.services.settings import AppSettingsService

scheduler = BackgroundScheduler(timezone="UTC")


def run_scheduled_backup() -> None:
    db = SessionLocal()
    try:
        BackupService(db).run(triggered_by="scheduler")
    finally:
        db.close()


def start_scheduler() -> None:
    settings = get_settings()
    db = SessionLocal()
    try:
        scheduler_config = AppSettingsService(db).scheduler_config()
    finally:
        db.close()
    if scheduler.running:
        return
    if not scheduler_config["enabled"]:
        app_logger.info("scheduler_disabled")
        return
    scheduler.add_job(
        run_scheduled_backup,
        trigger="cron",
        hour=int(scheduler_config["hour"]),
        minute=int(scheduler_config["minute"]),
        id="daily-network-backup",
        replace_existing=True,
    )
    scheduler.start()
    app_logger.info("scheduler_started")


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
        app_logger.info("scheduler_stopped")
