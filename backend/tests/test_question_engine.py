"""Tests for Question Cards, Questions (all types + qualitative), Questionnaires, and Assessments."""

from fastapi.testclient import TestClient


def test_initial_seeded_question_card_and_reflective_questions(client: TestClient):
    cards = client.get("/api/v1/question-cards").json()["data"]
    assert len(cards) >= 3
    by_code = {c["code"]: c for c in cards}
    assert {"cci-stem-card-01", "cci-stem-card-02", "cci-stem-card-03"}.issubset(
        by_code.keys()
    )
    reflective_questions = [
        q
        for code in ("cci-stem-card-01", "cci-stem-card-02", "cci-stem-card-03")
        for q in by_code[code]["questions"]
    ]
    texts = {q["question_text"] for q in reflective_questions}
    assert "Which do you think matters more early in your tech career?" in texts
    assert "Which of your skills make your work easier?" in texts
    assert "What can you teach someone in 10 minutes?" in texts
    # Reflective discussion questions must be qualitative (not scorable)
    for q in reflective_questions:
        assert q["is_scorable"] is False


def test_question_card_question_lifecycle_and_questionnaire_publish(
    client: TestClient, admin_headers: dict[str, str]
):
    pillars = client.get("/api/v1/pillars").json()["data"]
    assert len(pillars) == 6
    p_engagement = next(p for p in pillars if p["code"] == "professional_engagement")
    p_knowledge = next(p for p in pillars if p["code"] == "knowledge_and_insights")

    # Create custom question card
    card = client.post(
        "/api/v1/question-cards",
        headers=admin_headers,
        json={
            "code": "cci-card-02",
            "title": "Leadership & Excellence Card",
            "category": "leadership",
        },
    ).json()["data"]

    # Add multi-pillar single-choice question with options & explanation to the card
    q1 = client.post(
        f"/api/v1/question-cards/{card['id']}/questions",
        headers=admin_headers,
        json={
            "code": "custom_single_choice_01",
            "question_text": "Which workplace factor drives excellence most?",
            "question_type": "single_choice",
            "is_required": True,
            "is_scorable": True,
            "allow_explanation": True,
            "explanation_prompt": "Why did you choose this factor?",
            "pillar_ids": [p_engagement["id"], p_knowledge["id"]],
            "options": [
                {"option_value": "standards", "option_label": "Clear standards", "score_value": 100},
                {"option_value": "recognition", "option_label": "Fair recognition", "score_value": 80},
            ],
        },
    )
    assert q1.status_code == 201, q1.text
    q1_data = q1.json()["data"]
    assert len(q1_data["pillar_ids"]) == 2
    assert len(q1_data["options"]) == 2

    # Create date question and archive it
    q2 = client.post(
        "/api/v1/questions",
        headers=admin_headers,
        json={
            "code": "custom_date_01",
            "question_text": "When will you implement your first action?",
            "question_type": "date",
            "is_scorable": False,
        },
    ).json()["data"]

    archived = client.patch(
        f"/api/v1/questions/{q2['id']}/archive", headers=admin_headers
    )
    assert archived.status_code == 200
    assert archived.json()["data"]["is_archived"] is True

    # Build and publish questionnaire
    qn = client.post(
        "/api/v1/questionnaires",
        headers=admin_headers,
        json={
            "code": "custom-q-2026",
            "title": "Custom Reflection Questionnaire",
            "sections": [
                {
                    "code": "sec_1",
                    "title": "Section 1",
                    "display_order": 1,
                    "question_ids": [q1_data["id"]],
                }
            ],
        },
    ).json()["data"]
    assert qn["status"] == "draft"

    pub = client.post(
        f"/api/v1/questionnaires/{qn['id']}/publish", headers=admin_headers
    )
    assert pub.status_code == 200
    assert pub.json()["data"]["status"] == "published"


def test_assessment_submission_by_phone_and_validation(
    client: TestClient, admin_headers: dict[str, str]
):
    event = client.post(
        "/api/v1/events",
        headers=admin_headers,
        json={
            "slug": "stem-connect-assess-test",
            "title": "CCI STEM Connect Assessment Test",
            "event_date": "2026-09-01",
        },
    ).json()["data"]

    participant = client.post(
        "/api/v1/participants",
        headers=admin_headers,
        json={
            "full_name": "Ngozi Eze",
            "phone": "0805 222 3344",
            "email": "ngozi@example.com",
            "event_id": event["id"],
        },
    ).json()["data"]

    qns = client.get("/api/v1/questionnaires").json()["data"]
    default_qn = next(q for q in qns if q["code"] == "cci-stem-assessment-v1")
    q_by_code = {link["question"]["code"]: link["question"]["id"] for link in default_qn["questions"]}

    # Submit assessment using normalised phone lookup (no password / login)
    submit = client.post(
        "/api/v1/assessments/submit",
        json={
            "phone": "08052223344",
            "event_id": event["id"],
            "questionnaire_id": default_qn["id"],
            "profile_updates": {
                "current_role": "Product Manager",
                "industry": "HealthTech",
                "consent_given": True,
            },
            "responses": [
                {
                    "question_id": q_by_code["sec_b_discussion_participation"],
                    "response_numeric": 5,
                    "explanation_text": "Led table discussion on workplace excellence.",
                },
                {
                    "question_id": q_by_code["sec_c_most_important_takeaway"],
                    "response_text": "Clear recognition systems directly raise team productivity.",
                },
            ],
        },
    )
    assert submit.status_code == 201, submit.text
    sub_data = submit.json()["data"]
    assert sub_data["participant_id"] == participant["id"]
    assert len(sub_data["responses"]) == 2
    assert sub_data["completeness_ratio"] > 0

    # Invalid rating (>5) rejected cleanly
    bad_rating = client.post(
        "/api/v1/assessments/submit",
        json={
            "phone": "08052223344",
            "event_id": event["id"],
            "questionnaire_id": default_qn["id"],
            "responses": [
                {
                    "question_id": q_by_code["sec_b_discussion_participation"],
                    "response_numeric": 99,
                }
            ],
        },
    )
    assert bad_rating.status_code == 422

    # Retrieve participant assessments
    listed = client.get(
        f"/api/v1/participants/{participant['id']}/assessments",
        headers=admin_headers,
    )
    assert listed.status_code == 200
    assert listed.json()["meta"]["total"] == 1
