"""Questionnaire builder and publishing routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.core.responses import ok
from app.core.security import ActorContext, require_admin
from app.database.session import get_db
from app.schemas.questionnaire import QuestionnaireCreate, QuestionnaireUpdate
from app.services.questionnaire_service import QuestionEngineService

router = APIRouter(prefix="/questionnaires", tags=["Questionnaires"])


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Create a configurable questionnaire",
    description="Builds a questionnaire with custom sections (e.g., Sections A–F) composed from existing questions. Restricted to administrators.",
)
def create_questionnaire(
    payload: QuestionnaireCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin),
):
    qn = QuestionEngineService(db).create_questionnaire(payload, actor=actor)
    return ok(
        qn.model_dump(mode="json"),
        request_id=getattr(request.state, "request_id", None),
    )


@router.get(
    "",
    summary="List questionnaires",
)
def list_questionnaires(
    request: Request,
    event_id: UUID | None = Query(default=None),
    questionnaire_status: str | None = Query(default=None, alias="status"),
    questionnaire_type: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    items = QuestionEngineService(db).list_questionnaires(
        event_id=event_id,
        status=questionnaire_status,
        questionnaire_type=questionnaire_type,
    )
    return ok(
        [qn.model_dump(mode="json") for qn in items],
        meta={"total": len(items)},
        request_id=getattr(request.state, "request_id", None),
    )


@router.get(
    "/{questionnaire_id}",
    summary="Get a questionnaire with sections and questions",
)
def get_questionnaire(
    questionnaire_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
):
    qn = QuestionEngineService(db).get_questionnaire(questionnaire_id)
    return ok(
        qn.model_dump(mode="json"),
        request_id=getattr(request.state, "request_id", None),
    )


@router.patch(
    "/{questionnaire_id}",
    summary="Update a questionnaire",
    description="Updates questionnaire metadata, sections, or attached questions. Restricted to administrators.",
)
def update_questionnaire(
    questionnaire_id: UUID,
    payload: QuestionnaireUpdate,
    request: Request,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin),
):
    qn = QuestionEngineService(db).update_questionnaire(
        questionnaire_id, payload, actor=actor
    )
    return ok(
        qn.model_dump(mode="json"),
        request_id=getattr(request.state, "request_id", None),
    )


@router.post(
    "/{questionnaire_id}/publish",
    summary="Publish a questionnaire",
    description="Transitions a questionnaire to published status so participants can submit assessments against it. Restricted to administrators.",
)
def publish_questionnaire(
    questionnaire_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin),
):
    qn = QuestionEngineService(db).publish_questionnaire(questionnaire_id, actor=actor)
    return ok(
        qn.model_dump(mode="json"),
        request_id=getattr(request.state, "request_id", None),
    )
