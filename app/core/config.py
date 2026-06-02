from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "NetAudit Backup"
    environment: str = "local"
    database_url: str = "postgresql+psycopg://netaudit:netaudit@localhost:5432/netaudit"
    secret_key: str = "change-me"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 480
    fernet_key: str = "change-me"
    backup_root: Path = Path("backups")
    backup_workers: int = Field(default=30, ge=1, le=200)
    daily_backup_cron_hour: int = Field(default=2, ge=0, le=23)
    daily_backup_cron_minute: int = Field(default=0, ge=0, le=59)
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None
    evolution_api_url: str | None = None
    evolution_api_token: str | None = None
    evolution_api_instance: str | None = None

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
