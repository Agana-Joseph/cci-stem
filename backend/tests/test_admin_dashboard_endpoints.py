"""Tests covering all Admin Panel backend endpoints: auth, users, audit logs,
participant directory, assessments list, qualitative feedback, impact lists,
demographics/distributions analytics, report history, and direct file downloads.
"""

from datetime import date


def _bootstrap_event_and_submission(client, admin_headers):
    """Create an event, two participants, a published questionnaire, and one submission."""
    ev_resp = client.post(
        "/api/v1/events",
        headers=admin_headers,
        json={
            "slug": "cci-admin-panel-test-2026",
            "title": "CCI STEM Admin Panel Test 2026",
            "event_date": "2026-11-24",
            "location": "Lagos",
            "status": "active",
        },
    )
    assert ev_resp.status_code == 201
    event_id = ev_resp.json()["data"]["id"]

    p1_resp = client.post(
        "/api/v1/participants",
        headers=admin_headers,
        json={
            "full_name": "Adaeze Okafor",
            "email": "adaeze@example.com",
            "phone": "+2348011112222",
            "current_role": "Data Engineer",
            "industry": "FinTech",
            "organisation": "PayCo",
            "years_of_experience": 6,
            "consent_given": True,
            "event_id": event_id,
        },
    )
    assert p1_resp.status_code == 201
    p1_id = p1_resp.json()["data"]["id"]

    p2_resp = client.post(
        "/api/v1/participants",
        headers=admin_headers,
        json={
            "full_name": "Tunde Bello",
            "email": "tunde@example.com",
            "phone": "+2348033334444",
            "current_role": "ML Scientist",
            "industry": "HealthTech",
            "organisation": "MedLabs",
            "years_of_experience": 4,
            "consent_given": True,
            "event_id": event_id,
        },
    )
    assert p2_resp.status_code == 201
    p2_id = p2_resp.json()["data"]["id"]

    # Mark p1 confirmed attendance
    att_resp = client.post(
        f"/api/v1/events/{event_id}/attendance",
        headers=admin_headers,
        json={"participant_id": p1_id, "attendance_status": "confirmed"},
    )
    assert att_resp.status_code == 200

    # Grab seeded pillars and reflective card questions
    pillars = client.get("/api/v1/pillars").json()["data"]
    eng_pillar_id = pillars[0]["id"]
    cards = client.get("/api/v1/question-cards").json()["data"]
    reflective_card_id = cards[0]["id"]
    reflective_q_id = cards[0]["questions"][0]["id"]

    # Create one scorable rating question and one qualitative open-text question
    q_rating = client.post(
        "/api/v1/questions",
        headers=admin_headers,
        json={
            "code": "adm_test_rating",
            "question_text": "Rate overall session quality",
            "question_type": "rating_scale",
            "is_required": True,
            "is_scorable": True,
            "allow_explanation": True,
            "validation_config": {"min": 1, "max": 5},
            "pillar_ids": [eng_pillar_id],
        },
    ).json()["data"]

    q_takeaway = client.post(
        "/api/v1/questions",
        headers=admin_headers,
        json={
            "code": "adm_test_takeaway",
            "question_text": "What was your most important takeaway?",
            "question_type": "long_text",
            "is_required": False,
            "is_scorable": False,
            "pillar_ids": [eng_pillar_id],
        },
    ).json()["data"]

    qn = client.post(
        "/api/v1/questionnaires",
        headers=admin_headers,
        json={
            "code": "adm_test_qn",
            "title": "Admin Test Post-Event Survey",
            "event_id": event_id,
            "questionnaire_type": "post_event",
            "sections": [
                {
                    "code": "B",
                    "title": "Event Engagement",
                    "display_order": 1,
                    "question_ids": [q_rating["id"], q_takeaway["id"], reflective_q_id],
                }
            ],
        },
    ).json()["data"]
    pub = client.post(f"/api/v1/questionnaires/{qn['id']}/publish", headers=admin_headers)
    assert pub.status_code == 200

    # Submit assessment for p1
    sub_resp = client.post(
        "/api/v1/assessments/submit",
        json={
            "phone": "+2348011112222",
            "event_id": event_id,
            "questionnaire_id": qn["id"],
            "responses": [
                {
                    "question_id": q_rating["id"],
                    "response_numeric": 5,
                    "explanation_text": "Hands-on engineering depth was outstanding.",
                },
                {
                    "question_id": q_takeaway["id"],
                    "response_text": "Documenting impact metrics early drives career visibility.",
                },
                {
                    "question_id": reflective_q_id,
                    "response_text": "Consistent mentorship and strong problem framing.",
                },
            ],
        },
    )
    assert sub_resp.status_code == 201
    submission_id = sub_resp.json()["data"]["id"]

    return {
        "event_id": event_id,
        "p1_id": p1_id,
        "p2_id": p2_id,
        "pillar_id": eng_pillar_id,
        "reflective_card_id": reflective_card_id,
        "reflective_q_id": reflective_q_id,
        "q_rating_id": q_rating["id"],
        "q_takeaway_id": q_takeaway["id"],
        "questionnaire_id": qn["id"],
        "submission_id": submission_id,
    }


def test_admin_auth_users_and_audit_logs(client, admin_headers):
    # Unauthenticated request rejected
    unauth = client.get("/api/v1/admin/me")
    assert unauth.status_code == 401

    # Bootstrap admin identity works
    me = client.get("/api/v1/admin/me", headers=admin_headers)
    assert me.status_code == 200
    assert me.json()["data"]["is_admin"] is True
    assert me.json()["data"]["role"] == "super_admin"

    # Provision a new analyst administrator
    created = client.post(
        "/api/v1/admin/users",
        headers=admin_headers,
        json={
            "full_name": "Chioma Analyst",
            "email": "chioma.analyst@cci.org",
            "role": "analyst",
        },
    )
    assert created.status_code == 201
    new_admin = created.json()["data"]
    assert new_admin["api_key"].startswith("cci_")
    assert new_admin["role"] == "analyst"

    # Analyst can call /admin/me with their own API key
    analyst_headers = {"X-API-Key": new_admin["api_key"]}
    analyst_me = client.get("/api/v1/admin/me", headers=analyst_headers)
    assert analyst_me.status_code == 200
    assert analyst_me.json()["data"]["full_name"] == "Chioma Analyst"
    assert analyst_me.json()["data"]["email"] == "chioma.analyst@cci.org"
    assert analyst_me.json()["data"]["role"] == "analyst"

    # Analyst cannot list or create admin users (super_admin only -> 403)
    forbidden = client.get("/api/v1/admin/users", headers=analyst_headers)
    assert forbidden.status_code == 403

    # Super admin can list and deactivate the analyst
    users_list = client.get("/api/v1/admin/users", headers=admin_headers)
    assert users_list.status_code == 200
    assert len(users_list.json()["data"]) == 1
    assert "api_key_hash" not in users_list.json()["data"][0]

    deact = client.patch(
        f"/api/v1/admin/users/{new_admin['id']}",
        headers=admin_headers,
        json={"is_active": False},
    )
    assert deact.status_code == 200
    assert deact.json()["data"]["is_active"] is False

    # Deactivated key is rejected
    revoked = client.get("/api/v1/admin/me", headers=analyst_headers)
    assert revoked.status_code == 401

    # Audit logs contain recorded admin actions
    logs = client.get("/api/v1/admin/audit-logs?limit=20", headers=admin_headers)
    assert logs.status_code == 200
    actions = {row["action"] for row in logs.json()["data"]}
    assert "admin_user.create" in actions
    assert "admin_user.update" in actions


def test_participant_directory_assessments_and_feedback(client, admin_headers):
    ctx = _bootstrap_event_and_submission(client, admin_headers)

    # Unauthenticated calls blocked
    assert client.get("/api/v1/participants").status_code == 401
    assert client.get("/api/v1/assessments").status_code == 401
    assert client.get("/api/v1/feedback").status_code == 401

    # Global participant directory with search, filter, and status enrichment
    directory = client.get(
        f"/api/v1/participants?event_id={ctx['event_id']}&sort_by=full_name&sort_order=asc",
        headers=admin_headers,
    )
    assert directory.status_code == 200
    body = directory.json()
    assert body["meta"]["total"] == 2
    assert body["data"][0]["full_name"] == "Adaeze Okafor"
    assert body["data"][0]["assessment_status"] == "submitted"
    assert body["data"][0]["attendance_status"] == "confirmed"
    assert body["data"][1]["full_name"] == "Tunde Bello"
    assert body["data"][1]["assessment_status"] == "pending"

    # Filter by has_assessment=false and industry
    pending_only = client.get(
        f"/api/v1/participants?event_id={ctx['event_id']}&has_assessment=false&industry=Health",
        headers=admin_headers,
    )
    assert pending_only.status_code == 200
    assert pending_only.json()["meta"]["total"] == 1
    assert pending_only.json()["data"][0]["id"] == ctx["p2_id"]

    # Assessments list with search and date filtering
    today_iso = date.today().isoformat()
    subs = client.get(
        f"/api/v1/assessments?event_id={ctx['event_id']}&q=Adaeze&date_from={today_iso}",
        headers=admin_headers,
    )
    assert subs.status_code == 200
    sub_items = subs.json()["data"]
    assert len(sub_items) == 1
    assert sub_items[0]["id"] == ctx["submission_id"]
    assert sub_items[0]["participant_name"] == "Adaeze Okafor"
    assert sub_items[0]["responses_count"] == 3

    # Qualitative feedback filter (is_scorable=false preserves exact wording)
    fb_qual = client.get(
        f"/api/v1/feedback?event_id={ctx['event_id']}&is_scorable=false&section_code=B",
        headers=admin_headers,
    )
    assert fb_qual.status_code == 200
    fb_items = fb_qual.json()["data"]
    assert len(fb_items) == 2
    texts = {item["response_text"] for item in fb_items}
    assert "Documenting impact metrics early drives career visibility." in texts
    assert "Consistent mentorship and strong problem framing." in texts

    # Filter feedback by reflective card_id and full-text search
    fb_card = client.get(
        f"/api/v1/feedback?card_id={ctx['reflective_card_id']}&q=mentorship",
        headers=admin_headers,
    )
    assert fb_card.status_code == 200
    assert fb_card.json()["meta"]["total"] == 1
    assert fb_card.json()["data"][0]["question_id"] == ctx["reflective_q_id"]


def test_impact_lists_demographics_distributions_and_report_downloads(client, admin_headers):
    ctx = _bootstrap_event_and_submission(client, admin_headers)

    # Log action, connection, and outcome with evidence
    client.post(
        "/api/v1/impact/actions",
        json={
            "participant_id": ctx["p1_id"],
            "event_id": ctx["event_id"],
            "title": "Introduce impact scorecards",
            "action_status": "completed",
            "action_category": "workplace_improvement",
        },
    )
    client.post(
        "/api/v1/impact/connections",
        json={
            "participant_id": ctx["p1_id"],
            "event_id": ctx["event_id"],
            "contact_name": "Dr. Ngozi Eze",
            "connection_type": "mentor",
            "follow_up_occurred": True,
            "collaboration_started": True,
        },
    )
    client.post(
        "/api/v1/impact/outcomes",
        json={
            "participant_id": ctx["p1_id"],
            "event_id": ctx["event_id"],
            "outcome_type": "productivity_gain",
            "title": "Reduced pipeline latency by 25%",
            "evidence_items": [
                {"evidence_type": "url", "reference_url": "https://example.com/proof"}
            ],
        },
    )

    # Admin list endpoints for actions, connections, and outcomes
    actions_resp = client.get(
        f"/api/v1/impact/actions?event_id={ctx['event_id']}&action_status=completed",
        headers=admin_headers,
    )
    assert actions_resp.status_code == 200
    assert actions_resp.json()["meta"]["total"] == 1
    assert actions_resp.json()["data"][0]["participant_name"] == "Adaeze Okafor"

    conns_resp = client.get(
        f"/api/v1/impact/connections?event_id={ctx['event_id']}&connection_type=mentor",
        headers=admin_headers,
    )
    assert conns_resp.status_code == 200
    assert conns_resp.json()["meta"]["total"] == 1
    assert conns_resp.json()["data"][0]["contact_name"] == "Dr. Ngozi Eze"

    outcomes_resp = client.get(
        f"/api/v1/impact/outcomes?event_id={ctx['event_id']}&verification_status=pending_review",
        headers=admin_headers,
    )
    assert outcomes_resp.status_code == 200
    assert outcomes_resp.json()["meta"]["total"] == 1
    assert outcomes_resp.json()["data"][0]["evidence_classification"] == "documented"
    assert len(outcomes_resp.json()["data"][0]["evidence_items"]) == 1

    # Demographics analytics
    demo_resp = client.get(
        f"/api/v1/analytics/events/{ctx['event_id']}/demographics",
        headers=admin_headers,
    )
    assert demo_resp.status_code == 200
    demo = demo_resp.json()["data"]
    assert demo["total_participants"] == 2
    assert demo["years_of_experience"]["average"] == 5.0
    industries = {b["label"] for b in demo["by_industry"]["buckets"]}
    assert industries == {"FinTech", "HealthTech"}

    # Question response distributions analytics
    dist_resp = client.get(
        f"/api/v1/analytics/events/{ctx['event_id']}/distributions?questionnaire_id={ctx['questionnaire_id']}",
        headers=admin_headers,
    )
    assert dist_resp.status_code == 200
    dist_data = dist_resp.json()["data"]
    assert dist_data["respondents_count"] == 1
    rating_q = next(
        q for q in dist_data["questions"] if q["question_id"] == ctx["q_rating_id"]
    )
    assert rating_q["response_count"] == 1
    assert rating_q["numeric_stats"]["average"] == 5.0
    assert rating_q["distribution"][0]["value"] == "5"

    # Direct report downloads (CSV, XLSX, JSON) + export records history
    csv_dl = client.get(
        f"/api/v1/reports/events/{ctx['event_id']}/download?export_format=csv",
        headers=admin_headers,
    )
    assert csv_dl.status_code == 200
    assert "text/csv" in csv_dl.headers["content-type"]
    assert "attachment; filename=" in csv_dl.headers["content-disposition"]
    assert "pillar_code" in csv_dl.text

    xlsx_dl = client.get(
        f"/api/v1/reports/participants/{ctx['p1_id']}/download?export_format=xlsx",
        headers=admin_headers,
    )
    assert xlsx_dl.status_code == 200
    assert "spreadsheetml" in xlsx_dl.headers["content-type"]
    assert len(xlsx_dl.content) > 100

    records_resp = client.get(
        f"/api/v1/reports/records?event_id={ctx['event_id']}",
        headers=admin_headers,
    )
    assert records_resp.status_code == 200
    assert records_resp.json()["meta"]["total"] >= 1
