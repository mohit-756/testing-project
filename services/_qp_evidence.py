from __future__ import annotations

import re
from collections import OrderedDict
from collections.abc import Mapping
from dataclasses import asdict

# Date-range pattern: catches "Jan 2026 – Present", "March 2024 - Dec 2025", "2022 – 2023", etc.
_DATE_RANGE_RE = re.compile(
    r"""^\s*
    (?:
        (?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|
           jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)
        [\s,]+\d{4}
    |\d{4}
    )
    \s*(?:–|-|to)\s*
    (?:
        (?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|
           jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)
        [\s,]+\d{4}
    |\d{4}
    |present|current|now|ongoing
    )\s*$""",
    re.IGNORECASE | re.VERBOSE,
)

from services._qp_structs import (
    _ALL_CAPS_NAME_RE,
    _CITY_LOCATION_RE,
    AIML_TERMS,
    ARCHITECTURE_TERMS,
    BACKEND_TERMS,
    DATA_TERMS,
    EMAIL_PATTERN,
    EvidenceItem,
    FRONTEND_TERMS,
    LEADERSHIP_TERMS,
    METRIC_PATTERN,
    NAMEY_HEADER_PATTERN,
    PHONE_PATTERN,
    PlannerContext,
    RECENCY_TERMS,
    ROLE_FAMILY_KEYWORDS,
    StructuredJD,
    StructuredResume,
)
from services.resume_parser import parse_resume_text


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _dedupe(values: list[str], limit: int | None = None) -> list[str]:
    seen = OrderedDict()
    for value in values:
        cleaned = _clean(value)
        key = cleaned.lower()
        if cleaned and key not in seen:
            seen[key] = cleaned
        if limit and len(seen) >= limit:
            break
    return list(seen.values())


def _normalize_skill_token(value: str) -> str:
    token = _clean(value).lower()
    token = re.sub(r"[^a-z0-9+#./ ]+", "", token)
    return token.strip()


def _contains_metric(text: str | None) -> bool:
    return bool(METRIC_PATTERN.search(_clean(text)))


def _score_text_signal(text: str, keywords: set[str]) -> float:
    lowered = text.lower()
    hits = sum(1 for term in keywords if term in lowered)
    return min(1.0, hits / 3.0)


def _infer_years_band(text: str) -> str:
    match = re.search(r"(\d+)\+?\s*(?:years|yrs)", text.lower())
    if match:
        years = int(match.group(1))
        if years >= 12:
            return "12+"
        if years >= 8:
            return "8-11"
        if years >= 5:
            return "5-7"
        if years >= 2:
            return "2-4"
    return "0-2"


def _sanitize_evidence_text(value: str | None) -> str:
    cleaned = _clean(value)
    if not cleaned:
        return ""
    # Reject pure date ranges early: "Jan 2026 – Present", "2022 - 2023", etc.
    if _DATE_RANGE_RE.match(cleaned):
        return ""
    cleaned = EMAIL_PATTERN.sub("", cleaned)
    cleaned = PHONE_PATTERN.sub("", cleaned)
    if _CITY_LOCATION_RE.search(cleaned) and len(cleaned.split()) <= 6:
        return ""
    if _ALL_CAPS_NAME_RE.match(cleaned):
        return ""
    cleaned = re.sub(r"https?://\S+", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b(?:phone|mobile|email|gmail|contact|linkedin|address|location)\b.*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^[\-•*\d.)\s]+", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" -|,")
    if NAMEY_HEADER_PATTERN.match(cleaned) and len(cleaned.split()) <= 3:
        return ""
    if len(cleaned) < 12:
        return ""
    lowered = cleaned.lower()
    if any(token in lowered for token in ("curriculum vitae", "resume", "professional summary", "career objective")):
        return ""
    if sum(ch.isdigit() for ch in cleaned) >= max(6, len(cleaned) // 4):
        return ""
    if "|" in cleaned and len(cleaned.split("|")) >= 3 and not any(term in lowered for term in ("platform", "system", "pipeline", "service", "project", "engineer", "architect", "developer")):
        return ""
    return cleaned


def _split_evidence_fragments(lines: list[str]) -> list[str]:
    fragments: list[str] = []
    for raw in lines:
        text = str(raw or "")
        if not _clean(text):
            continue
        parts = re.split(r"[\u2022•]|(?<!\b[A-Z])[;]+|(?<=[.!?])\s+|\s{2,}", text)
        for part in parts:
            cleaned = _sanitize_evidence_text(part)
            if not cleaned:
                continue
            if len(cleaned) > 260 and ":" in cleaned:
                subparts = [seg for seg in re.split(r":\s+", cleaned) if _clean(seg)]
                for seg in subparts:
                    seg_clean = _sanitize_evidence_text(seg)
                    if seg_clean:
                        fragments.append(seg_clean)
                continue
            fragments.append(cleaned)
    return _dedupe(fragments, limit=36)


def _projectish_phrase(text: str) -> str:
    cleaned = _sanitize_evidence_text(text)
    if not cleaned:
        return ""
    lowered = cleaned.lower()
    if any(token in lowered for token in ("professional summary", "career objective", "hyderabad", "india", "guntur", "andhra pradesh")):
        return ""
    if _ALL_CAPS_NAME_RE.match(cleaned):
        return ""
    if NAMEY_HEADER_PATTERN.match(cleaned) or re.match(r"^[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,4}\s+(?:architect|engineer|developer|manager|head)$", cleaned):
        return ""

    # Only extract project names from actual noun phrases in the resume text.
    # NEVER invent project names from keyword combinations.
    head = re.split(r"[;:!?]", cleaned, maxsplit=1)[0]
    head = re.sub(r"\b(?:using|with|built|developed|implemented|designed|delivered|responsible for|worked on|at|for)\b.*", "", head, flags=re.IGNORECASE)
    head = re.sub(r"\s+", " ", head).strip(" -")
    words = head.split()
    if len(words) >= 2:
        phrase = " ".join(words[:6])
        if not NAMEY_HEADER_PATTERN.match(phrase) and not _CITY_LOCATION_RE.search(phrase):
            return phrase

    noun_chunks = re.findall(r"([A-Za-z][A-Za-z0-9+#./-]*(?:\s+[A-Za-z0-9+#./-]+){1,4}\s+(?:platform|system|pipeline|dashboard|service|application|portal|engine|workspace|lakehouse))", cleaned)
    if noun_chunks:
        return _clean(noun_chunks[0])
    return ""


def _evidence_priority(item: EvidenceItem) -> float:
    return round(item.kind_weight + item.recency + item.strength + item.measurable + (0.35 if item.label else 0.0), 3)


def _build_evidence_items(lines: list[str], source: str, known_skills: list[str]) -> list[EvidenceItem]:
    items: list[EvidenceItem] = []
    raw_fragments = _split_evidence_fragments(lines)
    ranked_fragments = sorted(
        enumerate(raw_fragments),
        key=lambda pair: (
            (1.0 if any(term in pair[1].lower() for term in RECENCY_TERMS | {"present", "current", "ongoing"}) else 0.0)
            + (0.9 if _projectish_phrase(pair[1]) else 0.0)
            + (0.45 if _contains_metric(pair[1]) else 0.0)
            + (0.35 if any(term in pair[1].lower() for term in ("ai", "ml", "nlp", "react", "frontend", "backend", "databricks", "lakehouse", "pipeline")) else 0.0),
            -pair[0],
        ),
        reverse=True,
    )
    fragments = [text for _, text in ranked_fragments]
    total = max(1, len(fragments))
    for index, line in enumerate(fragments[:14]):
        recency_rank = 1.0 - (index / total) * 0.55
        if any(term in line.lower() for term in RECENCY_TERMS):
            recency_rank = max(recency_rank, 0.95)
        skill_hits = [skill for skill in known_skills if _normalize_skill_token(skill) and _normalize_skill_token(skill) in _normalize_skill_token(line)]
        strength = min(1.0, 0.38 + (0.1 * len(skill_hits)) + (0.12 if _contains_metric(line) else 0.0))
        measurable = 0.8 if _contains_metric(line) else 0.0
        kind_weight = 1.2 if _projectish_phrase(line) else (0.95 if measurable else 0.55)
        items.append(
            EvidenceItem(
                text=line,
                source=source,
                recency=round(max(0.2, recency_rank), 3),
                strength=round(strength, 3),
                leadership=round(_score_text_signal(line, LEADERSHIP_TERMS), 3),
                architecture=round(_score_text_signal(line, ARCHITECTURE_TERMS), 3),
                measurable=measurable,
                kind_weight=kind_weight,
                label=_projectish_phrase(line),
                skills=_dedupe(skill_hits),
            )
        )
    items.sort(key=_evidence_priority, reverse=True)
    return items


def extract_structured_resume(resume_text: str) -> StructuredResume:
    parsed = parse_resume_text(resume_text or "")
    skills = _dedupe([str(item) for item in (parsed.get("skills") or [])], limit=18)
    raw_lines = [_clean(line) for line in (resume_text or "").splitlines() if _clean(line)]
    experience_lines = [str(item) for item in (parsed.get("experience") or [])]
    project_lines = [str(item) for item in (parsed.get("projects") or [])]
    project_lines += [
        line for line in raw_lines
        if any(token in line.lower() for token in ("project", "system", "platform", "dashboard", "analysis", "pipeline", "lakehouse"))
        and (":" in line or len(line.split()) <= 18)
    ][:12]
    experience_lines += [
        line for line in raw_lines
        if any(token in line.lower() for token in ("developed", "built", "implemented", "designed", "led", "managed", "integrated", "optimized", "collaborated"))
    ][:16]
    measurable_lines = [str(item) for item in (parsed.get("measurable_impacts") or [])]

    experiences = _build_evidence_items(experience_lines + measurable_lines[:4], "experience", skills)
    projects = _build_evidence_items(project_lines + measurable_lines[:4], "project", skills)

    all_items = experiences + projects
    leadership_signal = round(sum(item.leadership for item in all_items) / len(all_items), 3) if all_items else 0.0
    architecture_signal = round(sum(item.architecture for item in all_items) / len(all_items), 3) if all_items else 0.0
    summary = _sanitize_evidence_text(parsed.get("summary") or "")
    years_band = _infer_years_band((summary or "") + "\n" + (resume_text or ""))

    return StructuredResume(
        summary=summary,
        skills=skills,
        experiences=experiences,
        projects=projects,
        certifications=[str(item) for item in (parsed.get("certifications") or [])][:5],
        leadership_signal=leadership_signal,
        architecture_signal=architecture_signal,
        inferred_years_band=years_band,
    )


def extract_structured_jd(jd_title: str | None, jd_skill_scores: Mapping[str, int] | None) -> StructuredJD:
    required_skills = _dedupe([str(skill) for skill in (jd_skill_scores or {}).keys()], limit=18)
    title = _clean(jd_title or "Interview")
    all_keywords = _dedupe([title] + required_skills)
    joined = " ".join(all_keywords).lower()
    return StructuredJD(
        title=title,
        required_skills=required_skills,
        keywords=all_keywords,
        leadership_signal=round(_score_text_signal(joined, LEADERSHIP_TERMS), 3),
        architecture_signal=round(_score_text_signal(joined, ARCHITECTURE_TERMS), 3),
    )


def infer_role_family(title: str, resume: StructuredResume, jd: StructuredJD) -> tuple[str, str]:
    combined = " ".join([
        title or "",
        jd.title,
        " ".join(jd.required_skills),
        resume.summary,
        " ".join(item.text for item in resume.projects[:4]),
        " ".join(item.text for item in resume.experiences[:4]),
    ]).lower()

    for family in ("practice_head", "manager", "architect", "lead", "senior_engineer", "engineer"):
        if any(keyword in combined for keyword in ROLE_FAMILY_KEYWORDS[family]):
            seniority = family if family not in {"engineer", "senior_engineer"} else family
            return family, seniority

    if resume.leadership_signal >= 0.58 and resume.inferred_years_band in {"8-11", "12+"}:
        return "manager", "manager"
    if resume.architecture_signal >= 0.52 and resume.inferred_years_band in {"5-7", "8-11", "12+"}:
        return "architect", "architect"
    if resume.inferred_years_band in {"8-11", "12+"}:
        return "lead", "lead"
    if resume.inferred_years_band in {"5-7"}:
        return "senior_engineer", "senior_engineer"
    return "engineer", "engineer"


def role_track(context: PlannerContext) -> str:
    blob = " ".join([
        context.role_family,
        context.seniority,
        context.title,
        context.jd.title,
        " ".join(context.jd.required_skills),
        context.resume.summary,
        " ".join(item.text for item in (context.resume.projects[:4] + context.resume.experiences[:4])),
    ]).lower()
    normalized = f" {re.sub(r'[^a-z0-9+#./]+', ' ', blob)} "

    def _score(terms: set[str]) -> int:
        return sum(2 if f" {term} " in normalized else 0 for term in terms if " " in term) + sum(1 for term in terms if " " not in term and f" {term} " in normalized)

    frontend_score = _score(FRONTEND_TERMS)
    aiml_score = _score(AIML_TERMS)
    data_score = _score(DATA_TERMS)
    backend_score = _score(BACKEND_TERMS)

    if "ai interview system" in normalized or "resume screening system" in normalized or "screening" in normalized and "model" in normalized:
        aiml_score += 2
    if "databricks" in normalized or "lakehouse" in normalized or "unity catalog" in normalized:
        data_score += 2

    if data_score >= max(frontend_score, backend_score, aiml_score) and data_score >= 2:
        return "data"
    if aiml_score >= max(frontend_score, backend_score) and aiml_score >= 2:
        return "aiml"
    if frontend_score >= max(backend_score, data_score, aiml_score) and frontend_score >= 2:
        return "frontend"
    return "backend"


def get_resume_module(resume: StructuredResume) -> str:
    ordered = sorted(resume.projects + resume.experiences, key=_evidence_priority, reverse=True)
    for item in ordered:
        if item.label:
            return item.label
    return "your recent work"


def distribution_for_role(role_family: str, total_questions: int, project_ratio: float = 0.5) -> dict[str, int]:
    """
    Distribute questions based on project_ratio.
    
    Args:
        role_family: The role type (engineer, manager, etc.)
        total_questions: Total number of questions to generate
        project_ratio: Ratio of project-based questions (0.0-1.0). 
                     0.8 = 80% project questions, 20% theory (deep_dive/architecture/etc.)
    
    Categories:
        - PROJECT: Resume-based project questions
        - THEORY: deep_dive, architecture, leadership, behavioral
    
    Example: 5 questions, 0.8 ratio → 4 project, 1 theory
             5 questions, 0.6 ratio → 3 project, 2 theory
    """
    _ = role_family
    remaining = max(0, total_questions - 1)
    project_ratio = max(0.0, min(1.0, project_ratio))

    num_project = max(1, round(remaining * project_ratio))
    num_theory = remaining - num_project
    num_theory = max(0, num_theory)

    base = {"project": num_project}
    if num_theory > 0:
        base["deep_dive"] = 0
        base["architecture"] = 0
        base["leadership"] = 0
        base["behavioral"] = 0

        theory_slots = num_theory
        for key in ("deep_dive", "architecture", "leadership", "behavioral"):
            if theory_slots <= 0:
                break
            base[key] = 1
            theory_slots -= 1

    return {k: v for k, v in base.items() if v > 0}


def make_topic_candidates(resume: StructuredResume, jd: StructuredJD, role_family: str) -> list[dict[str, object]]:
    candidates: list[dict[str, object]] = []
    resume_skill_set = {_normalize_skill_token(item): item for item in resume.skills}
    jd_skill_set = {_normalize_skill_token(item): item for item in jd.required_skills}

    def _candidate_from_item(item: EvidenceItem, kind: str, priority_source: str, extra: float = 0.0) -> dict[str, object]:
        label = item.label or item.text
        role_alignment = 0.72 + (0.15 if kind in {"architecture", "leadership"} else 0.0)
        if kind == "architecture" and role_family == "architect":
            role_alignment = max(role_alignment, 0.92)
        if kind == "leadership" and role_family in {"lead", "manager", "practice_head"}:
            role_alignment = max(role_alignment, 0.9)
        return {
            "kind": kind,
            "label": label,
            "priority_source": priority_source,
            "score": round(_evidence_priority(item) + extra, 3),
            "resume_alignment": round(min(1.0, 0.58 + item.strength * 0.35), 3),
            "jd_alignment": round(0.45 + (0.12 * len(item.skills)), 3),
            "role_alignment": round(role_alignment, 3),
            "evidence": [item],
        }

    for item in resume.projects:
        candidates.append(_candidate_from_item(item, "project", "recent_project" if item.recency >= 0.75 else "resume_strength", 0.45))
    for item in resume.experiences[:8]:
        if item.label or item.measurable:
            candidates.append(_candidate_from_item(item, "project", "resume_strength", 0.25))
        if item.architecture >= 0.25:
            candidates.append(_candidate_from_item(item, "architecture", "architecture_signal", 0.35))
        if item.leadership >= 0.25:
            candidates.append(_candidate_from_item(item, "leadership", "leadership_signal", 0.35))

    overlap_keys = [key for key in resume_skill_set if key in jd_skill_set]
    jd_only_keys = [key for key in jd_skill_set if key not in resume_skill_set]
    for key in overlap_keys:
        canonical = resume_skill_set[key]
        evidence = [item for item in (resume.experiences + resume.projects) if canonical in item.skills]
        if evidence:
            best = sorted(evidence, key=_evidence_priority, reverse=True)[0]
            candidates.append({
                "kind": "skill_anchor",
                "label": best.label or canonical,
                "priority_source": "jd_resume_overlap",
                "score": round(_evidence_priority(best) + 0.25, 3),
                "resume_alignment": 0.92,
                "jd_alignment": 1.0,
                "role_alignment": 0.78,
                "evidence": [best],
                "focus_skill": canonical,
            })
    for key in jd_only_keys[:2]:
        canonical = jd_skill_set[key]
        candidates.append({
            "kind": "skill_gap",
            "label": canonical,
            "priority_source": "jd_gap_probe",
            "score": 0.95,
            "resume_alignment": 0.1,
            "jd_alignment": 0.95,
            "role_alignment": 0.7,
            "evidence": [],
            "focus_skill": canonical,
        })

    if role_family in {"architect", "lead", "manager", "practice_head"}:
        for item in resume.projects + resume.experiences:
            if item.architecture >= 0.3:
                candidates.append(_candidate_from_item(item, "architecture", "architecture_signal", 0.4))
            if item.leadership >= 0.3:
                candidates.append(_candidate_from_item(item, "leadership", "leadership_signal", 0.4))

    deduped: list[dict[str, object]] = []
    seen: set[tuple[str, str]] = set()
    for item in sorted(candidates, key=lambda x: (float(x["score"]), float(x["resume_alignment"])), reverse=True):
        key = (str(item["kind"]), _normalize_skill_token(str(item["label"])))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
        if len(deduped) >= 24:
            break
    return deduped


__all__ = [
    "_ALL_CAPS_NAME_RE",
    "_CITY_LOCATION_RE",
    "_clean",
    "_contains_metric",
    "_dedupe",
    "_evidence_priority",
    "_normalize_skill_token",
    "_projectish_phrase",
    "_sanitize_evidence_text",
    "distribution_for_role",
    "extract_structured_jd",
    "extract_structured_resume",
    "get_resume_module",
    "infer_role_family",
    "make_topic_candidates",
    "role_track",
]
