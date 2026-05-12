"""HR dashboard aggregation helpers."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime

from sqlalchemy.orm import Session, joinedload

from models import JobDescription, Result
from services.pipeline import normalize_stage, stage_payload


def latest_session(result: Result | None):
    if not result or not result.sessions:
        return None
    return max(result.sessions, key=lambda item: (item.started_at or datetime.min, item.id or 0))


def status_key(result: Result | None, latest_session_row) -> str:
    if not result:
        return "applied"
    stage = normalize_stage(result.stage)
    # If result already has interview_completed stage, use it
    if stage == "interview_completed":
        return "interview_completed"
    if latest_session_row:
        session_status = (latest_session_row.status or "").strip().lower()
        if session_status in {"selected", "rejected"}:
            return session_status
        # Check for any completion-like status OR if ended_at is set
        if latest_session_row.ended_at or session_status in {"completed", "done", "finished", "completed_successful", "completed_fail"}:
            return "interview_completed"
        if result.interview_date:
            return "interview_scheduled"
    return stage


def status_payload(result: Result | None, latest_session_row) -> dict[str, str]:
    return stage_payload(status_key(result, latest_session_row))


def _job_title(job: JobDescription | None) -> str:
    if not job:
        return "Unknown JD"
    return str(job.jd_title or f"JD #{job.id}")


def build_hr_dashboard_analytics(
    db: Session,
    *,
    hr_id: int | None = None,
    selected_job_id: int | None = None,
) -> dict[str, object]:
    query_jobs = db.query(JobDescription)
    if hr_id is not None:
        query_jobs = query_jobs.filter(JobDescription.company_id == hr_id)
    jobs = query_jobs.order_by(JobDescription.id.desc()).all()
    
    query_results = db.query(Result)
    if hr_id is not None:
        query_results = query_results.join(JobDescription, Result.job_id == JobDescription.id).filter(JobDescription.company_id == hr_id)
    results = (
        query_results
        .options(joinedload(Result.sessions), joinedload(Result.candidate), joinedload(Result.job))
        .order_by(Result.id.desc())
        .all()
    )

    selected_results = [result for result in results if not selected_job_id or result.job_id == selected_job_id]
    pipeline_counter: Counter[str] = Counter()
    missing_counter: Counter[str] = Counter()
    matched_counter: Counter[str] = Counter()
    score_values: list[float] = []
    candidate_ids: set[int] = set()
    shortlisted_count = 0
    selected_count = 0
    interview_success_count = 0
    interview_attempt_count = 0
    per_jd_scores: dict[int, list[float]] = defaultdict(list)
    per_jd_counts: Counter[int] = Counter()

    for result in selected_results:
        latest = latest_session(result)
        current_stage = status_key(result, latest)
        pipeline_counter[current_stage] += 1
        if result.candidate_id is not None:
            candidate_ids.add(int(result.candidate_id))
        if result.shortlisted:
            shortlisted_count += 1
        score_value = float(result.final_score or result.score or 0)
        if score_value > 0:
            score_values.append(score_value)
            if result.job_id is not None:
                per_jd_scores[int(result.job_id)].append(score_value)
        if result.job_id is not None:
            per_jd_counts[int(result.job_id)] += 1
        if current_stage == "selected":
            selected_count += 1
        if current_stage in {"interview_completed", "selected", "rejected"}:
            interview_attempt_count += 1
        if current_stage == "selected":
            interview_success_count += 1

        explanation = result.explanation or {}
        for skill in explanation.get("missing_skills") or []:
            key = str(skill or "").strip().lower()
            if key:
                missing_counter[key] += 1
        for skill in explanation.get("matched_skills") or []:
            key = str(skill or "").strip().lower()
            if key:
                matched_counter[key] += 1

    completed = pipeline_counter.get("interview_completed", 0)
    scheduled = pipeline_counter.get("interview_scheduled", 0)
    total_results = len(selected_results)
    avg_score = round(sum(score_values) / len(score_values), 2) if score_values else 0.0
    avg_resume_score = round(
        sum(float((result.explanation or {}).get("final_resume_score") or result.score or 0) for result in selected_results) / total_results,
        2,
    ) if total_results else 0.0
    shortlist_rate = round((shortlisted_count / total_results) * 100, 2) if total_results else 0.0
    completion_rate = round((completed / (completed + scheduled)) * 100, 2) if (completed + scheduled) else 0.0
    selection_rate = round((selected_count / total_results) * 100, 2) if total_results else 0.0
    interview_success_rate = round((interview_success_count / interview_attempt_count) * 100, 2) if interview_attempt_count else 0.0
    top_ranked = sorted(selected_results, key=lambda item: float(item.final_score or item.score or 0), reverse=True)[:5]

    stage_order = ("applied", "screening", "shortlisted", "interview_scheduled", "interview_completed", "selected", "rejected")
    funnel_order = ("applied", "shortlisted", "interview_completed", "selected")

    avg_score_per_jd = [
        {
            "job_id": job.id,
            "job_title": _job_title(job),
            "avg_score": round(sum(per_jd_scores.get(job.id, []) or [0.0]) / max(1, len(per_jd_scores.get(job.id, []))), 2) if per_jd_scores.get(job.id) else 0.0,
            "candidate_count": int(per_jd_counts.get(job.id, 0)),
        }
        for job in jobs
    ]

    return {
        "overview": {
            "total_jobs": len(jobs),
            "total_applications": total_results,
            "active_candidates": len(candidate_ids),
            "total_candidates": len(candidate_ids),
            "completed_interviews": completed,
            "shortlisted_count": pipeline_counter.get("shortlisted", 0),
            "rejected_count": pipeline_counter.get("rejected", 0),
            "avg_resume_score": avg_resume_score,
            "avg_interview_score": avg_score,
            "shortlist_rate": shortlist_rate,
            "selection_rate": selection_rate,
            "interview_completion_rate": completion_rate,
            "interview_success_rate": interview_success_rate,
        },
        "pipeline": [
            {
                **stage_payload(key),
                "count": pipeline_counter.get(key, 0),
            }
            for key in stage_order
        ],
        "funnel": [
            {
                **stage_payload(key),
                "count": pipeline_counter.get(key, 0),
            }
            for key in funnel_order
        ],
        "avg_score_per_jd": avg_score_per_jd,
        "top_missing_skills": [{"skill": skill, "count": count} for skill, count in missing_counter.most_common(5)],
        "top_matched_skills": [{"skill": skill, "count": count} for skill, count in matched_counter.most_common(8)],
        "top_ranked_candidates": [
            {
                "result_id": row.id,
                "application_id": row.application_id,
                "candidate_uid": row.candidate.candidate_uid if row.candidate else None,
                "candidate_name": row.candidate.name if row.candidate else None,
                "job_title": _job_title(row.job),
                "final_score": float(row.final_score or row.score or 0),
                "recommendation": row.recommendation,
            }
            for row in top_ranked
        ],
        "stage_wise_candidate_count": dict(pipeline_counter),
    }
