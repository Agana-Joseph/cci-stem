"""Root API v1 router aggregating all domain route modules."""

from fastapi import APIRouter

from app.api.v1 import (
    admin,
    analytics,
    assessments,
    events,
    follow_ups,
    participants,
    question_cards,
    questionnaires,
    questions,
    reports,
    scoring,
)

api_v1_router = APIRouter()
api_v1_router.include_router(admin.router)
api_v1_router.include_router(participants.router)
api_v1_router.include_router(events.router)
api_v1_router.include_router(question_cards.router)
api_v1_router.include_router(questions.categories_router)
api_v1_router.include_router(questions.router)
api_v1_router.include_router(questionnaires.router)
api_v1_router.include_router(assessments.router)
api_v1_router.include_router(scoring.router)
api_v1_router.include_router(follow_ups.router)
api_v1_router.include_router(analytics.router)
api_v1_router.include_router(reports.router)
