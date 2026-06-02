from sqlalchemy.orm import Session

from app.core.security import decrypt_secret, encrypt_secret
from app.models.credential import Credential
from app.repositories.credential import CredentialRepository
from app.schemas.credential import CredentialCreate


class CredentialService:
    def __init__(self, db: Session) -> None:
        self.repository = CredentialRepository(db)

    def create(self, payload: CredentialCreate) -> Credential:
        data = payload.model_dump()
        data["password"] = encrypt_secret(data["password"])
        data["enable_secret"] = encrypt_secret(data.get("enable_secret"))
        return self.repository.create(data)

    def reveal(self, credential: Credential) -> tuple[str, str | None]:
        password = decrypt_secret(credential.password)
        enable_secret = decrypt_secret(credential.enable_secret)
        if password is None:
            raise RuntimeError("Credential password could not be decrypted")
        return password, enable_secret
