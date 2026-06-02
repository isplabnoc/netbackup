from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_role
from app.core.rbac import Role
from app.database.session import get_db
from app.repositories.diff import DiffRepository
from app.schemas.diff import DiffRead

router = APIRouter(prefix="/api/diffs", tags=["diffs"])


@router.get("", response_model=list[DiffRead])
def list_diffs(
    db: Session = Depends(get_db),
    _user=Depends(require_role(Role.viewer)),
) -> list[DiffRead]:
    return [DiffRead.model_validate(diff) for diff in DiffRepository(db).list_recent()]
