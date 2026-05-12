"""Post-interview answer evaluation with structured metadata."""
from __future__ import annotations

import json
import logging
import re
import time
from collections import defaultdict
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ai_engine.phase1.scoring import compute_answer_scorecard
from database import get_db, SessionLocal
from models import InterviewAnswer, InterviewQuestion, InterviewSession
from routes.dependencies import SessionUser, require_role
from services.llm.client import _clean_json, _get_client, _llm_model, _llm_provider
from services.pipeline import record_stage_change
from services.scoring import build_application_score, summarize_interview

logger = logging.getLogger(__name__)
router = APIRouter(tags=["interview-evaluation"])


def _local_dimension_breakdown(question: InterviewQuestion, answer_text: str) -> dict[str, int]:
    scorecard = compute_answer_scorecard(
        question.text,
        answer_text,
        allotted_seconds=int(question.allotted_seconds or 0),
        time_taken_seconds=int(question.time_taken_seconds or 0),
        jd_skills=[question.focus_skill] if question.focus_skill else (),
    )
    overall = int(scorecard.get("overall_score", 0))
    relevance = int(scorecard.get("relevance_score", overall))
    completeness = int(scorecard.get("completeness_score", overall))
    clarity = int(scorecard.get("clarity_score", overall))
    confidence = max(35, min(100, int((clarity + completeness) / 2)))
    correctness = max(0, min(100, int((overall + relevance) / 2)))
    return {
        "relevance": relevance,
        "correctness": correctness,
        "completeness": completeness,
        "clarity": clarity,
        "confidence": confidence,
    }


def _fallback_evaluation(question: InterviewQuestion, answer_text: str) -> dict[str, object]:
    try:
        dims = _local_dimension_breakdown(question, answer_text)
        overall = round(sum(dims.values()) / len(dims), 1)
        strengths = []
        weaknesses = []
        if dims["relevance"] >= 65:
            strengths.append("The answer stayed relevant to the question.")
        else:
            weaknesses.append("The answer did not fully address the main intent of the question.")
        if dims["clarity"] >= 60:
            strengths.append("The explanation was reasonably clear and understandable.")
        else:
            weaknesses.append("The explanation could be structured more clearly.")
        if dims["completeness"] >= 65:
            strengths.append("The answer covered multiple useful points.")
        else:
            weaknesses.append("More concrete detail or examples were needed.")
        reference = question.reference_answer or "A strong answer should directly answer the question, use practical examples, and explain the reasoning behind decisions."
        return {
            "question": question.text,
            "candidate_answer": answer_text,
            "generated_reference_answer": reference,
            "score": overall,
            "feedback": "Scored using the local evaluation fallback. The answer was checked for relevance, clarity, completeness, and practical depth.",
            "strengths": strengths[:3],
            "weaknesses": weaknesses[:3],
            "section": question.question_type or "project",
            "dimension_breakdown": dims,
        }
    except Exception as exc:
        logger.error("Extreme fallback triggered in _fallback_evaluation: %s", exc)
        return {
            "question": question.text,
            "candidate_answer": answer_text,
            "generated_reference_answer": question.reference_answer or "A strong answer should directly answer the question, use practical examples, and explain the reasoning behind decisions.",
            "score": 50,
            "feedback": "Scored using the emergency evaluation fallback.",
            "strengths": ["The candidate provided an answer."],
            "weaknesses": ["The answer could not be properly evaluated due to an internal error."],
            "section": question.question_type or "project",
            "dimension_breakdown": {"relevance": 50, "correctness": 50, "completeness": 50, "clarity": 50, "confidence": 50},
        }


def _batch_llm_evaluate(questions: list[InterviewQuestion], db: Session = None) -> dict[int, dict[str, object]]:
    """
    Evaluate all answered questions in a SINGLE LLM call to minimize API usage.
    Returns a mapping of question.id -> evaluation dict.
    Falls back to local scoring if the LLM call fails.
    """
    # If questions don't have answer_text, check InterviewAnswer table
    answerable = []
    for q in questions:
        answer_text = (q.answer_text or "").strip()
        if not answer_text and db:
            # Fallback: check InterviewAnswer table
            ans = db.query(InterviewAnswer).filter(
                InterviewAnswer.question_id == q.id
            ).first()
            if ans and ans.answer_text:
                answer_text = ans.answer_text
                q.answer_text = answer_text  # Backfill
                q.skipped = ans.skipped or False
        if answer_text and not q.skipped:
            answerable.append(q)
    if not answerable:
        return {}

    # Build a compact batch prompt — one LLM call for all answers.
    items_text = ""
    for i, q in enumerate(answerable):
        items_text += (
            f'\n  {{"id": {q.id}, "question": {json.dumps((q.text or "")[:300])}, '
            f'"answer": {json.dumps((q.answer_text or "")[:600])}, '
            f'"section": {json.dumps(q.question_type or "project")}, '
            f'"focus_skill": {json.dumps(q.focus_skill or "")}, '
            f'"reference_hint": {json.dumps((q.reference_answer or "")[:300])}}}'
        )
        if i < len(answerable) - 1:
            items_text += ","

    prompt = f"""You are a senior technical interviewer performing a CRITICAL AUDIT of candidate answers.
Your goal is to identify technically incorrect, hallucinated, or superficial answers. 

Rules for Scoring:
1. TECHNICAL AUDIT: If an answer contains technically incorrect facts (e.g. "Python was built by Microsoft" or "A primary key can have duplicates"), you MUST assign a score below 40 regardless of how confident the candidate sounds.
2. RELEVANCE: Ensure the answer directly addresses the specific technical challenge in the question.
3. CONCISENESS: One concise sentence for feedback (max 80 chars).

Return ONLY a valid JSON object with this shape:
{{
  "evaluations": [
    {{
      "id": <id>,
      "score": <0-100>,
      "feedback": "<concise feedback>",
      "strengths": ["<short strength>"],
      "weaknesses": ["<short weakness>"],
      "dimension_breakdown": {{"relevance": <0-100>, "correctness": <0-100>, "completeness": <0-100>, "clarity": <0-100>, "confidence": <0-100>}}
    }}
  ]
}}

Answers to audit:
[{items_text}
]"""

    try:
        response = _get_client().create(
            model=_llm_model(),
            messages=[{"role": "user", "content": prompt}],
            temperature=0.05,
            max_tokens=2000,
        )
        raw = _clean_json(response.choices[0].message.content or "")
        # Find the outermost JSON object (handles nested braces correctly)
        match = re.search(r"\{[\s\S]*\}", raw)
        if match:
            raw = match.group(0)
        data = json.loads(raw)
        evals_list = data.get("evaluations") or []

        result: dict[int, dict[str, object]] = {}
        for ev in evals_list:
            if not isinstance(ev, dict):
                continue
            qid = ev.get("id")
            if not isinstance(qid, int):
                try:
                    qid = int(qid)
                except Exception:
                    continue
            dims = ev.get("dimension_breakdown") or {}
            if not isinstance(dims, dict):
                dims = {}
            clean_dims = {k: max(0, min(100, int(dims.get(k, 50)))) for k in ["relevance", "correctness", "completeness", "clarity", "confidence"]}
            score_raw = ev.get("score", 50)
            try:
                score_val = float(score_raw)
            except Exception:
                score_val = 50.0
            strengths = [str(x) for x in (ev.get("strengths") or [])[:3]]
            weaknesses = [str(x) for x in (ev.get("weaknesses") or [])[:3]]
            # Find matching question for reference
            q_obj = next((q for q in answerable if q.id == qid), None)
            result[qid] = {
                "question": q_obj.text if q_obj else "",
                "candidate_answer": q_obj.answer_text if q_obj else "",
                "generated_reference_answer": q_obj.reference_answer if q_obj else "",
                "score": max(0.0, min(100.0, score_val)),
                "feedback": str(ev.get("feedback") or "Evaluation completed."),
                "strengths": strengths,
                "weaknesses": weaknesses,
                "section": q_obj.question_type if q_obj else "project",
                "dimension_breakdown": clean_dims,
            }
        logger.info("batch_llm_evaluate_success provider=%s model=%s questions=%s evaluated=%s",
                    _llm_provider(), _llm_model(), len(answerable), len(result))
        return result
    except Exception as exc:
        logger.warning("batch_llm_evaluate_failed provider=%s model=%s error=%s — using local fallback",
                       _llm_provider(), _llm_model(), exc)
        return {}


def _upsert_llm_fields(db: Session, session_id: int, question: InterviewQuestion, evaluation: dict[str, object]) -> None:
    answer = (
        db.query(InterviewAnswer)
        .filter(InterviewAnswer.session_id == session_id, InterviewAnswer.question_id == question.id)
        .order_by(InterviewAnswer.id.desc())
        .first()
    )
    if answer:
        answer.llm_score = float(evaluation["score"])
        answer.llm_feedback = str(evaluation["feedback"])
        answer.evaluation_json = evaluation

    question.llm_score = float(evaluation["score"])
    question.llm_feedback = str(evaluation["feedback"])
    question.reference_answer = str(evaluation.get("generated_reference_answer") or question.reference_answer or "") or None
    question.evaluation_json = evaluation
    db.flush()


def _summary_ready_evaluation(evaluation: dict[str, object]) -> dict[str, object]:
    dims = evaluation.get("dimension_breakdown") or {}
    if not isinstance(dims, dict):
        dims = {}
    score = evaluation.get("overall_answer_score", evaluation.get("score", 0))
    try:
        overall = float(score or 0)
    except Exception:
        overall = 0.0
    return {
        **evaluation,
        "overall_answer_score": overall,
        "confidence_communication": float(
            evaluation.get("confidence_communication")
            or dims.get("confidence")
            or dims.get("clarity")
            or overall
            or 0
        ),
        "strengths": evaluation.get("strengths") if isinstance(evaluation.get("strengths"), list) else [],
        "weaknesses": evaluation.get("weaknesses") if isinstance(evaluation.get("weaknesses"), list) else [],
    }


def _collect_stored_evaluations(db: Session, session_id: int) -> tuple[list[dict[str, object]], dict[str, list[float]]]:
    questions = db.query(InterviewQuestion).filter(InterviewQuestion.session_id == session_id).order_by(InterviewQuestion.id.asc()).all()
    answer_evaluations: list[dict[str, object]] = []
    section_scores: dict[str, list[float]] = defaultdict(list)

    for question in questions:
        answer = (
            db.query(InterviewAnswer)
            .filter(InterviewAnswer.session_id == session_id, InterviewAnswer.question_id == question.id)
            .order_by(InterviewAnswer.id.desc())
            .first()
        )
        raw_eval = (answer.evaluation_json if answer and answer.evaluation_json else None) or question.evaluation_json or {}
        if not raw_eval:
            continue
        normalized = _summary_ready_evaluation(raw_eval)
        answer_evaluations.append(normalized)
        section = str(normalized.get("section") or question.question_type or "project")
        section_scores[section].append(float(normalized.get("overall_answer_score") or 0))

    return answer_evaluations, section_scores


def _finalize_interview_evaluation(
    db: Session,
    session: InterviewSession,
    answer_evaluations: list[dict[str, object]],
    section_scores: dict[str, list[float]],
) -> tuple[dict[str, object], dict[str, float]]:
    summary = summarize_interview(answer_evaluations)
    section_summary = {key: round(sum(values) / len(values), 1) for key, values in section_scores.items() if values}

    session.llm_eval_status = "completed"
    session.status = "completed"
    session.ended_at = session.ended_at or datetime.utcnow()
    session.evaluation_summary_json = summary

    result = session.result
    if result:
        explanation = result.explanation if isinstance(result.explanation, dict) else {}
        result.explanation = {
            **explanation,
            "overall_interview_score": summary.get("overall_interview_score", 0.0),
            "communication_score": summary.get("communication_score", 0.0),
            "strengths_summary": summary.get("strengths_summary", []),
            "weaknesses_summary": summary.get("weaknesses_summary", []),
            "hiring_recommendation": summary.get("hiring_recommendation"),
        }

        job = result.job
        score_breakdown = build_application_score(
            resume_score=float(explanation.get("final_resume_score") or result.score or 0.0),
            skills_match_score=float(explanation.get("matched_percentage") or explanation.get("weighted_skill_score") or 0.0),
            interview_score=float(summary.get("overall_interview_score") or 0.0),
            communication_score=float(summary.get("communication_score") or 0.0),
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
                note="Interview evaluation completed",
            )

    return summary, section_summary


def run_evaluation_task(session_id: int) -> None:
    """Background task to evaluate interview answers using a single batched LLM call."""
    db = SessionLocal()
    try:
        session = db.query(InterviewSession).filter(InterviewSession.id == session_id).first()
        if not session:
            logger.error("Session %s not found for background evaluation.", session_id)
            return

        rows_updated = db.query(InterviewSession).filter(
            InterviewSession.id == session_id,
            (InterviewSession.llm_eval_status == None) | (InterviewSession.llm_eval_status == "pending")
        ).update({"llm_eval_status": "running"}, synchronize_session=False)
        db.commit()
        db.refresh(session)

        if rows_updated == 0:
            logger.info("Evaluation for session %s already running or completed. Skipping background task.", session_id)
            return

        questions = db.query(InterviewQuestion).filter(InterviewQuestion.session_id == session_id).order_by(InterviewQuestion.id.asc()).all()
        scored = 0
        total_score = 0.0
        section_scores: dict[str, list[float]] = defaultdict(list)
        answer_evaluations: list[dict[str, object]] = []

        # ONE batched LLM call for all answered questions (saves N-1 API requests vs per-question).
        llm_results = _batch_llm_evaluate(questions)

        for question in questions:
            answer_text = (question.answer_text or "").strip()
            if not answer_text or question.skipped:
                evaluation: dict[str, object] = {
                    "question": question.text,
                    "candidate_answer": answer_text,
                    "generated_reference_answer": question.reference_answer or "A strong answer should directly respond to the prompt with practical detail.",
                    "score": 0,
                    "feedback": "Answer was skipped or empty.",
                    "strengths": [],
                    "weaknesses": ["No answer was provided."],
                    "section": question.question_type or "project",
                    "dimension_breakdown": {"relevance": 0, "correctness": 0, "completeness": 0, "clarity": 0, "confidence": 0},
                }
                _upsert_llm_fields(db, session_id, question, evaluation)
                continue

            # Use LLM result if available, otherwise fall back to local scoring.
            evaluation = llm_results.get(question.id) or _fallback_evaluation(question, answer_text)

            _upsert_llm_fields(db, session_id, question, evaluation)
            total_score += float(evaluation["score"])
            scored += 1
            normalized = _summary_ready_evaluation(evaluation)
            answer_evaluations.append(normalized)
            section_scores[str(evaluation.get("section") or "project")].append(float(normalized["overall_answer_score"]))

        _finalize_interview_evaluation(db, session, answer_evaluations, section_scores)

        db.commit()
    except Exception as exc:
        logger.error("Background evaluation task failed for session %s: %s", session_id, exc)
        db.rollback()
        session = db.query(InterviewSession).filter(InterviewSession.id == session_id).first()
        if session:
            session.llm_eval_status = "failed"
            db.commit()
    finally:
        db.close()


@router.post("/interview/{session_id}/evaluate")
def evaluate_interview(
    session_id: int,
    current_user: SessionUser = Depends(require_role("candidate")),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    session = db.query(InterviewSession).filter(InterviewSession.id == session_id, InterviewSession.candidate_id == current_user.user_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Interview session not found")

    # Atomic lock
    rows_updated = db.query(InterviewSession).filter(
        InterviewSession.id == session_id,
        (InterviewSession.llm_eval_status == None) | (InterviewSession.llm_eval_status == "pending")
    ).update({"llm_eval_status": "running"}, synchronize_session=False)
    db.commit()

    if rows_updated == 0:
        # Another thread (like the background task) already took the lock.
        # Wait for it to finish so the frontend spinner stays active.
        db.refresh(session)
        for _ in range(30):
            if session.llm_eval_status in ("completed", "failed"):
                break
            time.sleep(2)
            db.refresh(session)
        if session.llm_eval_status == "completed" and (session.status != "completed" or not session.evaluation_summary_json):
            answer_evaluations, section_scores = _collect_stored_evaluations(db, session_id)
            summary, section_summary = _finalize_interview_evaluation(db, session, answer_evaluations, section_scores)
            db.commit()
            return {
                "ok": True,
                "session_id": session_id,
                "status": session.llm_eval_status,
                "questions_evaluated": len(answer_evaluations),
                "average_llm_score": round(float(summary.get("overall_interview_score") or 0.0), 1),
                "section_summary": section_summary,
                "message": "Evaluation was repaired and finalized.",
            }
        return {"ok": True, "session_id": session_id, "status": session.llm_eval_status, "message": "Evaluation handled by background task."}

    questions = db.query(InterviewQuestion).filter(InterviewQuestion.session_id == session_id).order_by(InterviewQuestion.id.asc()).all()
    scored = 0
    total_score = 0.0
    section_scores: dict[str, list[float]] = defaultdict(list)
    answer_evaluations: list[dict[str, object]] = []

    # ONE batched LLM call for all questions (1 API request per interview, not N).
    llm_results = _batch_llm_evaluate(questions, db)

    for question in questions:
        answer_text = (question.answer_text or "").strip()
        # Fallback: check InterviewAnswer if not on question
        if not answer_text:
            ans = db.query(InterviewAnswer).filter(
                InterviewAnswer.question_id == question.id
            ).first()
            if ans and ans.answer_text:
                answer_text = ans.answer_text.strip()
                question.answer_text = answer_text
                question.skipped = ans.skipped or False
        
        if not answer_text or question.skipped:
            evaluation: dict[str, object] = {
                "question": question.text,
                "candidate_answer": answer_text,
                "generated_reference_answer": question.reference_answer or "A strong answer should directly respond to the prompt with practical detail.",
                "score": 0,
                "feedback": "Answer was skipped or empty.",
                "strengths": [],
                "weaknesses": ["No answer was provided."],
                "section": question.question_type or "project",
                "dimension_breakdown": {"relevance": 0, "correctness": 0, "completeness": 0, "clarity": 0, "confidence": 0},
            }
            _upsert_llm_fields(db, session_id, question, evaluation)
            continue

        # Use LLM result if available, otherwise fall back to local scoring.
        evaluation = llm_results.get(question.id) or _fallback_evaluation(question, answer_text)

        _upsert_llm_fields(db, session_id, question, evaluation)
        total_score += float(evaluation["score"])
        scored += 1
        normalized = _summary_ready_evaluation(evaluation)
        answer_evaluations.append(normalized)
        section_scores[str(evaluation.get("section") or "project")].append(float(normalized["overall_answer_score"]))

    summary, section_summary = _finalize_interview_evaluation(db, session, answer_evaluations, section_scores)
    db.commit()

    avg_score = round(float(summary.get("overall_interview_score") or (total_score / scored if scored else 0.0)), 1)
    return {"ok": True, "session_id": session_id, "questions_evaluated": scored, "average_llm_score": avg_score, "section_summary": section_summary}
