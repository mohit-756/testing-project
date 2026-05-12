"""Structured resume parsing helpers for ATS views and scoring."""

from __future__ import annotations

import re
from collections import OrderedDict

from ai_engine.phase1.matching import extract_text_from_file
from ai_engine.phase1.scoring import SKILL_ALIASES

# Reject lines that are purely employment date ranges (e.g. "Jan 2026 – Present", "2022 - 2023")
_DATE_RANGE_LINE_RE = re.compile(
    r"""^\s*
    (?:
        (?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|
           jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)
        [\s,]+\d{4}
    |\d{4}
    )
    \s*(?:–|-|to|/)
    \s*
    (?:
        (?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|
           jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)
        [\s,]+\d{4}
    |\d{4}
    |present|current|now|ongoing
    )\s*$""",
    re.IGNORECASE | re.VERBOSE,
)

SECTION_HEADERS = (
    "summary",
    "experience",
    "education",
    "skills",
    "projects",
    "certifications",
)

EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
PHONE_RE = re.compile(r"(?:\+?\d[\d\s().-]{7,}\d)")


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _split_lines(text: str) -> list[str]:
    return [_clean(line) for line in (text or "").splitlines() if _clean(line)]


def _detect_name(lines: list[str], email: str | None) -> str | None:
    for line in lines[:6]:
        if email and email.lower() in line.lower():
            continue
        if len(line.split()) in {2, 3, 4} and not re.search(r"\d", line):
            return line.title()
    return None


def _parse_sections(lines: list[str]) -> dict[str, list[str]]:
    # Improved: recognize more section headers and variants
    section_aliases = {
        "summary": ["summary", "professional summary", "profile"],
        "experience": ["work experience", "experience", "professional experience", "internship experience", "employment"],
        "projects": ["technical projects", "projects", "project", "academic projects", "personal projects"],
        "education": ["education", "academic background"],
        "skills": ["skills", "technical skills", "core skills"],
        "certifications": ["certifications", "certification", "licenses", "courses"],
    }
    header_map = {}
    for canonical, aliases in section_aliases.items():
        for alias in aliases:
            header_map[alias] = canonical
    sections: dict[str, list[str]] = {key: [] for key in SECTION_HEADERS}
    current = "summary"
    for line in lines:
        lowered = line.lower().strip(":")
        canonical = header_map.get(lowered, None)
        if canonical:
            current = canonical
            continue
        sections.setdefault(current, []).append(line)
    return sections


def _extract_skills(text: str) -> list[str]:
    detected: list[str] = []
    lowered = (text or "").lower()
    for canonical, aliases in SKILL_ALIASES.items():
        if any(re.search(rf"(?<!\w){re.escape(alias.lower())}(?!\w)", lowered) for alias in aliases):
            detected.append(canonical)
    return sorted(OrderedDict.fromkeys(detected))


def _bullets(lines: list[str], max_items: int = 6) -> list[str]:
    items: list[str] = []
    for line in lines:
        bullet = re.sub(r"^[\-\*•\d\.)\(\s]+", "", line).strip()
        if bullet:
            items.append(bullet)
        if len(items) >= max_items:
            break
    return items


def extract_projects_from_resume(
    resume_text: str,
    known_skills: dict[str, object] | None = None,
    candidate_name: str | None = None,
) -> list[str]:
    """Best-effort project extraction shared by resume advice and legacy callers."""
    _ = known_skills

    if not resume_text:
        return []

    lines = [line.strip() for line in resume_text.splitlines()]
    projects: list[str] = []
    in_project_section = False
    project_title = None

    # Pre-compute name tokens to scrub from project titles
    name_tokens: set[str] = set()
    if candidate_name:
        name_tokens.add(_clean(candidate_name).lower())
        for part in candidate_name.split():
            if len(part) > 1:
                name_tokens.add(part.lower())

    def _scrub_name(title: str) -> str:
        """Remove candidate name tokens from a project title."""
        result = title
        for token in name_tokens:
            result = re.sub(re.escape(token), "", result, flags=re.IGNORECASE)
        # Clean up possessive artifacts left after name removal (e.g. "'s", "'")
        result = re.sub(r"\b's\b", "", result, flags=re.IGNORECASE)
        result = re.sub(r"\s+", " ", result).strip(" -|:'")
        return result

    def _is_valid_project_title(title: str) -> bool:
        """Reject titles that are pure date ranges or too short."""
        stripped = title.strip()
        if len(stripped) < 3:
            return False
        if _DATE_RANGE_LINE_RE.match(stripped):
            return False
        return True

    for i, raw_line in enumerate(lines):
        line = raw_line.strip()
        if not line:
            continue
        lower = line.lower().rstrip(":")
        # Section start
        if any(lower.startswith(h) for h in ["technical projects", "projects", "project", "academic projects", "personal projects"]):
            in_project_section = True
            project_title = None
            continue
        # Section end
        if in_project_section and any(lower.startswith(h) for h in ["education", "skills", "certification", "experience", "achievements", "summary"]):
            in_project_section = False
            project_title = None
            continue
        if in_project_section:
            # Skip pure date-range lines (e.g. "Jan 2026 – Present", "2022 - 2023")
            if _DATE_RANGE_LINE_RE.match(line):
                continue
            # Project title: line ending with ':' or bolded
            if re.match(r"^[A-Za-z0-9\- &()]+:.*$", line) or (len(line) < 80 and not line.startswith("•") and not line.startswith("-") and not line.startswith("*")):
                project_title = _scrub_name(line.rstrip(":"))
                if project_title and _is_valid_project_title(project_title) and project_title not in projects:
                    projects.append(project_title)
                continue
            # Bullet or description
            if line.startswith("•") or line.startswith("-") or line.startswith("*") or (project_title and len(line) > 10):
                if project_title:
                    projects.append(f"{project_title}: {line}")
                else:
                    projects.append(line)
    # Fallback: scan for project-like lines
    if not projects:
        for line in lines:
            lower = line.lower()
            if any(keyword in lower for keyword in ("system", "portal", "app", "application", "dashboard", "bot", "platform", "website", "project", "tool")):
                if len(line) > 3 and not _DATE_RANGE_LINE_RE.match(line):
                    projects.append(_scrub_name(line) if name_tokens else line)
    seen = set()
    unique_projects: list[str] = []
    for project in projects:
        key = project.lower()
        if key not in seen:
            seen.add(key)
            unique_projects.append(project)
    return unique_projects


def parse_resume_text(text: str) -> dict[str, object]:
    raw_text = text or ""
    lines = _split_lines(raw_text)
    email_match = EMAIL_RE.search(raw_text)
    phone_match = PHONE_RE.search(raw_text)
    sections = _parse_sections(lines)
    summary_lines = sections.get("summary") or lines[:4]

    # Improved experience extraction
    experience_entries = []
    in_exp_section = False
    exp_title = None
    for i, line in enumerate(lines):
        l = line.strip()
        lower = l.lower().rstrip(":")
        if any(lower.startswith(h) for h in ["work experience", "experience", "professional experience", "internship experience", "employment"]):
            in_exp_section = True
            exp_title = None
            continue
        if in_exp_section and any(lower.startswith(h) for h in ["education", "skills", "certification", "projects", "achievements", "summary"]):
            in_exp_section = False
            exp_title = None
            continue
        if in_exp_section:
            # Skip pure date-range lines (e.g. "Jan 2026 – Present", "2024 - 2025")
            if _DATE_RANGE_LINE_RE.match(l):
                continue
            # Experience title: role/company | ...
            if re.match(r"^[A-Za-z0-9\- &|()]+\|.*$", l) or (len(l) < 80 and not l.startswith("•") and not l.startswith("-") and not l.startswith("*")):
                exp_title = l
                if exp_title and exp_title not in experience_entries:
                    experience_entries.append(exp_title)
                continue
            # Bullet or description
            if l.startswith("•") or l.startswith("-") or l.startswith("*") or (exp_title and len(l) > 10):
                if exp_title:
                    experience_entries.append(f"{exp_title}: {l}")
                else:
                    experience_entries.append(l)

    # Measurable impact extraction (from all lines)
    measurable_impacts = []
    impact_pattern = re.compile(r"(\d+%|\d+ percent|\d+x|reduced|improved|increased|decreased|boosted|cut|saved|grew|shrunk|doubled|halved|reduced by|increased by|improved by|decreased by|boosted by|cut by|saved by|grew by|shrunk by|doubled|halved)", re.I)
    for line in lines:
        if impact_pattern.search(line):
            measurable_impacts.append(line.strip())

    name = _detect_name(lines, email_match.group(0) if email_match else None)
    return {
        "full_name": name,
        "email": email_match.group(0) if email_match else None,
        "phone": _clean(phone_match.group(0)) if phone_match else None,
        "summary": " ".join(summary_lines[:3]).strip() or None,
        "skills": _extract_skills(raw_text),
        "education": _bullets(sections.get("education") or [], max_items=5),
        "projects": extract_projects_from_resume(raw_text, candidate_name=name),
        "experience": experience_entries,
        "measurable_impacts": measurable_impacts,
        "certifications": _bullets(sections.get("certifications") or [], max_items=5),
        "raw_text_available": bool(raw_text.strip()),
    }


def parse_resume_file(file_path: str) -> tuple[str, dict[str, object]]:
    text = extract_text_from_file(file_path)
    return text, parse_resume_text(text)
