from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.device import Vendor


class DeviceBase(BaseModel):
    hostname: str
    ip: str
    vendor: Vendor
    platform: str
    credential_group_id: int
    location: str | None = None
    enabled: bool = True


class DeviceCreate(DeviceBase):
    pass


class DeviceUpdate(BaseModel):
    hostname: str | None = None
    ip: str | None = None
    vendor: Vendor | None = None
    platform: str | None = None
    credential_group_id: int | None = None
    location: str | None = None
    enabled: bool | None = None


class DeviceRead(DeviceBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
