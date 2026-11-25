"""Administrator, AuditLog, NotificationRecord, and ReportRecord ORM models."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import AdminRole, ExportFormat
from app.database.base import Base, JSONBType, TimestampMixin, UUIDPrimaryKeyMixin, utc_now


class AdministratorRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Administrative actors authorised via API keys (not participant authentication)."""

    __tablename__ = "administrator_records"

    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    role: Mapped[str] = mapped_column(
        String(40), default=AdminRole.EVENT_ADMIN.value, nullable=False
    )
    api_key_hash: Mapped[str | None] = mapped_column(
        String(128), unique=True, nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_active_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class AuditLog(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_created_at", "created_at"),
        Index("ix_audit_logs_resource", "resource_type", "resource_id"),
    )

    actor_id: Mapped[str] = mapped_column(String(120), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(40), nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(80), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    details_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSONBType, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class NotificationRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "notification_records"
    __table_args__ = (
        Index("ix_notification_records_participant_id", "participant_id"),
        Index("ix_notification_records_event_id", "event_id"),
    )

    participant_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("participants.id", ondelete="SET NULL"),
        nullable=True,
    )
    event_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("events.id", ondelete="SET NULL"), nullable=True
    )
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    notification_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="queued", nullable=False)
    payload_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSONBType, nullable=True
    )
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class ReportRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "report_records"
    __table_args__ = (
        Index("ix_report_records_event_id", "event_id"),
        Index("ix_report_records_participant_id", "participant_id"),
    )

    report_type: Mapped[str] = mapped_column(String(60), nullable=False)
    event_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("events.id", ondelete="SET NULL"), nullable=True
    )
    participant_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("participants.id", ondelete="SET NULL"),
        nullable=True,
    )
    export_format: Mapped[str] = mapped_column(
        String(16), default=ExportFormat.JSON.value, nullable=False
    )
    generated_by: Mapped[str] = mapped_column(String(120), nullable=False)
    file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    parameters_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSONBType, nullable=True
    )
    summary_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSONBType, nullable=True
    )
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
