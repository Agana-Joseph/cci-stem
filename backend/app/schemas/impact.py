"""Pydantic schemas for Follow-Ups, Actions, Professional Connections, Outcomes, and Evidence."""

from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import (
    ActionCategory,
    ActionStatus,
    ConnectionType,
    EvidenceClassification,
    FollowUpStatus,
    OutcomeType,
    VerificationStatus,
)


class FollowUpStageConfigCreate(BaseModel):
    event_id: UUID | None = None
    stage_code: str = Field(..., min_length=2, max_length=40, pattern=r"^[a-z0-9_-]+$")
    stage_name: str = Field(..., min_length=2, max_length=120)
    days_after_event: int = Field(..., ge=0, le=3650)
    questionnaire_id: UUID | None = None
    display_order: int = 0


class FollowUpStageConfigRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    event_id: UUID | None = None
    stage_code: str
    stage_name: str
    days_after_event: int
    questionnaire_id: UUID | None = None
    display_order: int
    is_active: bool


class FollowUpScheduleCreate(BaseModel):
    participant_id: UUID
    event_id: UUID
    follow_up_stage: str | None = Field(
        default=None,
        description="Specific stage code (e.g. '30_day'). If omitted, schedules all active stages (30/60/90-day).",
    )
    due_date: date | None = None
    status: FollowUpStatus = FollowUpStatus.PENDING


class ReportedActionIn(BaseModel):
    action_category: ActionCategory = ActionCategory.IDEA_IMPLEMENTATION
    title: str = Field(..., min_length=2, max_length=240)
    description: str | None = None
    action_status: ActionStatus = ActionStatus.INTENDED
    target_date: date | None = None
    evidence_classification: EvidenceClassification = EvidenceClassification.SELF_REPORTED


class OutcomeEvidenceIn(BaseModel):
    evidence_type: str = Field(..., min_length=2, max_length=60)
    description: str | None = None
    reference_url: str | None = Field(default=None, max_length=500)


class FollowUpSubmitRequest(BaseModel):
    assessment_date: date | None = None
    assessment_submission_id: UUID | None = None
    responses: dict[str, Any] = Field(default_factory=dict)
    reported_actions: list[ReportedActionIn] = Field(default_factory=list)
    outcome_descriptions: str | None = None
    outcome_type: OutcomeType = OutcomeType.OTHER
    evidence_items: list[OutcomeEvidenceIn] = Field(default_factory=list)
    evidence_classification: EvidenceClassification | None = None


class FollowUpSubmissionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    follow_up_schedule_id: UUID
    participant_id: UUID
    event_id: UUID
    follow_up_stage: str
    assessment_submission_id: UUID | None = None
    assessment_date: date
    responses_json: dict[str, Any]
    reported_actions_json: list[dict[str, Any]]
    outcome_descriptions: str | None = None
    evidence_classification: str
    verification_status: str
    verified_by: str | None = None
    verified_at: datetime | None = None
    submitted_at: datetime


class FollowUpScheduleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    participant_id: UUID
    event_id: UUID
    stage_config_id: UUID | None = None
    follow_up_stage: str
    due_date: date
    status: str
    completed_at: datetime | None = None
    reminder_count: int
    submissions: list[FollowUpSubmissionRead] = Field(default_factory=list)
    created_at: datetime


class ParticipantActionCreate(BaseModel):
    participant_id: UUID
    event_id: UUID
    follow_up_submission_id: UUID | None = None
    action_category: ActionCategory = ActionCategory.IDEA_IMPLEMENTATION
    title: str = Field(..., min_length=2, max_length=240)
    description: str | None = None
    action_status: ActionStatus = ActionStatus.INTENDED
    target_date: date | None = None
    evidence_classification: EvidenceClassification = EvidenceClassification.SELF_REPORTED


class ParticipantActionUpdate(BaseModel):
    action_status: ActionStatus | None = None
    description: str | None = None
    target_date: date | None = None
    evidence_classification: EvidenceClassification | None = None


class ParticipantActionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    participant_id: UUID
    event_id: UUID
    follow_up_submission_id: UUID | None = None
    action_category: str
    title: str
    description: str | None = None
    action_status: str
    target_date: date | None = None
    completed_at: datetime | None = None
    evidence_classification: str
    created_at: datetime


class ParticipantActionListItem(ParticipantActionRead):
    participant_name: str


class ProfessionalConnectionCreate(BaseModel):
    participant_id: UUID
    event_id: UUID
    connected_participant_id: UUID | None = None
    contact_name: str | None = Field(default=None, max_length=200)
    contact_role: str | None = Field(default=None, max_length=160)
    connection_type: ConnectionType = ConnectionType.PEER
    follow_up_occurred: bool = False
    collaboration_started: bool = False
    opportunity_discovered: bool = False
    notes: str | None = None
    evidence_classification: EvidenceClassification = EvidenceClassification.SELF_REPORTED


class ProfessionalConnectionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    participant_id: UUID
    event_id: UUID
    connected_participant_id: UUID | None = None
    contact_name: str | None = None
    contact_role: str | None = None
    connection_type: str
    follow_up_occurred: bool
    collaboration_started: bool
    opportunity_discovered: bool
    notes: str | None = None
    evidence_classification: str
    created_at: datetime


class ProfessionalConnectionListItem(ProfessionalConnectionRead):
    participant_name: str


class ImpactOutcomeCreate(BaseModel):
    participant_id: UUID
    event_id: UUID
    follow_up_submission_id: UUID | None = None
    action_id: UUID | None = None
    outcome_type: OutcomeType = OutcomeType.OTHER
    title: str = Field(..., min_length=2, max_length=240)
    description: str | None = None
    observed_at: date | None = None
    evidence_items: list[OutcomeEvidenceIn] = Field(default_factory=list)


class OutcomeEvidenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    outcome_id: UUID
    evidence_type: str
    description: str | None = None
    reference_url: str | None = None
    submitted_by: str | None = None
    verified_by: str | None = None
    verified_at: datetime | None = None
    verification_notes: str | None = None


class OutcomeVerifyRequest(BaseModel):
    verification_status: VerificationStatus
    verification_notes: str | None = None


class ImpactOutcomeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    participant_id: UUID
    event_id: UUID
    follow_up_submission_id: UUID | None = None
    action_id: UUID | None = None
    outcome_type: str
    title: str
    description: str | None = None
    evidence_classification: str
    verification_status: str
    observed_at: date | None = None
    evidence_items: list[OutcomeEvidenceRead] = Field(default_factory=list)
    created_at: datetime


class ImpactOutcomeListItem(ImpactOutcomeRead):
    participant_name: str


class ParticipantImpactSummary(BaseModel):
    participant_id: UUID
    event_id: UUID | None = None
    latest_scores: list[dict[str, Any]]
    actions_summary: dict[str, int]
    connections_summary: dict[str, int]
    outcomes_by_evidence: dict[str, int]
    follow_up_progress: list[dict[str, Any]]
