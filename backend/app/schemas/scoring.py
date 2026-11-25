"""Pydantic schemas for Measurement Pillars, Scoring Frameworks, Rules, and Score Results."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.enums import ImpactCategory, ScoringRuleType


class MeasurementPillarRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    description: str | None = None
    impact_category: str
    default_weight: float
    display_order: int
    is_active: bool


class ScoringDimensionIn(BaseModel):
    pillar_id: UUID
    weight: float = Field(..., gt=0.0, le=1.0)
    impact_category: ImpactCategory = ImpactCategory.IMMEDIATE
    min_questions_required: int = Field(default=1, ge=1)


class ScoringRuleIn(BaseModel):
    pillar_id: UUID
    question_id: UUID
    rule_type: ScoringRuleType
    rule_config: dict[str, Any] = Field(default_factory=dict)
    question_weight: float = Field(default=1.0, gt=0.0)
    is_active: bool = True


class ScoringFrameworkCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=160)
    version: str = Field(..., min_length=1, max_length=32)
    description: str | None = None
    is_active: bool = True
    min_questions_per_pillar: int = Field(default=1, ge=1)
    min_pillars_required: int = Field(default=2, ge=1)
    min_completeness_ratio: float = Field(default=0.25, ge=0.0, le=1.0)
    dimensions: list[ScoringDimensionIn] = Field(..., min_length=1)
    rules: list[ScoringRuleIn] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_weights_sum_to_one(self) -> "ScoringFrameworkCreate":
        total = sum(d.weight for d in self.dimensions)
        if abs(total - 1.0) > 0.005:
            raise ValueError(
                f"Configured dimension weights must sum to 1.0 (got {total:.4f})."
            )
        return self


class ScoringFrameworkUpdate(BaseModel):
    description: str | None = None
    is_active: bool | None = None
    min_questions_per_pillar: int | None = Field(default=None, ge=1)
    min_pillars_required: int | None = Field(default=None, ge=1)
    min_completeness_ratio: float | None = Field(default=None, ge=0.0, le=1.0)
    dimensions: list[ScoringDimensionIn] | None = None
    rules: list[ScoringRuleIn] | None = None

    @model_validator(mode="after")
    def validate_weights_if_provided(self) -> "ScoringFrameworkUpdate":
        if self.dimensions is not None:
            total = sum(d.weight for d in self.dimensions)
            if abs(total - 1.0) > 0.005:
                raise ValueError(
                    f"Configured dimension weights must sum to 1.0 (got {total:.4f})."
                )
        return self


class ScoringDimensionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    pillar_id: UUID
    pillar_code: str | None = None
    pillar_name: str | None = None
    weight: float
    impact_category: str
    min_questions_required: int


class ScoringRuleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    dimension_id: UUID
    question_id: UUID
    rule_type: str
    rule_config: dict[str, Any]
    question_weight: float
    is_active: bool


class ScoringFrameworkRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    version: str
    description: str | None = None
    is_active: bool
    min_questions_per_pillar: int
    min_pillars_required: int
    min_completeness_ratio: float
    effective_from: datetime
    effective_to: datetime | None = None
    dimensions: list[ScoringDimensionRead] = Field(default_factory=list)
    rules: list[ScoringRuleRead] = Field(default_factory=list)
    created_at: datetime


class CalculateParticipantScoreRequest(BaseModel):
    event_id: UUID
    framework_id: UUID | None = None
    assessment_submission_id: UUID | None = None


class CalculateEventScoresRequest(BaseModel):
    framework_id: UUID | None = None


class ParticipantDimensionScoreRead(BaseModel):
    id: UUID
    dimension_id: UUID
    pillar_id: UUID
    pillar_code: str
    pillar_name: str
    raw_score: float | None = None
    normalised_score: float | None = None
    configured_weight: float
    effective_weight: float | None = None
    questions_answered: int
    questions_total: int
    completeness_ratio: float
    status: str


class ParticipantImpactScoreRead(BaseModel):
    id: UUID
    participant_id: UUID
    event_id: UUID
    framework_id: UUID
    framework_version: str
    assessment_submission_id: UUID | None = None
    score_scope: str
    status: str
    overall_impact_score: float | None = None
    immediate_impact_score: float | None = None
    post_event_application_score: float | None = None
    sustained_impact_score: float | None = None
    completeness_ratio: float
    covered_pillars_count: int
    total_pillars_count: int
    weight_renormalised: bool
    is_latest: bool
    calculated_at: datetime
    calculation_metadata: dict[str, Any] | None = None
    dimension_scores: list[ParticipantDimensionScoreRead] = Field(default_factory=list)


class EventBulkCalculationResult(BaseModel):
    event_id: UUID
    framework_id: UUID
    framework_version: str
    participants_processed: int
    calculated_count: int
    partial_count: int
    insufficient_data_count: int
    scores: list[ParticipantImpactScoreRead] = Field(default_factory=list)
