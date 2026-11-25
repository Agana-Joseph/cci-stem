"""Follow-Ups, Professional Connections, Participant Actions, Impact Outcomes & Evidence models."""

from datetime import date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
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
    ActionCategory,
    ActionStatus,
    ConnectionType,
    EvidenceClassification,
    FollowUpStatus,
    OutcomeType,
    VerificationStatus,
)
from app.database.base import Base, JSONBType, TimestampMixin, UUIDPrimaryKeyMixin, utc_now


class FollowUpStageConfig(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Configurable follow-up stages (30_day, 60_day, 90_day, and future periods)."""

    __tablename__ = "follow_up_stage_configs"
    __table_args__ = (
        UniqueConstraint("event_id", "stage_code", name="uq_event_followup_stage"),
    )

    event_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"), nullable=True
    )
    stage_code: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    stage_name: Mapped[str] = mapped_column(String(120), nullable=False)
    days_after_event: Mapped[int] = mapped_column(Integer, nullable=False)
    questionnaire_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("questionnaires.id", ondelete="SET NULL"),
        nullable=True,
    )
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class FollowUpSchedule(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "follow_up_schedules"
    __table_args__ = (
        UniqueConstraint(
            "participant_id", "event_id", "follow_up_stage", name="uq_participant_event_stage"
        ),
        Index("ix_follow_up_schedules_participant_id", "participant_id"),
        Index("ix_follow_up_schedules_event_id", "event_id"),
        Index("ix_follow_up_schedules_stage", "follow_up_stage"),
    )

    participant_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("participants.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"), nullable=False
    )
    stage_config_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("follow_up_stage_configs.id", ondelete="SET NULL"),
        nullable=True,
    )
    follow_up_stage: Mapped[str] = mapped_column(String(40), nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), default=FollowUpStatus.SCHEDULED.value, nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    reminder_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    submissions: Mapped[list["FollowUpSubmission"]] = relationship(
        back_populates="schedule", cascade="all, delete-orphan"
    )


class FollowUpSubmission(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "follow_up_submissions"
    __table_args__ = (
        Index("ix_follow_up_submissions_schedule_id", "follow_up_schedule_id"),
        Index("ix_follow_up_submissions_participant_id", "participant_id"),
        Index("ix_follow_up_submissions_event_id", "event_id"),
        Index("ix_follow_up_submissions_stage", "follow_up_stage"),
        Index("ix_follow_up_submissions_submitted_at", "submitted_at"),
    )

    follow_up_schedule_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("follow_up_schedules.id", ondelete="CASCADE"),
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
    follow_up_stage: Mapped[str] = mapped_column(String(40), nullable=False)
    assessment_submission_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("assessment_submissions.id", ondelete="SET NULL"),
        nullable=True,
    )
    assessment_date: Mapped[date] = mapped_column(Date, nullable=False)
    responses_json: Mapped[dict[str, Any]] = mapped_column(
        JSONBType, default=dict, nullable=False
    )
    reported_actions_json: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONBType, default=list, nullable=False
    )
    outcome_descriptions: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_classification: Mapped[str] = mapped_column(
        String(32), default=EvidenceClassification.SELF_REPORTED.value, nullable=False
    )
    verification_status: Mapped[str] = mapped_column(
        String(32), default=VerificationStatus.UNVERIFIED.value, nullable=False
    )
    verified_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    schedule: Mapped["FollowUpSchedule"] = relationship(back_populates="submissions")


class ProfessionalConnection(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "professional_connections"
    __table_args__ = (
        Index("ix_professional_connections_participant_id", "participant_id"),
        Index("ix_professional_connections_event_id", "event_id"),
    )

    participant_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("participants.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"), nullable=False
    )
    connected_participant_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("participants.id", ondelete="SET NULL"),
        nullable=True,
    )
    contact_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    contact_role: Mapped[str | None] = mapped_column(String(160), nullable=True)
    connection_type: Mapped[str] = mapped_column(
        String(40), default=ConnectionType.PEER.value, nullable=False
    )
    follow_up_occurred: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    collaboration_started: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    opportunity_discovered: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_classification: Mapped[str] = mapped_column(
        String(32), default=EvidenceClassification.SELF_REPORTED.value, nullable=False
    )


class ParticipantAction(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Distinguishes intended actions from in-progress and completed workplace applications."""

    __tablename__ = "participant_actions"
    __table_args__ = (
        Index("ix_participant_actions_participant_id", "participant_id"),
        Index("ix_participant_actions_event_id", "event_id"),
    )

    participant_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("participants.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"), nullable=False
    )
    follow_up_submission_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("follow_up_submissions.id", ondelete="SET NULL"),
        nullable=True,
    )
    action_category: Mapped[str] = mapped_column(
        String(40), default=ActionCategory.IDEA_IMPLEMENTATION.value, nullable=False
    )
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    action_status: Mapped[str] = mapped_column(
        String(32), default=ActionStatus.INTENDED.value, nullable=False
    )
    target_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    evidence_classification: Mapped[str] = mapped_column(
        String(32), default=EvidenceClassification.SELF_REPORTED.value, nullable=False
    )


class ImpactOutcome(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "impact_outcomes"
    __table_args__ = (
        Index("ix_impact_outcomes_participant_id", "participant_id"),
        Index("ix_impact_outcomes_event_id", "event_id"),
    )

    participant_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("participants.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"), nullable=False
    )
    follow_up_submission_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("follow_up_submissions.id", ondelete="SET NULL"),
        nullable=True,
    )
    action_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("participant_actions.id", ondelete="SET NULL"),
        nullable=True,
    )
    outcome_type: Mapped[str] = mapped_column(
        String(40), default=OutcomeType.OTHER.value, nullable=False
    )
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_classification: Mapped[str] = mapped_column(
        String(32), default=EvidenceClassification.SELF_REPORTED.value, nullable=False
    )
    verification_status: Mapped[str] = mapped_column(
        String(32), default=VerificationStatus.UNVERIFIED.value, nullable=False
    )
    observed_at: Mapped[date | None] = mapped_column(Date, nullable=True)

    evidence_items: Mapped[list["OutcomeEvidence"]] = relationship(
        back_populates="outcome", cascade="all, delete-orphan"
    )


class OutcomeEvidence(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "outcome_evidence"
    __table_args__ = (Index("ix_outcome_evidence_outcome_id", "outcome_id"),)

    outcome_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("impact_outcomes.id", ondelete="CASCADE"),
        nullable=False,
    )
    evidence_type: Mapped[str] = mapped_column(String(60), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    reference_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    submitted_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    verified_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    verification_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    outcome: Mapped["ImpactOutcome"] = relationship(back_populates="evidence_items")
