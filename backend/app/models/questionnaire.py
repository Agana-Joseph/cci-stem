"""Question Cards, Questions, Questionnaires, Assessment Submissions & Responses models."""

from datetime import date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import (
    QuestionType,
    QuestionnaireStatus,
    QuestionnaireType,
    SubmissionStatus,
)
from app.database.base import Base, JSONBType, TimestampMixin, UUIDPrimaryKeyMixin, utc_now


class QuestionCard(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "question_cards"

    code: Mapped[str] = mapped_column(String(80), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(100), default="reflection", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    questions: Mapped[list["Question"]] = relationship(
        back_populates="card", order_by="Question.display_order"
    )


class Question(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "questions"
    __table_args__ = (Index("ix_questions_card_id", "card_id"),)

    card_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("question_cards.id", ondelete="SET NULL"),
        nullable=True,
    )
    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    question_type: Mapped[str] = mapped_column(
        String(40), default=QuestionType.SHORT_TEXT.value, nullable=False
    )
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_scorable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    allow_explanation: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    explanation_prompt: Mapped[str | None] = mapped_column(String(300), nullable=True)
    validation_config: Mapped[dict[str, Any] | None] = mapped_column(
        JSONBType, nullable=True
    )
    scoring_config: Mapped[dict[str, Any] | None] = mapped_column(
        JSONBType, nullable=True
    )
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    card: Mapped["QuestionCard | None"] = relationship(back_populates="questions")
    options: Mapped[list["QuestionOption"]] = relationship(
        back_populates="question",
        cascade="all, delete-orphan",
        order_by="QuestionOption.display_order",
    )
    pillar_mappings: Mapped[list["QuestionPillarMapping"]] = relationship(
        back_populates="question", cascade="all, delete-orphan"
    )


class QuestionPillarMapping(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Many-to-many link allowing a question to map to one or more measurement pillars."""

    __tablename__ = "question_pillar_mappings"
    __table_args__ = (
        UniqueConstraint("question_id", "pillar_id", name="uq_question_pillar"),
        Index("ix_question_pillar_mappings_question_id", "question_id"),
        Index("ix_question_pillar_mappings_pillar_id", "pillar_id"),
    )

    question_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("questions.id", ondelete="CASCADE"), nullable=False
    )
    pillar_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("measurement_pillars.id", ondelete="CASCADE"),
        nullable=False,
    )
    is_primary: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    question: Mapped["Question"] = relationship(back_populates="pillar_mappings")


class QuestionOption(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "question_options"
    __table_args__ = (Index("ix_question_options_question_id", "question_id"),)

    question_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("questions.id", ondelete="CASCADE"), nullable=False
    )
    option_value: Mapped[str] = mapped_column(String(120), nullable=False)
    option_label: Mapped[str] = mapped_column(String(300), nullable=False)
    score_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    question: Mapped["Question"] = relationship(back_populates="options")


class Questionnaire(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "questionnaires"
    __table_args__ = (Index("ix_questionnaires_event_id", "event_id"),)

    event_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("events.id", ondelete="SET NULL"),
        nullable=True,
    )
    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    questionnaire_type: Mapped[str] = mapped_column(
        String(40), default=QuestionnaireType.POST_EVENT.value, nullable=False
    )
    version: Mapped[str] = mapped_column(String(32), default="1.0", nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), default=QuestionnaireStatus.DRAFT.value, nullable=False
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    sections: Mapped[list["QuestionnaireSection"]] = relationship(
        back_populates="questionnaire",
        cascade="all, delete-orphan",
        order_by="QuestionnaireSection.display_order",
    )
    questionnaire_questions: Mapped[list["QuestionnaireQuestion"]] = relationship(
        back_populates="questionnaire",
        cascade="all, delete-orphan",
        order_by="QuestionnaireQuestion.display_order",
    )


class QuestionnaireSection(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "questionnaire_sections"
    __table_args__ = (
        UniqueConstraint("questionnaire_id", "code", name="uq_qsection_code"),
        Index("ix_questionnaire_sections_questionnaire_id", "questionnaire_id"),
    )

    questionnaire_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("questionnaires.id", ondelete="CASCADE"),
        nullable=False,
    )
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    questionnaire: Mapped["Questionnaire"] = relationship(back_populates="sections")
    questions: Mapped[list["QuestionnaireQuestion"]] = relationship(
        back_populates="section", order_by="QuestionnaireQuestion.display_order"
    )


class QuestionnaireQuestion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "questionnaire_questions"
    __table_args__ = (
        UniqueConstraint(
            "questionnaire_id", "question_id", name="uq_questionnaire_question"
        ),
        Index("ix_questionnaire_questions_questionnaire_id", "questionnaire_id"),
    )

    questionnaire_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("questionnaires.id", ondelete="CASCADE"),
        nullable=False,
    )
    section_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("questionnaire_sections.id", ondelete="SET NULL"),
        nullable=True,
    )
    question_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("questions.id", ondelete="CASCADE"), nullable=False
    )
    is_required_override: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    questionnaire: Mapped["Questionnaire"] = relationship(
        back_populates="questionnaire_questions"
    )
    section: Mapped["QuestionnaireSection | None"] = relationship(
        back_populates="questions"
    )
    question: Mapped["Question"] = relationship()


class AssessmentSubmission(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "assessment_submissions"
    __table_args__ = (
        Index("ix_assessment_submissions_participant_id", "participant_id"),
        Index("ix_assessment_submissions_event_id", "event_id"),
        Index("ix_assessment_submissions_submitted_at", "submitted_at"),
    )

    participant_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("participants.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"), nullable=False
    )
    questionnaire_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("questionnaires.id", ondelete="RESTRICT"),
        nullable=False,
    )
    submission_channel: Mapped[str] = mapped_column(
        String(40), default="web_api", nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(32), default=SubmissionStatus.SUBMITTED.value, nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    completeness_ratio: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSONBType, nullable=True
    )

    responses: Mapped[list["AssessmentResponse"]] = relationship(
        back_populates="submission", cascade="all, delete-orphan"
    )


class AssessmentResponse(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "assessment_responses"
    __table_args__ = (
        UniqueConstraint(
            "submission_id", "question_id", name="uq_submission_question_response"
        ),
        Index("ix_assessment_responses_submission_id", "submission_id"),
        Index("ix_assessment_responses_question_id", "question_id"),
    )

    submission_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("assessment_submissions.id", ondelete="CASCADE"),
        nullable=False,
    )
    question_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("questions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    response_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_numeric: Mapped[float | None] = mapped_column(Float, nullable=True)
    response_boolean: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    response_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    response_json: Mapped[Any | None] = mapped_column(JSONBType, nullable=True)
    explanation_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    answered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    submission: Mapped["AssessmentSubmission"] = relationship(back_populates="responses")
    question: Mapped["Question"] = relationship()
