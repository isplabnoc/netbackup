import subprocess
from fastapi import APIRouter, BackgroundTasks, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from urllib.parse import quote
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_role
from app.core.rbac import Role
from app.core.rate_limit import limiter
from app.core.security import (
    create_access_token,
    encrypt_secret,
    generate_csrf_token,
    get_password_hash,
    validate_csrf_token,
    verify_password,
)
from app.database.session import get_db
from app.models.device import Vendor
from app.models.user import User
from app.repositories.backup import BackupJobRepository, BackupRepository
from app.repositories.credential import CredentialRepository
from app.repositories.device import DeviceRepository
from app.repositories.diff import DiffRepository
from app.repositories.user import UserRepository
from app.schemas.credential import CredentialCreate
from app.schemas.device import DeviceCreate
from app.services.backup import BackupService, run_backup_job
from app.services.audit import AuditService
from app.services.credential import CredentialService
from app.services.dashboard import DashboardService
from app.services.connection_test import ConnectionTestService
from app.services.settings import AppSettingsService
from app.services.notification import NotificationService
from app.services.retention import RetentionService
from app.workers.scheduler import reload_scheduler

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
    AuditService(db).record("login", "user", str(user.id), user, request.client.host if request.client else None)
    token = create_access_token(user.email, user.role)
    response = RedirectResponse("/", status_code=303)
    response.set_cookie("access_token", f"Bearer {token}", httponly=True, samesite="lax")
    return response


@router.post("/logout")
def web_logout(
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> RedirectResponse:
    AuditService(db).record("logout", "user", str(user.id), user, request.client.host if request.client else None)
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
            "test_result": request.query_params.get("test_result"),
            "test_message": request.query_params.get("test_message"),
        },
    )


@router.post("/devices")
def devices_create(
    request: Request,
    hostname: str = Form(),
    ip: str = Form(),
    ssh_port: int = Form(default=22),
    vendor: Vendor = Form(),
    platform: str = Form(),
    credential_group_id: int = Form(),
    location: str | None = Form(default=None),
    csrf_token: str = Form(),
    db: Session = Depends(get_db),
    user=Depends(require_role(Role.operator)),
) -> RedirectResponse:
    validate_csrf_token(request, csrf_token)
    if CredentialRepository(db).get(credential_group_id) is None:
        return RedirectResponse("/devices?error=credential", status_code=303)
    try:
        device = DeviceRepository(db).create(
            DeviceCreate(
                hostname=hostname,
                ip=ip,
                ssh_port=ssh_port,
                vendor=vendor,
                platform=platform,
                credential_group_id=credential_group_id,
                location=location,
            ).model_dump(mode="json")
        )
        AuditService(db).record("create", "device", str(device.id), user, request.client.host if request.client else None)
    except IntegrityError:
        db.rollback()
        return RedirectResponse("/devices?error=duplicate", status_code=303)
    return RedirectResponse("/devices", status_code=303)


@router.post("/devices/{device_id}/test")
def devices_test(
    device_id: int,
    request: Request,
    csrf_token: str = Form(),
    db: Session = Depends(get_db),
    user=Depends(require_role(Role.operator)),
) -> RedirectResponse:
    validate_csrf_token(request, csrf_token)
    device = DeviceRepository(db).get(device_id)
    if device is None:
        return RedirectResponse("/devices?error=notfound", status_code=303)
    result = ConnectionTestService(db).test_device(device)
    AuditService(db).record(
        "test",
        "device",
        str(device.id),
        user,
        request.client.host if request.client else None,
        {"success": result.success, "message": result.message},
    )
    status = "ok" if result.success else "fail"
    return RedirectResponse(
        f"/devices?test_result={status}&test_message={quote(result.message)}",
        status_code=303,
    )


@router.post("/devices/{device_id}/update")
def devices_update(
    device_id: int,
    request: Request,
    hostname: str = Form(),
    ip: str = Form(),
    ssh_port: int = Form(default=22),
    vendor: Vendor = Form(),
    platform: str = Form(),
    credential_group_id: int = Form(),
    location: str | None = Form(default=None),
    enabled: str | None = Form(default=None),
    csrf_token: str = Form(),
    db: Session = Depends(get_db),
    user=Depends(require_role(Role.operator)),
) -> RedirectResponse:
    validate_csrf_token(request, csrf_token)
    repo = DeviceRepository(db)
    device = repo.get(device_id)
    if device is None:
        return RedirectResponse("/devices?error=notfound", status_code=303)
    try:
        repo.update(
            device,
            {
                "hostname": hostname,
                "ip": ip,
                "ssh_port": ssh_port,
                "vendor": vendor.value,
                "platform": platform,
                "credential_group_id": credential_group_id,
                "location": location,
                "enabled": enabled == "on",
            },
        )
        AuditService(db).record("update", "device", str(device.id), user, request.client.host if request.client else None)
    except IntegrityError:
        db.rollback()
        return RedirectResponse("/devices?error=duplicate", status_code=303)
    return RedirectResponse("/devices", status_code=303)


@router.post("/devices/{device_id}/delete")
def devices_delete(
    device_id: int,
    request: Request,
    csrf_token: str = Form(),
    db: Session = Depends(get_db),
    user=Depends(require_role(Role.admin)),
) -> RedirectResponse:
    validate_csrf_token(request, csrf_token)
    repo = DeviceRepository(db)
    device = repo.get(device_id)
    if device is not None:
        repo.delete(device)
        AuditService(db).record("delete", "device", str(device_id), user, request.client.host if request.client else None)
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
    user=Depends(require_role(Role.operator)),
) -> RedirectResponse:
    validate_csrf_token(request, csrf_token)
    try:
        credential = CredentialService(db).create(
            CredentialCreate(
                name=name,
                username=username,
                password=password,
                enable_secret=enable_secret or None,
            )
        )
        AuditService(db).record(
            "create", "credential", str(credential.id), user, request.client.host if request.client else None
        )
    except IntegrityError:
        db.rollback()
        return RedirectResponse("/credentials?error=duplicate", status_code=303)
    except RuntimeError:
        return RedirectResponse("/credentials?error=fernet", status_code=303)
    return RedirectResponse("/credentials", status_code=303)


@router.post("/credentials/{credential_id}/update")
def credentials_update(
    credential_id: int,
    request: Request,
    name: str = Form(),
    username: str = Form(),
    password: str | None = Form(default=None),
    enable_secret: str | None = Form(default=None),
    csrf_token: str = Form(),
    db: Session = Depends(get_db),
    user=Depends(require_role(Role.operator)),
) -> RedirectResponse:
    validate_csrf_token(request, csrf_token)
    repo = CredentialRepository(db)
    credential = repo.get(credential_id)
    if credential is None:
        return RedirectResponse("/credentials?error=notfound", status_code=303)
    data = {"name": name, "username": username}
    if password:
        data["password"] = encrypt_secret(password)
    if enable_secret:
        data["enable_secret"] = encrypt_secret(enable_secret)
    try:
        repo.update(credential, data)
        AuditService(db).record(
            "update", "credential", str(credential.id), user, request.client.host if request.client else None
        )
    except IntegrityError:
        db.rollback()
        return RedirectResponse("/credentials?error=duplicate", status_code=303)
    except RuntimeError:
        return RedirectResponse("/credentials?error=fernet", status_code=303)
    return RedirectResponse("/credentials", status_code=303)


@router.post("/credentials/{credential_id}/delete")
def credentials_delete(
    credential_id: int,
    request: Request,
    csrf_token: str = Form(),
    db: Session = Depends(get_db),
    user=Depends(require_role(Role.admin)),
) -> RedirectResponse:
    validate_csrf_token(request, csrf_token)
    repo = CredentialRepository(db)
    credential = repo.get(credential_id)
    if credential is not None:
        try:
            repo.delete(credential)
            AuditService(db).record(
                "delete", "credential", str(credential_id), user, request.client.host if request.client else None
            )
        except IntegrityError:
            db.rollback()
            return RedirectResponse("/credentials?error=inuse", status_code=303)
    return RedirectResponse("/credentials", status_code=303)


@router.get("/backups", response_class=HTMLResponse)
def backups_page(request: Request, db: Session = Depends(get_db), user=Depends(get_current_user)) -> HTMLResponse:
    backups = []
    jobs = []
    load_error = None
    try:
        backups = BackupRepository(db).list_recent(limit=500)
        jobs = BackupJobRepository(db).list_recent(limit=100)
    except (RuntimeError, SQLAlchemyError, ValueError) as exc:
        db.rollback()
        load_error = str(exc)
    return templates.TemplateResponse(
        "backups/index.html",
        {
            "request": request,
            "user": user,
            "backups": backups,
            "jobs": jobs,
            "load_error": load_error,
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
    AuditService(db).record("run", "backup_job", str(job.id), user, request.client.host if request.client else None)
    background_tasks.add_task(run_backup_job, job.id, None)
    return RedirectResponse("/backups", status_code=303)


@router.get("/diffs", response_class=HTMLResponse)
def diffs_page(request: Request, db: Session = Depends(get_db), user=Depends(get_current_user)) -> HTMLResponse:
    device_id = request.query_params.get("device_id")
    repo = DiffRepository(db)
    diffs = repo.list_for_device(int(device_id)) if device_id and device_id.isdigit() else repo.list_recent()
    return templates.TemplateResponse(
        "diffs/index.html",
        {"request": request, "user": user, "diffs": diffs, "device_id": device_id},
    )


@router.get("/reports", response_class=HTMLResponse)
def reports_page(request: Request, db: Session = Depends(get_db), user=Depends(get_current_user)) -> HTMLResponse:
    return templates.TemplateResponse(
        "reports/index.html",
        {
            "request": request,
            "user": user,
            "metrics": DashboardService(db).metrics(),
        },
    )


@router.get("/vendors", response_class=HTMLResponse)
def vendors_page(request: Request, db: Session = Depends(get_db), user=Depends(get_current_user)) -> HTMLResponse:
    devices = DeviceRepository(db).list(limit=1000)
    rows = []
    for vendor in Vendor:
        vendor_devices = [device for device in devices if device.vendor == vendor.value]
        rows.append(
            {
                "vendor": vendor.value,
                "total": len(vendor_devices),
                "enabled": len([device for device in vendor_devices if device.enabled]),
                "platforms": sorted({device.platform for device in vendor_devices if device.platform}),
            }
        )
    return templates.TemplateResponse(
        "vendors/index.html",
        {"request": request, "user": user, "rows": rows},
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
            "retention_days": RetentionService(db).retention_days(),
            "notification_test": request.query_params.get("notification_test"),
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
    evolution_api_recipient: str | None = Form(default=None),
    retention_days: int = Form(default=365),
    csrf_token: str = Form(),
    db: Session = Depends(get_db),
    user=Depends(require_role(Role.admin)),
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
    settings_service.set("evolution.api_recipient", evolution_api_recipient or None)
    settings_service.set("retention.days", str(retention_days))
    reload_scheduler()
    AuditService(db).record("update", "settings", "system", user, request.client.host if request.client else None)
    return RedirectResponse("/settings", status_code=303)


@router.post("/settings/test-notifications")
def settings_test_notifications(
    request: Request,
    csrf_token: str = Form(),
    db: Session = Depends(get_db),
    user=Depends(require_role(Role.admin)),
) -> RedirectResponse:
    validate_csrf_token(request, csrf_token)
    results = NotificationService.from_db(AppSettingsService(db)).send_test()
    AuditService(db).record("test", "notifications", "system", user, request.client.host if request.client else None)
    failed = [result.channel for result in results if not result.success]
    status_value = "fail" if failed else "ok"
    return RedirectResponse(f"/settings?notification_test={status_value}", status_code=303)


@router.post("/settings/run-retention")
def settings_run_retention(
    request: Request,
    csrf_token: str = Form(),
    db: Session = Depends(get_db),
    user=Depends(require_role(Role.admin)),
) -> RedirectResponse:
    validate_csrf_token(request, csrf_token)
    RetentionService(db).cleanup()
    AuditService(db).record("run", "retention", "system", user, request.client.host if request.client else None)
    return RedirectResponse("/settings", status_code=303)


@router.get("/integrations/telegram", response_class=HTMLResponse)
def telegram_integration_page(
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(require_role(Role.admin)),
) -> HTMLResponse:
    settings_service = AppSettingsService(db)
    return templates.TemplateResponse(
        "integrations/telegram.html",
        {
            "request": request,
            "user": user,
            "notifications": settings_service.notification_config(),
            "result": request.query_params.get("result"),
            "message": request.query_params.get("message"),
            "csrf_token": generate_csrf_token(request),
        },
    )


@router.post("/integrations/telegram")
def telegram_integration_save(
    request: Request,
    telegram_bot_token: str | None = Form(default=None),
    telegram_chat_id: str | None = Form(default=None),
    csrf_token: str = Form(),
    db: Session = Depends(get_db),
    user=Depends(require_role(Role.admin)),
) -> RedirectResponse:
    validate_csrf_token(request, csrf_token)
    settings_service = AppSettingsService(db)
    settings_service.set("telegram.bot_token", telegram_bot_token or None, encrypted=True)
    settings_service.set("telegram.chat_id", telegram_chat_id or None)
    AuditService(db).record("update", "integration", "telegram", user, request.client.host if request.client else None)
    return RedirectResponse("/integrations/telegram?result=ok&message=Configuracao+salva", status_code=303)


@router.post("/integrations/telegram/test")
def telegram_integration_test(
    request: Request,
    csrf_token: str = Form(),
    db: Session = Depends(get_db),
    user=Depends(require_role(Role.admin)),
) -> RedirectResponse:
    validate_csrf_token(request, csrf_token)
    result = NotificationService.from_db(AppSettingsService(db)).send_telegram(
        "NetBackup Pro: teste real de notificacao Telegram"
    )
    AuditService(db).record("test", "integration", "telegram", user, request.client.host if request.client else None)
    status_value = "ok" if result.success else "fail"
    return RedirectResponse(
        f"/integrations/telegram?result={status_value}&message={quote(result.message)}",
        status_code=303,
    )


@router.get("/integrations/evolution", response_class=HTMLResponse)
def evolution_integration_page(
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(require_role(Role.admin)),
) -> HTMLResponse:
    settings_service = AppSettingsService(db)
    return templates.TemplateResponse(
        "integrations/evolution.html",
        {
            "request": request,
            "user": user,
            "notifications": settings_service.notification_config(),
            "result": request.query_params.get("result"),
            "message": request.query_params.get("message"),
            "csrf_token": generate_csrf_token(request),
        },
    )


@router.post("/integrations/evolution")
def evolution_integration_save(
    request: Request,
    evolution_api_url: str | None = Form(default=None),
    evolution_api_token: str | None = Form(default=None),
    evolution_api_instance: str | None = Form(default=None),
    evolution_api_recipient: str | None = Form(default=None),
    csrf_token: str = Form(),
    db: Session = Depends(get_db),
    user=Depends(require_role(Role.admin)),
) -> RedirectResponse:
    validate_csrf_token(request, csrf_token)
    settings_service = AppSettingsService(db)
    settings_service.set("evolution.api_url", evolution_api_url or None)
    settings_service.set("evolution.api_token", evolution_api_token or None, encrypted=True)
    settings_service.set("evolution.api_instance", evolution_api_instance or None)
    settings_service.set("evolution.api_recipient", evolution_api_recipient or None)
    AuditService(db).record("update", "integration", "evolution", user, request.client.host if request.client else None)
    return RedirectResponse("/integrations/evolution?result=ok&message=Configuracao+salva", status_code=303)


@router.post("/integrations/evolution/test")
def evolution_integration_test(
    request: Request,
    csrf_token: str = Form(),
    db: Session = Depends(get_db),
    user=Depends(require_role(Role.admin)),
) -> RedirectResponse:
    validate_csrf_token(request, csrf_token)
    result = NotificationService.from_db(AppSettingsService(db)).send_evolution(
        "NetBackup Pro: teste real de notificacao Evolution API"
    )
    AuditService(db).record("test", "integration", "evolution", user, request.client.host if request.client else None)
    status_value = "ok" if result.success else "fail"
    return RedirectResponse(
        f"/integrations/evolution?result={status_value}&message={quote(result.message)}",
        status_code=303,
    )


@router.get("/integrations/git", response_class=HTMLResponse)
def git_integration_page(
    request: Request,
    user=Depends(require_role(Role.admin)),
) -> HTMLResponse:
    git_info = {"available": False, "branch": "-", "commit": "-", "status": "Repositorio Git indisponivel."}
    try:
        branch = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout.strip()
        commit = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout.strip()
        status_text = subprocess.run(
            ["git", "status", "--short"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout.strip()
        git_info = {
            "available": True,
            "branch": branch,
            "commit": commit,
            "status": status_text or "Working tree limpo.",
        }
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        git_info["status"] = str(exc)
    return templates.TemplateResponse(
        "integrations/git.html",
        {"request": request, "user": user, "git_info": git_info},
    )


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
    user=Depends(require_role(Role.admin)),
) -> RedirectResponse:
    validate_csrf_token(request, csrf_token)
    try:
        created_user = UserRepository(db).create(
            {
                "email": email,
                "full_name": full_name,
                "hashed_password": get_password_hash(password),
                "role": role.value,
                "is_active": True,
            }
        )
        AuditService(db).record(
            "create", "user", str(created_user.id), user, request.client.host if request.client else None
        )
    except IntegrityError:
        db.rollback()
        return RedirectResponse("/users?error=duplicate", status_code=303)
    return RedirectResponse("/users", status_code=303)


@router.post("/users/{user_id}/toggle")
def users_toggle(
    user_id: int,
    request: Request,
    csrf_token: str = Form(),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.admin)),
) -> RedirectResponse:
    validate_csrf_token(request, csrf_token)
    repo = UserRepository(db)
    user = repo.get(user_id)
    if user is not None and user.id != current_user.id:
        user.is_active = not user.is_active
        db.commit()
        AuditService(db).record(
            "toggle",
            "user",
            str(user.id),
            current_user,
            request.client.host if request.client else None,
            {"is_active": user.is_active},
        )
    return RedirectResponse("/users", status_code=303)
