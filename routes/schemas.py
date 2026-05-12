"""Pydantic request bodies shared by API route modules."""

from typing import Any

from pydantic import BaseModel, EmailStr, Field


class LoginBody(BaseModel):
    email: EmailStr
    password: str
    role: str | None = None


class SignupBody(BaseModel):
    role: str = Field(..., description="candidate or hr")
    name: str = Field(..., min_length=2, max_length=150)
    email: EmailStr
    password: str = Field(..., min_length=6)
    gender: str | None = None


# NOTE: Support both the legacy backend payload shape and the current frontend
# payload shape for skill-weight updates.
# Frontend currently sends: { jd_id, weights, cutoff_score }
# Older backend code may still send: { job_id, skill_scores, cutoff_score, question_count }
class SkillWeightsBody(BaseModel):
    skill_scores: dict[str, int] | None = None
    weights: dict[str, int] | None = None
    job_id: int | None = None
    jd_id: int | None = None
    cutoff_score: float | None = Field(default=None, ge=0, le=100)
    question_count: int | None = Field(default=None, ge=2, le=20)


class ScheduleInterviewBody(BaseModel):
    result_id: int
    interview_date: str
    interview_time: str | None = None


class InterviewScoreBody(BaseModel):
    result_id: int
    technical_score: float = Field(..., ge=0, le=100)


class InterviewStartBody(BaseModel):
    candidate_id: int | None = None
    result_id: int | None = None
    interview_token: str | None = None
    consent_given: bool = False
    total_time_seconds: int | None = Field(default=None, ge=300, le=7200)
    max_questions: int | None = Field(default=None, ge=2, le=20)


class InterviewAnswerBody(BaseModel):
    session_id: int
    question_id: int
    answer_text: str = ""
    skipped: bool = False
    time_taken_sec: int = Field(default=0, ge=0, le=600)


class InterviewEventBody(BaseModel):
    event_type: str = Field(..., min_length=1, max_length=80)
    detail: str | None = Field(default=None, max_length=300)
    timestamp: str | None = Field(default=None, max_length=60)
    meta: dict[str, Any] | None = None


# NOTE: These fields mirror the exact payload shape sent by
# interview-frontend/src/pages/HRJdManagementPage.jsx.
class HrJDCreateBody(BaseModel):
    title: str = Field(..., min_length=2, max_length=200)
    jd_text: str = Field(..., min_length=2)
    jd_dict_json: dict[str, Any] | None = None
    weights_json: dict[str, int] = Field(default_factory=dict)
    qualify_score: float = Field(default=65.0, ge=0, le=100)
    education_requirement: str | None = Field(default=None, max_length=50)
    experience_requirement: int = Field(default=0, ge=0, le=100)
    min_academic_percent: float = Field(default=0.0, ge=0, le=100)
    total_questions: int = Field(default=8, ge=2, le=50)
    project_question_ratio: float = Field(default=0.8, ge=0.0, le=1.0)
    total_duration_minutes: int = Field(default=30, ge=5, le=120, description="Total interview duration in minutes")
    score_weights_json: dict[str, float] | None = Field(default=None, description="Custom weights for final score calculation: {resume: 0.35, skills: 0.25, interview: 0.25, communication: 0.15}")


class HrJDUpdateBody(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=200)
    jd_text: str | None = Field(default=None, min_length=10)
    jd_dict_json: dict[str, Any] | None = None
    weights_json: dict[str, int] | None = None
    qualify_score: float | None = Field(default=None, ge=0, le=100)
    education_requirement: str | None = Field(default=None, max_length=50)
    experience_requirement: int | None = Field(default=None, ge=0, le=100)
    min_academic_percent: float | None = Field(default=None, ge=0, le=100)
    total_questions: int | None = Field(default=None, ge=2, le=50)
    project_question_ratio: float | None = Field(default=None, ge=0.0, le=1.0)
    total_duration_minutes: int | None = Field(default=None, ge=5, le=120)
    score_weights_json: dict[str, float] | None = Field(default=None, description="Custom weights for final score calculation")


class CandidateSelectJDBody(BaseModel):
    jd_id: int


class StageUpdateBody(BaseModel):
    stage: str = Field(..., min_length=2, max_length=50)
    note: str | None = Field(default=None, max_length=500)


class CandidateCompareBody(BaseModel):
    result_ids: list[int] = Field(default_factory=list, min_length=1, max_length=10)


class CandidateAssignJDBody(BaseModel):
    jd_id: int


class HrCandidateNotesBody(BaseModel):
    notes: str = Field(default="", max_length=5000)

# Standard API response wrapper
from pydantic import BaseModel as _BaseModel
from typing import Generic, TypeVar, Optional

T = TypeVar('T')

class ApiResponse(_BaseModel, Generic[T]):
    success: bool = True
    data: Optional[T] = None
    error: Optional[str] = None
