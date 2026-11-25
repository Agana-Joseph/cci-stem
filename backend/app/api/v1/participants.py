"""Participant management, privacy-preserving lookup, CSV/Excel import, and impact routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile, status
from sqlalchemy.orm import Session

from app.core.responses import ok
from app.core.security import ActorContext, require_admin, resolve_optional_admin
from app.database.session import get_db
from app.schemas.participant import (
    ParticipantCreate,
    ParticipantRead,
    ParticipantUpdate,
)
from app.services.impact_service import ImpactTrackingService
from app.services.participant_service import ParticipantService

router = APIRouter(prefix="/participants", tags=["Participants"])


@router.get(
    "",
    summary="List participants directory",
    description=(
        "Returns a paginated, searchable, filterable participant directory including "
        "registration, attendance, and assessment status indicators. Restricted to administrators."
    ),
)
def list_participants(
    request: Request,
    q: str | None = Query(default=None, description="Search by name, email, phone, role, or organisation"),
    event_id: UUID | None = Query(default=None, description="Filter to participants registered for an event"),
    industry: str | None = Query(default=None, description="Filter by industry"),
    attendance_status: str | None = Query(default=None, description="Filter by attendance status"),
    has_assessment: bool | None = Query(default=None, description="Filter by whether an assessment was submitted"),
    sort_by: str = Query(default="created_at", pattern=r"^(created_at|full_name|industry|organisation)$"),
    sort_order: str = Query(default="desc", pattern=r"^(asc|desc)$"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin),
):
    items, total = ParticipantService(db).list_participants(
        q=q,
        event_id=event_id,
        industry=industry,
        attendance_status=attendance_status,
        has_assessment=has_assessment,
        sort_by=sort_by,
        sort_order=sort_order,
        limit=limit,
        offset=offset,
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
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Create a participant record",
    description=(
        "Creates a participant record identified by normalised phone number and/or email. "
        "Does not create passwords or participant login credentials. Restricted to administrators."
    ),
)
def create_participant(
    payload: ParticipantCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin),
):
    participant = ParticipantService(db).create_participant(payload, actor=actor)
    return ok(
        ParticipantRead.model_validate(participant).model_dump(mode="json"),
        request_id=getattr(request.state, "request_id", None),
    )


@router.get(
    "/lookup",
    summary="Identify a participant by phone number (preferred) or email",
    description=(
        "Privacy-preserving participant lookup. Unauthenticated public callers always "
        "receive a generic non-enumerating response ready for OTP verification. "
        "Authorised administrative callers receive the minimal matched record and the "
        "access is recorded in audit_logs."
    ),
)
def lookup_participant(
    request: Request,
    phone: str | None = Query(default=None, description="Registered or WhatsApp phone number"),
    email: str | None = Query(default=None, description="Registered email address"),
    event_id: UUID | None = Query(default=None, description="Optional event scope"),
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(resolve_optional_admin),
):
    result = ParticipantService(db).lookup_participant(
        phone=phone, email=email, event_id=event_id, actor=actor
    )
    return ok(
        result.model_dump(mode="json"),
        request_id=getattr(request.state, "request_id", None),
    )


@router.post(
    "/import",
    summary="Import participant records from CSV or Excel (.xlsx)",
    description=(
        "Validates, normalises phone numbers and emails, detects duplicates and incomplete rows, "
        "and produces an import report. Set dry_run=true (default) to review records before committing. "
        "Restricted to administrators."
    ),
)
async def import_participants(
    request: Request,
    file: UploadFile = File(..., description="CSV or Excel (.xlsx) participant file"),
    event_id: UUID | None = Form(default=None),
    data_source: str = Form(default="import"),
    dry_run: bool = Form(default=True),
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin),
):
    file_bytes = await file.read()
    report = ParticipantService(db).import_participants(
        file_bytes=file_bytes,
        filename=file.filename or "upload.csv",
        event_id=event_id,
        data_source=data_source,
        dry_run=dry_run,
        actor=actor,
    )
    return ok(
        report.model_dump(mode="json"),
        request_id=getattr(request.state, "request_id", None),
    )


@router.get(
    "/{participant_id}",
    summary="Retrieve a participant profile",
    description="Returns full participant record by UUID. Restricted to administrators to protect PII.",
)
def get_participant(
    participant_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin),
):
    participant = ParticipantService(db).get_participant(participant_id)
    return ok(
        ParticipantRead.model_validate(participant).model_dump(mode="json"),
        request_id=getattr(request.state, "request_id", None),
    )


@router.patch(
    "/{participant_id}",
    summary="Update a participant profile",
    description="Partially updates participant contact details or professional background. Restricted to administrators.",
)
def update_participant(
    participant_id: UUID,
    payload: ParticipantUpdate,
    request: Request,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin),
):
    participant = ParticipantService(db).update_participant(
        participant_id, payload, actor=actor
    )
    return ok(
        ParticipantRead.model_validate(participant).model_dump(mode="json"),
        request_id=getattr(request.state, "request_id", None),
    )


@router.get(
    "/{participant_id}/impact",
    summary="Get holistic impact summary for a participant",
    description=(
        "Returns latest six-pillar scores, intended vs. completed actions, networking connections, "
        "evidence-classified outcomes, and 30/60/90-day follow-up progress. Restricted to administrators."
    ),
)
def get_participant_impact(
    participant_id: UUID,
    request: Request,
    event_id: UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin),
):
    summary = ImpactTrackingService(db).get_participant_impact_summary(
        participant_id, event_id=event_id
    )
    return ok(
        summary.model_dump(mode="json"),
        request_id=getattr(request.state, "request_id", None),
    )
