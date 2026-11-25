"""Administrator identity verification, user management, and audit log routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.core.enums import AdminRole
from app.core.responses import ok
from app.core.security import ActorContext, require_admin, require_admin_roles
from app.database.session import get_db
from app.schemas.admin import (
    AdminUserCreate,
    AdminUserCreatedRead,
    AdminUserRead,
    AdminUserUpdate,
    AuditLogRead,
)
from app.services.admin_service import AdminService

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get(
    "/me",
    summary="Verify admin API key and return current administrator profile",
    description=(
        "Validates the caller's X-API-Key header and returns actor identity and role. "
        "Use from server-side Next.js login/session handlers to verify admin access."
    ),
)
def get_admin_me(
    request: Request,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin),
):
    identity = AdminService(db).get_current_admin(actor)
    return ok(
        identity.model_dump(mode="json"),
        request_id=getattr(request.state, "request_id", None),
    )


@router.get(
    "/users",
    summary="List provisioned administrator accounts",
    description="Lists administrator records without exposing API key hashes. Restricted to super administrators.",
)
def list_admin_users(
    request: Request,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin_roles(AdminRole.SUPER_ADMIN)),
):
    admins = AdminService(db).list_admins()
    return ok(
        [AdminUserRead.model_validate(a).model_dump(mode="json") for a in admins],
        meta={"total": len(admins)},
        request_id=getattr(request.state, "request_id", None),
    )


@router.post(
    "/users",
    status_code=status.HTTP_201_CREATED,
    summary="Provision a new administrator account and API key",
    description=(
        "Creates an administrator record with a generated API key (stored as SHA-256 hash). "
        "The plaintext api_key is returned once in this response. Restricted to super administrators."
    ),
)
def create_admin_user(
    payload: AdminUserCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin_roles(AdminRole.SUPER_ADMIN)),
):
    admin, raw_key = AdminService(db).create_admin(payload, actor=actor)
    data = AdminUserCreatedRead(
        **AdminUserRead.model_validate(admin).model_dump(),
        api_key=raw_key,
    )
    return ok(
        data.model_dump(mode="json"),
        request_id=getattr(request.state, "request_id", None),
    )


@router.patch(
    "/users/{admin_id}",
    summary="Update an administrator account",
    description="Updates administrator name, role, or active status. Restricted to super administrators.",
)
def update_admin_user(
    admin_id: UUID,
    payload: AdminUserUpdate,
    request: Request,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin_roles(AdminRole.SUPER_ADMIN)),
):
    admin = AdminService(db).update_admin(admin_id, payload, actor=actor)
    return ok(
        AdminUserRead.model_validate(admin).model_dump(mode="json"),
        request_id=getattr(request.state, "request_id", None),
    )


@router.get(
    "/audit-logs",
    summary="List recent administrative and submission audit logs",
    description="Returns paginated audit activity records for dashboard activity feeds and compliance reviews. Restricted to administrators.",
)
def list_audit_logs(
    request: Request,
    action: str | None = Query(default=None),
    resource_type: str | None = Query(default=None),
    actor_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin),
):
    items, total = AdminService(db).list_audit_logs(
        action=action,
        resource_type=resource_type,
        actor_id=actor_id,
        limit=limit,
        offset=offset,
    )
    return ok(
        [AuditLogRead.model_validate(item).model_dump(mode="json") for item in items],
        meta={
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": (offset + len(items)) < total,
        },
        request_id=getattr(request.state, "request_id", None),
    )
