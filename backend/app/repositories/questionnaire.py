"""Repositories for Question Cards, Questions, Questionnaires, and Assessment Submissions."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.questionnaire import (
    AssessmentSubmission,
    Question,
    QuestionCard,
    Questionnaire,
    QuestionnaireQuestion,
    QuestionPillarMapping,
)


class QuestionCardRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, card_id: UUID) -> QuestionCard | None:
        stmt = (
            select(QuestionCard)
            .options(
                selectinload(QuestionCard.questions).selectinload(Question.options),
                selectinload(QuestionCard.questions).selectinload(Question.pillar_mappings),
            )
            .where(QuestionCard.id == card_id)
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_code(self, code: str) -> QuestionCard | None:
        return self.db.execute(
            select(QuestionCard).where(QuestionCard.code == code)
        ).scalar_one_or_none()

    def list_cards(self, *, include_inactive: bool = False) -> list[QuestionCard]:
        stmt = select(QuestionCard).options(
            selectinload(QuestionCard.questions).selectinload(Question.options),
            selectinload(QuestionCard.questions).selectinload(Question.pillar_mappings),
        )
        if not include_inactive:
            stmt = stmt.where(QuestionCard.is_active.is_(True))
        return list(
            self.db.execute(stmt.order_by(QuestionCard.display_order.asc())).scalars().all()
        )


class QuestionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, question_id: UUID) -> Question | None:
        stmt = (
            select(Question)
            .options(
                selectinload(Question.options),
                selectinload(Question.pillar_mappings),
            )
            .where(Question.id == question_id)
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_code(self, code: str) -> Question | None:
        return self.db.execute(
            select(Question).where(Question.code == code)
        ).scalar_one_or_none()

    def list_questions(
        self,
        *,
        include_archived: bool = False,
        card_id: UUID | None = None,
        pillar_id: UUID | None = None,
        question_type: str | None = None,
        is_scorable: bool | None = None,
    ) -> list[Question]:
        stmt = select(Question).options(
            selectinload(Question.options),
            selectinload(Question.pillar_mappings),
        )
        if not include_archived:
            stmt = stmt.where(Question.is_archived.is_(False))
        if card_id is not None:
            stmt = stmt.where(Question.card_id == card_id)
        if question_type is not None:
            stmt = stmt.where(Question.question_type == question_type)
        if is_scorable is not None:
            stmt = stmt.where(Question.is_scorable.is_(is_scorable))
        if pillar_id is not None:
            stmt = stmt.join(QuestionPillarMapping).where(
                QuestionPillarMapping.pillar_id == pillar_id
            )
        return list(
            self.db.execute(stmt.order_by(Question.display_order.asc())).scalars().unique().all()
        )


class QuestionnaireRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, questionnaire_id: UUID) -> Questionnaire | None:
        stmt = (
            select(Questionnaire)
            .options(
                selectinload(Questionnaire.sections),
                selectinload(Questionnaire.questionnaire_questions)
                .selectinload(QuestionnaireQuestion.question)
                .selectinload(Question.options),
                selectinload(Questionnaire.questionnaire_questions)
                .selectinload(QuestionnaireQuestion.question)
                .selectinload(Question.pillar_mappings),
            )
            .where(Questionnaire.id == questionnaire_id)
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_code(self, code: str) -> Questionnaire | None:
        return self.db.execute(
            select(Questionnaire).where(Questionnaire.code == code)
        ).scalar_one_or_none()

    def list_questionnaires(
        self,
        *,
        event_id: UUID | None = None,
        status: str | None = None,
        questionnaire_type: str | None = None,
    ) -> list[Questionnaire]:
        stmt = select(Questionnaire).options(
            selectinload(Questionnaire.sections),
            selectinload(Questionnaire.questionnaire_questions)
            .selectinload(QuestionnaireQuestion.question)
            .selectinload(Question.options),
            selectinload(Questionnaire.questionnaire_questions)
            .selectinload(QuestionnaireQuestion.question)
            .selectinload(Question.pillar_mappings),
        )
        if event_id is not None:
            stmt = stmt.where(Questionnaire.event_id == event_id)
        if status is not None:
            stmt = stmt.where(Questionnaire.status == status)
        if questionnaire_type is not None:
            stmt = stmt.where(Questionnaire.questionnaire_type == questionnaire_type)
        return list(
            self.db.execute(stmt.order_by(Questionnaire.created_at.desc())).scalars().all()
        )


class AssessmentRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, submission_id: UUID) -> AssessmentSubmission | None:
        stmt = (
            select(AssessmentSubmission)
            .options(selectinload(AssessmentSubmission.responses))
            .where(AssessmentSubmission.id == submission_id)
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def list_by_participant(
        self, participant_id: UUID, *, event_id: UUID | None = None
    ) -> list[AssessmentSubmission]:
        stmt = (
            select(AssessmentSubmission)
            .options(selectinload(AssessmentSubmission.responses))
            .where(AssessmentSubmission.participant_id == participant_id)
        )
        if event_id is not None:
            stmt = stmt.where(AssessmentSubmission.event_id == event_id)
        return list(
            self.db.execute(stmt.order_by(AssessmentSubmission.submitted_at.desc()))
            .scalars()
            .all()
        )
