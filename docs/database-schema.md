# Database Schema — CCI STEM Connect (PostgreSQL)

All 30 tables use `UUID` primary keys, UTC timezone-aware timestamps (`created_at`, `updated_at`), foreign-key constraints with explicit `ON DELETE` rules, and targeted indexes.

## Table Groups

### 1. Participant & Event Records
| Table | Purpose | Key Constraints & Indexes |
|---|---|---|
| `participants` | Core participant profile (no password/auth columns) | `CHECK (email_normalised IS NOT NULL OR phone_normalised IS NOT NULL)`, unique + indexed `phone_normalised`, unique + indexed `email_normalised` |
| `events` | Event catalog | Unique indexed `slug`, indexed `event_date` |
| `event_registrations` | Unique participant registration per event (allows repeat attendance across multiple events) | `UNIQUE (event_id, participant_id)`, indexed `event_id`, `participant_id` |
| `attendance_records` | Verified attendance status (`confirmed`, `partial`, `absent`, `unverified`) | `UNIQUE (event_id, participant_id)`, indexed `event_id`, `participant_id` |

### 2. Question & Assessment Management
| Table | Purpose | Key Constraints & Indexes |
|---|---|---|
| `question_cards` | Reflective or topical question card groupings | Unique indexed `code` |
| `questions` | Configurable question bank (8 types + `allow_explanation` + `is_scorable` + soft archive) | Unique indexed `code`, FK `card_id` |
| `question_pillar_mappings` | Many-to-many assignment of questions to one or more measurement pillars | `UNIQUE (question_id, pillar_id)` |
| `question_options` | Configurable choices with optional `score_value` | FK `question_id` |
| `questionnaires` | Versioned draft/published/archived assessment definitions | Unique indexed `code`, FK `event_id` |
| `questionnaire_sections` | Configurable assessment sections (e.g., Sections A–F) | `UNIQUE (questionnaire_id, code)` |
| `questionnaire_questions` | Ordered attachment of bank questions into questionnaire sections | `UNIQUE (questionnaire_id, question_id)` |
| `assessment_submissions` | Participant assessment submission header & completeness ratio | Indexed `participant_id`, `event_id`, `submitted_at` |
| `assessment_responses` | Typed response values (`text`, `numeric`, `boolean`, `date`, `json`) + `explanation_text` | `UNIQUE (submission_id, question_id)`, indexed `submission_id` |

### 3. Measurement & Scoring
| Table | Purpose | Key Constraints & Indexes |
|---|---|---|
| `measurement_pillars` | The 6 configurable measurement dimensions | Unique indexed `code` |
| `scoring_frameworks` | Versioned scoring framework configurations & sufficiency thresholds | `UNIQUE (name, version)` |
| `scoring_dimensions` | Pillar weights & impact category per framework version | `UNIQUE (framework_id, pillar_id)` |
| `scoring_rules` | Explicit question-to-dimension scoring mappings (`rating_scale`, `yes_no`, `single_choice`, `multiple_choice`, `numeric_threshold`, `value_map`) | `UNIQUE (framework_id, dimension_id, question_id)` |
| `participant_impact_scores` | Historical & latest composite + horizon-separated scores (`immediate`, `post_event_application`, `sustained`) | Indexed `participant_id`, `event_id`, `assessment_submission_id`, `calculated_at` |
| `participant_dimension_scores` | Per-pillar 0–100 score, configured vs. effective renormalised weight, completeness & status | Indexed `impact_score_id`, `participant_id`, `event_id` |

### 4. Networking & Longitudinal Impact Tracking
| Table | Purpose | Key Constraints & Indexes |
|---|---|---|
| `follow_up_stage_configs` | Configurable follow-up horizons (`30_day`, `60_day`, `90_day`, extensible) | `UNIQUE (event_id, stage_code)` |
| `follow_up_schedules` | Scheduled/pending/completed follow-up instances per participant & event | `UNIQUE (participant_id, event_id, follow_up_stage)`, indexed `follow_up_stage` |
| `follow_up_submissions` | Follow-up responses, reported actions, outcomes, evidence classification & verification status | Indexed `follow_up_schedule_id`, `participant_id`, `event_id`, `follow_up_stage`, `submitted_at` |
| `professional_connections` | Connections established, follow-ups, collaborations, and opportunities | Indexed `participant_id`, `event_id` |
| `participant_actions` | Actions explicitly separated by status (`intended`, `in_progress`, `completed`, `abandoned`) | Indexed `participant_id`, `event_id` |
| `impact_outcomes` | Tangible outcomes tagged with `evidence_classification` (`self_reported`, `documented`, `verified`) | Indexed `participant_id`, `event_id` |
| `outcome_evidence` | Supporting evidence artifacts and independent admin verification metadata | Indexed `outcome_id` |

### 5. Administration, Audit & Reporting
| Table | Purpose |
|---|---|
| `administrator_records` | Authorised admin identities and SHA-256 API key hashes |
| `audit_logs` | Immutable audit trail of admin mutations, imports, exports, and lookups |
| `notification_records` | Audit log for email/SMS/WhatsApp invitations, reminders, and future OTP challenges |
| `report_records` | Metadata and storage path of generated JSON/CSV/XLSX exports |
