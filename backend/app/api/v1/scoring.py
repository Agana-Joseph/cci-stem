"""Measurement pillars, configurable scoring frameworks, and score calculation routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.core.responses import ok
from app.core.security import ActorContext, require_admin
from app.database.session import get_db
from app.schemas.scoring import (
    CalculateEventScoresRequest,
    CalculateParticipantScoreRequest,
    MeasurementPillarRead,
    ScoringFrameworkCreate,
    ScoringFrameworkUpdate,
)
from app.scoring.service import ScoringService

router = APIRouter(tags=["Scoring"])


@router.get(
    "/pillars",
    summary="List the six configurable measurement pillars",
    description="Returns active measurement pillars and their default proposed weights.",
)
def list_pillars(
    request: Request,
    db: Session = Depends(get_db),
):
    pillars = ScoringService(db).list_pillars()
    return ok(
        [MeasurementPillarRead.model_validate(p).model_dump(mode="json") for p in pillars],
        meta={"total": len(pillars)},
        request_id=getattr(request.state, "request_id", None),
    )


@router.get(
    "/scoring/frameworks",
    summary="List scoring frameworks",
    description="Returns all configured scoring framework versions with dimensions and rules. Restricted to administrators.",
)
def list_frameworks(
    request: Request,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin),
):
    items = ScoringService(db).list_frameworks()
    return ok(
        [fw.model_dump(mode="json") for fw in items],
        meta={"total": len(items)},
        request_id=getattr(request.state, "request_id", None),
    )


@router.post(
    "/scoring/frameworks",
    status_code=status.HTTP_201_CREATED,
    summary="Create a new versioned scoring framework",
    description="Creates a configurable scoring framework with pillar weights summing to 1.0 and question scoring rules. Restricted to administrators.",
)
def create_framework(
    payload: ScoringFrameworkCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin),
):
    fw = ScoringService(db).create_framework(payload, actor=actor)
    return ok(
        fw.model_dump(mode="json"),
        request_id=getattr(request.state, "request_id", None),
    )


@router.patch(
    "/scoring/frameworks/{framework_id}",
    summary="Update a scoring framework",
    description="Updates framework thresholds, pillar weights, or question scoring rules. Restricted to administrators.",
)
def update_framework(
    framework_id: UUID,
    payload: ScoringFrameworkUpdate,
    request: Request,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin),
):
    fw = ScoringService(db).update_framework(framework_id, payload, actor=actor)
    return ok(
        fw.model_dump(mode="json"),
        request_id=getattr(request.state, "request_id", None),
    )


@router.post(
    "/scoring/calculate/{participant_id}",
    summary="Calculate or recalculate impact score for a participant",
    description=(
        "Evaluates scorable responses across the six pillars, excludes missing dimensions "
        "with automatic weight renormalisation, separates immediate from post-event application "
        "and sustained impact, and preserves historical score records. Restricted to administrators."
    ),
)
def calculate_participant_score(
    participant_id: UUID,
    payload: CalculateParticipantScoreRequest,
    request: Request,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin),
):
    score = ScoringService(db).calculate_for_participant(
        participant_id=participant_id,
        event_id=payload.event_id,
        framework_id=payload.framework_id,
        assessment_submission_id=payload.assessment_submission_id,
        actor=actor,
    )
    return ok(
        score.model_dump(mode="json"),
        request_id=getattr(request.state, "request_id", None),
    )


@router.post(
    "/scoring/calculate-event/{event_id}",
    summary="Bulk calculate impact scores for all participants in an event",
    description="Calculates or recalculates scores for all registered and responding participants in an event. Restricted to administrators.",
)
def calculate_event_scores(
    event_id: UUID,
    request: Request,
    payload: CalculateEventScoresRequest | None = None,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin),
):
    result = ScoringService(db).calculate_for_event(
        event_id=event_id,
        framework_id=payload.framework_id if payload else None,
        actor=actor,
    )
    return ok(
        result.model_dump(mode="json"),
        request_id=getattr(request.state, "request_id", None),
    )


@router.get(
    "/scoring/participants/{participant_id}",
    summary="Get score history for a participant",
    description="Returns current and historical impact scores for a participant. Restricted to administrators.",
)
def get_participant_scores(
    participant_id: UUID,
    request: Request,
    event_id: UUID | None = Query(default=None),
    latest_only: bool = Query(default=False),
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin),
):
    scores = ScoringService(db).get_participant_scores(
        participant_id, event_id=event_id, latest_only=latest_only
    )
    return ok(
        [s.model_dump(mode="json") for s in scores],
        meta={"total": len(scores)},
        request_id=getattr(request.state, "request_id", None),
    )


@router.get(
    "/scoring/events/{event_id}",
    summary="Get impact scores for an event",
    description="Returns latest or historical participant impact scores for an event. Restricted to administrators.",
)
def get_event_scores(
    event_id: UUID,
    request: Request,
    latest_only: bool = Query(default=True),
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin),
):
    scores = ScoringService(db).get_event_scores(event_id, latest_only=latest_only)
    return ok(
        [s.model_dump(mode="json") for s in scores],
        meta={"total": len(scores)},
        request_id=getattr(request.state, "request_id", None),
    )
