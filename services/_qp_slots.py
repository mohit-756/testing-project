from __future__ import annotations

import re

from services._qp_evidence import (
    _clean,
    _contains_metric,
    _dedupe,
    _evidence_priority,
    _projectish_phrase,
    _sanitize_evidence_text,
    get_resume_module,
    role_track,
)
from services._qp_structs import (
    _ALL_CAPS_NAME_RE,
    _CITY_LOCATION_RE,
    NAMEY_HEADER_PATTERN,
    PlannerContext,
    StructuredResume,
    EvidenceItem,
)


def _pick_evidence(candidate: dict[str, object], category: str, role_family: str) -> EvidenceItem | None:
    evidence = list(candidate.get("evidence") or [])
    if not evidence:
        return None
    if category == "leadership":
        evidence.sort(key=lambda item: (item.leadership, _evidence_priority(item)), reverse=True)
    elif category == "architecture":
        evidence.sort(key=lambda item: (item.architecture, _evidence_priority(item)), reverse=True)
    elif role_family in {"engineer", "senior_engineer"}:
        evidence.sort(key=_evidence_priority, reverse=True)
    else:
        evidence.sort(key=lambda item: (_evidence_priority(item), item.strength), reverse=True)
    return evidence[0]


def slot_candidate(category: str, context: PlannerContext, occurrence: int = 1, _used_labels: frozenset | None = None) -> dict[str, object]:
    rt = role_track(context)
    prioritized = list(context.topic_priorities or [])
    module_label = get_resume_module(context.resume)
    evidence_pool = sorted(context.resume.projects + context.resume.experiences, key=_evidence_priority, reverse=True)

    def _fallback(label: str, evidence: list[EvidenceItem] | None = None, *, kind: str = "project") -> dict[str, object]:
        return {
            "kind": kind,
            "label": label or module_label,
            "priority_source": "structured_slot",
            "score": 0.9,
            "resume_alignment": 0.85,
            "jd_alignment": 0.72,
            "role_alignment": 0.82,
            "evidence": evidence or [],
        }

    def _pick(*kinds: str, predicate=None) -> dict[str, object] | None:
        _ul = _used_labels or frozenset()
        matches = [
            dict(item) for item in prioritized
            if (not kinds or str(item.get("kind")) in set(kinds))
            and (predicate is None or predicate(item))
            and str(item.get("label") or "").strip().lower() not in _ul
        ]
        if not matches:
            matches = [
                dict(item) for item in prioritized
                if (not kinds or str(item.get("kind")) in set(kinds))
                and (predicate is None or predicate(item))
            ]
        if not matches:
            return None
        return matches[min(len(matches) - 1, max(0, occurrence - 1))]

    if category == "intro":
        return _fallback(context.jd.title or context.title or "your background", kind="intro")

    best_project = next((item for item in context.resume.projects if item.label), None) or (context.resume.projects[0] if context.resume.projects else None)
    best_experience = next((item for item in context.resume.experiences if item.label), None) or (context.resume.experiences[0] if context.resume.experiences else best_project)
    debug_item = next((item for item in evidence_pool if any(term in item.text.lower() for term in ("debug", "bug", "failure", "incident", "issue", "root cause", "fix", "latency", "outage", "drift"))), None) or best_project
    architecture_item = next((item for item in evidence_pool if item.architecture >= 0.25 or any(term in item.text.lower() for term in ("design", "architecture", "platform", "scalable", "integration", "governance", "lakehouse"))), None) or best_project
    leadership_item = next((item for item in evidence_pool if item.leadership >= 0.25 or any(term in item.text.lower() for term in ("led", "stakeholder", "mentor", "managed", "delivery", "roadmap", "ownership", "hiring", "practice"))), None) or best_experience
    frontend_item = next((item for item in evidence_pool if any(term in item.text.lower() for term in ("frontend", "ui", "react", "component", "dashboard", "responsive", "browser", "design system"))), None)
    data_item = next((item for item in evidence_pool if any(term in item.text.lower() for term in ("databricks", "lakehouse", "pipeline", "governance", "spark", "warehouse", "platform"))), None)
    aiml_item = next((item for item in evidence_pool if any(term in item.text.lower() for term in ("ml", "ai", "nlp", "llm", "model", "recall", "precision", "rag", "inference"))), None)
    backend_item = next((item for item in evidence_pool if any(term in item.text.lower() for term in ("backend", "api", "service", "database", "integration", "workflow", "fastapi", "sql"))), None)

    if category == "project":
        chosen = frontend_item if rt == "frontend" and frontend_item else data_item if rt == "data" and data_item else aiml_item if rt == "aiml" and aiml_item else best_project
        return _pick("project", "skill_anchor") or _fallback((chosen.label if chosen else module_label), [chosen] if chosen else [])
    if category == "deep_dive":
        chosen = frontend_item if rt == "frontend" and frontend_item else data_item if rt == "data" and data_item else aiml_item if rt == "aiml" and aiml_item else backend_item or best_project
        return _pick("skill_anchor", predicate=lambda item: bool(item.get("evidence"))) or _pick("project", predicate=lambda item: bool(item.get("evidence"))) or _fallback((chosen.label if chosen else module_label), [chosen] if chosen else [])
    if category == "backend":
        chosen = frontend_item if rt == "frontend" and frontend_item else data_item if rt == "data" and data_item else aiml_item if rt == "aiml" and aiml_item else backend_item or best_project
        return _pick("project", "architecture", predicate=lambda item: bool(item.get("evidence"))) or _fallback((chosen.label if chosen else module_label), [chosen] if chosen else [])
    if category == "debugging":
        return _pick("project", "skill_anchor", predicate=lambda item: bool(item.get("evidence"))) or _fallback((debug_item.label if debug_item else module_label), [debug_item] if debug_item else [])
    if category == "architecture":
        chosen = frontend_item if rt == "frontend" and frontend_item else data_item if rt == "data" and data_item else aiml_item if rt == "aiml" and aiml_item else architecture_item
        return _pick("architecture") or _pick("project") or _fallback((chosen.label if chosen else module_label), [chosen] if chosen else [], kind="architecture")
    if category == "leadership":
        chosen = data_item if rt == "data" and data_item and context.role_family in {"lead", "manager", "practice_head", "architect"} else leadership_item
        return _pick("leadership") or _pick("project") or _fallback((chosen.label if chosen else module_label), [chosen] if chosen else [], kind="leadership")
    return _fallback(module_label, [best_project] if best_project else [])


def _safe_target(candidate_target: str, fallback: str) -> str:
    """Return candidate_target if it looks like a project label; fallback otherwise."""
    t = (candidate_target or "").strip()
    if not t or len(t) < 4:
        return fallback or "your recent work"
    if _ALL_CAPS_NAME_RE.match(t):
        return fallback
    if NAMEY_HEADER_PATTERN.match(t) and not any(
        tok in t.lower() for tok in (
            "system", "platform", "api", "app", "dashboard", "service",
            "pipeline", "engine", "portal", "bot", "lakehouse", "studio", "project",
        )
    ):
        return fallback
    if _CITY_LOCATION_RE.search(t) and len(t.split()) <= 5:
        return fallback
    return t


def question_text(category: str, candidate: dict[str, object], context: PlannerContext, index: int, occurrence: int = 1) -> tuple[str, str | None]:
    evidence = _pick_evidence(candidate, category, context.role_family)
    evidence_text = _sanitize_evidence_text(evidence.text if evidence else None) or None
    role_label = _clean(context.jd.title or context.title or "this role")
    rt = role_track(context)
    strongest_project = get_resume_module(context.resume)
    target = _clean(str(candidate.get("label") or "")) or (evidence.label if evidence else strongest_project) or strongest_project
    target = _safe_target(_projectish_phrase(target) or strongest_project, strongest_project)

    if category == "intro":
        return (
            f"Please introduce yourself briefly and connect your background to {role_label}, highlighting the project, platform, or outcome that best represents your work.",
            evidence_text,
        )
    if category == "project":
        variants = [
            f"Walk me through {target}: what problem was it solving, what did you personally own, and what measurable result, adoption signal, or business outcome told you it was working?",
            f"Looking at {target}, what was the hardest part you owned directly, and how did you know your changes moved the product, platform, or business in the right direction?",
            f"When you worked on {target}, what was the concrete objective, where did your ownership begin and end, and what outcome made that work meaningful?",
            f"For {target}, what did you change in the code, workflow, or product itself that moved the needle, and how did you validate that impact in practice?",
            f"Take {target} as an example: where was the engineering risk, what part did you drive yourself, and what evidence convinced you the solution was working well enough to keep?",
        ]
        return (variants[(occurrence - 1) % len(variants)], evidence_text)
    if category == "deep_dive":
        if rt == "frontend":
            return (f"In {target}, how did you break the UI into components, state boundaries, or reusable patterns, and what trade-offs shaped that structure?", evidence_text)
        if rt == "aiml":
            return (f"In {target}, how did you choose the model, feature, prompt, or evaluation approach you used, and what trade-offs mattered most for the real product constraint?", evidence_text)
        if rt == "data":
            return (f"In {target}, how did you decide the data model, orchestration approach, or platform pattern, and what trade-offs did you make around reliability, cost, and maintainability?", evidence_text)
        return (f"In {target}, which implementation choice best shows how you make engineering decisions under real constraints, and why was that the right trade-off at the time?", evidence_text)
    if category == "backend":
        if rt == "frontend":
            return (f"In {target}, how did you handle API integration, responsiveness, and browser or state-management concerns so the user experience stayed stable as the UI grew?", evidence_text)
        if rt == "data":
            return (f"How was {target} structured so the platform could support more domains, stricter governance, or higher data volume without turning into a brittle pipeline chain?", evidence_text)
        if rt == "aiml":
            return (f"How did you structure the serving path, feature flow, or system integration around {target} so model behavior stayed reliable in production rather than only in offline evaluation?", evidence_text)
        return (f"How did you structure the APIs, services, and data flow around {target} so the system stayed maintainable and reliable as usage grew?", evidence_text)
    if category == "debugging":
        if rt == "frontend":
            return (f"Tell me about a tricky bug or failure in {target}: what symptoms showed up first, how did you narrow the issue across UI, API, or state boundaries, and what change made the experience stable again?", evidence_text)
        if rt == "aiml":
            return (f"Tell me about a failure or quality issue in {target}: what signal told you the model or pipeline was off, how did you isolate the root cause, and what changed after the fix?", evidence_text)
        if rt == "data":
            return (f"Describe a production issue in {target}: what monitoring signal, data-quality break, or platform bottleneck surfaced first, how did you isolate the cause, and what prevented recurrence?", evidence_text)
        return (f"Tell me about a failure or debugging issue in {target}: what signal told you something was wrong, how did you isolate the root cause, and what changed afterward?", evidence_text)
    if category == "architecture":
        if rt == "frontend":
            variants = [
                f"If {target} had to support more features, heavier usage, or faster release velocity, how would you evolve the frontend architecture, performance strategy, and collaboration model without hurting UX?",
                f"Suppose {target} had to handle a much broader product surface: how would you reshape the component architecture, state model, and performance guardrails before the UI became fragile?",
            ]
            return (variants[(occurrence - 1) % len(variants)], evidence_text)
        if rt == "aiml":
            variants = [
                f"If {target} had to run at higher scale or tighter latency targets, how would you redesign the pipeline, serving path, or rollback strategy, and what trade-offs would you watch first?",
                f"If usage on {target} grew sharply, what would you change first in the model-serving path, evaluation loop, or fallback design so quality stayed stable under production pressure?",
            ]
            return (variants[(occurrence - 1) % len(variants)], evidence_text)
        if rt == "data":
            variants = [
                f"If {target} had to scale across more domains, workloads, or enterprise controls, what architecture, governance, or cost-management changes would you make first, and why?",
                f"Imagine {target} becoming the shared platform for more business units: how would you evolve the lakehouse architecture, governance model, and operating boundaries before scale created delivery drag?",
            ]
            return (variants[(occurrence - 1) % len(variants)], evidence_text)
        variants = [
            f"If {target} had to handle more scale, tighter reliability targets, or broader integration requirements, what design or architecture changes would you make first and what trade-offs would you watch?",
            f"As {target} grows, where would you redraw service boundaries, contracts, or operational guardrails first, and what trade-offs would drive that decision?",
        ]
        return (variants[(occurrence - 1) % len(variants)], evidence_text)
    if category == "leadership":
        if context.role_family in {"lead", "manager", "practice_head"} or rt == "data":
            variants = [
                f"Tell me about a situation around {target if rt == 'data' else 'your recent work'} where you had to align stakeholders, make a delivery or platform decision, or scale ownership beyond implementation. What did you do and what was the outcome?",
                f"In work related to {target}, when did you have to push alignment across business, engineering, or delivery teams rather than just solve the technical problem yourself, and how did that change the outcome?",
                f"Give me an example from {target if rt == 'data' else 'your recent work'} where ownership expanded beyond coding into planning, delegation, governance, or stakeholder management. How did you handle it?",
            ]
            return (variants[(occurrence - 1) % len(variants)], evidence_text)
        variants = [
            "Tell me about a situation in your recent work where you had to align people, make a delivery decision, or take ownership beyond implementation. How did you handle it and what was the outcome?",
            "When did your role expand beyond writing code into unblocking others, shaping scope, or driving a delivery decision, and what happened because of that?",
        ]
        return (variants[(occurrence - 1) % len(variants)], evidence_text)
    return (f"What from {target} best represents how you work in practice?", evidence_text)


def _difficulty_for(role_family: str, category: str) -> str:
    if category in {"architecture", "leadership"}:
        return "hard" if role_family in {"architect", "manager", "practice_head", "lead"} else "medium"
    if category in {"debugging", "backend", "deep_dive", "project"}:
        return "medium"
    return "easy"


def _reference_answer_for(category: str) -> str:
    if category == "architecture":
        return "A strong answer should explain the design changes, trade-offs, scaling plan, and how reliability or observability would be validated."
    if category == "debugging":
        return "A strong answer should explain the failure signal, debugging steps, root cause, the fix, and how recurrence was prevented."
    if category == "backend":
        return "A strong answer should explain implementation structure, interfaces, data flow, operational concerns, and why that approach held up in practice."
    if category == "leadership":
        return "A strong answer should describe the situation, ownership taken, how alignment or delivery was handled, and the concrete result."
    if category == "project":
        return "A strong answer should clearly state the problem, the candidate's ownership, key decisions, execution details, and measurable impact."
    if category == "deep_dive":
        return "A strong answer should focus on a concrete implementation choice, trade-offs, reasoning, and lessons learned."
    return "A strong answer should explain the candidate's real contribution, decisions, execution details, validation approach, and outcomes."


def build_question(category: str, candidate: dict[str, object], context: PlannerContext, index: int, occurrence: int = 1) -> dict[str, object]:
    text, evidence_text = question_text(category, candidate, context, index, occurrence)
    skill_or_topic = str(candidate.get("label") or category)
    normalized_category = "behavioral" if category == "behavioral" else category
    public_category = "project" if category == "backend" else normalized_category
    metadata = {
        "category": public_category,
        "slot": category,
        "priority_source": str(candidate.get("priority_source") or "derived"),
        "skill_or_topic": skill_or_topic,
        "role_alignment": round(float(candidate.get("role_alignment") or 0.0), 3),
        "resume_alignment": round(float(candidate.get("resume_alignment") or 0.0), 3),
        "jd_alignment": round(float(candidate.get("jd_alignment") or 0.0), 3),
        "relevance_score": round(max(float(candidate.get("role_alignment") or 0.0), float(candidate.get("resume_alignment") or 0.0), float(candidate.get("jd_alignment") or 0.0)), 3),
        "role_family": context.role_family,
        "seniority": context.seniority,
        "evidence_excerpt": evidence_text,
    }
    return {
        "text": text,
        "type": "hr" if public_category == "behavioral" else public_category,
        "category": public_category,
        "topic": skill_or_topic[:80],
        "intent": f"Assess {category.replace('_', ' ')} depth aligned to the {context.role_family} profile.",
        "focus_skill": None,
        "project_name": (skill_or_topic[:160] if public_category in {"project", "architecture", "leadership"} else None),
        "reference_answer": _reference_answer_for(category),
        "difficulty": _difficulty_for(context.role_family, category),
        "priority_source": metadata["priority_source"],
        "role_alignment": metadata["role_alignment"],
        "resume_alignment": metadata["resume_alignment"],
        "jd_alignment": metadata["jd_alignment"],
        "metadata": metadata,
    }


def has_duplicate_structure(questions: list[dict[str, object]]) -> bool:
    similarity_seen: set[str] = set()
    first_six_seen: set[str] = set()
    openings: dict[str, int] = {}
    for question in questions:
        text = _clean(question.get("text"))
        similarity = re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", "", text.lower())).strip()
        first_six = " ".join(re.findall(r"[a-z0-9']+", text.lower())[:6])
        if similarity in similarity_seen or (first_six and first_six in first_six_seen):
            return True
        similarity_seen.add(similarity)
        first_six_seen.add(first_six)
        opening = " ".join(re.findall(r"[a-z0-9']+", text.lower())[:2])
        openings[opening] = openings.get(opening, 0) + 1
        if openings[opening] > 2:
            return True
    return False


def slot_order_for_context(context: PlannerContext, total_questions: int) -> list[str]:
    role_family = context.role_family
    rt = role_track(context)

    if role_family == "architect":
        slot_order = ["intro", "project", "architecture", "deep_dive", "debugging", "architecture", "leadership"]
    elif role_family in {"manager", "practice_head"}:
        slot_order = ["intro", "project", "deep_dive", "debugging", "architecture", "leadership", "leadership"]
    elif role_family == "lead":
        slot_order = ["intro", "project", "deep_dive", "debugging", "architecture", "leadership", "project"]
    else:
        slot_order = ["intro", "project", "deep_dive", "backend", "debugging", "architecture", "project"]

    if total_questions >= 8:
        if role_family == "architect":
            slot_order.append("architecture")
        elif role_family in {"manager", "practice_head", "lead"}:
            slot_order.append("leadership")
        elif rt == "data":
            slot_order.append("architecture")
        else:
            slot_order.append("project")
    if total_questions >= 9:
        if role_family in {"manager", "practice_head"}:
            slot_order.append("architecture")
        elif role_family == "architect":
            slot_order.append("project")
        elif rt == "data":
            slot_order.append("project")
        else:
            slot_order.append("deep_dive")
    return slot_order[:total_questions]
