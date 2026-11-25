"""Assessment submission and retrieval routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.core.responses import ok
from app.core.security import ActorContext, require_admin, resolve_optional_admin
from app.database.session import get_db
from app.schemas.questionnaire import AssessmentSubmissionRead, AssessmentSubmitRequest
from app.services.questionnaire_service import QuestionEngineService

router = APIRouter(tags=["Assessments"])


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
