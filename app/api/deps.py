from collections.abc import Callable

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.rbac import Role, role_allows
from app.core.security import decode_access_token
from app.database.session import get_db
from app.models.user import User
from app.repositories.user import UserRepository

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token", auto_error=False)


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
    token: str | None = Depends(oauth2_scheme),
) -> User:
    raw_token = token or request.cookies.get("access_token")
    if raw_token and raw_token.startswith("Bearer "):
        raw_token = raw_token.removeprefix("Bearer ")
    if not raw_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    payload = decode_access_token(raw_token)
    user = UserRepository(db).get_by_email(str(payload["sub"]))
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive user")
    return user


def require_role(required_role: Role) -> Callable[[User], User]:
    def dependency(user: User = Depends(get_current_user)) -> User:
        current_role = Role(user.role)
        if not role_allows(current_role, required_role):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return user

    return dependency
