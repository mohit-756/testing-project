"""LLM-first interview question generation with natural flow (v2 approach)."""
from __future__ import annotations

from typing import Any

import json
import logging
import re
from collections import OrderedDict
from collections.abc import Mapping
from dataclasses import asdict, dataclass

from services.llm.client import _clean_json, _get_client, _llm_model, _llm_premium_model, _llm_provider
from services.question_plan import build_question_plan
from services.resume_parser import parse_resume_text

logger = logging.getLogger(__name__)

# Pattern to detect pure date-range strings that should never be used as project names
_DATE_RANGE_STR_RE = re.compile(
    r"""(?:^|\s)
    (?:
        (?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|
           jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)
        [\s,]+\d{4}
    |\d{4}
    )
    \s*(?:–|-|to|/)\s*
    (?:
        (?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|
           jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)
        [\s,]+\d{4}
    |\d{4}
    |present|current|now|ongoing
    )(?:\s|$)""",
    re.IGNORECASE | re.VERBOSE,
)


def _is_date_range_string(text: str | None) -> bool:
    """Return True if the text is primarily a date range with no substantive content."""
    cleaned = re.sub(r"\s+", " ", str(text or "")).strip()
    if not cleaned:
        return False
    stripped = _DATE_RANGE_STR_RE.sub("", cleaned).strip(" ,-|")
    return len(stripped) < 6


# ============================================================================
# V2 SYSTEM PROMPT - Natural Flow, Resume-Grounded
# ============================================================================

LLM_QUESTION_SYSTEM_PROMPT = """You are a senior technical interviewer. 
Generate interview questions that flow naturally, like a real conversation, grounded in the candidate's actual resume, projects, and the job description.

CORE PRINCIPLES

Every question must:
1. Reference SPECIFIC projects, technologies, or achievements from this resume
2. Be answerable ONLY by someone who did that exact work
3. Be clear enough for an interviewer to understand and follow up on
4. End with exactly ONE question mark
5. Be conversational, not academic

Never:
- Ask about skills NOT on the resume or JD
- Invent project names, company names, or outcomes
- Use vague phrases like "in your project" or "walk me through"
- Ask generic questions that fit any candidate (like "What is X?")

WHAT A GOOD QUESTION LOOKS LIKE

✓ Good: "In your Data Pipeline project, you mentioned reducing latency by 40%. What was the bottleneck you identified first?"
✗ Bad: "Tell me about a challenging project you worked on."

✓ Good: "You built the Admin Dashboard with React. What state management decisions did you make, and why?"
✗ Bad: "What is your experience with React?"

✓ Good: "You said the Payment Service went down during peak hours. Walk me through what you found in the logs."
✗ Bad: "How do you handle failures?"

INTERVIEW FLOW (Natural, not rigid)

Think of a real interview:
1. Opener (1 question): "Tell me about your background and what drew you to this role."
2. Deep Dive into Strongest Project (2-3 questions): Execution details, decisions, what went wrong
3. Secondary Project or Adjacent Skill (1-2 questions): Different angle—scaling, debugging, design
4. Behavioral / Soft Skills (1 question): How you collaborate, handle pressure, make trade-offs
5. Role-Specific (0-1 question): If design role, ask about system design. If lead, ask about mentoring.

Total: 6-8 questions that feel like a conversation.

DISTRIBUTION (Natural, not forced)

Aim for something like this (out of 8 questions):
- Opener: 1
- Project execution: 2-3
- Decision/trade-off: 1-2
- Debugging/failure: 1
- Behavioral/soft skills: 1
- Role-specific (design/scaling/mentoring): 0-1

This is guidance, not law. If no leadership signals, skip that. If all work in one project, go deep there.

QUESTION CHARACTERISTICS BY TYPE

Opener: Open-ended, conversational, sets tone.
  Example: "Walk me through your most recent role and what you're looking for next."

Project Execution: Specific to their work, ask about HOW not WHAT.
  Example: "You reduced latency by 40%. Walk me through what you measured and how."

Decision/Trade-off: Get at their reasoning.
  Example: "You used PostgreSQL. Why not NoSQL for that use case?"

Debugging/Failure: Shows problem-solving.
  Example: "The service was down for 2 hours. Walk me through your debugging steps."

Behavioral/Soft Skills: How they work with others.
  Example: "Tell me about a time you had to push back on a requirement."

Role-Specific: Design/scaling/mentoring (if relevant).
  Example: "How would you scale that system to 100x users?"

FORMAT (JSON)

Return ONLY valid JSON, no preamble:

{
  "questions": [
    {
      "text": "one question, specific project/outcome from resume",
      "type": "opener|project|decision|debugging|behavioral|role_specific",
      "focus": "what you're assessing",
      "project": "project name from resume (if applicable)",
      "intent": "why you're asking this",
      "reference_answer": "what a strong answer would include"
    }
  ]
}

QUALITY CHECKLIST

Before returning, verify:
- Every question references a REAL project or skill from the resume
- Could an interviewer understand each question without context?
- Is each question answerable ONLY by someone who did that work?
- Does the flow feel natural (not rigid)?
- Is there behavioral / soft skill coverage?
- No duplicate concepts or phrasing?
- Each question has exactly one "?"?

TONE

Professional but conversational. Curious, not interrogating. Technical but accessible.
Assume the interviewer is smart but may not know all the details of the candidate's project."""


@dataclass
class StructuredQuestionInput:
    role: str
    role_title: str
    role_family: str
    seniority: str
    experience_level: str
    jd_title: str
    jd_summary: str
    jd_core_skills: list[str]
    jd_secondary_skills: list[str]
    jd_responsibilities: list[str]
    jd_skills: list[str]
    jd_skill_weights: dict[str, int]
    resume_summary: str
    resume_recent_roles: list[str]
    resume_skills: list[str]
    resume_projects: list[str]
    resume_project_technologies: list[str]
    resume_experiences: list[str]
    resume_leadership_signals: list[str]
    resume_measurable_impact: list[str]
    certifications: list[str]
    overlap_skills: list[str]
    resume_only_skills: list[str]
    jd_only_skills: list[str]


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def _clean(value: str | None) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _normalize_token(value: str | None) -> str:
    return re.sub(r"[^a-z0-9+#./ %:-]+", "", _clean(value).lower()).strip()


def _similarity_key(value: str | None) -> str:
    lowered = _normalize_token(value)
    lowered = re.sub(r"\b(tell me about|walk me through|describe|explain|how would you|how do you|in your|for your|can you)\b", "", lowered)
    return re.sub(r"\s+", " ", lowered).strip()


def _dedupe_strings(values: list[str], *, limit: int | None = None) -> list[str]:
    seen: OrderedDict[str, str] = OrderedDict()
    for value in values:
        cleaned = _clean(value)
        if not cleaned:
            continue
        key = cleaned.lower()
        if key not in seen:
            seen[key] = cleaned
        if isinstance(limit, int):
            if len(seen) >= limit:
                break
    return list(seen.values())


def _opening_pattern(text: str | None) -> str:
    words = re.findall(r"[a-z0-9']+", _normalize_token(text))
    return " ".join(words[:2])


def _build_jd_text(jd_title: str | None, jd_skill_scores: Mapping[str, int] | None, jd_text: str | None = None) -> str:
    if _clean(jd_text):
        return _clean(jd_text)
    skills = [f"{skill} ({int(weight)})" for skill, weight in (jd_skill_scores or {}).items() if _clean(skill)]
    sections = [f"Role: {_clean(jd_title or 'Interview Role')}"]
    if skills:
        sections.append("Required skills: " + ", ".join(skills))
    return "\n".join(sections)


def _infer_experience_level(summary: str, resume_text: str) -> str:
    combined = f"{summary}\n{resume_text}".lower()
    match = re.search(r"(\d+)\+?\s*(?:years|yrs)", combined)
    if match:
        years = int(match.group(1))
        if years >= 12:
            return "executive"
        if years >= 8:
            return "staff_plus"
        if years >= 5:
            return "senior"
        if years >= 2:
            return "mid"
        return "junior"
    if any(term in combined for term in ("practice head", "director", "vp", "vice president")):
        return "executive"
    if any(term in combined for term in ("architect", "principal", "staff", "lead")):
        return "staff_plus"
    if "senior" in combined:
        return "senior"
    return "junior"


def _extract_inline_section_values(text: str, label: str) -> list[str]:
    pattern = re.compile(rf"{label}\s*:\s*(.+?)(?=(?:\n\s*[A-Za-z][A-Za-z ]*\s*:)|$)", re.IGNORECASE | re.DOTALL)
    matches = pattern.findall(text or "")
    values: list[str] = []
    for match in matches:
        for part in re.split(r"[,;\n]\s*", match):
            cleaned = _clean(part)
            if cleaned:
                values.append(cleaned)
    return _dedupe_strings(values)


def _augment_resume_skills(parsed_resume: dict[str, Any], resume_text: str, jd_skill_scores: Mapping[str, int] | None) -> list[str]:
    detected = [str(item) for item in (parsed_resume.get("skills") or [])]
    inline_skills = _extract_inline_section_values(resume_text, "skills")
    lowered_resume = _normalize_token(resume_text)
    jd_mentions = [str(skill) for skill in (jd_skill_scores or {}).keys() if _normalize_token(skill) and _normalize_token(skill) in lowered_resume]
    return _dedupe_strings(detected + inline_skills + jd_mentions, limit=24)


def _augment_resume_projects(parsed_resume: dict[str, Any], resume_text: str) -> list[str]:
    projects = [str(item) for item in (parsed_resume.get("projects") or [])]
    all_projects = projects + _extract_inline_section_values(resume_text, "projects")
    filtered = [p for p in all_projects if not _is_date_range_string(p)]
    return _dedupe_strings(filtered, limit=10)


def _augment_resume_experiences(parsed_resume: dict[str, Any], resume_text: str) -> list[str]:
    experience = [str(item) for item in (parsed_resume.get("experience") or [])]
    all_exp = experience + _extract_inline_section_values(resume_text, "experience")
    filtered = [e for e in all_exp if not _is_date_range_string(e)]
    return _dedupe_strings(filtered, limit=10)


def _augment_certifications(parsed_resume: dict[str, Any], resume_text: str) -> list[str]:
    certs = [str(item) for item in (parsed_resume.get("certifications") or [])]
    return _dedupe_strings(certs + _extract_inline_section_values(resume_text, "certifications"), limit=6)


def _extract_jd_responsibilities(jd_text: str, jd_title: str | None) -> list[str]:
    lines = [line.strip(" -*\t") for line in re.split(r"[\n\r]+", jd_text or "") if _clean(line)]
    keep: list[str] = []
    for line in lines:
        lowered = line.lower()
        if jd_title and _clean(jd_title).lower() == lowered:
            continue
        if any(token in lowered for token in ("responsib", "own", "design", "build", "lead", "manage", "deliver", "stakeholder", "architect", "optimi", "mentor", "develop", "implement")):
            keep.append(_clean(line))
    if not keep:
        sentences = re.split(r"(?<=[.!?])\s+", jd_text or "")
        keep = [_clean(sentence) for sentence in sentences if any(token in sentence.lower() for token in ("design", "build", "lead", "manage", "deliver", "own", "mentor", "stakeholder", "architect"))]
    return _dedupe_strings(keep, limit=8)


def _split_core_secondary_skills(jd_skill_scores: Mapping[str, int] | None) -> tuple[list[str], list[str]]:
    ordered = [(str(skill), int(weight)) for skill, weight in (jd_skill_scores or {}).items() if _clean(skill)]
    ordered.sort(key=lambda item: item[1], reverse=True)
    core = [ordered[i][0] for i in range(min(6, len(ordered)))]
    secondary = [ordered[i][0] for i in range(min(6, len(ordered)), min(12, len(ordered)))]
    return _dedupe_strings(core, limit=6), _dedupe_strings(secondary, limit=6)


def _extract_project_technologies(projects: list[str], resume_skills: list[str]) -> list[str]:
    techs: list[str] = []
    normalized_skills = [skill for skill in resume_skills if _normalize_token(skill)]
    for project in projects:
        lowered = _normalize_token(project)
        for skill in normalized_skills:
            token = _normalize_token(skill)
            if token and token in lowered:
                techs.append(skill)
    return _dedupe_strings(techs, limit=12)


def _extract_leadership_signals(resume_text: str, resume_experiences: list[str], resume_projects: list[str]) -> list[str]:
    pool = resume_experiences + resume_projects + [line.strip() for line in (resume_text or "").splitlines() if _clean(line)]
    signals = [item for item in pool if any(term in item.lower() for term in ("led", "lead", "mentored", "stakeholder", "roadmap", "hiring", "managed", "governance", "delivery", "strategy", "practice", "director", "head"))]
    return _dedupe_strings(signals, limit=8)


def _extract_measurable_impact(resume_text: str, resume_experiences: list[str], resume_projects: list[str]) -> list[str]:
    pool = resume_experiences + resume_projects + [line.strip() for line in (resume_text or "").splitlines() if _clean(line)]
    pattern = re.compile(r"(\b\d+[\d,.]*\+?%?\b|\b\d+x\b|\b\d+[\d,.]*\s*(?:users|clients|services|teams|engineers|apps|pipelines|projects|days|months|weeks|hours)\b)", re.IGNORECASE)
    impacts = [item for item in pool if pattern.search(item)]
    return _dedupe_strings(impacts, limit=8)


def _is_senior_profile(structured_input: StructuredQuestionInput) -> bool:
    seniority_blob = " ".join([
        structured_input.role_family,
        structured_input.seniority,
        structured_input.experience_level,
        structured_input.role_title,
    ]).lower()
    return any(term in seniority_blob for term in ("senior", "lead", "manager", "head", "director", "vp", "practice", "staff", "principal", "executive")) or structured_input.role_family in {"lead", "manager", "practice_head"}


def _is_architect_profile(structured_input: StructuredQuestionInput) -> bool:
    blob = " ".join([
        structured_input.role_family,
        structured_input.role_title,
        structured_input.jd_title,
        " ".join(structured_input.jd_core_skills),
        " ".join(structured_input.jd_responsibilities),
    ]).lower()
    return any(term in blob for term in ("architect", "architecture", "system design", "distributed", "trade-off", "scalab", "databricks"))


def _structured_role_track(structured_input: StructuredQuestionInput) -> str:
    tokens = re.sub(
        r"[^a-z0-9+#./]+",
        " ",
        " ".join([
            structured_input.role_family,
            structured_input.role_title,
            structured_input.jd_title,
            " ".join(structured_input.jd_core_skills),
            " ".join(structured_input.resume_projects),
            " ".join(structured_input.resume_recent_roles),
        ]).lower(),
    )
    padded = f" {tokens} "

    def _has(*terms: str) -> bool:
        return any(f" {term} " in padded for term in terms)

    frontend = sum(1 for term in ("frontend", "react", "javascript", "typescript", "ui", "component", "responsive") if _has(term))
    data = sum(1 for term in ("databricks", "lakehouse", "spark", "pipeline", "warehouse", "governance", "unity catalog") if _has(term))
    aiml = sum(1 for term in ("aiml", "ml", "nlp", "llm", "model", "mlops", "rag", "screening", "scoring", "ranking", "proctoring") if _has(term))
    if _has("ai", "resume screening", "ai screening", "ai interview"):
        aiml += 2
    if data >= max(frontend, aiml) and data >= 2:
        return "data"
    if aiml >= max(frontend, data) and aiml >= 2:
        return "aiml"
    if frontend >= 2:
        return "frontend"
    return "backend"


def _planner_meta_for_structured_input(
    *,
    resume_text: str,
    jd_title: str | None,
    jd_skill_scores: Mapping[str, int] | None,
) -> dict[str, Any]:
    planner_bundle = build_question_plan(
        resume_text=resume_text,
        jd_title=jd_title,
        jd_skill_scores=jd_skill_scores or {},
        question_count=8,
    ) or {}
    planner_meta = planner_bundle.get("meta") if isinstance(planner_bundle, dict) else {}
    return planner_meta if isinstance(planner_meta, dict) else {}


# ============================================================================
# STRUCTURED INPUT BUILDING
# ============================================================================

def build_structured_question_input(
    *,
    resume_text: str,
    jd_title: str | None,
    jd_skill_scores: Mapping[str, int] | None,
    jd_text: str | None = None,
) -> StructuredQuestionInput:
    planner_meta = _planner_meta_for_structured_input(
        resume_text=resume_text,
        jd_title=jd_title,
        jd_skill_scores=jd_skill_scores,
    )
    parsed_resume = parse_resume_text(resume_text or "")
    structured_resume = planner_meta.get("structured_resume") if isinstance(planner_meta, dict) else {}
    structured_jd = planner_meta.get("structured_jd") if isinstance(planner_meta, dict) else {}

    resume_skills = _augment_resume_skills(parsed_resume, resume_text or "", jd_skill_scores)
    if not resume_skills:
        resume_skills = _dedupe_strings([str(item) for item in (structured_resume.get("skills") or [])], limit=24)
    jd_skills = _dedupe_strings([str(item) for item in ((jd_skill_scores or {}).keys() or structured_jd.get("required_skills") or [])], limit=20)

    resume_skill_keys = {_normalize_token(item): item for item in resume_skills}
    jd_skill_keys = {_normalize_token(item): item for item in jd_skills}
    overlap = [resume_skill_keys[key] for key in resume_skill_keys if key in jd_skill_keys]
    resume_only = [resume_skill_keys[key] for key in resume_skill_keys if key not in jd_skill_keys]
    jd_only = [jd_skill_keys[key] for key in jd_skill_keys if key not in resume_skill_keys]

    role_family = str(planner_meta.get("role_family") or "engineer")
    seniority = str(planner_meta.get("seniority") or role_family)
    jd_summary = _build_jd_text(jd_title=jd_title, jd_skill_scores=jd_skill_scores, jd_text=jd_text)
    resume_summary = _clean(parsed_resume.get("summary") or structured_resume.get("summary") or "")
    resume_projects = _augment_resume_projects(parsed_resume, resume_text or "")
    resume_experiences = _augment_resume_experiences(parsed_resume, resume_text or "")
    jd_core_skills, jd_secondary_skills = _split_core_secondary_skills(jd_skill_scores)

    return StructuredQuestionInput(
        role=_clean(jd_title or structured_jd.get("title") or "Interview Role"),
        role_title=_clean(jd_title or structured_jd.get("title") or "Interview Role"),
        role_family=role_family,
        seniority=seniority,
        experience_level=_infer_experience_level(resume_summary, resume_text or ""),
        jd_title=_clean(jd_title or structured_jd.get("title") or "Interview Role"),
        jd_summary=jd_summary,
        jd_core_skills=jd_core_skills,
        jd_secondary_skills=jd_secondary_skills,
        jd_responsibilities=_extract_jd_responsibilities(jd_summary, jd_title),
        jd_skills=jd_skills,
        jd_skill_weights={_clean(k): int(v) for k, v in (jd_skill_scores or {}).items() if _clean(k)},
        resume_summary=resume_summary,
        resume_recent_roles=resume_experiences[:5],
        resume_skills=resume_skills,
        resume_projects=resume_projects,
        resume_project_technologies=_extract_project_technologies(resume_projects, resume_skills),
        resume_experiences=resume_experiences,
        resume_leadership_signals=_extract_leadership_signals(resume_text or "", resume_experiences, resume_projects),
        resume_measurable_impact=_extract_measurable_impact(resume_text or "", resume_experiences, resume_projects),
        certifications=_augment_certifications(parsed_resume, resume_text or ""),
        overlap_skills=_dedupe_strings(overlap, limit=12),
        resume_only_skills=_dedupe_strings(resume_only, limit=12),
        jd_only_skills=_dedupe_strings(jd_only, limit=12),
    )


# ============================================================================
# V2 PROMPT CONSTRUCTION - Simpler, Natural
# ============================================================================

def _llm_user_prompt_v2(structured_input: StructuredQuestionInput, question_count: int, retry_note: str | None = None) -> str:
    """
    Build user prompt with evidence snapshot and clear instructions.
    Focus on: what we know about the candidate, what we want, constraints.
    """
    projects = structured_input.resume_projects or []
    roles = structured_input.resume_recent_roles or []
    skills = structured_input.overlap_skills or []
    impact = structured_input.resume_measurable_impact or []
    jd_title = structured_input.jd_title or "Role"
    
    # Build evidence snapshot (compact, readable)
    evidence_lines = []
    
    if projects:
        evidence_lines.append("CANDIDATE'S PROJECTS:")
        for p in projects[:5]:
            evidence_lines.append(f"  • {p}")
    
    if roles:
        evidence_lines.append("\nRECENT ROLES:")
        for r in roles[:3]:
            evidence_lines.append(f"  • {r}")
    
    if impact:
        evidence_lines.append("\nMEASURABLE OUTCOMES:")
        for m in impact[:3]:
            evidence_lines.append(f"  • {m}")
    
    if skills:
        evidence_lines.append("\nSKILLS (matches JD):")
        evidence_lines.append(f"  {', '.join(skills[:8])}")
    
    evidence_snapshot = "\n".join(evidence_lines)
    
    # Build instructions (simple, clear)
    instructions = [
        f"Generate exactly {question_count} questions for a {jd_title} interview.",
        "Ground each question in the candidate's resume projects, roles, or outcomes above.",
        "Make questions flow naturally—like a real conversation, not an interrogation.",
        "Include mix: 1 opener, 2-3 technical deep-dives, 1 behavioral, 1-2 role-specific.",
        "Each question = exactly 1 '?', clear language, 20-100 words.",
        "Reference specific project names, not 'your project.'",
        "Don't ask about skills that aren't on the resume above.",
    ]
    
    if retry_note:
        instructions.append(f"\nFEEDBACK FROM FIRST ATTEMPT:\n{retry_note}")
    
    return (
        "=== CANDIDATE EVIDENCE ===\n" 
        + evidence_snapshot 
        + "\n\n=== INSTRUCTIONS ===\n" 
        + "\n".join(instructions)
    )


# ============================================================================
# V2 NORMALIZATION - Simpler Type Mapping
# ============================================================================

def _normalize_question_type_v2(raw_type: str | None) -> str:
    """Map LLM's type to one of: opener, project, decision, debugging, behavioral, role_specific."""
    if not raw_type:
        return "project"
    
    normalized = _normalize_token(raw_type)
    
    mapping = {
        "opener": "opener",
        "intro": "opener",
        "introduction": "opener",
        "opening": "opener",
        "project": "project",
        "deep_dive": "project",
        "deepdive": "project",
        "execution": "project",
        "implementation": "project",
        "decision": "decision",
        "tradeoff": "decision",
        "trade_off": "decision",
        "why": "decision",
        "debugging": "debugging",
        "debug": "debugging",
        "failure": "debugging",
        "incident": "debugging",
        "error": "debugging",
        "behavioral": "behavioral",
        "behavior": "behavioral",
        "soft_skill": "behavioral",
        "communication": "behavioral",
        "collaboration": "behavioral",
        "leadership": "behavioral",
        "role_specific": "role_specific",
        "design": "role_specific",
        "architecture": "role_specific",
        "system_design": "role_specific",
        "scaling": "role_specific",
    }
    
    return mapping.get(normalized, "project")


# ============================================================================
# V2 VALIDATION - Natural Distribution Check
# ============================================================================

def _validate_question_set_v2(questions: list[dict[str, Any]], structured_input: StructuredQuestionInput, question_count: int) -> list[str]:
    """
    Validate questions for: resume grounding, natural distribution, clarity.
    Focus on: at least 1 opener, at least 1 behavioral, grounded technical depth.
    """
    issues: list[str] = []
    
    if len(questions) < max(2, question_count - 2):
        issues.append(f"insufficient_questions: got {len(questions)}, need ~{question_count}")
        return issues

    # Check 1: Every question grounded in resume
    resume_skills = {_normalize_token(s) for s in (structured_input.resume_skills or [])}
    resume_projects = {_normalize_token(p) for p in (structured_input.resume_projects or [])}
    resume_roles = {_normalize_token(r) for r in (structured_input.resume_recent_roles or [])}
    
    grounded_count = 0
    for q in questions:
        text_norm = _normalize_token(q.get("text", ""))
        
        # Check if it mentions a real project, role, or skill
        is_grounded = (
            q.get("type") == "opener" or
            any(proj and proj in text_norm for proj in resume_projects) or
            any(role and role in text_norm for role in resume_roles) or
            any(skill and skill in text_norm for skill in resume_skills) or
            bool(q.get("project"))
        )
        if is_grounded:
            grounded_count += 1
        elif q.get("type") not in {"behavioral", "opener"}:
            issues.append(f"question_not_grounded: {q.get('text', '')[:60]}")

    # Check 2: Type distribution (natural, not rigid)
    type_counts = {}
    for q in questions:
        qtype = q.get("type", "project")
        type_counts[qtype] = type_counts.get(qtype, 0) + 1

    has_opener = type_counts.get("opener", 0) >= 1
    has_behavioral = type_counts.get("behavioral", 0) >= 1
    has_technical = grounded_count >= 1

    if not has_opener and len(questions) > 1:
        issues.append("missing_opener")
    if not has_behavioral and len(questions) > 2:
        issues.append("missing_behavioral")
    if not has_technical and len(questions) > 1:
        issues.append("insufficient_technical_grounding")

    # Check 3: No weak phrases or duplicates
    seen_similarity = set()
    for q in questions:
        text = q.get("text", "")
        
        weak = ["tell me about yourself", "what is your experience with", "explain what", "what do you think about"]
        if any(phrase in text.lower() for phrase in weak):
            issues.append(f"weak_phrase: {text[:50]}")
        
        similarity = _similarity_key(text)
        if similarity in seen_similarity:
            issues.append("duplicate_question")
        seen_similarity.add(similarity)

    # Check 4: Question clarity
    for q in questions:
        text = q.get("text", "")
        if text.count("?") != 1:
            issues.append(f"wrong_question_mark_count: {text[:50]}")
        if len(text) < 15:
            issues.append(f"question_too_short: {text}")
        if len(text) > 150:
            issues.append(f"question_too_long: {text[:60]}")

    return _dedupe_strings(issues)


# ============================================================================
# V2 NORMALIZATION - Simplify LLM Output
# ============================================================================

def _normalize_llm_questions_v2(
    *,
    raw_questions: list[Any],
    structured_input: StructuredQuestionInput,
    question_count: int,
) -> list[dict[str, Any]]:
    """
    Normalize LLM output with simpler, more lenient criteria.
    Focus on: valid JSON structure, question clarity, no duplicates.
    """
    normalized = []
    seen_text = set()
    
    for item in raw_questions:
        if not isinstance(item, dict):
            continue
        
        text = _clean(item.get("text"))
        
        # Basic validation
        if not text or len(text) < 15 or text.count("?") != 1:
            continue
        
        # Reject if already seen
        similarity = _similarity_key(text)
        if similarity in seen_text:
            continue
        
        qtype = _normalize_question_type_v2(item.get("type"))
        
        q = {
            "text": text,
            "type": qtype,
            "focus": _clean(item.get("focus")) or qtype,
            "project": _clean(item.get("project")) or None,
            "intent": _clean(item.get("intent")) or f"Assess {qtype}.",
            "reference_answer": _clean(item.get("reference_answer")) or "A detailed, specific answer grounded in their experience.",
        }
        
        normalized.append(q)
        seen_text.add(similarity)
        
        if len(normalized) >= question_count + 3:
            break
    
    return normalized


# ============================================================================
# EXTRACTION & JSON PARSING
# ============================================================================

def _extract_json_object(raw: str) -> dict[str, Any]:
    """Extract JSON object from LLM response with multiple fallback strategies."""
    cleaned = _clean_json(raw or "")

    # Strategy 0: Let JSONDecoder find the first decodable JSON value in noisy text
    decoder = json.JSONDecoder()
    for match in re.finditer(r"[\[{]", cleaned):
        start = match.start()
        try:
            data, _ = decoder.raw_decode(cleaned[start:])
            if isinstance(data, dict):
                return data
            if isinstance(data, list) and data:
                return {"questions": data}
        except Exception:
            continue
    
    # Strategy 1: Find JSON object with proper brace matching
    start = cleaned.find("{")
    if start == -1:
        start = cleaned.find("[")
        if start == -1:
            raise ValueError("No JSON found in response")
    
    # Find matching closing brace
    brace_count = 0
    in_string = False
    escape = False
    end = start
    for i, char in enumerate(cleaned[start:], start):
        if escape:
            escape = False
            continue
        if char == "\\":
            escape = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if char == "{" or char == "[":
            brace_count += 1
        elif char == "}" or char == "]":
            brace_count -= 1
            if brace_count == 0:
                end = i + 1
                break
    
    cleaned = cleaned[start:end]
    
    # Strategy 2: Try direct parse
    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            return data
        if isinstance(data, list) and len(data) > 0:
            return {"questions": data}
    except:
        pass
    
    # Strategy 3: Fix common JSON issues
    try:
        cleaned = cleaned.replace("\u201c", '"').replace("\u201d", '"').replace("\u2018", "'").replace("\u2019", "'")
        # Remove trailing commas
        cleaned = re.sub(r',(\s*[}\]])', r'\1', cleaned)
        # Remove comments
        cleaned = re.sub(r'//.*', '', cleaned)
        cleaned = re.sub(r'/\*.*?\*/', '', cleaned, flags=re.DOTALL)
        data = json.loads(cleaned)
        if isinstance(data, dict):
            return data
    except:
        pass
    
    # Strategy 4: Extract questions array manually
    try:
        match = re.search(r'"questions"\s*:\s*\[([\s\S]*)\]', cleaned)
        if match:
            questions_str = "[" + match.group(1) + "]"
            questions = json.loads(questions_str)
            return {"questions": questions}
    except:
        pass
    
    raise ValueError("Could not parse JSON from LLM response")


# ============================================================================
# LLM CALL & VALIDATION
# ============================================================================

def _call_llm(structured_input: StructuredQuestionInput, question_count: int, retry_note: str | None = None) -> dict[str, Any]:
    user_prompt = _llm_user_prompt_v2(structured_input, question_count, retry_note=retry_note)
    provider = _llm_provider()
    model = _llm_model()
    
    logger.info(
        "llm_question_request_v2 provider=%s model=%s question_count=%s retry=%s role_family=%s",
        provider,
        model,
        question_count,
        bool(retry_note),
        structured_input.role_family,
    )
    
    max_tokens = max(2000, min(6000, int(question_count) * 220))
    use_strict_json = provider == "openai"

    try:
        response = _get_client().create(
            model=model,
            messages=[
                {"role": "system", "content": LLM_QUESTION_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.25 if retry_note else 0.35,
            max_tokens=max_tokens,
            response_format={"type": "json_object"} if use_strict_json else None,
        )
        logger.info("llm_question_request_success provider=%s model=%s retry=%s", provider, model, bool(retry_note))
    except Exception as exc:
        logger.warning("llm_question_request_failure provider=%s model=%s retry=%s error=%s", provider, model, bool(retry_note), exc)
        raise

    raw_content = response.choices[0].message.content or ""
    try:
        payload = _extract_json_object(raw_content)
    except Exception:
        logger.warning(
            "llm_json_parse_retry provider=%s model=%s question_count=%s retry=%s",
            provider,
            model,
            question_count,
            bool(retry_note),
        )
        repair_prompt = user_prompt + "\n\nIMPORTANT: Return ONLY valid JSON object. No markdown, no explanations."
        repair_response = _get_client().create(
            model=model,
            messages=[
                {"role": "system", "content": LLM_QUESTION_SYSTEM_PROMPT},
                {"role": "user", "content": repair_prompt},
            ],
            temperature=0.15,
            max_tokens=max_tokens,
            response_format={"type": "json_object"} if use_strict_json else None,
        )
        payload = _extract_json_object(repair_response.choices[0].message.content or "")

    questions = _normalize_llm_questions_v2(
        raw_questions=list(payload.get("questions") or []),
        structured_input=structured_input,
        question_count=max(2, int(question_count)),
    )
    
    logger.info(
        "llm_question_response_v2 provider=%s model=%s question_count_requested=%s question_count_returned=%s retry=%s",
        provider,
        model,
        question_count,
        len(questions),
        bool(retry_note),
    )
    
    return {
        "questions": questions,
        "user_prompt": user_prompt,
    }


def _retry_note_for_issues(issues: list[str]) -> str:
    return (
        "Regenerate with stronger grounding. Quality issues: "
        + ", ".join(issues[:5])
        + ". Ensure: specific project names, 1 opener, 1 behavioral, no duplicates, no weak phrases, all technical questions reference actual resume content."
    )


def _generate_validated_llm_questions(
    structured_input: StructuredQuestionInput,
    question_count: int,
) -> tuple[list[dict[str, Any]], str, dict[str, Any]]:
    requested_count = max(2, int(question_count))
    first_attempt = _call_llm(structured_input, requested_count)
    first_issues = _validate_question_set_v2(first_attempt["questions"], structured_input, requested_count)

    final_questions = first_attempt["questions"]
    final_user_prompt = first_attempt["user_prompt"]
    retry_issues: list[str] = []
    retry_used = False

    if first_issues:
        retry_used = True
        retry_note = _retry_note_for_issues(first_issues)
        second_attempt = _call_llm(structured_input, requested_count, retry_note=retry_note)
        retry_issues = _validate_question_set_v2(second_attempt["questions"], structured_input, requested_count)

        if len(retry_issues) <= len(first_issues):
            final_questions = second_attempt["questions"]
            final_user_prompt = second_attempt["user_prompt"]

    quality = {
        "first_attempt_issues": first_issues,
        "retry_used": retry_used,
        "retry_issues": retry_issues,
        "final_issues": retry_issues if retry_used else first_issues,
    }
    
    return final_questions, final_user_prompt, quality


# ============================================================================
# MAIN LLM GENERATION
# ============================================================================

def generate_llm_questions(
    *,
    jd_text: str,
    resume_text: str,
    question_count: int,
    jd_title: str | None = None,
    jd_skill_scores: Mapping[str, int] | None = None,
) -> dict[str, Any]:
    structured_input = build_structured_question_input(
        resume_text=resume_text,
        jd_title=jd_title,
        jd_skill_scores=jd_skill_scores,
        jd_text=jd_text,
    )
    
    final_questions, final_user_prompt, quality = _generate_validated_llm_questions(
        structured_input,
        max(2, int(question_count)),
    )

    return {
        "questions": final_questions[: max(2, int(question_count))],
        "structured_input": asdict(structured_input),
        "system_prompt": LLM_QUESTION_SYSTEM_PROMPT,
        "user_prompt": final_user_prompt,
        "llm_model": _llm_premium_model(),
        "quality": quality,
    }


# ============================================================================
# FALLBACK BUNDLE & RUNTIME ASSEMBLY
# ============================================================================

def _pick_fallback_top_up_v2(
    *,
    llm_questions: list[dict[str, Any]],
    fallback_questions: list[dict[str, Any]],
    needed: int,
) -> list[dict[str, Any]]:
    """Top up with fallback questions, prioritizing diversity of type."""
    if needed <= 0:
        return []
    
    seen_text = {_similarity_key(q.get("text")) for q in llm_questions}
    llm_types = {q.get("type", "project") for q in llm_questions}
    
    candidates = []
    for fq in fallback_questions:
        if _similarity_key(fq.get("text")) in seen_text:
            continue
        
        fq_type = fq.get("type", "project")
        is_new_type = fq_type not in llm_types
        relevance = float(((fq.get("metadata") or {}).get("relevance_score") or 0.0))
        
        candidates.append((is_new_type, relevance, fq))
    
    candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
    
    picked = []
    for _, _, fq in candidates:
        if len(picked) >= needed:
            break
        picked.append(fq)
        seen_text.add(_similarity_key(fq.get("text")))
    
    return picked


def _enforce_category_coverage(
    questions: list[dict[str, Any]],
    fallback_questions: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Ensure we have at least 1 opener and 1 behavioral."""
    if not fallback_questions:
        return questions
        
    categories_present = {str(q.get("type") or q.get("category") or "project") for q in questions}
    has_opener = "opener" in categories_present
    has_behavioral = "behavioral" in categories_present
    
    if has_opener and has_behavioral:
        return questions
        
    result = list(questions)
    seen_texts = {_similarity_key(q.get("text")) for q in result}
    
    def _swap_question(target_type: str | tuple[str, ...], replace_from_end: bool = True) -> bool:
        candidate = None
        for fq in fallback_questions:
            cat = str(fq.get("type") or fq.get("category") or "project")
            is_match = cat in target_type if isinstance(target_type, tuple) else cat == target_type
            if is_match and _similarity_key(fq.get("text")) not in seen_texts:
                candidate = fq
                break
                
        if not candidate:
            return False
            
        victim_idx = -1
        if replace_from_end:
            for i in range(len(result) - 1, -1, -1):
                if str(result[i].get("type")) in {"project", "decision"}:
                    victim_idx = i
                    break
        else:
            for i in range(len(result)):
                if str(result[i].get("type")) in {"project", "decision"}:
                    victim_idx = i
                    break
                    
        if victim_idx >= 0:
            result[victim_idx] = candidate
            seen_texts.add(_similarity_key(candidate.get("text")))
            return True
            
        return False

    if not has_opener:
        success = _swap_question("opener", replace_from_end=False)
        if not success and result:
            result[0] = {
                "text": "Walk me through your background and what drew you to this role.",
                "type": "opener",
                "focus": "background",
                "intent": "Understand candidate background and motivation.",
                "reference_answer": "Clear summary of experience and specific interest in the role.",
            }
        
    if not has_behavioral:
        success = _swap_question("behavioral", replace_from_end=True)
        if not success and result:
            if len(result) > 1:
                result[-1] = {
                    "text": "Tell me about a time you had to balance delivering quickly with maintaining code quality.",
                    "type": "behavioral",
                    "focus": "pragmatism",
                    "intent": "Assess technical judgment and communication.",
                    "reference_answer": "Specific example showing trade-off thinking and reasoning.",
                }
        
    return result


def _build_fallback_bundle(
    *,
    resume_text: str,
    jd_title: str | None,
    jd_skill_scores: Mapping[str, int] | None,
    question_count: int,
    project_ratio: float | None = None,
) -> dict[str, Any]:
    fallback_bundle = build_question_plan(
        resume_text=resume_text,
        jd_title=jd_title,
        jd_skill_scores=jd_skill_scores or {},
        question_count=question_count,
        project_ratio=project_ratio,
    ) or {}
    return fallback_bundle if isinstance(fallback_bundle, dict) else {}


def _question_text_key(question: Mapping[str, Any]) -> str:
    return _similarity_key(question.get("text"))


def _synthetic_top_up_questions(*, desired_count: int, jd_title: str | None, jd_skill_scores: Mapping[str, int] | None, existing: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if len(existing) >= desired_count:
        return []

    seen = {_question_text_key(q) for q in existing if q.get("text")}
    role = _clean(jd_title) or "this role"
    primary_skills = [str(skill) for skill in (jd_skill_scores or {}).keys() if _clean(skill)]
    if not primary_skills:
        primary_skills = ["your core stack"]

    templates = [
        ("project", "In this role, where have you applied {skill} to deliver a measurable outcome?"),
        ("decision", "Tell me about a trade-off you made while using {skill}, and why you chose that path."),
        ("debugging", "Describe a production issue related to {skill} that you diagnosed and fixed end-to-end."),
        ("behavioral", "How do you collaborate with stakeholders when priorities shift during a {skill} initiative?"),
        ("role_specific", "For {role}, what architecture choices would you make first if scope doubled next quarter?"),
    ]

    generated: list[dict[str, Any]] = []
    idx = 0
    guard = 0
    while len(existing) + len(generated) < desired_count and guard < 200:
        qtype, template = templates[idx % len(templates)]
        skill = primary_skills[idx % len(primary_skills)]
        text = template.format(skill=skill, role=role)
        key = _similarity_key(text)
        if key and key not in seen:
            seen.add(key)
            generated.append(
                {
                    "text": text,
                    "type": qtype,
                    "focus": _clean(skill if qtype != "role_specific" else role) or qtype,
                    "project": None,
                    "intent": f"Assess {qtype.replace('_', ' ')} capability relevant to {role}.",
                    "reference_answer": "Specific ownership, decisions, impact, and lessons learned.",
                }
            )
        idx += 1
        guard += 1

    return generated


def _bundle_counts_v2(questions: list[dict[str, Any]]) -> dict[str, Any]:
    """Count questions by type for reporting."""
    type_counts = {}
    for q in questions:
        qtype = q.get("type", "project")
        type_counts[qtype] = type_counts.get(qtype, 0) + 1
    
    return {
        "total_questions": len(questions),
        "by_type": type_counts,
        "has_opener": type_counts.get("opener", 0) >= 1,
        "has_behavioral": type_counts.get("behavioral", 0) >= 1,
        "technical_count": sum(1 for q in questions if q.get("type") not in {"opener", "behavioral"}),
    }


def _runtime_bundle_from_llm(
    *,
    llm_bundle: dict[str, Any],
    fallback_bundle: dict[str, Any],
    questions: list[dict[str, Any]],
    project_ratio: float | None,
    llm_topped_up_with_fallback: bool,
) -> dict[str, Any]:
    logger.info(
        "llm_question_bundle_ready_v2 provider=%s model=%s generation_mode=%s fallback_used=%s questions=%s",
        _llm_provider(),
        llm_bundle.get("llm_model"),
        "llm_primary",
        False,
        len(questions),
    )
    
    counts = _bundle_counts_v2(questions)
    
    return {
        "questions": questions,
        **counts,
        "projects": list((llm_bundle.get("structured_input") or {}).get("resume_projects") or [])[:6],
        "meta": {
            **(fallback_bundle.get("meta") or {}),
            "generation_mode": "llm_primary",
            "fallback_used": False,
            "llm_topped_up_with_fallback": llm_topped_up_with_fallback,
            "llm_model": llm_bundle.get("llm_model"),
            "llm_system_prompt": llm_bundle.get("system_prompt"),
            "llm_user_prompt": llm_bundle.get("user_prompt"),
            "structured_input": llm_bundle.get("structured_input"),
            "llm_quality": llm_bundle.get("quality"),
            "project_ratio_requested": project_ratio,
        },
    }


def _runtime_bundle_from_fallback(
    *,
    fallback_bundle: dict[str, Any],
    fallback_reason: str,
    project_ratio: float | None,
    structured_input: StructuredQuestionInput,
) -> dict[str, Any]:
    questions = list(fallback_bundle.get("questions") or [])
    meta = dict(fallback_bundle.get("meta") or {})
    meta.update(
        {
            "generation_mode": "fallback_dynamic_plan",
            "fallback_used": True,
            "fallback_reason": fallback_reason,
            "project_ratio_requested": project_ratio,
            "structured_input": asdict(structured_input),
        }
    )
    
    logger.info(
        "llm_question_bundle_ready_v2 provider=%s model=%s generation_mode=%s fallback_used=%s questions=%s",
        _llm_provider(),
        _llm_model(),
        "fallback_dynamic_plan",
        True,
        len(questions),
    )
    
    counts = _bundle_counts_v2(questions)
    
    return {
        "questions": questions,
        **counts,
        "projects": list(fallback_bundle.get("projects") or []),
        "meta": meta,
    }


EMERGENCY_FALLBACK_QUESTIONS = [
    {
        "text": "Walk me through your background and the most recent role on your resume.",
        "type": "opener",
        "focus": "background",
        "intent": "Understand candidate background.",
        "reference_answer": "Clear summary of experience and key skills.",
    },
    {
        "text": "Tell me about a time you had to manage conflicting priorities or navigate a difficult situation to deliver a project.",
        "type": "behavioral",
        "focus": "conflict resolution",
        "intent": "Assess soft skills and communication.",
        "reference_answer": "Specific example with clear outcome.",
    },
    {
        "text": "Describe a recent technical challenge you faced and how you resolved it.",
        "type": "project",
        "focus": "problem-solving",
        "intent": "Assess analytical and technical skills.",
        "reference_answer": "Detailed explanation of approach and results.",
    },
    {
        "text": "How would you approach scaling a system to handle 10x more requests?",
        "type": "role_specific",
        "focus": "systems thinking",
        "intent": "Assess architectural thinking.",
        "reference_answer": "Thoughtful discussion of bottlenecks and tradeoffs.",
    },
    {
        "text": "How do you ensure code you deliver is maintainable and reliable?",
        "type": "project",
        "focus": "software engineering practices",
        "intent": "Assess quality standards.",
        "reference_answer": "Specific practices and reasoning.",
    },
    {
        "text": "Tell me about a time you learned a new technology quickly to deliver a critical feature.",
        "type": "behavioral",
        "focus": "learning agility",
        "intent": "Assess adaptability.",
        "reference_answer": "Specific example with clear learning and delivery.",
    },
    {
        "text": "What is the most complex debugging situation you've worked through in production?",
        "type": "debugging",
        "focus": "troubleshooting",
        "intent": "Assess technical depth.",
        "reference_answer": "Detailed walkthrough of diagnosis and resolution.",
    },
    {
        "text": "How do you approach trade-offs between perfect engineering and shipping quickly?",
        "type": "decision",
        "focus": "pragmatism",
        "intent": "Assess business acumen.",
        "reference_answer": "Thoughtful discussion of decision-making process.",
    }
]


# ============================================================================
# MAIN ENTRY POINT - WITH FALLBACK
# ============================================================================

def generate_question_bundle_with_fallback(
    *,
    resume_text: str,
    jd_title: str | None,
    jd_skill_scores: Mapping[str, int] | None,
    question_count: int | None = None,
    project_ratio: float | None = None,
    jd_text: str | None = None,
) -> dict[str, Any]:
    """
    Generate interview questions with natural flow.
    Falls back to deterministic planner if LLM fails.
    
    Returns: {
        "questions": [list of questions],
        "total_questions": int,
        "by_type": dict of type counts,
        "has_opener": bool,
        "has_behavioral": bool,
        "technical_count": int,
        "projects": [list of top projects],
        "meta": {metadata about generation}
    }
    """
    desired_count = max(2, min(20, int(question_count or 8)))
    provider = _llm_provider()
    model = _llm_premium_model()
    
    try:
        fallback_bundle = _build_fallback_bundle(
            resume_text=resume_text,
            jd_title=jd_title,
            jd_skill_scores=jd_skill_scores,
            question_count=desired_count,
            project_ratio=project_ratio,
        )
    except Exception as exc:
        logger.error("Fallback bundle generation failed: %s", exc)
        fallback_bundle = {"questions": EMERGENCY_FALLBACK_QUESTIONS[:desired_count]}

    try:
        llm_bundle = generate_llm_questions(
            jd_text=_build_jd_text(jd_title, jd_skill_scores, jd_text=jd_text),
            resume_text=resume_text,
            question_count=desired_count,
            jd_title=jd_title,
            jd_skill_scores=jd_skill_scores or {},
        )
        questions = list(llm_bundle["questions"])
        llm_topped_up_with_fallback = False

        # Top up if needed
        missing = desired_count - len(questions)
        if missing > 0:
            top_up_questions = _pick_fallback_top_up_v2(
                llm_questions=questions,
                fallback_questions=list(fallback_bundle.get("questions") or []),
                needed=missing,
            )
            if top_up_questions:
                questions.extend(top_up_questions)
                llm_topped_up_with_fallback = True

        # Enforce required categories (opener + behavioral)
        original_len = len(questions)
        questions = _enforce_category_coverage(questions, list(fallback_bundle.get("questions") or []))
        if len(questions) != original_len or any(q.get("type") in {"opener", "behavioral"} for q in questions):
            llm_topped_up_with_fallback = True
            
        logger.info(
            "LLM_SUCCESS_v2 provider=%s model=%s question_count_requested=%s question_count_returned=%s fallback_used=%s",
            provider,
            model,
            desired_count,
            len(questions),
            False,
        )

        return _runtime_bundle_from_llm(
            llm_bundle=llm_bundle,
            fallback_bundle=fallback_bundle,
            questions=questions,
            project_ratio=project_ratio,
            llm_topped_up_with_fallback=llm_topped_up_with_fallback,
        )
        
    except Exception as exc:
        logger.warning("LLM question generation failed, using fallback: %s", exc)
        fallback_questions = list(fallback_bundle.get("questions") or [])
        
        if not fallback_questions or len(fallback_questions) < desired_count:
            pool = fallback_questions + EMERGENCY_FALLBACK_QUESTIONS
            deduped: list[dict[str, Any]] = []
            seen: set[str] = set()
            for question in pool:
                text_key = _question_text_key(question)
                if not text_key or text_key in seen:
                    continue
                seen.add(text_key)
                deduped.append(question)
                if len(deduped) >= desired_count:
                    break

            if len(deduped) < desired_count:
                deduped.extend(
                    _synthetic_top_up_questions(
                        desired_count=desired_count,
                        jd_title=jd_title,
                        jd_skill_scores=jd_skill_scores,
                        existing=deduped,
                    )
                )

            fallback_questions = deduped[:desired_count]
        else:
            fallback_questions = _enforce_category_coverage(fallback_questions, fallback_questions)

        if len(fallback_questions) < desired_count:
            fallback_questions.extend(
                _synthetic_top_up_questions(
                    desired_count=desired_count,
                    jd_title=jd_title,
                    jd_skill_scores=jd_skill_scores,
                    existing=fallback_questions,
                )
            )
            fallback_questions = fallback_questions[:desired_count]
            
        fallback_bundle["questions"] = fallback_questions
        
        logger.warning(
            "LLM_FAILED_v2 provider=%s model=%s question_count_requested=%s question_count_returned=%s fallback_used=%s error=%s",
            provider,
            model,
            desired_count,
            len(fallback_questions),
            True,
            str(exc)[:100],
        )
        
        try:
            structured_input = build_structured_question_input(
                resume_text=resume_text,
                jd_title=jd_title,
                jd_skill_scores=jd_skill_scores or {},
                jd_text=jd_text,
            )
        except Exception:
            structured_input = StructuredQuestionInput(
                role=jd_title or "Interview Role",
                role_title=jd_title or "Interview Role",
                role_family="engineer",
                seniority="mid",
                experience_level="mid",
                jd_title=jd_title or "Interview Role",
                jd_summary="",
                jd_core_skills=[],
                jd_secondary_skills=[],
                jd_responsibilities=[],
                jd_skills=[],
                jd_skill_weights={},
                resume_summary="",
                resume_recent_roles=[],
                resume_skills=[],
                resume_projects=[],
                resume_project_technologies=[],
                resume_experiences=[],
                resume_leadership_signals=[],
                resume_measurable_impact=[],
                certifications=[],
                overlap_skills=[],
                resume_only_skills=[],
                jd_only_skills=[],
            )

        return _runtime_bundle_from_fallback(
            fallback_bundle=fallback_bundle,
            fallback_reason=str(exc)[:200],
            project_ratio=project_ratio,
            structured_input=structured_input,
        )


# ============================================================================
# ADAPTIVE PROBING (Phase 2) - Keep existing
# ============================================================================

FOLLOWUP_QUESTION_SYSTEM_PROMPT = """You are a highly experienced technical interviewer. 
The candidate just gave an answer that was either too short, too vague, or lacked technical depth.
Your goal is to generate exactly ONE follow-up question to probe deeper into their specific implementation, decision, or result.

RULES:
- Reference the original question and the candidate's partial answer.
- Ask for a specific detail, trade-off, or "how" / "why" that was missing.
- The question must be a single sentence ending with a single "?".
- Keep it surgical and grounded in the context of their resume.
- Do NOT repeat the original question.
- Do NOT ask more than one question.

Return a JSON object:
{
  "text": "string — the surgical follow-up question",
  "intent": "string — what specific depth this probes",
  "reference_answer": "string — what a strong technical deep-dive answer would cover"
}
"""


def generate_followup_question(
    original_question: str,
    candidate_answer: str,
    resume_text: str = "",
) -> dict[str, Any] | None:
    """Generate a surgical follow-up question using the LLM."""
    provider = _llm_provider()
    model = _llm_model()
    
    user_prompt = f"RESUME CONTEXT (Optional):\n{resume_text[:2000]}\n\nORIGINAL QUESTION: {original_question}\n\nCANDIDATE ANSWER: {candidate_answer}\n\nGenerate a deep-probe follow-up question."

    logger.info("llm_followup_request_start provider=%s model=%s", provider, model)
    try:
        response = _get_client().create(
            model=model,
            messages=[
                {"role": "system", "content": FOLLOWUP_QUESTION_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            max_tokens=1000,
        )
        data = _extract_json_object(response.choices[0].message.content or "")
        
        text = _clean(data.get("text"))
        if not text or "?" not in text or text.count("?") > 1:
            return None
            
        logger.info("llm_followup_request_success text=%r", text[:100])
        return {
            "text": text,
            "intent": _clean(data.get("intent")) or "Deep-probe clarification.",
            "reference_answer": _clean(data.get("reference_answer")) or "A detailed explanation of the implementation and decisions.",
            "type": "followup",
            "focus": "follow-up",
        }
    except Exception as exc:
        logger.warning("llm_followup_request_failed error=%s", exc)
        return None


# ============================================================================
# DYNAMIC NEXT QUESTION (Conversational)
# ============================================================================

DYNAMIC_NEXT_QUESTION_SYSTEM_PROMPT = """You are a senior technical interviewer. 
You are conducting a conversation. Based on the candidate's last answer, generate the NEXT logical question.
If the answer was strong, move to a new project or a design challenge.
If the answer was weak/vague, probe for technical implementation details.
ALWAYS ground your question in the resume and overall projects.

Return JSON:
{
  "text": "one surgical question",
  "type": "type from: opener, project, decision, debugging, behavioral, role_specific",
  "project": "project name from resume",
  "intent": "intent",
  "reference_answer": "strong answer expectations"
}
"""

def generate_dynamic_next_question(
    *,
    resume_text: str,
    jd_title: str,
    jd_skill_scores: dict,
    history: list[dict[str, str]],
    question_count: int,
) -> dict[str, Any] | None:
    """Generate the next question based on interview history."""
    structured_input = build_structured_question_input(
        resume_text=resume_text,
        jd_title=jd_title,
        jd_skill_scores=jd_skill_scores,
    )
    
    evidence = "\n".join([f"PROJECT: {p}" for p in structured_input.resume_projects[:3]])
    
    chat_history = ""
    for turn in history[-4:]:
        chat_history += f"Q: {turn.get('question')}\nA: {turn.get('answer')}\n\n"
        
    user_prompt = (
        f"CANDIDATE PROJECTS:\n{evidence}\n\n"
        f"INTERVIEW HISTORY:\n{chat_history}"
        f"Generate question number {len(history) + 1} of {question_count}."
    )
    
    try:
        response = _get_client().create(
            model=_llm_model(),
            messages=[
                {"role": "system", "content": DYNAMIC_NEXT_QUESTION_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.4,
            max_tokens=1000,
        )
        data = _extract_json_object(response.choices[0].message.content or "")
        raw_text = data.get("text")
        if not raw_text:
            return None
        return {
            "text": _clean(raw_text),
            "type": _normalize_question_type_v2(data.get("type")),
            "project": _clean(data.get("project")),
            "intent": _clean(data.get("intent")),
            "reference_answer": _clean(data.get("reference_answer")),
            "focus": "dynamic",
        }
    except Exception as exc:
        logger.warning(f"Dynamic question gen failed: {exc}")
        return None