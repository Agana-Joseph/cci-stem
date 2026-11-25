"""Measurement Pillars, Configurable Scoring Frameworks, Rules, and Historical Scores models."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
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

from app.core.enums import ImpactCategory, ScoreScope, ScoreStatus
from app.database.base import Base, JSONBType, TimestampMixin, UUIDPrimaryKeyMixin, utc_now


class MeasurementPillar(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "measurement_pillars"

    code: Mapped[str] = mapped_column(String(80), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    impact_category: Mapped[str] = mapped_column(
        String(32), default=ImpactCategory.IMMEDIATE.value, nullable=False
    )
    default_weight: Mapped[float] = mapped_column(Float, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class ScoringFramework(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "scoring_frameworks"
    __table_args__ = (
        UniqueConstraint("name", "version", name="uq_scoring_framework_name_version"),
    )

    name: Mapped[str] = mapped_column(String(160), nullable=False)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    min_questions_per_pillar: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    min_pillars_required: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    min_completeness_ratio: Mapped[float] = mapped_column(Float, default=0.25, nullable=False)
    effective_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    effective_to: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    dimensions: Mapped[list["ScoringDimension"]] = relationship(
        back_populates="framework", cascade="all, delete-orphan"
    )
    rules: Mapped[list["ScoringRule"]] = relationship(
        back_populates="framework", cascade="all, delete-orphan"
    )


class ScoringDimension(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "scoring_dimensions"
    __table_args__ = (
        UniqueConstraint("framework_id", "pillar_id", name="uq_framework_pillar_dim"),
        Index("ix_scoring_dimensions_framework_id", "framework_id"),
    )

    framework_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("scoring_frameworks.id", ondelete="CASCADE"),
        nullable=False,
    )
    pillar_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("measurement_pillars.id", ondelete="RESTRICT"),
        nullable=False,
    )
    weight: Mapped[float] = mapped_column(Float, nullable=False)
    impact_category: Mapped[str] = mapped_column(
        String(32), default=ImpactCategory.IMMEDIATE.value, nullable=False
    )
    min_questions_required: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    framework: Mapped["ScoringFramework"] = relationship(back_populates="dimensions")
    pillar: Mapped["MeasurementPillar"] = relationship()
    rules: Mapped[list["ScoringRule"]] = relationship(
        back_populates="dimension", cascade="all, delete-orphan"
    )


class ScoringRule(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "scoring_rules"
    __table_args__ = (
        UniqueConstraint(
            "framework_id", "dimension_id", "question_id", name="uq_scoring_rule_q"
        ),
        Index("ix_scoring_rules_framework_id", "framework_id"),
        Index("ix_scoring_rules_question_id", "question_id"),
    )

    framework_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("scoring_frameworks.id", ondelete="CASCADE"),
        nullable=False,
    )
    dimension_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("scoring_dimensions.id", ondelete="CASCADE"),
        nullable=False,
    )
    question_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("questions.id", ondelete="CASCADE"),
        nullable=False,
    )
    rule_type: Mapped[str] = mapped_column(String(40), nullable=False)
    rule_config: Mapped[dict[str, Any]] = mapped_column(
        JSONBType, default=dict, nullable=False
    )
    question_weight: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    framework: Mapped["ScoringFramework"] = relationship(back_populates="rules")
    dimension: Mapped["ScoringDimension"] = relationship(back_populates="rules")


class ParticipantImpactScore(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Historical & current impact score record for a participant in an event."""

    __tablename__ = "participant_impact_scores"
    __table_args__ = (
        Index("ix_participant_impact_scores_participant_id", "participant_id"),
        Index("ix_participant_impact_scores_event_id", "event_id"),
        Index("ix_participant_impact_scores_submission_id", "assessment_submission_id"),
        Index("ix_participant_impact_scores_calculated_at", "calculated_at"),
    )

    participant_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("participants.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"), nullable=False
    )
    framework_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("scoring_frameworks.id", ondelete="RESTRICT"),
        nullable=False,
    )
    framework_version: Mapped[str] = mapped_column(String(32), nullable=False)
    assessment_submission_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("assessment_submissions.id", ondelete="SET NULL"),
        nullable=True,
    )
    score_scope: Mapped[str] = mapped_column(
        String(32), default=ScoreScope.COMBINED.value, nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(32), default=ScoreStatus.CALCULATED.value, nullable=False
    )
    overall_impact_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    immediate_impact_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    post_event_application_score: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    sustained_impact_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    completeness_ratio: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    covered_pillars_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_pillars_count: Mapped[int] = mapped_column(Integer, default=6, nullable=False)
    weight_renormalised: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_latest: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    calculation_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        JSONBType, nullable=True
    )

    dimension_scores: Mapped[list["ParticipantDimensionScore"]] = relationship(
        back_populates="impact_score", cascade="all, delete-orphan"
    )


class ParticipantDimensionScore(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "participant_dimension_scores"
    __table_args__ = (
        Index("ix_participant_dimension_scores_impact_score_id", "impact_score_id"),
        Index("ix_participant_dimension_scores_participant_id", "participant_id"),
        Index("ix_participant_dimension_scores_event_id", "event_id"),
    )

    impact_score_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("participant_impact_scores.id", ondelete="CASCADE"),
        nullable=False,
    )
    participant_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("participants.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"), nullable=False
    )
    dimension_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("scoring_dimensions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    pillar_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("measurement_pillars.id", ondelete="RESTRICT"),
        nullable=False,
    )
    raw_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    normalised_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    configured_weight: Mapped[float] = mapped_column(Float, nullable=False)
    effective_weight: Mapped[float | None] = mapped_column(Float, nullable=True)
    questions_answered: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    questions_total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completeness_ratio: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), default=ScoreStatus.CALCULATED.value, nullable=False
    )

    impact_score: Mapped["ParticipantImpactScore"] = relationship(
        back_populates="dimension_scores"
    )
    pillar: Mapped["MeasurementPillar"] = relationship()
