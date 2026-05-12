"""Candidate-facing dashboard and resume workflows."""

import logging
import secrets
import shutil
import uuid
from pathlib import Path

import requests
from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session
from services.question_generation import build_question_bundle
from ai_engine.phase1.scoring import compute_resume_skill_match
from ai_engine.phase1.matching import extract_text_from_file
from database import get_db
from models import InterviewSession, JobDescription, Result
from core.config import config
from routes.common import (
    UPLOAD_DIR,
    ensure_candidate_profile,
    evaluate_resume_for_job,
    get_candidate_or_404,
    interview_entry_url,
    list_active_jds,
    list_available_jobs,
    parse_interview_datetime_utc,
    serialize_result,
    upsert_result,
)
from routes.dependencies import SessionUser, require_role
from routes.schemas import CandidateSelectJDBody, ScheduleInterviewBody
from services.practice import build_practice_kit
from services.resume_advice import build_resume_advice

from utils.email_service import send_interview_email, send_eligibility_email, send_interview_confirmation_email

router = APIRouter()
logger = logging.getLogger(__name__)


# Result.interview_questions remains the stored question-bank source of truth.
# Generation flows through the shared facade in services.question_generation.
def _generate_result_question_bank(
    *,
    result: Result,
    resume_text: str,
    job: JobDescription,
) -> list[dict[str, object]]:
    project_ratio = float(job.project_question_ratio) if job and job.project_question_ratio is not None else 0.8
    bundle = build_question_bundle(
        resume_text=resume_text,
        jd_title=job.jd_title,
        jd_skill_scores=(job.skill_scores or {}),
        question_count=int(job.question_count if job.question_count is not None else 8),
        project_ratio=project_ratio,
    )
    questions = bundle.get("questions") or []
    result.interview_questions = questions
    return questions


def _selected_jd_or_404(db: Session, jd_id: int) -> JobDescription:
    selected_jd = db.query(JobDescription).filter(JobDescription.id == jd_id).first()
    if not selected_jd:
        raise HTTPException(status_code=404, detail="JD not found")
    return selected_jd


def _resume_advice_payload(
    *,
    candidate,
    selected_jd: JobDescription | None,
    explanation: dict[str, object] | None,
) -> dict[str, object] | None:
    if not selected_jd:
        return None
    resume_text = (candidate.resume_text or "").strip()
    if not resume_text:
        return None
    return build_resume_advice(
        resume_text=resume_text,
        jd_skill_scores=selected_jd.weights_json or {},
        explanation=explanation or {},
        candidate_name=getattr(candidate, 'name', None) or None,
    )


@router.get("/candidate/dashboard")
def candidate_dashboard(
    job_id: int | None = None,
    current_user: SessionUser = Depends(require_role("candidate")),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    candidate = get_candidate_or_404(db, current_user.user_id)
    if ensure_candidate_profile(candidate, db):
        db.commit()
        db.refresh(candidate)
    if job_id is not None and job_id > 0 and candidate.selected_jd_id != job_id:
        candidate.selected_jd_id = job_id
        db.commit()
        db.refresh(candidate)

    available_jobs = list_available_jobs(db)
    available_jds = list_active_jds(db)
    selected_job_id = candidate.selected_jd_id or (available_jds[0]["id"] if available_jds else None)

    result = None
    selected_jd = None
    if selected_job_id:
        try:
            selected_jd = _selected_jd_or_404(db, selected_job_id)
        except HTTPException:
            selected_jd = None
        result = (
            db.query(Result)
            .filter(Result.candidate_id == candidate.id, Result.job_id == selected_job_id)
            .order_by(Result.id.desc())
            .first()
        )

    return {
        "ok": True,
        "candidate": {
            "id": candidate.id,
            "candidate_uid": candidate.candidate_uid,
            "name": candidate.name,
            "email": candidate.email,
            "gender": candidate.gender,
            "resume_path": candidate.resume_path,
            "created_at": candidate.created_at,
        },
        "available_jobs": available_jobs,
        "available_jds": available_jds,
        "selected_job_id": selected_job_id,
        "selected_jd_id": selected_job_id,
        "result": serialize_result(result),
        "resume_advice": _resume_advice_payload(
            candidate=candidate,
            selected_jd=selected_jd,
            explanation=(result.explanation if result else None),
        ),
    }


@router.get("/candidate/jds")
def candidate_jds(
    current_user: SessionUser = Depends(require_role("candidate")),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    candidate = get_candidate_or_404(db, current_user.user_id)
    if ensure_candidate_profile(candidate, db):
        db.commit()
        db.refresh(candidate)
    return {
        "ok": True,
        "selected_jd_id": candidate.selected_jd_id,
        "jds": list_active_jds(db),
    }


@router.get("/candidate/all-results")
def candidate_all_results(
    current_user: SessionUser = Depends(require_role("candidate")),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    """Return results for all JDs the candidate has applied to (safe data - no scores)."""
    candidate = get_candidate_or_404(db, current_user.user_id)
    if ensure_candidate_profile(candidate, db):
        db.commit()
        db.refresh(candidate)

    results = (
        db.query(Result)
        .filter(Result.candidate_id == candidate.id)
        .order_by(Result.id.desc())
        .all()
    )

    available_jds = list_active_jds(db)
    jd_map = {jd["id"]: jd for jd in available_jds}

    applications = []
    for r in results:
        jd_info = jd_map.get(r.job_id, {})
        status = "under_review"
        if r.shortlisted:
            status = "selected"
        elif r.stage and r.stage.key == "rejected":
            status = "rejected"
        
        applications.append({
            "jd_id": r.job_id,
            "jd_title": jd_info.get("title", "Unknown Role"),
            "jd_qualify_score": jd_info.get("qualify_score"),
            "status": status,
            "applied_at": r.created_at.isoformat() if r.created_at else None,
        })

    return {
        "ok": True,
        "applications": applications,
        "available_jds": available_jds,
    }


@router.post("/candidate/select-jd")
def candidate_select_jd(
    payload: CandidateSelectJDBody,
    current_user: SessionUser = Depends(require_role("candidate")),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    candidate = get_candidate_or_404(db, current_user.user_id)
    selected_jd = _selected_jd_or_404(db, payload.jd_id)

    logger.info(f"SELECT_JD: candidate_id={candidate.id}, jd_id={selected_jd.id}, resume_path={bool(candidate.resume_path)}, resume_text={bool(candidate.resume_text)}")

    candidate.selected_jd_id = selected_jd.id
    db.commit()
    db.refresh(candidate)

    logger.info(f"SELECT_JD: resume_path={candidate.resume_path}, resume_text_len={len(candidate.resume_text or '')}")

    result_data = None
    if candidate.resume_path and (candidate.resume_text or "").strip():
        try:
            logger.info(f"SELECT_JD running resume screening for candidate_id={candidate.id}, jd_id={selected_jd.id}")
            score, explanation, _ = evaluate_resume_for_job(candidate, selected_jd)
            
            result = upsert_result(
                db,
                candidate.id,
                selected_jd.id,
                score,
                explanation,
                cutoff_score=float(selected_jd.qualify_score if selected_jd.qualify_score is not None else 65.0),
                job=selected_jd,
            )
            db.commit()
            db.refresh(result)
            
            result_data = serialize_result(result)
            logger.info(f"SELECT_JD screening complete: score={score}, shortlisted={result.shortlisted}, stage={result.stage}")
            
            return {
                "ok": True,
                "selected_jd_id": candidate.selected_jd_id,
                "jd": {
                    "id": selected_jd.id,
                    "title": selected_jd.title,
                    "qualify_score": float(selected_jd.qualify_score if selected_jd.qualify_score is not None else 65.0),
                    "total_questions": int(selected_jd.total_questions if selected_jd.total_questions is not None else 8),
                },
                "result": result_data,
            }
        except Exception as e:
            logger.error(f"SELECT_JD screening failed: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())

    return {
        "ok": True,
        "selected_jd_id": candidate.selected_jd_id,
        "jd": {
            "id": selected_jd.id,
            "title": selected_jd.title,
            "qualify_score": float(selected_jd.qualify_score if selected_jd.qualify_score is not None else 65.0),
            "total_questions": int(selected_jd.total_questions if selected_jd.total_questions is not None else 8),
        },
        "result": result_data,
    }


@router.get("/candidate/skill-match/{job_id}")
def candidate_skill_match(
    job_id: int,
    current_user: SessionUser = Depends(require_role("candidate")),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    candidate = get_candidate_or_404(db, current_user.user_id)
    if not candidate.resume_path:
        raise HTTPException(status_code=400, detail="Please upload resume first")

    job = db.query(JobDescription).filter(JobDescription.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    resume_text = (candidate.resume_text or "").strip()
    if not resume_text:
        raise HTTPException(status_code=400, detail="Resume text is not available. Please re-upload your resume.")
    skill_match = compute_resume_skill_match(
        resume_text,
        (job.skill_scores or {}).keys(),
        job.skill_scores
    )
    return {"ok": True, "job_id": job.id, **skill_match}


@router.post("/candidate/upload-resume")
def upload_resume(
    resume: UploadFile = File(...),
    job_id: int | None = Form(None),
    current_user: SessionUser = Depends(require_role("candidate")),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    logger.info(f"UPLOAD_RESUME_START candidate_id={current_user.user_id} filename={resume.filename}")
    candidate = get_candidate_or_404(db, current_user.user_id)
    profile_changed = ensure_candidate_profile(candidate, db)
    safe_filename = Path(resume.filename or "resume").name
    if not safe_filename:
        raise HTTPException(status_code=400, detail="Resume filename is invalid")

    allowed_extensions = {".pdf", ".docx", ".doc", ".txt", ".rtf"}
    file_ext = Path(safe_filename).suffix.lower()
    if file_ext not in allowed_extensions:
        raise HTTPException(status_code=400, detail=f"Unsupported file type '{file_ext}'. Allowed: {', '.join(sorted(allowed_extensions))}")

    resume.file.seek(0, 2)
    file_size = resume.file.tell()
    resume.file.seek(0)
    max_size_bytes = config.MAX_UPLOAD_SIZE_MB * 1_000_000
    if file_size > max_size_bytes:
        raise HTTPException(status_code=400, detail=f"Resume file exceeds {config.MAX_UPLOAD_SIZE_MB}MB limit")

    logger.info(f"UPLOAD_RESUME saving file for candidate_id={candidate.id}")
    resume_path = UPLOAD_DIR / f"resume_{candidate.id}_{uuid.uuid4().hex}_{safe_filename}"
    logger.info(f"UPLOAD_RESUME filepath={resume_path}")
    try:
        with resume_path.open("wb") as buffer:
            shutil.copyfileobj(resume.file, buffer)
        logger.info(f"UPLOAD_RESUME file saved successfully")
    except Exception as e:
        logger.error(f"UPLOAD_RESUME file save FAILED: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")

    candidate.resume_path = str(resume_path)
    if profile_changed:
        db.add(candidate)
    db.commit()
    db.refresh(candidate)
    logger.info(f"UPLOAD_RESUME resume_path saved to DB: {candidate.resume_path}")

    selected_jd_id = job_id or candidate.selected_jd_id
    if not selected_jd_id:
        raise HTTPException(status_code=400, detail="Select a JD before uploading resume")

    selected_jd = _selected_jd_or_404(db, selected_jd_id)
    candidate.selected_jd_id = selected_jd.id
    db.commit()
    db.refresh(candidate)

    logger.info(f"UPLOAD_RESUME calling evaluate_resume_for_job")
    try:
        score, explanation, _ = evaluate_resume_for_job(candidate, selected_jd)
        logger.info(f"UPLOAD_RESUME evaluation done, score={score}")
    except Exception as e:
        logger.error(f"UPLOAD_RESUME evaluation FAILED: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Resume evaluation failed: {str(e)}")
    
    resume_text = (candidate.resume_text or "").strip()
    logger.info(
        "resume_upload_extracted candidate_id=%s file_path=%s text_len=%d stored_in_db=%s",
        candidate.id,
        candidate.resume_path,
        len(resume_text),
        bool(resume_text),
    )
    if not resume_text:
        raise HTTPException(status_code=400, detail="Resume text could not be extracted. Please upload a valid PDF, DOCX, or TXT file.")
    if not selected_jd:
        db.commit()
        return {
            "ok": True,
            "message": "Resume uploaded. No job description available yet.",
            "uploaded_resume": safe_filename,
            "result": None,
            "available_jobs": list_available_jobs(db),
            "available_jds": list_active_jds(db),
            "selected_job_id": None,
            "selected_jd_id": None,
        }

    result = upsert_result(
        db,
        candidate.id,
        selected_jd.id,
        score,
        explanation,
        cutoff_score=float(selected_jd.qualify_score if selected_jd.qualify_score is not None else 65.0),
        job=selected_jd,
    )

    questions = _generate_result_question_bank(result=result, resume_text=resume_text, job=selected_jd)
    db.commit()
    db.refresh(result)

    dashboard_url = f"{config.FRONTEND_URL.rstrip('/')}/#/login?next=%2Fcandidate%2Fschedule" if result.shortlisted else f"{config.FRONTEND_URL.rstrip('/')}/#/login"
    try:
        feedback_items = []
        if explanation:
            matched = explanation.get("matched_skills", [])
            missing = explanation.get("missing_skills", [])
            if missing:
                feedback_items.append(f"Consider improving these skills: {', '.join(missing[:5])}")
            if explanation.get("final_resume_score"):
                score_val = float(explanation.get("final_resume_score", 0))
                if score_val < float(selected_jd.qualify_score):
                    feedback_items.append(f"Resume score ({int(score_val)}%) below required cutoff ({int(selected_jd.qualify_score)}%)")
        
        result.eligibility_feedback = "\n".join(feedback_items) if feedback_items else "Your profile did not meet the current requirements"
        db.commit()
        
        send_eligibility_email(
            to_email=candidate.email,
            candidate_name=candidate.name or "Candidate",
            role_title=selected_jd.title or "the position",
            is_eligible=bool(result.shortlisted),
            feedback=feedback_items,
            dashboard_url=dashboard_url
        )
    except Exception as e:
        logger.warning(f"Failed to send eligibility email: {e}")

    return {
        "ok": True,
        "message": "Resume uploaded and scoring completed.",
        "uploaded_resume": safe_filename,
        "candidate": {
            "id": candidate.id,
            "candidate_uid": candidate.candidate_uid,
            "name": candidate.name,
            "email": candidate.email,
            "gender": candidate.gender,
            "resume_path": candidate.resume_path,
            "created_at": candidate.created_at,
        },
        "available_jobs": list_available_jobs(db),
        "available_jds": list_active_jds(db),
        "selected_job_id": selected_jd.id,
        "selected_jd_id": selected_jd.id,
        "result": serialize_result(result),
        "question_count": len(questions or []),
        "resume_advice": _resume_advice_payload(
            candidate=candidate,
            selected_jd=selected_jd,
            explanation=result.explanation if result else None,
        ),
    }


@router.post("/candidate/upload-resume-s3")
def upload_resume_s3(
    resume_url: str = Body(...),
    job_id: int | None = Body(None),
    current_user: SessionUser = Depends(require_role("candidate")),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    """Upload resume via S3 URL (frontend uploads to S3 directly)."""
    logger.info(f"UPLOAD_RESUME_S3_START candidate_id={current_user.user_id} url_len={len(resume_url)}")

    if not resume_url or len(resume_url) > 500:
        logger.error(f"UPLOAD_RESUME_S3 invalid url length: {len(resume_url)}, content preview: {resume_url[:200]}")
        raise HTTPException(status_code=400, detail="Invalid resume URL. Please re-upload your resume file.")
    candidate = get_candidate_or_404(db, current_user.user_id)
    profile_changed = ensure_candidate_profile(candidate, db)

    candidate.resume_path = resume_url
    if profile_changed:
        db.add(candidate)
    db.commit()
    db.refresh(candidate)

    selected_jd_id = job_id or candidate.selected_jd_id
    if not selected_jd_id:
        raise HTTPException(status_code=400, detail="Select a JD before uploading resume")

    selected_jd = _selected_jd_or_404(db, selected_jd_id)
    candidate.selected_jd_id = selected_jd.id
    db.commit()
    db.refresh(candidate)

    try:
        if not resume_url.startswith(("http://", "https://")):
            logger.error(f"UPLOAD_RESUME_S3 invalid URL format: {resume_url[:100]}")
            raise HTTPException(status_code=400, detail="Invalid URL format. Must start with http:// or https://")

        response = requests.get(resume_url, timeout=30)
        response.raise_for_status()

        content_type = response.headers.get("content-type", "")
        if "pdf" in content_type:
            file_ext = ".pdf"
        elif "word" in content_type or "document" in content_type:
            file_ext = ".docx"
        else:
            file_ext = Path(resume_url).suffix.lower() or ".pdf"

        temp_path = UPLOAD_DIR / f"resume_{candidate.id}_{uuid.uuid4().hex}{file_ext}"
        with temp_path.open("wb") as f:
            f.write(response.content)

        resume_text = extract_text_from_file(temp_path)
        candidate.resume_text = resume_text
        temp_path.unlink(missing_ok=True)
        logger.info(f"UPLOAD_RESUME_S3 text extracted len={len(resume_text)}")
    except requests.exceptions.RequestException as e:
        logger.error(f"UPLOAD_RESUME_S3 failed to download from S3: {e}")
        raise HTTPException(status_code=400, detail=f"Could not download resume from S3: {str(e)}")
    except Exception as e:
        logger.warning(f"UPLOAD_RESUME_S3 text extraction failed: {e}")

    if not candidate.resume_text:
        raise HTTPException(status_code=400, detail="Resume text could not be extracted. Please upload a valid PDF, DOCX, or TXT file.")

    try:
        score, explanation, _ = evaluate_resume_for_job(candidate, selected_jd)
        logger.info(f"UPLOAD_RESUME_S3 evaluation done, score={score}")
    except Exception as e:
        logger.error(f"UPLOAD_RESUME_S3 evaluation FAILED: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Resume evaluation failed: {str(e)}")

    result = upsert_result(
        db,
        candidate.id,
        selected_jd.id,
        score,
        explanation,
        cutoff_score=float(selected_jd.qualify_score if selected_jd.qualify_score is not None else 65.0),
        job=selected_jd,
    )

    questions = _generate_result_question_bank(result=result, resume_text=candidate.resume_text or "", job=selected_jd)
    db.commit()
    db.refresh(result)

    dashboard_url = f"{config.FRONTEND_URL.rstrip('/')}/#/login?next=%2Fcandidate%2Fschedule" if result.shortlisted else f"{config.FRONTEND_URL.rstrip('/')}/#/login"
    try:
        feedback_items = []
        if explanation:
            matched = explanation.get("matched_skills", [])
            missing = explanation.get("missing_skills", [])
            if missing:
                feedback_items.append(f"Consider improving these skills: {', '.join(missing[:5])}")
            if explanation.get("final_resume_score"):
                score_val = float(explanation.get("final_resume_score", 0))
                if score_val < float(selected_jd.qualify_score):
                    feedback_items.append(f"Resume score ({int(score_val)}%) below required cutoff ({int(selected_jd.qualify_score)}%)")
        
        result.eligibility_feedback = "\n".join(feedback_items) if feedback_items else "Your profile did not meet the current requirements"
        db.commit()
        
        send_eligibility_email(
            to_email=candidate.email,
            candidate_name=candidate.name or "Candidate",
            role_title=selected_jd.title or "the position",
            is_eligible=bool(result.shortlisted),
            feedback=feedback_items,
            dashboard_url=dashboard_url
        )
    except Exception as e:
        logger.warning(f"Failed to send eligibility email: {e}")

    return {
        "ok": True,
        "message": "Resume uploaded and scoring completed.",
        "uploaded_resume": Path(resume_url).name,
        "candidate": {
            "id": candidate.id,
            "candidate_uid": candidate.candidate_uid,
            "name": candidate.name,
            "email": candidate.email,
            "gender": candidate.gender,
            "resume_path": candidate.resume_path,
            "created_at": candidate.created_at,
        },
        "available_jobs": list_available_jobs(db),
        "available_jds": list_active_jds(db),
        "selected_job_id": selected_jd.id,
        "selected_jd_id": selected_jd.id,
        "result": serialize_result(result),
        "question_count": len(questions or []),
        "resume_advice": _resume_advice_payload(
            candidate=candidate,
            selected_jd=selected_jd,
            explanation=result.explanation if result else None,
        ),
    }


@router.post("/candidate/select-interview-date")
def select_interview_date(
    payload: ScheduleInterviewBody,
    current_user: SessionUser = Depends(require_role("candidate")),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    if not (payload.interview_date or "").strip():
        raise HTTPException(status_code=400, detail="Interview date is required")

    result = (
        db.query(Result)
        .filter(Result.id == payload.result_id, Result.candidate_id == current_user.user_id)
        .first()
    )
    if not result:
        raise HTTPException(status_code=404, detail="Result not found")
    if not result.shortlisted:
        raise HTTPException(status_code=400, detail="Interview can be scheduled only for shortlisted result")

    is_reschedule = bool(result.interview_date)

    date_raw = payload.interview_date.strip()
    time_raw = payload.interview_time.strip() if payload.interview_time else ""

    try:
        interview_dt_utc = parse_interview_datetime_utc(date_raw, time_raw or None)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid interview date/time: {exc}")

    if "T" in date_raw and not time_raw:
        split_date, split_time = date_raw.split("T", 1)
        result.interview_date = split_date.strip()
        result.interview_time = split_time.strip()[:5]
    else:
        result.interview_date = date_raw
        if time_raw:
            result.interview_time = time_raw[:5]

    result.interview_datetime = interview_dt_utc
    result.interview_token = secrets.token_urlsafe(24)
    result.interview_link = interview_entry_url(result.id, result.interview_token)
    
    if is_reschedule:
        result.interview_rescheduled_count = (result.interview_rescheduled_count or 0) + 1

    # If a stale active session exists, it can bypass fresh schedule-window checks.
    # Mark it abandoned whenever candidate sets a new interview datetime.
    stale_active_sessions = (
        db.query(InterviewSession)
        .filter(
            InterviewSession.result_id == result.id,
            InterviewSession.candidate_id == current_user.user_id,
            InterviewSession.status == "in_progress",
        )
        .all()
    )
    for session in stale_active_sessions:
        session.status = "abandoned"
    
    result.reminder_24h_sent = False
    result.reminder_1h_sent = False
    db.commit()

    candidate = get_candidate_or_404(db, current_user.user_id)
    job = db.query(JobDescription).filter(JobDescription.id == result.job_id).first()
    role_title = job.title if job else "the position"
    
    email_sent = True
    message = "Interview scheduled. Confirmation sent to your email."
    try:
        send_interview_confirmation_email(
            to_email=candidate.email,
            candidate_name=candidate.name or "Candidate",
            role_title=role_title,
            interview_datetime=result.interview_datetime or result.interview_date,
            interview_link=result.interview_link,
            is_reschedule=is_reschedule
        )
    except Exception as e:
        logger.warning(f"Failed to send interview confirmation email: {e}")
        email_sent = False
        message = "Interview scheduled, but email delivery failed."

    return {
        "ok": True,
        "email_sent": email_sent,
        "message": message,
        "result": serialize_result(result),
    }


@router.get("/candidate/practice-kit")
def candidate_practice_kit(
    job_id: int | None = None,
    current_user: SessionUser = Depends(require_role("candidate")),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    candidate = get_candidate_or_404(db, current_user.user_id)
    if not candidate.resume_path:
        raise HTTPException(status_code=400, detail="Upload your resume before starting practice mode")

    selected_jd_id = job_id or candidate.selected_jd_id
    if not selected_jd_id:
        raise HTTPException(status_code=400, detail="Select a JD before starting practice mode")

    selected_jd = _selected_jd_or_404(db, selected_jd_id)
    resume_text = (candidate.resume_text or "").strip()
    if not resume_text:
        raise HTTPException(status_code=400, detail="Resume text is not available. Please re-upload your resume.")

    practice = build_practice_kit(
        resume_text=resume_text,
        jd_title=selected_jd.title,
        jd_skill_scores=selected_jd.weights_json or {},
        question_count=int(selected_jd.total_questions if selected_jd.total_questions is not None else 6),
    )
    score, explanation, _ = evaluate_resume_for_job(candidate, selected_jd)
    advice = build_resume_advice(
        resume_text=resume_text,
        jd_skill_scores=selected_jd.weights_json or {},
        explanation=explanation,
        candidate_name=getattr(candidate, 'name', None) or None,
    )

    return {
        "ok": True,
        "jd": {
            "id": selected_jd.id,
            "title": selected_jd.title,
            "qualify_score": float(selected_jd.qualify_score if selected_jd.qualify_score is not None else 65.0),
            "total_questions": int(selected_jd.total_questions if selected_jd.total_questions is not None else 8),
        },
        "practice": practice,
        "resume_advice": advice,
        "score_preview": score,
    }


@router.post("/candidate/regenerate-questions")
def regenerate_questions(
    payload: dict,
    current_user: SessionUser = Depends(require_role("candidate")),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    """Regenerate the question bank for a result."""
    result_id = payload.get("result_id")
    if not result_id:
        raise HTTPException(status_code=400, detail="result_id is required")

    result = db.query(Result).filter(Result.id == result_id, Result.candidate_id == current_user.user_id).first()
    if not result:
        raise HTTPException(status_code=404, detail="Result not found")

    selected_jd = db.query(JobDescription).filter(JobDescription.id == result.job_id).first()
    if not selected_jd:
        raise HTTPException(status_code=404, detail="Job not found")

    from services.question_generation import build_question_bundle

    candidate = db.query(Candidate).filter(Candidate.id == current_user.user_id).first()
    project_ratio = float(selected_jd.project_question_ratio) if selected_jd and selected_jd.project_question_ratio is not None else 0.8
    bundle = build_question_bundle(
        resume_text=candidate.resume_text or "",
        jd_text=selected_jd.jd_text or "",
        jd_dict=selected_jd.jd_dict_json or {},
        job_title=selected_jd.title or "",
        project_ratio=project_ratio,
        question_count=int(selected_jd.question_count if selected_jd.question_count is not None else 8),
    )
    questions = bundle.get("questions") or []
    result.interview_questions = questions
    db.commit()

    return {"ok": True, "question_count": len(questions)}
