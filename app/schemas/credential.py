from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CredentialCreate(BaseModel):
    name: str
    username: str
    password: str
    enable_secret: str | None = None


class CredentialRead(BaseModel):
    id: int
    name: str
    username: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
