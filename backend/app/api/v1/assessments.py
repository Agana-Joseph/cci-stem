"""Assessment submission, admin review list, and qualitative feedback routes."""

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.core.responses import ok
from app.core.security import ActorContext, require_admin, resolve_optional_admin
from app.database.session import get_db
from app.schemas.questionnaire import AssessmentSubmissionRead, AssessmentSubmitRequest
from app.services.questionnaire_service import QuestionEngineService

router = APIRouter(tags=["Assessments"])


@router.get(
    "/assessments",
    summary="List assessment submissions",
    description=(
        "Returns a paginated list of assessment submissions across events and participants "
        "with search, status, and date filters. Restricted to administrators."
    ),
)
def list_assessments(
    request: Request,
    event_id: UUID | None = Query(default=None),
    questionnaire_id: UUID | None = Query(default=None),
    participant_id: UUID | None = Query(default=None),
    submission_status: str | None = Query(default=None, alias="status"),
    q: str | None = Query(default=None, description="Search by participant name, email, or phone"),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    sort_order: str = Query(default="desc", pattern=r"^(asc|desc)$"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin),
):
    items, total = QuestionEngineService(db).list_assessments(
        event_id=event_id,
        questionnaire_id=questionnaire_id,
        participant_id=participant_id,
        status=submission_status,
        q=q,
        date_from=date_from,
        date_to=date_to,
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


@router.get(
    "/feedback",
    tags=["Feedback"],
    summary="List qualitative feedback and individual assessment responses",
    description=(
        "Queries individual assessment responses preserving original participant wording. "
        "Filter by event, question, reflective card, questionnaire section, measurement pillar, "
        "scorable flag (e.g. is_scorable=false for reflective/qualitative feedback), industry, or date range. "
        "Restricted to administrators."
    ),
)
def list_feedback(
    request: Request,
    event_id: UUID | None = Query(default=None),
    questionnaire_id: UUID | None = Query(default=None),
    question_id: UUID | None = Query(default=None),
    card_id: UUID | None = Query(default=None),
    section_code: str | None = Query(default=None),
    pillar_id: UUID | None = Query(default=None),
    is_scorable: bool | None = Query(default=None),
    industry: str | None = Query(default=None),
    participant_id: UUID | None = Query(default=None),
    q: str | None = Query(default=None, description="Full-text search in response or explanation text"),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin),
):
    items, total = QuestionEngineService(db).list_feedback(
        event_id=event_id,
        questionnaire_id=questionnaire_id,
        question_id=question_id,
        card_id=card_id,
        section_code=section_code,
        pillar_id=pillar_id,
        is_scorable=is_scorable,
        industry=industry,
        participant_id=participant_id,
        q=q,
        date_from=date_from,
        date_to=date_to,
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
    "/assessments/submit",
    status_code=status.HTTP_201_CREATED,
    summary="Submit a participant assessment",
    description=(
        "Associates assessment responses to an existing participant (via participant_id, "
        "normalised phone number, or email), validates every response against its question "
        "definition, and calculates submission completeness."
    ),
)
def submit_assessment(
    payload: AssessmentSubmitRequest,
    request: Request,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(resolve_optional_admin),
):
    submission = QuestionEngineService(db).submit_assessment(payload, actor=actor)
    return ok(
        AssessmentSubmissionRead.model_validate(submission).model_dump(mode="json"),
        request_id=getattr(request.state, "request_id", None),
    )


@router.get(
    "/assessments/{assessment_id}",
    summary="Get an assessment submission by ID",
    description="Returns submission metadata and responses. Restricted to administrators.",
)
def get_assessment(
    assessment_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin),
):
    submission = QuestionEngineService(db).get_assessment(assessment_id)
    return ok(
        AssessmentSubmissionRead.model_validate(submission).model_dump(mode="json"),
        request_id=getattr(request.state, "request_id", None),
    )


@router.get(
    "/participants/{participant_id}/assessments",
    summary="List assessment submissions for a participant",
    description="Returns all assessment submissions belonging to the specified participant. Restricted to administrators.",
)
def list_participant_assessments(
    participant_id: UUID,
    request: Request,
    event_id: UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin),
):
    submissions = QuestionEngineService(db).list_participant_assessments(
        participant_id, event_id=event_id
    )
    return ok(
        [
            AssessmentSubmissionRead.model_validate(s).model_dump(mode="json")
            for s in submissions
        ],
        meta={"total": len(submissions)},
        request_id=getattr(request.state, "request_id", None),
    )
