"""Aggregate API router mounted by main.py."""

from fastapi import APIRouter

from routes.auth.sessions import router as auth_router
from routes.candidate.workflow import router as candidate_router
from routes.hr.management import router as hr_router
from routes.interview.runtime import router as interview_router
from routes.interview.evaluation import router as evaluation_router
from routes.hr.interview_review import router as api_hr_dashboard_router
from routes.faq import router as faq_router

api_router = APIRouter(prefix="/api", tags=["api"])
api_router.include_router(auth_router)
api_router.include_router(candidate_router)
api_router.include_router(hr_router)
api_router.include_router(interview_router)
api_router.include_router(evaluation_router)
api_router.include_router(api_hr_dashboard_router)
api_router.include_router(faq_router)
