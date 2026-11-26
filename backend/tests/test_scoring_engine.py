"""Tests for Scoring Engine including Scenarios A, B, C, qualitative exclusion, and score history."""

from fastapi.testclient import TestClient


def _setup_event_and_default_qn(client: TestClient, admin_headers: dict[str, str], slug: str):
    event = client.post(
        "/api/v1/events",
        headers=admin_headers,
        json={"slug": slug, "title": f"Event {slug}", "event_date": "2026-07-01"},
    ).json()["data"]
    qns = client.get("/api/v1/questionnaires").json()["data"]
    qn = next(q for q in qns if q["code"] == "cci-stem-assessment-v1")
    q_by_code = {link["question"]["code"]: link["question"]["id"] for link in qn["questions"]}
    return event, qn, q_by_code


def test_scenario_a_all_six_pillars_completed(
    client: TestClient, admin_headers: dict[str, str]
):
    """Scenario A: Participant completes all six pillars -> exact weighted impact score."""
    event, qn, q = _setup_event_and_default_qn(client, admin_headers, "scenario-a")
    p = client.post(
        "/api/v1/participants",
        headers=admin_headers,
        json={"full_name": "Scenario A User", "phone": "08030000001", "event_id": event["id"]},
    ).json()["data"]

    # Pillar scores engineered to exact values:
    # Engagement (15%): 5/5->100, 5/5->100, 5/5->100, yes->100, 5/5->100  => 100.0
    # Knowledge (20%): 4/5->75, 4/5->75, 4/5->75                          => 75.0
    # Workplace Excellence (15%): 5/5->100, 3/5->50                       => 75.0
    # Recognition & Rewards (15%): 4/5->75, 4/5->75                       => 75.0
    # Networking (20%): 5 connections->100, yes->100, 3/5->50             => 83.33
    # Post-Event Application (15%): yes->100, 3/5->50, no->0              => 50.0
    # Expected overall = 100*0.15 + 75*0.20 + 75*0.15 + 75*0.15 + 83.33*0.20 + 50*0.15
    #                  = 15 + 15 + 11.25 + 11.25 + 16.666 + 7.5 = 76.67
    responses = [
        {"question_id": q["sec_b_discussion_participation"], "response_numeric": 5},
        {"question_id": q["sec_b_speaker_interaction"], "response_numeric": 5},
        {"question_id": q["sec_b_peer_interaction"], "response_numeric": 5},
        {"question_id": q["sec_b_contributed_questions"], "response_boolean": True},
        {"question_id": q["sec_b_overall_engagement"], "response_numeric": 5},
        {"question_id": q["sec_c_new_perspectives"], "response_numeric": 4},
        {"question_id": q["sec_c_peer_knowledge"], "response_numeric": 4},
        {"question_id": q["sec_c_decision_influence"], "response_numeric": 4},
        {"question_id": q["sec_d_standards_understanding"], "response_numeric": 5},
        {"question_id": q["sec_d_org_performance_link"], "response_numeric": 3},
        {"question_id": q["sec_d_recognition_insights"], "response_numeric": 4},
        {"question_id": q["sec_d_unrecognised_impact"], "response_numeric": 4},
        {"question_id": q["sec_e_meaningful_connections_count"], "response_numeric": 5},
        {"question_id": q["sec_e_potential_collaboration"], "response_boolean": True},
        {"question_id": q["sec_e_follow_up_conversations"], "response_numeric": 3},
        {"question_id": q["sec_f_implemented_idea"], "response_boolean": True},
        {"question_id": q["sec_f_habits_changed"], "response_numeric": 3},
        {"question_id": q["sec_f_shared_with_colleagues"], "response_boolean": False},
    ]

    sub = client.post(
        "/api/v1/assessments/submit",
        json={
            "participant_id": p["id"],
            "event_id": event["id"],
            "questionnaire_id": qn["id"],
            "responses": responses,
        },
    )
    assert sub.status_code == 201

    calc = client.post(
        f"/api/v1/scoring/calculate/{p['id']}",
        headers=admin_headers,
        json={"event_id": event["id"]},
    )
    assert calc.status_code == 200, calc.text
    score = calc.json()["data"]
    assert score["status"] == "calculated"
    assert score["covered_pillars_count"] == 6
    assert score["weight_renormalised"] is False
    assert score["completeness_ratio"] == 1.0
    assert abs(score["overall_impact_score"] - 76.67) < 0.05
    assert score["post_event_application_score"] == 50.0
    assert score["immediate_impact_score"] is not None
    # Immediate positive experience must NOT fabricate sustained longitudinal impact
    assert score["sustained_impact_score"] is None

    # Recalculation preserves historical score record
    recalc = client.post(
        f"/api/v1/scoring/calculate/{p['id']}",
        headers=admin_headers,
        json={"event_id": event["id"]},
    )
    assert recalc.status_code == 200
    history = client.get(
        f"/api/v1/scoring/participants/{p['id']}", headers=admin_headers
    ).json()["data"]
    assert len(history) == 3
    assert sum(1 for h in history if h["is_latest"]) == 1


def test_scenario_b_four_pillars_completed_weight_renormalisation(
    client: TestClient, admin_headers: dict[str, str]
):
    """Scenario B: Only 4 pillars completed -> missing 2 excluded (NOT zeroed), weights renormalised."""
    event, qn, q = _setup_event_and_default_qn(client, admin_headers, "scenario-b")
    p = client.post(
        "/api/v1/participants",
        headers=admin_headers,
        json={"full_name": "Scenario B User", "phone": "08030000002", "event_id": event["id"]},
    ).json()["data"]

    # Complete ONLY 4 pillars (weights: 0.15, 0.20, 0.15, 0.15 -> sum = 0.65)
    # Missing: Networking (0.20) & Post-Event Application (0.15)
    # Scores: Engagement=100, Knowledge=50, Workplace=100, Recognition=50
    # Renormalised overall = (100*0.15 + 50*0.20 + 100*0.15 + 50*0.15) / 0.65
    #                      = (15 + 10 + 15 + 7.5) / 0.65 = 47.5 / 0.65 = 73.08
    responses = [
        {"question_id": q["sec_b_discussion_participation"], "response_numeric": 5},
        {"question_id": q["sec_c_new_perspectives"], "response_numeric": 3},
        {"question_id": q["sec_d_standards_understanding"], "response_numeric": 5},
        {"question_id": q["sec_d_recognition_insights"], "response_numeric": 3},
        {"question_id": q["sec_b_overall_engagement"], "response_numeric": 5},
    ]

    client.post(
        "/api/v1/assessments/submit",
        json={
            "participant_id": p["id"],
            "event_id": event["id"],
            "questionnaire_id": qn["id"],
            "responses": responses,
        },
    )

    score = client.post(
        f"/api/v1/scoring/calculate/{p['id']}",
        headers=admin_headers,
        json={"event_id": event["id"]},
    ).json()["data"]

    assert score["status"] == "partial"
    assert score["covered_pillars_count"] == 4
    assert score["weight_renormalised"] is True
    assert abs(score["overall_impact_score"] - 73.08) < 0.05
    assert score["post_event_application_score"] is None

    dim_by_code = {d["pillar_code"]: d for d in score["dimension_scores"]}
    assert dim_by_code["networking_and_relationships"]["status"] == "missing"
    assert dim_by_code["networking_and_relationships"]["normalised_score"] is None
    assert dim_by_code["post_event_application"]["status"] == "missing"
    assert dim_by_code["post_event_application"]["normalised_score"] is None
    eff_sum = sum(
        d["effective_weight"]
        for d in score["dimension_scores"]
        if d["effective_weight"] is not None
    )
    assert abs(eff_sum - 1.0) < 0.001


def test_scenario_c_insufficient_assessment_data(
    client: TestClient, admin_headers: dict[str, str]
):
    """Scenario C: Not enough scorable questions completed -> insufficient_data."""
    event, qn, q = _setup_event_and_default_qn(client, admin_headers, "scenario-c")
    p = client.post(
        "/api/v1/participants",
        headers=admin_headers,
        json={"full_name": "Scenario C User", "phone": "08030000003", "event_id": event["id"]},
    ).json()["data"]

    # Only qualitative text + 1 single scorable question (below min_pillars_required=2 & min_completeness=0.25)
    client.post(
        "/api/v1/assessments/submit",
        json={
            "participant_id": p["id"],
            "event_id": event["id"],
            "questionnaire_id": qn["id"],
            "responses": [
                {
                    "question_id": q["sec_c_most_important_takeaway"],
                    "response_text": "Loved the panel discussion.",
                },
                {
                    "question_id": q["sec_b_discussion_participation"],
                    "response_numeric": 5,
                },
            ],
        },
    )

    score = client.post(
        f"/api/v1/scoring/calculate/{p['id']}",
        headers=admin_headers,
        json={"event_id": event["id"]},
    ).json()["data"]

    assert score["status"] == "insufficient_data"
    assert score["overall_impact_score"] is None
    assert score["covered_pillars_count"] == 1
    assert score["completeness_ratio"] < 0.25
