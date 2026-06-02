from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DiffRead(BaseModel):
    id: int
    device_id: int
    backup_id: int
    previous_backup_id: int | None
    added_lines: int
    removed_lines: int
    html: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
