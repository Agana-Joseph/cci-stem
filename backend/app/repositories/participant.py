"""Repositories for Participant, Event, EventRegistration, and AttendanceRecord."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.enums import EventStatus
from app.models.participant import (
    AttendanceRecord,
    Event,
    EventObjective,
    EventPillar,
    EventRegistration,
    Participant,
)


class ParticipantRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, participant_id: UUID) -> Participant | None:
        return self.db.get(Participant, participant_id)

    def get_by_phone(self, phone_normalised: str) -> Participant | None:
        return self.db.execute(
            select(Participant).where(Participant.phone_normalised == phone_normalised)
        ).scalar_one_or_none()

    def get_by_email(self, email_normalised: str) -> Participant | None:
        return self.db.execute(
            select(Participant).where(Participant.email_normalised == email_normalised)
        ).scalar_one_or_none()

    def find_by_contact(
        self,
        *,
        phone_normalised: str | None = None,
        email_normalised: str | None = None,
    ) -> tuple[Participant | None, str | None]:
        """Phone number is the preferred identifier; email is the fallback."""
        if phone_normalised:
            found = self.get_by_phone(phone_normalised)
            if found is not None:
                return found, "phone"
        if email_normalised:
            found = self.get_by_email(email_normalised)
            if found is not None:
                return found, "email"
        return None, None

    def create(self, participant: Participant) -> Participant:
        self.db.add(participant)
        self.db.flush()
        return participant

    def list_registered_event_ids(self, participant_id: UUID) -> list[UUID]:
        rows = self.db.execute(
            select(EventRegistration.event_id).where(
                EventRegistration.participant_id == participant_id
            )
        ).scalars().all()
        return list(rows)


class EventRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, event_id: UUID) -> Event | None:
        return self.db.execute(
            select(Event)
            .options(
                selectinload(Event.objectives),
                selectinload(Event.event_pillars),
            )
            .where(Event.id == event_id)
        ).scalar_one_or_none()

    def get_by_slug(self, slug: str) -> Event | None:
        return self.db.execute(
            select(Event)
            .options(
                selectinload(Event.objectives),
                selectinload(Event.event_pillars),
            )
            .where(Event.slug == slug)
        ).scalar_one_or_none()

    def get_default_event(self) -> Event | None:
        stmt = (
            select(Event)
            .options(
                selectinload(Event.objectives),
                selectinload(Event.event_pillars),
            )
            .where(
                Event.public_visibility.is_(True),
                Event.status.in_(
                    [EventStatus.PUBLISHED.value, EventStatus.ACTIVE.value]
                ),
            )
            .order_by(Event.is_default.desc(), Event.created_at.desc())
        )
        return self.db.execute(stmt).scalars().first()

    def list_events(
        self, *, status: str | None = None, limit: int = 50, offset: int = 0
    ) -> tuple[list[Event], int]:
        stmt = select(Event).options(selectinload(Event.objectives))
        count_stmt = select(func.count(Event.id))
        if status:
            stmt = stmt.where(Event.status == status)
            count_stmt = count_stmt.where(Event.status == status)
        total = self.db.execute(count_stmt).scalar_one()
        items = (
            self.db.execute(
                stmt.order_by(
                    Event.is_default.desc(),
                    Event.event_date.desc(),
                    Event.created_at.desc(),
                )
                .limit(limit)
                .offset(offset)
            )
            .scalars()
            .all()
        )
        return list(items), int(total)

    def create(self, event: Event) -> Event:
        self.db.add(event)
        self.db.flush()
        return event

    def get_registration(
        self, event_id: UUID, participant_id: UUID
    ) -> EventRegistration | None:
        return self.db.execute(
            select(EventRegistration).where(
                EventRegistration.event_id == event_id,
                EventRegistration.participant_id == participant_id,
            )
        ).scalar_one_or_none()

    def get_attendance(
        self, event_id: UUID, participant_id: UUID
    ) -> AttendanceRecord | None:
        return self.db.execute(
            select(AttendanceRecord).where(
                AttendanceRecord.event_id == event_id,
                AttendanceRecord.participant_id == participant_id,
            )
        ).scalar_one_or_none()

    def list_event_participants(
        self, event_id: UUID, *, limit: int = 100, offset: int = 0
    ) -> tuple[list[tuple[Participant, EventRegistration, AttendanceRecord | None]], int]:
        total = self.db.execute(
            select(func.count(EventRegistration.id)).where(
                EventRegistration.event_id == event_id
            )
        ).scalar_one()
        stmt = (
            select(Participant, EventRegistration, AttendanceRecord)
            .join(
                EventRegistration,
                EventRegistration.participant_id == Participant.id,
            )
            .outerjoin(
                AttendanceRecord,
                (AttendanceRecord.participant_id == Participant.id)
                & (AttendanceRecord.event_id == event_id),
            )
            .where(EventRegistration.event_id == event_id)
            .order_by(EventRegistration.registered_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = self.db.execute(stmt).all()
        return [(r[0], r[1], r[2]) for r in rows], int(total)
