"""Question bank management routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.core.responses import ok
from app.core.security import ActorContext, require_admin
from app.database.session import get_db
from app.schemas.questionnaire import QuestionCreate, QuestionUpdate
from app.services.questionnaire_service import QuestionEngineService

router = APIRouter(prefix="/questions", tags=["Questions"])


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Create a question",
    description="Creates a configurable question supporting multiple types, pillar mappings, options, and qualitative vs. scorable distinction. Restricted to administrators.",
)
def create_question(
    payload: QuestionCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin),
):
    question = QuestionEngineService(db).create_question(payload, actor=actor)
    return ok(
        question.model_dump(mode="json"),
        request_id=getattr(request.state, "request_id", None),
    )


@router.get(
    "",
    summary="List questions",
    description="Lists questions with optional filters by card, measurement pillar, type, or scorable status.",
)
def list_questions(
    request: Request,
    include_archived: bool = Query(default=False),
    card_id: UUID | None = Query(default=None),
    pillar_id: UUID | None = Query(default=None),
    question_type: str | None = Query(default=None),
    is_scorable: bool | None = Query(default=None),
    db: Session = Depends(get_db),
):
    questions = QuestionEngineService(db).list_questions(
        include_archived=include_archived,
        card_id=card_id,
        pillar_id=pillar_id,
        question_type=question_type,
        is_scorable=is_scorable,
    )
    return ok(
        [q.model_dump(mode="json") for q in questions],
        meta={"total": len(questions)},
        request_id=getattr(request.state, "request_id", None),
    )


@router.get(
    "/{question_id}",
    summary="Get a question by ID",
)
def get_question(
    question_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
):
    question = QuestionEngineService(db).get_question(question_id)
    return ok(
        question.model_dump(mode="json"),
        request_id=getattr(request.state, "request_id", None),
    )


@router.patch(
    "/{question_id}",
    summary="Update a question",
    description="Updates question text, type, options, pillar assignments, or scoring metadata. Restricted to administrators.",
)
def update_question(
    question_id: UUID,
    payload: QuestionUpdate,
    request: Request,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin),
):
    question = QuestionEngineService(db).update_question(
        question_id, payload, actor=actor
    )
    return ok(
        question.model_dump(mode="json"),
        request_id=getattr(request.state, "request_id", None),
    )


@router.patch(
    "/{question_id}/archive",
    summary="Archive a question",
    description="Soft-archives a question so historical responses remain intact. Restricted to administrators.",
)
def archive_question(
    question_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin),
):
    question = QuestionEngineService(db).archive_question(question_id, actor=actor)
    return ok(
        question.model_dump(mode="json"),
        request_id=getattr(request.state, "request_id", None),
    )
