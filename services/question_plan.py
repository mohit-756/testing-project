"""Public wrapper for deterministic interview question planning."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict

from services._qp_evidence import (
    _clean,
    distribution_for_role,
    extract_structured_jd,
    extract_structured_resume,
    get_resume_module,
    infer_role_family,
    make_topic_candidates,
    role_track,
)
from services._qp_slots import build_question, has_duplicate_structure, slot_candidate, slot_order_for_context
from services._qp_structs import PlannerContext


def _materialize_questions(
    *,
    slot_order: list[str],
    total_questions: int,
    context: PlannerContext,
    occurrence_shift: int,
    index_shift: int,
) -> list[dict[str, object]]:
    category_counts: dict[str, int] = {}
    questions: list[dict[str, object]] = []
    used_labels: set[str] = set()

    for i, slot in enumerate(slot_order[:total_questions], start=1):
        category_counts[slot] = category_counts.get(slot, 0) + 1
        occurrence = category_counts[slot] + occurrence_shift
        candidate = slot_candidate(slot, context, occurrence, _used_labels=frozenset(used_labels))
        questions.append(build_question(slot, candidate, context, i + index_shift, occurrence))
        label = str(candidate.get("label") or "").strip().lower()
        if label and slot not in {"intro", "behavioral", "leadership"}:
            used_labels.add(label)

    return questions


def build_question_context(*, resume_text: str, jd_title: str | None, jd_skill_scores: Mapping[str, int] | None, question_count: int | None = None, project_ratio: float | None = None) -> dict[str, object]:
    resume = extract_structured_resume(resume_text or "")
    jd = extract_structured_jd(jd_title, jd_skill_scores)
    role_family, seniority = infer_role_family(jd_title or jd.title, resume, jd)
    ratio = project_ratio if project_ratio is not None else 0.8
    distribution = distribution_for_role(role_family, max(2, min(20, int(question_count or 8))), ratio)
    topic_priorities = make_topic_candidates(resume, jd, role_family)
    return {
        "role_title": _clean(jd_title or jd.title),
        "role_family": role_family,
        "seniority": seniority,
        "distribution": distribution,
        "jd_core_skills": jd.required_skills[:8],
        "jd_keywords": jd.keywords[:12],
        "resume_summary": resume.summary,
        "resume_projects": [item.text for item in resume.projects[:6]],
        "resume_recent_experience": [item.text for item in resume.experiences[:6]],
        "resume_skills": resume.skills[:12],
        "resume_certifications": resume.certifications[:5],
        "resume_leadership_signal": resume.leadership_signal,
        "resume_architecture_signal": resume.architecture_signal,
        "topic_priorities": topic_priorities[:10],
    }



def build_question_plan(*, resume_text: str, jd_title: str | None, jd_skill_scores: Mapping[str, int] | None, question_count: int | None = None, project_ratio: float | None = None) -> dict[str, object]:
    total_questions = max(6, min(9, int(question_count or 8)))
    resume = extract_structured_resume(resume_text or "")
    jd = extract_structured_jd(jd_title, jd_skill_scores)
    role_family, seniority = infer_role_family(jd_title or jd.title, resume, jd)
    topic_priorities = make_topic_candidates(resume, jd, role_family)
    ratio = project_ratio if project_ratio is not None else 0.8
    context = PlannerContext(
        role_family=role_family,
        seniority=seniority,
        title=_clean(jd_title or jd.title),
        resume=resume,
        jd=jd,
        topic_priorities=topic_priorities,
        distribution=distribution_for_role(role_family, total_questions, ratio),
    )

    rt = role_track(context)
    slot_order = slot_order_for_context(context, total_questions)

    questions = _materialize_questions(
        slot_order=slot_order,
        total_questions=total_questions,
        context=context,
        occurrence_shift=0,
        index_shift=0,
    )

    if has_duplicate_structure(questions):
        questions = _materialize_questions(
            slot_order=slot_order,
            total_questions=total_questions,
            context=context,
            occurrence_shift=1,
            index_shift=10,
        )

    project_like_count = sum(1 for item in questions if item.get("category") in {"deep_dive", "project", "architecture", "leadership"})
    hr_count = sum(1 for item in questions if item.get("category") == "behavioral")
    intro_count = sum(1 for item in questions if item.get("category") == "intro")
    projects = [item.label or item.text for item in resume.projects[:6]]
    structured_resume_meta = {
        "projects": [item.text for item in resume.projects[:6]],
        "experience": [item.text for item in resume.experiences[:6]],
        "skills": list(resume.skills[:18]),
    }

    return {
        "questions": questions,
        "total_questions": len(questions),
        "project_count": project_like_count,
        "hr_count": hr_count,
        "project_questions_count": project_like_count,
        "theory_questions_count": hr_count,
        "intro_count": intro_count,
        "projects": projects,
        "meta": {
            "total_questions": len(questions),
            "project_count": project_like_count,
            "hr_count": hr_count,
            "project_questions_count": project_like_count,
            "theory_questions_count": hr_count,
            "intro_count": intro_count,
            "projects": projects,
            "role_family": role_family,
            "seniority": seniority,
            "distribution": context.distribution,
            "structured_resume": structured_resume_meta,
            "structured_jd": asdict(jd),
            "topic_priorities": topic_priorities,
            "resume_module": get_resume_module(resume),
            "role_track": rt,
        },
    }
