from apscheduler.schedulers.background import BackgroundScheduler

from app.core.config import get_settings
from app.core.logging import app_logger
from app.database.session import SessionLocal
from app.services.backup import BackupService

scheduler = BackgroundScheduler(timezone="UTC")


def run_scheduled_backup() -> None:
    db = SessionLocal()
    try:
        BackupService(db).run(triggered_by="scheduler")
    finally:
        db.close()


def start_scheduler() -> None:
    settings = get_settings()
    if scheduler.running:
        return
    scheduler.add_job(
        run_scheduled_backup,
        trigger="cron",
        hour=settings.daily_backup_cron_hour,
        minute=settings.daily_backup_cron_minute,
        id="daily-network-backup",
        replace_existing=True,
    )
    scheduler.start()
    app_logger.info("scheduler_started")


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
        app_logger.info("scheduler_stopped")
