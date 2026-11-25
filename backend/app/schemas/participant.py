"""Pydantic schemas for Participants, Events, Registrations, Attendance, and Imports."""

from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.enums import (
    AttendanceStatus,
    EventStatus,
    RegistrationSource,
    RegistrationStatus,
)


class ParticipantCreate(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=200)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=64)
    current_role: str | None = Field(default=None, max_length=160)
    industry: str | None = Field(default=None, max_length=160)
    organisation: str | None = Field(default=None, max_length=200)
    years_of_experience: int | None = Field(default=None, ge=0, le=80)
    reason_for_attending: str | None = None
    data_source: str = Field(default="manual", max_length=64)
    consent_given: bool = False
    event_id: UUID | None = None
    registration_source: RegistrationSource = RegistrationSource.MANUAL
    metadata_json: dict[str, Any] | None = None

    @model_validator(mode="after")
    def require_at_least_one_contact(self) -> "ParticipantCreate":
        if not (self.email and self.email.strip()) and not (
            self.phone and self.phone.strip()
        ):
            raise ValueError(
                "At least one contact identifier (email or phone) must be provided."
            )
        return self


class ParticipantUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=200)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=64)
    current_role: str | None = Field(default=None, max_length=160)
    industry: str | None = Field(default=None, max_length=160)
    organisation: str | None = Field(default=None, max_length=200)
    years_of_experience: int | None = Field(default=None, ge=0, le=80)
    reason_for_attending: str | None = None
    consent_given: bool | None = None
    retention_until: datetime | None = None
    metadata_json: dict[str, Any] | None = None


class ParticipantRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    full_name: str
    email_raw: str | None = None
    email_normalised: str | None = None
    phone_raw: str | None = None
    phone_normalised: str | None = None
    current_role: str | None = None
    industry: str | None = None
    organisation: str | None = None
    years_of_experience: int | None = None
    reason_for_attending: str | None = None
    data_source: str
    consent_given: bool
    consent_recorded_at: datetime | None = None
    retention_until: datetime | None = None
    created_at: datetime
    updated_at: datetime


class ParticipantLookupPublicResponse(BaseModel):
    """Generic non-enumerating response for unauthenticated public lookup calls."""

    status: str = "verification_required"
    verification_channel: str
    verification_supported_channels: list[str] = Field(
        default_factory=lambda: ["whatsapp_otp", "sms_otp", "email_otp"]
    )
    message: str


class ParticipantLookupAdminResponse(BaseModel):
    matched: bool
    match_channel: str | None = None
    participant_id: UUID | None = None
    full_name: str | None = None
    registered_event_ids: list[UUID] = Field(default_factory=list)
    message: str


class ImportRowError(BaseModel):
    row_number: int
    field: str | None = None
    reason: str
    raw_values: dict[str, Any] = Field(default_factory=dict)


class ParticipantImportReport(BaseModel):
    dry_run: bool
    filename: str
    total_rows: int
    valid_rows: int
    created_count: int
    updated_count: int
    duplicate_count: int
    error_count: int
    errors: list[ImportRowError] = Field(default_factory=list)
    preview_records: list[dict[str, Any]] = Field(default_factory=list)


class EventCreate(BaseModel):
    slug: str = Field(..., min_length=2, max_length=120, pattern=r"^[a-z0-9-]+$")
    title: str = Field(..., min_length=2, max_length=240)
    description: str | None = None
    event_type: str = Field(default="networking_and_knowledge_sharing", max_length=80)
    event_date: date
    end_date: date | None = None
    location: str | None = Field(default=None, max_length=240)
    status: EventStatus = EventStatus.ACTIVE
    metadata_json: dict[str, Any] | None = None


class EventUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=240)
    description: str | None = None
    event_type: str | None = Field(default=None, max_length=80)
    event_date: date | None = None
    end_date: date | None = None
    location: str | None = Field(default=None, max_length=240)
    status: EventStatus | None = None
    metadata_json: dict[str, Any] | None = None


class EventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    slug: str
    title: str
    description: str | None = None
    event_type: str
    event_date: date
    end_date: date | None = None
    location: str | None = None
    status: str
    metadata_json: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime


class RegistrationCreate(BaseModel):
    participant_id: UUID
    registration_source: RegistrationSource = RegistrationSource.FORM
    registration_status: RegistrationStatus = RegistrationStatus.REGISTERED
    reason_for_attending: str | None = None


class RegistrationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    event_id: UUID
    participant_id: UUID
    registration_source: str
    registration_status: str
    registered_at: datetime
    reason_for_attending: str | None = None


class AttendanceUpsert(BaseModel):
    participant_id: UUID
    attendance_status: AttendanceStatus = AttendanceStatus.CONFIRMED
    check_in_at: datetime | None = None
    check_out_at: datetime | None = None
    verification_source: str | None = Field(default=None, max_length=80)
    notes: str | None = None


class AttendanceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    event_id: UUID
    participant_id: UUID
    attendance_status: str
    check_in_at: datetime | None = None
    check_out_at: datetime | None = None
    verification_source: str | None = None
    notes: str | None = None


class EventParticipantSummary(BaseModel):
    participant_id: UUID
    full_name: str
    email_normalised: str | None = None
    phone_normalised: str | None = None
    current_role: str | None = None
    industry: str | None = None
    organisation: str | None = None
    registration_status: str
    registration_source: str
    attendance_status: str | None = None
