"""Administrative API key guard, actor context, and future OTP verification interface.

Important: Participants do NOT authenticate with passwords or accounts.
Administrative endpoints require a valid `X-API-Key` header so participant PII,
lists, imports, scoring management, and exports are never publicly exposed.
"""

import hashlib
import hmac
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from fastapi import Depends, Header, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.enums import AdminRole
from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.database.session import get_db
from app.models.admin import AdministratorRecord


def hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ActorContext:
    actor_id: str
    actor_type: str  # "admin" | "public_client" | "system"
    role: str | None
    is_admin: bool
    ip_address: str | None
    request_id: str | None


def _extract_ip(request: Request) -> str | None:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


def resolve_optional_admin(
    request: Request,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    x_actor_id: str | None = Header(default=None, alias="X-Actor-Id"),
    db: Session = Depends(get_db),
) -> ActorContext:
    """Resolve caller identity without rejecting public requests."""
    settings = get_settings()
    ip_address = _extract_ip(request)
    request_id = getattr(request.state, "request_id", None)

    if not x_api_key:
        return ActorContext(
            actor_id=x_actor_id or "anonymous",
            actor_type="public_client",
            role=None,
            is_admin=False,
            ip_address=ip_address,
            request_id=request_id,
        )

    # 1. Check bootstrap environment admin key (constant-time comparison)
    if settings.admin_api_key and hmac.compare_digest(x_api_key, settings.admin_api_key):
        return ActorContext(
            actor_id=x_actor_id or "bootstrap-admin",
            actor_type="admin",
            role=AdminRole.SUPER_ADMIN.value,
            is_admin=True,
            ip_address=ip_address,
            request_id=request_id,
        )

    # 2. Check persisted administrator_records table
    key_hash = hash_api_key(x_api_key)
    admin = db.execute(
        select(AdministratorRecord).where(
            AdministratorRecord.api_key_hash == key_hash,
            AdministratorRecord.is_active.is_(True),
        )
    ).scalar_one_or_none()
    if admin is not None:
        admin.last_active_at = datetime.now(timezone.utc)
        db.flush()
        return ActorContext(
            actor_id=str(admin.id),
            actor_type="admin",
            role=admin.role,
            is_admin=True,
            ip_address=ip_address,
            request_id=request_id,
        )

    raise UnauthorizedError("Invalid administrative API key.")


def require_admin(
    actor: ActorContext = Depends(resolve_optional_admin),
) -> ActorContext:
    """Guard dependency ensuring the caller is an authenticated administrator."""
    if not actor.is_admin:
        raise UnauthorizedError(
            "This endpoint is restricted to authorised administrators."
        )
    return actor


def require_admin_roles(*allowed_roles: AdminRole):
    """Role-scoped admin dependency for fine-grained permissions."""
    allowed_values = {r.value for r in allowed_roles}

    def _checker(actor: ActorContext = Depends(require_admin)) -> ActorContext:
        if actor.role not in allowed_values:
            raise ForbiddenError(
                f"Role '{actor.role}' is not permitted for this operation."
            )
        return actor

    return _checker


class VerificationProvider(ABC):
    """Future-proof extension contract for Email OTP, SMS OTP, or WhatsApp verification.

    v1 does not require participant authentication; this interface allows v2
    verification flows to plug into the participant lookup & assessment pipeline
    without changing core domain services.
    """

    @abstractmethod
    def initiate_challenge(
        self, channel: str, destination: str, participant_id: UUID | None = None
    ) -> dict[str, str]:
        raise NotImplementedError

    @abstractmethod
    def verify_challenge(self, challenge_id: str, code: str) -> bool:
        raise NotImplementedError


class DeferredVerificationProvider(VerificationProvider):
    """Default v1 placeholder provider returning generic non-enumerating responses."""

    def initiate_challenge(
        self, channel: str, destination: str, participant_id: UUID | None = None
    ) -> dict[str, str]:
        return {
            "channel": channel,
            "status": "verification_required",
            "message": (
                "If a matching registration exists, please proceed through the "
                "configured verification channel."
            ),
        }

    def verify_challenge(self, challenge_id: str, code: str) -> bool:
        return False
