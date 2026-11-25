"""Tests for participant creation, contact normalisation, duplicates, lookup, events & attendance."""

import pytest
from fastapi.testclient import TestClient

from app.core.exceptions import ValidationAppError
from app.core.normalisation import normalise_email, normalise_phone


def test_phone_and_email_normalisation():
    # Local Nigerian number -> E.164
    assert normalise_phone("0803 123 4567") == "+2348031234567"
    assert normalise_phone("+234-803-123-4567") == "+2348031234567"
    assert normalise_phone("0044 7911 123456") == "+447911123456"
    assert normalise_email("  Ada.Lovelace@Example.COM ") == "ada.lovelace@example.com"

    with pytest.raises(ValidationAppError):
        normalise_phone("12345")
    with pytest.raises(ValidationAppError):
        normalise_email("not-an-email")


def test_participant_creation_duplicate_detection_and_update(
    client: TestClient, admin_headers: dict[str, str]
):
    resp = client.post(
        "/api/v1/participants",
        headers=admin_headers,
        json={
            "full_name": "Chinedu Okafor",
            "email": "Chinedu.Okafor@Example.COM",
            "phone": "0803 555 0199",
            "current_role": "Systems Architect",
            "industry": "FinTech",
            "organisation": "PayGrid",
            "years_of_experience": 9,
            "consent_given": True,
        },
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    assert data["email_normalised"] == "chinedu.okafor@example.com"
    assert data["phone_normalised"] == "+2348035550199"
    assert data["phone_raw"] == "0803 555 0199"
    pid = data["id"]

    # Duplicate phone in different formatting must return 409 Conflict
    dup_phone = client.post(
        "/api/v1/participants",
        headers=admin_headers,
        json={"full_name": "Duplicate Phone", "phone": "+2348035550199"},
    )
    assert dup_phone.status_code == 409

    # Duplicate email in different casing must return 409 Conflict
    dup_email = client.post(
        "/api/v1/participants",
        headers=admin_headers,
        json={"full_name": "Duplicate Email", "email": "chinedu.okafor@example.com"},
    )
    assert dup_email.status_code == 409

    # Missing both contacts fails validation
    no_contact = client.post(
        "/api/v1/participants",
        headers=admin_headers,
        json={"full_name": "No Contact"},
    )
    assert no_contact.status_code == 422

    # Update participant
    patch = client.patch(
        f"/api/v1/participants/{pid}",
        headers=admin_headers,
        json={"current_role": "Principal Engineer"},
    )
    assert patch.status_code == 200
    assert patch.json()["data"]["current_role"] == "Principal Engineer"


def test_participant_lookup_privacy_and_admin_workflow(
    client: TestClient, admin_headers: dict[str, str]
):
    client.post(
        "/api/v1/participants",
        headers=admin_headers,
        json={
            "full_name": "Amina Bello",
            "email": "amina@example.com",
            "phone": "0809 876 5432",
        },
    )

    # Public lookup for EXISTING contact vs NON-EXISTING contact must return IDENTICAL generic payload
    pub_existing = client.get("/api/v1/participants/lookup", params={"phone": "08098765432"})
    pub_missing = client.get("/api/v1/participants/lookup", params={"phone": "08090001111"})
    assert pub_existing.status_code == 200
    assert pub_missing.status_code == 200
    assert pub_existing.json()["data"] == pub_missing.json()["data"]
    assert pub_existing.json()["data"]["status"] == "verification_required"

    # Admin lookup matches by normalised phone (preferred) or email
    adm_phone = client.get(
        "/api/v1/participants/lookup",
        headers=admin_headers,
        params={"phone": "+234 809 876 5432"},
    )
    assert adm_phone.status_code == 200
    assert adm_phone.json()["data"]["matched"] is True
    assert adm_phone.json()["data"]["match_channel"] == "phone"
    assert adm_phone.json()["data"]["full_name"] == "Amina Bello"

    adm_email = client.get(
        "/api/v1/participants/lookup",
        headers=admin_headers,
        params={"email": "AMINA@example.com"},
    )
    assert adm_email.status_code == 200
    assert adm_email.json()["data"]["matched"] is True
    assert adm_email.json()["data"]["match_channel"] == "email"


def test_event_registration_repeat_attendance_and_roster(
    client: TestClient, admin_headers: dict[str, str]
):
    e1 = client.post(
        "/api/v1/events",
        headers=admin_headers,
        json={
            "slug": "cci-stem-connect-2026",
            "title": "CCI STEM Connect 2026",
            "event_date": "2026-08-15",
            "location": "Lagos",
        },
    ).json()["data"]
    e2 = client.post(
        "/api/v1/events",
        headers=admin_headers,
        json={
            "slug": "cci-stem-connect-2027",
            "title": "CCI STEM Connect 2027",
            "event_date": "2027-08-15",
            "location": "Abuja",
        },
    ).json()["data"]

    p = client.post(
        "/api/v1/participants",
        headers=admin_headers,
        json={
            "full_name": "Tunde Adeyemi",
            "phone": "0802 111 2233",
            "event_id": e1["id"],
        },
    ).json()["data"]

    # Duplicate registration in the same event is rejected
    dup_reg = client.post(
        f"/api/v1/events/{e1['id']}/registrations",
        headers=admin_headers,
        json={"participant_id": p["id"]},
    )
    assert dup_reg.status_code == 409

    # Same participant can attend a future event
    second_reg = client.post(
        f"/api/v1/events/{e2['id']}/registrations",
        headers=admin_headers,
        json={"participant_id": p["id"], "registration_source": "whatsapp"},
    )
    assert second_reg.status_code == 201

    # Record attendance
    att = client.post(
        f"/api/v1/events/{e1['id']}/attendance",
        headers=admin_headers,
        json={
            "participant_id": p["id"],
            "attendance_status": "confirmed",
            "verification_source": "checkin_desk",
        },
    )
    assert att.status_code == 200
    assert att.json()["data"]["attendance_status"] == "confirmed"

    # Event participants roster returns confirmed attendance
    roster = client.get(f"/api/v1/events/{e1['id']}/participants", headers=admin_headers)
    assert roster.status_code == 200
    assert roster.json()["meta"]["total"] == 1
    assert roster.json()["data"][0]["attendance_status"] == "confirmed"
