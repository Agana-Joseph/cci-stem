"""Aggregate event analytics endpoints for the future dashboard."""

from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.analytics.service import AnalyticsService
from app.core.responses import ok
from app.core.security import ActorContext, require_admin
from app.database.session import get_db

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get(
    "/events/{event_id}/overview",
    summary="Event overview analytics",
    description=(
        "Returns registered participants, confirmed attendees, attendance rate (only when reliable), "
        "assessment completion, composite and horizon-separated impact scores with response counts "
        "and data coverage indicators. Restricted to administrators."
    ),
)
def event_overview(
    event_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin),
):
    data = AnalyticsService(db).get_event_overview(event_id)
    return ok(data, request_id=getattr(request.state, "request_id", None))


@router.get(
    "/events/{event_id}/pillars",
    summary="Six-pillar performance analytics for an event",
    description="Returns mean, median, std dev, min, max, sample size, missing count, and data coverage per measurement pillar. Restricted to administrators.",
)
def event_pillars(
    event_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin),
):
    data = AnalyticsService(db).get_pillar_analytics(event_id)
    return ok(data, request_id=getattr(request.state, "request_id", None))


@router.get(
    "/events/{event_id}/networking",
    summary="Networking and relationship outcomes analytics",
    description="Returns connection volume, follow-up conversations, collaborations started, opportunities discovered, and data coverage. Restricted to administrators.",
)
def event_networking(
    event_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin),
):
    data = AnalyticsService(db).get_networking_analytics(event_id)
    return ok(data, request_id=getattr(request.state, "request_id", None))


@router.get(
    "/events/{event_id}/application",
    summary="Post-event application and action conversion analytics",
    description="Separates intended actions from completed workplace implementations and breaks down outcomes by evidence classification. Restricted to administrators.",
)
def event_application(
    event_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin),
):
    data = AnalyticsService(db).get_application_analytics(event_id)
    return ok(data, request_id=getattr(request.state, "request_id", None))


@router.get(
    "/events/{event_id}/follow-ups",
    summary="30/60/90-day longitudinal follow-up comparison analytics",
    description="Compares completion rates, reported actions, positive action signals, and evidence classifications across follow-up stages. Restricted to administrators.",
)
def event_follow_ups(
    event_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin),
):
    data = AnalyticsService(db).get_follow_up_analytics(event_id)
    return ok(data, request_id=getattr(request.state, "request_id", None))
