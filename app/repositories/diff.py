from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.diff import Diff
from app.repositories.base import BaseRepository


class DiffRepository(BaseRepository[Diff]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, Diff)

    def list_recent(self, limit: int = 100) -> list[Diff]:
        stmt = select(Diff).order_by(Diff.created_at.desc()).limit(limit)
        return list(self.db.scalars(stmt).all())

    def list_for_device(self, device_id: int, limit: int = 100) -> list[Diff]:
        stmt = select(Diff).where(Diff.device_id == device_id).order_by(Diff.created_at.desc()).limit(limit)
        return list(self.db.scalars(stmt).all())
