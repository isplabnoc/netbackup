from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.app_setting import AppSetting
from app.repositories.base import BaseRepository


class AppSettingRepository(BaseRepository[AppSetting]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, AppSetting)

    def get_by_key(self, key: str) -> AppSetting | None:
        stmt = select(AppSetting).where(AppSetting.key == key)
        return self.db.scalars(stmt).first()

    def upsert(self, key: str, value: str | None, encrypted: bool = False) -> AppSetting:
        setting = self.get_by_key(key)
        if setting is None:
            return self.create({"key": key, "value": value, "encrypted": encrypted})
        setting.value = value
        setting.encrypted = encrypted
        self.db.commit()
        self.db.refresh(setting)
        return setting
