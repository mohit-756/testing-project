"""Deterministic local-only resume improvement suggestions."""

from __future__ import annotations

from services.resume_parser import extract_projects_from_resume


def _skill_order(jd_skill_scores: dict[str, int] | None) -> list[tuple[str, int]]:
    ordered = []
    for skill, weight in (jd_skill_scores or {}).items():
        key = str(skill or "").strip().lower()
        if not key:
            continue
        try:
            ordered.append((key, int(weight)))
        except Exception:
            ordered.append((key, 0))
    ordered.sort(key=lambda item: (-item[1], item[0]))
    return ordered


def _string_list(values: object) -> list[str]:
    if not isinstance(values, list):
        return []
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = str(value or "").strip().lower()
        if not item or item in seen:
            continue
        seen.add(item)
        cleaned.append(item)
    return cleaned


def build_resume_advice(
    *,
    resume_text: str,
    jd_skill_scores: dict[str, int] | None,
    explanation: dict[str, object] | None,
    candidate_name: str | None = None,
) -> dict[str, object]:
    normalized_text = (resume_text or "").strip()
    ordered_skills = _skill_order(jd_skill_scores)
    matched_skills = _string_list((explanation or {}).get("matched_skills"))
    missing_skills = _string_list((explanation or {}).get("missing_skills"))

    if not missing_skills:
        missing_skills = [skill for skill, _weight in ordered_skills if skill not in set(matched_skills)][:5]

    strengths = matched_skills[:4] or [skill for skill, _weight in ordered_skills[:3]]
    priority_gaps = [
        {
            "skill": skill,
            "weight": weight,
            "reason": f"{skill.title()} is weighted in the JD but is not clearly evidenced in the resume.",
        }
        for skill, weight in ordered_skills
        if skill in set(missing_skills)
    ][:4]

    projects = extract_projects_from_resume(normalized_text, known_skills=dict(ordered_skills), candidate_name=candidate_name)
    project_tips = []
    for index, project in enumerate(projects[:2], start=1):
        focus_skill = priority_gaps[index - 1]["skill"] if len(priority_gaps) >= index else (strengths[0] if strengths else "your core stack")
        # Compatibility fix: older project extraction returned dicts, while newer
        # resume parsing may surface plain strings. Support both shapes safely.
        if isinstance(project, dict):
            tech_stack = ", ".join(project.get("tech_stack") or []) or "the exact stack you used"
            title = project.get("title") or f"Project {index}"
        else:
            tech_stack = "the exact stack you used"
            title = str(project or f"Project {index}").strip() or f"Project {index}"
        project_tips.append(
            {
                "title": title,
                "tip": f"Rewrite this project with the problem, your ownership, {tech_stack}, measurable impact, and where {focus_skill} was applied.",
            }
        )

    rewrite_tips = [
        "Lead each bullet with an action verb, then add one measurable outcome.",
        "Mention production ownership, debugging, testing, or deployment instead of only listing tools.",
    ]
    if priority_gaps:
        rewrite_tips.append(
            "Add one bullet per priority gap showing where that skill was used in a project, internship, or coursework."
        )
    if not normalized_text:
        rewrite_tips = ["Upload a resume with project, experience, and skill sections to generate targeted advice."]

    next_steps = []
    if priority_gaps:
        next_steps.append(
            f"Prioritize evidence for {', '.join(item['skill'] for item in priority_gaps[:3])} in your next resume edit."
        )
    if strengths:
        next_steps.append(
            f"Keep {', '.join(strengths[:3])} visible near the top because those are already helping your score."
        )
    next_steps.append("Turn project descriptions into result-oriented bullets with scale, users, latency, savings, or reliability metrics.")

    return {
        "strengths": strengths,
        "priority_gaps": priority_gaps,
        "rewrite_tips": rewrite_tips,
        "project_tips": project_tips,
        "next_steps": next_steps,
    }
