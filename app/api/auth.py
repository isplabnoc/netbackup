from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.rate_limit import limiter
from app.core.rbac import Role
from app.core.security import create_access_token, get_password_hash, verify_password
from app.database.session import get_db
from app.repositories.user import UserRepository
from app.schemas.user import Token, UserCreate, UserRead

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/token", response_model=Token)
@limiter.limit("10/minute")
def login(
    request: Request,
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
) -> Token:
    user = UserRepository(db).get_by_email(form_data.username)
    if user is None or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = create_access_token(subject=user.email, role=user.role)
    response.set_cookie("access_token", f"Bearer {token}", httponly=True, samesite="lax")
    return Token(access_token=token)


@router.post("/bootstrap-admin", response_model=UserRead, status_code=status.HTTP_201_CREATED)
@limiter.limit("3/minute")
def bootstrap_admin(request: Request, payload: UserCreate, db: Session = Depends(get_db)) -> UserRead:
    repo = UserRepository(db)
    if repo.list(limit=1):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Initial user already exists")
    user = repo.create(
        {
            "email": payload.email,
            "full_name": payload.full_name,
            "hashed_password": get_password_hash(payload.password),
            "role": Role.admin.value,
        }
    )
    return UserRead.model_validate(user)


@router.post("/logout")
def logout(response: Response) -> dict[str, str]:
    response.delete_cookie("access_token")
    return {"detail": "logged out"}
