from datetime import datetime

from pydantic import BaseModel, ConfigDict


class BackupRead(BaseModel):
    id: int
    device_id: int
    job_id: int | None
    status: str
    file_path: str | None
    error_message: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BackupRunRequest(BaseModel):
    device_ids: list[int] | None = None


class BackupJobRead(BaseModel):
    id: int
    status: str
    total: int
    success: int
    failed: int
    triggered_by: str | None
    created_at: datetime
    finished_at: datetime | None

    model_config = ConfigDict(from_attributes=True)
