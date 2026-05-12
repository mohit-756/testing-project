"""
models.py — ORM models for Interview Bot.

FIX: Added dedicated HR decision columns to Result table so that
     HR decision data is no longer mixed into the resume explanation
     JSON blob. This eliminates silent data-loss bugs when multiple
     code paths write to result.explanation concurrently.
"""
from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey,
    Integer, JSON, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import relationship

from database import Base

# NOTE: Central ATS pipeline stages reused across screening, interview, ranking,
# and HR review screens.
APPLICATION_STAGES = (
    "applied",
    "screening",
    "shortlisted",
    "interview_scheduled",
    "interview_completed",
    "selected",
    "rejected",
)


class Candidate(Base):
    __tablename__ = "candidates"

    id = Column(Integer, primary_key=True, index=True)
    candidate_uid = Column(String(32), unique=True, nullable=True, index=True)
    name = Column(String(100))
    email = Column(String(120), unique=True, index=True)
    password = Column(String(200))
    gender = Column(String(20))
    resume_path = Column(String(300))
    # NOTE: Keep raw resume text and parsed structured resume data available for
    # ATS views, ranking, and HR detail pages.
    resume_text = Column(Text, nullable=True)
    parsed_resume_json = Column(JSON, nullable=True)
    selected_jd_id = Column(Integer, ForeignKey("jobs.id"), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=True, index=True)

    results = relationship("Result", back_populates="candidate", cascade="all, delete-orphan")
    interviews = relationship("InterviewSession", back_populates="candidate", cascade="all, delete-orphan")
    selected_jd = relationship("JobDescription", foreign_keys=[selected_jd_id])
    avatar_path = Column(String(300), nullable=True)
    linkedin_url = Column(String(500), nullable=True)
    github_url = Column(String(500), nullable=True)


class HR(Base):
    __tablename__ = "hr"

    id = Column(Integer, primary_key=True, index=True)
    company_name = Column(String(150))
    email = Column(String(120), unique=True, index=True)
    password = Column(String(200))
    avatar_path = Column(String(300), nullable=True)

    jobs = relationship("JobDescription", back_populates="company")


class JobDescription(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("hr.id"))
    title = Column(String(200), nullable=False)
    jd_title = Column(String(150), nullable=True) # Legacy alias
    jd_text = Column(Text, nullable=False)
    jd_dict_json = Column(JSON, nullable=True)
    weights_json = Column(JSON, nullable=True)
    skill_scores = Column(JSON, nullable=True) # Legacy alias
    qualify_score = Column(Float, default=65.0, nullable=False)
    cutoff_score = Column(Float, default=65.0, nullable=False) # Legacy alias
    min_academic_percent = Column(Float, default=0.0, nullable=False)
    total_questions = Column(Integer, default=8, nullable=False)
    question_count = Column(Integer, default=8, nullable=False) # Legacy alias
    project_question_ratio = Column(Float, default=0.8, nullable=False)
    total_duration_minutes = Column(Integer, default=30, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    gender_requirement = Column(String(50), nullable=True)
    education_requirement = Column(String(50), nullable=True)
    experience_requirement = Column(Integer, default=0, nullable=False)
    custom_questions = Column(JSON, nullable=True)
    
    # Configurable scoring weights for final application score
    # Default: resume=0.35, skills=0.25, interview=0.25, communication=0.15
    score_weights_json = Column(JSON, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    company = relationship("HR", back_populates="jobs")
    results = relationship("Result", back_populates="job")


class Result(Base):
    __tablename__ = "results"

    # Enforce one interview attempt per (candidate, JD) pair.
    __table_args__ = (
        UniqueConstraint("candidate_id", "job_id", name="uq_result_candidate_job"),
    )

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"))
    job_id = Column(Integer, ForeignKey("jobs.id"))
    application_id = Column(String(64), unique=True, nullable=True, index=True)

    # Resume screening output
    score = Column(Float)
    shortlisted = Column(Boolean)
    explanation = Column(JSON)  # resume scorecard only going forward
    interview_date = Column(String, nullable=True)
    interview_time = Column(String, nullable=True)
    interview_datetime = Column(DateTime, nullable=True)
    interview_link = Column(String, nullable=True)
    interview_questions = Column(JSON, nullable=True)
    interview_token = Column(String, nullable=True)
    events_json = Column(JSON, nullable=True)
    reminder_24h_sent = Column(Boolean, default=False, nullable=True)
    reminder_1h_sent = Column(Boolean, default=False, nullable=True)
    interview_rescheduled_count = Column(Integer, default=0, nullable=True)
    eligibility_feedback = Column(Text, nullable=True)
    # NOTE: ATS pipeline state and final ranking values live on the application row.
    stage = Column(String(50), default="applied", nullable=False, index=True)
    stage_updated_at = Column(DateTime, default=datetime.utcnow, nullable=True)
    final_score = Column(Float, nullable=True)
    score_breakdown_json = Column(JSON, nullable=True)
    recommendation = Column(String(50), nullable=True)

    # FIX: Dedicated HR decision columns — no longer stored inside explanation JSON.
    # This prevents silent data loss when multiple code paths write to explanation.
    hr_decision = Column(String(20), nullable=True)          # 'selected' | 'rejected'
    hr_final_score = Column(Float, nullable=True)
    hr_behavioral_score = Column(Float, nullable=True)
    hr_communication_score = Column(Float, nullable=True)
    hr_notes = Column(Text, nullable=True)
    hr_red_flags = Column(Text, nullable=True)

    candidate = relationship("Candidate", back_populates="results")
    job = relationship("JobDescription", back_populates="results")
    sessions = relationship("InterviewSession", back_populates="result", cascade="all, delete-orphan")
    stage_history = relationship("ApplicationStageHistory", cascade="all, delete-orphan")


class InterviewSession(Base):
    __tablename__ = "interview_sessions"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), nullable=False, index=True)
    result_id = Column(Integer, ForeignKey("results.id"), nullable=False, index=True)
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    ended_at = Column(DateTime, nullable=True)
    status = Column(String(50), default="in_progress", nullable=False)
    per_question_seconds = Column(Integer, default=60, nullable=False)
    total_time_seconds = Column(Integer, default=1200, nullable=False)
    remaining_time_seconds = Column(Integer, default=1200, nullable=False)
    max_questions = Column(Integer, default=8, nullable=False)
    baseline_face_signature = Column(Text, nullable=True)
    baseline_face_captured_at = Column(DateTime, nullable=True)
    consent_given = Column(Boolean, default=False, nullable=False)
    warning_count = Column(Integer, default=0, nullable=False)
    consecutive_violation_frames = Column(Integer, default=0, nullable=False)
    paused_until = Column(DateTime, nullable=True)
    # NEW: track LLM evaluation job status
    llm_eval_status = Column(String(20), default="pending", nullable=False)
    # values: pending | running | completed | failed
    # NOTE: Interview-level ATS summary for completed page and HR review.
    evaluation_summary_json = Column(JSON, nullable=True)
    recording_path = Column(String(500), nullable=True)
    recording_mime_type = Column(String(120), nullable=True)
    recording_size_bytes = Column(Integer, nullable=True)
    recording_uploaded_at = Column(DateTime, nullable=True)

    candidate = relationship("Candidate", back_populates="interviews")
    result = relationship("Result", back_populates="sessions")
    questions = relationship("InterviewQuestion", back_populates="session", cascade="all, delete-orphan")
    answers = relationship("InterviewAnswer", back_populates="session", cascade="all, delete-orphan")
    proctor_events = relationship("ProctorEvent", back_populates="session", cascade="all, delete-orphan")
    feedbacks = relationship("InterviewFeedback", back_populates="session", cascade="all, delete-orphan")


class InterviewQuestion(Base):
    __tablename__ = "interview_questions_v2"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("interview_sessions.id"), nullable=False, index=True)
    text = Column(Text, nullable=False)
    difficulty = Column(String(30), default="medium", nullable=False)
    topic = Column(String(80), default="general", nullable=False)
    # Final interview-question metadata used by runtime, evaluation, and HR review.
    question_type = Column(String(30), default="project", nullable=False)
    intent = Column(Text, nullable=True)
    focus_skill = Column(String(80), nullable=True)
    project_name = Column(String(160), nullable=True)
    reference_answer = Column(Text, nullable=True)
    metadata_json = Column(JSON, nullable=True)
    answer_text = Column(Text, nullable=True)
    answer_summary = Column(Text, nullable=True)
    relevance_score = Column(Float, nullable=True)
    allotted_seconds = Column(Integer, default=60, nullable=False)
    # NEW: Server-side tracking for question elapsed time
    started_at = Column(DateTime, nullable=True)
    time_taken_seconds = Column(Integer, nullable=True)
    skipped = Column(Boolean, default=False, nullable=False)
    llm_score = Column(Float, nullable=True)
    llm_feedback = Column(Text, nullable=True)
    evaluation_json = Column(JSON, nullable=True)

    session = relationship("InterviewSession", back_populates="questions")
    answers = relationship("InterviewAnswer", back_populates="question", cascade="all, delete-orphan")


class InterviewAnswer(Base):
    __tablename__ = "interview_answers"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("interview_sessions.id"), nullable=False, index=True)
    question_id = Column(Integer, ForeignKey("interview_questions_v2.id"), nullable=False, index=True)
    answer_text = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=True)
    ended_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    skipped = Column(Boolean, default=False, nullable=False)
    time_taken_sec = Column(Integer, default=0, nullable=False)
    llm_score = Column(Float, nullable=True)
    llm_feedback = Column(Text, nullable=True)
    # NOTE: Structured per-answer evaluation used by ATS review pages.
    evaluation_json = Column(JSON, nullable=True)

    session = relationship("InterviewSession", back_populates="answers")
    question = relationship("InterviewQuestion", back_populates="answers")


class ApplicationStageHistory(Base):
    __tablename__ = "application_stage_history"

    id = Column(Integer, primary_key=True, index=True)
    result_id = Column(Integer, ForeignKey("results.id"), nullable=False, index=True)
    stage = Column(String(50), nullable=False, index=True)
    note = Column(Text, nullable=True)
    changed_by_role = Column(String(20), nullable=True)
    changed_by_user_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)


class ProctorEvent(Base):
    __tablename__ = "proctor_events"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("interview_sessions.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    event_type = Column(String(80), nullable=False)
    score = Column(Float, default=0.0, nullable=False)
    meta_json = Column(JSON, nullable=True)
    image_path = Column(String(500), nullable=True)

    session = relationship("InterviewSession", back_populates="proctor_events")

class InterviewFeedback(Base):
    """Candidate experience feedback collected at the end of the session."""
    __tablename__ = "interview_feedbacks"

    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("interview_sessions.id"))
    rating = Column(Integer, nullable=False)  # 1-5 stars
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("InterviewSession", back_populates="feedbacks")


class PasswordResetToken(Base):
    """Secure one-time password reset tokens."""
    __tablename__ = "password_reset_tokens"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(120), nullable=False, index=True)
    token = Column(String(128), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class FAQQuestion(Base):
    """User-submitted questions for FAQ system."""
    __tablename__ = "faq_questions"

    id = Column(Integer, primary_key=True)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=True)
    status = Column(String(20), default="pending")
    user_type = Column(String(20), nullable=False)
    user_id = Column(Integer, nullable=False)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=True)
    answered_by = Column(Integer, ForeignKey("hr.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    answered_at = Column(DateTime, nullable=True)

    job = relationship("JobDescription")
    answered_by_user = relationship("HR")


class UserPreferences(Base):
    """Persisted notification and appearance preferences per user."""
    __tablename__ = "user_preferences"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    role = Column(String(20), nullable=False)
    preferences_json = Column(JSON, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)
