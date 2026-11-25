"""Longitudinal follow-up (30/60/90-day), actions, connections, and outcome evidence routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.core.responses import ok
from app.core.security import ActorContext, require_admin, resolve_optional_admin
from app.database.session import get_db
from app.schemas.impact import (
    FollowUpScheduleCreate,
    FollowUpScheduleRead,
    FollowUpStageConfigCreate,
    FollowUpStageConfigRead,
    FollowUpSubmissionRead,
    FollowUpSubmitRequest,
    ImpactOutcomeCreate,
    ImpactOutcomeRead,
    OutcomeEvidenceIn,
    OutcomeVerifyRequest,
    ParticipantActionCreate,
    ParticipantActionRead,
    ParticipantActionUpdate,
    ProfessionalConnectionCreate,
    ProfessionalConnectionRead,
)
from app.services.impact_service import ImpactTrackingService

router = APIRouter(tags=["Follow-Ups & Impact Tracking"])


@router.post(
    "/follow-ups/stages",
    status_code=status.HTTP_201_CREATED,
    summary="Configure a custom follow-up stage",
    description="Adds a configurable follow-up period (e.g., 180_day) globally or for a specific event without database changes. Restricted to administrators.",
)
def create_follow_up_stage(
    payload: FollowUpStageConfigCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin),
):
    cfg = ImpactTrackingService(db).create_stage_config(payload, actor=actor)
    return ok(
        FollowUpStageConfigRead.model_validate(cfg).model_dump(mode="json"),
        request_id=getattr(request.state, "request_id", None),
    )


@router.get(
    "/follow-ups/stages",
    summary="List configured follow-up stages",
)
def list_follow_up_stages(
    request: Request,
    event_id: UUID | None = Query(default=None),
    db: Session = Depends(get_db),
):
    stages = ImpactTrackingService(db).list_stage_configs(event_id=event_id)
    return ok(
        [FollowUpStageConfigRead.model_validate(s).model_dump(mode="json") for s in stages],
        meta={"total": len(stages)},
        request_id=getattr(request.state, "request_id", None),
    )


@router.post(
    "/follow-ups",
    status_code=status.HTTP_201_CREATED,
    summary="Schedule follow-up assessments for a participant",
    description=(
        "Creates a specific follow-up schedule or auto-generates all active stages "
        "(30-day, 60-day, 90-day) relative to the event date. Restricted to administrators."
    ),
)
def create_follow_ups(
    payload: FollowUpScheduleCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin),
):
    schedules = ImpactTrackingService(db).create_follow_up_schedules(
        payload, actor=actor
    )
    return ok(
        [FollowUpScheduleRead.model_validate(s).model_dump(mode="json") for s in schedules],
        meta={"total": len(schedules)},
        request_id=getattr(request.state, "request_id", None),
    )


@router.get(
    "/follow-ups",
    summary="List follow-up schedules",
    description="Lists follow-up schedules filtered by event, participant, stage, or status. Restricted to administrators.",
)
def list_follow_ups(
    request: Request,
    event_id: UUID | None = Query(default=None),
    participant_id: UUID | None = Query(default=None),
    follow_up_stage: str | None = Query(default=None),
    follow_up_status: str | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin),
):
    schedules = ImpactTrackingService(db).list_follow_ups(
        event_id=event_id,
        participant_id=participant_id,
        follow_up_stage=follow_up_stage,
        status=follow_up_status,
    )
    return ok(
        [FollowUpScheduleRead.model_validate(s).model_dump(mode="json") for s in schedules],
        meta={"total": len(schedules)},
        request_id=getattr(request.state, "request_id", None),
    )


@router.post(
    "/follow-ups/{follow_up_id}/submit",
    status_code=status.HTTP_201_CREATED,
    summary="Submit a follow-up assessment",
    description=(
        "Records a participant's 30/60/90-day follow-up responses, actions (separating "
        "intended vs. completed), and outcomes with evidence classification. Leaves other "
        "scheduled follow-up stages independent."
    ),
)
def submit_follow_up(
    follow_up_id: UUID,
    payload: FollowUpSubmitRequest,
    request: Request,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(resolve_optional_admin),
):
    sub = ImpactTrackingService(db).submit_follow_up(
        follow_up_id, payload, actor=actor
    )
    return ok(
        FollowUpSubmissionRead.model_validate(sub).model_dump(mode="json"),
        request_id=getattr(request.state, "request_id", None),
    )


@router.get(
    "/participants/{participant_id}/follow-ups",
    summary="Get longitudinal follow-up timeline for a participant",
    description="Returns all scheduled, pending, and completed follow-up stages and submissions for a participant. Restricted to administrators.",
)
def get_participant_follow_ups(
    participant_id: UUID,
    request: Request,
    event_id: UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin),
):
    schedules = ImpactTrackingService(db).get_participant_follow_ups(
        participant_id, event_id=event_id
    )
    return ok(
        [FollowUpScheduleRead.model_validate(s).model_dump(mode="json") for s in schedules],
        meta={"total": len(schedules)},
        request_id=getattr(request.state, "request_id", None),
    )


# --- Structured Impact Tracking Sub-Resources ---


@router.get(
    "/impact/actions",
    summary="List participant actions",
    description="Returns paginated intended, in-progress, completed, and abandoned participant actions. Restricted to administrators.",
)
def list_actions(
    request: Request,
    event_id: UUID | None = Query(default=None),
    participant_id: UUID | None = Query(default=None),
    action_status: str | None = Query(default=None),
    action_category: str | None = Query(default=None),
    evidence_classification: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin),
):
    items, total = ImpactTrackingService(db).list_actions(
        event_id=event_id,
        participant_id=participant_id,
        action_status=action_status,
        action_category=action_category,
        evidence_classification=evidence_classification,
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
    "/impact/actions",
    status_code=status.HTTP_201_CREATED,
    summary="Record a participant action (intended, in_progress, or completed)",
)
def create_action(
    payload: ParticipantActionCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(resolve_optional_admin),
):
    action = ImpactTrackingService(db).create_action(payload, actor=actor)
    return ok(
        ParticipantActionRead.model_validate(action).model_dump(mode="json"),
        request_id=getattr(request.state, "request_id", None),
    )


@router.patch(
    "/impact/actions/{action_id}",
    summary="Update a participant action status or evidence",
)
def update_action(
    action_id: UUID,
    payload: ParticipantActionUpdate,
    request: Request,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin),
):
    action = ImpactTrackingService(db).update_action(action_id, payload, actor=actor)
    return ok(
        ParticipantActionRead.model_validate(action).model_dump(mode="json"),
        request_id=getattr(request.state, "request_id", None),
    )


@router.get(
    "/impact/connections",
    summary="List professional connections",
    description="Returns paginated participant-reported networking connections, collaborations, and opportunities. Restricted to administrators.",
)
def list_connections(
    request: Request,
    event_id: UUID | None = Query(default=None),
    participant_id: UUID | None = Query(default=None),
    connection_type: str | None = Query(default=None),
    evidence_classification: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin),
):
    items, total = ImpactTrackingService(db).list_connections(
        event_id=event_id,
        participant_id=participant_id,
        connection_type=connection_type,
        evidence_classification=evidence_classification,
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
    "/impact/connections",
    status_code=status.HTTP_201_CREATED,
    summary="Record a meaningful professional connection established at an event",
)
def create_connection(
    payload: ProfessionalConnectionCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(resolve_optional_admin),
):
    conn = ImpactTrackingService(db).create_connection(payload, actor=actor)
    return ok(
        ProfessionalConnectionRead.model_validate(conn).model_dump(mode="json"),
        request_id=getattr(request.state, "request_id", None),
    )


@router.get(
    "/impact/outcomes",
    summary="List impact outcomes and evidence",
    description="Returns paginated impact outcomes with evidence items and verification status for review and verification. Restricted to administrators.",
)
def list_outcomes(
    request: Request,
    event_id: UUID | None = Query(default=None),
    participant_id: UUID | None = Query(default=None),
    outcome_type: str | None = Query(default=None),
    evidence_classification: str | None = Query(default=None),
    verification_status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin),
):
    items, total = ImpactTrackingService(db).list_outcomes(
        event_id=event_id,
        participant_id=participant_id,
        outcome_type=outcome_type,
        evidence_classification=evidence_classification,
        verification_status=verification_status,
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
    "/impact/outcomes",
    status_code=status.HTTP_201_CREATED,
    summary="Record a participant impact outcome",
    description="Outcomes submitted without supporting evidence are automatically classified as self_reported.",
)
def create_outcome(
    payload: ImpactOutcomeCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(resolve_optional_admin),
):
    outcome = ImpactTrackingService(db).create_outcome(payload, actor=actor)
    return ok(
        ImpactOutcomeRead.model_validate(outcome).model_dump(mode="json"),
        request_id=getattr(request.state, "request_id", None),
    )


@router.post(
    "/impact/outcomes/{outcome_id}/evidence",
    status_code=status.HTTP_201_CREATED,
    summary="Attach supporting evidence to an outcome (promotes to documented)",
)
def attach_evidence(
    outcome_id: UUID,
    payload: OutcomeEvidenceIn,
    request: Request,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(resolve_optional_admin),
):
    outcome = ImpactTrackingService(db).attach_evidence(
        outcome_id, payload, actor=actor
    )
    return ok(
        ImpactOutcomeRead.model_validate(outcome).model_dump(mode="json"),
        request_id=getattr(request.state, "request_id", None),
    )


@router.patch(
    "/impact/outcomes/{outcome_id}/verify",
    summary="Independently verify or reject a documented outcome",
    description="Promotes outcome evidence_classification to verified upon approval. Restricted to administrators.",
)
def verify_outcome(
    outcome_id: UUID,
    payload: OutcomeVerifyRequest,
    request: Request,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin),
):
    outcome = ImpactTrackingService(db).verify_outcome(outcome_id, payload, actor=actor)
    return ok(
        ImpactOutcomeRead.model_validate(outcome).model_dump(mode="json"),
        request_id=getattr(request.state, "request_id", None),
    )
