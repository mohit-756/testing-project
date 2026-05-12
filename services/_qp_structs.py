from __future__ import annotations

import re
from dataclasses import dataclass, field

EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
PHONE_PATTERN = re.compile(r"\b\+?\d[\d\s().-]{7,}\b")
NAMEY_HEADER_PATTERN = re.compile(r"^[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3}$")
METRIC_PATTERN = re.compile(
    r"(\b\d+[\d,.]*\+?%\b|\b\d+x\b|\b\d+[\d,.]*\s*(?:ms|s|sec|seconds|minutes|hrs|hours|days|weeks|months|users|clients|customers|services|teams|engineers|apps|pipelines|projects|accounts|stores|records|events)\b)",
    re.IGNORECASE,
)
_CITY_LOCATION_RE = re.compile(
    r"\b(?:hyderabad|bangalore|chennai|mumbai|pune|delhi|guntur|andhra\s+pradesh|"
    r"telangana|india|karnataka|uttar\s+pradesh|rajasthan)\b",
    re.IGNORECASE,
)
_ALL_CAPS_NAME_RE = re.compile(r"^[A-Z]{2,}(?:\s+[A-Z]{2,}){0,3}$")

ROLE_FAMILY_KEYWORDS = {
    "practice_head": (
        "practice head", "head of", "delivery head", "practice lead", "practice manager", "capability head",
        "center of excellence", "coe lead", "practice director",
    ),
    "manager": (
        "engineering manager", "manager", "director", "vp", "vice president", "delivery manager", "program manager",
    ),
    "architect": (
        "architect", "solution architect", "enterprise architect", "principal architect", "platform architect",
    ),
    "lead": (
        "tech lead", "lead engineer", "technical lead", "team lead", "staff engineer", "principal engineer", "lead",
    ),
    "senior_engineer": (
        "senior", "sr.", "sr ", "sde 2", "sde2", "iii", "level 3", "software engineer ii",
    ),
    "engineer": (
        "engineer", "developer", "programmer", "sde", "software", "backend", "frontend", "full stack", "qa", "data engineer", "aiml engineer",
    ),
}

LEADERSHIP_TERMS = {
    "led", "owned", "mentored", "hired", "roadmap", "stakeholder", "strategy", "delivery", "managed", "budget",
    "cross-functional", "practice", "governance", "director", "head", "alignment", "capability",
}
ARCHITECTURE_TERMS = {
    "architecture", "scalable", "distributed", "microservices", "event-driven", "system design", "availability", "latency",
    "kafka", "cloud", "aws", "azure", "gcp", "platform", "governance", "lakehouse", "databricks",
}
FRONTEND_TERMS = {
    "frontend", "ui", "ux", "react", "javascript", "typescript", "next.js", "nextjs", "angular", "vue", "css",
    "component", "responsive", "browser", "accessibility", "figma",
}
BACKEND_TERMS = {
    "backend", "api", "service", "microservice", "fastapi", "django", "flask", "spring", "node", "java", "python",
    "postgres", "sql", "database", "integration", "webhook", "redis", "queue",
}
AIML_TERMS = {
    "aiml", "ai", "ml", "machine learning", "deep learning", "nlp", "llm", "rag", "prompt", "embedding", "inference",
    "model", "feature engineering", "evaluation", "mlops", "recall", "precision", "screening", "scoring", "ranking",
    "retrieval", "proctoring", "recommendation",
}
DATA_TERMS = {
    "data", "databricks", "lakehouse", "delta", "spark", "warehouse", "etl", "elt", "pipeline", "governance", "unity catalog",
    "airflow", "dbt", "analytics", "streaming", "medallion", "fabric",
}
RECENCY_TERMS = {"current", "present", "recent", "latest", "ongoing", "now"}

INTRO_QUESTION = {
    "text": "Please introduce yourself briefly and connect your background to this role, highlighting the project, platform, or business outcome that best represents your work.",
    "type": "intro",
    "category": "intro",
    "topic": "self_intro",
    "intent": "Understand the candidate's background, strongest evidence, and communication style.",
    "focus_skill": None,
    "project_name": None,
    "reference_answer": "A strong answer briefly covers background, the most relevant experience, direct contribution, impact, and what the candidate learned.",
    "difficulty": "easy",
    "priority_source": "baseline",
    "role_alignment": 1.0,
    "resume_alignment": 1.0,
    "jd_alignment": 1.0,
    "metadata": {
        "category": "intro",
        "priority_source": "baseline",
        "skill_or_topic": "self_intro",
        "role_alignment": 1.0,
        "resume_alignment": 1.0,
        "jd_alignment": 1.0,
        "relevance_score": 1.0,
    },
}


@dataclass
class EvidenceItem:
    text: str
    source: str
    recency: float = 0.4
    strength: float = 0.4
    leadership: float = 0.0
    architecture: float = 0.0
    measurable: float = 0.0
    kind_weight: float = 0.0
    label: str = ""
    skills: list[str] = field(default_factory=list)


@dataclass
class StructuredResume:
    summary: str
    skills: list[str]
    experiences: list[EvidenceItem]
    projects: list[EvidenceItem]
    certifications: list[str]
    leadership_signal: float
    architecture_signal: float
    inferred_years_band: str


@dataclass
class StructuredJD:
    title: str
    required_skills: list[str]
    keywords: list[str]
    leadership_signal: float
    architecture_signal: float


@dataclass
class PlannerContext:
    role_family: str
    seniority: str
    title: str
    resume: StructuredResume
    jd: StructuredJD
    topic_priorities: list[dict[str, object]]
    distribution: dict[str, int]
