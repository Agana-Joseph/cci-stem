"""Schemas for Question Cards, Questions, Questionnaires, and Assessment Submissions."""

from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.enums import QuestionType, QuestionnaireStatus, QuestionnaireType


class QuestionCategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    description: str | None = None
    display_order: int
    is_active: bool


class QuestionOptionIn(BaseModel):
    option_value: str = Field(..., min_length=1, max_length=120)
    option_label: str = Field(..., min_length=1, max_length=300)
    score_value: float | None = None
    display_order: int = 0
    is_active: bool = True


class QuestionOptionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    option_value: str
    option_label: str
    score_value: float | None = None
    display_order: int
    is_active: bool


class QuestionCreate(BaseModel):
    code: str = Field(..., min_length=2, max_length=100, pattern=r"^[a-z0-9_-]+$")
    question_text: str = Field(..., min_length=3)
    description: str | None = None
    question_type: QuestionType = QuestionType.SHORT_TEXT
    card_id: UUID | None = None
    category_id: UUID | None = None
    category: str | None = Field(default=None, max_length=100)
    is_required: bool = False
    is_scorable: bool = False
    allow_explanation: bool = False
    explanation_prompt: str | None = Field(default=None, max_length=300)
    validation_config: dict[str, Any] | None = None
    scoring_config: dict[str, Any] | None = None
    display_order: int = 0
    pillar_ids: list[UUID] = Field(default_factory=list)
    options: list[QuestionOptionIn] = Field(default_factory=list)


class QuestionUpdate(BaseModel):
    question_text: str | None = Field(default=None, min_length=3)
    description: str | None = None
    question_type: QuestionType | None = None
    card_id: UUID | None = None
    category_id: UUID | None = None
    category: str | None = Field(default=None, max_length=100)
    is_required: bool | None = None
    is_scorable: bool | None = None
    allow_explanation: bool | None = None
    explanation_prompt: str | None = Field(default=None, max_length=300)
    validation_config: dict[str, Any] | None = None
    scoring_config: dict[str, Any] | None = None
    display_order: int | None = None
    pillar_ids: list[UUID] | None = None
    options: list[QuestionOptionIn] | None = None


class QuestionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    card_id: UUID | None = None
    category_id: UUID | None = None
    code: str
    question_text: str
    description: str | None = None
    question_type: str
    category: str | None = None
    is_required: bool
    is_scorable: bool
    allow_explanation: bool
    explanation_prompt: str | None = None
    validation_config: dict[str, Any] | None = None
    scoring_config: dict[str, Any] | None = None
    display_order: int
    is_archived: bool
    archived_at: datetime | None = None
    pillar_ids: list[UUID] = Field(default_factory=list)
    options: list[QuestionOptionRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class QuestionCardCreate(BaseModel):
    code: str = Field(..., min_length=2, max_length=80, pattern=r"^[a-z0-9_-]+$")
    title: str = Field(..., min_length=2, max_length=200)
    description: str | None = None
    category: str = Field(default="reflection", max_length=100)
    is_active: bool = True
    display_order: int = 0


class QuestionCardUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=200)
    description: str | None = None
    category: str | None = Field(default=None, max_length=100)
    is_active: bool | None = None
    display_order: int | None = None


class QuestionCardRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    title: str
    description: str | None = None
    category: str
    is_active: bool
    display_order: int
    questions: list[QuestionRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class QuestionnaireSectionIn(BaseModel):
    code: str = Field(..., min_length=1, max_length=40)
    title: str = Field(..., min_length=2, max_length=200)
    description: str | None = None
    display_order: int = 0
    question_ids: list[UUID] = Field(default_factory=list)


class QuestionnaireQuestionLinkIn(BaseModel):
    question_id: UUID
    section_code: str | None = None
    is_required_override: bool | None = None
    display_order: int = 0


class QuestionnaireCreate(BaseModel):
    code: str = Field(..., min_length=2, max_length=100, pattern=r"^[a-z0-9_-]+$")
    title: str = Field(..., min_length=2, max_length=240)
    description: str | None = None
    event_id: UUID | None = None
    questionnaire_type: QuestionnaireType = QuestionnaireType.POST_EVENT
    assessment_stage: str | None = Field(default=None, max_length=40)
    version: str = Field(default="1.0", max_length=32)
    sections: list[QuestionnaireSectionIn] = Field(default_factory=list)
    questions: list[QuestionnaireQuestionLinkIn] = Field(default_factory=list)


class QuestionnaireUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=240)
    description: str | None = None
    event_id: UUID | None = None
    questionnaire_type: QuestionnaireType | None = None
    assessment_stage: str | None = Field(default=None, max_length=40)
    version: str | None = Field(default=None, max_length=32)
    status: QuestionnaireStatus | None = None
    sections: list[QuestionnaireSectionIn] | None = None
    questions: list[QuestionnaireQuestionLinkIn] | None = None


class QuestionnaireQuestionRead(BaseModel):
    id: UUID
    section_id: UUID | None = None
    question_id: UUID
    is_required_override: bool | None = None
    display_order: int
    question: QuestionRead


class QuestionnaireSectionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    title: str
    description: str | None = None
    display_order: int


class QuestionnaireRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    event_id: UUID | None = None
    code: str
    title: str
    description: str | None = None
    questionnaire_type: str
    assessment_stage: str | None = None
    version: str
    status: str
    published_at: datetime | None = None
    sections: list[QuestionnaireSectionRead] = Field(default_factory=list)
    questions: list[QuestionnaireQuestionRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class AssessmentResponseIn(BaseModel):
    question_id: UUID
    response_text: str | None = None
    response_numeric: float | None = None
    response_boolean: bool | None = None
    response_date: date | None = None
    response_json: Any | None = None
    explanation_text: str | None = None


class ParticipantProfilePatch(BaseModel):
    """Optional Section A background details submitted alongside an assessment."""

    current_role: str | None = Field(default=None, max_length=160)
    industry: str | None = Field(default=None, max_length=160)
    organisation: str | None = Field(default=None, max_length=200)
    years_of_experience: int | None = Field(default=None, ge=0, le=80)
    reason_for_attending: str | None = None
    consent_given: bool | None = None


class AssessmentSubmitRequest(BaseModel):
    participant_id: UUID | None = None
    phone: str | None = None
    email: str | None = None
    event_id: UUID
    questionnaire_id: UUID
    submission_channel: str = Field(default="web_api", max_length=40)
    started_at: datetime | None = None
    profile_updates: ParticipantProfilePatch | None = None
    responses: list[AssessmentResponseIn] = Field(default_factory=list)
    metadata_json: dict[str, Any] | None = None

    @model_validator(mode="after")
    def require_participant_identifier(self) -> "AssessmentSubmitRequest":
        if not self.participant_id and not self.phone and not self.email:
            raise ValueError(
                "Provide participant_id, phone, or email to associate the assessment."
            )
        return self


class AssessmentResponseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    question_id: UUID
    response_text: str | None = None
    response_numeric: float | None = None
    response_boolean: bool | None = None
    response_date: date | None = None
    response_json: Any | None = None
    explanation_text: str | None = None
    answered_at: datetime


class AssessmentSubmissionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    participant_id: UUID
    event_id: UUID
    questionnaire_id: UUID
    submission_channel: str
    status: str
    started_at: datetime | None = None
    submitted_at: datetime
    completeness_ratio: float
    responses: list[AssessmentResponseRead] = Field(default_factory=list)
    created_at: datetime


class AssessmentSummaryRead(BaseModel):
    id: UUID
    participant_id: UUID
    participant_name: str
    participant_email: str | None = None
    participant_phone: str | None = None
    event_id: UUID
    event_title: str
    questionnaire_id: UUID
    questionnaire_title: str
    questionnaire_type: str
    submission_channel: str
    status: str
    started_at: datetime | None = None
    submitted_at: datetime
    completeness_ratio: float
    responses_count: int
    created_at: datetime


class FeedbackResponseRead(BaseModel):
    response_id: UUID
    submission_id: UUID
    submitted_at: datetime
    answered_at: datetime
    event_id: UUID
    event_title: str
    questionnaire_id: UUID
    questionnaire_title: str
    participant_id: UUID
    participant_name: str
    participant_industry: str | None = None
    participant_role: str | None = None
    question_id: UUID
    question_code: str
    question_text: str
    question_type: str
    is_scorable: bool
    card_id: UUID | None = None
    section_code: str | None = None
    section_title: str | None = None
    pillar_ids: list[UUID] = Field(default_factory=list)
    response_text: str | None = None
    response_numeric: float | None = None
    response_boolean: bool | None = None
    response_date: date | None = None
    response_json: Any | None = None
    explanation_text: str | None = None
