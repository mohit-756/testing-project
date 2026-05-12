"""HR-facing JD management, candidate management, and interview scoring routes."""

from __future__ import annotations
from typing import Any


import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from routes.auth import get_current_user
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from sqlalchemy.orm import Session, joinedload

from ai_engine.phase1.scoring import compute_interview_scoring, compute_resume_skill_match
from ai_engine.phase1.matching import extract_skills_from_jd, extract_text_from_file
from database import get_db
from services.llm.client import extract_jd_requirements, extract_skills as llm_extract_skills
from models import Candidate, InterviewSession, JobDescription, Result, ApplicationStageHistory
from routes.common import (
    UPLOAD_DIR,
    _latest_interview_session,
    ensure_candidate_profile,
    evaluate_resume_for_job,
    safe_delete_upload,
    serialize_result,
    upsert_result,
)
from routes.dependencies import SessionUser, require_role
from routes.schemas import HrJDCreateBody, HrJDUpdateBody, InterviewScoreBody, SkillWeightsBody, StageUpdateBody, CandidateCompareBody, CandidateAssignJDBody, HrCandidateNotesBody
from services.hr_dashboard import build_hr_dashboard_analytics
from services.pipeline import normalize_stage, record_stage_change, stage_payload
from services.local_exports import create_local_backup_archive
from services.resume_advice import build_resume_advice

router = APIRouter(dependencies=[Depends(get_current_user)])
jd_router = APIRouter(prefix="/hr/jds", tags=["hr-jds"])


@router.get("/hr/resume/{candidate_uid}")
def get_resume(candidate_uid: str, db: Session = Depends(get_db)):
    """Serve the resume file for a candidate."""
    candidate = db.query(Candidate).filter(Candidate.candidate_uid == candidate_uid).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    if not candidate.resume_path:
        raise HTTPException(status_code=404, detail="No resume has been uploaded for this candidate")
    
    from core.config import config
    
    base_upload_dir = Path(str(config.UPLOAD_DIR)).resolve()
    path = Path(candidate.resume_path)
    
    if path.exists():
        pass
    elif not path.is_absolute():
        filename = path.name.replace("\\", "/").split("/")[-1]
        path = base_upload_dir / filename
    
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Resume file not found on server. Path: {candidate.resume_path}")
    
    media_type = "application/pdf"
    if path.suffix.lower() == ".docx":
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    elif path.suffix.lower() == ".doc":
        media_type = "application/msword"
    elif path.suffix.lower() == ".txt":
        media_type = "text/plain"
    
    return FileResponse(path, media_type=media_type)
# Keep FastAPI path params in plain `{jd_id}` form here. Using Starlette-style
# converter syntax (`{jd_id:int}`) can produce route resolution mismatches across
# versions and was breaking the frontend's /api/hr/jds/:id and toggle-active calls.

PAGE_SIZE = 10


# Alias to shared helper — avoids duplicating _latest_interview_session logic.
_latest_session = _latest_interview_session


# 1) What this does: converts result/session data into a stable status key.
# 2) Why needed: the UI needs a single normalized status value for labels and filtering.
# 3) How it works: checks Result.stage first (source of truth), then session state fallbacks.
def _status_key(result: Result | None, latest_session: InterviewSession | None) -> str:
    if not result:
        return "applied"
    
    stage = normalize_stage(result.stage)
    
    # Priority 1: If Result.stage is already interview_completed, return it immediately
    if stage == "interview_completed":
        return stage
    
    if latest_session:
        session_status = (latest_session.status or "").strip().lower()
        if session_status in {"selected", "rejected"}:
            return session_status
        if latest_session.ended_at or session_status == "completed":
            return "interview_completed"
    
    # Priority 2: Return stage from Result (could be interview_scheduled, shortlisted, etc.)
    # Only fall back to interview_scheduled if stage is still the default scheduled state
    if stage == "interview_scheduled" and result.interview_date:
        return stage
    
    return stage


# 1) What this does: maps the status key to the UI-ready label and badge tone.
# 2) Why needed: keeps status presentation consistent across pages.
# 3) How it works: reuses the shared ATS stage metadata.
def _status_payload(result: Result | None, latest_session: InterviewSession | None) -> dict[str, str]:
    return stage_payload(_status_key(result, latest_session))


# 1) What this does: builds the candidate summary payload used by the HR list page.
# 2) Why needed: keeps row shaping in one place.
# 3) How it works: combines candidate identity, current result data, and derived status.
def _serialize_candidate_summary(candidate: Candidate, result: Result | None) -> dict[str, object]:
    latest_session = _latest_session(result)
    status = _status_payload(result, latest_session)
    return {
        "id": candidate.id,
        "candidate_uid": candidate.candidate_uid,
        "name": candidate.name,
        "email": candidate.email,
        "resume_path": candidate.resume_path,
        "created_at": candidate.created_at,
        "status": status,
        "stage": status,
        "score": float(result.score) if result and result.score is not None else None,
        "final_score": float(result.final_score) if result and result.final_score is not None else None,
        "recommendation": result.recommendation if result else None,
        "score_breakdown": result.score_breakdown_json if result else {},
        "result_id": result.id if result else None,
        "application_id": result.application_id if result else None,
        "job": {
            "id": result.job.id if result and result.job else None,
            "title": (result.job.jd_title or Path(result.job.jd_text).name) if result and result.job else None,
        },
        "assigned_jd": {
            "id": candidate.selected_jd_id,
            "title": candidate.selected_jd.title if candidate.selected_jd else (candidate.selected_jd.jd_title if candidate.selected_jd else None),
        },
        "interview_date": result.interview_date if result else None,
        "hr_notes": result.hr_notes if result else None,
    }


# 1) What this does: scopes candidate results to the current HR's jobs.
# 2) Why needed: prevents cross-company access and keeps downstream queries consistent.
# 3) How it works: joins results to jobs and preloads related data once.
def _candidate_result_scope(db: Session):
    return (
        db.query(Result)
        .options(
            joinedload(Result.candidate).joinedload(Candidate.selected_jd),
            joinedload(Result.job),
            joinedload(Result.sessions),
        )
    )


def _candidate_summaries(db: Session) -> list[dict[str, object]]:
    scoped_results = _candidate_result_scope(db).order_by(Result.id.desc()).all()
    summaries_by_candidate: dict[int, dict[str, object]] = {}
    application_counts: dict[int, int] = {}
    jd_ids_per_candidate: dict[int, set] = {}
    changed = False

    for result in scoped_results:
        candidate = result.candidate
        if not candidate:
            continue
        changed = ensure_candidate_profile(candidate, db) or changed
        cid = candidate.id
        application_counts[cid] = application_counts.get(cid, 0) + 1
        if result.job_id:
            if cid not in jd_ids_per_candidate:
                jd_ids_per_candidate[cid] = set()
            jd_ids_per_candidate[cid].add(result.job_id)
        if cid in summaries_by_candidate:
            continue
        summaries_by_candidate[cid] = _serialize_candidate_summary(candidate, result)

    if changed:
        db.commit()
        for summary in summaries_by_candidate.values():
            candidate = db.query(Candidate).filter(Candidate.id == summary["id"]).first()
            if candidate:
                summary["candidate_uid"] = candidate.candidate_uid
                summary["created_at"] = candidate.created_at

    result_list = list(summaries_by_candidate.values())
    for summary in result_list:
        cid = summary["id"]
        summary["application_count"] = application_counts.get(cid, 1)
        summary["jd_ids_applied"] = list(jd_ids_per_candidate.get(cid, set()))
    return result_list


# 1) What this does: checks whether one candidate summary matches the search text.
# 2) Why needed: powers HR search without changing existing data models.
# 3) How it works: compares the lowered search text with candidate id, name, email, and status text.
def _matches_query(candidate_summary: dict[str, object], search_text: str) -> bool:
    if not search_text:
        return True

    status = candidate_summary.get("status") or {}
    haystacks = [
        str(candidate_summary.get("candidate_uid") or "").lower(),
        str(candidate_summary.get("name") or "").lower(),
        str(candidate_summary.get("email") or "").lower(),
        str(status.get("label") or "").lower(),
        str(status.get("key") or "").lower(),
    ]
    return any(search_text in value for value in haystacks)


# 1) What this does: sorts the candidate list using the selected mode.
# 2) Why needed: the HR list supports newest-first and score-desc ordering.
# 3) How it works: sorts in place using a stable tuple key.
def _sort_candidate_summaries(candidates: list[dict[str, object]], sort: str) -> list[dict[str, object]]:
    def score_value(item: dict[str, object]) -> float:
        if item.get("final_score") is not None:
            return float(item["final_score"])
        if item.get("score") is not None:
            return float(item["score"])
        return -1.0

    if sort in {"score_desc", "highest_score"}:
        candidates.sort(key=lambda item: (score_value(item), item.get("created_at") or datetime.min), reverse=True)
        return candidates
    if sort == "lowest_score":
        candidates.sort(key=lambda item: (9999 if score_value(item) < 0 else score_value(item), item.get("created_at") or datetime.min))
        return candidates

    candidates.sort(
        key=lambda item: (
            item.get("created_at") or datetime.min,
            int(item.get("id") or 0),
        ),
        reverse=True,
    )
    return candidates


def _normalize_weight_map(raw_map: dict[str, int] | None) -> dict[str, int]:
    normalized: dict[str, int] = {}
    for key, value in (raw_map or {}).items():
        skill = str(key or "").strip().lower()
        if not skill:
            continue
        try:
            normalized[skill] = int(value)
        except Exception:
            normalized[skill] = 0
    return normalized


# NOTE: Keep this serializer aligned with the exact field names expected by
# interview-frontend/src/pages/HRJdManagementPage.jsx and related HR views.
def _serialize_jd(jd: JobDescription) -> dict[str, object]:
    return {
        "id": jd.id,
        "title": jd.title or jd.jd_title or Path(jd.jd_text or "").name or "Untitled Role",
        "jd_text": jd.jd_text,
        "weights_json": jd.weights_json or jd.skill_scores or {},
        "qualify_score": float(jd.qualify_score if jd.qualify_score is not None else 65.0),
        "education_requirement": jd.education_requirement,
        "experience_requirement": int(jd.experience_requirement if jd.experience_requirement is not None else 0),
        "min_academic_percent": float(jd.min_academic_percent if jd.min_academic_percent is not None else 0.0),
        "total_questions": int(jd.total_questions if jd.total_questions is not None else 8),
        "project_question_ratio": float(jd.project_question_ratio if jd.project_question_ratio is not None else 0.8),
        "is_active": bool(jd.is_active if jd.is_active is not None else True),
        "created_at": jd.created_at,
        "score_weights_json": jd.score_weights_json,
    }


def _get_hr_jd_or_404(db: Session, jd_id: int) -> JobDescription:
    jd = db.query(JobDescription).filter(JobDescription.id == jd_id).first()
    if not jd:
        raise HTTPException(status_code=404, detail="JD not found")
    return jd


# 1) What this does: creates one JD config row for HR and syncs scoring table.
# 2) Why needed: supports N number of JDs with per-JD scoring config.
# 3) How it works: stores canonical config in job_descriptions and mirrors to legacy jobs by same id.
@jd_router.post("")
def hr_create_jd(
    payload: HrJDCreateBody,
    current_user: SessionUser = Depends(require_role("hr")),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    jd = JobDescription(
        title=payload.title.strip(),
        jd_title=payload.title.strip(),
        jd_text=payload.jd_text.strip(),
        weights_json=_normalize_weight_map(payload.weights_json),
        skill_scores=_normalize_weight_map(payload.weights_json),
        qualify_score=float(payload.qualify_score),
        cutoff_score=float(payload.qualify_score),
        education_requirement=(payload.education_requirement.strip() if payload.education_requirement else None),
        experience_requirement=int(payload.experience_requirement if payload.experience_requirement is not None else 0),
        min_academic_percent=float(payload.min_academic_percent),
        total_questions=int(payload.total_questions),
        question_count=int(payload.total_questions),
        project_question_ratio=float(payload.project_question_ratio),
        is_active=True,
        score_weights_json=payload.score_weights_json,
        total_duration_minutes=payload.total_duration_minutes or 30,
    )
    db.add(jd)
    db.commit()
    db.refresh(jd)
    return {"ok": True, "jd": _serialize_jd(jd)}


@jd_router.get("")
def hr_list_jds(
    current_user: SessionUser = Depends(require_role("hr")),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    jds = db.query(JobDescription).order_by(JobDescription.id.desc()).all()
    return {"ok": True, "jds": [_serialize_jd(row) for row in jds]}


# 1) What this does: fetches details for one HR-owned JD config.
# 2) Why needed: allows per-JD view/edit flows.
# 3) How it works: verifies HR ownership via legacy jobs table.
@jd_router.get("/{jd_id}")
def hr_get_jd(
    jd_id: int,
    current_user: SessionUser = Depends(require_role("hr")),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    jd = _get_hr_jd_or_404(db, jd_id)
    return {"ok": True, "jd": _serialize_jd(jd)}


# 1) What this does: updates one HR-owned JD config and syncs scoring table.
# 2) Why needed: HR can tune qualify score, weights, and question count without re-uploading.
# 3) How it works: applies partial fields to job_descriptions and mirrors into jobs.
@jd_router.put("/{jd_id}")
def hr_update_jd(
    jd_id: int,
    payload: HrJDUpdateBody,
    current_user: SessionUser = Depends(require_role("hr")),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    jd = _get_hr_jd_or_404(db, jd_id)

    if payload.title is not None:
        jd.title = payload.title.strip()
        jd.jd_title = jd.title
    if payload.jd_text is not None:
        jd.jd_text = payload.jd_text.strip()
    if payload.jd_dict_json is not None:
        jd.jd_dict_json = payload.jd_dict_json
    if payload.weights_json is not None:
        jd.weights_json = _normalize_weight_map(payload.weights_json)
        jd.skill_scores = jd.weights_json
    if payload.qualify_score is not None:
        jd.qualify_score = float(payload.qualify_score)
        jd.cutoff_score = jd.qualify_score
    if payload.education_requirement is not None:
        jd.education_requirement = payload.education_requirement.strip() or None
    if payload.experience_requirement is not None:
        jd.experience_requirement = int(payload.experience_requirement)
    if payload.min_academic_percent is not None:
        jd.min_academic_percent = float(payload.min_academic_percent)
    if payload.total_questions is not None:
        jd.total_questions = int(payload.total_questions)
        jd.question_count = jd.total_questions
    if payload.project_question_ratio is not None:
        jd.project_question_ratio = float(payload.project_question_ratio)
    if payload.total_duration_minutes is not None:
        jd.total_duration_minutes = int(payload.total_duration_minutes)
    if payload.score_weights_json is not None:
        jd.score_weights_json = payload.score_weights_json

    db.commit()
    db.refresh(jd)
    return {"ok": True, "jd": _serialize_jd(jd)}


# NOTE: Backward-safe minimal toggle for demo readiness.
# HR keeps seeing all JDs, while candidate-facing lists only show active ones.
@jd_router.post("/{jd_id}/toggle-active")
def hr_toggle_jd_active(
    jd_id: int,
    current_user: SessionUser = Depends(require_role("hr")),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    jd = _get_hr_jd_or_404(db, jd_id)
    next_active = not bool(jd.is_active)
    jd.is_active = next_active
    db.commit()
    db.refresh(jd)
    return {"ok": True, "jd": _serialize_jd(jd)}


@jd_router.delete("/{jd_id}")
def hr_delete_jd(
    jd_id: int,
    current_user: SessionUser = Depends(require_role("hr")),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    jd = _get_hr_jd_or_404(db, jd_id)
    
    applications_count = db.query(Result).filter(Result.job_id == jd_id).count()
    if applications_count:
        raise HTTPException(status_code=400, detail="Cannot delete a JD with active applications")

    candidates_with_this_jd = db.query(Candidate).filter(Candidate.selected_jd_id == jd_id).all()
    for candidate in candidates_with_this_jd:
        candidate.selected_jd_id = None

    deleted_upload = False
    if jd.jd_text:
        deleted_upload = safe_delete_upload(jd.jd_text)

    db.delete(jd)
    db.commit()
    return {"ok": True, "jd_id": jd_id, "deleted_upload": deleted_upload}

# Register the JD subrouter after all JD handlers are defined.
router.include_router(jd_router)


# 1) What this does: returns the HR dashboard payload with jobs and shortlisted candidates.
# 2) Why needed: drives the main HR home page without extra round-trips.
# 3) How it works: loads jobs, picks the selected one, and returns derived summaries.
@router.get("/hr/dashboard")
def hr_dashboard(
    job_id: int | None = None,
    current_user: SessionUser = Depends(require_role("hr")),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    jobs = db.query(JobDescription).order_by(JobDescription.id.desc()).all()
    selected_job = None
    if job_id:
        selected_job = next((job for job in jobs if job.id == job_id), None)
    if not selected_job and jobs:
        selected_job = jobs[0]

    shortlisted_candidates: list[dict[str, object]] = []
    changed = False
    if selected_job:
        results = (
            db.query(Result)
            .options(
                joinedload(Result.candidate).joinedload(Candidate.selected_jd),
                joinedload(Result.job),
                joinedload(Result.sessions),
            )
            .filter(Result.job_id == selected_job.id, Result.shortlisted.is_(True))
            .order_by(Result.id.desc())
            .all()
        )
        for result in results:
            candidate = result.candidate
            if not candidate:
                continue
            changed = ensure_candidate_profile(candidate, db) or changed
            shortlisted_candidates.append(
                {
                    "candidate": {
                        "id": candidate.id,
                        "candidate_uid": candidate.candidate_uid,
                        "name": candidate.name,
                        "email": candidate.email,
                        "resume_path": candidate.resume_path,
                        "created_at": candidate.created_at,
                    },
                    "status": _status_payload(result, _latest_session(result)),
                    "result": serialize_result(result),
                }
            )
    if changed:
        db.commit()

    analytics = build_hr_dashboard_analytics(
        db,
        hr_id=None,
        selected_job_id=selected_job.id if selected_job else None,
    )
    jobs_payload = [
        {
            "id": job.id,
            "jd_title": job.jd_title or Path(job.jd_text).name,
            "jd_name": Path(job.jd_text).name,
            "jd_text": job.jd_text,
            "skill_scores": job.skill_scores or {},
            "gender_requirement": None,
            "education_requirement": job.education_requirement,
            "experience_requirement": job.experience_requirement,
            "cutoff_score": float(job.cutoff_score if job.cutoff_score is not None else 65.0),
            "question_count": int(job.question_count if job.question_count is not None else 8),
        }
        for job in jobs
    ]

    return {
        "ok": True,
        "selected_job_id": selected_job.id if selected_job else None,
        "jobs": jobs_payload,
        "latest_jd": (
            {
                "id": selected_job.id,
                "jd_title": selected_job.jd_title or Path(selected_job.jd_text).name,
                "jd_text": selected_job.jd_text,
                "skill_scores": selected_job.skill_scores or {},
                "gender_requirement": None,
                "education_requirement": selected_job.education_requirement,
                "experience_requirement": selected_job.experience_requirement,
                "cutoff_score": float(selected_job.cutoff_score if selected_job.cutoff_score is not None else 65.0),
                "question_count": int(selected_job.question_count if selected_job.question_count is not None else 8),
            }
            if selected_job
            else None
        ),
        "shortlisted_candidates": shortlisted_candidates,
        "analytics": analytics,
    }


# ── HR Dashboard Calendar ─────────────────────────────────────────────────────
@router.get("/hr/dashboard/calendar")
def hr_dashboard_calendar(
    month: int | None = None,
    year: int | None = None,
    current_user: SessionUser = Depends(require_role("hr")),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    from datetime import datetime, timedelta
    from sqlalchemy import and_
    
    if not month:
        month = datetime.now().month
    if not year:
        year = datetime.now().year
    
    start_date = datetime(year, month, 1)
    if month == 12:
        end_date = datetime(year + 1, 1, 1) - timedelta(days=1)
    else:
        end_date = datetime(year, month + 1, 1) - timedelta(days=1)
    
    results = (
        db.query(Result)
        .filter(
            Result.interview_datetime.isnot(None),
            Result.interview_datetime >= start_date,
            Result.interview_datetime <= end_date + timedelta(days=1),
        )
        .all()
    )
    
    date_map = {}
    for result in results:
        candidate = result.candidate
        job = result.job
        
        if not candidate or not job:
            continue
        
        date_key = result.interview_datetime.strftime("%Y-%m-%d")
        
        status = "scheduled"
        if result.shortlisted and result.interview_date:
            sessions = result.sessions or []
            completed = any((s.ended_at or s.status == "completed") for s in sessions)
            if completed:
                status = "completed"
            else:
                status = "scheduled"
        
        if date_key not in date_map:
            date_map[date_key] = {"completed": 0, "scheduled": 0, "new": 0, "candidates": []}
        
        if status == "completed":
            date_map[date_key]["completed"] += 1
        else:
            date_map[date_key]["scheduled"] += 1
        
        date_map[date_key]["candidates"].append({
            "result_id": result.id,
            "candidate_id": candidate.id,
            "candidate_uid": candidate.candidate_uid,
            "name": candidate.name,
            "job_title": job.jd_title or job.title or "JD",
            "status": status,
            "score": float(result.final_score or result.score or 0),
        })
    
    return {"ok": True, "dates": date_map}
# 2) Why needed: supports search, filter, sorting, and paging in one API.
# 3) How it works: builds summaries, filters them in memory, then slices the requested page.
@router.get("/hr/candidates")
def hr_candidates(
    q: str = "",
    stage: str = "all",
    status: str | None = None,
    sort: str = "newest",
    min_score: float | None = None,
    max_score: float | None = None,
    job_id: int | None = None,
    page: int = 1,
    current_user: SessionUser = Depends(require_role("hr")),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    search_text = (q or "").strip().lower()
    status_key = normalize_stage(stage if stage not in {None, ""} else status)
    if (stage or status or "all").strip().lower() == "all":
        status_key = "all"
    sort_key = (sort or "newest").strip().lower()
    if sort_key not in {"newest", "score_desc", "highest_score", "lowest_score"}:
        sort_key = "newest"
    page_number = max(1, int(page or 1))

    candidates = _candidate_summaries(db)
    if job_id:
        candidates = [item for item in candidates if int(item.get("job", {}).get("id") or 0) == int(job_id)]
    filtered = []
    for item in candidates:
        score_value = item.get("final_score") if item.get("final_score") is not None else item.get("score")
        if status_key not in {"", "all"} and item["status"]["key"] != status_key:
            continue
        if min_score is not None and (score_value is None or float(score_value) < float(min_score)):
            continue
        if max_score is not None and (score_value is None or float(score_value) > float(max_score)):
            continue
        if not _matches_query(item, search_text):
            continue
        filtered.append(item)
    _sort_candidate_summaries(filtered, sort_key)

    total_results = len(filtered)
    total_pages = max(1, (total_results + PAGE_SIZE - 1) // PAGE_SIZE) if total_results else 1
    if page_number > total_pages:
        page_number = total_pages
    for index, item in enumerate(filtered, start=1):
        item["rank"] = index
        item["recommended"] = index <= 3 and (float(item.get("final_score") or item.get("score") or 0) >= 65.0)

    start = (page_number - 1) * PAGE_SIZE
    end = start + PAGE_SIZE
    paged_candidates = filtered[start:end]

    return {
        "ok": True,
        "q": q,
        "stage": status_key,
        "status": status_key,
        "sort": sort_key,
        "page": page_number,
        "page_size": PAGE_SIZE,
        "total_pages": total_pages,
        "total_results": total_results,
        "results_found": len(paged_candidates),
        "has_prev": page_number > 1,
        "has_next": page_number < total_pages,
        "candidates": paged_candidates,
    }


# 1) What this does: returns the full HR candidate detail payload.
# 2) Why needed: powers the detail page for one candidate and their applications.
# 3) How it works: loads the candidate, verifies HR ownership via scoped results, and returns application history.
@router.get("/hr/candidates/ranked")
def hr_ranked_candidates(
    job_id: int | None = None,
    limit: int = 10,
    current_user: SessionUser = Depends(require_role("hr")),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    payload = hr_candidates(
        q="",
        stage="all",
        status=None,
        sort="highest_score",
        min_score=None,
        max_score=None,
        job_id=job_id,
        page=1,
        current_user=current_user,
        db=db,
    )
    ranked = list(payload.get("candidates") or [])[: max(1, min(50, int(limit)))]
    return {"ok": True, "candidates": ranked}


@router.get("/hr/applications")
def hr_all_applications(
    job_id: int | None = None,
    stage: str = "all",
    current_user: SessionUser = Depends(require_role("hr")),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    scoped_results = _candidate_result_scope(db).order_by(Result.id.desc()).all()

    applications = []
    for result in scoped_results:
        if job_id and result.job_id != job_id:
            continue
        candidate = result.candidate
        if not candidate:
            continue
        latest_session = _latest_session(result)
        status = _status_payload(result, latest_session)
        if stage not in {"", "all"} and status["key"] != stage:
            continue
        applications.append({
            "result_id": result.id,
            "application_id": result.application_id,
            "candidate": {
                "id": candidate.id,
                "candidate_uid": candidate.candidate_uid,
                "name": candidate.name,
                "email": candidate.email,
                "created_at": candidate.created_at,
            },
            "job": {
                "id": result.job.id if result.job else None,
                "title": (result.job.jd_title or Path(result.job.jd_text).name) if result.job else None,
            },
            "score": float(result.score) if result.score is not None else None,
            "final_score": float(result.final_score) if result.final_score is not None else None,
            "recommendation": result.recommendation,
            "score_breakdown": result.score_breakdown_json or {},
            "shortlisted": bool(result.shortlisted),
            "status": status,
            "stage": status,
            "interview_date": result.interview_date,
            "hr_decision": result.hr_decision,
            "hr_final_score": result.hr_final_score,
            "latest_session": {
                "id": latest_session.id,
                "status": latest_session.status,
                "started_at": latest_session.started_at,
                "ended_at": latest_session.ended_at,
            } if latest_session else None,
        })

    return {"ok": True, "applications": applications, "total": len(applications)}


@router.get("/hr/candidates/{candidate_uid}")
def hr_candidate_detail(
    candidate_uid: str,
    current_user: SessionUser = Depends(require_role("hr")),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    candidate = db.query(Candidate).filter(Candidate.candidate_uid == candidate_uid).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    if ensure_candidate_profile(candidate, db):
        db.commit()
        db.refresh(candidate)

    # Get all results for this candidate that belong to THIS HR's JDs
    results = (
        _candidate_result_scope(db)
        .filter(Result.candidate_id == candidate.id)
        .order_by(Result.id.desc())
        .all()
    )
    
    if not results:
        raise HTTPException(status_code=404, detail="Candidate not found for this HR")

    applications: list[dict[str, object]] = []
    for result in results:
        latest_session = _latest_session(result)
        stage_history_rows = (
            db.query(ApplicationStageHistory)
            .filter(ApplicationStageHistory.result_id == result.id)
            .order_by(ApplicationStageHistory.created_at.asc(), ApplicationStageHistory.id.asc())
            .all()
        )
        applications.append(
            {
                "result_id": result.id,
                "application_id": result.application_id,
                "job": {
                    "id": result.job.id if result.job else None,
                    "title": (result.job.jd_title or Path(result.job.jd_text).name) if result.job else None,
                },
                "score": float(result.score) if result.score is not None else None,
                "final_score": float(result.final_score) if result.final_score is not None else None,
                "recommendation": result.recommendation,
                "score_breakdown": result.score_breakdown_json or {},
                "shortlisted": bool(result.shortlisted),
                "status": _status_payload(result, latest_session),
                "stage": _status_payload(result, latest_session),
                "interview_date": result.interview_date,
                "interview_link": result.interview_link,
                "explanation": result.explanation or {},
                "stage_history": [
                    {
                        "id": row.id,
                        "stage": stage_payload(row.stage),
                        "note": row.note,
                        "changed_by_role": row.changed_by_role,
                        "changed_by_user_id": row.changed_by_user_id,
                        "created_at": row.created_at,
                    }
                    for row in stage_history_rows
                ],
                "latest_session": {
                    "id": latest_session.id,
                    "status": latest_session.status,
                    "started_at": latest_session.started_at,
                    "ended_at": latest_session.ended_at,
                    "evaluation_summary": latest_session.evaluation_summary_json or {},
                }
                if latest_session
                else None,
                "hr_notes": result.hr_notes,
            }
        )

    latest_application = applications[0]
    latest_result = results[0]
    latest_job = latest_result.job
    resume_text = extract_text_from_file(candidate.resume_path or "")
    # Keep frontend "Question Set" tab working, but source questions from the
    # real runtime bank stored on the latest Result (not manual HR generation).
    generated_questions = []
    try:
        from ai_engine.phase3.question_flow import normalize_result_questions

        generated_questions = [
            {
                "index": idx,
                "text": str(item.get("text") or "").strip(),
                "type": str(item.get("type") or "unknown"),
                "topic": str(item.get("topic") or "general"),
                "difficulty": str(item.get("difficulty") or "medium"),
            }
            for idx, item in enumerate(normalize_result_questions(latest_result.interview_questions), start=1)
            if str(item.get("text") or "").strip()
        ]
    except Exception:
        generated_questions = []
    skill_gap = None
    resume_advice = None
    if latest_job and resume_text.strip():
        skill_gap = compute_resume_skill_match(
            resume_text,
            (latest_job.skill_scores or {}).keys(),
            latest_job.skill_scores
        )
        resume_advice = build_resume_advice(
            resume_text=resume_text,
            jd_skill_scores=latest_job.skill_scores or {},
            explanation=latest_result.explanation or {},
            candidate_name=candidate.name,
        )
    return {
        "ok": True,
        "candidate": {
            "id": candidate.id,
            "candidate_uid": candidate.candidate_uid,
            "name": candidate.name,
            "email": candidate.email,
            "resume_path": candidate.resume_path,
            "resume_text": candidate.resume_text,
            "parsed_resume": candidate.parsed_resume_json or {},
            "created_at": candidate.created_at,
            "current_status": latest_application["status"],
            "current_stage": latest_application["stage"],
            "current_score": latest_application["score"],
            "final_score": latest_application.get("final_score"),
            "recommendation": latest_application.get("recommendation"),
            "linkedin_url": candidate.linkedin_url,
            "github_url": candidate.github_url,
            "assigned_jd": {
                "id": candidate.selected_jd_id,
                "title": candidate.selected_jd.title if candidate.selected_jd else (candidate.selected_jd.jd_title if candidate.selected_jd else None),
            },
            "hr_notes": latest_result.hr_notes,
        },
        "applications": applications,
        "generated_questions": generated_questions,
        "generated_questions_meta": {
            "source": "result.interview_questions",
            "result_id": latest_result.id,
            "job_id": latest_job.id if latest_job else None,
            "total_questions": len(generated_questions),
        },
        "skill_gap": (
            {
                "ok": True,
                "candidate_uid": candidate.candidate_uid,
                "job_id": latest_job.id,
                "job_title": latest_job.jd_title or Path(latest_job.jd_text).name,
                "matched_skills": list(skill_gap["matched_skills"]),
                "missing_skills": list(skill_gap["missing_skills"]),
                "match_percentage": float(skill_gap["matched_percentage"]),
                "matched_percentage": float(skill_gap["matched_percentage"]),
            }
            if latest_job and skill_gap
            else None
        ),
        "resume_advice": resume_advice,
    }


@router.post("/hr/candidates/batch-details")
def hr_candidates_batch_details(
    payload: dict,
    current_user: SessionUser = Depends(require_role("hr")),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    candidate_uids = payload.get("candidate_uids", [])
    if not candidate_uids or not isinstance(candidate_uids, list):
        raise HTTPException(status_code=400, detail="Invalid candidate_uids list")

    candidates = (
        db.query(Candidate)
        .filter(Candidate.candidate_uid.in_(candidate_uids))
        .all()
    )

    results_by_candidate = {}
    for candidate in candidates:
        results = (
            _candidate_result_scope(db)
            .filter(Result.candidate_id == candidate.id)
            .order_by(Result.id.desc())
            .all()
        )
        applications = []
        latest_result = results[0] if results else None
        score_breakdown = latest_result.score_breakdown_json or {} if latest_result else {}
        
        semantic_score = float(latest_result.score) if latest_result and latest_result.score is not None else None
        skill_match_score = float(latest_result.explanation.get("matched_percentage", 0)) if latest_result and latest_result.explanation else None
        interview_score = score_breakdown.get("interview_performance_score") or score_breakdown.get("interview_score")
        behavioral_score = latest_result.hr_behavioral_score if latest_result and latest_result.hr_behavioral_score is not None else score_breakdown.get("behavioral_score")
        communication_score = latest_result.hr_communication_score if latest_result and latest_result.hr_communication_score is not None else score_breakdown.get("communication_behavior_score")
        final_ai_score = latest_result.final_score if latest_result and latest_result.final_score is not None else score_breakdown.get("final_weighted_score")
        
        for result in results:
            latest_session = _latest_session(result)
            applications.append({
                "result_id": result.id,
                "application_id": result.application_id,
                "job": {
                    "id": result.job.id if result.job else None,
                    "title": (result.job.jd_title or Path(result.job.jd_text).name) if result.job else None,
                },
                "score": float(result.score) if result.score is not None else None,
                "final_score": float(result.final_score) if result.final_score is not None else None,
                "recommendation": result.recommendation,
                "score_breakdown": result.score_breakdown_json or {},
                "shortlisted": bool(result.shortlisted),
                "status": _status_payload(result, latest_session),
                "stage": _status_payload(result, latest_session),
                "interview_date": result.interview_date,
                "interview_link": result.interview_link,
                "explanation": result.explanation or {},
            })
        
        results_by_candidate[candidate.candidate_uid] = {
            "candidate": {
                "id": candidate.id,
                "candidate_uid": candidate.candidate_uid,
                "name": candidate.name,
                "email": candidate.email,
                "resume_path": candidate.resume_path,
                "semanticScore": semantic_score,
                "skillMatchScore": skill_match_score,
                "interviewScore": interview_score,
                "behavioralScore": behavioral_score,
                "communicationScore": communication_score,
                "finalAIScore": final_ai_score,
                "finalDecision": latest_result.hr_decision if latest_result else None,
            },
            "applications": applications,
        }

    return {"ok": True, "candidates": results_by_candidate}
def hr_assign_candidate_to_jd(
    candidate_uid: str,
    payload: CandidateAssignJDBody,
    current_user: SessionUser = Depends(require_role("hr")),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    candidate = db.query(Candidate).filter(Candidate.candidate_uid == candidate_uid).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    job = db.query(JobDescription).filter(JobDescription.id == payload.jd_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="JD not found")

    candidate.selected_jd_id = job.id
    changed = ensure_candidate_profile(candidate, db)
    result = None
    if candidate.resume_path:
        evaluation = evaluate_resume_for_job(candidate, job)
        result = upsert_result(db, candidate_id=candidate.id, job_id=job.id, score=evaluation["score"], explanation=evaluation["explanation"])
    if changed:
        db.commit()
    else:
        db.commit()
    return {
        "ok": True,
        "candidate_uid": candidate.candidate_uid,
        "jd_id": job.id,
        "result": serialize_result(result) if result else None,
    }


@router.post("/hr/results/{result_id}/notes")
def hr_update_candidate_notes(
    result_id: int,
    payload: HrCandidateNotesBody,
    current_user: SessionUser = Depends(require_role("hr")),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    result = (
        _candidate_result_scope(db)
        .filter(Result.id == result_id)
        .first()
    )
    if not result:
        raise HTTPException(status_code=404, detail="Application not found")

    result.hr_notes = (payload.notes or "").strip() or None
    db.commit()
    db.refresh(result)
    return {"ok": True, "result_id": result.id, "hr_notes": result.hr_notes or ""}


@router.post("/hr/results/{result_id}/stage")
def hr_update_candidate_stage(
    result_id: int,
    payload: StageUpdateBody,
    current_user: SessionUser = Depends(require_role("hr")),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    result = (
        _candidate_result_scope(db)
        .filter(Result.id == result_id)
        .first()
    )
    if not result:
        raise HTTPException(status_code=404, detail="Application not found")

    record_stage_change(
        db,
        result,
        stage=payload.stage,
        changed_by_role="hr",
        changed_by_user_id=current_user.user_id,
        note=payload.note,
    )
    stage_key = normalize_stage(payload.stage)
    result.shortlisted = stage_key in {"shortlisted", "interview_scheduled", "interview_completed", "selected"}
    if stage_key == "interview_scheduled" and not result.interview_date:
        result.interview_date = datetime.utcnow().replace(tzinfo=timezone.utc).isoformat(timespec="minutes").replace("+00:00", "Z")
    db.commit()
    db.refresh(result)
    return {"ok": True, "result_id": result.id, "stage": stage_payload(result.stage)}


@router.post("/hr/candidates/compare")
def hr_compare_candidates(
    payload: CandidateCompareBody,
    current_user: SessionUser = Depends(require_role("hr")),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    result_ids = [int(value) for value in payload.result_ids[:10]]
    results = (
        _candidate_result_scope(db)
        .filter(Result.id.in_(result_ids))
        .all()
    )
    comparisons = []
    for result in results:
        latest_session = _latest_session(result)
        comparisons.append(
            {
                "result_id": result.id,
                "application_id": result.application_id,
                "candidate": {
                    "id": result.candidate.id if result.candidate else None,
                    "name": result.candidate.name if result.candidate else None,
                    "candidate_uid": result.candidate.candidate_uid if result.candidate else None,
                },
                "job": {"id": result.job.id if result.job else None, "title": result.job.jd_title if result.job else None},
                "stage": stage_payload(result.stage),
                "score": result.score,
                "final_score": result.final_score,
                "recommendation": result.recommendation,
                "score_breakdown": result.score_breakdown_json or {},
                "parsed_resume": (result.candidate.parsed_resume_json or {}) if result.candidate else {},
                "interview_summary": (latest_session.evaluation_summary_json if latest_session else {}) or {},
                "assigned_jd": {
                    "id": result.candidate.selected_jd_id if result.candidate else None,
                    "title": result.candidate.selected_jd.title if result.candidate and result.candidate.selected_jd else None,
                },
                "hr_notes": result.hr_notes,
            }
        )
    comparisons.sort(key=lambda item: float(item.get("final_score") or item.get("score") or 0), reverse=True)
    return {"ok": True, "candidates": comparisons}


@router.get("/hr/candidates/{candidate_uid}/skill-gap")
def hr_candidate_skill_gap(
    candidate_uid: str,
    job_id: int | None = None,
    current_user: SessionUser = Depends(require_role("hr")),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    # 1) What this does: loads the target candidate row.
    # 2) Why needed: skill-gap analysis starts from the stored resume.
    # 3) How it works: looks up by the human-friendly candidate UID.
    candidate = db.query(Candidate).filter(Candidate.candidate_uid == candidate_uid).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    # 1) What this does: keeps legacy candidate records hydrated with modern metadata.
    # 2) Why needed: older rows may still be missing generated profile fields.
    # 3) How it works: updates candidate metadata only when needed.
    if ensure_candidate_profile(candidate, db):
        db.commit()
        db.refresh(candidate)

    # 1) What this does: resolves the target job for the skill-gap analysis.
    # 2) Why needed: the UI can pass a job id, but should also work with the latest application.
    # 3) How it works: uses the requested HR-owned job when present, otherwise falls back to the latest HR-owned application.
    target_job: JobDescription | None = None
    if job_id is not None:
        target_job = db.query(JobDescription).filter(JobDescription.id == job_id).first()
    else:
        latest_result = (
            _candidate_result_scope(db)
            .filter(Result.candidate_id == candidate.id)
            .order_by(Result.id.desc())
            .first()
        )
        if latest_result:
            target_job = latest_result.job

    if not target_job:
        raise HTTPException(status_code=404, detail="No matching job found for this candidate")

    # 1) What this does: reads the stored resume text.
    # 2) Why needed: the skill matcher works on plain text.
    # 3) How it works: uses the existing file extractor and stays null-safe for missing files.
    resume_text = extract_text_from_file(candidate.resume_path or "")

    # 1) What this does: calculates matched and missing skills.
    # 2) Why needed: this is the same local-only logic already used elsewhere in the app.
    # 3) How it works: reuses the existing compute_resume_skill_match helper with the JD skill keys.
    skill_gap = compute_resume_skill_match(
            resume_text,
            (target_job.skill_scores or {}).keys(),
            target_job.skill_scores
        )

    return {
        "ok": True,
        "candidate_uid": candidate.candidate_uid,
        "job_id": target_job.id,
        "job_title": target_job.jd_title or Path(target_job.jd_text).name,
        "matched_skills": list(skill_gap["matched_skills"]),
        "missing_skills": list(skill_gap["missing_skills"]),
        "match_percentage": float(skill_gap["matched_percentage"]),
        "matched_percentage": float(skill_gap["matched_percentage"]),
    }


# 1) What this does: deletes a candidate and related local data.
# 2) Why needed: HR needs a safe cleanup action from the candidate manager.
# 3) How it works: verifies ownership, deletes uploads, sessions, results, then the candidate row.
@router.post("/hr/candidates/{candidate_uid}/delete")
def hr_delete_candidate(
    candidate_uid: str,
    current_user: SessionUser = Depends(require_role("hr")),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    candidate = db.query(Candidate).filter(Candidate.candidate_uid == candidate_uid).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    try:
        safe_delete_upload(candidate.resume_path)
        db.delete(candidate)
        db.commit()
    except Exception as e:
        db.rollback()
        import logging
        logging.getLogger("uvicorn").error(f"[DELETE] Failed to delete candidate {candidate_uid}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error during deletion: {str(e)}")

    return JSONResponse(
        content={"ok": True, "message": "Candidate deleted", "candidate_uid": candidate_uid},
        media_type="application/json"
    )


# 1) What this does: uploads a JD file and extracts its initial skill list.
# 2) Why needed: HR can review skills before saving the JD permanently.
# 3) How it works: stores the upload locally and keeps a temporary session payload until confirmation.
@router.post("/hr/upload-jd")
def upload_jd(
    request: Request,
    jd_file: UploadFile = File(...),
    jd_title: str = Form(""),
    gender_requirement: str = Form(""),
    education_requirement: str = Form(""),
    experience_requirement: str = Form(""),
    cutoff_score: str = Form("65"),
    question_count: str = Form("8"),
    project_question_ratio: str = Form("0.8"),
    current_user: SessionUser = Depends(require_role("hr")),
) -> dict[str, object]:
    from core.config import config
    _ = gender_requirement
    safe_filename = Path(jd_file.filename or "jd").name
    allowed_extensions = {".pdf", ".docx", ".doc", ".txt", ".rtf"}
    file_ext = Path(safe_filename).suffix.lower()
    if file_ext not in allowed_extensions:
        raise HTTPException(status_code=400, detail=f"Unsupported file type '{file_ext}'. Allowed: {', '.join(sorted(allowed_extensions))}")

    jd_file.file.seek(0, 2)
    file_size = jd_file.file.tell()
    jd_file.file.seek(0)
    max_size_bytes = config.MAX_UPLOAD_SIZE_MB * 1_000_000
    if file_size > max_size_bytes:
        raise HTTPException(status_code=400, detail=f"JD file exceeds {config.MAX_UPLOAD_SIZE_MB}MB limit")

    try:
        years = int(experience_requirement) if experience_requirement else 0
    except ValueError:
        years = 0
    try:
        cutoff = float(cutoff_score) if cutoff_score else 65.0
    except ValueError:
        cutoff = 65.0
    cutoff = max(0.0, min(100.0, cutoff))
    try:
        questions = int(question_count) if question_count else 8
    except ValueError:
        questions = 8
    questions = max(3, min(20, questions))

    try:
        ratio = float(project_question_ratio) if project_question_ratio else 0.8
    except ValueError:
        ratio = 0.8
    ratio = max(0.0, min(1.0, ratio))

    safe_filename = Path(jd_file.filename or "job_description").name
    jd_path = UPLOAD_DIR / f"jd_{current_user.user_id}_{uuid.uuid4().hex}_{safe_filename}"

    # Write file first, fully closed before reading
    with jd_path.open("wb") as buffer:
        shutil.copyfileobj(jd_file.file, buffer)

    # Extract text and all requirements after file is closed
    jd_raw_text = extract_text_from_file(str(jd_path))
    requirements = extract_jd_requirements(jd_raw_text)
    ai_skills = requirements.get("skills") or {}
    if not ai_skills:
        extracted_skills = extract_skills_from_jd(str(jd_path))
        ai_skills = {skill: 5 for skill in extracted_skills}

    extracted_education = requirements.get("education_requirement") or education_requirement
    extracted_experience = requirements.get("experience_requirement") or years
    extracted_min_percent = requirements.get("min_academic_percent") or 0

    request.session["temp_jd"] = {
        "jd_title": jd_title.strip() if jd_title else None,
        "jd_path": str(jd_path),
        "jd_raw_text": jd_raw_text[:8000],
        "gender_requirement": None,
        "education_requirement": extracted_education,
        "experience_requirement": extracted_experience,
        "cutoff_score": cutoff,
        "question_count": questions,
        "project_question_ratio": ratio,
        "min_academic_percent": extracted_min_percent,
    }

    return {
        "ok": True,
        "jd_title": request.session["temp_jd"]["jd_title"],
        "jd_text": jd_raw_text[:500],
        "uploaded_jd": safe_filename,
        "ai_skills": ai_skills,
        "cutoff_score": cutoff,
        "question_count": questions,
        "project_question_ratio": ratio,
        "education_requirement": extracted_education,
        "experience_requirement": extracted_experience,
        "min_academic_percent": extracted_min_percent,
    }


@router.post("/hr/parse-jd-text")
def parse_jd_text(
    request: Request,
    jd_text: str = Form(...),
    jd_title: str = Form(""),
    current_user: SessionUser = Depends(require_role("hr")),
) -> dict[str, Any]:
    if not jd_text or not jd_text.strip():
        raise HTTPException(status_code=400, detail="JD text is required")

    requirements = extract_jd_requirements(jd_text)
    ai_skills = requirements.get("skills") or {}
    if not ai_skills:
        ai_skills = {"Add skills manually": 5}

    return {
        "ok": True,
        "jd_title": jd_title.strip() or None,
        "jd_text": jd_text[:500],
        "ai_skills": ai_skills,
        "education_requirement": requirements.get("education_requirement"),
        "experience_requirement": requirements.get("experience_requirement", 0),
        "min_academic_percent": requirements.get("min_academic_percent", 0),
    }


# 1) What this does: saves the uploaded JD and backfills scoring for current candidates.
# 2) Why needed: a confirmed JD becomes available for screening and interview setup.
# 3) How it works: persists the job, then recomputes resume scoring for candidates with resumes.
@router.post("/hr/confirm-jd")
def confirm_jd(
    payload: SkillWeightsBody,
    request: Request,
    current_user: SessionUser = Depends(require_role("hr")),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    temp_jd = request.session.get("temp_jd")
    if not temp_jd:
        raise HTTPException(status_code=400, detail="Please upload JD first")
    if not payload.skill_scores:
        raise HTTPException(status_code=400, detail="skill_scores cannot be empty")

    normalized_scores: dict[str, int] = {}
    for skill, weight in payload.skill_scores.items():
        key = (skill or "").strip().lower()
        if not key:
            continue
        normalized_scores[key] = int(weight)

    job = JobDescription(
        title=temp_jd.get("jd_title") or "Untitled Role",
        jd_title=temp_jd.get("jd_title") or "Untitled Role",
        jd_text=temp_jd["jd_path"],
        skill_scores=normalized_scores,
        gender_requirement=None,
        education_requirement=temp_jd.get("education_requirement"),
        experience_requirement=temp_jd.get("experience_requirement", 0),
        cutoff_score=float(temp_jd.get("cutoff_score", 65.0)),
        question_count=int(temp_jd.get("question_count", 8)),
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    candidates = db.query(Candidate).all()
    for candidate in candidates:
        if ensure_candidate_profile(candidate, db):
            db.commit()
            db.refresh(candidate)
        if not candidate.resume_path:
            continue
        score, explanation, _ = evaluate_resume_for_job(candidate, job)
        upsert_result(
            db,
            candidate.id,
            job.id,
            score,
            explanation,
            cutoff_score=float(job.cutoff_score if job.cutoff_score is not None else 65.0),
        )

    request.session.pop("temp_jd", None)
    return {"ok": True, "message": "JD confirmed and candidate scoring completed.", "job_id": job.id}


# 1) What this does: updates the selected job's skill weights.
# 2) Why needed: HR can tune screening criteria without re-uploading the JD.
# 3) How it works: saves normalized weights and recalculates candidate results for that job.
@router.post("/hr/update-skill-weights")
def update_skill_weights(
    payload: SkillWeightsBody,
    current_user: SessionUser = Depends(require_role("hr")),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    # NOTE: Accept both payload shapes here.
    # Frontend currently sends: { jd_id, weights, cutoff_score }
    # Older code may still send: { job_id, skill_scores, cutoff_score, question_count }
    requested_job_id = payload.job_id or payload.jd_id
    incoming_skill_scores = payload.skill_scores if payload.skill_scores is not None else payload.weights

    target_job = None
    if requested_job_id:
        target_job = db.query(JobDescription).filter(JobDescription.id == requested_job_id).first()
    if not target_job:
        target_job = db.query(JobDescription).order_by(JobDescription.id.desc()).first()
    if not target_job:
        raise HTTPException(status_code=404, detail="No JD found")
    if not incoming_skill_scores:
        raise HTTPException(status_code=400, detail="weights cannot be empty")

    # NOTE: Normalize whichever field name the caller used so the current
    # frontend HRSkillWeightsPage.jsx works without renaming its payload.
    target_job.skill_scores = {
        str(key).strip().lower(): int(value)
        for key, value in incoming_skill_scores.items()
        if str(key).strip()
    }
    if payload.cutoff_score is not None:
        target_job.cutoff_score = float(payload.cutoff_score)
    if payload.question_count is not None:
        target_job.question_count = int(payload.question_count)
    db.commit()

    candidates = db.query(Candidate).filter(Candidate.resume_path.isnot(None)).all()
    for candidate in candidates:
        if ensure_candidate_profile(candidate, db):
            db.commit()
            db.refresh(candidate)
        score, explanation, _ = evaluate_resume_for_job(candidate, target_job)
        upsert_result(
            db,
            candidate.id,
            target_job.id,
            score,
            explanation,
            cutoff_score=float(target_job.cutoff_score if target_job.cutoff_score is not None else 65.0),
        )

    return {"ok": True, "message": "Skill weights updated and scores recalculated."}


@router.get("/hr/local-backup")
def hr_local_backup(
    current_user: SessionUser = Depends(require_role("hr")),
    db: Session = Depends(get_db),
):
    _ = current_user
    archive_path = create_local_backup_archive(db)
    return FileResponse(
        path=archive_path,
        media_type="application/zip",
        filename=archive_path.name,
    )


# 1) What this does: stores HR-entered interview scoring for a candidate result.
# 2) Why needed: combines the resume and technical scores into one final interview outcome.
# 3) How it works: validates job ownership, computes the scorecard, and stores it in explanation JSON.
@router.post("/hr/interview-score")
def hr_interview_score(
    payload: InterviewScoreBody,
    current_user: SessionUser = Depends(require_role("hr")),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    result = db.query(Result).filter(Result.id == payload.result_id).first()
    if not result:
        raise HTTPException(status_code=404, detail="Result not found")

    job = db.query(JobDescription).filter(JobDescription.id == result.job_id).first()
    if not job:
        raise HTTPException(status_code=403, detail="Not allowed to score this result")

    explanation = result.explanation or {}
    resume_score = explanation.get("final_resume_score", result.score or 0)
    scorecard = compute_interview_scoring(payload.technical_score, float(resume_score))

    explanation["interview_scoring"] = scorecard
    result.explanation = explanation
    db.commit()
    db.refresh(result)

    return {"ok": True, "result_id": result.id, **scorecard}


@router.get("/hr/interviews/{session_id}/export-pdf")
def hr_export_interview_pdf(
    session_id: int,
    upload_s3: bool = False,
    current_user: SessionUser = Depends(require_role("hr")),
    db: Session = Depends(get_db),
):
    """Generate and download a comprehensive PDF report for an interview session."""
    from services.pdf_report import generate_interview_pdf

    session = db.query(InterviewSession).filter(InterviewSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Interview session not found")

    # Verify HR ownership
    result = db.query(Result).filter(Result.id == session.result_id).first()
    if not result:
        raise HTTPException(status_code=404, detail="Result not found")

    job = db.query(JobDescription).filter(JobDescription.id == result.job_id).first()
    if not job:
        raise HTTPException(status_code=403, detail="Not authorized to export this report")

    if session.status != "completed":
         # Optional: you could allow partial reports, but usually best after completion
         pass

    return_s3 = upload_s3 and db.query(Result).filter(Result.id == session.result_id).first()
    pdf_result = generate_interview_pdf(session, db, return_s3_url=return_s3)
    
    candidate = db.query(Candidate).filter(Candidate.id == session.candidate_id).first()
    safe_name = (candidate.name or "Candidate").replace(" ", "_")
    filename = f"Interview_Report_{safe_name}_{session.id}.pdf"

    if isinstance(pdf_result, tuple):
        pdf_buffer, s3_url = pdf_result
        return {
            "pdf_url": s3_url,
            "filename": filename,
            "message": "PDF uploaded to S3 successfully"
        }
    
    pdf_buffer = pdf_result
    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )