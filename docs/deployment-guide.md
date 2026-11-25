# Deployment & Operations Guide

## 1. Environment Variables

Copy `.env.example` to `.env` and configure:

- `DATABASE_URL`: PostgreSQL connection string (`postgresql+psycopg2://user:pass@host:5432/db`).
- `ADMIN_API_KEY`: High-entropy secret key for administrative API access (`X-API-Key`).
- `DEFAULT_PHONE_REGION`: ISO-3166 alpha-2 region code used when normalising local phone numbers without a country code (default `NG`).
- `CORS_ALLOWED_ORIGINS`: JSON array of allowed Next.js frontend origins.
- `RATE_LIMIT_REQUESTS_PER_MINUTE`, `RATE_LIMIT_LOOKUP_PER_MINUTE`, `RATE_LIMIT_SUBMIT_PER_MINUTE`: Per-IP sliding-window limits.
- `REPORTS_STORAGE_DIR`: Persistent volume path for exported report files.

## 2. Docker Compose Deployment

```bash
cp .env.example .env
docker compose up -d --build
```

The container startup sequence automatically runs:
1. `alembic upgrade head` — applies all schema migrations.
2. `python -m app.database.seed` — idempotently seeds the 6 pillars, Framework v1.0, initial 3 reflective question cards, Sections A–F questionnaire template, and 30/60/90-day follow-up stages.
3. `uvicorn app.main:app --host 0.0.0.0 --port 8000` — starts the API server with `/health` monitoring.

## 3. Database Migrations

```bash
cd backend
# Create a new migration after model changes
alembic revision --autogenerate -m "describe_change"

# Apply migrations
alembic upgrade head

# Roll back one revision
alembic downgrade -1
```

## 4. Production Hardening Recommendations

- Terminate TLS at a reverse proxy (Nginx / Caddy / Cloud Load Balancer) and forward `X-Forwarded-For` and `X-Request-ID`.
- Provision per-administrator API keys in `administrator_records` (stored as SHA-256 hashes) rather than sharing the bootstrap `ADMIN_API_KEY`.
- Swap `SlidingWindowRateLimiter` for a Redis-backed limiter when scaling horizontally across multiple Uvicorn/Gunicorn workers.
- Schedule regular PostgreSQL automated backups and configure `participants.retention_until` anonymisation jobs in line with institutional data governance policies.
