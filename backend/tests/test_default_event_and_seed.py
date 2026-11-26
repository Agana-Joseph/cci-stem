"""Comprehensive verification suite for the CCI STEM Connect default event,
full Sections A-F initial assessment, 3 reflection cards, 4 stages, 30/60/90-day
follow-up questionnaires, scoring framework, seed idempotency, and privacy.
"""

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.seed import seed_reference_data
from app.models.impact import FollowUpStageConfig
from app.models.participant import Event, EventObjective, EventPillar
from app.models.questionnaire import (
    Question,
    QuestionCard,
    QuestionCategory,
    Questionnaire,
)
from app.models.scoring import MeasurementPillar, ScoringRule


def test_default_event_bundle_objectives_pillars_categories_cards_and_stages(
    client: TestClient, admin_headers: dict[str, str]
):
    # 1, 2, 3: Default published event retrievable without manual event selection
    res = client.get("/api/v1/events/default")
    assert res.status_code == 200, res.text
    bundle = res.json()["data"]

    event = bundle["event"]
    assert event["slug"] == "cci-stem-connect"
    assert event["title"] == "CCI STEM Connect"
    assert event["headline"] == "Connect. Grow. Improve. Excel."
    assert event["status"] == "published"
    assert event["is_default"] is True
    assert event["assessment_enabled"] is True
    assert event["follow_up_enabled"] is True
    assert event["public_visibility"] is True
    assert event["reflection_cards_enabled"] is True
    # Confirmed date/venue must NOT be fabricated
    assert event["event_date"] is None
    assert event["location"] is None

    # Default event appears first in GET /api/v1/events
    listed_events = client.get("/api/v1/events").json()["data"]
    assert listed_events[0]["slug"] == "cci-stem-connect"

    # 4: Seven event objectives in exact order
    objectives = bundle["objectives"]
    assert len(objectives) == 7
    assert objectives[0]["objective_text"] == (
        "Encourage meaningful professional engagement and knowledge sharing."
    )
    assert objectives[6]["objective_text"] == (
        "Measure the immediate and long-term value participants derive from the event."
    )
    obj_endpoint = client.get(f"/api/v1/events/{event['id']}/objectives").json()["data"]
    assert len(obj_endpoint) == 7

    # 5: Six measurement pillars linked to event with weights summing to 1.0 (100%)
    pillars = bundle["measurement_pillars"]
    assert len(pillars) == 6
    assert abs(sum(p["default_weight"] for p in pillars) - 1.0) < 0.001

    # Question categories (9 configured categories)
    categories = client.get("/api/v1/question-categories").json()["data"]
    assert len(categories) == 9
    assert len(bundle["question_categories"]) == 9

    # 6 & 7: Initial assessment has 6 sections (A-F) and all 35 questions
    initial_qn = bundle["default_questionnaire"]
    assert initial_qn["code"] == "cci-stem-connect-initial-assessment"
    assert initial_qn["title"] == "CCI STEM Connect Initial Assessment"
    assert initial_qn["status"] == "published"
    assert initial_qn["assessment_stage"] == "immediate"
    assert len(initial_qn["sections"]) == 6
    assert len(initial_qn["questions"]) == 35

    q_by_code = {item["question"]["code"]: item["question"] for item in initial_qn["questions"]}
    # Verify key question types and options (Check #9)
    assert q_by_code["a2_email_address"]["question_type"] == "email"
    assert q_by_code["a3_active_phone_number"]["question_type"] == "phone"
    assert len(q_by_code["a5_industry_sector"]["options"]) == 10
    assert len(q_by_code["a7_years_of_experience"]["options"]) == 5
    assert len(q_by_code["b1_active_participation"]["options"]) == 5
    assert q_by_code["b1_active_participation"]["options"][0]["option_label"] == "Not actively involved"
    assert len(q_by_code["e5_desired_relationships"]["options"]) == 7
    assert len(q_by_code["f2_areas_to_improve"]["options"]) == 10
    # Qualitative questions are never marked scorable
    for qual_code in (
        "c1_most_important_insight",
        "c5_decision_influencing_idea",
        "d1_describe_workplace_excellence",
        "d4_unrecognised_excellence_consequences",
        "d5_organisations_encourage_excellence",
        "e5_desired_relationships",
        "f1_intended_idea_to_apply",
    ):
        assert q_by_code[qual_code]["is_scorable"] is False

    # 8: Three original reflection cards with exact preserved wording
    cards = bundle["reflection_cards"]
    assert len(cards) == 3
    card_prompts = [c["questions"][0]["question_text"] for c in cards]
    assert card_prompts == [
        "Which do you think matters more early in your tech career?",
        "Which of your skills make your work easier?",
        "What can you teach someone in 10 minutes?",
    ]
    for c in cards:
        assert c["questions"][0]["is_scorable"] is False

    # 10: Four assessment stages + three published follow-up questionnaires (6 + 6 + 7 questions)
    stages = bundle["assessment_stages"]
    assert [s["stage_code"] for s in stages] == ["immediate", "30_day", "60_day", "90_day"]
    assert all(s["questionnaire_id"] is not None for s in stages)

    fu_qns = {q["code"]: q for q in bundle["follow_up_questionnaires"]}
    assert len(fu_qns["cci-stem-connect-30-day-follow-up"]["questions"]) == 6
    assert len(fu_qns["cci-stem-connect-60-day-follow-up"]["questions"]) == 6
    assert len(fu_qns["cci-stem-connect-90-day-follow-up"]["questions"]) == 7

    # 11 & 12: Active scoring framework weights total 100% and rules are retrievable
    frameworks = client.get("/api/v1/scoring/frameworks", headers=admin_headers).json()["data"]
    active_fw = next(f for f in frameworks if f["is_active"])
    assert active_fw["name"] == "CCI STEM Connect Participant Impact Framework"
    assert abs(sum(d["weight"] for d in active_fw["dimensions"]) - 1.0) < 0.001
    assert len(active_fw["rules"]) >= 24

    # 16: Historical questionnaire versions remain intact
    all_qns = {q["code"] for q in client.get("/api/v1/questionnaires").json()["data"]}
    assert "cci-stem-connect-initial-assessment" in all_qns
    assert "cci-stem-assessment-v1" in all_qns


def test_seed_idempotency_no_duplicates(db_session: Session):
    """Check #17: Re-running seed_reference_data never creates duplicates."""
    def _snapshot() -> dict[str, int]:
        return {
            "events": int(db_session.execute(select(func.count(Event.id))).scalar_one()),
            "objectives": int(db_session.execute(select(func.count(EventObjective.id))).scalar_one()),
            "pillars": int(db_session.execute(select(func.count(MeasurementPillar.id))).scalar_one()),
            "event_pillars": int(db_session.execute(select(func.count(EventPillar.id))).scalar_one()),
            "categories": int(db_session.execute(select(func.count(QuestionCategory.id))).scalar_one()),
            "cards": int(db_session.execute(select(func.count(QuestionCard.id))).scalar_one()),
            "questions": int(db_session.execute(select(func.count(Question.id))).scalar_one()),
            "questionnaires": int(db_session.execute(select(func.count(Questionnaire.id))).scalar_one()),
            "stages": int(db_session.execute(select(func.count(FollowUpStageConfig.id))).scalar_one()),
            "rules": int(db_session.execute(select(func.count(ScoringRule.id))).scalar_one()),
        }

    before = _snapshot()
    rerun_counts = seed_reference_data(db_session)
    after = _snapshot()

    assert before == after
    assert all(v == 0 for v in rerun_counts.values()), rerun_counts


def test_default_event_end_to_end_submission_scoring_followups_and_privacy(
    client: TestClient, admin_headers: dict[str, str]
):
    """Checks #13, #14, #15, #18, #19, #20 against the default CCI STEM Connect event."""
    bundle = client.get("/api/v1/events/default").json()["data"]
    event_id = bundle["event"]["id"]
    initial_qn = bundle["default_questionnaire"]
    q_by_code = {item["question"]["code"]: item["question"]["id"] for item in initial_qn["questions"]}
    card_q_id = bundle["reflection_cards"][0]["questions"][0]["id"]

    # 19: Empty default event analytics report zero responses and null averages (never fabricated)
    empty_overview = client.get(
        f"/api/v1/analytics/events/{event_id}/overview", headers=admin_headers
    ).json()["data"]
    assert empty_overview["impact_scores"]["overall_event_impact"]["average"] is None
    assert empty_overview["impact_scores"]["overall_event_impact"]["response_count"] == 0
    assert empty_overview["participation"]["attendance_rate"] is None

    # Register participant on the default CCI STEM Connect event
    p = client.post(
        "/api/v1/participants",
        headers=admin_headers,
        json={
            "full_name": "Chidinma Nwosu",
            "email": "chidinma@example.com",
            "phone": "0807 111 9988",
            "current_role": "Backend Engineer",
            "industry": "Technology",
            "organisation": "TechBridge",
            "years_of_experience": 5,
            "consent_given": True,
            "event_id": event_id,
        },
    ).json()["data"]

    # 13: Submit complete initial assessment + reflection card answer
    responses = [
        {"question_id": q_by_code["a1_full_name"], "response_text": "Chidinma Nwosu"},
        {"question_id": q_by_code["a2_email_address"], "response_text": "chidinma@example.com"},
        {"question_id": q_by_code["a3_active_phone_number"], "response_text": "08071119988"},
        {"question_id": q_by_code["a4_current_professional_role"], "response_text": "Backend Engineer"},
        {"question_id": q_by_code["a5_industry_sector"], "response_text": "technology"},
        {"question_id": q_by_code["a7_years_of_experience"], "response_text": "3_5_years"},
        {"question_id": q_by_code["a8_motivation_to_attend"], "response_text": "Grow professionally and connect with Christian STEM peers."},
        {"question_id": q_by_code["b1_active_participation"], "response_numeric": 5},
        {"question_id": q_by_code["b2_speaker_interaction"], "response_text": "yes"},
        {"question_id": q_by_code["b3_peer_interaction"], "response_numeric": 4},
        {"question_id": q_by_code["b4_contributed_discussions"], "response_text": "yes_actively"},
        {"question_id": q_by_code["b5_discussion_relevance"], "response_numeric": 5},
        {"question_id": q_by_code["b6_overall_engagement"], "response_numeric": 5},
        {"question_id": q_by_code["c1_most_important_insight"], "response_text": "Excellence is a daily discipline."},
        {"question_id": q_by_code["c2_new_perspectives"], "response_text": "yes_significantly"},
        {"question_id": q_by_code["c3_understanding_excellence"], "response_numeric": 5},
        {"question_id": q_by_code["c4_productivity_responsibility_influence"], "response_numeric": 4},
        {"question_id": q_by_code["c5_decision_influencing_idea"], "response_text": "Document measurable impact every sprint."},
        {"question_id": q_by_code["d1_describe_workplace_excellence"], "response_text": "Delivering reliable work with integrity."},
        {"question_id": q_by_code["d2_integrity_responsibility_importance"], "response_numeric": 5},
        {"question_id": q_by_code["d3_recognition_rewards_importance"], "response_numeric": 4},
        {"question_id": q_by_code["d4_unrecognised_excellence_consequences"], "response_text": "Disengagement and high attrition."},
        {"question_id": q_by_code["d5_organisations_encourage_excellence"], "response_text": "Transparent feedback and merit-based rewards."},
        {"question_id": q_by_code["d6_personal_commitment_standards"], "response_numeric": 5},
        {"question_id": q_by_code["e1_meaningful_connections"], "response_text": "yes_several"},
        {"question_id": q_by_code["e2_collaboration_opportunities"], "response_text": "yes"},
        {"question_id": q_by_code["e3_mentorship_opportunities"], "response_text": "possibly"},
        {"question_id": q_by_code["e4_followed_up_professionals"], "response_text": "yes"},
        {"question_id": q_by_code["e5_desired_relationships"], "response_json": ["mentorship", "collaboration"]},
        {"question_id": q_by_code["f1_intended_idea_to_apply"], "response_text": "Weekly reflection and peer code reviews."},
        {"question_id": q_by_code["f2_areas_to_improve"], "response_json": ["work_ethic_and_discipline", "leadership"]},
        {"question_id": q_by_code["f3_intend_to_share_knowledge"], "response_text": "yes"},
        {"question_id": q_by_code["f4_action_within_30_days"], "response_text": "Lead a team session on engineering standards."},
        {"question_id": q_by_code["f5_commitment_to_apply"], "response_numeric": 5},
        # Also include a reflection card response
        {"question_id": card_q_id, "response_text": "Building strong fundamentals and consistent character."},
    ]
    sub_resp = client.post(
        "/api/v1/assessments/submit",
        json={
            "phone": "08071119988",
            "event_id": event_id,
            "questionnaire_id": initial_qn["id"],
            "responses": responses,
        },
    )
    assert sub_resp.status_code == 201, sub_resp.text
    sub_id = sub_resp.json()["data"]["id"]

    # Calculate score on default event -> all 6 pillars covered, completeness 1.0
    score_resp = client.post(
        f"/api/v1/scoring/calculate/{p['id']}",
        headers=admin_headers,
        json={"event_id": event_id},
    )
    assert score_resp.status_code == 200, score_resp.text
    score = score_resp.json()["data"]
    assert score["status"] == "calculated"
    assert score["covered_pillars_count"] == 6
    assert score["completeness_ratio"] == 1.0
    assert score["overall_impact_score"] is not None
    assert score["sustained_impact_score"] is None

    # 14: Authorised admin retrieves individual responses & reflection card feedback
    admin_sub = client.get(f"/api/v1/assessments/{sub_id}", headers=admin_headers)
    assert admin_sub.status_code == 200
    assert len(admin_sub.json()["data"]["responses"]) == 35

    card_fb = client.get(
        f"/api/v1/feedback?card_id={bundle['reflection_cards'][0]['id']}",
        headers=admin_headers,
    )
    assert card_fb.status_code == 200
    assert card_fb.json()["meta"]["total"] == 1
    assert (
        card_fb.json()["data"][0]["response_text"]
        == "Building strong fundamentals and consistent character."
    )

    # 15: Follow-ups schedule cleanly even when event_date is None (30/60/90-day)
    sched_resp = client.post(
        "/api/v1/follow-ups",
        headers=admin_headers,
        json={"participant_id": p["id"], "event_id": event_id},
    )
    assert sched_resp.status_code == 201, sched_resp.text
    scheds = sched_resp.json()["data"]
    assert [s["follow_up_stage"] for s in scheds] == ["30_day", "60_day", "90_day"]

    fu_submit = client.post(
        f"/api/v1/follow-ups/{scheds[0]['id']}/submit",
        json={
            "responses": {"fu_30d_01_applied_insights": "yes"},
            "reported_actions": [
                {
                    "title": "Led team standards review",
                    "action_status": "completed",
                    "action_category": "workplace_improvement",
                }
            ],
        },
    )
    assert fu_submit.status_code == 201

    # 20: Private participant data is NOT exposed through public endpoints
    assert "participants" not in bundle
    assert client.get(f"/api/v1/assessments/{sub_id}").status_code == 401
    assert client.get(f"/api/v1/participants/{p['id']}").status_code == 401
    assert client.get("/api/v1/participants").status_code == 401
    assert client.get("/api/v1/feedback").status_code == 401
    assert client.get(f"/api/v1/analytics/events/{event_id}/overview").status_code == 401


def test_assessment_submit_auto_registers_new_participant_and_event_registration(
    client: TestClient, admin_headers: dict[str, str]
):
    """First-time attendees hitting Submit Assessment are auto-registered without prior admin signup."""
    bundle = client.get("/api/v1/events/default").json()["data"]
    event_id = bundle["event"]["id"]
    initial_qn = bundle["default_questionnaire"]
    q_by_code = {item["question"]["code"]: item["question"]["id"] for item in initial_qn["questions"]}

    # Invalid submission (missing required questions) must NOT auto-register an orphan participant
    bad = client.post(
        "/api/v1/assessments/submit",
        json={
            "phone": "+2348099990000",
            "email": "orphan@example.com",
            "event_id": event_id,
            "questionnaire_id": initial_qn["id"],
            "responses": [],
        },
    )
    assert bad.status_code == 422
    lookup_orphan = client.get(
        "/api/v1/participants/lookup",
        headers=admin_headers,
        params={"phone": "+2348099990000"},
    )
    assert lookup_orphan.json()["data"]["matched"] is False

    # Valid submission from a brand-new unregistered attendee auto-creates participant + registration
    responses = [
        {"question_id": q_by_code["a1_full_name"], "response_text": "Agana Omahi"},
        {"question_id": q_by_code["a2_email_address"], "response_text": "josephagana6@gmail.com"},
        {"question_id": q_by_code["a3_active_phone_number"], "response_text": "+2348020898617"},
        {"question_id": q_by_code["a4_current_professional_role"], "response_text": "Senior Engineer"},
        {"question_id": q_by_code["a5_industry_sector"], "response_text": "business_and_entrepreneurship"},
        {"question_id": q_by_code["a6_organisation"], "response_text": "Aceldus Technologies LTD"},
        {"question_id": q_by_code["a7_years_of_experience"], "response_text": "6_10_years"},
        {"question_id": q_by_code["a8_motivation_to_attend"], "response_text": "Networking and growth"},
        {"question_id": q_by_code["b1_active_participation"], "response_numeric": 4},
        {"question_id": q_by_code["b2_speaker_interaction"], "response_text": "no"},
        {"question_id": q_by_code["b3_peer_interaction"], "response_numeric": 4},
        {"question_id": q_by_code["b4_contributed_discussions"], "response_text": "yes_occasionally"},
        {"question_id": q_by_code["b5_discussion_relevance"], "response_numeric": 4},
        {"question_id": q_by_code["b6_overall_engagement"], "response_numeric": 4},
        {"question_id": q_by_code["c1_most_important_insight"], "response_text": "To be excellent"},
        {"question_id": q_by_code["c2_new_perspectives"], "response_text": "yes_to_some_extent"},
        {"question_id": q_by_code["c3_understanding_excellence"], "response_numeric": 4},
        {"question_id": q_by_code["c4_productivity_responsibility_influence"], "response_numeric": 4},
        {"question_id": q_by_code["c5_decision_influencing_idea"], "response_text": "Be consistent"},
        {"question_id": q_by_code["d1_describe_workplace_excellence"], "response_text": "Doing great work"},
        {"question_id": q_by_code["d2_integrity_responsibility_importance"], "response_numeric": 5},
        {"question_id": q_by_code["d3_recognition_rewards_importance"], "response_numeric": 4},
        {"question_id": q_by_code["d4_unrecognised_excellence_consequences"], "response_text": "Demotivation"},
        {"question_id": q_by_code["d5_organisations_encourage_excellence"], "response_text": "To appreciate"},
        {"question_id": q_by_code["d6_personal_commitment_standards"], "response_numeric": 4},
        {"question_id": q_by_code["e1_meaningful_connections"], "response_text": "yes_one_or_two"},
        {"question_id": q_by_code["e2_collaboration_opportunities"], "response_text": "possibly"},
        {"question_id": q_by_code["e3_mentorship_opportunities"], "response_text": "no"},
        {"question_id": q_by_code["e4_followed_up_professionals"], "response_text": "no"},
        {"question_id": q_by_code["f1_intended_idea_to_apply"], "response_text": "Be community active"},
        {"question_id": q_by_code["f2_areas_to_improve"], "response_json": ["leadership", "work_ethic_and_discipline"]},
        {"question_id": q_by_code["f3_intend_to_share_knowledge"], "response_text": "yes"},
        {"question_id": q_by_code["f4_action_within_30_days"], "response_text": "Apply workplace excellence"},
        {"question_id": q_by_code["f5_commitment_to_apply"], "response_numeric": 4},
    ]
    sub = client.post(
        "/api/v1/assessments/submit",
        json={
            "phone": "+2348020898617",
            "email": "josephagana6@gmail.com",
            "event_id": event_id,
            "questionnaire_id": initial_qn["id"],
            "responses": responses,
        },
    )
    assert sub.status_code == 201, sub.text
    participant_id = sub.json()["data"]["participant_id"]

    # Verify participant profile was auto-created and registered for CCI STEM Connect
    p_profile = client.get(
        f"/api/v1/participants/{participant_id}", headers=admin_headers
    ).json()["data"]
    assert p_profile["full_name"] == "Agana Omahi"
    assert p_profile["email_normalised"] == "josephagana6@gmail.com"
    assert p_profile["phone_normalised"] == "+2348020898617"
    assert p_profile["current_role"] == "Senior Engineer"
    assert p_profile["industry"] == "Business and Entrepreneurship"
    assert p_profile["organisation"] == "Aceldus Technologies LTD"
    assert p_profile["data_source"] == "self_assessment"

    roster = client.get(
        f"/api/v1/events/{event_id}/participants", headers=admin_headers
    ).json()["data"]
    assert any(r["participant_id"] == participant_id for r in roster)

    # Re-submitting with the same phone reuses the same participant without creating duplicates
    sub2 = client.post(
        "/api/v1/assessments/submit",
        json={
            "phone": "08020898617",
            "event_id": event_id,
            "questionnaire_id": initial_qn["id"],
            "responses": responses,
        },
    )
    assert sub2.status_code == 201
    assert sub2.json()["data"]["participant_id"] == participant_id
