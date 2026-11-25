"""Services for administrator identity verification, admin user management, and audit log queries."""

import secrets
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError
from app.core.normalisation import normalise_email
from app.core.security import ActorContext, hash_api_key
from app.models.admin import AdministratorRecord, AuditLog
from app.schemas.admin import (
    AdminIdentityRead,
    AdminUserCreate,
    AdminUserUpdate,
)
from app.services.audit_service import record_audit


class AdminService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_current_admin(self, actor: ActorContext) -> AdminIdentityRead:
        full_name = "Bootstrap Administrator"
        email: str | None = None
        try:
            admin_uuid = UUID(actor.actor_id)
        except (ValueError, TypeError):
            admin_uuid = None

        if admin_uuid is not None:
            record = self.db.get(AdministratorRecord, admin_uuid)
            if record is not None:
                full_name = record.full_name
                email = record.email

        return AdminIdentityRead(
            actor_id=actor.actor_id,
            actor_type=actor.actor_type,
            role=actor.role or "super_admin",
            is_admin=actor.is_admin,
            full_name=full_name,
            email=email,
        )

    def list_admins(self) -> list[AdministratorRecord]:
        return list(
            self.db.execute(
                select(AdministratorRecord).order_by(AdministratorRecord.created_at.desc())
            )
            .scalars()
            .all()
        )

    def create_admin(
        self, payload: AdminUserCreate, *, actor: ActorContext
    ) -> tuple[AdministratorRecord, str]:
        email_norm = normalise_email(payload.email)
        assert email_norm is not None

        existing = self.db.execute(
            select(AdministratorRecord).where(AdministratorRecord.email == email_norm)
        ).scalar_one_or_none()
        if existing is not None:
            raise ConflictError(
                f"An administrator with email '{email_norm}' already exists.",
                details={"field": "email"},
            )

        raw_key = f"cci_{secrets.token_urlsafe(32)}"
        admin = AdministratorRecord(
            full_name=payload.full_name.strip(),
            email=email_norm,
            role=payload.role.value,
            api_key_hash=hash_api_key(raw_key),
            is_active=True,
        )
        self.db.add(admin)
        self.db.flush()
        record_audit(
            self.db,
            actor=actor,
            action="admin_user.create",
            resource_type="administrator_record",
            resource_id=str(admin.id),
            details={"email": admin.email, "role": admin.role},
        )
        self.db.commit()
        self.db.refresh(admin)
        return admin, raw_key

    def update_admin(
        self, admin_id: UUID, payload: AdminUserUpdate, *, actor: ActorContext
    ) -> AdministratorRecord:
        admin = self.db.get(AdministratorRecord, admin_id)
        if admin is None:
            raise NotFoundError("AdministratorRecord", admin_id)

        updates = payload.model_dump(exclude_unset=True)
        for field, value in updates.items():
            if field == "full_name" and isinstance(value, str):
                value = value.strip()
            setattr(admin, field, value.value if hasattr(value, "value") else value)

        record_audit(
            self.db,
            actor=actor,
            action="admin_user.update",
            resource_type="administrator_record",
            resource_id=str(admin.id),
            details={"updated_fields": sorted(updates.keys())},
        )
        self.db.commit()
        self.db.refresh(admin)
        return admin

    def list_audit_logs(
        self,
        *,
        action: str | None = None,
        resource_type: str | None = None,
        actor_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[AuditLog], int]:
        stmt = select(AuditLog)
        count_stmt = select(func.count(AuditLog.id))
        if action:
            stmt = stmt.where(AuditLog.action == action)
            count_stmt = count_stmt.where(AuditLog.action == action)
        if resource_type:
            stmt = stmt.where(AuditLog.resource_type == resource_type)
            count_stmt = count_stmt.where(AuditLog.resource_type == resource_type)
        if actor_id:
            stmt = stmt.where(AuditLog.actor_id == actor_id)
            count_stmt = count_stmt.where(AuditLog.actor_id == actor_id)

        total = int(self.db.execute(count_stmt).scalar_one())
        items = list(
            self.db.execute(
                stmt.order_by(AuditLog.created_at.desc()).limit(limit).offset(offset)
            )
            .scalars()
            .all()
        )
        return items, total
