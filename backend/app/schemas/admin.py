"""Pydantic schemas for Admin authentication identity, administrator management, and audit logs."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import AdminRole


class AdminIdentityRead(BaseModel):
    actor_id: str
    actor_type: str
    role: str
    is_admin: bool
    full_name: str
    email: str | None = None


class AdminUserCreate(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=200)
    email: str = Field(..., min_length=5, max_length=320)
    role: AdminRole = AdminRole.EVENT_ADMIN


class AdminUserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=200)
    role: AdminRole | None = None
    is_active: bool | None = None


class AdminUserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    full_name: str
    email: str
    role: str
    is_active: bool
    last_active_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class AdminUserCreatedRead(AdminUserRead):
    """Returned once upon creation; the raw api_key cannot be retrieved again."""

    api_key: str


class AuditLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    actor_id: str
    actor_type: str
    action: str
    resource_type: str
    resource_id: str | None = None
    ip_address: str | None = None
    request_id: str | None = None
    details_json: dict[str, Any] | None = None
    created_at: datetime
