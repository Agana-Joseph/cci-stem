"""Question Card management routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.core.responses import ok
from app.core.security import ActorContext, require_admin
from app.database.session import get_db
from app.schemas.questionnaire import (
    QuestionCardCreate,
    QuestionCardUpdate,
    QuestionCreate,
)
from app.services.questionnaire_service import QuestionEngineService

router = APIRouter(prefix="/question-cards", tags=["Question Cards"])


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Create a question card",
    description="Creates a new discussion or assessment question card. Restricted to administrators.",
)
def create_card(
    payload: QuestionCardCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin),
):
    card = QuestionEngineService(db).create_card(payload, actor=actor)
    return ok(
        card.model_dump(mode="json"),
        request_id=getattr(request.state, "request_id", None),
    )


@router.get(
    "",
    summary="List question cards",
    description="Returns active question cards along with their non-archived questions.",
)
def list_cards(
    request: Request,
    include_inactive: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    cards = QuestionEngineService(db).list_cards(include_inactive=include_inactive)
    return ok(
        [c.model_dump(mode="json") for c in cards],
        meta={"total": len(cards)},
        request_id=getattr(request.state, "request_id", None),
    )


@router.get(
    "/{card_id}",
    summary="Get a question card by ID",
)
def get_card(
    card_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
):
    card = QuestionEngineService(db).get_card(card_id)
    return ok(
        card.model_dump(mode="json"),
        request_id=getattr(request.state, "request_id", None),
    )


@router.patch(
    "/{card_id}",
    summary="Update a question card",
    description="Updates question card metadata or active status. Restricted to administrators.",
)
def update_card(
    card_id: UUID,
    payload: QuestionCardUpdate,
    request: Request,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin),
):
    card = QuestionEngineService(db).update_card(card_id, payload, actor=actor)
    return ok(
        card.model_dump(mode="json"),
        request_id=getattr(request.state, "request_id", None),
    )


@router.post(
    "/{card_id}/questions",
    status_code=status.HTTP_201_CREATED,
    summary="Add a question to a question card",
    description="Creates a new question attached to the specified question card. Restricted to administrators.",
)
def add_question_to_card(
    card_id: UUID,
    payload: QuestionCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin),
):
    question = QuestionEngineService(db).add_question_to_card(
        card_id, payload, actor=actor
    )
    return ok(
        question.model_dump(mode="json"),
        request_id=getattr(request.state, "request_id", None),
    )
