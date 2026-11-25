"""Event CRUD, participant registration, attendance tracking, and event roster routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.core.responses import ok
from app.core.security import ActorContext, require_admin
from app.database.session import get_db
from app.schemas.participant import (
    AttendanceRead,
    AttendanceUpsert,
    EventCreate,
    EventRead,
    EventUpdate,
    RegistrationCreate,
    RegistrationRead,
)
from app.services.participant_service import EventService

router = APIRouter(prefix="/events", tags=["Events"])


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Create an event",
    description="Creates a new CCI STEM Connect event record. Restricted to administrators.",
)
def create_event(
    payload: EventCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin),
):
    event = EventService(db).create_event(payload, actor=actor)
    return ok(
        EventRead.model_validate(event).model_dump(mode="json"),
        request_id=getattr(request.state, "request_id", None),
    )


@router.get(
    "",
    summary="List events",
    description="Returns non-sensitive event metadata for frontend event selection.",
)
def list_events(
    request: Request,
    event_status: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    events, total = EventService(db).list_events(
        status=event_status, limit=limit, offset=offset
    )
    return ok(
        [EventRead.model_validate(e).model_dump(mode="json") for e in events],
        meta={
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": (offset + len(events)) < total,
        },
        request_id=getattr(request.state, "request_id", None),
    )


@router.get(
    "/{event_id}",
    summary="Get event details",
    description="Returns metadata for a single event.",
)
def get_event(
    event_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
):
    event = EventService(db).get_event(event_id)
    return ok(
        EventRead.model_validate(event).model_dump(mode="json"),
        request_id=getattr(request.state, "request_id", None),
    )


@router.patch(
    "/{event_id}",
    summary="Update event details",
    description="Updates an event record. Restricted to administrators.",
)
def update_event(
    event_id: UUID,
    payload: EventUpdate,
    request: Request,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin),
):
    event = EventService(db).update_event(event_id, payload, actor=actor)
    return ok(
        EventRead.model_validate(event).model_dump(mode="json"),
        request_id=getattr(request.state, "request_id", None),
    )


@router.get(
    "/{event_id}/participants",
    summary="List participants registered for an event",
    description="Returns registered participants with attendance status. Restricted to administrators; never publicly exposed.",
)
def list_event_participants(
    event_id: UUID,
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin),
):
    items, total = EventService(db).list_event_participants(
        event_id, limit=limit, offset=offset
    )
    return ok(
        [item.model_dump(mode="json") for item in items],
        meta={
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": (offset + len(items)) < total,
        },
        request_id=getattr(request.state, "request_id", None),
    )


@router.post(
    "/{event_id}/registrations",
    status_code=status.HTTP_201_CREATED,
    summary="Register an existing participant for an event",
    description="Associates a participant uniquely with an event. Restricted to administrators.",
)
def register_participant(
    event_id: UUID,
    payload: RegistrationCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin),
):
    reg = EventService(db).register_participant(event_id, payload, actor=actor)
    return ok(
        RegistrationRead.model_validate(reg).model_dump(mode="json"),
        request_id=getattr(request.state, "request_id", None),
    )


@router.post(
    "/{event_id}/attendance",
    summary="Record or update participant attendance for an event",
    description="Creates or updates an attendance record. Restricted to administrators.",
)
def upsert_attendance(
    event_id: UUID,
    payload: AttendanceUpsert,
    request: Request,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin),
):
    att = EventService(db).upsert_attendance(event_id, payload, actor=actor)
    return ok(
        AttendanceRead.model_validate(att).model_dump(mode="json"),
        request_id=getattr(request.state, "request_id", None),
    )
