"""Audit logging service for all administrative operations and sensitive lookups."""

from typing import Any

from sqlalchemy.orm import Session

from app.core.security import ActorContext
from app.models.admin import AuditLog


def record_audit(
    db: Session,
    *,
    actor: ActorContext,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> AuditLog:
    entry = AuditLog(
        actor_id=actor.actor_id,
        actor_type=actor.actor_type,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        ip_address=actor.ip_address,
        request_id=actor.request_id,
        details_json=details,
    )
    db.add(entry)
    db.flush()
    return entry
