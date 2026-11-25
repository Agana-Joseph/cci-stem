"""Tests for CSV/Excel import validation, API access restrictions, and rate limiting."""

from io import BytesIO

import pandas as pd
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.rate_limiter import rate_limiter


def test_csv_and_excel_import_dry_run_validation_and_commit(
    client: TestClient, admin_headers: dict[str, str]
):
    event = client.post(
        "/api/v1/events",
        headers=admin_headers,
        json={
            "slug": "cci-import-event",
            "title": "CCI Import Test Event",
            "event_date": "2026-09-10",
        },
    ).json()["data"]

    csv_content = (
        "full_name,email,phone,current_role,industry,attended,consent_given\n"
        "Sadiq Lawal,sadiq@example.com,0803 111 0001,Data Scientist,AI,yes,true\n"
        "Duplicate Phone,other@example.com,+2348031110001,Analyst,AI,yes,true\n"
        ",missingname@example.com,0803 111 0002,Engineer,Tech,yes,true\n"
        "Bad Email,not-an-email,0803 111 0003,Designer,Tech,no,true\n"
        "No Contact,,,Manager,Finance,no,false\n"
    ).encode("utf-8")

    # 1. Dry-run preview must validate without committing
    preview = client.post(
        "/api/v1/participants/import",
        headers=admin_headers,
        files={"file": ("participants.csv", csv_content, "text/csv")},
        data={"event_id": event["id"], "data_source": "whatsapp", "dry_run": "true"},
    )
    assert preview.status_code == 200, preview.text
    rep = preview.json()["data"]
    assert rep["dry_run"] is True
    assert rep["total_rows"] == 5
    assert rep["valid_rows"] == 1
    assert rep["created_count"] == 0
    assert rep["duplicate_count"] == 1
    assert rep["error_count"] == 4

    # Confirm nothing committed yet
    roster_before = client.get(
        f"/api/v1/events/{event['id']}/participants", headers=admin_headers
    ).json()["meta"]["total"]
    assert roster_before == 0

    # 2. Commit CSV import
    commit = client.post(
        "/api/v1/participants/import",
        headers=admin_headers,
        files={"file": ("participants.csv", csv_content, "text/csv")},
        data={"event_id": event["id"], "data_source": "whatsapp", "dry_run": "false"},
    )
    assert commit.status_code == 200
    assert commit.json()["data"]["created_count"] == 1

    # 3. Excel (.xlsx) import support
    df = pd.DataFrame(
        [
            {
                "full_name": "Bola Adesina",
                "email": "bola@example.com",
                "phone": "0809 444 5566",
                "organisation": "STEM Hub",
                "attended": "true",
            }
        ]
    )
    buf = BytesIO()
    df.to_excel(buf, index=False, engine="openpyxl")
    buf.seek(0)

    xlsx_resp = client.post(
        "/api/v1/participants/import",
        headers=admin_headers,
        files={
            "file": (
                "roster.xlsx",
                buf.getvalue(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
        data={"event_id": event["id"], "dry_run": "false"},
    )
    assert xlsx_resp.status_code == 200
    assert xlsx_resp.json()["data"]["created_count"] == 1

    roster_after = client.get(
        f"/api/v1/events/{event['id']}/participants", headers=admin_headers
    ).json()["meta"]["total"]
    assert roster_after == 2


def test_api_access_restrictions_and_rate_limiting(
    client: TestClient, admin_headers: dict[str, str]
):
    event = client.post(
        "/api/v1/events",
        headers=admin_headers,
        json={"slug": "sec-event", "title": "Security Event", "event_date": "2026-10-01"},
    ).json()["data"]

    # Sensitive admin endpoints MUST reject unauthenticated public callers with 401
    assert client.post("/api/v1/participants", json={"full_name": "X", "email": "x@x.com"}).status_code == 401
    assert client.get(f"/api/v1/events/{event['id']}/participants").status_code == 401
    assert client.get(f"/api/v1/analytics/events/{event['id']}/overview").status_code == 401
    assert client.get(f"/api/v1/reports/events/{event['id']}").status_code == 401
    assert client.get("/api/v1/scoring/frameworks").status_code == 401

    # Invalid API key must also return 401
    assert (
        client.get(
            f"/api/v1/events/{event['id']}/participants",
            headers={"X-API-Key": "wrong-key"},
        ).status_code
        == 401
    )

    # Rate limiting enforces 429 on participant lookup abuse
    rate_limiter.reset()
    settings = get_settings()
    original_limit = settings.rate_limit_lookup_per_minute
    settings.rate_limit_lookup_per_minute = 3
    try:
        for _ in range(3):
            r = client.get("/api/v1/participants/lookup", params={"email": "test@example.com"})
            assert r.status_code == 200
        blocked = client.get(
            "/api/v1/participants/lookup", params={"email": "test@example.com"}
        )
        assert blocked.status_code == 429
        assert blocked.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"
    finally:
        settings.rate_limit_lookup_per_minute = original_limit
        rate_limiter.reset()
