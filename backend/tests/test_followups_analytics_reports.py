"""Tests for Scenarios D, E, F, Follow-Ups (30/60/90d), Analytics, and Report Exports."""

from pathlib import Path

from fastapi.testclient import TestClient


def test_scenarios_d_e_f_and_analytics_and_exports(
    client: TestClient, admin_headers: dict[str, str]
):
    event = client.post(
        "/api/v1/events",
        headers=admin_headers,
        json={
            "slug": "cci-stem-longitudinal",
            "title": "CCI STEM Connect Longitudinal Event",
            "event_date": "2026-06-01",
        },
    ).json()["data"]

    # Empty event analytics must NOT fabricate averages from empty datasets
    empty_overview = client.get(
        f"/api/v1/analytics/events/{event['id']}/overview", headers=admin_headers
    ).json()["data"]
    assert empty_overview["impact_scores"]["overall_event_impact"]["average"] is None
    assert empty_overview["impact_scores"]["overall_event_impact"]["response_count"] == 0
    assert (
        empty_overview["impact_scores"]["overall_event_impact"]["data_coverage"][
            "coverage_level"
        ]
        == "none"
    )
    assert empty_overview["participation"]["attendance_rate"] is None

    participant = client.post(
        "/api/v1/participants",
        headers=admin_headers,
        json={
            "full_name": "Kemi Adeola",
            "phone": "0806 333 4455",
            "email": "kemi@example.com",
            "event_id": event["id"],
        },
    ).json()["data"]

    # Scenario D: Participant intends to implement an idea (not yet completed)
    intended = client.post(
        "/api/v1/impact/actions",
        json={
            "participant_id": participant["id"],
            "event_id": event["id"],
            "action_category": "workplace_improvement",
            "title": "Introduce monthly excellence recognition standup",
            "action_status": "intended",
        },
    )
    assert intended.status_code == 201
    assert intended.json()["data"]["action_status"] == "intended"
    assert intended.json()["data"]["completed_at"] is None

    # Scenario E: Participant reports an outcome without supporting evidence -> self_reported
    outcome_self = client.post(
        "/api/v1/impact/outcomes",
        json={
            "participant_id": participant["id"],
            "event_id": event["id"],
            "outcome_type": "productivity_gain",
            "title": "Reduced weekly status meeting overhead by 30%",
            "description": "Self-reported team efficiency gain.",
        },
    )
    assert outcome_self.status_code == 201
    out_data = outcome_self.json()["data"]
    assert out_data["evidence_classification"] == "self_reported"
    assert out_data["verification_status"] == "unverified"

    # Adding documentation promotes outcome to documented; admin verification promotes to verified
    documented = client.post(
        f"/api/v1/impact/outcomes/{out_data['id']}/evidence",
        json={
            "evidence_type": "document_link",
            "description": "Team sprint velocity retrospective notes",
            "reference_url": "https://example.org/docs/velocity-report",
        },
    )
    assert documented.status_code == 201
    assert documented.json()["data"]["evidence_classification"] == "documented"

    verified = client.patch(
        f"/api/v1/impact/outcomes/{out_data['id']}/verify",
        headers=admin_headers,
        json={"verification_status": "verified", "verification_notes": "Confirmed with manager."},
    )
    assert verified.status_code == 200
    assert verified.json()["data"]["evidence_classification"] == "verified"

    # Scenario F: Schedule 30/60/90-day follow-ups; complete 30-day only -> 60 & 90 remain pending
    schedules = client.post(
        "/api/v1/follow-ups",
        headers=admin_headers,
        json={"participant_id": participant["id"], "event_id": event["id"]},
    )
    assert schedules.status_code == 201
    sched_list = schedules.json()["data"]
    assert [s["follow_up_stage"] for s in sched_list] == ["30_day", "60_day", "90_day"]
    sched_30 = sched_list[0]

    fu_submit = client.post(
        f"/api/v1/follow-ups/{sched_30['id']}/submit",
        json={
            "responses": {
                "applied_idea": True,
                "followed_up_connections": True,
                "shared_with_colleagues": True,
            },
            "reported_actions": [
                {
                    "action_category": "knowledge_sharing",
                    "title": "Ran lunch-and-learn on professional standards",
                    "action_status": "completed",
                }
            ],
            "outcome_descriptions": "Colleagues adopted peer recognition shout-outs.",
        },
    )
    assert fu_submit.status_code == 201
    assert fu_submit.json()["data"]["evidence_classification"] == "self_reported"

    # Verify 30_day is completed while 60_day and 90_day remain pending
    timeline = client.get(
        f"/api/v1/participants/{participant['id']}/follow-ups",
        headers=admin_headers,
    ).json()["data"]
    status_by_stage = {s["follow_up_stage"]: s["status"] for s in timeline}
    assert status_by_stage["30_day"] == "completed"
    assert status_by_stage["60_day"] == "pending"
    assert status_by_stage["90_day"] == "pending"

    # Record a networking connection
    conn = client.post(
        "/api/v1/impact/connections",
        json={
            "participant_id": participant["id"],
            "event_id": event["id"],
            "contact_name": "Dr. Musa Ibrahim",
            "connection_type": "mentor",
            "follow_up_occurred": True,
            "collaboration_started": True,
        },
    )
    assert conn.status_code == 201

    # Application analytics strictly separates intended vs completed actions
    app_analytics = client.get(
        f"/api/v1/analytics/events/{event['id']}/application", headers=admin_headers
    ).json()["data"]
    assert app_analytics["actions"]["intended_only_count"] == 1
    assert app_analytics["actions"]["completed_count"] == 1

    # Networking & Follow-Up analytics
    net_analytics = client.get(
        f"/api/v1/analytics/events/{event['id']}/networking", headers=admin_headers
    ).json()["data"]
    assert net_analytics["total_connections_reported"] == 1
    assert net_analytics["collaborations_started_count"] == 1

    fu_analytics = client.get(
        f"/api/v1/analytics/events/{event['id']}/follow-ups", headers=admin_headers
    ).json()["data"]
    stage_map = {s["follow_up_stage"]: s for s in fu_analytics["stages"]}
    assert stage_map["30_day"]["completed_count"] == 1
    assert stage_map["60_day"]["pending_count"] == 1

    # Reports & Exports (JSON, CSV, XLSX)
    event_report = client.get(
        f"/api/v1/reports/events/{event['id']}", headers=admin_headers
    )
    assert event_report.status_code == 200

    for fmt in ("json", "csv", "xlsx"):
        exp = client.post(
            f"/api/v1/reports/events/{event['id']}/export",
            headers=admin_headers,
            json={"export_format": fmt},
        )
        assert exp.status_code == 200
        assert Path(exp.json()["data"]["file_path"]).exists()

    part_exp = client.post(
        f"/api/v1/reports/participants/{participant['id']}/export",
        headers=admin_headers,
        json={"export_format": "csv", "event_id": event["id"]},
    )
    assert part_exp.status_code == 200
    assert Path(part_exp.json()["data"]["file_path"]).exists()
