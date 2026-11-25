"""Domain enumerations shared across models, schemas, and services."""

from enum import StrEnum


class EventStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ACTIVE = "active"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class RegistrationSource(StrEnum):
    FORM = "form"
    WHATSAPP = "whatsapp"
    MANUAL = "manual"
    IMPORT = "import"


class RegistrationStatus(StrEnum):
    REGISTERED = "registered"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    WAITLISTED = "waitlisted"


class AttendanceStatus(StrEnum):
    CONFIRMED = "confirmed"
    PARTIAL = "partial"
    ABSENT = "absent"
    UNVERIFIED = "unverified"


class QuestionType(StrEnum):
    SHORT_TEXT = "short_text"
    LONG_TEXT = "long_text"
    EMAIL = "email"
    PHONE = "phone"
    SINGLE_CHOICE = "single_choice"
    MULTIPLE_CHOICE = "multiple_choice"
    YES_NO = "yes_no"
    RATING_SCALE = "rating_scale"
    NUMERIC = "numeric"
    DATE = "date"


class QuestionnaireType(StrEnum):
    POST_EVENT = "post_event"
    FOLLOW_UP = "follow_up"
    REFLECTION = "reflection"
    CUSTOM = "custom"


class QuestionnaireStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class SubmissionStatus(StrEnum):
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    VALIDATED = "validated"


class ImpactCategory(StrEnum):
    IMMEDIATE = "immediate"
    APPLICATION = "application"
    SUSTAINED = "sustained"


class ScoringRuleType(StrEnum):
    RATING_SCALE = "rating_scale"
    YES_NO = "yes_no"
    SINGLE_CHOICE = "single_choice"
    MULTIPLE_CHOICE = "multiple_choice"
    NUMERIC_THRESHOLD = "numeric_threshold"
    VALUE_MAP = "value_map"


class ScoreStatus(StrEnum):
    CALCULATED = "calculated"
    PARTIAL = "partial"
    INSUFFICIENT_DATA = "insufficient_data"
    MISSING = "missing"


class ScoreScope(StrEnum):
    IMMEDIATE = "immediate"
    FOLLOW_UP = "follow_up"
    COMBINED = "combined"


class FollowUpStatus(StrEnum):
    SCHEDULED = "scheduled"
    PENDING = "pending"
    COMPLETED = "completed"
    OVERDUE = "overdue"
    SKIPPED = "skipped"


class EvidenceClassification(StrEnum):
    SELF_REPORTED = "self_reported"
    DOCUMENTED = "documented"
    VERIFIED = "verified"


class VerificationStatus(StrEnum):
    UNVERIFIED = "unverified"
    PENDING_REVIEW = "pending_review"
    VERIFIED = "verified"
    REJECTED = "rejected"


class ActionStatus(StrEnum):
    INTENDED = "intended"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class ActionCategory(StrEnum):
    IDEA_IMPLEMENTATION = "idea_implementation"
    HABIT_CHANGE = "habit_change"
    KNOWLEDGE_SHARING = "knowledge_sharing"
    WORKPLACE_IMPROVEMENT = "workplace_improvement"
    CAREER_GOAL = "career_goal"


class ConnectionType(StrEnum):
    PEER = "peer"
    SPEAKER = "speaker"
    MENTOR = "mentor"
    MENTEE = "mentee"
    COLLABORATOR = "collaborator"
    OPPORTUNITY = "opportunity"


class OutcomeType(StrEnum):
    PRODUCTIVITY_GAIN = "productivity_gain"
    COLLABORATION = "collaboration"
    MENTORSHIP = "mentorship"
    CAREER_ADVANCEMENT = "career_advancement"
    WORKPLACE_POLICY = "workplace_policy"
    KNOWLEDGE_TRANSFER = "knowledge_transfer"
    OTHER = "other"


class AdminRole(StrEnum):
    SUPER_ADMIN = "super_admin"
    EVENT_ADMIN = "event_admin"
    ANALYST = "analyst"
    AUDITOR = "auditor"


class ExportFormat(StrEnum):
    JSON = "json"
    CSV = "csv"
    XLSX = "xlsx"
