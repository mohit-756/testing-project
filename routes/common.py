from __future__ import annotations

"""Shared constants and helper functions used by route modules."""
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
import logging
from datetime import datetime, timedelta, timezone
import os
import re
from pathlib import Path
from urllib.parse import quote_plus
from uuid import uuid4
from zoneinfo import ZoneInfo
from sqlalchemy.orm import Session
from sqlalchemy import text

logger = logging.getLogger(__name__)

def create_error_handler(app: FastAPI):
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error(f"Unhandled exception: {exc}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"success": False, "data": None, "error": "Internal server error"},
        )

def create_http_exception_handler(app: FastAPI):
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"success": False, "data": None, "error": exc.detail},
        )

from core.config import config
from ai_engine.phase1.scoring import compute_resume_scorecard
from ai_engine.phase1.matching import extract_text_from_file
from models import Candidate, HR, JobDescription, Result
from services.pipeline import normalize_stage, record_stage_change, stage_payload
from services.resume_parser import parse_resume_text
from services.scoring import build_application_score

UPLOAD_DIR = config.UPLOAD_DIR
UPLOAD_DIR.mkdir(exist_ok=True, parents=True)


def utc_isoformat(value: datetime | None) -> str | None:
    if not value:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    return value.isoformat(timespec="seconds").replace("+00:00", "Z")


def frontend_base_url() -> str:
    return config.FRONTEND_URL.rstrip("/")


def interview_entry_url(result_id: int | None, token: str | None = None) -> str | None:
    if not result_id:
        return None
    base_url = frontend_base_url()
    encoded_token = quote_plus((token or "").strip()) if token else ""
    path = f"{base_url}/#/interview/{int(result_id)}"
    return f"{path}?token={encoded_token}" if encoded_token else path


def parse_interview_datetime_utc(interview_date: str, interview_time: str | None = None) -> datetime:
    date_raw = str(interview_date or "").strip()
    time_raw = str(interview_time or "").strip()
    if not date_raw:
        raise ValueError("Interview date is required")

    if "T" in date_raw:
        candidate = date_raw
    elif time_raw:
        candidate = f"{date_raw}T{time_raw}"
    else:
        candidate = date_raw

    normalized = candidate.replace("Z", "+00:00")
    parsed: datetime
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        parsed = datetime.strptime(date_raw, "%Y-%m-%d")
        if time_raw:
            hh, mm = time_raw.split(":")[:2]
            parsed = parsed.replace(hour=int(hh), minute=int(mm))

    if parsed.tzinfo is None:
        tz_name = str(getattr(config, "INTERVIEW_DEFAULT_TIMEZONE", "Asia/Kolkata") or "Asia/Kolkata")
        try:
            parsed = parsed.replace(tzinfo=ZoneInfo(tz_name))
        except Exception:
            parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc).replace(tzinfo=None)


def resolve_interview_datetime_utc(result: Result | None) -> datetime | None:
    if not result:
        return None
    if result.interview_datetime:
        return result.interview_datetime
    date_raw = str(result.interview_date or "").strip()
    if not date_raw:
        return None
    try:
        return parse_interview_datetime_utc(date_raw, result.interview_time)
    except Exception:
        return None


def interview_schedule_state(result: Result | None) -> dict[str, object]:
    scheduled_utc = resolve_interview_datetime_utc(result)
    now_utc = datetime.utcnow()
    if not scheduled_utc:
        return {
            "scheduled_utc": None,
            "window_open_utc": None,
            "window_close_utc": None,
            "can_start_now": False,
            "locked_reason": None,
        }

    early_min = max(0, int(getattr(config, "INTERVIEW_START_EARLY_MINUTES", 10) or 10))
    late_min = max(0, int(getattr(config, "INTERVIEW_START_LATE_GRACE_MINUTES", 30) or 30))
    window_open_utc = scheduled_utc - timedelta(minutes=early_min)
    window_close_utc = scheduled_utc + timedelta(minutes=late_min)
    can_start = window_open_utc <= now_utc <= window_close_utc

    locked_reason = None
    if now_utc < window_open_utc:
        locked_reason = "scheduled_for_future"
    elif now_utc > window_close_utc:
        locked_reason = "start_window_expired"

    return {
        "scheduled_utc": scheduled_utc,
        "window_open_utc": window_open_utc,
        "window_close_utc": window_close_utc,
        "can_start_now": can_start,
        "locked_reason": locked_reason,
    }


def _latest_interview_session(result: Result | None):
    sessions = getattr(result, "sessions", None) or []
    if not sessions:
        return None
    return max(
        sessions,
        key=lambda item: (item.started_at or datetime.min, item.id or 0),
    )


def _application_stage(result: Result | None, latest_session) -> str | None:
    if not result:
        return None

    session_status = str(getattr(latest_session, "status", "") or "").strip().lower()
    if session_status in {"selected", "rejected"}:
        return session_status
    if latest_session and (latest_session.ended_at or session_status == "completed"):
        return "interview_completed"
    if session_status == "in_progress":
        return "interview_scheduled"
    if result.interview_date:
        return "interview_scheduled"
    return normalize_stage(result.stage)


def interview_access_state(result: Result | None) -> dict[str, object]:
    if not result:
        return {
            "interview_scheduled": False,
            "interview_ready": False,
            "interview_locked_reason": None,
        }

    if not result.shortlisted:
        return {
            "interview_scheduled": False,
            "interview_ready": False,
            "interview_locked_reason": "shortlist_required",
        }

    if not (result.interview_date or "").strip():
        return {
            "interview_scheduled": False,
            "interview_ready": False,
            "interview_locked_reason": "schedule_required",
        }

    latest_session = _latest_interview_session(result)
    latest_status = str(getattr(latest_session, "status", "") or "").strip().lower()
    if latest_status == "in_progress":
        return {
            "interview_scheduled": True,
            "interview_ready": True,
            "interview_locked_reason": None,
        }

    if latest_session and (latest_session.ended_at or latest_status in {"completed", "selected", "rejected"}):
        return {
            "interview_scheduled": True,
            "interview_ready": False,
            "interview_locked_reason": "already_completed",
        }

    schedule = interview_schedule_state(result)
    if schedule["locked_reason"]:
        return {
            "interview_scheduled": True,
            "interview_ready": False,
            "interview_locked_reason": str(schedule["locked_reason"]),
        }

    return {
        "interview_scheduled": True,
        "interview_ready": True,
        "interview_locked_reason": None,
    }


def generate_candidate_uid(db: Session) -> str:
    """
    Generate sequential candidate UID: MMyyNNNN
    Example: 4260001 = Month(4) + Year(26) + 0001st candidate
    
    Format: MMyyNNNN where:
    - MM = month (1-12)
    - yy = 2-digit year  
    - NNNN = sequential number
    
    Returns sequential UID that increments each time.
    """
    from sqlalchemy import text
    
    now = datetime.utcnow()
    month = now.month
    year_2digit = now.strftime("%y")
    prefix = f"{month}{year_2digit}"  # e.g., "426" for April 2026
    
    # Direct SQL to find max
    # For SQLite: extract numeric part after prefix
    sql = text("""
        SELECT candidate_uid FROM candidates 
        WHERE candidate_uid LIKE :prefix || '%'
        AND LENGTH(candidate_uid) = 7
        ORDER BY CAST(SUBSTR(candidate_uid, 4) AS INTEGER) DESC 
        LIMIT 1
    """)
    result = db.execute(sql, {"prefix": prefix}).fetchone()
    
    max_num = 0
    if result and result[0]:
        uid = result[0]
        try:
            max_num = int(uid[len(prefix):])
        except (ValueError, IndexError):
            max_num = 0
    
    next_num = max_num + 1
    candidate_uid = f"{prefix}{next_num:04d}"
    
    return candidate_uid


def ensure_candidate_profile(candidate: Candidate, db: Session) -> bool:
    changed = False

    if not candidate.created_at:
        candidate.created_at = datetime.utcnow()
        changed = True

    if candidate.candidate_uid:
        return changed

    for _ in range(10):
        candidate_uid = generate_candidate_uid(db)
        query = db.query(Candidate).filter(Candidate.candidate_uid == candidate_uid)
        if candidate.id is not None:
            query = query.filter(Candidate.id != candidate.id)
        exists = query.first()
        if exists:
            continue
        candidate.candidate_uid = candidate_uid
        changed = True
        return changed

    raise RuntimeError("Unable to allocate a unique candidate ID after multiple attempts.")


def get_candidate_or_404(db: Session, candidate_id: int) -> Candidate:
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return candidate


def get_hr_or_404(db: Session, hr_id: int) -> HR:
    hr_user = db.query(HR).filter(HR.id == hr_id).first()
    if not hr_user:
        raise HTTPException(status_code=404, detail="HR user not found")
    return hr_user


def list_available_jobs(db: Session) -> list[dict[str, object]]:
    jobs = db.query(JobDescription).order_by(JobDescription.id.desc()).all()
    companies = {item.id: item.company_name for item in db.query(HR).all()}
    payload: list[dict[str, object]] = []
    for job in jobs:
        payload.append(
            {
                "id": job.id,
                "company_id": job.company_id,
                "company_name": companies.get(job.company_id, "Unknown Company"),
                "jd_title": job.jd_title or Path(job.jd_text).name,
                "jd_name": Path(job.jd_text).name,
                "gender_requirement": None,
                "education_requirement": job.education_requirement,
                "experience_requirement": job.experience_requirement,
                "skill_scores": job.skill_scores or {},
                "cutoff_score": float(job.qualify_score if job.qualify_score is not None else 65.0),
                "min_academic_percent": float(job.min_academic_percent if job.min_academic_percent is not None else 0.0),
                "question_count": int(job.total_questions if job.total_questions is not None else 8),
            }
        )
    return payload


def list_active_jds(db: Session) -> list[dict[str, object]]:
    jds = db.query(JobDescription).filter(JobDescription.is_active == True).order_by(JobDescription.id.desc()).all()
    payload: list[dict[str, object]] = []
    for jd in jds:
        payload.append(
            {
                "id": jd.id,
                "title": jd.title or jd.jd_title or "Untitled Role",
                "jd_text": jd.jd_text,
                "weights_json": jd.weights_json or jd.skill_scores or {},
                "qualify_score": float(jd.qualify_score if jd.qualify_score is not None else 65.0),
                "education_requirement": jd.education_requirement,
                "experience_requirement": int(jd.experience_requirement if jd.experience_requirement is not None else 0),
                "min_academic_percent": float(jd.min_academic_percent if jd.min_academic_percent is not None else 0.0),
                "total_questions": int(jd.total_questions if jd.total_questions is not None else 8),
                "project_question_ratio": float(jd.project_question_ratio if jd.project_question_ratio is not None else 0.8),
                "is_active": True,
                "created_at": jd.created_at,
            }
        )
    return payload


def serialize_result(result: Result | None) -> dict[str, object] | None:
    if not result:
        return None
    access = interview_access_state(result)
    latest_session = _latest_interview_session(result)
    schedule = interview_schedule_state(result)
    latest_session_status = str(getattr(latest_session, "status", "") or "").strip().lower() or None
    interview_completed = bool(
        latest_session and (latest_session.ended_at or latest_session_status in {"completed", "selected", "rejected"})
    )
    final_decision = (
        (str(result.hr_decision or "").strip().lower() if str(result.hr_decision or "").strip().lower() in {"selected", "rejected"} else None)
        or (latest_session_status if latest_session_status in {"selected", "rejected"} else None)
    )
    explanation = result.explanation or {}
    # NOTE: Dedicated HR review columns are now the source of truth.
    # Fall back to the legacy explanation JSON only when the new columns are empty.
    final_review = {
        "final_score": result.hr_final_score if result.hr_final_score is not None else explanation.get("hr_final_score"),
        "behavioral_score": result.hr_behavioral_score if result.hr_behavioral_score is not None else explanation.get("hr_behavioral_score"),
        "communication_score": result.hr_communication_score if result.hr_communication_score is not None else explanation.get("hr_communication_score"),
        "red_flags": result.hr_red_flags if result.hr_red_flags is not None else explanation.get("hr_red_flags"),
        "notes": result.hr_notes if result.hr_notes is not None else explanation.get("hr_final_notes"),
    }
    final_review_available = final_decision is not None or any(
        value is not None and value != "" for value in final_review.values()
    )
    return {
        "id": result.id,
        "score": float(result.score or 0),
        "final_score": float(result.final_score) if result.final_score is not None else None,
        "shortlisted": bool(result.shortlisted),
        "explanation": explanation,
        "score_breakdown": result.score_breakdown_json or {},
        "recommendation": result.recommendation,
        "stage": stage_payload(_application_stage(result, latest_session)),
        "interview_date": result.interview_date,
        "interview_time": result.interview_time,
        "interview_datetime": utc_isoformat(result.interview_datetime),
        "interview_datetime_utc": utc_isoformat(schedule["scheduled_utc"]),
        "interview_window_open_utc": utc_isoformat(schedule["window_open_utc"]),
        "interview_window_close_utc": utc_isoformat(schedule["window_close_utc"]),
        "interview_scheduled": bool(access["interview_scheduled"]),
        "interview_ready": bool(access["interview_ready"]),
        "interview_locked_reason": access["interview_locked_reason"],
        "interview_link": interview_entry_url(result.id, result.interview_token) if access["interview_scheduled"] else None,
        "interview_session_status": latest_session_status,
        "interview_completed": interview_completed,
        "final_decision": final_decision,
        "final_review": final_review if final_review_available else None,
        "application_stage": _application_stage(result, latest_session),
    }


def safe_delete_upload(stored_path: str | None) -> bool:
    if not stored_path:
        return False

    try:
        candidate_path = Path(stored_path)
        if not candidate_path.is_absolute():
            candidate_path = Path.cwd() / candidate_path
        resolved_path = candidate_path.resolve()
        upload_root = (Path.cwd() / UPLOAD_DIR).resolve()
        if upload_root != resolved_path and upload_root not in resolved_path.parents:
            return False
        if not resolved_path.is_file():
            return False
        resolved_path.unlink(missing_ok=True)
        return True
    except Exception:
        return False


def _load_jd_text(jd_text_value: str) -> str:
    import logging
    logger = logging.getLogger(__name__)
    raw = (jd_text_value or "").strip()
    if not raw:
        return ""
    if raw.startswith("{") or raw.startswith("["):
        logger.warning(f"_load_jd_text received JSON instead of text, returning empty: {raw[:100]}")
        return ""
    if len(raw) > 1000 and "job_title" in raw and "skills" in raw:
        logger.warning(f"_load_jd_text received JD JSON string, returning empty")
        return ""
    possible_path = Path(raw)
    if possible_path.is_file():
        return extract_text_from_file(raw)
    return raw


def extract_min_academic_percent(requirement_text: str | None) -> float:
    """Extract a minimum academic percentage from a requirement string (e.g. 'Min 60%')."""
    if not requirement_text:
        return 0.0
    match = re.search(r"(\d{2,3}(?:\.\d+)?)\s*%", requirement_text)
    if match:
        return float(match.group(1))
    return 0.0


def evaluate_resume_for_job(
    candidate: Candidate,
    job: JobDescription,
) -> tuple[float, dict[str, object], list[dict[str, str]]]:
    import logging
    logger = logging.getLogger(__name__)
    jd_text_raw = getattr(job, "jd_text", "") or ""
    logger.info(f"evaluate_resume_for_job: jd_text type={type(jd_text_raw)}, len={len(jd_text_raw)}, preview={jd_text_raw[:200]}")
    resume_text = candidate.resume_text or ""
    if not resume_text and candidate.resume_path:
        resume_text = extract_text_from_file(str(candidate.resume_path) if candidate.resume_path else "")
        candidate.resume_text = resume_text  # Persist for downstream logic
    candidate.parsed_resume_json = parse_resume_text(resume_text)
    jd_text = _load_jd_text(jd_text_raw)
    jd_skill_scores = (
        getattr(job, "skill_scores", None)
        or getattr(job, "weights_json", None)
        or {}
    )
    education_requirement = getattr(job, "education_requirement", None)
    experience_requirement = int(getattr(job, "experience_requirement", 0) or 0)
    min_academic_percent = float(
        getattr(job, "min_academic_percent", None)
        if getattr(job, "min_academic_percent", None) is not None
        else extract_min_academic_percent(education_requirement)
    )
    cutoff_score = float(
        getattr(job, "cutoff_score", None)
        if getattr(job, "cutoff_score", None) is not None
        else getattr(job, "qualify_score", 65.0)
    )
    question_count = int(
        getattr(job, "question_count", None)
        if getattr(job, "question_count", None) is not None
        else getattr(job, "total_questions", 8)
    )
    jd_title = getattr(job, "jd_title", None) or getattr(job, "title", None)
    project_ratio = float(getattr(job, "project_question_ratio", 0.80) or 0.80)
    project_ratio = max(0.0, min(1.0, project_ratio))
    explanation = compute_resume_scorecard(
        resume_text=resume_text,
        jd_text=jd_text,
        jd_skill_scores=jd_skill_scores,
        education_requirement=education_requirement,
        experience_requirement=experience_requirement,
        min_academic_percent=min_academic_percent,
    )
    explanation["cutoff_score_used"] = cutoff_score
    explanation["score_cutoff_met"] = float(explanation["final_resume_score"]) >= cutoff_score
    explanation["shortlist_eligible"] = bool(explanation["score_cutoff_met"])
    explanation["question_count_used"] = question_count
    explanation["project_ratio_used"] = project_ratio
    return float(explanation["final_resume_score"]), explanation, []


def upsert_result(
    db: Session,
    candidate_id: int,
    job_id: int,
    score: float,
    explanation: dict[str, object],
    interview_questions: list[dict[str, str]] | None = None,
    cutoff_score: float = 65.0,
    job=None,
) -> Result:
    score_cutoff_met = score >= float(cutoff_score)
    shortlisted = bool(explanation.get("shortlist_eligible", score_cutoff_met))

    explanation["score_cutoff_met"] = score_cutoff_met
    explanation["shortlist_eligible"] = shortlisted
    
    weights_json = None
    if job and hasattr(job, 'score_weights_json') and job.score_weights_json:
        weights_json = job.score_weights_json
    
    current = (
        db.query(Result)
        .filter(Result.candidate_id == candidate_id, Result.job_id == job_id)
        .order_by(Result.id.desc())
        .first()
    )
    score_breakdown = build_application_score(
        resume_score=float(explanation.get("final_resume_score") or score or 0.0),
        skills_match_score=float(explanation.get("matched_percentage") or 0.0),
        interview_score=0.0,
        communication_score=0.0,
        weights_json=weights_json,
    )
    target_stage = "shortlisted" if shortlisted else ("screening" if score is not None else "applied")

    if current:
        previous_stage = current.stage
        was_shortlisted = current.shortlisted
        current.score = score
        current.shortlisted = shortlisted
        current.explanation = explanation
        current.interview_questions = None
        current.score_breakdown_json = score_breakdown
        current.final_score = float(score_breakdown["final_weighted_score"])
        current.recommendation = str(score_breakdown["recommendation"])
        if not current.application_id:
            current.application_id = f"APP-{job_id}-{candidate_id}-{uuid4().hex[:6].upper()}"
        # FIX C4: Do NOT clear interview_date / interview_link / interview_token on re-score.
        if not current.interview_date:
            current.interview_date = None
            current.interview_link = None
            current.interview_token = None
        if previous_stage != target_stage:
            record_stage_change(db, current, stage=target_stage, changed_by_role="system", changed_by_user_id=None, note="Resume screening updated")
        
        db.commit()
        db.refresh(current)
        return current

    result = Result(
        candidate_id=candidate_id,
        job_id=job_id,
        score=score,
        shortlisted=shortlisted,
        explanation=explanation,
        application_id=f"APP-{job_id}-{candidate_id}-{uuid4().hex[:6].upper()}",
        interview_questions=None,
        stage=target_stage,
        score_breakdown_json=score_breakdown,
        final_score=float(score_breakdown["final_weighted_score"]),
        recommendation=str(score_breakdown["recommendation"]),
    )
    db.add(result)
    db.flush()
    record_stage_change(db, result, stage=target_stage, changed_by_role="system", changed_by_user_id=None, note="Application created")
    db.commit()
    db.refresh(result)
    return result
