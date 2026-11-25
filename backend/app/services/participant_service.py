"""Business services for Participants, Identification, Events, Registrations, Attendance & Imports."""

from datetime import datetime, timezone
from io import BytesIO
from typing import Any
from uuid import UUID

import pandas as pd
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.enums import AttendanceStatus, RegistrationSource, RegistrationStatus
from app.core.exceptions import ConflictError, NotFoundError, ValidationAppError
from app.core.normalisation import normalise_email, normalise_phone
from app.core.security import ActorContext, DeferredVerificationProvider
from app.models.participant import (
    AttendanceRecord,
    Event,
    EventRegistration,
    Participant,
)
from app.repositories.participant import EventRepository, ParticipantRepository
from app.schemas.participant import (
    AttendanceUpsert,
    EventCreate,
    EventParticipantSummary,
    EventUpdate,
    ImportRowError,
    ParticipantCreate,
    ParticipantImportReport,
    ParticipantLookupAdminResponse,
    ParticipantLookupPublicResponse,
    ParticipantUpdate,
    RegistrationCreate,
)
from app.services.audit_service import record_audit

_COLUMN_ALIASES = {
    "full_name": ["full_name", "name", "participant_name", "attendee_name"],
    "email": ["email", "email_address", "registered_email"],
    "phone": ["phone", "phone_number", "whatsapp_number", "mobile", "telephone"],
    "current_role": ["current_role", "role", "job_title", "title"],
    "industry": ["industry", "sector"],
    "organisation": ["organisation", "organization", "company", "employer"],
    "years_of_experience": ["years_of_experience", "experience_years", "yoe"],
    "reason_for_attending": ["reason_for_attending", "reason", "attendance_reason"],
    "attendance_status": ["attendance_status", "attended", "attendance"],
    "consent_given": ["consent_given", "consent"],
}


def _clean_cell(value: Any) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null"}:
        return None
    return text


def _parse_bool(value: Any, default: bool = False) -> bool:
    cleaned = _clean_cell(value)
    if cleaned is None:
        return default
    return cleaned.lower() in {"true", "1", "yes", "y", "confirmed", "present"}


class ParticipantService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = ParticipantRepository(db)
        self.event_repo = EventRepository(db)
        self.verification_provider = DeferredVerificationProvider()

    def create_participant(
        self, payload: ParticipantCreate, *, actor: ActorContext
    ) -> Participant:
        email_norm = normalise_email(payload.email)
        phone_norm = normalise_phone(payload.phone)

        if not email_norm and not phone_norm:
            raise ValidationAppError(
                "At least one valid email or phone number must be supplied."
            )

        if phone_norm and self.repo.get_by_phone(phone_norm) is not None:
            raise ConflictError(
                "A participant with this phone number already exists.",
                details={"field": "phone"},
            )
        if email_norm and self.repo.get_by_email(email_norm) is not None:
            raise ConflictError(
                "A participant with this email address already exists.",
                details={"field": "email"},
            )

        now = datetime.now(timezone.utc)
        participant = Participant(
            full_name=payload.full_name.strip(),
            email_raw=payload.email.strip() if payload.email else None,
            email_normalised=email_norm,
            phone_raw=payload.phone.strip() if payload.phone else None,
            phone_normalised=phone_norm,
            current_role=payload.current_role,
            industry=payload.industry,
            organisation=payload.organisation,
            years_of_experience=payload.years_of_experience,
            reason_for_attending=payload.reason_for_attending,
            data_source=payload.data_source,
            consent_given=payload.consent_given,
            consent_recorded_at=now if payload.consent_given else None,
            metadata_json=payload.metadata_json,
        )
        self.repo.create(participant)

        if payload.event_id is not None:
            event = self.event_repo.get_by_id(payload.event_id)
            if event is None:
                raise NotFoundError("Event", payload.event_id)
            reg = EventRegistration(
                event_id=event.id,
                participant_id=participant.id,
                registration_source=payload.registration_source.value,
                registration_status=RegistrationStatus.REGISTERED.value,
                reason_for_attending=payload.reason_for_attending,
            )
            self.db.add(reg)

        record_audit(
            self.db,
            actor=actor,
            action="participant.create",
            resource_type="participant",
            resource_id=str(participant.id),
            details={"event_id": str(payload.event_id) if payload.event_id else None},
        )
        self.db.commit()
        self.db.refresh(participant)
        return participant

    def get_participant(self, participant_id: UUID) -> Participant:
        participant = self.repo.get_by_id(participant_id)
        if participant is None:
            raise NotFoundError("Participant", participant_id)
        return participant

    def update_participant(
        self, participant_id: UUID, payload: ParticipantUpdate, *, actor: ActorContext
    ) -> Participant:
        participant = self.get_participant(participant_id)
        updates = payload.model_dump(exclude_unset=True)

        if "email" in updates:
            raw_email = updates.pop("email")
            email_norm = normalise_email(raw_email)
            if email_norm:
                existing = self.repo.get_by_email(email_norm)
                if existing and existing.id != participant.id:
                    raise ConflictError(
                        "Another participant already uses this email address.",
                        details={"field": "email"},
                    )
            participant.email_raw = raw_email.strip() if raw_email else None
            participant.email_normalised = email_norm

        if "phone" in updates:
            raw_phone = updates.pop("phone")
            phone_norm = normalise_phone(raw_phone)
            if phone_norm:
                existing = self.repo.get_by_phone(phone_norm)
                if existing and existing.id != participant.id:
                    raise ConflictError(
                        "Another participant already uses this phone number.",
                        details={"field": "phone"},
                    )
            participant.phone_raw = raw_phone.strip() if raw_phone else None
            participant.phone_normalised = phone_norm

        if not participant.email_normalised and not participant.phone_normalised:
            raise ValidationAppError(
                "Participant must retain at least one valid contact identifier."
            )

        if updates.get("consent_given") is True and not participant.consent_recorded_at:
            participant.consent_recorded_at = datetime.now(timezone.utc)

        for field, value in updates.items():
            setattr(participant, field, value)

        record_audit(
            self.db,
            actor=actor,
            action="participant.update",
            resource_type="participant",
            resource_id=str(participant.id),
            details={"updated_fields": sorted(payload.model_dump(exclude_unset=True).keys())},
        )
        self.db.commit()
        self.db.refresh(participant)
        return participant

    def lookup_participant(
        self,
        *,
        phone: str | None = None,
        email: str | None = None,
        event_id: UUID | None = None,
        actor: ActorContext,
    ) -> ParticipantLookupPublicResponse | ParticipantLookupAdminResponse:
        """Identify a participant by phone (preferred) or email.

        Security guarantee:
        - Public / unauthenticated callers ALWAYS receive a generic, non-enumerating
          verification-required response regardless of whether the contact exists.
        - Trusted administrative callers receive the minimal matched record and the
          lookup is recorded in `audit_logs`.
        """
        if not phone and not email:
            raise ValidationAppError(
                "Provide either a phone number or an email address for lookup."
            )

        phone_norm = normalise_phone(phone) if phone else None
        email_norm = normalise_email(email) if email else None
        channel = "phone" if phone_norm else "email"

        # Non-admin callers never get existence oracle responses
        if not actor.is_admin:
            challenge = self.verification_provider.initiate_challenge(
                channel=channel,
                destination=phone_norm or email_norm or "",
            )
            return ParticipantLookupPublicResponse(
                status=challenge["status"],
                verification_channel=channel,
                message=challenge["message"],
            )

        participant, match_channel = self.repo.find_by_contact(
            phone_normalised=phone_norm, email_normalised=email_norm
        )

        record_audit(
            self.db,
            actor=actor,
            action="participant.lookup",
            resource_type="participant",
            resource_id=str(participant.id) if participant else None,
            details={
                "lookup_channel": channel,
                "matched": participant is not None,
                "event_id": str(event_id) if event_id else None,
            },
        )
        self.db.commit()

        if participant is None:
            return ParticipantLookupAdminResponse(
                matched=False,
                message="No matching participant record was found for the supplied identifier.",
            )

        event_ids = self.repo.list_registered_event_ids(participant.id)
        if event_id is not None and event_id not in event_ids:
            return ParticipantLookupAdminResponse(
                matched=False,
                message="No matching participant registration was found for the specified event.",
            )

        return ParticipantLookupAdminResponse(
            matched=True,
            match_channel=match_channel,
            participant_id=participant.id,
            full_name=participant.full_name,
            registered_event_ids=event_ids,
            message="Participant record matched successfully.",
        )

    def import_participants(
        self,
        *,
        file_bytes: bytes,
        filename: str,
        event_id: UUID | None = None,
        data_source: str = "import",
        dry_run: bool = True,
        actor: ActorContext,
    ) -> ParticipantImportReport:
        """Validate and optionally commit CSV or Excel (.xlsx/.xls) participant imports."""
        settings = get_settings()
        if len(file_bytes) > settings.max_import_file_bytes:
            raise ValidationAppError(
                f"Import file exceeds maximum allowed size of {settings.max_import_file_size_mb} MB."
            )

        lower_name = filename.lower()
        try:
            if lower_name.endswith(".csv"):
                df = pd.read_csv(BytesIO(file_bytes), dtype=str)
            elif lower_name.endswith((".xlsx", ".xls")):
                df = pd.read_excel(BytesIO(file_bytes), dtype=str)
            else:
                raise ValidationAppError(
                    "Unsupported file format. Only .csv and .xlsx/.xls files are supported."
                )
        except ValidationAppError:
            raise
        except Exception as exc:
            raise ValidationAppError(
                "Could not parse import file. Ensure it is a valid CSV or Excel workbook.",
                details={"reason": str(exc)},
            ) from exc

        if event_id is not None and self.event_repo.get_by_id(event_id) is None:
            raise NotFoundError("Event", event_id)

        # Normalise column headers via alias mapping
        col_map: dict[str, str] = {}
        raw_cols_lower = {str(c).strip().lower().replace(" ", "_"): c for c in df.columns}
        for canonical, aliases in _COLUMN_ALIASES.items():
            for alias in aliases:
                if alias in raw_cols_lower:
                    col_map[canonical] = raw_cols_lower[alias]
                    break

        errors: list[ImportRowError] = []
        preview_records: list[dict[str, Any]] = []
        seen_phones: set[str] = set()
        seen_emails: set[str] = set()

        valid_rows = 0
        created_count = 0
        updated_count = 0
        duplicate_count = 0

        for idx, row in df.iterrows():
            row_num = int(idx) + 2  # 1-indexed + header row
            raw_dict = {
                k: _clean_cell(row[col_map[k]]) for k in col_map if col_map[k] in row
            }

            full_name = raw_dict.get("full_name")
            email_raw = raw_dict.get("email")
            phone_raw = raw_dict.get("phone")

            if not full_name:
                errors.append(
                    ImportRowError(
                        row_number=row_num,
                        field="full_name",
                        reason="Incomplete record: missing full_name.",
                        raw_values=raw_dict,
                    )
                )
                continue

            if not email_raw and not phone_raw:
                errors.append(
                    ImportRowError(
                        row_number=row_num,
                        field="phone/email",
                        reason="Incomplete record: at least one of phone or email is required.",
                        raw_values=raw_dict,
                    )
                )
                continue

            email_norm = None
            phone_norm = None
            row_invalid = False

            if email_raw:
                try:
                    email_norm = normalise_email(email_raw)
                except ValidationAppError as exc:
                    errors.append(
                        ImportRowError(
                            row_number=row_num,
                            field="email",
                            reason=exc.message,
                            raw_values=raw_dict,
                        )
                    )
                    row_invalid = True

            if phone_raw:
                try:
                    phone_norm = normalise_phone(phone_raw)
                except ValidationAppError as exc:
                    errors.append(
                        ImportRowError(
                            row_number=row_num,
                            field="phone",
                            reason=exc.message,
                            raw_values=raw_dict,
                        )
                    )
                    row_invalid = True

            if row_invalid:
                continue

            # Detect duplicates within the uploaded batch
            if (phone_norm and phone_norm in seen_phones) or (
                email_norm and email_norm in seen_emails
            ):
                duplicate_count += 1
                errors.append(
                    ImportRowError(
                        row_number=row_num,
                        field="phone" if phone_norm in seen_phones else "email",
                        reason="Duplicate contact identifier detected within the import file.",
                        raw_values=raw_dict,
                    )
                )
                continue

            if phone_norm:
                seen_phones.add(phone_norm)
            if email_norm:
                seen_emails.add(email_norm)

            yoe_val: int | None = None
            if raw_dict.get("years_of_experience"):
                try:
                    yoe_val = int(float(raw_dict["years_of_experience"]))
                except ValueError:
                    errors.append(
                        ImportRowError(
                            row_number=row_num,
                            field="years_of_experience",
                            reason="years_of_experience must be an integer.",
                            raw_values=raw_dict,
                        )
                    )
                    continue

            existing, _ = self.repo.find_by_contact(
                phone_normalised=phone_norm, email_normalised=email_norm
            )
            valid_rows += 1

            record_preview = {
                "row_number": row_num,
                "full_name": full_name,
                "phone_normalised": phone_norm,
                "email_normalised": email_norm,
                "action": "update_or_register" if existing else "create",
            }
            if len(preview_records) < 50:
                preview_records.append(record_preview)

            if not dry_run:
                if existing is None:
                    participant = Participant(
                        full_name=full_name,
                        email_raw=email_raw,
                        email_normalised=email_norm,
                        phone_raw=phone_raw,
                        phone_normalised=phone_norm,
                        current_role=raw_dict.get("current_role"),
                        industry=raw_dict.get("industry"),
                        organisation=raw_dict.get("organisation"),
                        years_of_experience=yoe_val,
                        reason_for_attending=raw_dict.get("reason_for_attending"),
                        data_source=data_source,
                        consent_given=_parse_bool(raw_dict.get("consent_given"), False),
                        consent_recorded_at=datetime.now(timezone.utc)
                        if _parse_bool(raw_dict.get("consent_given"), False)
                        else None,
                    )
                    self.repo.create(participant)
                    created_count += 1
                else:
                    participant = existing
                    # Enrich missing contact or profile fields without clobbering existing data
                    if not participant.email_normalised and email_norm:
                        if self.repo.get_by_email(email_norm) is None:
                            participant.email_raw = email_raw
                            participant.email_normalised = email_norm
                    if not participant.phone_normalised and phone_norm:
                        if self.repo.get_by_phone(phone_norm) is None:
                            participant.phone_raw = phone_raw
                            participant.phone_normalised = phone_norm
                    for attr in ("current_role", "industry", "organisation"):
                        if not getattr(participant, attr) and raw_dict.get(attr):
                            setattr(participant, attr, raw_dict[attr])
                    updated_count += 1

                if event_id is not None:
                    reg = self.event_repo.get_registration(event_id, participant.id)
                    if reg is None:
                        self.db.add(
                            EventRegistration(
                                event_id=event_id,
                                participant_id=participant.id,
                                registration_source=data_source
                                if data_source in {s.value for s in RegistrationSource}
                                else RegistrationSource.IMPORT.value,
                                registration_status=RegistrationStatus.REGISTERED.value,
                                reason_for_attending=raw_dict.get("reason_for_attending"),
                            )
                        )
                    if raw_dict.get("attendance_status"):
                        att_status = (
                            AttendanceStatus.CONFIRMED.value
                            if _parse_bool(raw_dict.get("attendance_status"), False)
                            else AttendanceStatus.UNVERIFIED.value
                        )
                        att = self.event_repo.get_attendance(event_id, participant.id)
                        if att is None:
                            self.db.add(
                                AttendanceRecord(
                                    event_id=event_id,
                                    participant_id=participant.id,
                                    attendance_status=att_status,
                                    verification_source=data_source,
                                )
                            )
                        else:
                            att.attendance_status = att_status

        record_audit(
            self.db,
            actor=actor,
            action="participant.import_preview" if dry_run else "participant.import_commit",
            resource_type="participant_import",
            resource_id=str(event_id) if event_id else None,
            details={
                "filename": filename,
                "dry_run": dry_run,
                "total_rows": len(df),
                "valid_rows": valid_rows,
                "created_count": created_count,
                "updated_count": updated_count,
                "duplicate_count": duplicate_count,
                "error_count": len(errors),
            },
        )
        if not dry_run:
            self.db.commit()
        else:
            self.db.commit()  # persist audit record of the preview review

        return ParticipantImportReport(
            dry_run=dry_run,
            filename=filename,
            total_rows=len(df),
            valid_rows=valid_rows,
            created_count=created_count,
            updated_count=updated_count,
            duplicate_count=duplicate_count,
            error_count=len(errors),
            errors=errors,
            preview_records=preview_records,
        )


class EventService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = EventRepository(db)
        self.participant_repo = ParticipantRepository(db)

    def create_event(self, payload: EventCreate, *, actor: ActorContext) -> Event:
        if self.repo.get_by_slug(payload.slug) is not None:
            raise ConflictError(
                f"Event with slug '{payload.slug}' already exists.",
                details={"field": "slug"},
            )
        event = Event(**payload.model_dump())
        self.repo.create(event)
        record_audit(
            self.db,
            actor=actor,
            action="event.create",
            resource_type="event",
            resource_id=str(event.id),
            details={"slug": event.slug},
        )
        self.db.commit()
        self.db.refresh(event)
        return event

    def get_event(self, event_id: UUID) -> Event:
        event = self.repo.get_by_id(event_id)
        if event is None:
            raise NotFoundError("Event", event_id)
        return event

    def list_events(
        self, *, status: str | None = None, limit: int = 50, offset: int = 0
    ) -> tuple[list[Event], int]:
        return self.repo.list_events(status=status, limit=limit, offset=offset)

    def update_event(
        self, event_id: UUID, payload: EventUpdate, *, actor: ActorContext
    ) -> Event:
        event = self.get_event(event_id)
        updates = payload.model_dump(exclude_unset=True)
        for field, value in updates.items():
            setattr(event, field, value.value if hasattr(value, "value") else value)
        record_audit(
            self.db,
            actor=actor,
            action="event.update",
            resource_type="event",
            resource_id=str(event.id),
            details={"updated_fields": sorted(updates.keys())},
        )
        self.db.commit()
        self.db.refresh(event)
        return event

    def register_participant(
        self, event_id: UUID, payload: RegistrationCreate, *, actor: ActorContext
    ) -> EventRegistration:
        event = self.get_event(event_id)
        participant = self.participant_repo.get_by_id(payload.participant_id)
        if participant is None:
            raise NotFoundError("Participant", payload.participant_id)

        existing = self.repo.get_registration(event.id, participant.id)
        if existing is not None:
            raise ConflictError(
                "Participant is already registered for this event.",
                details={
                    "event_id": str(event.id),
                    "participant_id": str(participant.id),
                },
            )

        reg = EventRegistration(
            event_id=event.id,
            participant_id=participant.id,
            registration_source=payload.registration_source.value,
            registration_status=payload.registration_status.value,
            reason_for_attending=payload.reason_for_attending,
        )
        self.db.add(reg)
        record_audit(
            self.db,
            actor=actor,
            action="event.register_participant",
            resource_type="event_registration",
            resource_id=str(reg.id),
            details={
                "event_id": str(event.id),
                "participant_id": str(participant.id),
            },
        )
        self.db.commit()
        self.db.refresh(reg)
        return reg

    def upsert_attendance(
        self, event_id: UUID, payload: AttendanceUpsert, *, actor: ActorContext
    ) -> AttendanceRecord:
        event = self.get_event(event_id)
        participant = self.participant_repo.get_by_id(payload.participant_id)
        if participant is None:
            raise NotFoundError("Participant", payload.participant_id)

        att = self.repo.get_attendance(event.id, participant.id)
        if att is None:
            att = AttendanceRecord(
                event_id=event.id,
                participant_id=participant.id,
                attendance_status=payload.attendance_status.value,
                check_in_at=payload.check_in_at,
                check_out_at=payload.check_out_at,
                verification_source=payload.verification_source,
                notes=payload.notes,
            )
            self.db.add(att)
        else:
            att.attendance_status = payload.attendance_status.value
            if payload.check_in_at is not None:
                att.check_in_at = payload.check_in_at
            if payload.check_out_at is not None:
                att.check_out_at = payload.check_out_at
            if payload.verification_source is not None:
                att.verification_source = payload.verification_source
            if payload.notes is not None:
                att.notes = payload.notes

        self.db.flush()
        record_audit(
            self.db,
            actor=actor,
            action="event.record_attendance",
            resource_type="attendance_record",
            resource_id=str(att.id),
            details={
                "event_id": str(event.id),
                "participant_id": str(participant.id),
                "attendance_status": att.attendance_status,
            },
        )
        self.db.commit()
        self.db.refresh(att)
        return att

    def list_event_participants(
        self, event_id: UUID, *, limit: int = 100, offset: int = 0
    ) -> tuple[list[EventParticipantSummary], int]:
        self.get_event(event_id)
        rows, total = self.repo.list_event_participants(
            event_id, limit=limit, offset=offset
        )
        summaries = [
            EventParticipantSummary(
                participant_id=p.id,
                full_name=p.full_name,
                email_normalised=p.email_normalised,
                phone_normalised=p.phone_normalised,
                current_role=p.current_role,
                industry=p.industry,
                organisation=p.organisation,
                registration_status=reg.registration_status,
                registration_source=reg.registration_source,
                attendance_status=att.attendance_status if att else None,
            )
            for p, reg, att in rows
        ]
        return summaries, total
