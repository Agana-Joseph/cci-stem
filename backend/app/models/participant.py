"""Participant, Event, EventRegistration, and AttendanceRecord ORM models."""

from datetime import date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
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
    headline: Mapped[str | None] = mapped_column(String(240), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    introduction: Mapped[str | None] = mapped_column(Text, nullable=True)
    event_category: Mapped[str | None] = mapped_column(String(160), nullable=True)
    event_type: Mapped[str] = mapped_column(
        String(80), default="networking_and_knowledge_sharing", nullable=False
    )
    event_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    location: Mapped[str | None] = mapped_column(String(240), nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), default=EventStatus.ACTIVE.value, nullable=False
    )
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    assessment_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    follow_up_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    public_visibility: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    reflection_cards_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    immediate_assessment_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    follow_up_30d_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    follow_up_60d_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    follow_up_90d_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    default_questionnaire_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("questionnaires.id", ondelete="SET NULL", use_alter=True, name="fk_events_default_questionnaire"),
        nullable=True,
    )
    active_framework_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("scoring_frameworks.id", ondelete="SET NULL", use_alter=True, name="fk_events_active_framework"),
        nullable=True,
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
    objectives: Mapped[list["EventObjective"]] = relationship(
        back_populates="event",
        cascade="all, delete-orphan",
        order_by="EventObjective.display_order",
    )
    event_pillars: Mapped[list["EventPillar"]] = relationship(
        back_populates="event",
        cascade="all, delete-orphan",
        order_by="EventPillar.display_order",
    )


class EventObjective(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Structured event objectives displayed on the public portal and reports."""

    __tablename__ = "event_objectives"
    __table_args__ = (
        UniqueConstraint("event_id", "display_order", name="uq_event_objective_order"),
        Index("ix_event_objectives_event_id", "event_id"),
    )

    event_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"), nullable=False
    )
    objective_text: Mapped[str] = mapped_column(Text, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    event: Mapped["Event"] = relationship(back_populates="objectives")


class EventPillar(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Associates configurable measurement pillars with a specific event."""

    __tablename__ = "event_pillars"
    __table_args__ = (
        UniqueConstraint("event_id", "pillar_id", name="uq_event_pillar"),
        Index("ix_event_pillars_event_id", "event_id"),
        Index("ix_event_pillars_pillar_id", "pillar_id"),
    )

    event_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"), nullable=False
    )
    pillar_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("measurement_pillars.id", ondelete="CASCADE"),
        nullable=False,
    )
    weight_override: Mapped[float | None] = mapped_column(Float, nullable=True)
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    event: Mapped["Event"] = relationship(back_populates="event_pillars")


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
