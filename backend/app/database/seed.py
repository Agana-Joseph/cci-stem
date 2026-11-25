"""Idempotent database population & reference seeder for CCI STEM Connect.

Follows the required 15-step seed sequence safely and idempotently:
 1. Seed the default published CCI STEM Connect event (without fabricating date/venue).
 2. Seed the 7 event objectives in `event_objectives`.
 3. Seed the 6 configurable measurement pillars in `measurement_pillars`.
 4. Associate all 6 pillars with CCI STEM Connect via `event_pillars`.
 5. Seed the 9 question categories in `question_categories`.
 6. Seed the CCI STEM Connect Initial Assessment questionnaire (`cci-stem-connect-initial-assessment`).
 7. Seed questionnaire sections A–F.
 8. Seed all 35 initial questions (A1–F5) and their answer options.
 9. Seed the 3 original reflection cards (`cci-stem-card-01`, `02`, `03`) with exact wording.
10. Seed the active scoring framework (`CCI STEM Connect Participant Impact Framework`, v1.0).
11. Seed scoring dimensions (15/20/15/15/20/15 = 100%) and configurable scoring rules.
12. Seed the 4 assessment stages (Immediate, 30-day, 60-day, 90-day).
13. Seed the 30-Day Follow-Up questionnaire (6 questions).
14. Seed the 60-Day Follow-Up questionnaire (6 questions).
15. Seed the 90-Day Follow-Up questionnaire (7 questions).

Preserves existing participants, submissions, responses, and legacy template compatibility.
Never creates fabricated participants, attendance figures, scores, or analytics data.
"""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import (
    EventStatus,
    ImpactCategory,
    QuestionType,
    QuestionnaireStatus,
    QuestionnaireType,
    ScoringRuleType,
)
from app.database.session import SessionLocal
from app.models.impact import FollowUpStageConfig
from app.models.participant import Event, EventObjective, EventPillar
from app.models.questionnaire import (
    Question,
    QuestionCard,
    QuestionCategory,
    Questionnaire,
    QuestionnaireQuestion,
    QuestionnaireSection,
    QuestionOption,
    QuestionPillarMapping,
)
from app.models.scoring import (
    MeasurementPillar,
    ScoringDimension,
    ScoringFramework,
    ScoringRule,
)

# ---------------------------------------------------------------------------
# 1. Default Event & Objectives
# ---------------------------------------------------------------------------

DEFAULT_EVENT_SLUG = "cci-stem-connect"

DEFAULT_EVENT_CONFIG: dict[str, Any] = {
    "slug": DEFAULT_EVENT_SLUG,
    "title": "CCI STEM Connect",
    "headline": "Connect. Grow. Improve. Excel.",
    "event_category": "Professional Engagement and Knowledge Sharing",
    "event_type": "networking_and_knowledge_sharing",
    "description": (
        "CCI STEM Connect brings professionals together to exchange ideas, share experiences, "
        "explore workplace productivity and excellence, discuss professional recognition and "
        "rewards, and build meaningful professional relationships grounded in Christ-like character."
    ),
    "introduction": (
        "CCI STEM Connect provides a platform for professionals to engage in meaningful "
        "conversations about professional development, workplace standards, productivity, "
        "excellence, recognition and the importance of building relationships within the "
        "professional community.\n\n"
        "The event encourages participants to reflect on their professional journeys, understand "
        "the value of their contributions, strengthen their work ethic and pursue excellence "
        "through integrity, responsibility, discipline and Christ-like character."
    ),
    "event_date": None,
    "end_date": None,
    "location": None,
    "status": EventStatus.PUBLISHED.value,
    "is_default": True,
    "assessment_enabled": True,
    "follow_up_enabled": True,
    "public_visibility": True,
    "reflection_cards_enabled": True,
    "immediate_assessment_enabled": True,
    "follow_up_30d_enabled": True,
    "follow_up_60d_enabled": True,
    "follow_up_90d_enabled": True,
}

EVENT_OBJECTIVES: list[tuple[int, str]] = [
    (1, "Encourage meaningful professional engagement and knowledge sharing."),
    (2, "Promote productivity and excellence in the workplace."),
    (3, "Encourage integrity, discipline and Christ-like professional character."),
    (4, "Explore the importance of recognising and rewarding excellence."),
    (5, "Build meaningful professional relationships and networking opportunities."),
    (6, "Encourage participants to apply insights and knowledge to their professional journeys."),
    (7, "Measure the immediate and long-term value participants derive from the event."),
]

# ---------------------------------------------------------------------------
# 2. Six Measurement Pillars (weights total 1.00 = 100%)
# ---------------------------------------------------------------------------

PILLAR_DEFINITIONS: list[dict[str, Any]] = [
    {
        "code": "professional_engagement",
        "name": "Professional Engagement",
        "description": (
            "Measures how actively participants engaged with the event, speakers, "
            "discussions and other professionals."
        ),
        "impact_category": ImpactCategory.IMMEDIATE.value,
        "default_weight": 0.15,
        "display_order": 1,
    },
    {
        "code": "knowledge_and_insights",
        "name": "Knowledge and Insights",
        "description": (
            "Measures the knowledge, perspectives and insights participants gained from "
            "the event, particularly around productivity, professional development and "
            "workplace excellence."
        ),
        "impact_category": ImpactCategory.IMMEDIATE.value,
        "default_weight": 0.20,
        "display_order": 2,
    },
    {
        "code": "workplace_excellence",
        "name": "Workplace Excellence",
        "description": (
            "Measures participants' understanding of professional standards, responsibility, "
            "productivity, work ethic and excellence in the workplace."
        ),
        "impact_category": ImpactCategory.IMMEDIATE.value,
        "default_weight": 0.15,
        "display_order": 3,
    },
    {
        "code": "recognition_and_rewards",
        "name": "Recognition and Rewards",
        "description": (
            "Measures participants' understanding of recognition, appreciation and rewards "
            "for professional excellence, including the consequences of excellent work "
            "going unnoticed or unrewarded."
        ),
        "impact_category": ImpactCategory.IMMEDIATE.value,
        "default_weight": 0.15,
        "display_order": 4,
    },
    {
        "code": "networking_and_relationships",
        "name": "Networking and Relationships",
        "description": (
            "Measures the meaningful professional relationships participants establish "
            "through the event and the opportunities arising from those connections."
        ),
        "impact_category": ImpactCategory.IMMEDIATE.value,
        "default_weight": 0.20,
        "display_order": 5,
    },
    {
        "code": "post_event_application",
        "name": "Post-Event Application",
        "description": (
            "Measures how participants apply insights from the event to their professional "
            "lives, workplaces and relationships after the event."
        ),
        "impact_category": ImpactCategory.APPLICATION.value,
        "default_weight": 0.15,
        "display_order": 6,
    },
]

# ---------------------------------------------------------------------------
# 3. Nine Question Categories
# ---------------------------------------------------------------------------

QUESTION_CATEGORIES: list[dict[str, Any]] = [
    {"code": "professional_background", "name": "Professional Background", "display_order": 1},
    {"code": "event_engagement", "name": "Event Engagement", "display_order": 2},
    {"code": "knowledge_and_insights", "name": "Knowledge and Insights", "display_order": 3},
    {"code": "workplace_excellence", "name": "Workplace Excellence", "display_order": 4},
    {"code": "recognition_and_rewards", "name": "Recognition and Rewards", "display_order": 5},
    {"code": "networking_and_relationships", "name": "Networking and Relationships", "display_order": 6},
    {"code": "professional_reflection", "name": "Professional Reflection", "display_order": 7},
    {"code": "post_event_application", "name": "Post-Event Application", "display_order": 8},
    {"code": "professional_outcomes", "name": "Professional Outcomes", "display_order": 9},
]

# ---------------------------------------------------------------------------
# 4. Three Original Professional Reflection Cards (exact preserved wording)
# ---------------------------------------------------------------------------

REFLECTION_CARDS: list[dict[str, Any]] = [
    {
        "card_code": "cci-stem-card-01",
        "card_title": "Reflection Card 01",
        "card_description": "Original CCI STEM Connect reflective discussion prompt on early-career priorities.",
        "card_order": 1,
        "question_code": "card_01_early_career_priority",
        "question_text": "Which do you think matters more early in your tech career?",
        "question_description": "Original CCI STEM Connect reflection card (qualitative; not automatically scored).",
        "question_type": QuestionType.LONG_TEXT.value,
        "category_code": "professional_reflection",
        "allow_explanation": True,
        "explanation_prompt": "Share a brief reason or personal example.",
        "pillar_codes": ["knowledge_and_insights"],
    },
    {
        "card_code": "cci-stem-card-02",
        "card_title": "Reflection Card 02",
        "card_description": "Original CCI STEM Connect reflective discussion prompt on productivity and workplace skills.",
        "card_order": 2,
        "question_code": "card_01_skills_easier_work",
        "question_text": "Which of your skills make your work easier?",
        "question_description": "Original CCI STEM Connect reflection card (qualitative; not automatically scored).",
        "question_type": QuestionType.LONG_TEXT.value,
        "category_code": "professional_reflection",
        "allow_explanation": True,
        "explanation_prompt": "Describe how this skill improves your daily productivity.",
        "pillar_codes": ["workplace_excellence", "knowledge_and_insights"],
    },
    {
        "card_code": "cci-stem-card-03",
        "card_title": "Reflection Card 03",
        "card_description": "Original CCI STEM Connect reflective discussion prompt on strengths and knowledge sharing.",
        "card_order": 3,
        "question_code": "card_01_teach_in_10_minutes",
        "question_text": "What can you teach someone in 10 minutes?",
        "question_description": "Original CCI STEM Connect reflection card (qualitative; not automatically scored).",
        "question_type": QuestionType.LONG_TEXT.value,
        "category_code": "professional_reflection",
        "allow_explanation": False,
        "explanation_prompt": None,
        "pillar_codes": ["knowledge_and_insights", "networking_and_relationships"],
    },
]

# ---------------------------------------------------------------------------
# 5. Initial Assessment Questionnaire (Sections A–F, 35 questions)
# ---------------------------------------------------------------------------

INITIAL_QUESTIONNAIRE_CODE = "cci-stem-connect-initial-assessment"

INITIAL_ASSESSMENT_SECTIONS: list[tuple[str, str, str, int]] = [
    ("section_a", "Section A — Professional Background", "Establish the participant's professional context.", 1),
    ("section_b", "Section B — Event Engagement", "Understand participants' involvement in the event.", 2),
    ("section_c", "Section C — Knowledge and Insights", "Understand what participants learned and the new perspectives they gained.", 3),
    ("section_d", "Section D — Workplace Excellence and Recognition", "Understand participants' perspectives on workplace standards, professional conduct, recognition and rewards.", 4),
    ("section_e", "Section E — Networking and Relationships", "Understand the professional relationships established through the event.", 5),
    ("section_f", "Section F — Post-Event Application", "Establish what participants intend to apply after attending the event.", 6),
]

RATING_1_5_OPTIONS = [
    ("1", "1 — Very Low / Not at all", 0.0, 1),
    ("2", "2 — Low / Slightly", 25.0, 2),
    ("3", "3 — Moderate", 50.0, 3),
    ("4", "4 — High / Actively", 75.0, 4),
    ("5", "5 — Very High / Extremely", 100.0, 5),
]

B1_ENGAGEMENT_OPTIONS = [
    ("1", "Not actively involved", 0.0, 1),
    ("2", "Slightly involved", 25.0, 2),
    ("3", "Moderately involved", 50.0, 3),
    ("4", "Actively involved", 75.0, 4),
    ("5", "Very actively involved", 100.0, 5),
]

INITIAL_ASSESSMENT_QUESTIONS: list[dict[str, Any]] = [
    # --- SECTION A — PROFESSIONAL BACKGROUND ---
    {
        "code": "a1_full_name",
        "section": "section_a",
        "text": "Full Name",
        "type": QuestionType.SHORT_TEXT.value,
        "required": True,
        "scorable": False,
        "category": "professional_background",
        "pillars": [],
        "validation_config": {"prepopulate_from": "full_name"},
        "order": 1,
    },
    {
        "code": "a2_email_address",
        "section": "section_a",
        "text": "Email Address",
        "type": QuestionType.EMAIL.value,
        "required": True,
        "scorable": False,
        "category": "professional_background",
        "pillars": [],
        "validation_config": {"prepopulate_from": "email"},
        "order": 2,
    },
    {
        "code": "a3_active_phone_number",
        "section": "section_a",
        "text": "Active Phone Number",
        "type": QuestionType.PHONE.value,
        "required": True,
        "scorable": False,
        "category": "professional_background",
        "pillars": [],
        "validation_config": {"prepopulate_from": "phone"},
        "order": 3,
    },
    {
        "code": "a4_current_professional_role",
        "section": "section_a",
        "text": "What is your current professional role?",
        "type": QuestionType.SHORT_TEXT.value,
        "required": True,
        "scorable": False,
        "category": "professional_background",
        "pillars": [],
        "order": 4,
    },
    {
        "code": "a5_industry_sector",
        "section": "section_a",
        "text": "Which industry or professional sector do you work in?",
        "type": QuestionType.SINGLE_CHOICE.value,
        "required": True,
        "scorable": False,
        "category": "professional_background",
        "pillars": [],
        "allow_explanation": True,
        "explanation_prompt": "If you selected Other, please specify your industry or sector.",
        "validation_config": {"allow_other_text": True, "other_option_value": "other"},
        "options": [
            ("technology", "Technology", None, 1),
            ("finance_and_banking", "Finance and Banking", None, 2),
            ("education", "Education", None, 3),
            ("healthcare", "Healthcare", None, 4),
            ("business_and_entrepreneurship", "Business and Entrepreneurship", None, 5),
            ("engineering", "Engineering", None, 6),
            ("media_and_communications", "Media and Communications", None, 7),
            ("consulting", "Consulting", None, 8),
            ("government_and_public_sector", "Government and Public Sector", None, 9),
            ("other", "Other", None, 10),
        ],
        "order": 5,
    },
    {
        "code": "a6_organisation",
        "section": "section_a",
        "text": "What organisation or company do you currently work with?",
        "type": QuestionType.SHORT_TEXT.value,
        "required": False,
        "scorable": False,
        "category": "professional_background",
        "pillars": [],
        "order": 6,
    },
    {
        "code": "a7_years_of_experience",
        "section": "section_a",
        "text": "How many years of professional experience do you have?",
        "type": QuestionType.SINGLE_CHOICE.value,
        "required": True,
        "scorable": False,
        "category": "professional_background",
        "pillars": [],
        "options": [
            ("less_than_1_year", "Less than 1 year", None, 1),
            ("1_2_years", "1–2 years", None, 2),
            ("3_5_years", "3–5 years", None, 3),
            ("6_10_years", "6–10 years", None, 4),
            ("more_than_10_years", "More than 10 years", None, 5),
        ],
        "order": 7,
    },
    {
        "code": "a8_motivation_to_attend",
        "section": "section_a",
        "text": "What motivated you to attend CCI STEM Connect?",
        "type": QuestionType.LONG_TEXT.value,
        "required": True,
        "scorable": False,
        "category": "professional_background",
        "pillars": [],
        "order": 8,
    },
    # --- SECTION B — EVENT ENGAGEMENT ---
    {
        "code": "b1_active_participation",
        "section": "section_b",
        "text": "How actively did you participate in the event?",
        "type": QuestionType.RATING_SCALE.value,
        "required": True,
        "scorable": True,
        "category": "event_engagement",
        "pillars": ["professional_engagement"],
        "validation_config": {"min": 1, "max": 5},
        "options": B1_ENGAGEMENT_OPTIONS,
        "rule": (ScoringRuleType.RATING_SCALE.value, {"min": 1, "max": 5}),
        "order": 1,
    },
    {
        "code": "b2_speaker_interaction",
        "section": "section_b",
        "text": "Did you interact with any of the speakers or facilitators?",
        "type": QuestionType.SINGLE_CHOICE.value,
        "required": True,
        "scorable": True,
        "category": "event_engagement",
        "pillars": ["professional_engagement"],
        "options": [
            ("yes", "Yes", 100.0, 1),
            ("no", "No", 0.0, 2),
        ],
        "rule": (
            ScoringRuleType.SINGLE_CHOICE.value,
            {"option_scores": {"yes": 100.0, "no": 0.0}, "max_score": 100.0},
        ),
        "order": 2,
    },
    {
        "code": "b3_peer_interaction",
        "section": "section_b",
        "text": "Did you interact with other professionals during the event?",
        "type": QuestionType.RATING_SCALE.value,
        "required": True,
        "scorable": True,
        "category": "event_engagement",
        "pillars": ["professional_engagement"],
        "validation_config": {"min": 1, "max": 5},
        "options": RATING_1_5_OPTIONS,
        "rule": (ScoringRuleType.RATING_SCALE.value, {"min": 1, "max": 5}),
        "order": 3,
    },
    {
        "code": "b4_contributed_discussions",
        "section": "section_b",
        "text": "Did you contribute questions, ideas or experiences during the discussions?",
        "type": QuestionType.SINGLE_CHOICE.value,
        "required": True,
        "scorable": True,
        "category": "event_engagement",
        "pillars": ["professional_engagement"],
        "options": [
            ("yes_actively", "Yes, actively", 100.0, 1),
            ("yes_occasionally", "Yes, occasionally", 60.0, 2),
            ("no", "No", 0.0, 3),
        ],
        "rule": (
            ScoringRuleType.SINGLE_CHOICE.value,
            {
                "option_scores": {"yes_actively": 100.0, "yes_occasionally": 60.0, "no": 0.0},
                "max_score": 100.0,
            },
        ),
        "order": 4,
    },
    {
        "code": "b5_discussion_relevance",
        "section": "section_b",
        "text": "How relevant were the discussions to your professional journey?",
        "type": QuestionType.RATING_SCALE.value,
        "required": True,
        "scorable": True,
        "category": "event_engagement",
        "pillars": ["professional_engagement"],
        "validation_config": {"min": 1, "max": 5},
        "options": RATING_1_5_OPTIONS,
        "rule": (ScoringRuleType.RATING_SCALE.value, {"min": 1, "max": 5}),
        "order": 5,
    },
    {
        "code": "b6_overall_engagement",
        "section": "section_b",
        "text": "Overall, how would you rate your engagement with CCI STEM Connect?",
        "type": QuestionType.RATING_SCALE.value,
        "required": True,
        "scorable": True,
        "category": "event_engagement",
        "pillars": ["professional_engagement"],
        "validation_config": {"min": 1, "max": 5},
        "options": RATING_1_5_OPTIONS,
        "rule": (ScoringRuleType.RATING_SCALE.value, {"min": 1, "max": 5}),
        "order": 6,
    },
    # --- SECTION C — KNOWLEDGE AND INSIGHTS ---
    {
        "code": "c1_most_important_insight",
        "section": "section_c",
        "text": "What was the most important insight or lesson you took away from CCI STEM Connect?",
        "type": QuestionType.LONG_TEXT.value,
        "required": True,
        "scorable": False,
        "category": "knowledge_and_insights",
        "pillars": ["knowledge_and_insights"],
        "order": 1,
    },
    {
        "code": "c2_new_perspectives",
        "section": "section_c",
        "text": "Did the discussions introduce new perspectives about productivity and workplace excellence?",
        "type": QuestionType.SINGLE_CHOICE.value,
        "required": True,
        "scorable": True,
        "category": "knowledge_and_insights",
        "pillars": ["knowledge_and_insights"],
        "options": [
            ("yes_significantly", "Yes, significantly", 100.0, 1),
            ("yes_to_some_extent", "Yes, to some extent", 65.0, 2),
            ("no_significant_change", "No significant change", 20.0, 3),
            ("not_sure", "Not sure", 35.0, 4),
        ],
        "rule": (
            ScoringRuleType.SINGLE_CHOICE.value,
            {
                "option_scores": {
                    "yes_significantly": 100.0,
                    "yes_to_some_extent": 65.0,
                    "no_significant_change": 20.0,
                    "not_sure": 35.0,
                },
                "max_score": 100.0,
            },
        ),
        "order": 2,
    },
    {
        "code": "c3_understanding_excellence",
        "section": "section_c",
        "text": "How much did the event improve your understanding of professional excellence?",
        "type": QuestionType.RATING_SCALE.value,
        "required": True,
        "scorable": True,
        "category": "knowledge_and_insights",
        "pillars": ["knowledge_and_insights"],
        "validation_config": {"min": 1, "max": 5},
        "options": RATING_1_5_OPTIONS,
        "rule": (ScoringRuleType.RATING_SCALE.value, {"min": 1, "max": 5}),
        "order": 3,
    },
    {
        "code": "c4_productivity_responsibility_influence",
        "section": "section_c",
        "text": "How much did the event influence the way you think about productivity and professional responsibility?",
        "type": QuestionType.RATING_SCALE.value,
        "required": True,
        "scorable": True,
        "category": "knowledge_and_insights",
        "pillars": ["knowledge_and_insights"],
        "validation_config": {"min": 1, "max": 5},
        "options": RATING_1_5_OPTIONS,
        "rule": (ScoringRuleType.RATING_SCALE.value, {"min": 1, "max": 5}),
        "order": 4,
    },
    {
        "code": "c5_decision_influencing_idea",
        "section": "section_c",
        "text": "What new idea or perspective will influence your professional decisions going forward?",
        "type": QuestionType.LONG_TEXT.value,
        "required": True,
        "scorable": False,
        "category": "knowledge_and_insights",
        "pillars": ["knowledge_and_insights"],
        "order": 5,
    },
    # --- SECTION D — WORKPLACE EXCELLENCE AND RECOGNITION ---
    {
        "code": "d1_describe_workplace_excellence",
        "section": "section_d",
        "text": "How would you describe workplace excellence in your own words?",
        "type": QuestionType.LONG_TEXT.value,
        "required": True,
        "scorable": False,
        "category": "workplace_excellence",
        "pillars": ["workplace_excellence"],
        "order": 1,
    },
    {
        "code": "d2_integrity_responsibility_importance",
        "section": "section_d",
        "text": "How important is integrity and personal responsibility in achieving professional excellence?",
        "type": QuestionType.RATING_SCALE.value,
        "required": True,
        "scorable": True,
        "category": "workplace_excellence",
        "pillars": ["workplace_excellence"],
        "validation_config": {"min": 1, "max": 5},
        "options": RATING_1_5_OPTIONS,
        "rule": (ScoringRuleType.RATING_SCALE.value, {"min": 1, "max": 5}),
        "order": 2,
    },
    {
        "code": "d3_recognition_rewards_importance",
        "section": "section_d",
        "text": "How important is recognising and rewarding excellent work in an organisation?",
        "type": QuestionType.RATING_SCALE.value,
        "required": True,
        "scorable": True,
        "category": "recognition_and_rewards",
        "pillars": ["recognition_and_rewards"],
        "validation_config": {"min": 1, "max": 5},
        "options": RATING_1_5_OPTIONS,
        "rule": (ScoringRuleType.RATING_SCALE.value, {"min": 1, "max": 5}),
        "order": 3,
    },
    {
        "code": "d4_unrecognised_excellence_consequences",
        "section": "section_d",
        "text": "What do you think happens when employees consistently deliver excellent work but their contributions go unnoticed or unrewarded?",
        "type": QuestionType.LONG_TEXT.value,
        "required": True,
        "scorable": False,
        "category": "recognition_and_rewards",
        "pillars": ["recognition_and_rewards"],
        "order": 4,
    },
    {
        "code": "d5_organisations_encourage_excellence",
        "section": "section_d",
        "text": "What can organisations do to encourage a culture of excellence?",
        "type": QuestionType.LONG_TEXT.value,
        "required": True,
        "scorable": False,
        "category": "recognition_and_rewards",
        "pillars": ["recognition_and_rewards"],
        "order": 5,
    },
    {
        "code": "d6_personal_commitment_standards",
        "section": "section_d",
        "text": "How would you rate your personal commitment to improving your work ethic and professional standards?",
        "type": QuestionType.RATING_SCALE.value,
        "required": True,
        "scorable": True,
        "category": "workplace_excellence",
        "pillars": ["workplace_excellence"],
        "validation_config": {"min": 1, "max": 5},
        "options": RATING_1_5_OPTIONS,
        "rule": (ScoringRuleType.RATING_SCALE.value, {"min": 1, "max": 5}),
        "order": 6,
    },
    # --- SECTION E — NETWORKING AND RELATIONSHIPS ---
    {
        "code": "e1_meaningful_connections",
        "section": "section_e",
        "text": "Did you establish any meaningful professional connections during CCI STEM Connect?",
        "type": QuestionType.SINGLE_CHOICE.value,
        "required": True,
        "scorable": True,
        "category": "networking_and_relationships",
        "pillars": ["networking_and_relationships"],
        "options": [
            ("yes_several", "Yes, several", 100.0, 1),
            ("yes_one_or_two", "Yes, one or two", 65.0, 2),
            ("no", "No", 0.0, 3),
        ],
        "rule": (
            ScoringRuleType.SINGLE_CHOICE.value,
            {
                "option_scores": {"yes_several": 100.0, "yes_one_or_two": 65.0, "no": 0.0},
                "max_score": 100.0,
            },
        ),
        "order": 1,
    },
    {
        "code": "e2_collaboration_opportunities",
        "section": "section_e",
        "text": "Did you identify any potential collaboration opportunities?",
        "type": QuestionType.SINGLE_CHOICE.value,
        "required": True,
        "scorable": True,
        "category": "networking_and_relationships",
        "pillars": ["networking_and_relationships"],
        "options": [
            ("yes", "Yes", 100.0, 1),
            ("possibly", "Possibly", 55.0, 2),
            ("no", "No", 0.0, 3),
        ],
        "rule": (
            ScoringRuleType.SINGLE_CHOICE.value,
            {
                "option_scores": {"yes": 100.0, "possibly": 55.0, "no": 0.0},
                "max_score": 100.0,
            },
        ),
        "order": 2,
    },
    {
        "code": "e3_mentorship_opportunities",
        "section": "section_e",
        "text": "Did you identify any mentorship or professional development opportunities?",
        "type": QuestionType.SINGLE_CHOICE.value,
        "required": True,
        "scorable": True,
        "category": "networking_and_relationships",
        "pillars": ["networking_and_relationships"],
        "options": [
            ("yes", "Yes", 100.0, 1),
            ("possibly", "Possibly", 55.0, 2),
            ("no", "No", 0.0, 3),
        ],
        "rule": (
            ScoringRuleType.SINGLE_CHOICE.value,
            {
                "option_scores": {"yes": 100.0, "possibly": 55.0, "no": 0.0},
                "max_score": 100.0,
            },
        ),
        "order": 3,
    },
    {
        "code": "e4_followed_up_professionals",
        "section": "section_e",
        "text": "Have you followed up with any of the professionals you met?",
        "type": QuestionType.SINGLE_CHOICE.value,
        "required": True,
        "scorable": True,
        "category": "networking_and_relationships",
        "pillars": ["networking_and_relationships"],
        "options": [
            ("yes", "Yes", 100.0, 1),
            ("not_yet_intend_to", "Not yet, but I intend to", 50.0, 2),
            ("no", "No", 0.0, 3),
        ],
        "rule": (
            ScoringRuleType.SINGLE_CHOICE.value,
            {
                "option_scores": {"yes": 100.0, "not_yet_intend_to": 50.0, "no": 0.0},
                "max_score": 100.0,
            },
        ),
        "order": 4,
    },
    {
        "code": "e5_desired_relationships",
        "section": "section_e",
        "text": "What type of professional relationship or opportunity would you like to develop from the connections you made?",
        "type": QuestionType.MULTIPLE_CHOICE.value,
        "required": False,
        "scorable": False,
        "category": "networking_and_relationships",
        "pillars": ["networking_and_relationships"],
        "allow_explanation": True,
        "explanation_prompt": "If you selected Other, please specify.",
        "options": [
            ("mentorship", "Mentorship", None, 1),
            ("collaboration", "Collaboration", None, 2),
            ("employment_opportunities", "Employment opportunities", None, 3),
            ("business_partnerships", "Business partnerships", None, 4),
            ("knowledge_sharing", "Knowledge sharing", None, 5),
            ("professional_friendships", "Professional friendships", None, 6),
            ("other", "Other", None, 7),
        ],
        "order": 5,
    },
    # --- SECTION F — POST-EVENT APPLICATION (INTENDED) ---
    {
        "code": "f1_intended_idea_to_apply",
        "section": "section_f",
        "text": "What specific idea or lesson from the event do you intend to apply in your professional life?",
        "type": QuestionType.LONG_TEXT.value,
        "required": True,
        "scorable": False,
        "category": "post_event_application",
        "pillars": ["post_event_application"],
        "scoring_config": {"impact_classification": "intended_application"},
        "order": 1,
    },
    {
        "code": "f2_areas_to_improve",
        "section": "section_f",
        "text": "Which area of your professional life would you most like to improve?",
        "type": QuestionType.MULTIPLE_CHOICE.value,
        "required": True,
        "scorable": False,
        "category": "post_event_application",
        "pillars": ["post_event_application"],
        "allow_explanation": True,
        "explanation_prompt": "If you selected Other, please specify.",
        "options": [
            ("work_ethic_and_discipline", "Work ethic and discipline", None, 1),
            ("productivity_and_time_management", "Productivity and time management", None, 2),
            ("integrity_and_professional_responsibility", "Integrity and professional responsibility", None, 3),
            ("communication", "Communication", None, 4),
            ("leadership", "Leadership", None, 5),
            ("technical_or_professional_skills", "Technical or professional skills", None, 6),
            ("collaboration_and_teamwork", "Collaboration and teamwork", None, 7),
            ("relationship_building", "Relationship building", None, 8),
            ("recognition_of_excellence", "Recognition of excellence", None, 9),
            ("other", "Other", None, 10),
        ],
        "order": 2,
    },
    {
        "code": "f3_intend_to_share_knowledge",
        "section": "section_f",
        "text": "Do you intend to share any knowledge or insight from this event with another person?",
        "type": QuestionType.SINGLE_CHOICE.value,
        "required": True,
        "scorable": False,
        "category": "post_event_application",
        "pillars": ["post_event_application"],
        "scoring_config": {"impact_classification": "intended_application"},
        "options": [
            ("yes", "Yes", None, 1),
            ("no", "No", None, 2),
            ("not_sure_yet", "Not sure yet", None, 3),
        ],
        "order": 3,
    },
    {
        "code": "f4_action_within_30_days",
        "section": "section_f",
        "text": "What action will you take within the next 30 days as a result of this event?",
        "type": QuestionType.LONG_TEXT.value,
        "required": True,
        "scorable": False,
        "category": "post_event_application",
        "pillars": ["post_event_application"],
        "scoring_config": {"impact_classification": "intended_application"},
        "order": 4,
    },
    {
        "code": "f5_commitment_to_apply",
        "section": "section_f",
        "text": "How committed are you to applying the insights you gained?",
        "type": QuestionType.RATING_SCALE.value,
        "required": True,
        "scorable": True,
        "category": "post_event_application",
        "pillars": ["post_event_application"],
        "validation_config": {"min": 1, "max": 5},
        "scoring_config": {"impact_classification": "intended_commitment"},
        "options": RATING_1_5_OPTIONS,
        "rule": (
            ScoringRuleType.RATING_SCALE.value,
            {"min": 1, "max": 5, "impact_classification": "intended_commitment"},
        ),
        "order": 5,
    },
]

# ---------------------------------------------------------------------------
# 6. Follow-Up Questionnaires (30-Day, 60-Day, 90-Day)
# ---------------------------------------------------------------------------

FOLLOW_UP_QUESTIONNAIRES: list[dict[str, Any]] = [
    {
        "code": "cci-stem-connect-30-day-follow-up",
        "title": "CCI STEM Connect — 30-Day Follow-Up",
        "description": "Measure early application of event insights 30 days after CCI STEM Connect.",
        "stage": "30_day",
        "section_code": "stage_30_day",
        "section_title": "30-Day Early Application Check-In",
        "questions": [
            {
                "code": "fu_30d_01_applied_insights",
                "text": "Have you applied any of the ideas or insights you gained from CCI STEM Connect?",
                "type": QuestionType.SINGLE_CHOICE.value,
                "required": True,
                "scorable": True,
                "category": "post_event_application",
                "pillars": ["post_event_application"],
                "options": [
                    ("yes", "Yes", 100.0, 1),
                    ("partially", "Partially", 55.0, 2),
                    ("not_yet", "Not yet", 0.0, 3),
                ],
                "rule": (
                    ScoringRuleType.SINGLE_CHOICE.value,
                    {"option_scores": {"yes": 100.0, "partially": 55.0, "not_yet": 0.0}, "max_score": 100.0},
                ),
                "order": 1,
            },
            {
                "code": "fu_30d_02_specific_action",
                "text": "What specific action have you taken as a result of the event?",
                "type": QuestionType.LONG_TEXT.value,
                "required": False,
                "scorable": False,
                "category": "post_event_application",
                "pillars": ["post_event_application"],
                "order": 2,
            },
            {
                "code": "fu_30d_03_followed_up_connections",
                "text": "Have you followed up with any professional connections established during the event?",
                "type": QuestionType.SINGLE_CHOICE.value,
                "required": True,
                "scorable": True,
                "category": "networking_and_relationships",
                "pillars": ["networking_and_relationships"],
                "options": [
                    ("yes", "Yes", 100.0, 1),
                    ("no", "No", 0.0, 2),
                    ("not_yet", "Not yet", 25.0, 3),
                ],
                "rule": (
                    ScoringRuleType.SINGLE_CHOICE.value,
                    {"option_scores": {"yes": 100.0, "no": 0.0, "not_yet": 25.0}, "max_score": 100.0},
                ),
                "order": 3,
            },
            {
                "code": "fu_30d_04_shared_knowledge",
                "text": "Have you shared any knowledge or insight from the event with someone else?",
                "type": QuestionType.SINGLE_CHOICE.value,
                "required": True,
                "scorable": True,
                "category": "post_event_application",
                "pillars": ["post_event_application"],
                "options": [
                    ("yes", "Yes", 100.0, 1),
                    ("no", "No", 0.0, 2),
                    ("planning_to", "Planning to", 35.0, 3),
                ],
                "rule": (
                    ScoringRuleType.SINGLE_CHOICE.value,
                    {"option_scores": {"yes": 100.0, "no": 0.0, "planning_to": 35.0}, "max_score": 100.0},
                ),
                "order": 4,
            },
            {
                "code": "fu_30d_05_habit_changes",
                "text": "Have you noticed any changes in your work ethic, productivity or professional habits?",
                "type": QuestionType.LONG_TEXT.value,
                "required": False,
                "scorable": False,
                "category": "workplace_excellence",
                "pillars": ["workplace_excellence"],
                "order": 5,
            },
            {
                "code": "fu_30d_06_challenges",
                "text": "What challenges have prevented you from applying any of the lessons from the event?",
                "type": QuestionType.LONG_TEXT.value,
                "required": False,
                "scorable": False,
                "category": "post_event_application",
                "pillars": ["post_event_application"],
                "order": 6,
            },
        ],
    },
    {
        "code": "cci-stem-connect-60-day-follow-up",
        "title": "CCI STEM Connect — 60-Day Follow-Up",
        "description": "Measure continued application, relationship development and emerging improvements 60 days after CCI STEM Connect.",
        "stage": "60_day",
        "section_code": "stage_60_day",
        "section_title": "60-Day Continued Application & Relationships",
        "questions": [
            {
                "code": "fu_60d_01_still_applying",
                "text": "Are you still applying any of the ideas or lessons gained from CCI STEM Connect?",
                "type": QuestionType.SINGLE_CHOICE.value,
                "required": True,
                "scorable": True,
                "category": "post_event_application",
                "pillars": ["post_event_application"],
                "options": [
                    ("consistently", "Consistently", 100.0, 1),
                    ("occasionally", "Occasionally", 65.0, 2),
                    ("no_longer", "No longer", 20.0, 3),
                    ("not_yet", "Not yet", 0.0, 4),
                ],
                "rule": (
                    ScoringRuleType.SINGLE_CHOICE.value,
                    {
                        "option_scores": {
                            "consistently": 100.0,
                            "occasionally": 65.0,
                            "no_longer": 20.0,
                            "not_yet": 0.0,
                        },
                        "max_score": 100.0,
                    },
                ),
                "order": 1,
            },
            {
                "code": "fu_60d_02_practice_changes",
                "text": "What changes have you made to your professional habits or workplace practices since the event?",
                "type": QuestionType.LONG_TEXT.value,
                "required": False,
                "scorable": False,
                "category": "workplace_excellence",
                "pillars": ["workplace_excellence"],
                "order": 2,
            },
            {
                "code": "fu_60d_03_continued_collaboration",
                "text": "Have any of the professional connections you made resulted in continued communication or collaboration?",
                "type": QuestionType.SINGLE_CHOICE.value,
                "required": True,
                "scorable": True,
                "category": "networking_and_relationships",
                "pillars": ["networking_and_relationships"],
                "options": [
                    ("yes", "Yes", 100.0, 1),
                    ("no", "No", 0.0, 2),
                    ("discussions_ongoing", "Discussions ongoing", 60.0, 3),
                ],
                "rule": (
                    ScoringRuleType.SINGLE_CHOICE.value,
                    {"option_scores": {"yes": 100.0, "no": 0.0, "discussions_ongoing": 60.0}, "max_score": 100.0},
                ),
                "order": 3,
            },
            {
                "code": "fu_60d_04_relationship_opportunities",
                "text": "Have you experienced any professional, business or career opportunities connected to relationships from the event?",
                "type": QuestionType.LONG_TEXT.value,
                "required": False,
                "scorable": False,
                "category": "networking_and_relationships",
                "pillars": ["networking_and_relationships"],
                "order": 4,
            },
            {
                "code": "fu_60d_05_shared_skills",
                "text": "Have you shared any skills, knowledge or experience with another person since attending the event?",
                "type": QuestionType.LONG_TEXT.value,
                "required": False,
                "scorable": False,
                "category": "knowledge_and_insights",
                "pillars": ["knowledge_and_insights"],
                "order": 5,
            },
            {
                "code": "fu_60d_06_proudest_progress",
                "text": "What improvement or progress are you most proud of since attending CCI STEM Connect?",
                "type": QuestionType.LONG_TEXT.value,
                "required": False,
                "scorable": False,
                "category": "post_event_application",
                "pillars": ["post_event_application"],
                "order": 6,
            },
        ],
    },
    {
        "code": "cci-stem-connect-90-day-follow-up",
        "title": "CCI STEM Connect — 90-Day Follow-Up",
        "description": "Measure sustained application and tangible professional outcomes 90 days after CCI STEM Connect.",
        "stage": "90_day",
        "section_code": "stage_90_day",
        "section_title": "90-Day Sustained Impact & Outcomes",
        "questions": [
            {
                "code": "fu_90d_01_regular_practice",
                "text": "Which insights or lessons from CCI STEM Connect have become part of your regular professional practice?",
                "type": QuestionType.LONG_TEXT.value,
                "required": False,
                "scorable": False,
                "category": "post_event_application",
                "pillars": ["post_event_application"],
                "order": 1,
            },
            {
                "code": "fu_90d_02_measurable_improvement",
                "text": "What measurable improvement have you experienced in your productivity, work ethic or professional performance?",
                "type": QuestionType.LONG_TEXT.value,
                "required": False,
                "scorable": False,
                "category": "workplace_excellence",
                "pillars": ["workplace_excellence"],
                "order": 2,
            },
            {
                "code": "fu_90d_03_relationship_outcomes",
                "text": "Have any of the relationships established through the event resulted in completed collaboration, mentorship or professional opportunities?",
                "type": QuestionType.MULTIPLE_CHOICE.value,
                "required": True,
                "scorable": True,
                "category": "networking_and_relationships",
                "pillars": ["networking_and_relationships"],
                "options": [
                    ("completed_collaboration", "Completed collaboration", 35.0, 1),
                    ("active_mentorship", "Active mentorship", 30.0, 2),
                    ("professional_opportunity", "Professional opportunity", 35.0, 3),
                    ("business_partnership", "Business partnership", 35.0, 4),
                    ("continued_professional_relationship", "Continued professional relationship", 20.0, 5),
                    ("no_tangible_outcome_yet", "No tangible outcome yet", 0.0, 6),
                ],
                "rule": (
                    ScoringRuleType.MULTIPLE_CHOICE.value,
                    {
                        "option_scores": {
                            "completed_collaboration": 35.0,
                            "active_mentorship": 30.0,
                            "professional_opportunity": 35.0,
                            "business_partnership": 35.0,
                            "continued_professional_relationship": 20.0,
                            "no_tangible_outcome_yet": 0.0,
                        },
                        "aggregation": "sum",
                        "max_score": 100.0,
                    },
                ),
                "order": 3,
            },
            {
                "code": "fu_90d_04_tangible_outcome",
                "text": "What tangible outcome can you attribute, at least in part, to the connections or insights gained from CCI STEM Connect?",
                "type": QuestionType.LONG_TEXT.value,
                "required": False,
                "scorable": False,
                "category": "professional_outcomes",
                "pillars": ["post_event_application"],
                "order": 4,
            },
            {
                "code": "fu_90d_05_influenced_others",
                "text": "Have you influenced or helped another person improve their professional knowledge, work ethic or productivity?",
                "type": QuestionType.LONG_TEXT.value,
                "required": False,
                "scorable": False,
                "category": "knowledge_and_insights",
                "pillars": ["knowledge_and_insights"],
                "order": 5,
            },
            {
                "code": "fu_90d_06_overall_90d_value",
                "text": "Overall, how valuable has CCI STEM Connect been to your professional development over the past 90 days?",
                "type": QuestionType.RATING_SCALE.value,
                "required": True,
                "scorable": True,
                "category": "professional_outcomes",
                "pillars": ["post_event_application"],
                "validation_config": {"min": 1, "max": 5},
                "options": RATING_1_5_OPTIONS,
                "rule": (ScoringRuleType.RATING_SCALE.value, {"min": 1, "max": 5}),
                "order": 6,
            },
            {
                "code": "fu_90d_07_significant_change_share",
                "text": "What is one significant change or outcome you would like to share with the CCI STEM Connect community?",
                "type": QuestionType.LONG_TEXT.value,
                "required": False,
                "scorable": False,
                "category": "professional_outcomes",
                "pillars": ["post_event_application"],
                "order": 7,
            },
        ],
    },
]

# ---------------------------------------------------------------------------
# 7. Four Configurable Assessment Stages
# ---------------------------------------------------------------------------

ASSESSMENT_STAGES: list[dict[str, Any]] = [
    {
        "stage_code": "immediate",
        "stage_name": "Immediate Event Assessment",
        "days_after_event": 0,
        "display_order": 0,
        "questionnaire_code": INITIAL_QUESTIONNAIRE_CODE,
    },
    {
        "stage_code": "30_day",
        "stage_name": "30-Day Follow-Up",
        "days_after_event": 30,
        "display_order": 1,
        "questionnaire_code": "cci-stem-connect-30-day-follow-up",
    },
    {
        "stage_code": "60_day",
        "stage_name": "60-Day Follow-Up",
        "days_after_event": 60,
        "display_order": 2,
        "questionnaire_code": "cci-stem-connect-60-day-follow-up",
    },
    {
        "stage_code": "90_day",
        "stage_name": "90-Day Follow-Up",
        "days_after_event": 90,
        "display_order": 3,
        "questionnaire_code": "cci-stem-connect-90-day-follow-up",
    },
]

# ---------------------------------------------------------------------------
# 8. Legacy v1.0 Template Questions (preserved for historical/test compatibility)
# ---------------------------------------------------------------------------

LEGACY_TEMPLATE_SECTIONS = [
    ("section_a", "Section A — Professional Background", "Participant professional context and attendance motivation.", 1),
    ("section_b", "Section B — Event Engagement", "Participation, speaker/peer interaction, and discussion relevance.", 2),
    ("section_c", "Section C — Knowledge and Insights", "Key takeaways and perspectives gained on productivity and excellence.", 3),
    ("section_d", "Section D — Workplace Excellence and Recognition", "Understanding of professional standards, recognition, and rewards.", 4),
    ("section_e", "Section E — Networking and Professional Relationships", "Meaningful connections, collaborations, mentorship, and opportunities.", 5),
    ("section_f", "Section F — Post-Event Application", "Intentions, implemented ideas, changed habits, and shared knowledge.", 6),
]

LEGACY_TEMPLATE_QUESTIONS = [
    ("sec_a_reason_attending", "section_a", "What was your primary reason for attending CCI STEM Connect?", QuestionType.LONG_TEXT.value, False, [], None, 1),
    ("sec_b_discussion_participation", "section_b", "How actively did you participate in event discussions?", QuestionType.RATING_SCALE.value, True, ["professional_engagement"], (ScoringRuleType.RATING_SCALE.value, {"min": 1, "max": 5}), 1),
    ("sec_b_speaker_interaction", "section_b", "To what extent did you interact with speakers or panellists?", QuestionType.RATING_SCALE.value, True, ["professional_engagement"], (ScoringRuleType.RATING_SCALE.value, {"min": 1, "max": 5}), 2),
    ("sec_b_peer_interaction", "section_b", "How actively did you interact with other professionals during the event?", QuestionType.RATING_SCALE.value, True, ["professional_engagement"], (ScoringRuleType.RATING_SCALE.value, {"min": 1, "max": 5}), 3),
    ("sec_b_contributed_questions", "section_b", "Did you contribute a question, insight, or idea during the sessions?", QuestionType.YES_NO.value, True, ["professional_engagement"], (ScoringRuleType.YES_NO.value, {"yes_score": 100.0, "no_score": 0.0}), 4),
    ("sec_b_overall_engagement", "section_b", "How would you rate your overall engagement with CCI STEM Connect?", QuestionType.RATING_SCALE.value, True, ["professional_engagement"], (ScoringRuleType.RATING_SCALE.value, {"min": 1, "max": 5}), 5),
    ("sec_c_most_important_takeaway", "section_c", "What was your single most important takeaway from the event?", QuestionType.LONG_TEXT.value, False, ["knowledge_and_insights"], None, 1),
    ("sec_c_new_perspectives", "section_c", "To what extent did you gain new perspectives on workplace productivity and excellence?", QuestionType.RATING_SCALE.value, True, ["knowledge_and_insights"], (ScoringRuleType.RATING_SCALE.value, {"min": 1, "max": 5}), 2),
    ("sec_c_peer_knowledge", "section_c", "How valuable was the knowledge you gained from other professionals?", QuestionType.RATING_SCALE.value, True, ["knowledge_and_insights"], (ScoringRuleType.RATING_SCALE.value, {"min": 1, "max": 5}), 3),
    ("sec_c_decision_influence", "section_c", "How likely are the insights from this event to influence your professional decisions?", QuestionType.RATING_SCALE.value, True, ["knowledge_and_insights"], (ScoringRuleType.RATING_SCALE.value, {"min": 1, "max": 5}), 4),
    ("sec_d_standards_understanding", "section_d", "How much did the event improve your understanding of professional standards and excellence?", QuestionType.RATING_SCALE.value, True, ["workplace_excellence"], (ScoringRuleType.RATING_SCALE.value, {"min": 1, "max": 5}), 1),
    ("sec_d_org_performance_link", "section_d", "How clearly do you now see the link between individual excellence and organisational performance?", QuestionType.RATING_SCALE.value, True, ["workplace_excellence"], (ScoringRuleType.RATING_SCALE.value, {"min": 1, "max": 5}), 2),
    ("sec_d_recognition_insights", "section_d", "To what extent did you gain practical insights on how excellence should be recognised and rewarded?", QuestionType.RATING_SCALE.value, True, ["recognition_and_rewards"], (ScoringRuleType.RATING_SCALE.value, {"min": 1, "max": 5}), 3),
    ("sec_d_unrecognised_impact", "section_d", "How strongly did the event deepen your awareness of the consequences when organisations fail to recognise excellence?", QuestionType.RATING_SCALE.value, True, ["recognition_and_rewards"], (ScoringRuleType.RATING_SCALE.value, {"min": 1, "max": 5}), 4),
    ("sec_d_encourage_excellence_ideas", "section_d", "What practical ways can organisations better encourage and reward excellence?", QuestionType.LONG_TEXT.value, False, ["recognition_and_rewards"], None, 5),
    ("sec_e_meaningful_connections_count", "section_e", "How many meaningful professional connections did you establish at the event?", QuestionType.NUMERIC.value, True, ["networking_and_relationships"], (ScoringRuleType.NUMERIC_THRESHOLD.value, {"min_value": 0, "target_value": 5}), 1),
    ("sec_e_potential_collaboration", "section_e", "Did you identify at least one potential professional collaboration or mentorship opportunity?", QuestionType.YES_NO.value, True, ["networking_and_relationships"], (ScoringRuleType.YES_NO.value, {"yes_score": 100.0, "no_score": 0.0}), 2),
    ("sec_e_follow_up_conversations", "section_e", "Have you initiated follow-up conversations with connections made at the event?", QuestionType.RATING_SCALE.value, True, ["networking_and_relationships"], (ScoringRuleType.RATING_SCALE.value, {"min": 1, "max": 5}), 3),
    ("sec_f_intended_ideas", "section_f", "Which ideas from the event do you intend to apply in your workplace or career?", QuestionType.LONG_TEXT.value, False, ["post_event_application"], None, 1),
    ("sec_f_implemented_idea", "section_f", "Have you already implemented at least one idea or insight from the event?", QuestionType.YES_NO.value, True, ["post_event_application"], (ScoringRuleType.YES_NO.value, {"yes_score": 100.0, "no_score": 0.0}), 2),
    ("sec_f_habits_changed", "section_f", "To what extent have you changed professional habits based on the event?", QuestionType.RATING_SCALE.value, True, ["post_event_application"], (ScoringRuleType.RATING_SCALE.value, {"min": 1, "max": 5}), 3),
    ("sec_f_shared_with_colleagues", "section_f", "Have you shared insights from the event with colleagues or your team?", QuestionType.YES_NO.value, True, ["post_event_application"], (ScoringRuleType.YES_NO.value, {"yes_score": 100.0, "no_score": 0.0}), 4),
]


def _ensure_question_with_options(
    db: Session,
    *,
    qdef: dict[str, Any],
    categories_by_code: dict[str, QuestionCategory],
    pillars_by_code: dict[str, MeasurementPillar],
    counts: dict[str, int],
) -> Question:
    q = db.execute(select(Question).where(Question.code == qdef["code"])).scalar_one_or_none()
    cat_code = qdef.get("category")
    cat_obj = categories_by_code.get(cat_code) if cat_code else None
    if q is None:
        q = Question(
            code=qdef["code"],
            question_text=qdef["text"],
            description=qdef.get("description"),
            question_type=qdef["type"],
            category=cat_obj.name if cat_obj else cat_code,
            category_id=cat_obj.id if cat_obj else None,
            is_required=qdef.get("required", False),
            is_scorable=qdef.get("scorable", False),
            allow_explanation=qdef.get("allow_explanation", False),
            explanation_prompt=qdef.get("explanation_prompt"),
            validation_config=qdef.get("validation_config"),
            scoring_config=qdef.get("scoring_config"),
            display_order=qdef.get("order", 0),
        )
        db.add(q)
        db.flush()
        counts["questions"] += 1
    else:
        if cat_obj and q.category_id is None:
            q.category_id = cat_obj.id
            q.category = cat_obj.name

    # Ensure pillar mappings exist without duplicating
    existing_pids = set(
        db.execute(
            select(QuestionPillarMapping.pillar_id).where(
                QuestionPillarMapping.question_id == q.id
            )
        )
        .scalars()
        .all()
    )
    for idx, pcode in enumerate(qdef.get("pillars", [])):
        pid = pillars_by_code[pcode].id
        if pid not in existing_pids:
            db.add(
                QuestionPillarMapping(
                    question_id=q.id, pillar_id=pid, is_primary=(idx == 0)
                )
            )
            existing_pids.add(pid)

    # Ensure answer options exist without duplicating
    existing_opt_vals = set(
        db.execute(
            select(QuestionOption.option_value).where(QuestionOption.question_id == q.id)
        )
        .scalars()
        .all()
    )
    for opt_val, opt_label, opt_score, opt_order in qdef.get("options", []):
        if opt_val not in existing_opt_vals:
            db.add(
                QuestionOption(
                    question_id=q.id,
                    option_value=opt_val,
                    option_label=opt_label,
                    score_value=opt_score,
                    display_order=opt_order,
                    is_active=True,
                )
            )
            existing_opt_vals.add(opt_val)

    return q


def _ensure_scoring_rule(
    db: Session,
    *,
    framework: ScoringFramework,
    dimension: ScoringDimension,
    question: Question,
    rule_type: str,
    rule_config: dict[str, Any],
    counts: dict[str, int],
) -> None:
    existing = db.execute(
        select(ScoringRule).where(
            ScoringRule.framework_id == framework.id,
            ScoringRule.dimension_id == dimension.id,
            ScoringRule.question_id == question.id,
        )
    ).scalar_one_or_none()
    if existing is None:
        db.add(
            ScoringRule(
                framework_id=framework.id,
                dimension_id=dimension.id,
                question_id=question.id,
                rule_type=rule_type,
                rule_config=rule_config,
                question_weight=1.0,
                is_active=True,
            )
        )
        counts["rules"] += 1


def seed_reference_data(db: Session) -> dict[str, int]:
    """Idempotently populate CCI STEM Connect event, pillars, categories, questionnaires,
    reflection cards, scoring framework/rules, and follow-up stages.
    """
    counts = {
        "events": 0,
        "objectives": 0,
        "pillars": 0,
        "event_pillars": 0,
        "categories": 0,
        "cards": 0,
        "questions": 0,
        "questionnaires": 0,
        "stages": 0,
        "rules": 0,
    }

    # 1. Default Event: CCI STEM Connect
    event = db.execute(
        select(Event).where(Event.slug == DEFAULT_EVENT_SLUG)
    ).scalar_one_or_none()
    if event is None:
        event = Event(**DEFAULT_EVENT_CONFIG)
        db.add(event)
        db.flush()
        counts["events"] += 1
    else:
        # Reconcile configuration without overwriting confirmed event_date/location
        event.title = DEFAULT_EVENT_CONFIG["title"]
        event.headline = DEFAULT_EVENT_CONFIG["headline"]
        event.event_category = DEFAULT_EVENT_CONFIG["event_category"]
        event.description = DEFAULT_EVENT_CONFIG["description"]
        event.introduction = DEFAULT_EVENT_CONFIG["introduction"]
        event.status = DEFAULT_EVENT_CONFIG["status"]
        event.is_default = True
        event.assessment_enabled = True
        event.follow_up_enabled = True
        event.public_visibility = True
        event.reflection_cards_enabled = True
        event.immediate_assessment_enabled = True
        event.follow_up_30d_enabled = True
        event.follow_up_60d_enabled = True
        event.follow_up_90d_enabled = True

    # 2. Event Objectives (7 records)
    for order, obj_text in EVENT_OBJECTIVES:
        obj = db.execute(
            select(EventObjective).where(
                EventObjective.event_id == event.id,
                EventObjective.display_order == order,
            )
        ).scalar_one_or_none()
        if obj is None:
            db.add(
                EventObjective(
                    event_id=event.id,
                    objective_text=obj_text,
                    display_order=order,
                )
            )
            counts["objectives"] += 1
        elif obj.objective_text != obj_text:
            obj.objective_text = obj_text

    # 3. Six Measurement Pillars
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
        else:
            pillar.name = pdef["name"]
            pillar.description = pdef["description"]
            pillar.default_weight = pdef["default_weight"]
            pillar.display_order = pdef["display_order"]
        pillars_by_code[pillar.code] = pillar

    # 4. Associate all 6 Measurement Pillars with CCI STEM Connect
    for pdef in PILLAR_DEFINITIONS:
        pillar = pillars_by_code[pdef["code"]]
        ep = db.execute(
            select(EventPillar).where(
                EventPillar.event_id == event.id,
                EventPillar.pillar_id == pillar.id,
            )
        ).scalar_one_or_none()
        if ep is None:
            db.add(
                EventPillar(
                    event_id=event.id,
                    pillar_id=pillar.id,
                    display_order=pdef["display_order"],
                    is_active=True,
                )
            )
            counts["event_pillars"] += 1

    # 5. Nine Question Categories
    categories_by_code: dict[str, QuestionCategory] = {}
    for cdef in QUESTION_CATEGORIES:
        cat = db.execute(
            select(QuestionCategory).where(QuestionCategory.code == cdef["code"])
        ).scalar_one_or_none()
        if cat is None:
            cat = QuestionCategory(**cdef)
            db.add(cat)
            db.flush()
            counts["categories"] += 1
        categories_by_code[cat.code] = cat

    # 6. Scoring Framework & Dimensions (reconcile existing v1.0 name cleanly without duplicates)
    framework = db.execute(
        select(ScoringFramework).where(
            ScoringFramework.name.in_(
                [
                    "CCI STEM Connect Participant Impact Framework",
                    "CCI STEM Connect Impact Framework",
                ]
            ),
            ScoringFramework.version == "1.0",
        )
    ).scalar_one_or_none()
    if framework is None:
        framework = ScoringFramework(
            name="CCI STEM Connect Participant Impact Framework",
            version="1.0",
            description=(
                "Configurable 6-pillar scoring framework (15/20/15/15/20/15 = 100%) "
                "with missing-dimension exclusion, weight renormalisation, and separation "
                "of immediate, intended application, actual application, and sustained impact."
            ),
            is_active=True,
            min_questions_per_pillar=1,
            min_pillars_required=2,
            min_completeness_ratio=0.25,
        )
        db.add(framework)
        db.flush()
    else:
        framework.name = "CCI STEM Connect Participant Impact Framework"

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

    # 7. Three Original Professional Reflection Cards (preserving exact wording & existing responses)
    reflection_cat = categories_by_code["professional_reflection"]
    for rc in REFLECTION_CARDS:
        card = db.execute(
            select(QuestionCard).where(QuestionCard.code == rc["card_code"])
        ).scalar_one_or_none()
        if card is None:
            card = QuestionCard(
                code=rc["card_code"],
                title=rc["card_title"],
                description=rc["card_description"],
                category=reflection_cat.name,
                is_active=True,
                display_order=rc["card_order"],
            )
            db.add(card)
            db.flush()
            counts["cards"] += 1
        else:
            card.title = rc["card_title"]
            card.description = rc["card_description"]
            card.category = reflection_cat.name
            card.display_order = rc["card_order"]

        existing_q = db.execute(
            select(Question).where(Question.code == rc["question_code"])
        ).scalar_one_or_none()
        if existing_q is None:
            q = Question(
                card_id=card.id,
                category_id=reflection_cat.id,
                code=rc["question_code"],
                question_text=rc["question_text"],
                description=rc["question_description"],
                question_type=rc["question_type"],
                category=reflection_cat.name,
                is_required=False,
                is_scorable=False,
                allow_explanation=rc["allow_explanation"],
                explanation_prompt=rc["explanation_prompt"],
                display_order=1,
            )
            db.add(q)
            db.flush()
            counts["questions"] += 1
        else:
            q = existing_q
            q.card_id = card.id
            q.category_id = reflection_cat.id
            q.category = reflection_cat.name
            q.is_scorable = False

        existing_pids = set(
            db.execute(
                select(QuestionPillarMapping.pillar_id).where(
                    QuestionPillarMapping.question_id == q.id
                )
            )
            .scalars()
            .all()
        )
        for idx, pcode in enumerate(rc["pillar_codes"]):
            pid = pillars_by_code[pcode].id
            if pid not in existing_pids:
                db.add(
                    QuestionPillarMapping(
                        question_id=q.id, pillar_id=pid, is_primary=(idx == 0)
                    )
                )
                existing_pids.add(pid)

    # 8. Initial Assessment Questionnaire (Sections A–F, 35 questions)
    questionnaires_by_code: dict[str, Questionnaire] = {}
    initial_qn = db.execute(
        select(Questionnaire).where(Questionnaire.code == INITIAL_QUESTIONNAIRE_CODE)
    ).scalar_one_or_none()
    if initial_qn is None:
        initial_qn = Questionnaire(
            event_id=event.id,
            code=INITIAL_QUESTIONNAIRE_CODE,
            title="CCI STEM Connect Initial Assessment",
            description=(
                "To understand participants' professional backgrounds, their level of "
                "engagement with CCI STEM Connect, the insights they gained, their "
                "understanding of workplace excellence, the relationships they established "
                "and the value they intend to apply to their professional journeys."
            ),
            questionnaire_type=QuestionnaireType.POST_EVENT.value,
            assessment_stage="immediate",
            version="1.0",
            status=QuestionnaireStatus.PUBLISHED.value,
            published_at=datetime.now(timezone.utc),
        )
        db.add(initial_qn)
        db.flush()
        counts["questionnaires"] += 1
    else:
        initial_qn.event_id = event.id
        initial_qn.assessment_stage = "immediate"
        if initial_qn.status != QuestionnaireStatus.PUBLISHED.value:
            initial_qn.status = QuestionnaireStatus.PUBLISHED.value
            initial_qn.published_at = initial_qn.published_at or datetime.now(timezone.utc)
    questionnaires_by_code[INITIAL_QUESTIONNAIRE_CODE] = initial_qn

    # Sections A–F
    initial_sections: dict[str, QuestionnaireSection] = {}
    for sec_code, sec_title, sec_desc, sec_order in INITIAL_ASSESSMENT_SECTIONS:
        sec = db.execute(
            select(QuestionnaireSection).where(
                QuestionnaireSection.questionnaire_id == initial_qn.id,
                QuestionnaireSection.code == sec_code,
            )
        ).scalar_one_or_none()
        if sec is None:
            sec = QuestionnaireSection(
                questionnaire_id=initial_qn.id,
                code=sec_code,
                title=sec_title,
                description=sec_desc,
                display_order=sec_order,
            )
            db.add(sec)
            db.flush()
        initial_sections[sec_code] = sec

    # Questions A1–F5 + options + links + scoring rules
    existing_initial_links = set(
        db.execute(
            select(QuestionnaireQuestion.question_id).where(
                QuestionnaireQuestion.questionnaire_id == initial_qn.id
            )
        )
        .scalars()
        .all()
    )
    for qdef in INITIAL_ASSESSMENT_QUESTIONS:
        q = _ensure_question_with_options(
            db,
            qdef=qdef,
            categories_by_code=categories_by_code,
            pillars_by_code=pillars_by_code,
            counts=counts,
        )
        if q.id not in existing_initial_links:
            db.add(
                QuestionnaireQuestion(
                    questionnaire_id=initial_qn.id,
                    section_id=initial_sections[qdef["section"]].id,
                    question_id=q.id,
                    display_order=qdef["order"],
                )
            )
            existing_initial_links.add(q.id)

        rule_spec = qdef.get("rule")
        if qdef.get("scorable") and rule_spec is not None and qdef.get("pillars"):
            rule_type, rule_config = rule_spec
            dim = dimensions_by_code[qdef["pillars"][0]]
            _ensure_scoring_rule(
                db,
                framework=framework,
                dimension=dim,
                question=q,
                rule_type=rule_type,
                rule_config=rule_config,
                counts=counts,
            )

    # 9. Follow-Up Questionnaires (30-Day, 60-Day, 90-Day)
    for fqdef in FOLLOW_UP_QUESTIONNAIRES:
        fqn = db.execute(
            select(Questionnaire).where(Questionnaire.code == fqdef["code"])
        ).scalar_one_or_none()
        if fqn is None:
            fqn = Questionnaire(
                event_id=event.id,
                code=fqdef["code"],
                title=fqdef["title"],
                description=fqdef["description"],
                questionnaire_type=QuestionnaireType.FOLLOW_UP.value,
                assessment_stage=fqdef["stage"],
                version="1.0",
                status=QuestionnaireStatus.PUBLISHED.value,
                published_at=datetime.now(timezone.utc),
            )
            db.add(fqn)
            db.flush()
            counts["questionnaires"] += 1
        questionnaires_by_code[fqdef["code"]] = fqn

        fsec = db.execute(
            select(QuestionnaireSection).where(
                QuestionnaireSection.questionnaire_id == fqn.id,
                QuestionnaireSection.code == fqdef["section_code"],
            )
        ).scalar_one_or_none()
        if fsec is None:
            fsec = QuestionnaireSection(
                questionnaire_id=fqn.id,
                code=fqdef["section_code"],
                title=fqdef["section_title"],
                description=fqdef["description"],
                display_order=1,
            )
            db.add(fsec)
            db.flush()

        existing_fq_links = set(
            db.execute(
                select(QuestionnaireQuestion.question_id).where(
                    QuestionnaireQuestion.questionnaire_id == fqn.id
                )
            )
            .scalars()
            .all()
        )
        for qdef in fqdef["questions"]:
            q = _ensure_question_with_options(
                db,
                qdef=qdef,
                categories_by_code=categories_by_code,
                pillars_by_code=pillars_by_code,
                counts=counts,
            )
            if q.id not in existing_fq_links:
                db.add(
                    QuestionnaireQuestion(
                        questionnaire_id=fqn.id,
                        section_id=fsec.id,
                        question_id=q.id,
                        display_order=qdef["order"],
                    )
                )
                existing_fq_links.add(q.id)

            rule_spec = qdef.get("rule")
            if qdef.get("scorable") and rule_spec is not None and qdef.get("pillars"):
                rule_type, rule_config = rule_spec
                dim = dimensions_by_code[qdef["pillars"][0]]
                _ensure_scoring_rule(
                    db,
                    framework=framework,
                    dimension=dim,
                    question=q,
                    rule_type=rule_type,
                    rule_config=rule_config,
                    counts=counts,
                )

    # 10. Link default questionnaire & active framework onto CCI STEM Connect event
    event.default_questionnaire_id = initial_qn.id
    event.active_framework_id = framework.id

    # 11. Four Configurable Assessment Stages (Immediate, 30-day, 60-day, 90-day)
    for stage in ASSESSMENT_STAGES:
        linked_qn = questionnaires_by_code.get(stage["questionnaire_code"])
        existing_stage = db.execute(
            select(FollowUpStageConfig).where(
                FollowUpStageConfig.event_id.is_(None),
                FollowUpStageConfig.stage_code == stage["stage_code"],
            )
        ).scalar_one_or_none()
        if existing_stage is None:
            db.add(
                FollowUpStageConfig(
                    event_id=None,
                    stage_code=stage["stage_code"],
                    stage_name=stage["stage_name"],
                    days_after_event=stage["days_after_event"],
                    questionnaire_id=linked_qn.id if linked_qn else None,
                    display_order=stage["display_order"],
                    is_active=True,
                )
            )
            counts["stages"] += 1
        else:
            existing_stage.stage_name = stage["stage_name"]
            existing_stage.days_after_event = stage["days_after_event"]
            existing_stage.display_order = stage["display_order"]
            if linked_qn and existing_stage.questionnaire_id is None:
                existing_stage.questionnaire_id = linked_qn.id

    # 12. Legacy v1.0 Template Questionnaire (preserved for backward compatibility)
    legacy_qn = db.execute(
        select(Questionnaire).where(Questionnaire.code == "cci-stem-assessment-v1")
    ).scalar_one_or_none()
    if legacy_qn is None:
        legacy_qn = Questionnaire(
            event_id=None,
            code="cci-stem-assessment-v1",
            title="CCI STEM Connect Participant Impact Assessment (Sections A–F Template)",
            description="Reusable template questionnaire preserved for version compatibility.",
            questionnaire_type=QuestionnaireType.POST_EVENT.value,
            assessment_stage="immediate",
            version="1.0",
            status=QuestionnaireStatus.PUBLISHED.value,
            published_at=datetime.now(timezone.utc),
        )
        db.add(legacy_qn)
        db.flush()

        legacy_sections: dict[str, QuestionnaireSection] = {}
        for sec_code, sec_title, sec_desc, sec_order in LEGACY_TEMPLATE_SECTIONS:
            sec = QuestionnaireSection(
                questionnaire_id=legacy_qn.id,
                code=sec_code,
                title=sec_title,
                description=sec_desc,
                display_order=sec_order,
            )
            db.add(sec)
            db.flush()
            legacy_sections[sec_code] = sec

        for (
            q_code,
            sec_code,
            q_text,
            q_type,
            is_scorable,
            pillar_codes,
            rule_spec,
            order,
        ) in LEGACY_TEMPLATE_QUESTIONS:
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
                    questionnaire_id=legacy_qn.id,
                    section_id=legacy_sections[sec_code].id,
                    question_id=q.id,
                    display_order=order,
                )
            )
            if is_scorable and rule_spec is not None and pillar_codes:
                rule_type, rule_config = rule_spec
                dim = dimensions_by_code[pillar_codes[0]]
                _ensure_scoring_rule(
                    db,
                    framework=framework,
                    dimension=dim,
                    question=q,
                    rule_type=rule_type,
                    rule_config=rule_config,
                    counts=counts,
                )

    db.commit()
    return counts


if __name__ == "__main__":
    with SessionLocal() as session:
        result = seed_reference_data(session)
        print(f"Seeded CCI STEM Connect reference data: {result}")
