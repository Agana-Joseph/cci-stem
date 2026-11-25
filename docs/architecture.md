# Architecture — CCI STEM Connect Backend

## 1. Architectural Pattern

The backend implements a **Layered Modular Monolith** structured for clear domain boundaries, deterministic business logic, and future horizontal scalability:

```
┌────────────────────────────────────────────────────────────────┐
│ HTTP Edge: CORS + Request-ID + Sliding-Window Rate Limiter     │
├────────────────────────────────────────────────────────────────┤
│ API Layer (app/api/v1/*.py)                                    │
│ - Pydantic v2 validation & OpenAPI documentation               │
│ - Standardised {success, data, meta, request_id} envelope      │
│ - Admin API Key guard (X-API-Key) vs Public participant routes │
├────────────────────────────────────────────────────────────────┤
│ Service Layer (app/services/, app/scoring/, app/analytics/,    │
│                app/reports/)                                   │
│ - Transaction boundaries & immutable AuditLog emission         │
│ - Pure deterministic Scoring Calculator (zero HTTP coupling)   │
│ - Pandas/NumPy Analytics with mandatory data coverage          │
│ - JSON/CSV/XLSX Export Engine                                  │
├────────────────────────────────────────────────────────────────┤
│ Repository Layer (app/repositories/*.py)                       │
│ - Typed SQLAlchemy 2.0 queries & eager loading                 │
├────────────────────────────────────────────────────────────────┤
│ Persistence Layer (PostgreSQL 16 + Alembic Migrations)         │
│ - 30 normalised relational tables with UUID primary keys       │
└────────────────────────────────────────────────────────────────┘
```

## 2. Participant Identification Without Authentication

Participants never create passwords or accounts. Instead:

1. **Contact Normalisation**: Phone numbers are normalised to strict **E.164** format (default region configurable via `DEFAULT_PHONE_REGION`, e.g., `NG` so `0803 123 4567` → `+2348031234567`) while retaining `phone_raw`. Emails are trimmed and lowercased into `email_normalised` while retaining `email_raw`.
2. **Non-Enumerating Public Lookup**: `GET /api/v1/participants/lookup` without an `X-API-Key` header always returns an identical generic payload (`status: "verification_required"`) whether or not the contact exists in the database. This eliminates account/contact enumeration attacks.
3. **OTP-Ready Verification Contract**: `app.core.security.VerificationProvider` defines `initiate_challenge()` and `verify_challenge()` so Email OTP, SMS OTP, or WhatsApp verification can be dropped into v2 without changing core participant or assessment logic.
4. **Trusted Admin Access**: All participant PII endpoints, rosters, imports, scoring runs, analytics, and exports require a valid `X-API-Key` (validated against `administrator_records.api_key_hash` or the bootstrap `ADMIN_API_KEY`) and emit immutable records into `audit_logs`.

## 3. Security & Privacy Controls

- **Sliding-Window Rate Limiting**: Separate per-IP buckets for general endpoints (120 req/min), lookup endpoints (15 req/min), and submissions (30 req/min).
- **No Public Participant Listings**: `GET /api/v1/events/{event_id}/participants` and `GET /api/v1/participants/{id}` strictly enforce `require_admin`.
- **Safe File Imports**: File size limit (`MAX_IMPORT_FILE_SIZE_MB`), extension allowlist (`.csv`, `.xlsx`, `.xls`), row-level validation, and `dry_run=true` review before commit.
- **Consent & Retention**: `participants` stores `consent_given`, `consent_recorded_at`, `data_source`, `retention_until`, and `anonymised_at`.
