from sqlalchemy.orm import Session

from app.models.credential import Credential
from app.repositories.base import BaseRepository


class CredentialRepository(BaseRepository[Credential]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, Credential)
