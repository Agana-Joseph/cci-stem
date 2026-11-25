# REST API Documentation (`/api/v1/`)

Interactive OpenAPI 3.1 / Swagger documentation is automatically served at `/docs` and `/redoc`.

## Response & Error Envelope

All successful responses return:
```json
{
  "success": true,
  "data": { ... },
  "meta": { "total": 10 },
  "request_id": "uuid"
}
```

All error responses (`400`, `401`, `403`, `404`, `409`, `422`, `429`, `500`) return:
```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Human-readable description",
    "details": null
  },
  "request_id": "uuid"
}
```

## Permissions Model

- **Public**: Safe read-only metadata (`GET /events`, `GET /pillars`, `GET /question-cards`, `GET /questions`, `GET /questionnaires`), generic non-enumerating lookup (`GET /participants/lookup`), and participant assessment/follow-up submissions (`POST /assessments/submit`, `POST /follow-ups/{id}/submit`).
- **Admin (`X-API-Key` header required)**: All PII access, participant management/import, event rosters, question/framework mutations, scoring calculations, analytics, outcome verification, and report exports.

## Endpoint Reference

### Participants
| Method | Endpoint | Permission | Purpose |
|---|---|---|---|
| `POST` | `/api/v1/participants` | Admin | Create participant (normalises phone to E.164 & email to lowercase; rejects duplicates with `409`) |
| `GET` | `/api/v1/participants/lookup` | Public / Admin | Public: generic non-enumerating OTP-ready response. Admin: audited match by phone (preferred) or email |
| `GET` | `/api/v1/participants/{participant_id}` | Admin | Retrieve participant profile |
| `PATCH` | `/api/v1/participants/{participant_id}` | Admin | Partially update participant profile or contact info |
| `POST` | `/api/v1/participants/import` | Admin | Upload CSV or Excel (`.xlsx`) file; `dry_run=true` returns validation & duplicate error report before commit |
| `GET` | `/api/v1/participants/{participant_id}/impact` | Admin | Holistic participant impact summary (scores, actions, connections, outcomes, follow-ups) |

### Events
| Method | Endpoint | Permission | Purpose |
|---|---|---|---|
| `POST` | `/api/v1/events` | Admin | Create event |
| `GET` | `/api/v1/events` | Public | List events with pagination (`limit`, `offset`, `status`) |
| `GET` | `/api/v1/events/{event_id}` | Public | Get single event |
| `PATCH` | `/api/v1/events/{event_id}` | Admin | Update event metadata or status |
| `GET` | `/api/v1/events/{event_id}/participants` | Admin | List registered participants & attendance status |
| `POST` | `/api/v1/events/{event_id}/registrations` | Admin | Register existing participant for an event |
| `POST` | `/api/v1/events/{event_id}/attendance` | Admin | Record or update attendance status |

### Question Cards, Questions & Questionnaires
| Method | Endpoint | Permission | Purpose |
|---|---|---|---|
| `POST` | `/api/v1/question-cards` | Admin | Create question card |
| `GET` | `/api/v1/question-cards` | Public | List question cards with active questions |
| `GET` | `/api/v1/question-cards/{card_id}` | Public | Get question card |
| `PATCH` | `/api/v1/question-cards/{card_id}` | Admin | Update question card |
| `POST` | `/api/v1/question-cards/{card_id}/questions` | Admin | Add question to card |
| `POST` | `/api/v1/questions` | Admin | Create question (8 types, options, multi-pillar mapping, `is_scorable`) |
| `GET` | `/api/v1/questions` | Public | List/filter questions (`card_id`, `pillar_id`, `question_type`, `is_scorable`) |
| `GET` | `/api/v1/questions/{question_id}` | Public | Get question |
| `PATCH` | `/api/v1/questions/{question_id}` | Admin | Update question |
| `PATCH` | `/api/v1/questions/{question_id}/archive` | Admin | Soft-archive question |
| `POST` | `/api/v1/questionnaires` | Admin | Create questionnaire with sections (e.g., Sections A–F) |
| `GET` | `/api/v1/questionnaires` | Public | List questionnaires |
| `GET` | `/api/v1/questionnaires/{questionnaire_id}` | Public | Get questionnaire structure |
| `PATCH` | `/api/v1/questionnaires/{questionnaire_id}` | Admin | Update questionnaire |
| `POST` | `/api/v1/questionnaires/{questionnaire_id}/publish` | Admin | Publish questionnaire for submissions |

### Assessments
| Method | Endpoint | Permission | Purpose |
|---|---|---|---|
| `POST` | `/api/v1/assessments/submit` | Public / Admin | Submit assessment linked via `participant_id`, `phone`, or `email` |
| `GET` | `/api/v1/assessments/{assessment_id}` | Admin | Retrieve assessment submission and responses |
| `GET` | `/api/v1/participants/{participant_id}/assessments` | Admin | List all assessments for a participant |

### Scoring
| Method | Endpoint | Permission | Purpose |
|---|---|---|---|
| `GET` | `/api/v1/pillars` | Public | List the six configurable measurement pillars |
| `GET` | `/api/v1/scoring/frameworks` | Admin | List scoring framework versions |
| `POST` | `/api/v1/scoring/frameworks` | Admin | Create versioned scoring framework (weights must sum to `1.0`) |
| `PATCH` | `/api/v1/scoring/frameworks/{framework_id}` | Admin | Update framework weights, thresholds, or rules |
| `POST` | `/api/v1/scoring/calculate/{participant_id}` | Admin | Calculate/recalculate participant score (preserves history) |
| `POST` | `/api/v1/scoring/calculate-event/{event_id}` | Admin | Bulk calculate scores for all participants in an event |
| `GET` | `/api/v1/scoring/participants/{participant_id}` | Admin | Get participant score history |
| `GET` | `/api/v1/scoring/events/{event_id}` | Admin | Get latest or historical event scores |

### Follow-Ups & Impact Tracking
| Method | Endpoint | Permission | Purpose |
|---|---|---|---|
| `POST` | `/api/v1/follow-ups/stages` | Admin | Add custom follow-up stage (e.g., `180_day`) |
| `GET` | `/api/v1/follow-ups/stages` | Public | List configured follow-up stages |
| `POST` | `/api/v1/follow-ups` | Admin | Schedule 30/60/90-day (or specific) follow-ups |
| `GET` | `/api/v1/follow-ups` | Admin | List follow-up schedules |
| `POST` | `/api/v1/follow-ups/{follow_up_id}/submit` | Public / Admin | Submit follow-up responses, actions & outcomes |
| `GET` | `/api/v1/participants/{participant_id}/follow-ups` | Admin | Get participant longitudinal follow-up timeline |
| `POST` | `/api/v1/impact/actions` | Public / Admin | Record intended, in-progress, or completed action |
| `PATCH` | `/api/v1/impact/actions/{action_id}` | Admin | Update action status or evidence |
| `POST` | `/api/v1/impact/connections` | Public / Admin | Record networking connection, collaboration, or mentorship |
| `POST` | `/api/v1/impact/outcomes` | Public / Admin | Record outcome (defaults to `self_reported` without evidence) |
| `POST` | `/api/v1/impact/outcomes/{outcome_id}/evidence` | Public / Admin | Attach supporting evidence (promotes to `documented`) |
| `PATCH` | `/api/v1/impact/outcomes/{outcome_id}/verify` | Admin | Independently verify or reject outcome (`verified`) |

### Analytics & Reporting
| Method | Endpoint | Permission | Purpose |
|---|---|---|---|
| `GET` | `/api/v1/analytics/events/{event_id}/overview` | Admin | Event overview KPIs + data coverage |
| `GET` | `/api/v1/analytics/events/{event_id}/pillars` | Admin | Six-pillar aggregate statistics + sample counts |
| `GET` | `/api/v1/analytics/events/{event_id}/networking` | Admin | Networking & collaboration outcomes |
| `GET` | `/api/v1/analytics/events/{event_id}/application` | Admin | Intended vs. completed actions & outcome evidence ratios |
| `GET` | `/api/v1/analytics/events/{event_id}/follow-ups` | Admin | 30/60/90-day cohort comparison |
| `GET` | `/api/v1/reports/events/{event_id}` | Admin | Full structured event impact report |
| `GET` | `/api/v1/reports/participants/{participant_id}` | Admin | Full structured participant impact dossier |
| `POST` | `/api/v1/reports/events/{event_id}/export` | Admin | Export event report as JSON, CSV, or XLSX |
| `POST` | `/api/v1/reports/participants/{participant_id}/export` | Admin | Export participant report as JSON, CSV, or XLSX |
