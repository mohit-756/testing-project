from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ai_engine.phase2.question_plan import build_question_plan


def _questions(bundle):
    return bundle["questions"]


def test_junior_engineer_distribution_and_metadata():
    resume = """
    Jane Doe
    Summary
    Junior software engineer with 1+ years of experience building backend APIs and fixing production bugs.
    Skills
    Python
    FastAPI
    SQL
    Git
    Projects
    Issue tracker API using FastAPI and SQLite with auth and logging
    Experience
    Built REST APIs in Python, debugged SQL issues, and shipped bug fixes with mentor guidance
    """
    bundle = build_question_plan(
        resume_text=resume,
        jd_title="Backend Engineer",
        jd_skill_scores={"Python": 10, "FastAPI": 9, "SQL": 8, "Docker": 6},
        question_count=8,
    )
    questions = _questions(bundle)
    assert bundle["meta"]["role_family"] == "engineer"
    assert len(questions) == 8
    assert questions[0]["category"] == "intro"
    assert any(q["category"] == "deep_dive" for q in questions[1:])
    assert any(q["metadata"]["priority_source"] == "jd_resume_overlap" for q in questions[1:])
    assert all("metadata" in q for q in questions)



def test_architect_gets_architecture_focus():
    resume = """
    Alex Smith
    Summary
    Solution architect with 10+ years of experience designing distributed cloud systems and modernization programs.
    Skills
    AWS
    Kafka
    Python
    Microservices
    Projects
    Event driven payments platform migration across regions with Kafka and microservices
    Experience
    Led architecture for distributed services, defined integration patterns, and improved scalability and observability
    """
    bundle = build_question_plan(
        resume_text=resume,
        jd_title="Solution Architect",
        jd_skill_scores={"AWS": 10, "Kafka": 9, "Microservices": 10, "System Design": 9},
        question_count=8,
    )
    questions = _questions(bundle)
    categories = [q["category"] for q in questions]
    assert bundle["meta"]["role_family"] == "architect"
    assert categories.count("architecture") >= 2
    assert any(q["metadata"]["role_alignment"] >= 0.8 for q in questions if q["category"] == "architecture")



def test_fallback_plan_keeps_debugging_and_design_without_skill_clone_patterns():
    resume = """
    Backend engineer with 3+ years of experience building APIs and improving reliability.
    Skills
    Python
    FastAPI
    SQL
    Projects
    Payments API revamp reduced failures by 23% and improved partner onboarding
    Experience
    Built backend services, partner integrations, debugged production incidents, and redesigned API flows for maintainability
    """
    bundle = build_question_plan(
        resume_text=resume,
        jd_title="Backend Engineer",
        jd_skill_scores={"Python": 10, "FastAPI": 9, "SQL": 8, "API Design": 7},
        question_count=6,
    )
    texts = [q["text"].lower() for q in _questions(bundle)]
    assert any("debug" in text or "failure" in text or "root cause" in text for text in texts)
    assert any("design" in text or "architecture" in text for text in texts)
    assert not any(text.startswith("walk me through your ") for text in texts)



def test_practice_head_gets_leadership_focus_and_guardrails():
    resume = """
    Priya Rao
    Summary
    Practice head with 15+ years of experience in delivery leadership, stakeholder management, mentoring leaders, and scaling engineering teams.
    Skills
    Delivery Management
    Cloud
    Strategy
    Projects
    Global platform transformation for multiple enterprise clients
    Experience
    Owned roadmap, stakeholder alignment, team scaling, hiring, governance, and delivery outcomes across accounts
    """
    bundle = build_question_plan(
        resume_text=resume,
        jd_title="Practice Head - Digital Engineering",
        jd_skill_scores={"Delivery Management": 10, "Stakeholder Management": 9, "Cloud": 7, "Pega": 5},
        question_count=8,
    )
    questions = _questions(bundle)
    categories = [q["category"] for q in questions]
    assert bundle["meta"]["role_family"] == "practice_head"
    assert categories.count("leadership") >= 2
    weak_random = [q for q in questions if q["focus_skill"] == "Pega" and q["metadata"]["resume_alignment"] < 0.2]
    assert not weak_random
