from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.repositories.diff import DiffRepository
from app.schemas.diff import DiffRead

router = APIRouter(prefix="/api/diffs", tags=["diffs"])


@router.get("", response_model=list[DiffRead])
def list_diffs(db: Session = Depends(get_db)) -> list[DiffRead]:
    return [DiffRead.model_validate(diff) for diff in DiffRepository(db).list_recent()]
