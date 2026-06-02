from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import require_role
from app.core.rbac import Role
from app.database.session import get_db
from app.repositories.credential import CredentialRepository
from app.schemas.credential import CredentialCreate, CredentialRead
from app.services.credential import CredentialService

router = APIRouter(prefix="/api/credentials", tags=["credentials"])


@router.get("", response_model=list[CredentialRead])
def list_credentials(
    db: Session = Depends(get_db),
    _user=Depends(require_role(Role.viewer)),
) -> list[CredentialRead]:
    return [CredentialRead.model_validate(item) for item in CredentialRepository(db).list(limit=1000)]


@router.post("", response_model=CredentialRead, status_code=status.HTTP_201_CREATED)
def create_credential(
    payload: CredentialCreate,
    db: Session = Depends(get_db),
    _user=Depends(require_role(Role.admin)),
) -> CredentialRead:
    credential = CredentialService(db).create(payload)
    return CredentialRead.model_validate(credential)
