# """Resume and interview scoring helpers used across the application."""

# from __future__ import annotations

# import re
# from collections.abc import Mapping
# from typing import Iterable

# from ai_engine.phase1.matching import (
#     calculate_semantic_score,
#     extract_academic_percentages,
#     extract_education,
#     extract_experience,
#     extract_education_llm,
#     extract_experience_llm,
# )

# SKILL_ALIASES: dict[str, list[str]] = {
#     "python": ["python"],
#     "java": ["java"],
#     "c++": ["c++", "cpp"],
#     "c#": ["c#", "c sharp", "dotnet", ".net"],
#     "javascript": ["javascript", "js"],
#     "typescript": ["typescript", "ts"],
#     "react": ["react", "reactjs", "react.js"],
#     "node.js": ["node", "nodejs", "node.js"],
#     "fastapi": ["fastapi"],
#     "django": ["django"],
#     "flask": ["flask"],
#     "sql": ["sql"],
#     "mysql": ["mysql"],
#     "postgresql": ["postgresql", "postgres", "psql"],
#     "mongodb": ["mongodb", "mongo"],
#     "aws": ["aws", "amazon web services"],
#     "azure": ["azure", "microsoft azure"],
#     "gcp": ["gcp", "google cloud"],
#     "docker": ["docker"],
#     "kubernetes": ["kubernetes", "k8s"],
#     "git": ["git", "github", "gitlab"],
#     "linux": ["linux"],
#     "power bi": ["power bi", "powerbi"],
#     "tableau": ["tableau"],
#     "html": ["html", "html5"],
#     "css": ["css", "css3"],
#     "machine learning": ["machine learning", "ml"],
#     "deep learning": ["deep learning"],
#     "nlp": ["nlp", "natural language processing"],
# }

# RESUME_SECTION_MARKERS = {"skills", "experience", "project", "projects", "education"}
# ACTION_RESULT_WORDS = {
#     "built",
#     "improved",
#     "fixed",
#     "reduced",
#     "designed",
#     "deployed",
#     "led",
#     "measured",
#     "implemented",
#     "launched",
#     "optimized",
#     "delivered",
# }

# EDUCATION_KEYWORDS: dict[str, set[str]] = {
#     "bachelor": {"bachelor", "bachelors", "bachelor's", "b.tech", "btech", "b.e", "be", "bsc", "bca"},
#     "master": {"master", "masters", "master's", "m.tech", "mtech", "m.e", "me", "msc", "mba", "mca"},
#     "phd": {"phd", "doctorate"},
# }


# def _normalize_skill(skill: str) -> str:
#     cleaned = re.sub(r"[^a-zA-Z0-9+.# ]", " ", skill or "")
#     cleaned = re.sub(r"\s+", " ", cleaned).strip().lower()
#     return cleaned


# def _contains_skill(text: str, term: str) -> bool:
#     pattern = rf"(?<!\w){re.escape(term.lower())}(?!\w)"
#     return re.search(pattern, text.lower()) is not None


# def _tokenize(text: str) -> list[str]:
#     return re.findall(r"[a-zA-Z0-9+#.-]+", (text or "").lower())


# def compute_resume_skill_match(resume_text: str, jd_skills: Iterable[str], skill_weights: dict[str, int] | None = None) -> dict[str, object]:
#     """Compute overlap between JD-required skills and detected resume skills.
    
#     Now supports weighted skill matching:
#     - If skill_weights provided: weighted percentage = (matched_weight / total_weight) × 100
#     - If skill_weights not provided: simple count percentage (backward compatible)
#     """

#     normalized_required = sorted({_normalize_skill(skill) for skill in jd_skills if _normalize_skill(skill)})
#     if not normalized_required:
#         return {
#             "matched_percentage": 100.0,
#             "weighted_percentage": 100.0,
#             "matched_skills": [],
#             "missing_skills": [],
#             "matched_weight": 0.0,
#             "total_weight": 0.0,
#         }

#     resume_text = resume_text or ""
#     matched_skills: list[str] = []
#     missing_skills: list[str] = []
#     matched_weight: float = 0.0
#     total_weight: float = 0.0

#     for required_skill in normalized_required:
#         skill_weight = 0
#         if skill_weights:
#             normalized_weight_key = _normalize_skill(required_skill)
#             skill_weight = int(skill_weights.get(normalized_weight_key, skill_weights.get(required_skill, 0)))
#             if skill_weight > 0:
#                 total_weight += skill_weight

#         aliases = SKILL_ALIASES.get(required_skill, [required_skill])
#         if any(_contains_skill(resume_text, alias) for alias in aliases):
#             matched_skills.append(required_skill)
#             if skill_weight > 0:
#                 matched_weight += skill_weight
#         else:
#             missing_skills.append(required_skill)

#     simple_percentage = round((len(matched_skills) / len(normalized_required)) * 100, 2)
#     weighted_percentage = round((matched_weight / total_weight) * 100, 2) if total_weight > 0 else simple_percentage

#     return {
#         "matched_percentage": simple_percentage,
#         "weighted_percentage": weighted_percentage,
#         "matched_skills": matched_skills,
#         "missing_skills": missing_skills,
#         "matched_weight": matched_weight,
#         "total_weight": total_weight,
#     }


# def _clamp_score(score: float) -> float:
#     return round(max(0.0, min(100.0, float(score))), 2)


# def _recommendation(final_score: float) -> str:
#     if final_score >= 75:
#         return "Select"
#     if final_score >= 55:
#         return "Borderline"
#     return "Reject"


# def _screening_band(score: float) -> str:
#     if score >= 80:
#         return "strong_shortlist"
#     if score >= 65:
#         return "review_shortlist"
#     return "reject"


# def _semantic_percentage(semantic_similarity: float | None, jd_text: str, resume_text: str) -> float:
#     if semantic_similarity is None:
#         if not jd_text.strip() or not resume_text.strip():
#             return 0.0
#         try:
#             semantic_similarity = calculate_semantic_score(jd_text, resume_text)
#         except Exception:
#             semantic_similarity = 0.0

#     try:
#         numeric = float(semantic_similarity)
#     except Exception:
#         numeric = 0.0

#     if numeric > 1.0:
#         numeric = numeric / 100.0
#     return _clamp_score(max(0.0, min(1.0, numeric)) * 100.0)


# def _normalize_education(value: str | None) -> str | None:
#     normalized = _normalize_skill(value or "")
#     if not normalized:
#         return None
#     for level, keywords in EDUCATION_KEYWORDS.items():
#         if normalized == level or normalized in keywords:
#             return level
#     return normalized


# def _education_rank(value: str | None) -> int | None:
#     normalized = _normalize_education(value)
#     if normalized == "bachelor":
#         return 1
#     if normalized == "master":
#         return 2
#     if normalized == "phd":
#         return 3
#     return None


# def _resume_quality_score(resume_text: str) -> tuple[float, str]:
#     cleaned = (resume_text or "").strip()
#     if len(cleaned) < 100:
#         return 0.0, "Resume text is too short or unreadable."

#     text_lower = cleaned.lower()
#     markers_present = sum(1 for marker in RESUME_SECTION_MARKERS if marker in text_lower)
#     if markers_present >= 2:
#         return 100.0, "Resume includes multiple core sections."
#     return 60.0, "Resume text is present but missing clear structure."


# def _academic_cutoff_status(
#     resume_text: str,
#     min_academic_percent: float,
# ) -> tuple[dict[str, float | None], float | None, str | None, float, bool, str]:
#     academic_percentages = extract_academic_percentages(resume_text or "")

#     detected_percent: float | None = None
#     detected_level: str | None = None
#     for level in ("engineering", "intermediate", "10th"):
#         value = academic_percentages.get(level)
#         if value is None:
#             continue
#         detected_percent = float(value)
#         detected_level = level
#         break

#     required_percent = max(0.0, float(min_academic_percent or 0.0))
#     if required_percent <= 0:
#         return (
#             academic_percentages,
#             detected_percent,
#             detected_level,
#             100.0,
#             True,
#             "No academic cutoff configured.",
#         )

#     if detected_percent is None:
#         return (
#             academic_percentages,
#             None,
#             None,
#             0.0,
#             False,
#             f"Academic cutoff not met: required {required_percent:.0f}%, but no academic percentage was detected.",
#         )

#     if detected_percent >= required_percent:
#         return (
#             academic_percentages,
#             detected_percent,
#             detected_level,
#             100.0,
#             True,
#             f"Academic cutoff satisfied: required {required_percent:.0f}%, found {detected_percent:.2f}% ({detected_level}).",
#         )

#     return (
#         academic_percentages,
#         detected_percent,
#         detected_level,
#         0.0,
#         False,
#         f"Academic cutoff not met: required {required_percent:.0f}%, found {detected_percent:.2f}% ({detected_level}).",
#     )


# def _weighted_skill_score(skill_scores: Mapping[str, int] | None, matched_skills: list[str]) -> float:
#     if not skill_scores:
#         return 100.0

#     normalized_weights = {
#         _normalize_skill(skill): max(0.0, float(weight))
#         for skill, weight in skill_scores.items()
#         if _normalize_skill(skill)
#     }
#     total_weight = sum(normalized_weights.values())
#     if total_weight <= 0:
#         return 100.0

#     matched_weight = sum(normalized_weights.get(skill, 0.0) for skill in matched_skills)
#     match_ratio = matched_weight / total_weight
#     base_score = 70.0
#     bonus_for_match = match_ratio * 30.0
#     return _clamp_score(base_score + bonus_for_match)


# def _resume_reasons(
#     *,
#     screening_band: str,
#     matched_skills: list[str],
#     missing_skills: list[str],
#     experience_score: float,
#     education_score: float,
#     semantic_score: float,
#     academic_cutoff_met: bool,
#     academic_cutoff_reason: str,
#     resume_quality_reason: str,
# ) -> list[str]:
#     reasons: list[str] = []
#     if not academic_cutoff_met:
#         reasons.append(academic_cutoff_reason)

#     if screening_band == "strong_shortlist":
#         reasons.append("Overall profile is strong enough for direct shortlist review.")
#     elif screening_band == "review_shortlist":
#         reasons.append("Profile is worth manager review but has some measurable gaps.")
#     else:
#         reasons.append("Profile has too many gaps for shortlist at this stage.")

#     if matched_skills:
#         reasons.append(f"Matched skills: {', '.join(matched_skills[:5])}.")
#     if missing_skills:
#         reasons.append(f"Missing skills: {', '.join(missing_skills[:5])}.")
#     if experience_score < 100:
#         reasons.append("Experience is below the stated requirement.")
#     if education_score < 100:
#         reasons.append("Education is below the preferred level.")
#     if semantic_score < 40:
#         reasons.append("Resume wording is only loosely aligned with the JD.")
#     reasons.append(resume_quality_reason)
#     return reasons[:5]


# def compute_resume_scorecard(
#     *,
#     resume_text: str,
#     jd_text: str,
#     jd_skill_scores: Mapping[str, int] | None,
#     education_requirement: str | None = None,
#     experience_requirement: int = 0,
#     semantic_similarity: float | None = None,
#     min_academic_percent: float = 0.0,
#     use_llm: bool = True,
# ) -> dict[str, object]:
#     """Build a stable explainable resume scorecard with a 0-100 final score.
    
#     Args:
#         use_llm: If True, uses LLM for experience/education detection (default True)
#     """

#     resume_text = resume_text or ""
#     jd_text = jd_text or ""
#     skill_match = compute_resume_skill_match(resume_text, (jd_skill_scores or {}).keys(), jd_skill_scores)

#     weighted_skill_score = _weighted_skill_score(jd_skill_scores, list(skill_match["matched_skills"]))
#     semantic_score = _semantic_percentage(semantic_similarity, jd_text, resume_text)
#     (
#         academic_percentages,
#         detected_academic_percent,
#         detected_academic_level,
#         academic_cutoff_score,
#         academic_cutoff_met,
#         academic_cutoff_reason,
#     ) = _academic_cutoff_status(resume_text, min_academic_percent)

#     detected_experience_years = max(0, int(extract_experience_llm(resume_text) if use_llm else extract_experience(resume_text)))
#     required_years = max(0, int(experience_requirement or 0))
#     if required_years == 0:
#         experience_score = 100.0
#         experience_reason = "No experience requirement configured."
#     else:
#         experience_score = _clamp_score((detected_experience_years / required_years) * 100.0)
#         if detected_experience_years >= required_years:
#             experience_reason = "Experience requirement satisfied."
#         else:
#             experience_reason = f"Required {required_years} years, found {detected_experience_years}."

#     detected_education_level = _normalize_education(extract_education_llm(resume_text) if use_llm else extract_education(resume_text))
#     required_education_level = _normalize_education(education_requirement)
#     required_education_rank = _education_rank(required_education_level)
#     detected_education_rank = _education_rank(detected_education_level)
#     if required_education_rank is None:
#         education_score = 100.0
#         education_reason = "No education requirement configured."
#     elif detected_education_rank is None:
#         education_score = 0.0
#         education_reason = f"Required {required_education_level}, no matching degree found."
#     elif detected_education_rank >= required_education_rank:
#         education_score = 100.0
#         education_reason = "Education requirement satisfied."
#     elif detected_education_rank == required_education_rank - 1:
#         education_score = 50.0
#         education_reason = (
#             f"Required {required_education_level}, found {detected_education_level}; partial match only."
#         )
#     else:
#         education_score = 0.0
#         education_reason = f"Required {required_education_level}, found {detected_education_level}."

#     resume_quality_score, resume_quality_reason = _resume_quality_score(resume_text)

#     final_resume_score = _clamp_score(
#         (weighted_skill_score * 0.50)
#         + (semantic_score * 0.15)
#         + (experience_score * 0.15)
#         + (education_score * 0.10)
#         + (academic_cutoff_score * 0.05)
#         + (resume_quality_score * 0.05)
#     )
#     screening_band = _screening_band(final_resume_score) if academic_cutoff_met else "reject"

#     reasons = _resume_reasons(
#         screening_band=screening_band,
#         matched_skills=list(skill_match["matched_skills"]),
#         missing_skills=list(skill_match["missing_skills"]),
#         experience_score=experience_score,
#         education_score=education_score,
#         semantic_score=semantic_score,
#         academic_cutoff_met=academic_cutoff_met,
#         academic_cutoff_reason=academic_cutoff_reason,
#         resume_quality_reason=resume_quality_reason,
#     )

#     return {
#         "score_version": "v2",
#         "screening_band": screening_band,
#         "final_resume_score": final_resume_score,
#         "weighted_skill_score": weighted_skill_score,
#         "semantic_score": semantic_score,
#         "experience_score": experience_score,
#         "education_score": education_score,
#         "resume_quality_score": resume_quality_score,
#         "academic_cutoff_score": academic_cutoff_score,
#         "academic_cutoff_met": academic_cutoff_met,
#         "academic_cutoff_reason": academic_cutoff_reason,
#         "min_academic_percent_required": max(0.0, float(min_academic_percent or 0.0)),
#         "detected_academic_percent": detected_academic_percent,
#         "detected_academic_level": detected_academic_level,
#         "academic_percentages": academic_percentages,
#         "matched_percentage": float(skill_match["matched_percentage"]),
#         "matched_skills": list(skill_match["matched_skills"]),
#         "missing_skills": list(skill_match["missing_skills"]),
#         "detected_experience_years": detected_experience_years,
#         "detected_education_level": detected_education_level,
#         "reasons": reasons,
#         "skill_score": weighted_skill_score,
#         "education_reason": education_reason,
#         "experience_reason": experience_reason,
#         "resume_quality_reason": resume_quality_reason,
#         "total_experience_detected": detected_experience_years,
#     }


# def compute_interview_scoring(technical_score: float, resume_score: float) -> dict[str, object]:
#     """Aggregate technical and resume tracks into final interview outcome."""

#     technical = _clamp_score(technical_score)
#     resume = _clamp_score(resume_score)
#     final = _clamp_score((technical * 0.65) + (resume * 0.35))
#     return {
#         "technical_score": technical,
#         "resume_score": resume,
#         "resume_score_used": resume,
#         "final_score": final,
#         "recommendation": _recommendation(final),
#     }


# def _answer_relevance(question: str, answer: str, jd_skills: Iterable[str] | None) -> tuple[float, int]:
#     question_tokens = set(_tokenize(question))
#     answer_text = answer or ""
#     answer_tokens = set(_tokenize(answer_text))
#     if not answer_tokens:
#         return 0.0, 0

#     overlap_ratio = len(question_tokens & answer_tokens) / max(1, len(question_tokens))
#     relevance = overlap_ratio * 100.0

#     skill_hits = 0
#     normalized_skills = sorted({_normalize_skill(skill) for skill in (jd_skills or []) if _normalize_skill(skill)})
#     if normalized_skills:
#         for skill in normalized_skills:
#             aliases = SKILL_ALIASES.get(skill, [skill])
#             if any(_contains_skill(answer_text, alias) for alias in aliases):
#                 skill_hits += 1
#         relevance += (skill_hits / len(normalized_skills)) * 15.0

#     return _clamp_score(relevance), skill_hits


# def _answer_completeness(answer: str) -> tuple[float, int]:
#     answer_tokens = _tokenize(answer)
#     word_count = len(answer_tokens)
#     if word_count == 0:
#         return 0.0, 0

#     if word_count < 8:
#         score = 20.0
#     elif word_count < 20:
#         score = 55.0
#     elif word_count <= 80:
#         score = 85.0
#     elif word_count <= 140:
#         score = 100.0
#     else:
#         score = 80.0

#     action_hits = sum(1 for token in set(answer_tokens) if token in ACTION_RESULT_WORDS)
#     score += min(15.0, action_hits * 5.0)
#     if re.search(r"\d", answer or ""):
#         score += 5.0
#     return _clamp_score(score), word_count


# def _answer_clarity(answer: str, word_count: int) -> float:
#     if word_count == 0:
#         return 0.0
#     if word_count < 5:
#         return 40.0

#     tokens = _tokenize(answer)
#     unique_ratio = len(set(tokens)) / max(1, len(tokens))
#     sentences = [segment.strip() for segment in re.split(r"[.!?]+", answer or "") if segment.strip()]
#     longest_sentence = max((len(_tokenize(segment)) for segment in sentences), default=0)

#     clarity = 100.0
#     if unique_ratio < 0.35:
#         clarity -= 35.0
#     elif unique_ratio < 0.50:
#         clarity -= 15.0

#     if len(sentences) <= 1 and word_count > 25:
#         clarity -= 15.0
#     if longest_sentence > 40:
#         clarity -= 10.0
#     return _clamp_score(clarity)


# def _answer_time_fit(answer: str, allotted_seconds: int, time_taken_seconds: int) -> float:
#     if not (answer or "").strip():
#         return 0.0
#     if allotted_seconds <= 0 or time_taken_seconds <= 0:
#         return 70.0

#     ratio = time_taken_seconds / max(1, allotted_seconds)
#     if 0.40 <= ratio <= 0.95:
#         return 100.0
#     if 0.20 <= ratio < 0.40 or 0.95 < ratio <= 1.10:
#         return 70.0
#     return 40.0


# def compute_answer_scorecard(
#     question: str,
#     answer: str,
#     *,
#     allotted_seconds: int = 0,
#     time_taken_seconds: int = 0,
#     jd_skills: Iterable[str] | None = None,
# ) -> dict[str, float | int]:
#     """Return a structured 0-100 answer score and component breakdown."""

#     normalized_answer = (answer or "").strip()
#     if not normalized_answer:
#         return {
#             "overall_score": 0.0,
#             "relevance": 0.0,
#             "completeness": 0.0,
#             "clarity": 0.0,
#             "time_fit": 0.0,
#             "word_count": 0,
#             "skill_hits": 0,
#         }

#     relevance, skill_hits = _answer_relevance(question, normalized_answer, jd_skills)
#     completeness, word_count = _answer_completeness(normalized_answer)
#     clarity = _answer_clarity(normalized_answer, word_count)
#     time_fit = _answer_time_fit(normalized_answer, allotted_seconds, time_taken_seconds)
#     overall_score = _clamp_score(
#         (relevance * 0.40) + (completeness * 0.25) + (clarity * 0.20) + (time_fit * 0.15)
#     )
#     return {
#         "overall_score": overall_score,
#         "relevance": relevance,
#         "completeness": completeness,
#         "clarity": clarity,
#         "time_fit": time_fit,
#         "word_count": word_count,
#         "skill_hits": skill_hits,
#     }
"""Resume and interview scoring helpers used across the application."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Iterable

from ai_engine.phase1.matching import (
    calculate_semantic_score,
    extract_academic_percentages,
    extract_education,
    extract_experience,
    extract_education_llm,
    extract_experience_llm,
)

SKILL_ALIASES: dict[str, list[str]] = {
    "python": ["python"],
    "java": ["java"],
    "c++": ["c++", "cpp"],
    "c#": ["c#", "c sharp", "dotnet", ".net"],
    "javascript": ["javascript", "js"],
    "typescript": ["typescript", "ts"],
    "react": ["react", "reactjs", "react.js"],
    "node.js": ["node", "nodejs", "node.js"],
    "fastapi": ["fastapi"],
    "django": ["django"],
    "flask": ["flask"],
    "sql": ["sql"],
    "mysql": ["mysql"],
    "postgresql": ["postgresql", "postgres", "psql"],
    "mongodb": ["mongodb", "mongo"],
    "aws": ["aws", "amazon web services"],
    "azure": ["azure", "microsoft azure"],
    "gcp": ["gcp", "google cloud"],
    "docker": ["docker"],
    "kubernetes": ["kubernetes", "k8s"],
    "git": ["git", "github", "gitlab"],
    "linux": ["linux"],
    "power bi": ["power bi", "powerbi"],
    "tableau": ["tableau"],
    "html": ["html", "html5"],
    "css": ["css", "css3"],
    "machine learning": ["machine learning", "ml"],
    "deep learning": ["deep learning"],
    "nlp": ["nlp", "natural language processing"],
}

RESUME_SECTION_MARKERS = {"skills", "experience", "project", "projects", "education"}
ACTION_RESULT_WORDS = {
    "built",
    "improved",
    "fixed",
    "reduced",
    "designed",
    "deployed",
    "led",
    "measured",
    "implemented",
    "launched",
    "optimized",
    "delivered",
}

EDUCATION_KEYWORDS: dict[str, set[str]] = {
    "bachelor": {"bachelor", "bachelors", "bachelor's", "b.tech", "btech", "b.e", "be", "bsc", "bca"},
    "master": {"master", "masters", "master's", "m.tech", "mtech", "m.e", "me", "msc", "mba", "mca"},
    "phd": {"phd", "doctorate"},
}


def _normalize_skill(skill: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9+.# ]", " ", skill or "")
    cleaned = re.sub(r"\s+", " ", cleaned).strip().lower()
    return cleaned


def _contains_skill(text: str, term: str) -> bool:
    pattern = rf"(?<!\w){re.escape(term.lower())}(?!\w)"
    return re.search(pattern, text.lower()) is not None


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z0-9+#.-]+", (text or "").lower())


def compute_resume_skill_match(resume_text: str, jd_skills: Iterable[str], skill_weights: dict[str, int] | None = None) -> dict[str, object]:
    """Compute overlap between JD-required skills and detected resume skills.
    
    Now supports weighted skill matching:
    - If skill_weights provided: weighted percentage = (matched_weight / total_weight) × 100
    - If skill_weights not provided: simple count percentage (backward compatible)
    """

    normalized_required = sorted({_normalize_skill(skill) for skill in jd_skills if _normalize_skill(skill)})
    if not normalized_required:
        return {
            "matched_percentage": 100.0,
            "weighted_percentage": 100.0,
            "matched_skills": [],
            "missing_skills": [],
            "matched_weight": 0.0,
            "total_weight": 0.0,
        }

    resume_text = resume_text or ""
    matched_skills: list[str] = []
    missing_skills: list[str] = []
    matched_weight: float = 0.0
    total_weight: float = 0.0

    for required_skill in normalized_required:
        skill_weight = 0
        if skill_weights:
            normalized_weight_key = _normalize_skill(required_skill)
            skill_weight = int(skill_weights.get(normalized_weight_key, skill_weights.get(required_skill, 0)))
            if skill_weight > 0:
                total_weight += skill_weight

        aliases = SKILL_ALIASES.get(required_skill, [required_skill])
        if any(_contains_skill(resume_text, alias) for alias in aliases):
            matched_skills.append(required_skill)
            if skill_weight > 0:
                matched_weight += skill_weight
        else:
            missing_skills.append(required_skill)

    simple_percentage = round((len(matched_skills) / len(normalized_required)) * 100, 2)
    weighted_percentage = round((matched_weight / total_weight) * 100, 2) if total_weight > 0 else simple_percentage

    return {
        "matched_percentage": simple_percentage,
        "weighted_percentage": weighted_percentage,
        "matched_skills": matched_skills,
        "missing_skills": missing_skills,
        "matched_weight": matched_weight,
        "total_weight": total_weight,
    }


def _clamp_score(score: float) -> float:
    return round(max(0.0, min(100.0, float(score))), 2)


def _recommendation(final_score: float) -> str:
    if final_score >= 75:
        return "Select"
    if final_score >= 45:
        return "Shortlist"
    return "Weak"


def _screening_band(score: float) -> str:
    if score >= 80:
        return "strong_shortlist"
    if score >= 65:
        return "review_shortlist"
    return "reject"


def _semantic_percentage(semantic_similarity: float | None, jd_text: str, resume_text: str) -> float:
    if semantic_similarity is None:
        if not jd_text.strip() or not resume_text.strip():
            return 0.0
        try:
            semantic_similarity = calculate_semantic_score(jd_text, resume_text)
        except Exception:
            semantic_similarity = 0.0

    try:
        numeric = float(semantic_similarity)
    except Exception:
        numeric = 0.0

    if numeric > 1.0:
        numeric = numeric / 100.0
    return _clamp_score(max(0.0, min(1.0, numeric)) * 100.0)


def _normalize_education(value: str | None) -> str | None:
    normalized = _normalize_skill(value or "")
    if not normalized:
        return None
    for level, keywords in EDUCATION_KEYWORDS.items():
        if normalized == level or normalized in keywords:
            return level
    return normalized


def _education_rank(value: str | None) -> int | None:
    normalized = _normalize_education(value)
    if normalized == "bachelor":
        return 1
    if normalized == "master":
        return 2
    if normalized == "phd":
        return 3
    return None


def _resume_quality_score(resume_text: str) -> tuple[float, str]:
    cleaned = (resume_text or "").strip()
    if len(cleaned) < 100:
        return 0.0, "Resume text is too short or unreadable."

    text_lower = cleaned.lower()
    markers_present = sum(1 for marker in RESUME_SECTION_MARKERS if marker in text_lower)
    if markers_present >= 2:
        return 100.0, "Resume includes multiple core sections."
    return 60.0, "Resume text is present but missing clear structure."


def _academic_cutoff_status(
    resume_text: str,
    min_academic_percent: float,
) -> tuple[dict[str, float | None], float | None, str | None, float, bool, str]:
    academic_percentages = extract_academic_percentages(resume_text or "")

    detected_percent: float | None = None
    detected_level: str | None = None
    for level in ("engineering", "intermediate", "10th"):
        value = academic_percentages.get(level)
        if value is None:
            continue
        detected_percent = float(value)
        detected_level = level
        break

    required_percent = max(0.0, float(min_academic_percent or 0.0))
    if required_percent <= 0:
        return (
            academic_percentages,
            detected_percent,
            detected_level,
            100.0,
            True,
            "No academic cutoff configured.",
        )

    if detected_percent is None:
        return (
            academic_percentages,
            None,
            None,
            0.0,
            False,
            f"Academic cutoff not met: required {required_percent:.0f}%, but no academic percentage was detected.",
        )

    if detected_percent >= required_percent:
        return (
            academic_percentages,
            detected_percent,
            detected_level,
            100.0,
            True,
            f"Academic cutoff satisfied: required {required_percent:.0f}%, found {detected_percent:.2f}% ({detected_level}).",
        )

    return (
        academic_percentages,
        detected_percent,
        detected_level,
        0.0,
        False,
        f"Academic cutoff not met: required {required_percent:.0f}%, found {detected_percent:.2f}% ({detected_level}).",
    )


def _weighted_skill_score(skill_scores: Mapping[str, int] | None, matched_skills: list[str]) -> float:
    if not skill_scores:
        return 100.0

    normalized_weights = {
        _normalize_skill(skill): max(0.0, float(weight))
        for skill, weight in skill_scores.items()
        if _normalize_skill(skill)
    }
    total_weight = sum(normalized_weights.values())
    if total_weight <= 0:
        return 100.0

    matched_weight = sum(normalized_weights.get(skill, 0.0) for skill in matched_skills)
    return _clamp_score((matched_weight / total_weight) * 100.0)


def _resume_reasons(
    *,
    screening_band: str,
    matched_skills: list[str],
    missing_skills: list[str],
    experience_score: float,
    education_score: float,
    semantic_score: float,
    academic_cutoff_met: bool,
    academic_cutoff_reason: str,
    resume_quality_reason: str,
) -> list[str]:
    reasons: list[str] = []
    if not academic_cutoff_met:
        reasons.append(academic_cutoff_reason)

    if screening_band == "strong_shortlist":
        reasons.append("Overall profile is strong enough for direct shortlist review.")
    elif screening_band == "review_shortlist":
        reasons.append("Profile is worth manager review but has some measurable gaps.")
    else:
        reasons.append("Profile has too many gaps for shortlist at this stage.")

    if matched_skills:
        reasons.append(f"Matched skills: {', '.join(matched_skills[:5])}.")
    if missing_skills:
        reasons.append(f"Missing skills: {', '.join(missing_skills[:5])}.")
    if experience_score < 100:
        reasons.append("Experience is below the stated requirement.")
    if education_score < 100:
        reasons.append("Education is below the preferred level.")
    if semantic_score < 40:
        reasons.append("Resume wording is only loosely aligned with the JD.")
    reasons.append(resume_quality_reason)
    return reasons[:5]


def compute_resume_scorecard(
    *,
    resume_text: str,
    jd_text: str,
    jd_skill_scores: Mapping[str, int] | None,
    education_requirement: str | None = None,
    experience_requirement: int = 0,
    semantic_similarity: float | None = None,
    min_academic_percent: float = 0.0,
    use_llm: bool = True,
) -> dict[str, object]:
    """Build a stable explainable resume scorecard with a 0-100 final score.
    
    Args:
        use_llm: If True, uses LLM for experience/education detection (default True)
    """

    resume_text = resume_text or ""
    jd_text = jd_text or ""
    skill_match = compute_resume_skill_match(resume_text, (jd_skill_scores or {}).keys(), jd_skill_scores)

    weighted_skill_score = _weighted_skill_score(jd_skill_scores, list(skill_match["matched_skills"]))
    semantic_score = _semantic_percentage(semantic_similarity, jd_text, resume_text)
    (
        academic_percentages,
        detected_academic_percent,
        detected_academic_level,
        academic_cutoff_score,
        academic_cutoff_met,
        academic_cutoff_reason,
    ) = _academic_cutoff_status(resume_text, min_academic_percent)

    detected_experience_years = max(0, int(extract_experience_llm(resume_text) if use_llm else extract_experience(resume_text)))
    required_years = max(0, int(experience_requirement or 0))
    if required_years == 0:
        experience_score = 100.0
        experience_reason = "No experience requirement configured."
    else:
        experience_score = _clamp_score((detected_experience_years / required_years) * 100.0)
        if detected_experience_years >= required_years:
            experience_reason = "Experience requirement satisfied."
        else:
            experience_reason = f"Required {required_years} years, found {detected_experience_years}."

    detected_education_level = _normalize_education(extract_education_llm(resume_text) if use_llm else extract_education(resume_text))
    required_education_level = _normalize_education(education_requirement)
    required_education_rank = _education_rank(required_education_level)
    detected_education_rank = _education_rank(detected_education_level)
    if required_education_rank is None:
        education_score = 100.0
        education_reason = "No education requirement configured."
    elif detected_education_rank is None:
        education_score = 0.0
        education_reason = f"Required {required_education_level}, no matching degree found."
    elif detected_education_rank >= required_education_rank:
        education_score = 100.0
        education_reason = "Education requirement satisfied."
    elif detected_education_rank == required_education_rank - 1:
        education_score = 50.0
        education_reason = (
            f"Required {required_education_level}, found {detected_education_level}; partial match only."
        )
    else:
        education_score = 0.0
        education_reason = f"Required {required_education_level}, found {detected_education_level}."

    resume_quality_score, resume_quality_reason = _resume_quality_score(resume_text)

    final_resume_score = _clamp_score(
        (weighted_skill_score * 0.50)
        + (semantic_score * 0.15)
        + (experience_score * 0.15)
        + (education_score * 0.10)
        + (academic_cutoff_score * 0.05)
        + (resume_quality_score * 0.05)
    )
    screening_band = _screening_band(final_resume_score)

    reasons = _resume_reasons(
        screening_band=screening_band,
        matched_skills=list(skill_match["matched_skills"]),
        missing_skills=list(skill_match["missing_skills"]),
        experience_score=experience_score,
        education_score=education_score,
        semantic_score=semantic_score,
        academic_cutoff_met=academic_cutoff_met,
        academic_cutoff_reason=academic_cutoff_reason,
        resume_quality_reason=resume_quality_reason,
    )

    return {
        "score_version": "v2",
        "screening_band": screening_band,
        "final_resume_score": final_resume_score,
        "weighted_skill_score": weighted_skill_score,
        "semantic_score": semantic_score,
        "experience_score": experience_score,
        "education_score": education_score,
        "resume_quality_score": resume_quality_score,
        "academic_cutoff_score": academic_cutoff_score,
        "academic_cutoff_met": academic_cutoff_met,
        "academic_cutoff_reason": academic_cutoff_reason,
        "min_academic_percent_required": max(0.0, float(min_academic_percent or 0.0)),
        "detected_academic_percent": detected_academic_percent,
        "detected_academic_level": detected_academic_level,
        "academic_percentages": academic_percentages,
        "matched_percentage": float(skill_match["matched_percentage"]),
        "matched_skills": list(skill_match["matched_skills"]),
        "missing_skills": list(skill_match["missing_skills"]),
        "detected_experience_years": detected_experience_years,
        "detected_education_level": detected_education_level,
        "reasons": reasons,
        "skill_score": weighted_skill_score,
        "education_reason": education_reason,
        "experience_reason": experience_reason,
        "resume_quality_reason": resume_quality_reason,
        "total_experience_detected": detected_experience_years,
    }


def compute_interview_scoring(technical_score: float, resume_score: float) -> dict[str, object]:
    """Aggregate technical and resume tracks into final interview outcome."""

    technical = _clamp_score(technical_score)
    resume = _clamp_score(resume_score)
    final = _clamp_score((technical * 0.65) + (resume * 0.35))
    return {
        "technical_score": technical,
        "resume_score": resume,
        "resume_score_used": resume,
        "final_score": final,
        "recommendation": _recommendation(final),
    }


def _answer_relevance(question: str, answer: str, jd_skills: Iterable[str] | None) -> tuple[float, int]:
    question_tokens = set(_tokenize(question))
    answer_text = answer or ""
    answer_tokens = set(_tokenize(answer_text))
    if not answer_tokens:
        return 0.0, 0

    overlap_ratio = len(question_tokens & answer_tokens) / max(1, len(question_tokens))
    relevance = overlap_ratio * 100.0

    skill_hits = 0
    normalized_skills = sorted({_normalize_skill(skill) for skill in (jd_skills or []) if _normalize_skill(skill)})
    if normalized_skills:
        for skill in normalized_skills:
            aliases = SKILL_ALIASES.get(skill, [skill])
            if any(_contains_skill(answer_text, alias) for alias in aliases):
                skill_hits += 1
        relevance += (skill_hits / len(normalized_skills)) * 15.0

    return _clamp_score(relevance), skill_hits


def _answer_completeness(answer: str) -> tuple[float, int]:
    answer_tokens = _tokenize(answer)
    word_count = len(answer_tokens)
    if word_count == 0:
        return 0.0, 0

    if word_count < 8:
        score = 20.0
    elif word_count < 20:
        score = 55.0
    elif word_count <= 80:
        score = 85.0
    elif word_count <= 140:
        score = 100.0
    else:
        score = 80.0

    action_hits = sum(1 for token in set(answer_tokens) if token in ACTION_RESULT_WORDS)
    score += min(15.0, action_hits * 5.0)
    if re.search(r"\d", answer or ""):
        score += 5.0
    return _clamp_score(score), word_count


def _answer_clarity(answer: str, word_count: int) -> float:
    if word_count == 0:
        return 0.0
    if word_count < 5:
        return 40.0

    tokens = _tokenize(answer)
    unique_ratio = len(set(tokens)) / max(1, len(tokens))
    sentences = [segment.strip() for segment in re.split(r"[.!?]+", answer or "") if segment.strip()]
    longest_sentence = max((len(_tokenize(segment)) for segment in sentences), default=0)

    clarity = 100.0
    if unique_ratio < 0.35:
        clarity -= 35.0
    elif unique_ratio < 0.50:
        clarity -= 15.0

    if len(sentences) <= 1 and word_count > 25:
        clarity -= 15.0
    if longest_sentence > 40:
        clarity -= 10.0
    return _clamp_score(clarity)


def _answer_time_fit(answer: str, allotted_seconds: int, time_taken_seconds: int) -> float:
    if not (answer or "").strip():
        return 0.0
    if allotted_seconds <= 0 or time_taken_seconds <= 0:
        return 70.0

    ratio = time_taken_seconds / max(1, allotted_seconds)
    if 0.40 <= ratio <= 0.95:
        return 100.0
    if 0.20 <= ratio < 0.40 or 0.95 < ratio <= 1.10:
        return 70.0
    return 40.0


def compute_answer_scorecard(
    question: str,
    answer: str,
    *,
    allotted_seconds: int = 0,
    time_taken_seconds: int = 0,
    jd_skills: Iterable[str] | None = None,
) -> dict[str, float | int]:
    """Return a structured 0-100 answer score and component breakdown."""

    normalized_answer = (answer or "").strip()
    if not normalized_answer:
        return {
            "overall_score": 0.0,
            "relevance": 0.0,
            "completeness": 0.0,
            "clarity": 0.0,
            "time_fit": 0.0,
            "word_count": 0,
            "skill_hits": 0,
        }

    relevance, skill_hits = _answer_relevance(question, normalized_answer, jd_skills)
    completeness, word_count = _answer_completeness(normalized_answer)
    clarity = _answer_clarity(normalized_answer, word_count)
    time_fit = _answer_time_fit(normalized_answer, allotted_seconds, time_taken_seconds)
    overall_score = _clamp_score(
        (relevance * 0.40) + (completeness * 0.25) + (clarity * 0.20) + (time_fit * 0.15)
    )
    return {
        "overall_score": overall_score,
        "relevance": relevance,
        "completeness": completeness,
        "clarity": clarity,
        "time_fit": time_fit,
        "word_count": word_count,
        "skill_hits": skill_hits,
    }