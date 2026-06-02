from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_role
from app.core.rbac import Role
from app.core.rate_limit import limiter
from app.core.security import create_access_token, generate_csrf_token, validate_csrf_token, verify_password
from app.database.session import get_db
from app.models.device import Vendor
from app.repositories.backup import BackupRepository
from app.repositories.credential import CredentialRepository
from app.repositories.device import DeviceRepository
from app.repositories.diff import DiffRepository
from app.repositories.user import UserRepository
from app.schemas.device import DeviceCreate
from app.services.backup import BackupService
from app.services.dashboard import DashboardService

templates = Jinja2Templates(directory="app/templates")
router = APIRouter(tags=["web"])


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("auth/login.html", {"request": request, "csrf_token": generate_csrf_token(request)})


@router.post("/login")
@limiter.limit("10/minute")
def login_submit(
    request: Request,
    email: str = Form(),
    password: str = Form(),
    csrf_token: str = Form(),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    validate_csrf_token(request, csrf_token)
    user = UserRepository(db).get_by_email(email)
    if user is None or not verify_password(password, user.hashed_password):
        return RedirectResponse("/login?error=1", status_code=303)
    token = create_access_token(user.email, user.role)
    response = RedirectResponse("/", status_code=303)
    response.set_cookie("access_token", f"Bearer {token}", httponly=True, samesite="lax")
    return response


@router.post("/logout")
def web_logout() -> RedirectResponse:
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie("access_token")
    return response


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db), user=Depends(get_current_user)) -> HTMLResponse:
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "user": user,
            "metrics": DashboardService(db).metrics(),
            "csrf_token": generate_csrf_token(request),
        },
    )


@router.get("/devices", response_class=HTMLResponse)
def devices_page(request: Request, db: Session = Depends(get_db), user=Depends(get_current_user)) -> HTMLResponse:
    return templates.TemplateResponse(
        "devices/index.html",
        {
            "request": request,
            "user": user,
            "devices": DeviceRepository(db).list(limit=1000),
            "credentials": CredentialRepository(db).list(limit=1000),
            "vendors": [vendor.value for vendor in Vendor],
            "csrf_token": generate_csrf_token(request),
        },
    )


@router.post("/devices")
def devices_create(
    request: Request,
    hostname: str = Form(),
    ip: str = Form(),
    vendor: Vendor = Form(),
    platform: str = Form(),
    credential_group_id: int = Form(),
    location: str | None = Form(default=None),
    csrf_token: str = Form(),
    db: Session = Depends(get_db),
    _user=Depends(require_role(Role.operator)),
) -> RedirectResponse:
    validate_csrf_token(request, csrf_token)
    DeviceRepository(db).create(
        DeviceCreate(
            hostname=hostname,
            ip=ip,
            vendor=vendor,
            platform=platform,
            credential_group_id=credential_group_id,
            location=location,
        ).model_dump(mode="json")
    )
    return RedirectResponse("/devices", status_code=303)


@router.get("/backups", response_class=HTMLResponse)
def backups_page(request: Request, db: Session = Depends(get_db), user=Depends(get_current_user)) -> HTMLResponse:
    return templates.TemplateResponse(
        "backups/index.html",
        {
            "request": request,
            "user": user,
            "backups": BackupRepository(db).list(limit=500),
            "csrf_token": generate_csrf_token(request),
        },
    )


@router.post("/backups/run")
def web_run_backups(
    request: Request,
    csrf_token: str = Form(),
    db: Session = Depends(get_db),
    user=Depends(require_role(Role.operator)),
) -> RedirectResponse:
    validate_csrf_token(request, csrf_token)
    BackupService(db).run(triggered_by=user.email)
    return RedirectResponse("/backups", status_code=303)


@router.get("/diffs", response_class=HTMLResponse)
def diffs_page(request: Request, db: Session = Depends(get_db), user=Depends(get_current_user)) -> HTMLResponse:
    return templates.TemplateResponse(
        "diffs/index.html",
        {"request": request, "user": user, "diffs": DiffRepository(db).list_recent()},
    )
