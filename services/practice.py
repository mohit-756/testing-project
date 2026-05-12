"""Helpers for local practice interview preparation."""

from __future__ import annotations

from services.question_generation import build_question_bundle

def build_practice_kit(
    *,
    resume_text: str,
    jd_title: str | None,
    jd_skill_scores: dict[str, int] | None,
    question_count: int = 6,
) -> dict[str, object]:
    bundle = build_question_bundle(
        resume_text=resume_text,
        jd_title=jd_title,
        jd_skill_scores=jd_skill_scores or {},
        question_count=max(4, min(12, int(question_count or 6))),
        project_ratio=0.65,
    )
    return {
        "questions": list(bundle["questions"]),
        "meta": {
            "total_questions": int(bundle["total_questions"]),
            "project_questions_count": int(bundle["project_questions_count"]),
            "theory_questions_count": int(bundle["theory_questions_count"]),
            "projects": bundle["projects"],
        },
    }
