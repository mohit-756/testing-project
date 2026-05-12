"""Interview runtime routes: question-bank loading, persistence, timed flow, and proctoring."""

from __future__ import annotations



import json

import hashlib

import logging

import os

import re

import time
import uuid

from datetime import datetime, timedelta

from threading import Lock

from pathlib import Path

from typing import Any

import requests

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, BackgroundTasks
from routes.auth import get_current_user
from services.rate_limit import limiter

from ai_engine.phase1.matching import extract_text_from_file

from fastapi.responses import RedirectResponse

from services.question_generation import build_question_bundle

from sqlalchemy.orm import Session

from ai_engine.phase3.question_flow import compute_dynamic_seconds, normalize_result_questions

from database import get_db
from core.config import config

from models import (
    Candidate,
    InterviewAnswer,
    InterviewQuestion,
    InterviewSession,
    JobDescription,
    ProctorEvent,
    Result,
)

from routes.common import interview_access_state, interview_entry_url, interview_schedule_state, utc_isoformat
from routes.dependencies import SessionUser, require_role

from services.pipeline import record_stage_change

from services.scoring import build_application_score, evaluate_answer, summarize_interview

from routes.schemas import InterviewAnswerBody, InterviewEventBody, InterviewStartBody

from routes.interview.evaluation import run_evaluation_task



from utils.proctoring_cv import analyze_frame, compare_signatures, should_store_periodic

from utils.stt_whisper import transcribe_audio_bytes



router = APIRouter(dependencies=[Depends(get_current_user)])

logger = logging.getLogger(__name__)

_TRANSCRIBE_CACHE_TTL_SECONDS = 120
_TRANSCRIBE_CACHE_MAX_ITEMS = 256
_transcribe_cache_lock = Lock()
_transcribe_cache: dict[str, tuple[float, dict[str, Any]]] = {}


def _transcribe_cache_get(key: str) -> dict[str, Any] | None:
    now = time.time()
    with _transcribe_cache_lock:
        stale = [k for k, (ts, _) in _transcribe_cache.items() if now - ts > _TRANSCRIBE_CACHE_TTL_SECONDS]
        for k in stale:
            _transcribe_cache.pop(k, None)
        row = _transcribe_cache.get(key)
        if not row:
            return None
        ts, payload = row
        if now - ts > _TRANSCRIBE_CACHE_TTL_SECONDS:
            _transcribe_cache.pop(key, None)
            return None
        return dict(payload)


def _transcribe_cache_set(key: str, payload: dict[str, Any]) -> None:
    now = time.time()
    with _transcribe_cache_lock:
        _transcribe_cache[key] = (now, dict(payload))
        if len(_transcribe_cache) > _TRANSCRIBE_CACHE_MAX_ITEMS:
            oldest_key = min(_transcribe_cache.items(), key=lambda item: item[1][0])[0]
            _transcribe_cache.pop(oldest_key, None)



PROCTOR_UPLOAD_ROOT = Path("uploads") / "proctoring"

PROCTOR_UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)

RECORDING_UPLOAD_ROOT = config.UPLOAD_DIR / "interview_recordings"

RECORDING_UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)

INTERVIEW_RECORDING_MAX_MB = int(os.getenv("INTERVIEW_RECORDING_MAX_MB", "200"))



HIGH_MOTION_THRESHOLD = 0.25

FACE_MISMATCH_THRESHOLD = 0.70

SHOULDER_MIN_THRESHOLD = 0.50

PERIODIC_SAVE_SECONDS = 10

VIOLATION_FRAMES_PER_WARNING = 3

PAUSE_SECONDS_ON_THIRD_WARNING = 60

MAX_WARNINGS_BEFORE_PAUSE = 3



PAUSE_ON_WARNINGS_ENABLED: bool = os.getenv("PROCTOR_PAUSE_ENABLED", "false").lower() == "true"



SUSPICIOUS_TYPES = {
    "no_face",
    "multi_face",
    "face_mismatch",
    "high_motion",
    "shoulder_missing",
    "baseline_no_face",
    "baseline_multi_face",
    "baseline_no_shoulder",
    "warning_issued",
    "pause_enforced",
    "tab_switch",
    "paste_detected",
    "gaze_away",
}





# NOTE: Routes WITH specific paths MUST be registered BEFORE the wildcard /interview/{result_id}
# because FastAPI matches in registration order, not by specificity.





def _ordered_questions(db: Session, session_id: int) -> list[InterviewQuestion]:

    return (

        db.query(InterviewQuestion)

        .filter(InterviewQuestion.session_id == session_id)

        .order_by(InterviewQuestion.id.asc())

        .all()

    )





def _ensure_session_questions(

    db: Session,

    *,

    session: InterviewSession,

    result: Result,

) -> list[InterviewQuestion]:

    """Materialize the planned question bank into session rows once.



    This makes the interview progression deterministic: the session gets exactly

    `session.max_questions` questions (or fewer only if the bank itself is shorter),

    and the runtime simply serves the next unanswered row.

    """

    existing = _ordered_questions(db, session.id)



    source_questions = normalize_result_questions(result.interview_questions)

    if not source_questions:

        raise HTTPException(

            status_code=400,

            detail="Interview questions are not available for this session yet. Please reopen the interview from pre-check.",

        )



    max_questions = int(session.max_questions or 8)

    planned = source_questions[:max_questions]

    job_title = _job_title_for_result(db, result)



    # If the session was created earlier with a short/partial question list (e.g. old bug),

    # top it up to match the planned max_questions. This prevents "finish after 2".

    if existing and len(existing) >= len(planned):

        return existing



    logger.info(

        "interview_session_questions_materialize_start session_id=%s result_id=%s planned=%s bank=%s",

        session.id,

        result.id,

        max_questions,

        len(source_questions),

    )



    created: list[InterviewQuestion] = []

    existing_texts = {str(q.text or "").strip().lower() for q in existing} if existing else set()

    start_index = len(existing) if existing else 0



    for index in range(start_index, len(planned)):
        item = planned[index]
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        if text.lower() in existing_texts:
            continue
        question = InterviewQuestion(
            session_id=session.id,
            text=text,
            difficulty=str(item.get("difficulty") or "medium"),
            topic=str(item.get("topic") or "general"),
            question_type=str(item.get("type") or "project"),
            intent=item.get("intent"),
            focus_skill=item.get("focus_skill"),
            project_name=item.get("project_name"),
            reference_answer=item.get("reference_answer"),
            metadata_json=item.get("metadata") if isinstance(item.get("metadata"), dict) else {
                "category": item.get("category") or item.get("type") or "project",
                "priority_source": item.get("priority_source") or "derived",
                "skill_or_topic": item.get("focus_skill") or item.get("topic") or text,
                "role_alignment": item.get("role_alignment"),
                "resume_alignment": item.get("resume_alignment"),
                "jd_alignment": item.get("jd_alignment"),
            },
        )
        existing_texts.add(text.lower())
        created.append(question)
        db.add(question)



    if not (existing or created):
        raise HTTPException(status_code=400, detail=f"Interview questions could not be prepared for {job_title}.")
    db.flush()
    logger.info(
        "interview_session_questions_materialize_success session_id=%s existing=%s created=%s total=%s",
        session.id,
        len(existing),
        len(created),
        len(existing) + len(created),
    )

    return _ordered_questions(db, session.id)





def _serialize_question(question: InterviewQuestion | None) -> dict[str, Any] | None:

    if not question:

        return None

    return {

        "id": question.id,

        "text": question.text,

        "difficulty": question.difficulty,

"topic": question.topic,
        "metadata": question.metadata_json or {},
    }





def _pause_seconds_left(session: InterviewSession, now: datetime | None = None) -> int:

    if not PAUSE_ON_WARNINGS_ENABLED:

        return 0

    if not session.paused_until:

        return 0

    ref = now or datetime.utcnow()

    return max(0, int((session.paused_until - ref).total_seconds()))





def _clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:

    return float(max(minimum, min(maximum, value)))





def _float_or_none(value: Any) -> float | None:

    if value is None:

        return None

    try:

        return float(value)

    except Exception:

        return None





def _compute_face_score(

    faces_count: int,

    face_similarity: float | None,

    baseline_ready: bool,

) -> float:

    if faces_count != 1:

        return 0.0

    if not baseline_ready:

        return 1.0

    if face_similarity is None:

        return 0.7

    normalized = (face_similarity - FACE_MISMATCH_THRESHOLD) / (1.0 - FACE_MISMATCH_THRESHOLD)

    return _clamp(normalized)





def _frame_reasons(

    *,

    faces_count: int,

    baseline_ready: bool,

    face_similarity: float | None,

    shoulder_model_enabled: bool,

    shoulder_score: float | None,

) -> list[str]:

    reasons: list[str] = []

    if faces_count == 0:

        reasons.append("No face detected. Please face the camera.")

    elif faces_count > 1:

        reasons.append("Only one person should be visible in the frame.")

    if baseline_ready and face_similarity is not None and face_similarity < FACE_MISMATCH_THRESHOLD:

        reasons.append("Face mismatch detected. Ensure only the candidate is in front of the camera.")

    if shoulder_model_enabled and (shoulder_score is None or shoulder_score < SHOULDER_MIN_THRESHOLD):

        reasons.append("Both shoulders must be visible in frame.")

    return reasons





def _frame_status_from_reasons(reasons: list[str], faces_count: int) -> str:

    if not reasons:

        return "green"

    if faces_count == 1:

        return "amber"

    return "red"





def _get_candidate_session_or_403(

    db: Session,

    session_id: int,

    current_user: SessionUser,

) -> InterviewSession:

    session = db.query(InterviewSession).filter(InterviewSession.id == session_id).first()

    if not session:

        raise HTTPException(status_code=404, detail="Interview session not found")

    if session.candidate_id != current_user.user_id:

        raise HTTPException(status_code=403, detail="You can access only your own interview session")

    return session





def _resolve_candidate_result(db: Session, candidate_id: int, result_id: int | None) -> Result:

    if result_id is not None:

        result = db.query(Result).filter(

            Result.id == result_id,

            Result.candidate_id == candidate_id,

        ).first()

        if not result:

            # Backward-compatible fallback: some clients may send an interview

            # session id in place of result_id. Resolve it only for the same

            # candidate to preserve access isolation.

            session = db.query(InterviewSession).filter(

                InterviewSession.id == result_id,

                InterviewSession.candidate_id == candidate_id,

            ).first()

            if session:

                result = db.query(Result).filter(

                    Result.id == session.result_id,

                    Result.candidate_id == candidate_id,

                ).first()

        if not result:

            raise HTTPException(status_code=404, detail="Interview result not found")

        return result



    result = (

        db.query(Result)

        .filter(

            Result.candidate_id == candidate_id,

            Result.shortlisted.is_(True),

            Result.interview_date.is_not(None),

        )

        .order_by(Result.id.desc())

        .first()

    )

    if result:

        return result



    result = (

        db.query(Result)

        .filter(Result.candidate_id == candidate_id, Result.shortlisted.is_(True))

        .order_by(Result.id.desc())

        .first()

    )

    if result:

        return result



    result = (

        db.query(Result)

        .filter(Result.candidate_id == candidate_id)

        .order_by(Result.id.desc())

        .first()

    )

    if not result:

        raise HTTPException(status_code=404, detail="No interview context found for candidate")

    return result





def _ensure_interview_ready(result: Result) -> None:

    access = interview_access_state(result)

    if access["interview_ready"]:

        return

    if access["interview_locked_reason"] == "shortlist_required":

        raise HTTPException(status_code=403, detail="Only shortlisted candidates can start interviews")

    if access["interview_locked_reason"] == "already_started":

        raise HTTPException(status_code=409, detail="Interview session is already in progress")

    if access["interview_locked_reason"] == "already_completed":

        raise HTTPException(status_code=400, detail="Interview session has already been submitted")

    if access["interview_locked_reason"] == "scheduled_for_future":
        raise HTTPException(status_code=403, detail="Interview can be started only within the allowed start window")

    if access["interview_locked_reason"] == "start_window_expired":
        raise HTTPException(status_code=403, detail="Interview start window has expired. Please reschedule.")

    raise HTTPException(status_code=400, detail="Schedule your interview before starting")





def _resolve_result_by_token(db: Session, candidate_id: int, token: str) -> Result:

    token_value = (token or "").strip()

    if not token_value:

        raise HTTPException(status_code=404, detail="Interview token is missing")

    return _resolve_result_by_token_or_id(db, candidate_id, token_value)


def _resolve_result_by_token_or_id(db: Session, candidate_id: int, token: str) -> Result:
    token_value = (token or "").strip()

    query = db.query(Result).filter(Result.candidate_id == candidate_id)

    by_token = query.filter(Result.interview_token == token_value).order_by(Result.id.desc()).first()

    if by_token:

        return by_token

    if token_value.isdigit():
        by_id = query.filter(Result.id == int(token_value)).first()

        if by_id:
            return by_id

    raise HTTPException(status_code=404, detail="Interview token is invalid")





def _latest_interview_session(db: Session, result: Result) -> InterviewSession | None:

    return (

        db.query(InterviewSession)

        .filter(InterviewSession.result_id == result.id)

        .order_by(InterviewSession.id.desc())

        .first()

    )





def _job_title_for_result(db: Session, result: Result) -> str:

    job = db.query(JobDescription).filter(JobDescription.id == result.job_id).first()

    return str(

        getattr(job, "jd_title", None)

        or getattr(job, "title", None)

        or getattr(job, "job_title", None)

        or "Interview"

    )





def _create_next_question(
    db: Session,
    session: InterviewSession,
    result: Result,
    last_answer: str,
) -> InterviewQuestion | None:
    ordered = _ordered_questions(db, session.id)
    remaining_total = int(session.remaining_time_seconds or session.total_time_seconds or 1200)
    if remaining_total <= 0:
        return None

    current_idx = 0
    for i, item in enumerate(ordered):
        if item.time_taken_seconds is not None:
            current_idx = i + 1
            continue
        
        # If we have an answer to the previous question, we can potentially generate a dynamic one
        if i > 0 and last_answer and i == current_idx:
            try:
                from services.llm_question_generator import generate_dynamic_next_question
                
                history = []
                for prev in ordered[:i]:
                    ans = db.query(InterviewAnswer).filter(InterviewAnswer.question_id == prev.id).first()
                    history.append({"question": prev.text, "answer": ans.answer_text if ans else ""})
                
                job = db.query(JobDescription).filter(JobDescription.id == result.job_id).first()
                candidate = result.candidate
                
                new_q_data = generate_dynamic_next_question(
                    resume_text=(candidate.resume_text if candidate else "") or "",
                    jd_title=(job.title or job.jd_title or "") if job else "",
                    jd_skill_scores=(job.weights_json or job.skill_scores or {}) if job else {},
                    history=history,
                    question_count=len(ordered)
                )
                
                if new_q_data:
                    item.text = new_q_data["text"]
                    item.question_type = "followup" if new_q_data.get("category") == "followup" else item.question_type
                    item.intent = new_q_data["intent"]
                    item.reference_answer = new_q_data["reference_answer"]
                    db.add(item)
                    db.commit()
            except Exception as exc:
                logger.warning("dynamic_question_generation_failed error=%s", exc)

        if item.started_at is None:
            item.started_at = datetime.utcnow()
            db.add(item)
            db.commit()
            db.refresh(item)
        return item

    return None





def _is_redundant_text(new_text: str, existing_texts: list[str]) -> bool:
    """Primary redundancy gate using content-word overlap."""
    if not new_text:
        return True
    
    def get_tokens(text):
        cleaned = re.sub(r"[^a-z0-9\s]", "", (text or "").lower())
        return set(cleaned.split())
    
    stop_words = {'the', 'a', 'an', 'and', 'or', 'to', 'of', 'in', 'for', 'on', 'with', 'is', 'are', 'your', 'you', 'how', 'why', 'what'}
    new_tokens = get_tokens(new_text) - stop_words
    
    for prev in existing_texts:
        prev_tokens = get_tokens(prev) - stop_words
        if not new_tokens or not prev_tokens:
            continue
        overlap = len(new_tokens & prev_tokens) / max(len(new_tokens), len(prev_tokens))
        if overlap > 0.65: # High semantic overlap threshold
            return True
    return False


def _is_stale_question_bank(questions: list[dict[str, Any]]) -> tuple[bool, str]:
    if not questions:
        return False, "empty"

    texts = [str(item.get("text") or "").strip() for item in questions if str(item.get("text") or "").strip()]
    
    # Check for prefix/redundancy in the bank itself
    for i, text in enumerate(texts):
        if _is_redundant_text(text, texts[:i]):
            return True, "redundant_in_bank"

    lowered = [text.lower() for text in texts]
    has_debugging = any(any(token in text for token in ("debug", "root cause", "bottleneck", "what failed", "what went wrong")) for text in lowered)
    has_design = any(any(token in text for token in ("scale", "redesign", "architecture", "trade-off", "tradeoff", "reliability", "observability")) for text in lowered)
    
    if not has_debugging:
        return True, "missing_debugging"
    if not has_design:
        return True, "missing_design"
    return False, "ok"


def _evaluate_answer_quality(answer: str) -> str:
    """Heuristic for adaptive difficulty."""
    answer = (answer or "").strip()
    words = answer.split()
    if len(words) < 15:
        return "weak"
    
    signals = {"because", "tradeoff", "bottleneck", "optimized", "instead", "internals", "latency", "failure"}
    signal_count = sum(1 for w in signals if w in answer.lower())
    
    if signal_count >= 2 or len(words) > 40:
        return "strong"
    return "average"





def _question_bank_category_coverage(questions: list[dict[str, Any]]) -> dict[str, bool]:

    categories: set[str] = set()

    type_to_category = {
        "opener": "intro",
        "behavioral": "behavioral",
        "project": "project",
        "deep_dive": "project",
        "architecture": "project",
        "leadership": "project",
        "debugging": "project",
        "decision": "project",
        "role_specific": "project",
    }

    for item in questions:

        if not isinstance(item, dict):

            continue

        explicit = str(item.get("category") or item.get("type") or "").strip().lower()

        if explicit:

            if explicit in type_to_category:
                categories.add(type_to_category[explicit])
            else:
                categories.add(explicit)

            continue



        text = str(item.get("text") or "").strip().lower()

        if not text:

            continue

        if "introduce yourself" in text or "your background" in text:

            categories.add("intro")

            continue

        if any(token in text for token in ("describe a time", "stakeholder", "collaboration", "conflict", "requirement changed")):

            categories.add("behavioral")

            continue

        if any(token in text for token in ("project", "debug", "root cause", "architecture", "scale", "trade-off", "tradeoff")):

            categories.add("project")



    project_like_categories = {"project", "deep_dive", "architecture", "leadership"}

    has_project_like = any(category in project_like_categories for category in categories)

    return {

        "has_intro": "intro" in categories,

        "has_project_like": has_project_like,

        "has_behavioral": "behavioral" in categories,

    }





def _log_question_bank_event(event: str, **payload: object) -> None:

    fields = {"event": event, **payload}

    logger.info("interview_question_bank_event %s", json.dumps(fields, sort_keys=True, default=str))





def _ensure_question_bank(

    db: Session,

    *,

    result: Result,

    candidate: Candidate,

    job: JobDescription | None,

    question_count: int,

) -> list[dict[str, Any]]:

    # If any session for this result is already in_progress or completed,
    # DO NOT regenerate — serve the existing bank to avoid mid-interview changes.
    active_session = (
        db.query(InterviewSession)
        .filter(
            InterviewSession.result_id == result.id,
            InterviewSession.status.in_(["in_progress", "completed"]),
        )
        .first()
    )
    if active_session:
        questions = normalize_result_questions(result.interview_questions)
        if questions:
            _log_question_bank_event(
                "locked_existing",
                result_id=result.id,
                candidate_id=candidate.id,
                session_id=active_session.id,
                session_status=active_session.status,
                question_count=len(questions),
                source="result.interview_questions",
                generation_mode="locked_by_active_session",
            )
            return questions

    questions = normalize_result_questions(result.interview_questions)



    # -- Prepend HR-mandated custom questions first --

    _cq = list(getattr(job, 'custom_questions', None) or [])

    if _cq:

        _exist = {str(q.get('text') or '').lower().strip() for q in questions}

        _add = [{'text': t.strip(), 'category': 'mandatory', 'type': 'mandatory'} for t in _cq if isinstance(t, str) and t.strip() and t.strip().lower() not in _exist]

        if _add:

            questions = _add + questions

            result.interview_questions = questions

            db.add(result)

            db.commit()



    stale, stale_reason = _is_stale_question_bank(questions)

    if questions and len(questions) >= int(question_count or 0 or 8) and not stale:

        coverage = _question_bank_category_coverage(questions)

        _log_question_bank_event(

            "loaded_existing",

            result_id=result.id,

            candidate_id=candidate.id,

            question_count=len(questions),

            source="result.interview_questions",

            generation_mode="stored_existing",

            stale_reason=stale_reason,

            **coverage,

        )

        return questions



    # If a question bank exists but is too small (e.g., older runs, partial saves,

    # or previously stubbed generation), regenerate to match the configured count.

    if questions and len(questions) < int(question_count or 8):

        logger.info(

            "interview_question_bank_regenerate_short_bank result_id=%s existing=%s desired=%s",

            result.id,

            len(questions),

            int(question_count or 8),

        )

    elif questions and stale:

        logger.info(

            "interview_question_bank_regenerate_stale_bank result_id=%s candidate_id=%s existing=%s reason=%s",

            result.id,

            candidate.id,

            len(questions),

            stale_reason,

        )

    resume_text = (candidate.resume_text or "").strip()

    if not resume_text:

        if not candidate.resume_path:

            raise HTTPException(status_code=400, detail="Resume is required before interview questions can be prepared.")

        resume_text = extract_text_from_file(candidate.resume_path or "") or ""

        if resume_text.strip():

            candidate.resume_text = resume_text.strip()

            db.add(candidate)

            db.commit()

            logger.info(

                "resume_text_backfilled candidate_id=%s file_path=%s text_len=%d",

                candidate.id,

                candidate.resume_path,

                len(resume_text),

            )

        else:

            raise HTTPException(status_code=400, detail="Candidate resume text could not be extracted for interview question generation.")

    logger.info(

        "resume_text_loaded candidate_id=%s source=db text_len=%d resume_text_preview=%s",

        candidate.id,

        len(resume_text),

        resume_text[:200],

    )



    job = db.query(JobDescription).filter(JobDescription.id == result.job_id).first()
    project_ratio = float(job.project_question_ratio) if job and job.project_question_ratio is not None else None



    _log_question_bank_event(

        "generate_start",

        result_id=result.id,

        candidate_id=candidate.id,

        requested_question_count=int(question_count or 8),

        stale_reason=stale_reason,

        existing_question_count=len(questions),

    )

    bundle = build_question_bundle(

        resume_text=resume_text,

        jd_title=(job.jd_title if job else None),

        jd_skill_scores=(job.skill_scores if job else {}) or {},

        question_count=int(question_count or 8),

        project_ratio=project_ratio,

    )

    bundle_meta = dict(bundle.get("meta") or {})

    generation_mode = str(bundle_meta.get("generation_mode") or "unknown")

    fallback_used = bool(bundle_meta.get("fallback_used"))

    llm_topped_up_with_fallback = bool(bundle_meta.get("llm_topped_up_with_fallback"))

    questions = normalize_result_questions(bundle.get("questions") or [])

    if not questions:

        raise HTTPException(status_code=400, detail="Interview questions could not be generated for this result yet.")

    logger.info(

        "question_bank_generated result_id=%s candidate_id=%s mode=%s fallback=%s count=%s questions_preview=%s",

        result.id,

        candidate.id,

        generation_mode,

        fallback_used,

        len(questions),

        [q.get("text", "")[:80] for q in questions[:3]],

    )



    coverage = _question_bank_category_coverage(questions)

    if not all(coverage.values()):

        _log_question_bank_event(

            "generation_failed_guardrail",

            result_id=result.id,

            candidate_id=candidate.id,

            question_count=len(questions),

            generation_mode=generation_mode,

            fallback_used=fallback_used,

            llm_topped_up_with_fallback=llm_topped_up_with_fallback,

            **coverage,

        )

        raise HTTPException(

            status_code=400,

            detail="Generated question bank is missing required category coverage (intro/project/behavioral).",

        )



    result.interview_questions = questions

    db.add(result)

    db.commit()

    db.refresh(result)

    _log_question_bank_event(

        "generated_fresh",

        result_id=result.id,

        candidate_id=candidate.id,

        question_count=len(questions),

        source="result.interview_questions",

        generation_mode=generation_mode,

        fallback_used=fallback_used,

        llm_topped_up_with_fallback=llm_topped_up_with_fallback,

        **coverage,

    )

    return questions





def _compose_start_response(

    session: InterviewSession,

    question: InterviewQuestion | None,

    answered_count: int,

) -> dict[str, Any]:

    pause_seconds_left = _pause_seconds_left(session)

    return {

        "ok": True,

        "session_id": session.id,

        "interview_completed": question is None,

        "current_question": _serialize_question(question),

        "question_number": answered_count + (1 if question else 0),

"max_questions": int(session.max_questions or 8),
        "remaining_total_seconds": int(session.remaining_time_seconds or session.total_time_seconds or 1200),
        "total_time_seconds": int(session.total_time_seconds or 1200),

        "consent_given": bool(session.consent_given),

        "warning_count": int(session.warning_count or 0),

        "paused": pause_seconds_left > 0,

        "pause_seconds_left": pause_seconds_left,


    }


@router.post("/interview/tts")
async def synthesize_question_speech(
    request: Request,
):
    """Synthesize speech for interview question using Amazon Polly via Lambda."""
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    text = body.get("text", "")
    voice = body.get("voice", "kajal")

    if not text:
        raise HTTPException(status_code=400, detail="Text is required")

    if not config.LAMBDA_S3_URL:
        raise HTTPException(status_code=500, detail="TTS Lambda not configured")

    try:
        resp = requests.get(
            config.LAMBDA_S3_URL,
            params={"text": text, "voice": voice},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()

        if "error" in data:
            raise Exception(data["error"])

        logger.info("TTS synthesis success voice=%s text_len=%d", voice, len(text))
        return {"ok": True, **data}

    except Exception as exc:
        logger.error("TTS synthesis failed: %s", exc)
        # Return degraded response so frontend can fall back to browser TTS
        return {
            "ok": True,
            "audio_url": None,
            "text": text,
            "voice": voice,
            "degraded": True,
            "error": str(exc),
        }

    except Exception as exc:
        logger.error("TTS synthesis failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"TTS synthesis failed: {str(exc)}")




@router.get("/interview/{result_id}/access")

def interview_access(

    result_id: int,

    current_user: SessionUser = Depends(require_role("candidate")),

    db: Session = Depends(get_db),

) -> dict[str, Any]:

    candidate = db.query(Candidate).filter(Candidate.id == current_user.user_id).first()

    if not candidate:

        raise HTTPException(status_code=404, detail="Candidate not found")



    result = _resolve_candidate_result(db, candidate.id, result_id)

    access = interview_access_state(result)

    schedule = interview_schedule_state(result)

    latest_session = _latest_interview_session(db, result)

    job = db.query(JobDescription).filter(JobDescription.id == result.job_id).first()

    question_count = int(job.question_count if job and job.question_count is not None else 8)

    questions = _ensure_question_bank(

        db,

        result=result,

        candidate=candidate,

        job=job,

        question_count=question_count,

    )



    # ── Resume + JD local evaluation (zero extra API calls) ──────────────────

    resume_jd_eval: dict[str, Any] = {}

    try:

        from ai_engine.phase1.scoring import compute_resume_scorecard

        from ai_engine.phase1.matching import extract_text_from_file



        resume_text = (candidate.resume_text or "").strip()

        if not resume_text and candidate.resume_path:

            resume_text = extract_text_from_file(candidate.resume_path) or ""

            if resume_text.strip():

                candidate.resume_text = resume_text.strip()

                db.add(candidate)

                db.commit()

                logger.info(

                    "resume_text_backfilled_access candidate_id=%s file_path=%s text_len=%d",

                    candidate.id,

                    candidate.resume_path,

                    len(resume_text),

                )

        jd_text = str(job.jd_text or "") if job else ""

        jd_skill_scores = dict(job.skill_scores or {}) if job else {}

        education_req = str(getattr(job, "education_requirement", None) or "")

        experience_req = int(getattr(job, "experience_requirement", None) or 0)



        if resume_text.strip() and (jd_text.strip() or jd_skill_scores):

            scorecard = compute_resume_scorecard(

                resume_text=resume_text,

                jd_text=jd_text,

                jd_skill_scores=jd_skill_scores,

                education_requirement=education_req or None,

                experience_requirement=experience_req,

                semantic_similarity=float(result.score or 0) / 100.0 if result.score else None,

            )

            resume_jd_eval = {

                "resume_match_score": round(float(scorecard.get("final_resume_score") or 0), 1),

                "skill_match_percent": round(float(scorecard.get("matched_percentage") or 0), 1),

                "matched_skills": list(scorecard.get("matched_skills") or [])[:8],

                "missing_skills": list(scorecard.get("missing_skills") or [])[:5],

                "screening_band": str(scorecard.get("screening_band") or ""),

                "experience_years_detected": int(scorecard.get("detected_experience_years") or 0),

                "education_detected": str(scorecard.get("detected_education_level") or ""),

                "reasons": list(scorecard.get("reasons") or [])[:3],

                "readiness": (

                    "Strong Match" if float(scorecard.get("final_resume_score") or 0) >= 70

                    else "Good Match" if float(scorecard.get("final_resume_score") or 0) >= 50

                    else "Partial Match"

                ),

            }

    except Exception as exc:

        logger.warning("resume_jd_eval_failed result_id=%s error=%s", result_id, exc)



    return {

        "ok": True,

        "result_id": result.id,

        "shortlisted": bool(result.shortlisted),

        "interview_date": result.interview_date,

        "interview_ready": bool(access["interview_ready"]),

        "interview_locked_reason": access["interview_locked_reason"],

        "interview_datetime_utc": utc_isoformat(schedule["scheduled_utc"]),

        "interview_window_open_utc": utc_isoformat(schedule["window_open_utc"]),

        "interview_window_close_utc": utc_isoformat(schedule["window_close_utc"]),

        "can_start_now": bool(schedule["can_start_now"]),

        "latest_session_status": str(getattr(latest_session, "status", "") or "").strip().lower() or None,

        "question_count": len(questions),

        "resume_jd_evaluation": resume_jd_eval,

    }


@router.post("/interview/start")
def start_interview(
    payload: InterviewStartBody,
    current_user: SessionUser = Depends(require_role("candidate")),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Start or resume an interview session."""
    result_id = payload.result_id
    consent_given = payload.consent_given
    interview_token = payload.interview_token

    candidate = db.query(Candidate).filter(Candidate.id == current_user.user_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    if interview_token:
        result = _resolve_result_by_token(db, candidate.id, interview_token)
    else:
        result = _resolve_candidate_result(db, candidate.id, result_id)

    _ensure_interview_ready(result)

    active_session = _latest_interview_session(db, result)
    if active_session and active_session.status == "in_progress":
        session = active_session
    else:
        job = db.query(JobDescription).filter(JobDescription.id == result.job_id).first()
        question_count = int(job.question_count or 8) if job else 8
        duration_minutes = int(job.total_duration_minutes or 30) if job else 30
        per_question_seconds = (duration_minutes * 60) // question_count
        total_time_seconds = duration_minutes * 60

        session = InterviewSession(
            candidate_id=candidate.id,
            result_id=result.id,
            status="in_progress",
            per_question_seconds=per_question_seconds,
            total_time_seconds=total_time_seconds,
            remaining_time_seconds=total_time_seconds,
            max_questions=question_count,
            consent_given=consent_given,
        )
        db.add(session)
        db.flush()

    if consent_given and not session.consent_given:
        session.consent_given = True
        db.flush()

    _ensure_session_questions(db, session=session, result=result)

    if not result.interview_questions:
        from services.question_generation import build_question_bundle
        job = db.query(JobDescription).filter(JobDescription.id == result.job_id).first()
        candidate = db.query(Candidate).filter(Candidate.id == result.candidate_id).first()
        question_count = int(job.question_count or 8) if job else 8
        bundle = build_question_bundle(
            resume_text=candidate.resume_text or "",
            jd_text=job.jd_text or "",
            jd_dict=job.jd_dict_json or {},
            job_title=job.title or "",
            project_ratio=float(job.project_question_ratio or 0.8),
            question_count=question_count,
        )
        result.interview_questions = bundle.get("questions") or []
        db.commit()
        _ensure_session_questions(db, session=session, result=result)

    next_question = _create_next_question(db, session, result, "")
    answered_count = db.query(InterviewAnswer).filter(
        InterviewAnswer.session_id == session.id,
    ).count()

    return _compose_start_response(session, next_question, answered_count)


@router.post("/interview/answer")
def submit_interview_answer(
    payload: InterviewAnswerBody,
    current_user: SessionUser = Depends(require_role("candidate")),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Submit an answer for the current question."""
    session = db.query(InterviewSession).filter(
        InterviewSession.id == payload.session_id,
        InterviewSession.candidate_id == current_user.user_id,
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    question = db.query(InterviewQuestion).filter(
        InterviewQuestion.id == payload.question_id,
        InterviewQuestion.session_id == session.id,
    ).first()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    existing_answer = db.query(InterviewAnswer).filter(
        InterviewAnswer.question_id == question.id,
        InterviewAnswer.session_id == session.id,
    ).first()

    if existing_answer:
        existing_answer.answer_text = payload.answer_text
        existing_answer.time_taken_sec = payload.time_taken_sec
        existing_answer.skipped = payload.skipped
    else:
        answer = InterviewAnswer(
            session_id=session.id,
            question_id=question.id,
            answer_text=payload.answer_text,
            time_taken_sec=payload.time_taken_sec,
            skipped=payload.skipped,
        )
        db.add(answer)

    question.answer_text = payload.answer_text
    question.skipped = payload.skipped

    if not payload.skipped and payload.answer_text:
        session.remaining_time_seconds = max(0, session.remaining_time_seconds - payload.time_taken_sec)

    question.time_taken_seconds = payload.time_taken_sec or 0
    db.add(question)
    db.commit()

    result = db.query(Result).filter(Result.id == session.result_id).first()
    next_question = _create_next_question(db, session, result, payload.answer_text or "")
    answered_count = db.query(InterviewAnswer).filter(
        InterviewAnswer.session_id == session.id,
    ).count()

    response = _compose_start_response(session, next_question, answered_count)
    response["next_question"] = _serialize_question(next_question)
    return response


@router.post("/interview/{session_id}/recording")
def upload_interview_recording(
    session_id: int,
    recording: UploadFile = File(...),
    duration_seconds: int | None = Form(None),
    current_user: SessionUser = Depends(require_role("candidate")),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Persist the candidate's full interview recording for HR review."""
    session = db.query(InterviewSession).filter(
        InterviewSession.id == session_id,
        InterviewSession.candidate_id == current_user.user_id,
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    raw = recording.file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Recording payload is empty")

    max_size_bytes = INTERVIEW_RECORDING_MAX_MB * 1_000_000
    if len(raw) > max_size_bytes:
        raise HTTPException(status_code=400, detail=f"Recording file exceeds {INTERVIEW_RECORDING_MAX_MB}MB limit")

    content_type = (recording.content_type or "").lower()
    allowed_types = {
        "video/webm": "webm",
        "video/mp4": "mp4",
        "video/ogg": "ogv",
        "audio/webm": "webm",
        "audio/mp4": "mp4",
    }
    ext = allowed_types.get(content_type)
    if not ext:
        filename = (recording.filename or "").lower()
        ext = "mp4" if filename.endswith(".mp4") else "webm"

    filename = f"session_{session.id}_{uuid.uuid4().hex}.{ext}"
    file_path = RECORDING_UPLOAD_ROOT / filename
    with file_path.open("wb") as handle:
        handle.write(raw)

    previous_path = session.recording_path
    relative_path = f"interview_recordings/{filename}"
    session.recording_path = relative_path
    session.recording_mime_type = recording.content_type or f"video/{ext}"
    session.recording_size_bytes = len(raw)
    session.recording_uploaded_at = datetime.utcnow()

    meta = session.evaluation_summary_json if isinstance(session.evaluation_summary_json, dict) else {}
    if duration_seconds is not None:
        meta = {**meta, "recording_duration_seconds": int(duration_seconds)}
        session.evaluation_summary_json = meta

    db.commit()

    if previous_path and previous_path != relative_path and not previous_path.startswith(("http://", "https://")):
        previous_file = config.UPLOAD_DIR / previous_path
        try:
            if previous_file.is_file() and previous_file.resolve().is_relative_to(config.UPLOAD_DIR.resolve()):
                previous_file.unlink()
        except Exception:
            logger.warning("Unable to delete previous interview recording path=%s", previous_path)

    return {
        "ok": True,
        "session_id": session.id,
        "recording_url": f"/uploads/{relative_path}",
        "recording_size_bytes": len(raw),
        "recording_uploaded_at": utc_isoformat(session.recording_uploaded_at),
    }


@router.get("/interview/{result_id}/recheck")
def interview_recheck(
    result_id: int,
    current_user: SessionUser = Depends(require_role("candidate")),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    candidate = db.query(Candidate).filter(Candidate.id == current_user.user_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    result = _resolve_candidate_result(db, candidate.id, result_id)
    access = interview_access_state(result)
    schedule = interview_schedule_state(result)
    return {
        "ok": True,
        "access": access,
        "schedule": schedule,
    }
@router.post("/interview/transcribe")

def interview_transcribe(

    audio: UploadFile = File(...),

    language: str = Form("en"),

    context_hint: str = Form(""),

    current_user: SessionUser = Depends(require_role("candidate")),

) -> dict[str, Any]:

    _ = current_user

    raw = audio.file.read()

    if not raw:
        raise HTTPException(status_code=400, detail="Audio payload is empty")

    audio_size = len(raw)
    max_size_bytes = config.MAX_UPLOAD_SIZE_MB * 1_000_000
    if audio_size > max_size_bytes:
        raise HTTPException(status_code=400, detail=f"Audio file exceeds {config.MAX_UPLOAD_SIZE_MB}MB limit")

    if audio_size < 900:
        return {
            "ok": True,
            "text": "",
            "confidence": 0.0,
            "language": language,
            "duplicate_audio": False,
        }

    audio_hash = hashlib.sha256(raw).hexdigest()
    cache_key = f"{current_user.user_id}:{language}:{audio_hash}"
    cached = _transcribe_cache_get(cache_key)
    if cached is not None:
        return {"ok": True, **cached, "duplicate_audio": True}

    try:

        transcript = transcribe_audio_bytes(

            raw,

            language=language,

            filename=audio.filename,

            context_hint=context_hint,

        )

    except Exception as exc:

        logger.warning(

            "STT transcription unavailable — returning empty transcript. Error: %s",

            exc,

        )

        return {

            "ok": True,

            "text": "",

            "confidence": 0.0,

            "low_confidence": True,

            "language": language,

            "degraded": True,

            "error": str(exc),

        }

    _transcribe_cache_set(cache_key, transcript)
    return {"ok": True, **transcript}





@router.get("/interview/session/{session_id}/summary")

def interview_session_summary(

    session_id: int,

    current_user: SessionUser = Depends(require_role("candidate")),

    db: Session = Depends(get_db),

) -> dict[str, Any]:

    session = _get_candidate_session_or_403(db, session_id, current_user)

    answers = db.query(InterviewAnswer).filter(InterviewAnswer.session_id == session.id).all()

    answered_count = len([row for row in answers if (row.answer_text or "").strip() or row.skipped])

    strengths = []

    weaknesses = []

    for row in answers:

        evaluation = row.evaluation_json or {}

        strengths.extend(evaluation.get("strengths") or [])

        weaknesses.extend(evaluation.get("weaknesses") or [])

    summary = session.evaluation_summary_json or {}

    return {

        "ok": True,

        "session_id": session.id,

        "status": session.status,

        "answered_count": answered_count,

        "total_questions": int(session.max_questions or answered_count),

        "summary": summary,

        "strengths": list(dict.fromkeys(strengths))[:5],

        "weaknesses": list(dict.fromkeys(weaknesses))[:5],

    }





@router.post("/interview/{token}/event")
def interview_event(
    token: str,
    payload: InterviewEventBody,
    current_user: SessionUser = Depends(require_role("candidate")),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    result = _resolve_result_by_token_or_id(db, current_user.user_id, token)

    latest_session = (

        db.query(InterviewSession)

        .filter(

            InterviewSession.candidate_id == current_user.user_id,

            InterviewSession.result_id == result.id,

        )

        .order_by(InterviewSession.id.desc())

        .first()

    )



    normalized_event_type = (payload.event_type or "").strip().lower()

    if not normalized_event_type:

        raise HTTPException(status_code=400, detail="event_type is required")



    event_payload: dict[str, Any] = {
        "event_type": normalized_event_type,
        "detail": (payload.detail or "").strip() or None,
        "timestamp": (payload.timestamp or "").strip() or datetime.utcnow().isoformat(),
        "meta": payload.meta if isinstance(payload.meta, dict) else {},
        "session_id": latest_session.id if latest_session else None,
    }

    existing_events: list[dict[str, Any]]
    if isinstance(result.events_json, list):
        existing_events = [item for item in result.events_json if isinstance(item, dict)]
    elif isinstance(result.events_json, dict):
        existing_events = [result.events_json]
    else:
        existing_events = []

    existing_events.append(event_payload)
    if len(existing_events) > 500:
        existing_events = existing_events[-500:]

    result.events_json = existing_events

    if normalized_event_type in SUSPICIOUS_TYPES and latest_session:
        proctor_event = ProctorEvent(
            session_id=latest_session.id,
            event_type=normalized_event_type,
            score=1.0,
            meta_json=event_payload,
        )
        db.add(proctor_event)

    db.commit()
    return {"ok": True, "event_count": len(existing_events), "event": event_payload}





@router.post("/interview/{session_id}/event")

def interview_event_by_session(

    session_id: int,

    payload: InterviewEventBody,

    current_user: SessionUser = Depends(require_role("candidate")),

    db: Session = Depends(get_db),

) -> dict[str, Any]:

    """Frontend proctoring hook uses session-id-based event routing."""

    session = _get_candidate_session_or_403(db, session_id, current_user)

    result = db.query(Result).filter(Result.id == session.result_id).first()

    if not result:

        raise HTTPException(status_code=404, detail="Interview result not found")



    normalized_event_type = (payload.event_type or "").strip().lower()

    if not normalized_event_type:

        raise HTTPException(status_code=400, detail="event_type is required")



    event_payload: dict[str, Any] = {

        "event_type": normalized_event_type,

        "detail": (payload.detail or "").strip() or None,

        "timestamp": (payload.timestamp or "").strip() or datetime.utcnow().isoformat(),

        "meta": payload.meta if isinstance(payload.meta, dict) else {},

        "session_id": session.id,

    }



    existing_events: list[dict[str, Any]]

    if isinstance(result.events_json, list):

        existing_events = [item for item in result.events_json if isinstance(item, dict)]

    elif isinstance(result.events_json, dict):

        existing_events = [result.events_json]

    else:

        existing_events = []



    existing_events.append(event_payload)
    if len(existing_events) > 500:
        existing_events = existing_events[-500:]
    result.events_json = existing_events

    if normalized_event_type in SUSPICIOUS_TYPES:
        proctor_event = ProctorEvent(
            session_id=session.id,
            event_type=normalized_event_type,
            score=1.0,
            meta_json=event_payload,
        )
        db.add(proctor_event)

    db.commit()
    return {"ok": True, "event_count": len(existing_events), "event": event_payload}





_proctor_deps = [dep for dep in [limiter("30/minute")] if dep is not None]

@router.post("/proctor/frame", dependencies=_proctor_deps)
def upload_proctor_frame(
    background_tasks: BackgroundTasks,
    request: Request,
    file: UploadFile = File(...),
    session_id: int = Form(...),
    event_type: str = Form("scan"),
    current_user: SessionUser = Depends(require_role("candidate")),
    db: Session = Depends(get_db),
) -> dict[str, Any]:

    session = _get_candidate_session_or_403(db, session_id, current_user)

    raw = file.file.read()

    image_size = len(raw)
    max_size_bytes = config.MAX_UPLOAD_SIZE_MB * 1_000_000
    if image_size > max_size_bytes:
        raise HTTPException(status_code=400, detail=f"Image file exceeds {config.MAX_UPLOAD_SIZE_MB}MB limit")

    image_quality_score = None

    frame = analyze_frame(session.id, raw)

    if not frame["ok"]:

        raise HTTPException(status_code=400, detail=str(frame["error"]))



    now = datetime.utcnow()

    if session.paused_until and (session.paused_until <= now or not PAUSE_ON_WARNINGS_ENABLED):

        session.paused_until = None



    faces_count = int(frame["faces_count"])

    motion_score = float(frame["motion_score"])

    current_signature = frame["face_signature"]

    opencv_enabled = bool(frame.get("opencv_enabled"))

    shoulder_model_enabled = bool(frame.get("shoulder_model_enabled"))

    left_shoulder_visibility = _float_or_none(frame.get("left_shoulder_visibility"))

    right_shoulder_visibility = _float_or_none(frame.get("right_shoulder_visibility"))

    shoulder_score_raw = _float_or_none(frame.get("shoulder_score"))

    gaze_direction = frame.get("gaze_direction")
    mediapipe_enabled = bool(frame.get("mediapipe_enabled"))

    upper_bodies_count = int(frame.get("upper_bodies_count") or 0)

    baseline_signature = None

    if session.baseline_face_signature:

        try:

            baseline_signature = [float(item) for item in json.loads(session.baseline_face_signature)]

        except Exception:

            baseline_signature = None



    face_similarity = None

    if baseline_signature and current_signature:

        face_similarity = compare_signatures(baseline_signature, current_signature)



    baseline_ready = bool(session.baseline_face_signature)

    shoulder_score = shoulder_score_raw if shoulder_score_raw is not None else (1.0 if not shoulder_model_enabled else 0.0)

    face_score = _compute_face_score(faces_count, face_similarity, baseline_ready=baseline_ready)

    compliance_score = _clamp((0.6 * face_score) + (0.4 * shoulder_score))

    frame_reasons = _frame_reasons(

        faces_count=faces_count,

        baseline_ready=baseline_ready,

        face_similarity=face_similarity,

        shoulder_model_enabled=shoulder_model_enabled,

        shoulder_score=shoulder_score_raw,

    )

    frame_ready = len(frame_reasons) == 0

    frame_status = _frame_status_from_reasons(frame_reasons, faces_count)



    requested_event = (event_type or "").strip().lower()

    if requested_event not in {"scan", "baseline", "frame_check"}:

        requested_event = "scan"



    resolved_event_type = "periodic"

    action = "ok"

    warning_triggered = False

    pause_enforced = False

    suspicious = False

    pause_seconds_left = _pause_seconds_left(session, now)

    violation_for_warning = False



    if requested_event == "baseline":

        if not opencv_enabled:

            resolved_event_type = "baseline"

        elif faces_count == 0:

            resolved_event_type = "baseline_no_face"

        elif faces_count > 1:

            resolved_event_type = "baseline_multi_face"

        elif shoulder_model_enabled and shoulder_score < SHOULDER_MIN_THRESHOLD:

            resolved_event_type = "baseline_no_shoulder"

        elif current_signature:

            if not session.baseline_face_signature:

                session.baseline_face_signature = json.dumps(current_signature)

                session.baseline_face_captured_at = now

                baseline_ready = True

            resolved_event_type = "baseline"

        else:

            resolved_event_type = "baseline_no_face"

    elif requested_event == "frame_check":

        resolved_event_type = "frame_check_ok" if frame_ready else "frame_check_adjust"

        action = "adjust" if not frame_ready else "ok"

    else:

        if pause_seconds_left > 0:

            resolved_event_type = "pause_active"

            action = "paused"

        else:

            if faces_count == 0:

                resolved_event_type = "no_face"

            elif faces_count > 1:

                resolved_event_type = "multi_face"

            elif (

                baseline_signature

                and current_signature

                and face_similarity is not None

                and face_similarity < FACE_MISMATCH_THRESHOLD

            ):

                resolved_event_type = "face_mismatch"

            elif shoulder_model_enabled and shoulder_score < SHOULDER_MIN_THRESHOLD:

                resolved_event_type = "shoulder_missing"

            elif motion_score > HIGH_MOTION_THRESHOLD:

                resolved_event_type = "high_motion"

            elif gaze_direction and gaze_direction != "center":

                resolved_event_type = "gaze_away"

            else:

                resolved_event_type = "periodic"



            violation_for_warning = resolved_event_type in {

                "no_face",

                "multi_face",

                "face_mismatch",

                "shoulder_missing",

                "gaze_away",

            }

            if violation_for_warning:

                session.consecutive_violation_frames = int(session.consecutive_violation_frames or 0) + 1

                if session.consecutive_violation_frames >= VIOLATION_FRAMES_PER_WARNING:

                    session.warning_count = int(session.warning_count or 0) + 1

                    session.consecutive_violation_frames = 0

                    warning_triggered = True

                    resolved_event_type = "warning_issued"

                    action = "warning"

                    if PAUSE_ON_WARNINGS_ENABLED and int(session.warning_count or 0) >= MAX_WARNINGS_BEFORE_PAUSE:

                        session.paused_until = now + timedelta(seconds=PAUSE_SECONDS_ON_THIRD_WARNING)

                        pause_seconds_left = PAUSE_SECONDS_ON_THIRD_WARNING

                        pause_enforced = True

                        resolved_event_type = "pause_enforced"

                        action = "paused"

            else:

                session.consecutive_violation_frames = 0

                if resolved_event_type == "high_motion":

                    action = "observe"



    pause_seconds_left = _pause_seconds_left(session, now)

    paused = pause_seconds_left > 0

    suspicious = resolved_event_type in SUSPICIOUS_TYPES



    should_store = False

    if requested_event == "baseline":

        should_store = True

    elif requested_event == "scan":

        should_store = suspicious or warning_triggered or pause_enforced

        if resolved_event_type in {"periodic", "pause_active"}:

            should_store = should_store_periodic(session.id, PERIODIC_SAVE_SECONDS)



    payload_out = {

        "ok": True,

        "stored": False,

        "event_type": resolved_event_type,

        "requested_event_type": requested_event,

        "suspicious": suspicious,

        "action": action,

        "motion_score": motion_score,

        "faces_count": faces_count,

        "face_similarity": face_similarity,

        "face_score": round(face_score, 4),

        "left_shoulder_visibility": left_shoulder_visibility,

        "right_shoulder_visibility": right_shoulder_visibility,

        "shoulder_score": round(shoulder_score, 4),

        "shoulder_model_enabled": shoulder_model_enabled,

        "upper_bodies_count": upper_bodies_count,

        "compliance_score": round(compliance_score, 4),

        "frame_ready": frame_ready,

        "frame_status": frame_status,

        "frame_reasons": frame_reasons,

        "warning_count": int(session.warning_count or 0),

        "consecutive_violation_frames": int(session.consecutive_violation_frames or 0),

        "warning_triggered": warning_triggered,

        "paused": paused,

        "pause_seconds_left": pause_seconds_left,

        "baseline_ready": baseline_ready,

        "opencv_enabled": bool(frame.get("opencv_enabled")),

        "mediapipe_enabled": mediapipe_enabled,

        "gaze_direction": gaze_direction,

    }



    if not should_store:

        db.commit()

        return payload_out



    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%S%f")
    # Immediate placeholders; the client can retrieve the image later via event metadata.
    image_url = ""
    relative_path = ""

    score = float(motion_score)

    if resolved_event_type in {"no_face", "multi_face", "face_mismatch", "shoulder_missing"}:

        score += 1.0

    elif resolved_event_type == "high_motion":

        score += 0.7

    elif resolved_event_type in {"warning_issued", "pause_enforced"}:

        score += 1.2

    elif resolved_event_type in {"baseline", "baseline_no_face", "baseline_multi_face", "baseline_no_shoulder"}:

        score = 0.0 if resolved_event_type == "baseline" else 1.0

    if not frame_ready:

        score += 0.25



    event = ProctorEvent(

        session_id=session.id,

        event_type=resolved_event_type,

        score=round(float(score), 4),

        meta_json={

            "faces_count": faces_count,

            "motion_score": round(motion_score, 4),

            "face_similarity": round(face_similarity, 4) if face_similarity is not None else None,

            "face_score": round(face_score, 4),

            "left_shoulder_visibility": left_shoulder_visibility,

            "right_shoulder_visibility": right_shoulder_visibility,

            "shoulder_score": round(shoulder_score, 4),

            "shoulder_model_enabled": shoulder_model_enabled,

            "compliance_score": round(compliance_score, 4),

            "frame_ready": frame_ready,

            "frame_status": frame_status,

            "frame_reasons": frame_reasons,

            "baseline_ready": bool(session.baseline_face_signature),

            "suspicious": suspicious,

            "warning_count": int(session.warning_count or 0),

            "warning_triggered": warning_triggered,

            "paused": paused,

            "pause_seconds_left": pause_seconds_left,

            "opencv_enabled": bool(frame.get("opencv_enabled")),

        "mediapipe_enabled": mediapipe_enabled,

        "gaze_direction": gaze_direction,

            "requested_event_type": requested_event,

            "upper_bodies_count": upper_bodies_count,

        },

        image_path=relative_path,

    )

    db.add(event)

    db.commit()

    db.refresh(event)


    # Schedule asynchronous upload after event is created; pass event_id so S3 URL can be saved.
    from services.background_tasks import schedule_proctor_image_upload
    request_id = request.headers.get("X-Request-ID", "")
    schedule_proctor_image_upload(
        background_tasks,
        session.id,
        raw,
        timestamp,
        event_id=event.id,
        request_id=request_id,
    )



    payload_out["stored"] = True
    payload_out["event_id"] = event.id
    payload_out["image_url"] = image_url

    return payload_out





@router.get("/hr/proctoring/{session_id}")

def hr_proctoring_timeline(

    session_id: int,

    request: Request,

    current_user: SessionUser = Depends(require_role("hr")),

    db: Session = Depends(get_db),

) -> dict[str, Any]:

    session = (

        db.query(InterviewSession)

        .join(Result, InterviewSession.result_id == Result.id)

        .join(JobDescription, Result.job_id == JobDescription.id)

        .filter(

            InterviewSession.id == session_id,

            JobDescription.company_id == current_user.user_id,

        )

        .first()

    )

    if not session:

        raise HTTPException(status_code=404, detail="Interview session not found for this HR account")



    candidate = db.query(Candidate).filter(Candidate.id == session.candidate_id).first()

    events = (

        db.query(ProctorEvent)

        .filter(ProctorEvent.session_id == session.id)

        .order_by(ProctorEvent.created_at.asc())

        .all()

    )

    base_url = str(request.base_url).rstrip("/")



    return {

        "ok": True,

        "session": {

            "id": session.id,

            "candidate_id": session.candidate_id,

            "candidate_name": candidate.name if candidate else None,

            "status": session.status,

            "started_at": session.started_at,

            "ended_at": session.ended_at,

"remaining_time_seconds": session.remaining_time_seconds,
            "max_questions": session.max_questions,

            "baseline_captured": bool(session.baseline_face_signature),

            "consent_given": bool(session.consent_given),

            "warning_count": int(session.warning_count or 0),

            "paused": _pause_seconds_left(session) > 0,

            "pause_seconds_left": _pause_seconds_left(session),

            "llm_eval_status": session.llm_eval_status or "pending",

        },

        "timeline": [

            {

                "id": event.id,

                "created_at": event.created_at,

                "event_type": event.event_type,

                "score": float(event.score),

                "meta_json": event.meta_json or {},

                "suspicious": event.event_type in SUSPICIOUS_TYPES,

                "image_url": event.image_path if event.image_path and event.image_path.startswith("http") else (f"{base_url}/uploads/{event.image_path}" if event.image_path else None),

            }

            for event in events

        ],

    }

#  Feature: Candidate Experience Feedback ----------------------------------
from pydantic import BaseModel as _PydanticBase

class FeedbackBody(_PydanticBase):
    rating: int
    comment: str = ""

@router.post("/interview/{session_id}/feedback")
def submit_interview_feedback(
    session_id: int,
    payload: FeedbackBody,
    current_user: SessionUser = Depends(require_role("candidate")),
    db: Session = Depends(get_db),
):
    """Candidate submits experience rating at interview end."""
    from models import InterviewFeedback

    session = db.query(InterviewSession).filter(
        InterviewSession.id == session_id,
        InterviewSession.candidate_id == current_user.user_id,
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    rating = max(1, min(5, int(payload.rating)))
    feedback = InterviewFeedback(
        session_id=session_id,
        rating=rating,
        comment=(payload.comment or "").strip()[:1000],
    )
    db.add(feedback)
    db.commit()
    return {"ok": True, "rating": rating}


# ── LEGACY REDIRECT ──────────────────────────────────────────────────────────────────
# MUST be at the END - catches any remaining /interview/{result_id} requests and redirects to SPA.
# All specific /interview/{result_id}/... routes must be registered BEFORE this.

@router.get("/interview/{result_id}")
def legacy_interview_entry(result_id: int, token: str | None = None) -> RedirectResponse:
    """Redirect legacy backend interview URLs to the SPA pre-check route."""
    target = interview_entry_url(result_id) or "/"
    if token:
        target = f"{target}?token={token}"
    return RedirectResponse(url=target, status_code=307)
