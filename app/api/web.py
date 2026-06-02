from fastapi import APIRouter, BackgroundTasks, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_role
from app.core.rbac import Role
from app.core.rate_limit import limiter
from app.core.security import (
    create_access_token,
    generate_csrf_token,
    get_password_hash,
    validate_csrf_token,
    verify_password,
)
from app.database.session import get_db
from app.models.device import Vendor
from app.repositories.backup import BackupRepository
from app.repositories.credential import CredentialRepository
from app.repositories.device import DeviceRepository
from app.repositories.diff import DiffRepository
from app.repositories.user import UserRepository
from app.schemas.credential import CredentialCreate
from app.schemas.device import DeviceCreate
from app.services.backup import BackupService, run_backup_job
from app.services.credential import CredentialService
from app.services.dashboard import DashboardService
from app.services.settings import AppSettingsService

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
            "error": request.query_params.get("error"),
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
    if CredentialRepository(db).get(credential_group_id) is None:
        return RedirectResponse("/devices?error=credential", status_code=303)
    try:
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
    except IntegrityError:
        db.rollback()
        return RedirectResponse("/devices?error=duplicate", status_code=303)
    return RedirectResponse("/devices", status_code=303)


@router.get("/credentials", response_class=HTMLResponse)
def credentials_page(
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(require_role(Role.operator)),
) -> HTMLResponse:
    return templates.TemplateResponse(
        "credentials/index.html",
        {
            "request": request,
            "user": user,
            "credentials": CredentialRepository(db).list(limit=1000),
            "csrf_token": generate_csrf_token(request),
            "error": request.query_params.get("error"),
        },
    )


@router.post("/credentials")
def credentials_create(
    request: Request,
    name: str = Form(),
    username: str = Form(),
    password: str = Form(),
    enable_secret: str | None = Form(default=None),
    csrf_token: str = Form(),
    db: Session = Depends(get_db),
    _user=Depends(require_role(Role.operator)),
) -> RedirectResponse:
    validate_csrf_token(request, csrf_token)
    try:
        CredentialService(db).create(
            CredentialCreate(
                name=name,
                username=username,
                password=password,
                enable_secret=enable_secret or None,
            )
        )
    except IntegrityError:
        db.rollback()
        return RedirectResponse("/credentials?error=duplicate", status_code=303)
    except RuntimeError:
        return RedirectResponse("/credentials?error=fernet", status_code=303)
    return RedirectResponse("/credentials", status_code=303)


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
    background_tasks: BackgroundTasks,
    csrf_token: str = Form(),
    db: Session = Depends(get_db),
    user=Depends(require_role(Role.operator)),
) -> RedirectResponse:
    validate_csrf_token(request, csrf_token)
    job = BackupService(db).create_job(triggered_by=user.email)
    background_tasks.add_task(run_backup_job, job.id, None)
    return RedirectResponse("/backups", status_code=303)


@router.get("/diffs", response_class=HTMLResponse)
def diffs_page(request: Request, db: Session = Depends(get_db), user=Depends(get_current_user)) -> HTMLResponse:
    return templates.TemplateResponse(
        "diffs/index.html",
        {"request": request, "user": user, "diffs": DiffRepository(db).list_recent()},
    )


@router.get("/settings", response_class=HTMLResponse)
def settings_page(
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(require_role(Role.admin)),
) -> HTMLResponse:
    settings_service = AppSettingsService(db)
    return templates.TemplateResponse(
        "settings/index.html",
        {
            "request": request,
            "user": user,
            "scheduler": settings_service.scheduler_config(),
            "notifications": settings_service.notification_config(),
            "csrf_token": generate_csrf_token(request),
        },
    )


@router.post("/settings")
def settings_save(
    request: Request,
    scheduler_enabled: str | None = Form(default=None),
    scheduler_hour: int = Form(),
    scheduler_minute: int = Form(),
    telegram_bot_token: str | None = Form(default=None),
    telegram_chat_id: str | None = Form(default=None),
    evolution_api_url: str | None = Form(default=None),
    evolution_api_token: str | None = Form(default=None),
    evolution_api_instance: str | None = Form(default=None),
    csrf_token: str = Form(),
    db: Session = Depends(get_db),
    _user=Depends(require_role(Role.admin)),
) -> RedirectResponse:
    validate_csrf_token(request, csrf_token)
    settings_service = AppSettingsService(db)
    settings_service.set("scheduler.enabled", "true" if scheduler_enabled else "false")
    settings_service.set("scheduler.hour", str(scheduler_hour))
    settings_service.set("scheduler.minute", str(scheduler_minute))
    settings_service.set("telegram.bot_token", telegram_bot_token or None, encrypted=True)
    settings_service.set("telegram.chat_id", telegram_chat_id or None)
    settings_service.set("evolution.api_url", evolution_api_url or None)
    settings_service.set("evolution.api_token", evolution_api_token or None, encrypted=True)
    settings_service.set("evolution.api_instance", evolution_api_instance or None)
    return RedirectResponse("/settings", status_code=303)


@router.get("/users", response_class=HTMLResponse)
def users_page(
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(require_role(Role.admin)),
) -> HTMLResponse:
    return templates.TemplateResponse(
        "users/index.html",
        {
            "request": request,
            "user": user,
            "users": UserRepository(db).list(limit=1000),
            "roles": [role.value for role in Role],
            "csrf_token": generate_csrf_token(request),
            "error": request.query_params.get("error"),
        },
    )


@router.post("/users")
def users_create(
    request: Request,
    email: str = Form(),
    full_name: str = Form(),
    password: str = Form(),
    role: Role = Form(),
    csrf_token: str = Form(),
    db: Session = Depends(get_db),
    _user=Depends(require_role(Role.admin)),
) -> RedirectResponse:
    validate_csrf_token(request, csrf_token)
    try:
        UserRepository(db).create(
            {
                "email": email,
                "full_name": full_name,
                "hashed_password": get_password_hash(password),
                "role": role.value,
                "is_active": True,
            }
        )
    except IntegrityError:
        db.rollback()
        return RedirectResponse("/users?error=duplicate", status_code=303)
    return RedirectResponse("/users", status_code=303)
