"""Idempotent reference data seeder for CCI STEM Connect.

Seeds ONLY structural reference data:
1. The six configurable measurement pillars.
2. Scoring Framework v1.0 with proposed starting weights (15/20/15/15/20/15).
3. Initial Question Card containing the 3 reflective discussion questions
   (stored explicitly as qualitative, is_scorable=False).
4. Configurable 30/60/90-day follow-up stage definitions.
5. Configurable Sections A-F post-event assessment questionnaire template with
   explicit scoring rules for quantitative questions only.

Does NOT seed fabricated events, participants, or production analytics data.
"""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import (
    ImpactCategory,
    QuestionType,
    QuestionnaireStatus,
    QuestionnaireType,
    ScoringRuleType,
)
from app.database.session import SessionLocal
from app.models.impact import FollowUpStageConfig
from app.models.questionnaire import (
    Question,
    QuestionCard,
    Questionnaire,
    QuestionnaireQuestion,
    QuestionnaireSection,
    QuestionPillarMapping,
)
from app.models.scoring import (
    MeasurementPillar,
    ScoringDimension,
    ScoringFramework,
    ScoringRule,
)

PILLAR_DEFINITIONS = [
    {
        "code": "professional_engagement",
        "name": "Professional Engagement",
        "description": (
            "Measures active participation in discussions, interaction with speakers "
            "and peers, contribution of questions or ideas, and overall engagement."
        ),
        "impact_category": ImpactCategory.IMMEDIATE.value,
        "default_weight": 0.15,
        "display_order": 1,
    },
    {
        "code": "knowledge_and_insights",
        "name": "Knowledge and Insights",
        "description": (
            "Measures new perspectives gained on productivity and excellence, key "
            "takeaways, peer knowledge gained, and decision-influencing insights."
        ),
        "impact_category": ImpactCategory.IMMEDIATE.value,
        "default_weight": 0.20,
        "display_order": 2,
    },
    {
        "code": "workplace_excellence",
        "name": "Workplace Excellence",
        "description": (
            "Measures improved understanding of professional standards, workplace "
            "productivity, and the link between excellence and organisational performance."
        ),
        "impact_category": ImpactCategory.IMMEDIATE.value,
        "default_weight": 0.15,
        "display_order": 3,
    },
    {
        "code": "recognition_and_rewards",
        "name": "Recognition and Rewards",
        "description": (
            "Measures insights into recognising and rewarding excellence, consequences "
            "of unrecognised contributions, and ideas for encouraging excellence."
        ),
        "impact_category": ImpactCategory.IMMEDIATE.value,
        "default_weight": 0.15,
        "display_order": 4,
    },
    {
        "code": "networking_and_relationships",
        "name": "Networking and Relationships",
        "description": (
            "Measures meaningful professional connections, potential collaborations, "
            "mentorship opportunities, follow-up conversations, and discovered opportunities."
        ),
        "impact_category": ImpactCategory.IMMEDIATE.value,
        "default_weight": 0.20,
        "display_order": 5,
    },
    {
        "code": "post_event_application",
        "name": "Post-Event Application",
        "description": (
            "Measures ideas implemented, professional habits changed, knowledge shared "
            "with colleagues, workplace improvements, and tangible professional outcomes."
        ),
        "impact_category": ImpactCategory.APPLICATION.value,
        "default_weight": 0.15,
        "display_order": 6,
    },
]

INITIAL_REFLECTIVE_QUESTIONS = [
    {
        "code": "card_01_early_career_priority",
        "question_text": "Which do you think matters more early in your tech career?",
        "description": "Reflective discussion card prompt from CCI STEM Connect.",
        "question_type": QuestionType.LONG_TEXT.value,
        "category": "career_reflection",
        "is_scorable": False,
        "allow_explanation": True,
        "explanation_prompt": "Share a brief reason or personal example.",
        "pillar_codes": ["knowledge_and_insights"],
        "display_order": 1,
    },
    {
        "code": "card_01_skills_easier_work",
        "question_text": "Which of your skills make your work easier?",
        "description": "Reflective discussion card prompt exploring workplace productivity.",
        "question_type": QuestionType.LONG_TEXT.value,
        "category": "productivity_reflection",
        "is_scorable": False,
        "allow_explanation": True,
        "explanation_prompt": "Describe how this skill improves your daily productivity.",
        "pillar_codes": ["workplace_excellence"],
        "display_order": 2,
    },
    {
        "code": "card_01_teach_in_10_minutes",
        "question_text": "What can you teach someone in 10 minutes?",
        "description": "Qualitative reflection capturing strengths and knowledge-sharing capacity.",
        "question_type": QuestionType.LONG_TEXT.value,
        "category": "knowledge_sharing",
        "is_scorable": False,
        "allow_explanation": False,
        "explanation_prompt": None,
        "pillar_codes": ["knowledge_and_insights", "networking_and_relationships"],
        "display_order": 3,
    },
]

FOLLOW_UP_STAGES = [
    {"stage_code": "30_day", "stage_name": "30-Day Follow-Up", "days_after_event": 30, "display_order": 1},
    {"stage_code": "60_day", "stage_name": "60-Day Follow-Up", "days_after_event": 60, "display_order": 2},
    {"stage_code": "90_day", "stage_name": "90-Day Follow-Up", "days_after_event": 90, "display_order": 3},
]

DEFAULT_ASSESSMENT_SECTIONS = [
    ("section_a", "Section A — Professional Background", "Participant professional context and attendance motivation.", 1),
    ("section_b", "Section B — Event Engagement", "Participation, speaker/peer interaction, and discussion relevance.", 2),
    ("section_c", "Section C — Knowledge and Insights", "Key takeaways and perspectives gained on productivity and excellence.", 3),
    ("section_d", "Section D — Workplace Excellence and Recognition", "Understanding of professional standards, recognition, and rewards.", 4),
    ("section_e", "Section E — Networking and Professional Relationships", "Meaningful connections, collaborations, mentorship, and opportunities.", 5),
    ("section_f", "Section F — Post-Event Application", "Intentions, implemented ideas, changed habits, and shared knowledge.", 6),
]

DEFAULT_ASSESSMENT_QUESTIONS = [
    # Section A (qualitative context)
    ("sec_a_reason_attending", "section_a", "What was your primary reason for attending CCI STEM Connect?", QuestionType.LONG_TEXT.value, False, [], None, 1),
    # Section B — Professional Engagement (Pillar 1)
    ("sec_b_discussion_participation", "section_b", "How actively did you participate in event discussions?", QuestionType.RATING_SCALE.value, True, ["professional_engagement"], (ScoringRuleType.RATING_SCALE.value, {"min": 1, "max": 5}), 1),
    ("sec_b_speaker_interaction", "section_b", "To what extent did you interact with speakers or panellists?", QuestionType.RATING_SCALE.value, True, ["professional_engagement"], (ScoringRuleType.RATING_SCALE.value, {"min": 1, "max": 5}), 2),
    ("sec_b_peer_interaction", "section_b", "How actively did you interact with other professionals during the event?", QuestionType.RATING_SCALE.value, True, ["professional_engagement"], (ScoringRuleType.RATING_SCALE.value, {"min": 1, "max": 5}), 3),
    ("sec_b_contributed_questions", "section_b", "Did you contribute a question, insight, or idea during the sessions?", QuestionType.YES_NO.value, True, ["professional_engagement"], (ScoringRuleType.YES_NO.value, {"yes_score": 100.0, "no_score": 0.0}), 4),
    ("sec_b_overall_engagement", "section_b", "How would you rate your overall engagement with CCI STEM Connect?", QuestionType.RATING_SCALE.value, True, ["professional_engagement"], (ScoringRuleType.RATING_SCALE.value, {"min": 1, "max": 5}), 5),
    # Section C — Knowledge and Insights (Pillar 2)
    ("sec_c_most_important_takeaway", "section_c", "What was your single most important takeaway from the event?", QuestionType.LONG_TEXT.value, False, ["knowledge_and_insights"], None, 1),
    ("sec_c_new_perspectives", "section_c", "To what extent did you gain new perspectives on workplace productivity and excellence?", QuestionType.RATING_SCALE.value, True, ["knowledge_and_insights"], (ScoringRuleType.RATING_SCALE.value, {"min": 1, "max": 5}), 2),
    ("sec_c_peer_knowledge", "section_c", "How valuable was the knowledge you gained from other professionals?", QuestionType.RATING_SCALE.value, True, ["knowledge_and_insights"], (ScoringRuleType.RATING_SCALE.value, {"min": 1, "max": 5}), 3),
    ("sec_c_decision_influence", "section_c", "How likely are the insights from this event to influence your professional decisions?", QuestionType.RATING_SCALE.value, True, ["knowledge_and_insights"], (ScoringRuleType.RATING_SCALE.value, {"min": 1, "max": 5}), 4),
    # Section D — Workplace Excellence (Pillar 3) & Recognition and Rewards (Pillar 4)
    ("sec_d_standards_understanding", "section_d", "How much did the event improve your understanding of professional standards and excellence?", QuestionType.RATING_SCALE.value, True, ["workplace_excellence"], (ScoringRuleType.RATING_SCALE.value, {"min": 1, "max": 5}), 1),
    ("sec_d_org_performance_link", "section_d", "How clearly do you now see the link between individual excellence and organisational performance?", QuestionType.RATING_SCALE.value, True, ["workplace_excellence"], (ScoringRuleType.RATING_SCALE.value, {"min": 1, "max": 5}), 2),
    ("sec_d_recognition_insights", "section_d", "To what extent did you gain practical insights on how excellence should be recognised and rewarded?", QuestionType.RATING_SCALE.value, True, ["recognition_and_rewards"], (ScoringRuleType.RATING_SCALE.value, {"min": 1, "max": 5}), 3),
    ("sec_d_unrecognised_impact", "section_d", "How strongly did the event deepen your awareness of the consequences when organisations fail to recognise excellence?", QuestionType.RATING_SCALE.value, True, ["recognition_and_rewards"], (ScoringRuleType.RATING_SCALE.value, {"min": 1, "max": 5}), 4),
    ("sec_d_encourage_excellence_ideas", "section_d", "What practical ways can organisations better encourage and reward excellence?", QuestionType.LONG_TEXT.value, False, ["recognition_and_rewards"], None, 5),
    # Section E — Networking and Relationships (Pillar 5)
    ("sec_e_meaningful_connections_count", "section_e", "How many meaningful professional connections did you establish at the event?", QuestionType.NUMERIC.value, True, ["networking_and_relationships"], (ScoringRuleType.NUMERIC_THRESHOLD.value, {"min_value": 0, "target_value": 5}), 1),
    ("sec_e_potential_collaboration", "section_e", "Did you identify at least one potential professional collaboration or mentorship opportunity?", QuestionType.YES_NO.value, True, ["networking_and_relationships"], (ScoringRuleType.YES_NO.value, {"yes_score": 100.0, "no_score": 0.0}), 2),
    ("sec_e_follow_up_conversations", "section_e", "Have you initiated follow-up conversations with connections made at the event?", QuestionType.RATING_SCALE.value, True, ["networking_and_relationships"], (ScoringRuleType.RATING_SCALE.value, {"min": 1, "max": 5}), 3),
    # Section F — Post-Event Application (Pillar 6)
    ("sec_f_intended_ideas", "section_f", "Which ideas from the event do you intend to apply in your workplace or career?", QuestionType.LONG_TEXT.value, False, ["post_event_application"], None, 1),
    ("sec_f_implemented_idea", "section_f", "Have you already implemented at least one idea or insight from the event?", QuestionType.YES_NO.value, True, ["post_event_application"], (ScoringRuleType.YES_NO.value, {"yes_score": 100.0, "no_score": 0.0}), 2),
    ("sec_f_habits_changed", "section_f", "To what extent have you changed professional habits based on the event?", QuestionType.RATING_SCALE.value, True, ["post_event_application"], (ScoringRuleType.RATING_SCALE.value, {"min": 1, "max": 5}), 3),
    ("sec_f_shared_with_colleagues", "section_f", "Have you shared insights from the event with colleagues or your team?", QuestionType.YES_NO.value, True, ["post_event_application"], (ScoringRuleType.YES_NO.value, {"yes_score": 100.0, "no_score": 0.0}), 4),
]


def seed_reference_data(db: Session) -> dict[str, int]:
    """Idempotently seed pillars, default framework, initial question cards, follow-up stages, and base questionnaire."""
    counts = {"pillars": 0, "cards": 0, "questions": 0, "stages": 0, "rules": 0}

    # 1. Measurement Pillars
    pillars_by_code: dict[str, MeasurementPillar] = {}
    for pdef in PILLAR_DEFINITIONS:
        pillar = db.execute(
            select(MeasurementPillar).where(MeasurementPillar.code == pdef["code"])
        ).scalar_one_or_none()
        if pillar is None:
            pillar = MeasurementPillar(**pdef)
            db.add(pillar)
            db.flush()
            counts["pillars"] += 1
        pillars_by_code[pillar.code] = pillar

    # 2. Scoring Framework v1.0 + Dimensions
    framework = db.execute(
        select(ScoringFramework).where(
            ScoringFramework.name == "CCI STEM Connect Impact Framework",
            ScoringFramework.version == "1.0",
        )
    ).scalar_one_or_none()
    if framework is None:
        framework = ScoringFramework(
            name="CCI STEM Connect Impact Framework",
            version="1.0",
            description=(
                "Proposed starting 6-pillar scoring framework (15/20/15/15/20/15) "
                "with automatic missing-dimension exclusion and weight renormalisation."
            ),
            is_active=True,
            min_questions_per_pillar=1,
            min_pillars_required=2,
            min_completeness_ratio=0.25,
        )
        db.add(framework)
        db.flush()

    dimensions_by_code: dict[str, ScoringDimension] = {}
    for code, pillar in pillars_by_code.items():
        dim = db.execute(
            select(ScoringDimension).where(
                ScoringDimension.framework_id == framework.id,
                ScoringDimension.pillar_id == pillar.id,
            )
        ).scalar_one_or_none()
        if dim is None:
            dim = ScoringDimension(
                framework_id=framework.id,
                pillar_id=pillar.id,
                weight=pillar.default_weight,
                impact_category=pillar.impact_category,
                min_questions_required=1,
            )
            db.add(dim)
            db.flush()
        dimensions_by_code[code] = dim

    # 3. Initial Question Card + 3 Reflective Qualitative Questions
    card = db.execute(
        select(QuestionCard).where(QuestionCard.code == "cci-stem-card-01")
    ).scalar_one_or_none()
    if card is None:
        card = QuestionCard(
            code="cci-stem-card-01",
            title="CCI STEM Connect Reflective Discussion Card 1",
            description=(
                "Initial event discussion card containing reflective questions designed "
                "to stimulate professional reflection and knowledge sharing."
            ),
            category="reflection",
            is_active=True,
            display_order=1,
        )
        db.add(card)
        db.flush()
        counts["cards"] += 1

    for qdef in INITIAL_REFLECTIVE_QUESTIONS:
        existing_q = db.execute(
            select(Question).where(Question.code == qdef["code"])
        ).scalar_one_or_none()
        if existing_q is None:
            q = Question(
                card_id=card.id,
                code=qdef["code"],
                question_text=qdef["question_text"],
                description=qdef["description"],
                question_type=qdef["question_type"],
                category=qdef["category"],
                is_required=False,
                is_scorable=qdef["is_scorable"],
                allow_explanation=qdef["allow_explanation"],
                explanation_prompt=qdef["explanation_prompt"],
                display_order=qdef["display_order"],
            )
            db.add(q)
            db.flush()
            for idx, pcode in enumerate(qdef["pillar_codes"]):
                db.add(
                    QuestionPillarMapping(
                        question_id=q.id,
                        pillar_id=pillars_by_code[pcode].id,
                        is_primary=(idx == 0),
                    )
                )
            counts["questions"] += 1

    # 4. Global 30 / 60 / 90-day Follow-Up Stage Configs
    for stage in FOLLOW_UP_STAGES:
        existing_stage = db.execute(
            select(FollowUpStageConfig).where(
                FollowUpStageConfig.event_id.is_(None),
                FollowUpStageConfig.stage_code == stage["stage_code"],
            )
        ).scalar_one_or_none()
        if existing_stage is None:
            db.add(FollowUpStageConfig(event_id=None, **stage))
            counts["stages"] += 1

    # 5. Default Sections A-F Questionnaire Template + Scoring Rules
    questionnaire = db.execute(
        select(Questionnaire).where(Questionnaire.code == "cci-stem-assessment-v1")
    ).scalar_one_or_none()
    if questionnaire is None:
        questionnaire = Questionnaire(
            event_id=None,
            code="cci-stem-assessment-v1",
            title="CCI STEM Connect Participant Impact Assessment (Sections A–F)",
            description=(
                "Configurable multi-section assessment covering Professional Background, "
                "Event Engagement, Knowledge & Insights, Workplace Excellence & Recognition, "
                "Networking, and Post-Event Application."
            ),
            questionnaire_type=QuestionnaireType.POST_EVENT.value,
            version="1.0",
            status=QuestionnaireStatus.PUBLISHED.value,
            published_at=datetime.now(timezone.utc),
        )
        db.add(questionnaire)
        db.flush()

        sections_by_code: dict[str, QuestionnaireSection] = {}
        for sec_code, sec_title, sec_desc, sec_order in DEFAULT_ASSESSMENT_SECTIONS:
            sec = QuestionnaireSection(
                questionnaire_id=questionnaire.id,
                code=sec_code,
                title=sec_title,
                description=sec_desc,
                display_order=sec_order,
            )
            db.add(sec)
            db.flush()
            sections_by_code[sec_code] = sec

        for (
            q_code,
            sec_code,
            q_text,
            q_type,
            is_scorable,
            pillar_codes,
            rule_spec,
            order,
        ) in DEFAULT_ASSESSMENT_QUESTIONS:
            q = db.execute(
                select(Question).where(Question.code == q_code)
            ).scalar_one_or_none()
            if q is None:
                q = Question(
                    code=q_code,
                    question_text=q_text,
                    question_type=q_type,
                    category=sec_code,
                    is_required=False,
                    is_scorable=is_scorable,
                    allow_explanation=True,
                    validation_config={"min": 1, "max": 5}
                    if q_type == QuestionType.RATING_SCALE.value
                    else None,
                    display_order=order,
                )
                db.add(q)
                db.flush()
                for idx, pcode in enumerate(pillar_codes):
                    db.add(
                        QuestionPillarMapping(
                            question_id=q.id,
                            pillar_id=pillars_by_code[pcode].id,
                            is_primary=(idx == 0),
                        )
                    )
                counts["questions"] += 1

            db.add(
                QuestionnaireQuestion(
                    questionnaire_id=questionnaire.id,
                    section_id=sections_by_code[sec_code].id,
                    question_id=q.id,
                    display_order=order,
                )
            )

            if is_scorable and rule_spec is not None and pillar_codes:
                rule_type, rule_config = rule_spec
                dim = dimensions_by_code[pillar_codes[0]]
                existing_rule = db.execute(
                    select(ScoringRule).where(
                        ScoringRule.framework_id == framework.id,
                        ScoringRule.dimension_id == dim.id,
                        ScoringRule.question_id == q.id,
                    )
                ).scalar_one_or_none()
                if existing_rule is None:
                    db.add(
                        ScoringRule(
                            framework_id=framework.id,
                            dimension_id=dim.id,
                            question_id=q.id,
                            rule_type=rule_type,
                            rule_config=rule_config,
                            question_weight=1.0,
                            is_active=True,
                        )
                    )
                    counts["rules"] += 1

    db.commit()
    return counts


if __name__ == "__main__":
    with SessionLocal() as session:
        result = seed_reference_data(session)
        print(f"Seeded CCI STEM Connect reference data: {result}")
