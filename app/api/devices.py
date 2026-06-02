from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import require_role
from app.core.rbac import Role
from app.database.session import get_db
from app.repositories.device import DeviceRepository
from app.schemas.device import DeviceCreate, DeviceRead, DeviceUpdate
from app.services.audit import AuditService

router = APIRouter(prefix="/api/devices", tags=["devices"])


@router.get("", response_model=list[DeviceRead])
def list_devices(db: Session = Depends(get_db)) -> list[DeviceRead]:
    return [DeviceRead.model_validate(device) for device in DeviceRepository(db).list(limit=1000)]


@router.post("", response_model=DeviceRead, status_code=status.HTTP_201_CREATED)
def create_device(
    payload: DeviceCreate,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(require_role(Role.operator)),
) -> DeviceRead:
    device = DeviceRepository(db).create(payload.model_dump(mode="json"))
    AuditService(db).record("create", "device", str(device.id), user, request.client.host if request.client else None)
    return DeviceRead.model_validate(device)


@router.put("/{device_id}", response_model=DeviceRead)
def update_device(
    device_id: int,
    payload: DeviceUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(require_role(Role.operator)),
) -> DeviceRead:
    repo = DeviceRepository(db)
    device = repo.get(device_id)
    if device is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    device = repo.update(device, payload.model_dump(exclude_unset=True, mode="json"))
    AuditService(db).record("update", "device", str(device.id), user, request.client.host if request.client else None)
    return DeviceRead.model_validate(device)


@router.delete("/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_device(
    device_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(require_role(Role.admin)),
) -> None:
    repo = DeviceRepository(db)
    device = repo.get(device_id)
    if device is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    repo.delete(device)
    AuditService(db).record("delete", "device", str(device_id), user, request.client.host if request.client else None)
