"""Participant, Event, EventRegistration, and AttendanceRecord ORM models."""

from datetime import date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import AttendanceStatus, EventStatus, RegistrationSource, RegistrationStatus
from app.database.base import Base, JSONBType, TimestampMixin, UUIDPrimaryKeyMixin, utc_now


class Participant(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Participant profile identified by normalised phone number and/or email.

    No password or conventional authentication credentials are stored here.
    """

    __tablename__ = "participants"
    __table_args__ = (
        CheckConstraint(
            "email_normalised IS NOT NULL OR phone_normalised IS NOT NULL",
            name="participant_requires_contact",
        ),
        Index("ix_participants_phone_normalised", "phone_normalised"),
        Index("ix_participants_email_normalised", "email_normalised"),
    )

    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    email_raw: Mapped[str | None] = mapped_column(String(320), nullable=True)
    email_normalised: Mapped[str | None] = mapped_column(
        String(320), nullable=True, unique=True
    )
    phone_raw: Mapped[str | None] = mapped_column(String(64), nullable=True)
    phone_normalised: Mapped[str | None] = mapped_column(
        String(32), nullable=True, unique=True
    )

    # Professional Background (Section A)
    current_role: Mapped[str | None] = mapped_column(String(160), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(160), nullable=True)
    organisation: Mapped[str | None] = mapped_column(String(200), nullable=True)
    years_of_experience: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reason_for_attending: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Privacy, consent & data minimisation
    data_source: Mapped[str] = mapped_column(String(64), default="manual", nullable=False)
    consent_given: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    consent_recorded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    retention_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    anonymised_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSONBType, nullable=True
    )

    registrations: Mapped[list["EventRegistration"]] = relationship(
        back_populates="participant", cascade="all, delete-orphan"
    )
    attendance_records: Mapped[list["AttendanceRecord"]] = relationship(
        back_populates="participant", cascade="all, delete-orphan"
    )


class Event(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "events"

    slug: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    event_type: Mapped[str] = mapped_column(
        String(80), default="networking_and_knowledge_sharing", nullable=False
    )
    event_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    location: Mapped[str | None] = mapped_column(String(240), nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), default=EventStatus.ACTIVE.value, nullable=False
    )
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSONBType, nullable=True
    )

    registrations: Mapped[list["EventRegistration"]] = relationship(
        back_populates="event", cascade="all, delete-orphan"
    )
    attendance_records: Mapped[list["AttendanceRecord"]] = relationship(
        back_populates="event", cascade="all, delete-orphan"
    )


class EventRegistration(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Links a participant uniquely to a specific event while permitting repeat attendance across events."""

    __tablename__ = "event_registrations"
    __table_args__ = (
        UniqueConstraint("event_id", "participant_id", name="uq_event_participant_reg"),
        Index("ix_event_registrations_event_id", "event_id"),
        Index("ix_event_registrations_participant_id", "participant_id"),
    )

    event_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"), nullable=False
    )
    participant_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("participants.id", ondelete="CASCADE"),
        nullable=False,
    )
    registration_source: Mapped[str] = mapped_column(
        String(40), default=RegistrationSource.FORM.value, nullable=False
    )
    registration_status: Mapped[str] = mapped_column(
        String(40), default=RegistrationStatus.REGISTERED.value, nullable=False
    )
    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    reason_for_attending: Mapped[str | None] = mapped_column(Text, nullable=True)

    event: Mapped["Event"] = relationship(back_populates="registrations")
    participant: Mapped["Participant"] = relationship(back_populates="registrations")


class AttendanceRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "attendance_records"
    __table_args__ = (
        UniqueConstraint("event_id", "participant_id", name="uq_event_participant_att"),
        Index("ix_attendance_records_event_id", "event_id"),
        Index("ix_attendance_records_participant_id", "participant_id"),
    )

    event_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"), nullable=False
    )
    participant_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("participants.id", ondelete="CASCADE"),
        nullable=False,
    )
    attendance_status: Mapped[str] = mapped_column(
        String(32), default=AttendanceStatus.CONFIRMED.value, nullable=False
    )
    check_in_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    check_out_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    verification_source: Mapped[str | None] = mapped_column(String(80), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    event: Mapped["Event"] = relationship(back_populates="attendance_records")
    participant: Mapped["Participant"] = relationship(back_populates="attendance_records")
