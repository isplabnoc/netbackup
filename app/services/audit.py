import json
from typing import Any

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.user import User


class AuditService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def record(
        self,
        action: str,
        entity: str,
        entity_id: str | None = None,
        user: User | None = None,
        ip_address: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AuditLog:
        log = AuditLog(
            user_id=user.id if user else None,
            action=action,
            entity=entity,
            entity_id=entity_id,
            ip_address=ip_address,
            metadata_json=json.dumps(metadata or {}),
        )
        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)
        return log
