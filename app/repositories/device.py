from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.device import Device
from app.repositories.base import BaseRepository


class DeviceRepository(BaseRepository[Device]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, Device)

    def list_enabled(self) -> list[Device]:
        stmt = select(Device).where(Device.enabled.is_(True)).order_by(Device.hostname)
        return list(self.db.scalars(stmt).all())
