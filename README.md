# CCI STEM Connect — Professional Engagement & Impact Measurement System (Backend v1.0)

Production-grade REST API backend for measuring professional engagement, knowledge gained, workplace excellence, recognition insights, networking value, and longitudinal 30/60/90-day post-event impact for **CCI STEM Connect**.

> **Scope (v1.0)**: Pure backend infrastructure (`FastAPI` + `PostgreSQL` + `SQLAlchemy 2.0` + `Alembic` + `Pydantic v2` + `Pandas/NumPy`). No frontend UI or conventional participant password authentication. Designed for seamless consumption by a separate Next.js frontend.

## Key Capabilities

- **No-Authentication Participant Identification**: Identifies participants by E.164-normalised phone number (preferred — registration or WhatsApp group number) or normalised email address, with non-enumerating public lookup ready for Email/SMS/WhatsApp OTP verification in v2.
- **Six Configurable Measurement Pillars**: Database-driven dimensions for *Professional Engagement* (15%), *Knowledge & Insights* (20%), *Workplace Excellence* (15%), *Recognition & Rewards* (15%), *Networking & Relationships* (20%), and *Post-Event Application* (15%).
- **Flexible Question Card & Questionnaire Engine**: Supports 8 question types + optional free-text explanations, multi-pillar assignment, qualitative vs. scorable separation, archival, and Sections A–F questionnaire publishing. Includes the 3 initial reflective question cards stored strictly as qualitative data.
- **Configurable Scoring Engine**: Versioned scoring frameworks, automatic missing-pillar exclusion (never treated as zero), weight renormalisation, completeness tracking, separation of immediate vs. post-event application vs. sustained impact, and historical score preservation.
- **Longitudinal Impact Tracking**: Configurable 30/60/90-day (and future custom) follow-ups, separation of intended vs. completed actions, networking outcomes, and evidence classification (`self_reported`, `documented`, `verified`).
- **Analytics, Reporting & Data Imports**: Pandas/NumPy event analytics with mandatory response counts and data coverage indicators (never fabricating averages from empty datasets), JSON/CSV/XLSX exports, and CSV/Excel participant import with `dry_run` review reports.

## Quick Start (Docker Compose)

```bash
cp .env.example .env
# Edit .env and set a strong ADMIN_API_KEY
docker compose up --build
```

Interactive OpenAPI / Swagger UI will be available at `http://localhost:8000/docs`.

## Local Development & Testing

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run migrations & idempotent reference seeder (requires PostgreSQL DATABASE_URL)
alembic upgrade head
python -m app.database.seed

# Start API server
uvicorn app.main:app --reload

# Run automated test suite
pytest -v
```

## Documentation

- [Architecture Overview](docs/architecture.md)
- [Database Schema (30 Tables)](docs/database-schema.md)
- [REST API Documentation (`/api/v1/`)](docs/api-documentation.md)
- [Scoring Methodology](docs/scoring-methodology.md)
- [Deployment & Operations Guide](docs/deployment-guide.md)
