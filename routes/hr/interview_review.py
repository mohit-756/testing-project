"""
routes/hr/interview_review.py — HR dashboard APIs for interviews and proctoring.

FIXES applied:
  1. finalize_interview now writes to dedicated Result columns
     (hr_decision, hr_final_score, hr_behavioral_score, hr_communication_score,
      hr_notes, hr_red_flags) instead of merging into the explanation JSON blob.
     This eliminates silent data-loss when other code paths also write explanation.
  2. interview_detail reads HR review data from the new columns with a fallback
     to the old explanation keys for backward compatibility with existing rows.
  3. NEW endpoint: POST /hr/interviews/{id}/re-evaluate — lets HR manually
     re-trigger LLM scoring when it shows "Pending" after a Groq outage.
"""
from __future__ import annotations

from typing import Any

import json
import logging
from collections import defaultdict

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import FileResponse, RedirectResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import case, func
from sqlalchemy.orm import Session, joinedload

from ai_engine.phase1.scoring import compute_answer_scorecard
from database import get_db
from core.config import config
from models import (
    Candidate, InterviewAnswer, InterviewQuestion,
    InterviewSession, JobDescription, ProctorEvent, Result,
)
from routes.dependencies import require_role, SessionUser
from services.pdf_report import generate_interview_pdf
from services.pipeline import record_stage_change, stage_payload
from services.scoring import build_application_score, summarize_interview

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/hr", tags=["hr"])


# ── helpers ──────────────────────────────────────────────────────────────────

def _json_dict(value: Any) -> dict:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            return {}
    return {}


def _json_list(value: Any) -> list:
    if isinstance(value, list):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return parsed
        except Exception:
            return []
    return []


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except Exception:
        return None


def _safe_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except Exception:
        return None


def _normalize_answer_evaluation(value: Any) -> dict:
    raw = _json_dict(value)
    breakdown = _json_dict(raw.get("score_breakdown"))
    legacy_breakdown = _json_dict(raw.get("dimension_breakdown"))

    relevance = _safe_float(raw.get("relevance"))
    if relevance is None:
        relevance = _safe_float(legacy_breakdown.get("relevance"))
    if relevance is None:
        relevance = _safe_float(breakdown.get("relevance"))

    clarity = _safe_float(raw.get("clarity"))
    if clarity is None:
        clarity = _safe_float(legacy_breakdown.get("clarity"))
    if clarity is None:
        clarity = _safe_float(breakdown.get("clarity"))

    completeness = _safe_float(raw.get("completeness"))
    if completeness is None:
        completeness = _safe_float(legacy_breakdown.get("completeness"))
    if completeness is None:
        completeness = _safe_float(breakdown.get("completeness"))

    confidence = _safe_float(raw.get("confidence_communication"))
    if confidence is None:
        confidence = _safe_float(legacy_breakdown.get("confidence"))
    if confidence is None:
        confidence = _safe_float(breakdown.get("time_fit"))

    technical = _safe_float(raw.get("technical_correctness"))
    if technical is None:
        technical = _safe_float(legacy_breakdown.get("correctness"))
    if technical is None:
        technical = relevance

    overall = _safe_float(raw.get("overall_answer_score"))
    if overall is None:
        overall = _safe_float(raw.get("score"))
    if overall is None:
        overall = _safe_float(breakdown.get("overall_score"))

    normalized_breakdown = breakdown or {
        "relevance": relevance if relevance is not None else 0.0,
        "completeness": completeness if completeness is not None else 0.0,
        "clarity": clarity if clarity is not None else 0.0,
        "time_fit": confidence if confidence is not None else 0.0,
        "overall_score": overall if overall is not None else 0.0,
        "word_count": _safe_int(raw.get("word_count")) or 0,
    }

    return {
        **raw,
        "relevance": relevance,
        "technical_correctness": technical,
        "clarity": clarity,
        "confidence_communication": confidence,
        "completeness": completeness,
        "overall_answer_score": overall,
        "strengths": raw.get("strengths") if isinstance(raw.get("strengths"), list) else [],
        "weaknesses": raw.get("weaknesses") if isinstance(raw.get("weaknesses"), list) else [],
        "improvement_suggestion": raw.get("improvement_suggestion") or raw.get("feedback") or "No answer evaluation available yet.",
        "score_breakdown": normalized_breakdown,
    }


def _hr_review_from_result(result: Result) -> dict:
    """Read HR review data from the dedicated columns (new) or explanation JSON (legacy)."""
    expl = _json_dict(result.explanation)
    return {
        # New dedicated columns take precedence; fall back to legacy JSON keys.
        "final_score":         result.hr_final_score         if result.hr_final_score         is not None else expl.get("hr_final_score"),
        "behavioral_score":    result.hr_behavioral_score    if result.hr_behavioral_score    is not None else expl.get("hr_behavioral_score"),
        "communication_score": result.hr_communication_score if result.hr_communication_score is not None else expl.get("hr_communication_score"),
        "red_flags":           result.hr_red_flags           if result.hr_red_flags           is not None else expl.get("hr_red_flags"),
        "notes":               result.hr_notes               if result.hr_notes               is not None else expl.get("hr_final_notes"),
    }


# ── list interviews ───────────────────────────────────────────────────────────

def _recording_url(session: InterviewSession) -> str | None:
    path = getattr(session, "recording_path", None)
    if not path:
        return None
    value = str(path)
    if value.startswith(("http://", "https://")):
        return value
    return f"/api/hr/interviews/{session.id}/recording"


def _recording_file_path(session: InterviewSession):
    path = getattr(session, "recording_path", None)
    if not path:
        return None
    value = str(path)
    if value.startswith(("http://", "https://")):
        return value
    upload_root = config.UPLOAD_DIR.resolve()
    candidate = (upload_root / value.lstrip("/")).resolve()
    try:
        if candidate.is_file() and candidate.is_relative_to(upload_root):
            return candidate
    except Exception:
        return None
    return None


@router.get("/interviews")
def list_interviews(
    current_user: SessionUser = Depends(require_role("hr")),
    db: Session = Depends(get_db),
):
    sessions = (
        db.query(InterviewSession)
        .join(Result, InterviewSession.result_id == Result.id)
        .join(JobDescription, Result.job_id == JobDescription.id)
        .options(joinedload(InterviewSession.result), joinedload(InterviewSession.candidate))
.all()
    )
    count_map = {
        row.session_id: {
            "events_count": int(row.events_count or 0),
            "suspicious_count": int(row.suspicious_count or 0),
        }
        for row in counts
    }

    payload = []
    for session in sessions:
        result = session.result
        candidate = session.candidate
        job = db.query(JobDescription).filter(JobDescription.id == result.job_id).first()
        payload.append(
            {
                "interview_id": session.id,
                "application_id": result.application_id,
                "candidate": {"id": candidate.id, "name": candidate.name, "email": candidate.email},
                "job": {"id": job.id if job else None, "title": job.jd_title if job else None},
                "status": "completed" if session.llm_eval_status == "completed" and session.status == "in_progress" else session.status,
                "started_at": session.started_at,
                "ended_at": session.ended_at,
                "events_count": count_map.get(session.id, {}).get("events_count", 0),
                "suspicious_events_count": count_map.get(session.id, {}).get("suspicious_count", 0),
                # FIX: expose LLM eval status so the frontend can show "Pending / Scored"
                "llm_eval_status": session.llm_eval_status or "pending",
                "recording_available": bool(session.recording_path),
            }
        )
    return {"ok": True, "interviews": payload}


# ── interview detail ──────────────────────────────────────────────────────────

@router.get("/interviews/{interview_id}")
def interview_detail(
    interview_id: int,
    current_user: SessionUser = Depends(require_role("hr")),
    db: Session = Depends(get_db),
):
    session = (
        db.query(InterviewSession)
        .join(Result, InterviewSession.result_id == Result.id)
        .join(JobDescription, Result.job_id == JobDescription.id)
        .options(joinedload(InterviewSession.questions))
        .filter(
            InterviewSession.id == interview_id,
            JobDescription.company_id == current_user.user_id,
        )
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Interview not found")

    result = session.result
    candidate = db.query(Candidate).filter(Candidate.id == session.candidate_id).first()
    job = db.query(JobDescription).filter(JobDescription.id == result.job_id).first()
    events = (
        db.query(ProctorEvent)
        .filter(ProctorEvent.session_id == session.id)
        .order_by(ProctorEvent.created_at.asc())
        .all()
    )
    latest_answers: dict[int, InterviewAnswer] = {}
    for row in (
        db.query(InterviewAnswer)
        .filter(InterviewAnswer.session_id == session.id)
        .order_by(InterviewAnswer.question_id.asc(), InterviewAnswer.id.desc())
        .all()
    ):
        latest_answers.setdefault(row.question_id, row)

    # FIX: read HR review from dedicated columns (new) with JSON fallback (legacy)
    hr_review = _hr_review_from_result(result)
    job_skills = _json_dict(job.skill_scores).keys() if job else ()

    questions_payload = []
    section_scores: dict[str, list[float]] = defaultdict(list)
    answer_evaluations: list[dict[str, object]] = []
    
    # Sort and filter: Only show questions that were actually presented, answered, or skipped.
    # This prevents the full 8-20 question bank from cluttering the review if the interview ended early.
    target_questions = sorted(session.questions, key=lambda item: item.id)
    
    for q in target_questions:
        latest_answer = latest_answers.get(q.id)
        answer_text = q.answer_text if q.answer_text is not None else (latest_answer.answer_text if latest_answer else None)
        time_taken_seconds = q.time_taken_seconds if q.time_taken_seconds is not None else (latest_answer.time_taken_sec if latest_answer else None)
        skipped = q.skipped or (latest_answer.skipped if latest_answer else False)
        
        # A question is "asked" if it was served (started_at), answered, or explicitly skipped.
        is_asked = bool(q.started_at or answer_text or skipped or (time_taken_seconds and time_taken_seconds > 0))
        if not is_asked:
            continue

        stored_evaluation = _normalize_answer_evaluation(
            latest_answer.evaluation_json if latest_answer and latest_answer.evaluation_json is not None else q.evaluation_json
        )
        score_breakdown = _json_dict(stored_evaluation.get("score_breakdown"))
        if not score_breakdown:
            score_breakdown = compute_answer_scorecard(
                q.text,
                answer_text or "",
                allotted_seconds=int(q.allotted_seconds or 0),
                time_taken_seconds=int(time_taken_seconds or 0),
                jd_skills=job_skills,
            )
            stored_evaluation["score_breakdown"] = score_breakdown

        ai_answer_score = _safe_float(stored_evaluation.get("overall_answer_score"))
        if ai_answer_score is None:
            ai_answer_score = _safe_float(q.llm_score)
        if ai_answer_score is None:
            ai_answer_score = _safe_float(q.relevance_score)
        if ai_answer_score is None:
            ai_answer_score = _safe_float(score_breakdown.get("overall_score")) or 0.0

        section_name = str(q.question_type or q.topic or "project")
        section_scores[section_name].append(ai_answer_score)
        answer_evaluations.append(stored_evaluation)

        questions_payload.append(
            {
                "id": q.id,
                "text": q.text,
                "difficulty": q.difficulty,
                "topic": q.topic,
                "section": section_name,
                "reference_answer": q.reference_answer,
                "answer_text": answer_text,
                "answer_summary": q.answer_summary,
                "relevance_score": q.relevance_score,
                "ai_answer_score": ai_answer_score,
                "score_breakdown": score_breakdown,
                "allotted_seconds": q.allotted_seconds,
                "time_taken_seconds": time_taken_seconds,
                "skipped": skipped,
                "llm_score": q.llm_score,
                "llm_feedback": q.llm_feedback,
                "feedback": q.llm_feedback or stored_evaluation.get("feedback"),
                "evaluation": stored_evaluation,
            }
        )

    evaluation_summary = _json_dict(session.evaluation_summary_json)
    if session.llm_eval_status == "completed" and (session.status != "completed" or not evaluation_summary):
        evaluation_summary = summarize_interview(answer_evaluations)
        session.status = "completed"
        session.ended_at = session.ended_at or session.started_at
        session.evaluation_summary_json = evaluation_summary

        explanation = _json_dict(result.explanation)
        result.explanation = {
            **explanation,
            "overall_interview_score": evaluation_summary.get("overall_interview_score", 0.0),
            "communication_score": evaluation_summary.get("communication_score", 0.0),
            "strengths_summary": evaluation_summary.get("strengths_summary", []),
            "weaknesses_summary": evaluation_summary.get("weaknesses_summary", []),
            "hiring_recommendation": evaluation_summary.get("hiring_recommendation"),
        }

        score_breakdown = build_application_score(
            resume_score=float(explanation.get("final_resume_score") or result.score or 0.0),
            skills_match_score=float(explanation.get("matched_percentage") or explanation.get("weighted_skill_score") or 0.0),
            interview_score=float(evaluation_summary.get("overall_interview_score") or 0.0),
            communication_score=float(evaluation_summary.get("communication_score") or 0.0),
            weights_json=job.score_weights_json if job and getattr(job, "score_weights_json", None) else None,
        )
        result.score_breakdown_json = score_breakdown
        result.final_score = float(score_breakdown["final_weighted_score"])
        result.recommendation = score_breakdown["recommendation"]

        if result.stage != "interview_completed":
            record_stage_change(
                db,
                result,
                stage="interview_completed",
                changed_by_role="system",
                changed_by_user_id=None,
                note="Interview evaluation repaired from HR review",
            )
        db.commit()
    return {
        "ok": True,
        "interview": {
            "interview_id": session.id,
            "application_id": result.application_id,
            "candidate": {"id": candidate.id if candidate else None, "name": candidate.name if candidate else None, "email": candidate.email if candidate else None},
            "job": {"id": job.id if job else None, "title": job.jd_title if job else None},
            "status": session.status,
            "stage": stage_payload(result.stage),
            "started_at": session.started_at,
            "ended_at": session.ended_at,
            "llm_eval_status": session.llm_eval_status or "pending",
            "evaluation_summary": evaluation_summary,

            "recording_url": _recording_url(session),

            "recording_mime_type": session.recording_mime_type,

            "recording_size_bytes": session.recording_size_bytes,

            "recording_uploaded_at": session.recording_uploaded_at,
        },
        "questions": questions_payload,
        "events": [
            {
                "id": ev.id,
                "event_type": ev.event_type,
                "score": _safe_float(ev.score),
                "created_at": ev.created_at,
                "meta_json": _json_dict(ev.meta_json),
                "image_url": ev.image_path if ev.image_path and ev.image_path.startswith("http") else (f"/uploads/{ev.image_path}" if ev.image_path else None),
                "suspicious": ev.event_type not in {"periodic", "baseline"},
            }
            for ev in events
        ],
        "hr_review": hr_review,
        "section_summary": {key: round(float(sum(values)) / len(values), 1) for key, values in section_scores.items() if values},
    }


# ── finalize interview ────────────────────────────────────────────────────────

@router.get("/interviews/{interview_id}/recording")
def interview_recording(
    interview_id: int,
    current_user: SessionUser = Depends(require_role("hr")),
    db: Session = Depends(get_db),
):
    session = (
        db.query(InterviewSession)
        .join(Result, InterviewSession.result_id == Result.id)
        .join(JobDescription, Result.job_id == JobDescription.id)
        .filter(
            InterviewSession.id == interview_id,
            JobDescription.company_id == current_user.user_id,
        )
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Interview not found")

    recording_path = _recording_file_path(session)
    if not recording_path:
        raise HTTPException(status_code=404, detail="Recording file not found")
    if isinstance(recording_path, str):
        return RedirectResponse(recording_path)

    media_type = (session.recording_mime_type or "video/webm").split(";")[0].strip() or "video/webm"
    return FileResponse(
        path=str(recording_path),
        media_type=media_type,
        filename=recording_path.name,
        content_disposition_type="inline",
        headers={
            "Accept-Ranges": "bytes",
            "Cache-Control": "private, max-age=0, no-store",
        },
    )


class FinalizeBody(BaseModel):
    decision: str
    notes: str | None = None
    final_score: float | None = Field(default=None, ge=0, le=100)
    behavioral_score: float | None = Field(default=None, ge=0, le=100)
    communication_score: float | None = Field(default=None, ge=0, le=100)
    red_flags: str | None = None


@router.post("/interviews/{interview_id}/finalize")
def finalize_interview(
    interview_id: int,
    payload: FinalizeBody,
    background_tasks: BackgroundTasks,
    current_user: SessionUser = Depends(require_role("hr")),
    db: Session = Depends(get_db),
):
    session = (
        db.query(InterviewSession)
        .join(Result, InterviewSession.result_id == Result.id)
        .join(JobDescription, Result.job_id == JobDescription.id)
        .filter(
            InterviewSession.id == interview_id,
            JobDescription.company_id == current_user.user_id,
        )
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Interview not found")

    session.status = payload.decision.lower()
    session.ended_at = session.ended_at or session.started_at

    result = session.result
    job = result.job

    # FIX: Write to dedicated columns — no longer merging into explanation JSON.
    result.hr_decision = payload.decision.lower()
    result.hr_final_score = payload.final_score
    result.hr_behavioral_score = payload.behavioral_score
    result.hr_communication_score = payload.communication_score
    result.hr_notes = payload.notes
    result.hr_red_flags = payload.red_flags

    if payload.final_score is not None:

        result.score = payload.final_score

        score_breakdown = build_application_score(

            resume_score=float((result.explanation or {}).get("final_resume_score") or result.score or 0.0),

            skills_match_score=float((result.explanation or {}).get("matched_percentage") or 0.0),

            interview_score=float(payload.final_score),

            communication_score=float(payload.communication_score or 0.0),

            weights_json=job.score_weights_json if job and hasattr(job, 'score_weights_json') and job.score_weights_json else None,

        )
        result.final_score = float(score_breakdown["final_weighted_score"])
        result.score_breakdown_json = score_breakdown
        result.recommendation = score_breakdown["recommendation"]

    record_stage_change(
        db,
        result,
        stage=payload.decision.lower(),
        changed_by_role="hr",
        changed_by_user_id=current_user.user_id,
        note=payload.notes,
    )

    # ── Automated Correspondence ─────────────────────────────────────────────
    # Trigger Selection or Rejection emails based on the HR decision.
    from utils.email_service import send_selection_email, send_rejection_email
    
    candidate = session.candidate
    job_title = job.jd_title if job and job.jd_title else "Software Engineer"
    
    if payload.decision.lower() == "selected":
        # Dispatch email as a background task to prevent blocking the UI response.
        background_tasks.add_task(send_selection_email, candidate.email, candidate.name, job_title)
    elif payload.decision.lower() == "rejected":
        background_tasks.add_task(send_rejection_email, candidate.email, candidate.name, job_title)

    db.commit()
    return {
        "ok": True,
        "status": session.status,
# ...
        "hr_review": {
            "final_score": payload.final_score,
            "behavioral_score": payload.behavioral_score,
            "communication_score": payload.communication_score,
            "red_flags": payload.red_flags,
            "notes": payload.notes,
        },
    }


# ── re-evaluate interview answers ────────────────────────────────────────────

@router.post("/interviews/{interview_id}/re-evaluate")
def re_evaluate_interview(
    interview_id: int,
    background_tasks: BackgroundTasks,
    current_user: SessionUser = Depends(require_role("hr")),
    db: Session = Depends(get_db),
):
    session = (
        db.query(InterviewSession)
        .join(Result, InterviewSession.result_id == Result.id)
        .join(JobDescription, Result.job_id == JobDescription.id)
        .filter(
            InterviewSession.id == interview_id,
            JobDescription.company_id == current_user.user_id,
        )
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Interview not found")
    if session.status == "in_progress":
        raise HTTPException(status_code=400, detail="Cannot re-evaluate an interview that is still in progress.")

    session.llm_eval_status = "running"
    db.commit()
    background_tasks.add_task(_run_llm_evaluation, interview_id)
    return {"ok": True, "message": "AI re-evaluation started. Refresh the interview detail page in ~30 seconds.", "session_id": interview_id}


# Keep the import available for background tasks.
from database import SessionLocal  # noqa: E402


def _run_llm_evaluation(session_id: int) -> None:
    from services.llm.client import evaluate_answer_detailed

    db = SessionLocal()
    try:
        session = db.query(InterviewSession).filter(InterviewSession.id == session_id).first()
        if not session:
            return

        questions = (
            db.query(InterviewQuestion)
            .filter(InterviewQuestion.session_id == session_id)
            .order_by(InterviewQuestion.id.asc())
            .all()
        )

        scored = 0
        total_score = 0.0
        for question in questions:
            answer_text = (question.answer_text or "").strip()
            if not answer_text or question.skipped:
                evaluation = {
                    "question": question.text,
                    "candidate_answer": answer_text,
                    "generated_reference_answer": question.reference_answer or "A strong answer should directly answer the question with practical detail.",
                    "score": 0,
                    "feedback": "Answer was skipped or empty.",
                    "strengths": [],
                    "weaknesses": ["No answer was provided."],
                    "section": question.question_type or "project",
                    "dimension_breakdown": {"relevance": 0, "correctness": 0, "completeness": 0, "clarity": 0, "confidence": 0},
                }
                _save_llm_fields(db, session_id, question.id, evaluation)
                continue

            try:
                evaluation = evaluate_answer_detailed(
                    question=question.text,
                    answer=answer_text,
                    section=question.question_type or "project",
                    reference_answer=question.reference_answer,
                    intent=question.intent,
                    focus_skill=question.focus_skill,
                    project_name=question.project_name,
                )
            except Exception as exc:
                logger.error("AI scoring failed for question %s: %s", question.id, exc)
                from ai_engine.phase1.scoring import compute_answer_scorecard
                local = compute_answer_scorecard(question.text, answer_text)
                overall = int(local["overall_score"])
                evaluation = {
                    "question": question.text,
                    "candidate_answer": answer_text,
                    "generated_reference_answer": question.reference_answer or "A strong answer should directly answer the question with practical detail.",
                    "score": overall,
                    "feedback": "Scored locally (AI unavailable).",
                    "strengths": ["The answer was evaluated using the local fallback scorer."],
                    "weaknesses": [],
                    "section": question.question_type or "project",
                    "dimension_breakdown": {"relevance": overall, "correctness": overall, "completeness": overall, "clarity": overall, "confidence": overall},
                }

            _save_llm_fields(db, session_id, question.id, evaluation)
            total_score += float(evaluation["score"])
            scored += 1

        session = db.query(InterviewSession).filter(InterviewSession.id == session_id).first()
        if session:
            session.llm_eval_status = "completed"
        db.commit()
        logger.info("AI re-evaluation done: session=%s scored=%s avg=%.1f", session_id, scored, total_score / scored if scored else 0)
    except Exception as exc:
        logger.error("AI re-evaluation worker failed for session %s: %s", session_id, exc)
        try:
            session = db.query(InterviewSession).filter(InterviewSession.id == session_id).first()
            if session:
                session.llm_eval_status = "failed"
                db.commit()
        except Exception:
            pass
    finally:
        db.close()


def _save_llm_fields(db: Session, session_id: int, question_id: int, evaluation: dict[str, Any]) -> None:
    answer = (
        db.query(InterviewAnswer)
        .filter(
            InterviewAnswer.session_id == session_id,
            InterviewAnswer.question_id == question_id,
        )
        .order_by(InterviewAnswer.id.desc())
        .first()
    )
    if answer:
        answer.llm_score = float(evaluation["score"])
        answer.llm_feedback = str(evaluation["feedback"])
        answer.evaluation_json = evaluation

    question = db.query(InterviewQuestion).filter(InterviewQuestion.id == question_id).first()
    if question:
        question.llm_score = float(evaluation["score"])
        question.llm_feedback = str(evaluation["feedback"])
        question.reference_answer = str(evaluation.get("generated_reference_answer") or question.reference_answer or "") or None
        question.evaluation_json = evaluation

        question.llm_score = float(evaluation["score"])
        question.llm_feedback = str(evaluation["feedback"])
        question.reference_answer = str(evaluation.get("generated_reference_answer") or question.reference_answer or "") or None
        question.evaluation_json = evaluation

    db.flush()


# ── Feature: Send Performance Feedback Email ──────────────────────────────────
@router.post("/interviews/{interview_id}/send-feedback")
def send_candidate_feedback(
    interview_id: int,
    background_tasks: BackgroundTasks,
    current_user: SessionUser = Depends(require_role("hr")),
    db: Session = Depends(get_db),
):
    """Send AI-generated performance feedback to the candidate via email."""
    session = (
        db.query(InterviewSession)
        .join(Result, InterviewSession.result_id == Result.id)
        .join(JobDescription, Result.job_id == JobDescription.id)
        .filter(
            InterviewSession.id == interview_id,
            JobDescription.company_id == current_user.user_id,
        )
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Interview not found")

    candidate = session.candidate
    result = session.result
    job = result.job if result else None
    job_title = (job.jd_title if job and job.jd_title else "Software Engineer")

    # Pull summary data from result explanation
    explanation = result.explanation or {} if result else {}
    strengths = list(explanation.get("strengths_summary") or [])[:5]
    weaknesses = list(explanation.get("weaknesses_summary") or [])[:5]
    overall_score = float(explanation.get("overall_interview_score") or result.hr_final_score or 0)

    from utils.email_service import send_performance_feedback_email
    background_tasks.add_task(
        send_performance_feedback_email,
        candidate.email, candidate.name, job_title, strengths, weaknesses, overall_score
    )

    return {"ok": True, "message": f"Feedback email is being sent to {candidate.email}"}


# ── Feature: HR Custom Questions PATCH ───────────────────────────────────────
class CustomQuestionsBody(BaseModel):
    questions: list[str] = Field(default_factory=list)

@router.patch("/jobs/{job_id}/custom-questions")
def update_custom_questions(
    job_id: int,
    payload: CustomQuestionsBody,
    current_user: SessionUser = Depends(require_role("hr")),
    db: Session = Depends(get_db),
):
    """HR can set mandatory questions for a job description."""
    job = (
        db.query(JobDescription)
        .filter(JobDescription.id == job_id, JobDescription.company_id == current_user.user_id)
        .first()
    )
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    job.custom_questions = [q.strip() for q in payload.questions if q.strip()]
    db.commit()
    return {"ok": True, "custom_questions": job.custom_questions}



# -- Feature: PDF Interview Report Export --

@router.get("/interviews/{session_id}/report")
def download_interview_report(
    session_id: int,
    current_user: SessionUser = Depends(require_role("hr")),
    db: Session = Depends(get_db),
):
    """Download a PDF interview report for HR review."""
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
        raise HTTPException(status_code=404, detail="Interview session not found")

    pdf_buffer = generate_interview_pdf(session, db)
    candidate = db.query(Candidate).filter(Candidate.id == session.candidate_id).first()
    filename = f"interview_report_{candidate.name.replace(' ', '_') if candidate else 'unknown'}_{session_id}.pdf"

    return StreamingResponse(
        iter([pdf_buffer.getvalue()]),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
