from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import decrypt_secret, encrypt_secret
from app.repositories.app_setting import AppSettingRepository


class AppSettingsService:
    def __init__(self, db: Session) -> None:
        self.repository = AppSettingRepository(db)

    def get(self, key: str, default: str | None = None) -> str | None:
        setting = self.repository.get_by_key(key)
        if setting is None or setting.value is None:
            return default
        if setting.encrypted:
            return decrypt_secret(setting.value)
        return setting.value

    def set(self, key: str, value: str | None, encrypted: bool = False) -> None:
        stored_value = encrypt_secret(value) if encrypted and value else value
        self.repository.upsert(key, stored_value, encrypted=encrypted)

    def scheduler_config(self) -> dict[str, object]:
        settings = get_settings()
        return {
            "enabled": self.get("scheduler.enabled", "true") == "true",
            "hour": int(self.get("scheduler.hour", str(settings.daily_backup_cron_hour)) or settings.daily_backup_cron_hour),
            "minute": int(
                self.get("scheduler.minute", str(settings.daily_backup_cron_minute))
                or settings.daily_backup_cron_minute
            ),
        }

    def notification_config(self) -> dict[str, str | None]:
        return {
            "telegram_bot_token": self.get("telegram.bot_token"),
            "telegram_chat_id": self.get("telegram.chat_id"),
            "evolution_api_url": self.get("evolution.api_url"),
            "evolution_api_token": self.get("evolution.api_token"),
            "evolution_api_instance": self.get("evolution.api_instance"),
        }
