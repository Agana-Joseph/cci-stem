"""Model registry — importing this module registers all 30 ORM tables with Base.metadata."""

from app.models.admin import (
    AdministratorRecord,
    AuditLog,
    NotificationRecord,
    ReportRecord,
)
from app.models.impact import (
    FollowUpSchedule,
    FollowUpStageConfig,
    FollowUpSubmission,
    ImpactOutcome,
    OutcomeEvidence,
    ParticipantAction,
    ProfessionalConnection,
)
from app.models.participant import (
    AttendanceRecord,
    Event,
    EventRegistration,
    Participant,
)
from app.models.questionnaire import (
    AssessmentResponse,
    AssessmentSubmission,
    Question,
    QuestionCard,
    Questionnaire,
    QuestionnaireQuestion,
    QuestionnaireSection,
    QuestionOption,
    QuestionPillarMapping,
)
from app.models.scoring import (
    MeasurementPillar,
    ParticipantDimensionScore,
    ParticipantImpactScore,
    ScoringDimension,
    ScoringFramework,
    ScoringRule,
)

__all__ = [
    "Participant",
    "Event",
    "EventRegistration",
    "AttendanceRecord",
    "QuestionCard",
    "Question",
    "QuestionPillarMapping",
    "QuestionOption",
    "Questionnaire",
    "QuestionnaireSection",
    "QuestionnaireQuestion",
    "AssessmentSubmission",
    "AssessmentResponse",
    "MeasurementPillar",
    "ScoringFramework",
    "ScoringDimension",
    "ScoringRule",
    "ParticipantImpactScore",
    "ParticipantDimensionScore",
    "FollowUpStageConfig",
    "FollowUpSchedule",
    "FollowUpSubmission",
    "ProfessionalConnection",
    "ParticipantAction",
    "ImpactOutcome",
    "OutcomeEvidence",
    "AdministratorRecord",
    "AuditLog",
    "NotificationRecord",
    "ReportRecord",
]
