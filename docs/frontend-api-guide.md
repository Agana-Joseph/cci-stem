# CCI STEM Connect — Frontend API Integration Guide (v1.0)

Complete REST API specification for building the **Participant Web Portal** and **Admin Panel** (Next.js / React / TypeScript) against the CCI STEM Connect backend.

---

## 1. Base URL, OpenAPI Spec & CORS

| Environment | Base URL |
| --- | --- |
| **Production (Render)** | `https://<your-render-service>.onrender.com` |
| **Local Development** | `http://localhost:8000` |
| **API v1 Prefix** | `/api/v1` |
| **Interactive Swagger UI** | `<BASE_URL>/docs` |
| **ReDoc** | `<BASE_URL>/redoc` |
| **OpenAPI 3.1 JSON** | `<BASE_URL>/openapi.json` |

> **Tip (Auto-Generate TypeScript Types):** You can generate strongly typed TS definitions directly from the live backend:
> ```bash
> npx openapi-typescript https://<your-render-service>.onrender.com/openapi.json -o src/types/api.d.ts
> ```

### CORS Configuration
Add your frontend origin(s) to the `CORS_ALLOWED_ORIGINS` environment variable on Render (`cci-stem-api → Environment`), e.g.:
```text
https://cci-stem-web.onrender.com,http://localhost:3000
```
*(Accepts either a comma-separated list or a JSON array `["https://..."]`.)*

---

## 2. Authentication, Headers & Security Model

There are **no participant passwords or user accounts**. Participants are identified by their registered **phone number** (preferred — normalised to E.164, default region `NG`) or **email address** (normalised lowercase).

### Request Headers

| Header | Required For | Description |
| --- | --- | --- |
| `Content-Type` | JSON requests | `application/json` (omit for `multipart/form-data` file uploads) |
| `X-API-Key` | **Admin endpoints** | Administrative API key (`ADMIN_API_KEY` env var on Render or a provisioned admin key from `administrator_records`) |
| `X-Actor-Id` | Optional | Identifier for audit logs (e.g. admin email or user ID) |
| `X-Request-ID` | Optional | Client-generated correlation UUID (echoed back in response header & body) |

> **Security Warning for Next.js / Frontend Devs:**
> **NEVER** expose `ADMIN_API_KEY` in `NEXT_PUBLIC_*` variables or browser network requests.
> Proxy all `/admin` API calls through Next.js **Route Handlers (`app/api/admin/[...path]/route.ts`)** or **Server Actions** that read `process.env.ADMIN_API_KEY` on the server and verify an admin session cookie before forwarding `X-API-Key` to Render.

### Permission Tiers
- **Public**: Event/pillar/question/questionnaire reads, privacy-preserving participant lookup, assessment submission, follow-up submission, and logging actions/connections/outcomes/evidence.
- **Public / Admin (Dual Behaviour)**: `GET /api/v1/participants/lookup` returns a generic non-enumerating response for public callers, and full match metadata for admin callers.
- **Admin (`X-API-Key` required)**: Creating/editing/importing participants, event rosters & attendance, creating/editing/publishing questions & questionnaires, scoring frameworks & calculations, analytics, outcome verification, and report generation/exports.

---

## 3. Response Envelopes, Pagination, Errors & Rate Limits

### Standard Success Envelope
Every `2xx` response returns:
```json
{
  "success": true,
  "data": { ... },
  "meta": {
    "total": 42,
    "limit": 50,
    "offset": 0,
    "has_more": false
  },
  "request_id": "8e31d198-3e21-4091-b507-656713cf9391"
}
```
*Note: `meta` is `null` on single-resource responses, `{ "total": N }` on unpaginated lists, and `{ "total", "limit", "offset", "has_more" }` on paginated lists.*

### Standard Error Envelope
Every `4xx` / `5xx` response returns:
```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Human-readable error message",
    "details": null
  },
  "request_id": "8e31d198-3e21-4091-b507-656713cf9391"
}
```

### Error Codes & HTTP Statuses

| HTTP Status | `error.code` | When It Occurs |
| --- | --- | --- |
| `400` | `APPLICATION_ERROR` | Generic domain error |
| `401` | `UNAUTHORIZED` | Missing or invalid `X-API-Key` header |
| `403` | `FORBIDDEN` | Admin key lacks permission |
| `404` | `NOT_FOUND` | Resource UUID not found (or participant contact not registered on submit) |
| `409` | `CONFLICT` | Duplicate phone, email, event slug, question/card/questionnaire code, or duplicate event registration |
| `422` | `VALIDATION_ERROR` | Domain rule failure (e.g. missing required questions, invalid option, weights != 1.0, unpublished questionnaire) |
| `422` | `REQUEST_VALIDATION_ERROR` | Pydantic schema / type / query param validation error (`details` is an array of FastAPI field errors) |
| `429` | `RATE_LIMIT_EXCEEDED` | Rate limit exceeded (`details.retry_after_seconds` + `Retry-After` header) |
| `500` | `INTERNAL_SERVER_ERROR` | Unexpected server error |

### Rate Limits (Per IP, 60-Second Sliding Window)
All non-`/health` responses include `X-Request-ID` and `X-RateLimit-Remaining` headers.

| Endpoint Group | Default Limit |
| --- | --- |
| `GET /api/v1/participants/lookup` | `15 req / min` |
| `POST .../submit` (assessments & follow-ups) | `30 req / min` |
| All other endpoints | `120 req / min` |

---

## 4. Shared Enums (TypeScript Reference)

```ts
export type EventStatus = "draft" | "published" | "active" | "completed" | "archived";
export type RegistrationSource = "form" | "whatsapp" | "manual" | "import";
export type RegistrationStatus = "registered" | "confirmed" | "cancelled" | "waitlisted";
export type AttendanceStatus = "confirmed" | "partial" | "absent" | "unverified";

export type QuestionType =
  | "short_text"
  | "long_text"
  | "email"
  | "phone"
  | "single_choice"
  | "multiple_choice"
  | "yes_no"
  | "rating_scale"
  | "numeric"
  | "date";

export type QuestionnaireType = "post_event" | "follow_up" | "reflection" | "custom";
export type QuestionnaireStatus = "draft" | "published" | "archived";
export type SubmissionStatus = "in_progress" | "submitted" | "validated";

export type ImpactCategory = "immediate" | "application" | "sustained";
export type ScoringRuleType =
  | "rating_scale"
  | "yes_no"
  | "single_choice"
  | "multiple_choice"
  | "numeric_threshold"
  | "value_map";
export type ScoreStatus = "calculated" | "partial" | "insufficient_data" | "missing";
export type ScoreScope = "immediate" | "follow_up" | "combined";

export type FollowUpStatus = "scheduled" | "pending" | "completed" | "overdue" | "skipped";
export type EvidenceClassification = "self_reported" | "documented" | "verified";
export type VerificationStatus = "unverified" | "pending_review" | "verified" | "rejected";

export type ActionStatus = "intended" | "in_progress" | "completed" | "abandoned";
export type ActionCategory =
  | "idea_implementation"
  | "habit_change"
  | "knowledge_sharing"
  | "workplace_improvement"
  | "career_goal";

export type ConnectionType =
  | "peer"
  | "speaker"
  | "mentor"
  | "mentee"
  | "collaborator"
  | "opportunity";

export type OutcomeType =
  | "productivity_gain"
  | "collaboration"
  | "mentorship"
  | "career_advancement"
  | "workplace_policy"
  | "knowledge_transfer"
  | "other";

export type ExportFormat = "json" | "csv" | "xlsx";
```

---

## 5. Health Check

### `GET /health`
- **Access:** Public (exempt from rate limiting)
- **Status:** `200 OK`
- **Response `data`:**
```json
{
  "status": "healthy",
  "service": "CCI STEM Connect Impact Measurement API",
  "version": "1.0.0",
  "environment": "production"
}
```
> **Render Free-Tier Note:** The first request after 15 minutes of inactivity can take 30–50 seconds while the container wakes up. Call `/health` or handle initial cold-start timeouts gracefully in the frontend.

---

## 6. Events (`/api/v1/events`)

### 6.0 Get Default Published Event Bundle — `GET /api/v1/events/default`
- **Access:** Public
- **Status:** `200 OK`
- **Purpose:** Single bootstrap call for the participant-facing frontend — automatically retrieves the default published **CCI STEM Connect** event without manual event selection.
- **Response `data`:**
  - `event`: `EventRead` (includes `headline`, `introduction`, `event_category`, `status: "published"`, `is_default: true`, feature flags, and `objectives[]`)
  - `objectives`: `EventObjectiveRead[]` (7 ordered event objectives)
  - `measurement_pillars`: `MeasurementPillarRead[]` (6 pillars linked via `event_pillars`)
  - `question_categories`: `QuestionCategoryRead[]` (9 configured categories; also at `GET /api/v1/question-categories`)
  - `default_questionnaire`: `QuestionnaireRead` (`cci-stem-connect-initial-assessment` — Sections A–F, 35 questions + answer options)
  - `reflection_cards`: `QuestionCardRead[]` (3 original reflection cards with preserved wording)
  - `assessment_stages`: `FollowUpStageConfigRead[]` (4 stages: `immediate`, `30_day`, `60_day`, `90_day`)
  - `follow_up_questionnaires`: `QuestionnaireRead[]` (30-day, 60-day, and 90-day published questionnaires)
  - `active_framework`: Public summary `{ id, name, version, is_active, dimensions[] }`

### 6.1 List Events — `GET /api/v1/events`
- **Access:** Public
- **Query Params:**
  - `status` (`EventStatus`, optional) — filter by event status
  - `limit` (`int`, `1..200`, default `50`)
  - `offset` (`int`, `>= 0`, default `0`)
- **Response:** `200 OK`, `data: EventRead[]`, `meta: PaginationMeta`

### 6.2 Get Event — `GET /api/v1/events/{event_id}`
- **Access:** Public
- **Response:** `200 OK`, `data: EventRead`
```json
{
  "id": "b7c0f0e1-2d33-4a9b-8f12-1c2d3e4f5a6b",
  "slug": "cci-stem-lagos-2026",
  "title": "CCI STEM Connect Lagos 2026",
  "description": "Annual networking & knowledge-sharing summit",
  "event_type": "networking_and_knowledge_sharing",
  "event_date": "2026-11-24",
  "end_date": "2026-11-24",
  "location": "Lagos, Nigeria",
  "status": "active",
  "metadata_json": null,
  "created_at": "2026-11-24T10:00:00Z",
  "updated_at": "2026-11-24T10:00:00Z"
}
```

### 6.3 Create Event — `POST /api/v1/events`
- **Access:** Admin (`X-API-Key`)
- **Status:** `201 Created` (`409` if `slug` already exists)
- **Request Body (`EventCreate`):**
```json
{
  "slug": "cci-stem-lagos-2026",
  "title": "CCI STEM Connect Lagos 2026",
  "description": "Optional description",
  "event_type": "networking_and_knowledge_sharing",
  "event_date": "2026-11-24",
  "end_date": "2026-11-24",
  "location": "Lagos, Nigeria",
  "status": "active",
  "metadata_json": {}
}
```
*Validation:* `slug` required (`^[a-z0-9-]+$`, 2–120 chars), `title` required (2–240 chars), `event_date` required (`YYYY-MM-DD`).

### 6.4 Update Event — `PATCH /api/v1/events/{event_id}`
- **Access:** Admin (`X-API-Key`)
- **Request Body (`EventUpdate`):** Any subset of `title`, `description`, `event_type`, `event_date`, `end_date`, `location`, `status`, `metadata_json`.
- **Response:** `200 OK`, `data: EventRead`

### 6.5 List Event Roster — `GET /api/v1/events/{event_id}/participants`
- **Access:** Admin (`X-API-Key`)
- **Query Params:** `limit` (`1..500`, default `100`), `offset` (`>= 0`, default `0`)
- **Response:** `200 OK`, `data: EventParticipantSummary[]`, `meta: PaginationMeta`
```json
[
  {
    "participant_id": "2c8d1a10-...",
    "full_name": "Adaeze Okafor",
    "email_normalised": "adaeze@example.com",
    "phone_normalised": "+2348012345678",
    "current_role": "Senior Data Engineer",
    "industry": "FinTech",
    "organisation": "PayStack",
    "registration_status": "registered",
    "registration_source": "import",
    "attendance_status": "confirmed"
  }
]
```

### 6.6 Register Participant for Event — `POST /api/v1/events/{event_id}/registrations`
- **Access:** Admin (`X-API-Key`)
- **Status:** `201 Created` (`409` if already registered)
- **Request Body (`RegistrationCreate`):**
```json
{
  "participant_id": "2c8d1a10-...",
  "registration_source": "form",
  "registration_status": "registered",
  "reason_for_attending": "Networking and career growth"
}
```
- **Response `data` (`RegistrationRead`):** `{ id, event_id, participant_id, registration_source, registration_status, registered_at, reason_for_attending }`

### 6.7 Record / Update Attendance — `POST /api/v1/events/{event_id}/attendance`
- **Access:** Admin (`X-API-Key`)
- **Status:** `200 OK` (upserts attendance for `(event_id, participant_id)`)
- **Request Body (`AttendanceUpsert`):**
```json
{
  "participant_id": "2c8d1a10-...",
  "attendance_status": "confirmed",
  "check_in_at": "2026-11-24T09:15:00Z",
  "check_out_at": "2026-11-24T16:30:00Z",
  "verification_source": "qr_checkin",
  "notes": "Checked in at main desk"
}
```
- **Response `data` (`AttendanceRead`):** `{ id, event_id, participant_id, attendance_status, check_in_at, check_out_at, verification_source, notes }`

---

## 7. Participants (`/api/v1/participants`)

### 7.1 Create Participant — `POST /api/v1/participants`
- **Access:** Admin (`X-API-Key`)
- **Status:** `201 Created` (`409` if phone or email already exists)
- **Request Body (`ParticipantCreate`):**
```json
{
  "full_name": "Adaeze Okafor",
  "email": "adaeze@example.com",
  "phone": "08012345678",
  "current_role": "Senior Data Engineer",
  "industry": "FinTech",
  "organisation": "PayStack",
  "years_of_experience": 6,
  "reason_for_attending": "Peer networking",
  "data_source": "manual",
  "consent_given": true,
  "event_id": "b7c0f0e1-...",
  "registration_source": "manual",
  "metadata_json": {}
}
```
*Rules:* At least one of `phone` or `email` is required. Local numbers (e.g. `08012345678`) are automatically normalised to E.164 (`+2348012345678`). Passing `event_id` also registers the participant for that event immediately.
- **Response `data` (`ParticipantRead`):**
```json
{
  "id": "2c8d1a10-...",
  "full_name": "Adaeze Okafor",
  "email_raw": "adaeze@example.com",
  "email_normalised": "adaeze@example.com",
  "phone_raw": "08012345678",
  "phone_normalised": "+2348012345678",
  "current_role": "Senior Data Engineer",
  "industry": "FinTech",
  "organisation": "PayStack",
  "years_of_experience": 6,
  "reason_for_attending": "Peer networking",
  "data_source": "manual",
  "consent_given": true,
  "consent_recorded_at": "2026-11-24T10:05:00Z",
  "retention_until": null,
  "created_at": "2026-11-24T10:05:00Z",
  "updated_at": "2026-11-24T10:05:00Z"
}
```

### 7.2 Lookup Participant — `GET /api/v1/participants/lookup`
- **Access:** Public **or** Admin (`X-API-Key`)
- **Query Params:**
  - `phone` (`string`, optional — preferred)
  - `email` (`string`, optional)
  - `event_id` (`UUID`, optional — narrows match to a specific event)
  - *(At least one of `phone` or `email` is required, otherwise `422`.)*
- **Public Response (`200 OK` — non-enumerating):**
```json
{
  "status": "verification_required",
  "verification_channel": "phone",
  "verification_supported_channels": ["whatsapp_otp", "sms_otp", "email_otp"],
  "message": "If a matching registration exists, verification can proceed via the registered contact channel."
}
```
- **Admin Response (`200 OK` — with `X-API-Key`):**
```json
{
  "matched": true,
  "match_channel": "phone",
  "participant_id": "2c8d1a10-...",
  "full_name": "Adaeze Okafor",
  "registered_event_ids": ["b7c0f0e1-..."],
  "message": "Participant record matched successfully."
}
```

### 7.3 Bulk Import Participants (CSV / Excel) — `POST /api/v1/participants/import`
- **Access:** Admin (`X-API-Key`)
- **Content-Type:** `multipart/form-data`
- **Max File Size:** `10 MB` (`.csv`, `.xlsx`, `.xls`)
- **Form Fields:**
  - `file` *(required)*: Binary CSV or Excel file
  - `event_id` *(optional UUID)*: Automatically registers imported rows to this event (and records attendance if column present)
  - `data_source` *(optional string, default `"import"`)*
  - `dry_run` *(optional boolean, default `true`)* — **Always call with `dry_run=true` first** so the admin can preview rows & errors, then submit again with `dry_run=false` to commit!
- **Accepted Spreadsheet Column Headers (case-insensitive, spaces or underscores):**
  - `full_name`: `full_name`, `name`, `participant_name`, `attendee_name` *(required)*
  - `email`: `email`, `email_address`, `registered_email`
  - `phone`: `phone`, `phone_number`, `whatsapp_number`, `mobile`, `telephone`
  - `current_role`: `current_role`, `role`, `job_title`, `title`
  - `industry`: `industry`, `sector`
  - `organisation`: `organisation`, `organization`, `company`, `employer`
  - `years_of_experience`: `years_of_experience`, `experience_years`, `yoe`
  - `reason_for_attending`: `reason_for_attending`, `reason`, `attendance_reason`
  - `attendance_status`: `attendance_status`, `attended`, `attendance` *(truthy values: `true`, `1`, `yes`, `y`, `confirmed`, `present`)*
  - `consent_given`: `consent_given`, `consent`
- **Response `data` (`ParticipantImportReport`):**
```json
{
  "dry_run": true,
  "filename": "attendees.xlsx",
  "total_rows": 50,
  "valid_rows": 47,
  "created_count": 0,
  "updated_count": 0,
  "duplicate_count": 2,
  "error_count": 3,
  "errors": [
    {
      "row_number": 12,
      "field": "phone/email",
      "reason": "Incomplete record: at least one of phone or email is required.",
      "raw_values": { "full_name": "John Doe" }
    }
  ],
  "preview_records": [
    {
      "row_number": 2,
      "full_name": "Adaeze Okafor",
      "phone_normalised": "+2348012345678",
      "email_normalised": "adaeze@example.com",
      "action": "create"
    }
  ]
}
```
*Note: `preview_records` returns up to the first 50 valid rows; `action` is `"create"` or `"update_or_register"`.*

### 7.4 Get Participant — `GET /api/v1/participants/{participant_id}`
- **Access:** Admin (`X-API-Key`)
- **Response:** `200 OK`, `data: ParticipantRead`

### 7.5 Update Participant — `PATCH /api/v1/participants/{participant_id}`
- **Access:** Admin (`X-API-Key`)
- **Request Body (`ParticipantUpdate`):** Any subset of `full_name`, `email`, `phone`, `current_role`, `industry`, `organisation`, `years_of_experience`, `reason_for_attending`, `consent_given`, `retention_until`, `metadata_json`.
- **Response:** `200 OK`, `data: ParticipantRead`

### 7.6 Get Participant Impact Summary — `GET /api/v1/participants/{participant_id}/impact`
- **Access:** Admin (`X-API-Key`)
- **Query Params:** `event_id` (`UUID`, optional)
- **Response `data` (`ParticipantImpactSummary`):**
```json
{
  "participant_id": "2c8d1a10-...",
  "event_id": null,
  "latest_scores": [ ... ],
  "actions_summary": {
    "intended": 2,
    "in_progress": 1,
    "completed": 1,
    "abandoned": 0
  },
  "connections_summary": {
    "total_connections": 3,
    "follow_up_occurred": 2,
    "collaborations_started": 1,
    "opportunities_discovered": 1
  },
  "outcomes_by_evidence": {
    "self_reported": 1,
    "documented": 1,
    "verified": 0
  },
  "follow_up_progress": [ ... ]
}
```

---

## 8. Question Cards, Questions & Questionnaires

### 8.1 Question Cards (`/api/v1/question-cards`)

| Method | Path | Access | Notes |
| --- | --- | --- | --- |
| `GET` | `/api/v1/question-cards` | Public | Query: `include_inactive` (`bool`, default `false`). Returns `QuestionCardRead[]` with non-archived `questions`. |
| `GET` | `/api/v1/question-cards/{card_id}` | Public | Returns single `QuestionCardRead`. |
| `POST` | `/api/v1/question-cards` | Admin | `201 Created`. Body: `{ code, title, description?, category? ("reflection"), is_active? (true), display_order? (0) }` |
| `PATCH` | `/api/v1/question-cards/{card_id}` | Admin | Partial update of `title`, `description`, `category`, `is_active`, `display_order`. |
| `POST` | `/api/v1/question-cards/{card_id}/questions` | Admin | `201 Created`. Same body as `QuestionCreate` (`card_id` is auto-attached). |

### 8.2 Questions (`/api/v1/questions`)

| Method | Path | Access | Notes |
| --- | --- | --- | --- |
| `GET` | `/api/v1/questions` | Public | Query filters: `include_archived` (`false`), `card_id`, `pillar_id`, `question_type`, `is_scorable` (`bool`). |
| `GET` | `/api/v1/questions/{question_id}` | Public | Returns `QuestionRead`. |
| `POST` | `/api/v1/questions` | Admin | `201 Created`. Body: `QuestionCreate` (below). |
| `PATCH` | `/api/v1/questions/{question_id}` | Admin | Partial update (`QuestionUpdate`). Note: sending `pillar_ids` or `options` replaces the full list for that question. |
| `PATCH` | `/api/v1/questions/{question_id}/archive` | Admin | Soft-archives question (`is_archived=true`) without deleting historical responses. |

**`QuestionCreate` Body Example:**
```json
{
  "code": "eng_session_relevance",
  "question_text": "How relevant were the sessions to your current STEM work?",
  "description": "Rate from 1 (Not relevant) to 5 (Highly relevant)",
  "question_type": "rating_scale",
  "card_id": null,
  "category": "engagement",
  "is_required": true,
  "is_scorable": true,
  "allow_explanation": true,
  "explanation_prompt": "Briefly share why (optional)",
  "validation_config": { "min": 1, "max": 5 },
  "scoring_config": { "min": 1, "max": 5 },
  "display_order": 1,
  "pillar_ids": ["<pillar-uuid>"],
  "options": [
    {
      "option_value": "1",
      "option_label": "Not relevant",
      "score_value": 0,
      "display_order": 1,
      "is_active": true
    }
  ]
}
```
*Note: `code` must match `^[a-z0-9_-]+$` (2–100 chars). For qualitative/reflective questions, set `is_scorable: false`.*

### 8.3 Questionnaires (`/api/v1/questionnaires`)

| Method | Path | Access | Notes |
| --- | --- | --- | --- |
| `GET` | `/api/v1/questionnaires` | Public | Query filters: `event_id`, `status` (`draft`/`published`/`archived`), `questionnaire_type`. |
| `GET` | `/api/v1/questionnaires/{questionnaire_id}` | Public | Returns full `QuestionnaireRead` with `sections` and ordered `questions` (each embeds full `QuestionRead` + `options`). |
| `POST` | `/api/v1/questionnaires` | Admin | `201 Created` (starts in `draft` status). |
| `PATCH` | `/api/v1/questionnaires/{questionnaire_id}` | Admin | Partial update (`QuestionnaireUpdate`). Passing `sections` or `questions` replaces the questionnaire structure. |
| `POST` | `/api/v1/questionnaires/{questionnaire_id}/publish` | Admin | Transitions status to `published` (requires at least 1 attached question, else `422`). |

**`QuestionnaireCreate` Body Example:**
```json
{
  "code": "post_event_2026_v1",
  "title": "Post-Event Impact Assessment",
  "description": "Sections A–F post-event survey",
  "event_id": "b7c0f0e1-...",
  "questionnaire_type": "post_event",
  "version": "1.0",
  "sections": [
    {
      "code": "B",
      "title": "Professional Engagement",
      "description": "Session engagement and active participation",
      "display_order": 1,
      "question_ids": ["<question-uuid-1>", "<question-uuid-2>"]
    }
  ],
  "questions": [
    {
      "question_id": "<question-uuid-3>",
      "section_code": "B",
      "is_required_override": true,
      "display_order": 3
    }
  ]
}
```
**Rendering Tip for Frontend:** `QuestionnaireRead` returns `sections[]` and `questions[]` where each item in `questions[]` has `section_id`, `display_order`, `is_required_override`, and the nested `question` object. Group `questions` by `section_id`, sort by `display_order`, and compute required state as:
```ts
const isRequired = item.is_required_override ?? item.question.is_required;
```

---

## 9. Assessments (`/api/v1/assessments`)

### 9.1 Submit Assessment — `POST /api/v1/assessments/submit`
- **Access:** Public or Admin
- **Status:** `201 Created`
- **Validation Rules (Atomic — all responses validated before saving):**
  - Questionnaire must have `status === "published"` (else `422`).
  - Participant must already exist and match `participant_id`, `phone`, or `email` (else `404`).
  - Duplicate `question_id` entries in `responses` are rejected (`422`).
  - Every required question must be answered (else `422` with `details.missing_question_codes`).

#### CRITICAL: Which Response Field to Populate per `question_type`

| `question_type` | Field to Send in `responses[]` | Validation Enforced |
| --- | --- | --- |
| `short_text`, `long_text` | `response_text` (`string`) | Non-empty trimmed string |
| `yes_no` | `response_boolean` (`boolean`) | Must be `true` or `false` |
| `rating_scale`, `numeric` | `response_numeric` (`number`) | Checked against `question.validation_config.min` / `.max` |
| `date` | `response_date` (`"YYYY-MM-DD"`) | Valid ISO date |
| `single_choice` | `response_text` (`string`) | Must match an active `option.option_value` |
| `multiple_choice` | `response_json` (`string[]`) | Must be a JSON array of active `option.option_value` strings |
| *(Any question with `allow_explanation: true`)* | `explanation_text` (`string`, optional) | Stored alongside the primary answer |

**Request Body (`AssessmentSubmitRequest`):**
```json
{
  "phone": "08012345678",
  "email": null,
  "participant_id": null,
  "event_id": "b7c0f0e1-...",
  "questionnaire_id": "9f11a2b3-...",
  "submission_channel": "web_portal",
  "started_at": "2026-11-24T16:40:00Z",
  "profile_updates": {
    "current_role": "Senior Data Engineer",
    "industry": "FinTech",
    "organisation": "PayStack",
    "years_of_experience": 6,
    "reason_for_attending": "Learning & networking",
    "consent_given": true
  },
  "responses": [
    {
      "question_id": "q-uuid-1",
      "response_numeric": 5,
      "explanation_text": "Loved the AI systems workshop."
    },
    {
      "question_id": "q-uuid-2",
      "response_boolean": true
    },
    {
      "question_id": "q-uuid-3",
      "response_text": "career_growth"
    },
    {
      "question_id": "q-uuid-4",
      "response_json": ["peer_networking", "mentorship"]
    }
  ],
  "metadata_json": { "client": "nextjs-v1" }
}
```
- **Response `data` (`AssessmentSubmissionRead`):** `{ id, participant_id, event_id, questionnaire_id, submission_channel, status, started_at, submitted_at, completeness_ratio, responses[], created_at }`

### 9.2 Get Assessment — `GET /api/v1/assessments/{assessment_id}`
- **Access:** Admin (`X-API-Key`)
- **Response:** `200 OK`, `data: AssessmentSubmissionRead`

### 9.3 List Participant Assessments — `GET /api/v1/participants/{participant_id}/assessments`
- **Access:** Admin (`X-API-Key`)
- **Query Params:** `event_id` (`UUID`, optional)
- **Response:** `200 OK`, `data: AssessmentSubmissionRead[]`, `meta: { total }`

---

## 10. Measurement Pillars & Scoring (`/api/v1/pillars`, `/api/v1/scoring`)

### 10.1 List Measurement Pillars — `GET /api/v1/pillars`
- **Access:** Public
- **Response:** `200 OK`, `data: MeasurementPillarRead[]` (the 6 seeded pillars: Professional Engagement `0.15`, Knowledge & Insights `0.20`, Workplace Excellence `0.15`, Recognition & Rewards `0.15`, Networking & Relationships `0.20`, Post-Event Application `0.15`).
```json
[
  {
    "id": "p-uuid-1",
    "code": "professional_engagement",
    "name": "Professional Engagement",
    "description": "...",
    "impact_category": "immediate",
    "default_weight": 0.15,
    "display_order": 1,
    "is_active": true
  }
]
```

### 10.2 Scoring Frameworks (Admin Only)

| Method | Path | Access | Notes |
| --- | --- | --- | --- |
| `GET` | `/api/v1/scoring/frameworks` | Admin | Lists all framework versions with `dimensions[]` and `rules[]`. |
| `POST` | `/api/v1/scoring/frameworks` | Admin | `201 Created`. Dimension `weight` values **must sum to `1.0`** (`±0.005`). |
| `PATCH` | `/api/v1/scoring/frameworks/{framework_id}` | Admin | Updates thresholds, dimensions (must sum to `1.0`), or rules. |

**`ScoringFrameworkCreate` Body:**
```json
{
  "name": "CCI STEM Impact Framework",
  "version": "1.1",
  "description": "Updated weights for 2026",
  "is_active": true,
  "min_questions_per_pillar": 1,
  "min_pillars_required": 2,
  "min_completeness_ratio": 0.25,
  "dimensions": [
    {
      "pillar_id": "p-uuid-1",
      "weight": 0.20,
      "impact_category": "immediate",
      "min_questions_required": 1
    }
  ],
  "rules": [
    {
      "pillar_id": "p-uuid-1",
      "question_id": "q-uuid-1",
      "rule_type": "rating_scale",
      "rule_config": { "min": 1, "max": 5 },
      "question_weight": 1.0,
      "is_active": true
    }
  ]
}
```

### 10.3 Calculate & Read Scores (Admin Only)

| Method | Path | Access | Request / Query | Response `data` |
| --- | --- | --- | --- | --- |
| `POST` | `/api/v1/scoring/calculate/{participant_id}` | Admin | Body: `{ event_id, framework_id?, assessment_submission_id? }` | `ParticipantImpactScoreRead` |
| `POST` | `/api/v1/scoring/calculate-event/{event_id}` | Admin | Body (optional): `{ framework_id? }` | `EventBulkCalculationResult` |
| `GET` | `/api/v1/scoring/participants/{participant_id}` | Admin | Query: `event_id?`, `latest_only` (`bool`, default `false`) | `ParticipantImpactScoreRead[]` |
| `GET` | `/api/v1/scoring/events/{event_id}` | Admin | Query: `latest_only` (`bool`, default `true`) | `ParticipantImpactScoreRead[]` |

**`ParticipantImpactScoreRead` Shape:**
```json
{
  "id": "score-uuid",
  "participant_id": "2c8d1a10-...",
  "event_id": "b7c0f0e1-...",
  "framework_id": "fw-uuid",
  "framework_version": "1.0",
  "assessment_submission_id": "sub-uuid",
  "score_scope": "immediate",
  "status": "calculated",
  "overall_impact_score": 82.5,
  "immediate_impact_score": 84.0,
  "post_event_application_score": 78.0,
  "sustained_impact_score": null,
  "completeness_ratio": 0.8333,
  "covered_pillars_count": 5,
  "total_pillars_count": 6,
  "weight_renormalised": true,
  "is_latest": true,
  "calculated_at": "2026-11-24T17:00:00Z",
  "calculation_metadata": {},
  "dimension_scores": [
    {
      "id": "dim-score-uuid",
      "dimension_id": "dim-uuid",
      "pillar_id": "p-uuid-1",
      "pillar_code": "professional_engagement",
      "pillar_name": "Professional Engagement",
      "raw_score": 4.2,
      "normalised_score": 80.0,
      "configured_weight": 0.15,
      "effective_weight": 0.1765,
      "questions_answered": 2,
      "questions_total": 2,
      "completeness_ratio": 1.0,
      "status": "calculated"
    }
  ]
}
```
> **UI Tip:** Missing pillars have `normalised_score: null`, `effective_weight: null`, `status: "missing"`. Never render `null` scores as `0` — display `"N/A"` or `"Insufficient data"` and badge `weight_renormalised: true` when applicable.

---

## 11. Longitudinal Follow-Ups & Impact Tracking

### 11.1 Follow-Up Stages & Schedules

| Method | Path | Access | Details |
| --- | --- | --- | --- |
| `GET` | `/api/v1/follow-ups/stages` | Public | Query: `event_id?`. Lists active stages (seeded: `30_day`, `60_day`, `90_day`). |
| `POST` | `/api/v1/follow-ups/stages` | Admin | `201 Created`. Body: `{ event_id?, stage_code, stage_name, days_after_event (1..3650), questionnaire_id?, display_order? }`. |
| `POST` | `/api/v1/follow-ups` | Admin | `201 Created`. Body: `{ participant_id, event_id, follow_up_stage?, due_date?, status? ("pending") }`. Omit `follow_up_stage` to schedule all active stages (30/60/90-day) automatically. Returns `FollowUpScheduleRead[]`. |
| `GET` | `/api/v1/follow-ups` | Admin | Query: `event_id?`, `participant_id?`, `follow_up_stage?`, `status?`. Returns `FollowUpScheduleRead[]`. |
| `GET` | `/api/v1/participants/{participant_id}/follow-ups` | Admin | Query: `event_id?`. Longitudinal timeline (`FollowUpScheduleRead[]` with nested `submissions[]`). |

### 11.2 Submit Follow-Up — `POST /api/v1/follow-ups/{follow_up_id}/submit`
- **Access:** Public or Admin
- **Status:** `201 Created`
- **Request Body (`FollowUpSubmitRequest`):**
```json
{
  "assessment_date": "2026-12-24",
  "assessment_submission_id": null,
  "responses": {
    "applied_new_skill": true,
    "shared_with_team": true,
    "summary": "Introduced automated testing workflow to my engineering team."
  },
  "reported_actions": [
    {
      "action_category": "workplace_improvement",
      "title": "Set up CI quality gates",
      "description": "Rolled out across 3 repositories",
      "action_status": "completed",
      "target_date": "2026-12-20",
      "evidence_classification": "self_reported"
    }
  ],
  "outcome_descriptions": "Reduced production regression bugs by 30%.",
  "outcome_type": "productivity_gain",
  "evidence_items": [
    {
      "evidence_type": "url",
      "description": "Internal engineering changelog screenshot",
      "reference_url": "https://example.com/evidence/123"
    }
  ],
  "evidence_classification": null
}
```
- **Response `data` (`FollowUpSubmissionRead`):** `{ id, follow_up_schedule_id, participant_id, event_id, follow_up_stage, assessment_submission_id, assessment_date, responses_json, reported_actions_json, outcome_descriptions, evidence_classification, verification_status, verified_by, verified_at, submitted_at }`

### 11.3 Actions, Connections, Outcomes & Evidence (`/api/v1/impact/*`)

| Method | Path | Access | Status | Body / Purpose |
| --- | --- | --- | --- | --- |
| `POST` | `/api/v1/impact/actions` | Public / Admin | `201` | `{ participant_id, event_id, follow_up_submission_id?, action_category?, title, description?, action_status? ("intended"), target_date?, evidence_classification? }` |
| `PATCH` | `/api/v1/impact/actions/{action_id}` | Admin | `200` | `{ action_status?, description?, target_date?, evidence_classification? }` |
| `POST` | `/api/v1/impact/connections` | Public / Admin | `201` | `{ participant_id, event_id, connected_participant_id?, contact_name?, contact_role?, connection_type? ("peer"), follow_up_occurred? (false), collaboration_started? (false), opportunity_discovered? (false), notes?, evidence_classification? }` |
| `POST` | `/api/v1/impact/outcomes` | Public / Admin | `201` | `{ participant_id, event_id, follow_up_submission_id?, action_id?, outcome_type? ("other"), title, description?, observed_at?, evidence_items?: [{ evidence_type, description?, reference_url? }] }` |
| `POST` | `/api/v1/impact/outcomes/{outcome_id}/evidence` | Public / Admin | `201` | `{ evidence_type, description?, reference_url? }` — Attaches evidence and automatically promotes `evidence_classification` to `"documented"`. |
| `PATCH` | `/api/v1/impact/outcomes/{outcome_id}/verify` | Admin | `200` | `{ verification_status ("verified" \| "rejected" \| "pending_review" \| "unverified"), verification_notes? }` — Approving (`"verified"`) promotes `evidence_classification` to `"verified"`. |

> **Evidence Lifecycle:** `self_reported` (submitted without evidence) → `documented` (has `evidence_items`) → `verified` (approved by an Admin via `/verify`).

---

## 12. Analytics (`/api/v1/analytics`) — Admin Only

Every analytics endpoint requires `X-API-Key` and **never fabricates averages from empty datasets**: when `response_count === 0`, `average`, `median`, `std_dev`, `min`, and `max` are `null`.

### Shared Sub-Objects
```ts
export interface DataCoverage {
  response_count: number;
  reference_population: number;
  coverage_ratio: number; // 0.0 to 1.0
  coverage_level: "none" | "low" | "moderate" | "high"; // <0.30 low, <0.70 moderate, >=0.70 high
}

export interface NumericStats {
  average: number | null;
  median: number | null;
  std_dev: number | null;
  min: number | null;
  max: number | null;
  response_count: number;
  data_coverage: DataCoverage;
}
```

### 12.1 Event Overview — `GET /api/v1/analytics/events/{event_id}/overview`
```json
{
  "event_id": "b7c0f0e1-...",
  "event_slug": "cci-stem-lagos-2026",
  "event_title": "CCI STEM Connect Lagos 2026",
  "event_date": "2026-11-24",
  "participation": {
    "total_registered_participants": 120,
    "total_confirmed_attendees": 96,
    "attendance_records_available": 110,
    "attendance_rate": 0.8,
    "attendance_data_reliable": true,
    "assessment_respondents_count": 72,
    "assessment_completion_rate": 0.75,
    "assessment_data_coverage": { "response_count": 72, "reference_population": 96, "coverage_ratio": 0.75, "coverage_level": "high" }
  },
  "impact_scores": {
    "overall_event_impact": { "...NumericStats" },
    "immediate_event_impact": { "...NumericStats" },
    "post_event_application_impact": { "...NumericStats" },
    "sustained_longitudinal_impact": { "...NumericStats" },
    "score_status_breakdown": { "calculated": 65, "partial": 5, "insufficient_data": 2 }
  },
  "actions_progress": {
    "total_actions": 45,
    "by_status": { "intended": 20, "in_progress": 10, "completed": 14, "abandoned": 1 }
  },
  "outcomes_summary": {
    "total_outcomes": 18,
    "by_evidence_classification": { "self_reported": 10, "documented": 5, "verified": 3 }
  },
  "follow_up_summary": {
    "total_scheduled": 216,
    "total_completed": 64,
    "completion_rate": 0.2963,
    "data_coverage": { "...DataCoverage" }
  }
}
```

### 12.2 Six-Pillar Analytics — `GET /api/v1/analytics/events/{event_id}/pillars`
Returns `{ event_id, event_title, participants_scored, pillars[] }` where each pillar item includes `pillar_id`, `pillar_code`, `pillar_name`, `impact_category`, `default_weight`, `missing_count`, and all `NumericStats` fields.

### 12.3 Networking Analytics — `GET /api/v1/analytics/events/{event_id}/networking`
Returns `{ event_id, event_title, total_connections_reported, participants_reporting_connections, connections_per_reporting_participant: NumericStats, follow_up_conversations_count, collaborations_started_count, opportunities_discovered_count, by_connection_type, by_evidence_classification, data_coverage }`.

### 12.4 Application & Outcomes Analytics — `GET /api/v1/analytics/events/{event_id}/application`
Returns `{ event_id, event_title, actions: { total_recorded, intended_only_count, in_progress_count, completed_count, abandoned_count, implementation_conversion_rate, participants_with_actions, participants_with_completed_actions, by_category, data_coverage }, outcomes: { total_outcomes, by_type, by_evidence_classification, verified_outcome_ratio } }`.

### 12.5 Longitudinal Follow-Up Analytics — `GET /api/v1/analytics/events/{event_id}/follow-ups`
Returns `{ event_id, event_title, stages_tracked, stages[] }` where each stage item has `follow_up_stage`, `scheduled_count`, `completed_count`, `pending_count`, `overdue_count`, `completion_rate`, `submissions_count`, `reported_actions_count`, `positive_action_signal: NumericStats`, `by_evidence_classification`, and `data_coverage`.

---

## 13. Reports & Exports (`/api/v1/reports`) — Admin Only

| Method | Path | Request / Query | Response `data` |
| --- | --- | --- | --- |
| `GET` | `/api/v1/reports/events/{event_id}` | — | Full combined report: `{ report_type, generated_at, event, overview, pillars, networking, application, follow_ups }` |
| `GET` | `/api/v1/reports/participants/{participant_id}` | Query: `event_id?` | `{ report_type, generated_at, participant, impact_summary, score_history }` |
| `POST` | `/api/v1/reports/events/{event_id}/export` | Body (optional): `{ export_format: "json" \| "csv" \| "xlsx" }` | `{ report_record_id, report_type, export_format, file_path, generated_at, report }` |
| `POST` | `/api/v1/reports/participants/{participant_id}/export` | Body (optional): `{ export_format: "json" \| "csv" \| "xlsx", event_id? }` | `{ report_record_id, report_type, export_format, file_path, generated_at, report }` |

> **Frontend Download Tip:** The `/export` endpoints return both metadata (`report_record_id`, `file_path`) **and** the full `report` JSON object in the response body. For instant browser CSV/JSON downloads on Render's free tier (which has an ephemeral disk), you can serialize `data.report` client-side or add a file-streaming download endpoint if needed.

---

## 14. Admin Panel Dedicated Endpoints (Added for `/admin` Dashboard)

All endpoints below require the `X-API-Key` header (and `/admin/users*` requires `super_admin` role).

### 14.1 Admin Auth, User Provisioning & Audit Logs (`/api/v1/admin`)

| Method | Path | Role | Summary |
| --- | --- | --- | --- |
| `GET` | `/api/v1/admin/me` | Any Admin | Validates `X-API-Key` and returns `{ actor_id, actor_type, role, is_admin, full_name, email }` |
| `GET` | `/api/v1/admin/users` | `super_admin` | Lists provisioned `AdministratorRecord` accounts (no key hashes) |
| `POST` | `/api/v1/admin/users` | `super_admin` | `201 Created`. Body: `{ full_name, email, role }`. Returns account + plaintext `api_key` **once** |
| `PATCH` | `/api/v1/admin/users/{admin_id}` | `super_admin` | Update `{ full_name?, role?, is_active? }` |
| `GET` | `/api/v1/admin/audit-logs` | Any Admin | Paginated activity log. Query: `action?`, `resource_type?`, `actor_id?`, `limit`, `offset` |

### 14.2 Global Participant Directory, Assessments List & Qualitative Feedback

| Method | Path | Query Filters | Response `data` |
| --- | --- | --- | --- |
| `GET` | `/api/v1/participants` | `q?`, `event_id?`, `industry?`, `attendance_status?`, `has_assessment?`, `sort_by` (`created_at\|full_name\|industry\|organisation`), `sort_order` (`asc\|desc`), `limit`, `offset` | Paginated `ParticipantDirectoryItem[]` (profile + `registered_event_count`, `assessments_count`, `latest_assessment_at`, `registration_date`, `attendance_status`, `assessment_status`) |
| `GET` | `/api/v1/assessments` | `event_id?`, `questionnaire_id?`, `participant_id?`, `status?`, `q?`, `date_from?`, `date_to?`, `sort_order?`, `limit`, `offset` | Paginated `AssessmentSummaryRead[]` (submission + `participant_name`, `participant_email`, `participant_phone`, `event_title`, `questionnaire_title`, `questionnaire_type`, `responses_count`) |
| `GET` | `/api/v1/feedback` | `event_id?`, `questionnaire_id?`, `question_id?`, `card_id?`, `section_code?`, `pillar_id?`, `is_scorable?` (`false` for reflective/qualitative), `industry?`, `participant_id?`, `q?`, `date_from?`, `date_to?`, `limit`, `offset` | Paginated `FeedbackResponseRead[]` (exact verbatim `response_text` / `explanation_text` + question, section, pillar, and participant metadata) |

### 14.3 Impact Lists, Demographics/Distributions & Direct Report Downloads

| Method | Path | Query Filters | Response |
| --- | --- | --- | --- |
| `GET` | `/api/v1/impact/actions` | `event_id?`, `participant_id?`, `action_status?`, `action_category?`, `evidence_classification?`, `limit`, `offset` | Paginated `ParticipantActionListItem[]` (includes `participant_name`) |
| `GET` | `/api/v1/impact/connections` | `event_id?`, `participant_id?`, `connection_type?`, `evidence_classification?`, `limit`, `offset` | Paginated `ProfessionalConnectionListItem[]` (includes `participant_name`) |
| `GET` | `/api/v1/impact/outcomes` | `event_id?`, `participant_id?`, `outcome_type?`, `evidence_classification?`, `verification_status?`, `limit`, `offset` | Paginated `ImpactOutcomeListItem[]` (includes `participant_name` & `evidence_items[]`) |
| `GET` | `/api/v1/analytics/events/{event_id}/demographics` | — | Industry, role, organisation buckets + `years_of_experience` `NumericStats` + `data_coverage` |
| `GET` | `/api/v1/analytics/events/{event_id}/distributions` | `questionnaire_id?`, `question_id?` | Per-question option/rating frequency distributions + `numeric_stats` + `data_coverage` |
| `GET` | `/api/v1/reports/records` | `event_id?`, `participant_id?`, `report_type?`, `limit`, `offset` | Paginated `ReportRecord` export history |
| `GET` | `/api/v1/reports/events/{event_id}/download` | `export_format` (`csv` \| `xlsx` \| `json`, default `csv`) | Direct HTTP file attachment download (`Content-Disposition: attachment`) |
| `GET` | `/api/v1/reports/participants/{participant_id}/download` | `export_format` (`csv` \| `xlsx` \| `json`, default `csv`), `event_id?` | Direct HTTP file attachment download (`Content-Disposition: attachment`) |

---

## 15. Starter TypeScript Client Pattern (Next.js)

```ts
// lib/api-client.ts
const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface ApiSuccess<T> {
  success: true;
  data: T;
  meta: { total?: number; limit?: number; offset?: number; has_more?: boolean } | null;
  request_id: string | null;
}

export interface ApiFailure {
  success: false;
  error: { code: string; message: string; details: unknown };
  request_id: string | null;
}

export class ApiClientError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public details: unknown = null,
    public requestId: string | null = null
  ) {
    super(message);
  }
}

export async function apiRequest<T>(
  path: string,
  options: RequestInit & { adminKey?: string; actorId?: string } = {}
): Promise<ApiSuccess<T>> {
  const { adminKey, actorId, headers, ...rest } = options;
  const isFormData = rest.body instanceof FormData;

  const res = await fetch(`${API_BASE}${path}`, {
    ...rest,
    headers: {
      ...(isFormData ? {} : { "Content-Type": "application/json" }),
      ...(adminKey ? { "X-API-Key": adminKey } : {}),
      ...(actorId ? { "X-Actor-Id": actorId } : {}),
      ...headers,
    },
  });

  const payload = (await res.json()) as ApiSuccess<T> | ApiFailure;
  if (!res.ok || !payload.success) {
    const err = !payload.success ? payload.error : { code: "HTTP_ERROR", message: res.statusText, details: null };
    throw new ApiClientError(res.status, err.code, err.message, err.details, payload.request_id);
  }
  return payload;
}
```

### Recommended Frontend Page Flows
1. **Participant Assessment Flow (Public):**
   - `GET /api/v1/events?status=active` → user picks event
   - `GET /api/v1/questionnaires?event_id=<id>&status=published` → fetch form sections & questions
   - Render dynamic inputs by `question_type` (and optional `explanation_text` when `allow_explanation` is `true`)
   - Collect `phone` (or `email`) + optional `profile_updates`
   - `POST /api/v1/assessments/submit` → display confirmation + `completeness_ratio`
2. **Admin Event & Analytics Dashboard (Server-Proxied `X-API-Key`):**
   - Event selector: `GET /api/v1/events`
   - Participant onboarding: `POST /api/v1/participants/import` (`dry_run=true` → review errors → `dry_run=false`)
   - Roster & check-in: `GET /api/v1/events/{id}/participants` & `POST /api/v1/events/{id}/attendance`
   - Scoring trigger: `POST /api/v1/scoring/calculate-event/{id}`
   - Charts & KPIs: `GET /api/v1/analytics/events/{id}/{overview,pillars,networking,application,follow-ups}`
   - Evidence moderation: `PATCH /api/v1/impact/outcomes/{id}/verify`
