"""Event and participant reporting & export routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.enums import ExportFormat
from app.core.responses import ok
from app.core.security import ActorContext, require_admin
from app.database.session import get_db
from app.reports.service import ReportingService

router = APIRouter(prefix="/reports", tags=["Reporting"])


class ExportRequest(BaseModel):
    export_format: ExportFormat = ExportFormat.JSON
    event_id: UUID | None = None


@router.get(
    "/events/{event_id}",
    summary="Generate structured event impact report",
    description="Returns complete event overview, six-pillar performance, networking, application, and 30/60/90-day follow-up data. Restricted to administrators.",
)
def get_event_report(
    event_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin),
):
    report = ReportingService(db).build_event_report(event_id)
    return ok(report, request_id=getattr(request.state, "request_id", None))


@router.get(
    "/participants/{participant_id}",
    summary="Generate structured participant impact report",
    description="Returns participant profile summary, score history, actions, connections, outcomes, and follow-up timeline. Restricted to administrators.",
)
def get_participant_report(
    participant_id: UUID,
    request: Request,
    event_id: UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin),
):
    report = ReportingService(db).build_participant_report(
        participant_id, event_id=event_id
    )
    return ok(report, request_id=getattr(request.state, "request_id", None))


@router.post(
    "/events/{event_id}/export",
    summary="Export an event impact report (JSON, CSV, or XLSX)",
    description="Writes an export artifact, records a ReportRecord and AuditLog entry, and returns export metadata. Restricted to administrators.",
)
def export_event_report(
    event_id: UUID,
    request: Request,
    payload: ExportRequest | None = None,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin),
):
    fmt = payload.export_format if payload else ExportFormat.JSON
    result = ReportingService(db).export_event_report(
        event_id, export_format=fmt, actor=actor
    )
    return ok(result, request_id=getattr(request.state, "request_id", None))


@router.post(
    "/participants/{participant_id}/export",
    summary="Export a participant impact report (JSON, CSV, or XLSX)",
    description="Writes a participant export artifact, records a ReportRecord and AuditLog entry, and returns export metadata. Restricted to administrators.",
)
def export_participant_report(
    participant_id: UUID,
    request: Request,
    payload: ExportRequest | None = None,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin),
):
    fmt = payload.export_format if payload else ExportFormat.JSON
    event_id = payload.event_id if payload else None
    result = ReportingService(db).export_participant_report(
        participant_id, event_id=event_id, export_format=fmt, actor=actor
    )
    return ok(result, request_id=getattr(request.state, "request_id", None))
