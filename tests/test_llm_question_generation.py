from pathlib import Path
import sys
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.llm_answer_generator import generate_answer
from services.llm.client import _get_client, _llm_model, _llm_provider, _resolve_llm_config
from ai_engine.phase2.llm_question_generator import (
    LLM_QUESTION_SYSTEM_PROMPT,
    build_structured_question_input,
    generate_llm_questions,
    generate_question_bundle_with_fallback,
)
from ai_engine.phase2.question_generation import build_question_bundle


class _FakeMessage:
    def __init__(self, content: str):
        self.content = content


class _FakeChoice:
    def __init__(self, content: str):
        self.message = _FakeMessage(content)


class _FakeResponse:
    def __init__(self, content: str):
        self.choices = [_FakeChoice(content)]


class _SequencedCompletions:
    def __init__(self, contents: list[str]):
        self._contents = list(contents)
        self.calls = 0

    def create(self, **kwargs):
        index = min(self.calls, len(self._contents) - 1)
        self.calls += 1
        return _FakeResponse(self._contents[index])


class _SequencedClient:
    def __init__(self, contents: list[str]):
        self._completions = _SequencedCompletions(contents)
        self.chat = type("_FakeChat", (), {"completions": self._completions})()

    def create(self, **kwargs):
        return self._completions.create(**kwargs)

    @property
    def calls(self):
        return self._completions.calls


def test_generate_llm_questions_postprocesses_duplicates_and_noise(monkeypatch):
    fake_json = """
    {
      "questions": [
        {
          "text": "Please introduce yourself briefly and highlight the project or work that best matches this backend role?",
          "category": "intro",
          "focus_skill": null,
          "project_name": null,
          "intent": "Assess background fit and communication.",
          "reference_answer": "A strong answer should connect experience, strongest project, impact, and motivation.",
          "difficulty": "easy",
          "priority_source": "baseline",
          "rationale": "Opens with a resume-aware summary prompt."
        },
        {
          "text": "In the issue tracker API project, what backend problem were you solving, what did you personally own, and how did you validate auth and logging behavior before shipping?",
          "category": "project",
          "focus_skill": "FastAPI",
          "project_name": "Issue tracker API using FastAPI and SQLite with auth and logging",
          "intent": "Assess practical backend implementation depth.",
          "reference_answer": "A strong answer should explain architecture, auth flow, logging, validation, ownership boundaries, and lessons learned.",
          "difficulty": "medium",
          "priority_source": "recent_project",
          "rationale": "Issue tracker API using FastAPI and SQLite with auth and logging"
        },
        {
          "text": "When you debugged SQL issues in production-like scenarios, what signals helped you isolate the root cause quickly and how did you verify the fix?",
          "category": "deep_dive",
          "focus_skill": "SQL",
          "project_name": null,
          "intent": "Assess debugging depth.",
          "reference_answer": "A strong answer should cover reproduction, observability, narrowing hypotheses, validating fixes, and preventing recurrence.",
          "difficulty": "medium",
          "priority_source": "jd_resume_overlap",
          "rationale": "Built REST APIs in Python, debugged SQL issues, and shipped bug fixes with mentor guidance"
        },
        {
          "text": "If this service had to support 10x usage, what API, data, and observability trade-offs would you revisit first in the issue tracker design?",
          "category": "architecture_or_design",
          "focus_skill": "FastAPI",
          "project_name": "Issue tracker API using FastAPI and SQLite with auth and logging",
          "intent": "Assess scaling judgment.",
          "reference_answer": "A strong answer should explain expected bottlenecks, design options, trade-offs, and a validation plan.",
          "difficulty": "medium",
          "priority_source": "architecture_signal",
          "rationale": "Issue tracker API using FastAPI and SQLite with auth and logging"
        },
        {
          "text": "Docker is important in this JD. Given your FastAPI service experience, how would you package, configure, and locally verify that service in a containerized workflow?",
          "category": "deep_dive",
          "focus_skill": "Docker",
          "project_name": null,
          "intent": "Assess practical transfer ability on a critical JD skill.",
          "reference_answer": "A strong answer should explain Dockerfile structure, configuration handling, runtime choices, and local verification.",
          "difficulty": "medium",
          "priority_source": "jd_gap_probe",
          "rationale": "JD asks for Docker but resume evidence is weak."
        },
        {
          "text": "Describe a time a backend requirement changed midway and how you adjusted your implementation plan without losing correctness or delivery momentum?",
          "category": "behavioral",
          "focus_skill": null,
          "project_name": null,
          "intent": "Assess adaptability.",
          "reference_answer": "A strong answer should describe the change, decision process, communication, execution changes, and outcome.",
          "difficulty": "easy",
          "priority_source": "resume_strength",
          "rationale": "Shipped bug fixes with mentor guidance under delivery pressure."
        }
      ]
    }
    """
    monkeypatch.setattr("ai_engine.phase2.llm_question_generator._get_client", lambda: _SequencedClient([fake_json]))
    monkeypatch.setattr("ai_engine.phase2.llm_question_generator._llm_model", lambda: "fake-model")

    result = generate_llm_questions(
        jd_text="Backend Engineer role requiring Python, FastAPI, SQL, Docker.",
        resume_text="""
        Junior software engineer with 1+ years of experience building backend APIs and fixing production bugs.
        Skills: Python, FastAPI, SQL, Git.
        Projects: Issue tracker API using FastAPI and SQLite with auth and logging.
        Experience: Built REST APIs in Python, debugged SQL issues, and shipped bug fixes with mentor guidance.
        """,
        question_count=6,
        jd_title="Backend Engineer",
        jd_skill_scores={"Python": 10, "FastAPI": 9, "SQL": 8, "Docker": 6},
    )

    questions = result["questions"]
    assert len(questions) == 6
    assert questions[0]["category"] == "intro"
    assert len({q["text"] for q in questions}) == 6
    assert any(q["category"] == "architecture" for q in questions)
    assert any(q["category"] == "behavioral" for q in questions)
    assert any(q["category"] == "project" for q in questions)
    assert all(len(q["text"]) > 20 for q in questions)
    assert result["system_prompt"] == LLM_QUESTION_SYSTEM_PROMPT
    assert result["quality"]["retry_used"] is False


def test_generate_llm_questions_retries_once_when_first_output_is_generic(monkeypatch):
    generic_first = """
    {
      "questions": [
        {"text": "Please introduce yourself briefly and highlight your most relevant project?", "category": "intro", "focus_skill": null, "project_name": null, "intent": "intro", "reference_answer": "intro answer", "difficulty": "easy", "priority_source": "baseline", "rationale": "intro"},
        {"text": "Walk me through your most relevant project?", "category": "project", "focus_skill": null, "project_name": null, "intent": "generic", "reference_answer": "generic", "difficulty": "medium", "priority_source": "resume_strength", "rationale": "generic"},
        {"text": "Walk me through your React experience?", "category": "deep_dive", "focus_skill": "React", "project_name": null, "intent": "generic", "reference_answer": "generic", "difficulty": "medium", "priority_source": "jd_resume_overlap", "rationale": "generic"},
        {"text": "Walk me through your JavaScript experience?", "category": "deep_dive", "focus_skill": "JavaScript", "project_name": null, "intent": "generic", "reference_answer": "generic", "difficulty": "medium", "priority_source": "jd_resume_overlap", "rationale": "generic"},
        {"text": "Describe a time you handled stakeholders?", "category": "behavioral", "focus_skill": null, "project_name": null, "intent": "generic", "reference_answer": "generic", "difficulty": "easy", "priority_source": "resume_strength", "rationale": "generic"},
        {"text": "Describe a time you handled conflict?", "category": "behavioral", "focus_skill": null, "project_name": null, "intent": "generic", "reference_answer": "generic", "difficulty": "easy", "priority_source": "resume_strength", "rationale": "generic"}
      ]
    }
    """
    improved_second = """
    {
      "questions": [
        {"text": "Please introduce yourself briefly, focusing on the frontend work or product area where you had the clearest ownership and user impact?", "category": "intro", "focus_skill": null, "project_name": null, "intent": "Assess background and strongest evidence.", "reference_answer": "A strong answer should connect background, strongest frontend work, impact, and motivation.", "difficulty": "easy", "priority_source": "baseline", "rationale": "Resume shows ownership across frontend delivery."},
        {"text": "In the analytics dashboard rebuild, what interaction or rendering problem were you solving, what did you personally change in React, and how did you confirm the UI became faster or easier to use?", "category": "project", "focus_skill": "React", "project_name": "Analytics dashboard rebuild for customer operations", "intent": "Assess concrete frontend implementation depth.", "reference_answer": "A strong answer should explain the problem, ownership, React implementation details, validation metrics, and user outcome.", "difficulty": "medium", "priority_source": "recent_project", "rationale": "Analytics dashboard rebuild for customer operations improved page performance by 32%."},
        {"text": "When you built reusable components in the design system, how did you balance consistency, flexibility, and developer adoption across product teams?", "category": "deep_dive", "focus_skill": "React", "project_name": "Reusable design system", "intent": "Assess component architecture and practical trade-offs.", "reference_answer": "A strong answer should cover component boundaries, API choices, migration strategy, and adoption trade-offs.", "difficulty": "medium", "priority_source": "jd_resume_overlap", "rationale": "Built reusable component library adopted across product surfaces."},
        {"text": "The resume mentions a 32% page-performance improvement. Which frontend bottlenecks did you find first, what debugging tools did you use, and what changes moved the metric the most?", "category": "deep_dive", "focus_skill": "JavaScript", "project_name": "Analytics dashboard rebuild for customer operations", "intent": "Assess debugging and performance depth.", "reference_answer": "A strong answer should describe bottleneck discovery, tooling, implemented fixes, and measured impact.", "difficulty": "medium", "priority_source": "resume_strength", "rationale": "Improved page performance by 32% in analytics dashboard rebuild."},
        {"text": "If this product had to support twice the feature surface without slowing down, how would you evolve the frontend architecture, state boundaries, and observability strategy?", "category": "architecture", "focus_skill": "Frontend Architecture", "project_name": "Analytics dashboard rebuild for customer operations", "intent": "Assess system design judgment for frontend scale.", "reference_answer": "A strong answer should explain architecture options, state-management trade-offs, observability, and scaling decisions.", "difficulty": "medium", "priority_source": "architecture_signal", "rationale": "Resume shows component architecture and performance optimization work."},
        {"text": "Describe a release where product expectations changed late. How did you reset scope with design or product partners while still shipping a stable frontend experience?", "category": "behavioral", "focus_skill": null, "project_name": null, "intent": "Assess collaboration and prioritization.", "reference_answer": "A strong answer should cover expectation reset, stakeholder communication, prioritization, execution, and outcome.", "difficulty": "easy", "priority_source": "resume_strength", "rationale": "Frontend delivery requires close product/design coordination."}
      ]
    }
    """
    client = _SequencedClient([generic_first, improved_second])
    monkeypatch.setattr("ai_engine.phase2.llm_question_generator._get_client", lambda: client)
    monkeypatch.setattr("ai_engine.phase2.llm_question_generator._llm_model", lambda: "fake-model")

    result = generate_llm_questions(
        jd_text="Frontend Engineer responsible for React, JavaScript, performance optimization, reusable components, and collaboration with product/design.",
        resume_text="""
        Frontend engineer with 4+ years of experience building product UIs.
        Skills: React, JavaScript, TypeScript, Performance Optimization.
        Projects: Analytics dashboard rebuild for customer operations improved page performance by 32%; Reusable design system adopted across product teams.
        Experience: Built reusable component libraries, optimized rendering bottlenecks, and collaborated with product and design on releases.
        """,
        question_count=6,
        jd_title="Frontend Engineer",
        jd_skill_scores={"React": 10, "JavaScript": 9, "TypeScript": 8, "Performance Optimization": 8},
    )

    assert client.calls == 2
    assert result["quality"]["retry_used"] is True
    assert result["quality"]["first_attempt_issues"]
    assert len(result["questions"]) == 6
    assert any(q["category"] == "project" for q in result["questions"])


def test_build_question_bundle_falls_back_to_dynamic_planner(monkeypatch):
    def _boom(*args, **kwargs):
        raise RuntimeError("groq temporarily unavailable")

    monkeypatch.setattr("ai_engine.phase2.llm_question_generator.generate_llm_questions", _boom)

    bundle = build_question_bundle(
        resume_text="""
        Solution architect with 10+ years of experience designing distributed cloud systems.
        Skills: AWS, Kafka, Python, Microservices.
        Projects: Event driven payments platform migration across regions with Kafka and microservices.
        Experience: Led architecture for distributed services and modernization programs.
        """,
        jd_title="Solution Architect",
        jd_skill_scores={"AWS": 10, "Kafka": 9, "Microservices": 10, "System Design": 9},
        question_count=8,
    )

    assert bundle["meta"]["fallback_used"] is True
    assert bundle["meta"]["generation_mode"] == "fallback_dynamic_plan"
    assert len(bundle["questions"]) == 8
    assert bundle["questions"][0]["category"] == "intro"
    assert any(q["category"] == "architecture" for q in bundle["questions"])


def test_structured_input_is_dynamic_and_role_aware():
    structured = build_structured_question_input(
        resume_text="""
        Practice head with 15+ years of experience in delivery leadership, stakeholder management, mentoring leaders, and scaling engineering teams.
        Skills: Delivery Management, Cloud, Strategy.
        Projects: Global platform transformation for multiple enterprise clients.
        Experience: Owned roadmap, stakeholder alignment, team scaling, hiring, governance, and delivery outcomes across accounts.
        Certifications: AWS Certified Solutions Architect.
        """,
        jd_title="Practice Head - Digital Engineering",
        jd_skill_scores={"Delivery Management": 10, "Stakeholder Management": 9, "Cloud": 7, "Pega": 5},
    )

    assert structured.role == "Practice Head - Digital Engineering"
    assert structured.role_family == "practice_head"
    assert structured.seniority in {"practice_head", "manager", "lead"}
    assert structured.experience_level in {"executive", "staff_plus"}
    assert "Delivery Management" in structured.resume_skills
    assert "Cloud" in structured.overlap_skills
    assert "Pega" in structured.jd_only_skills
    assert structured.resume_projects
    assert structured.resume_leadership_signals


def test_validate_three_priority_profiles_with_retry_and_fallback(monkeypatch):
    frontend_json = """
    {
      "questions": [
        {"text": "Please introduce yourself briefly, focusing on the frontend work where you had the clearest ownership and impact?", "category": "intro", "focus_skill": null, "project_name": null, "intent": "intro", "reference_answer": "good", "difficulty": "easy", "priority_source": "baseline", "rationale": "frontend intro"},
        {"text": "In the analytics dashboard rebuild, what did you personally change in React, and how did you verify the 32% performance gain?", "category": "project", "focus_skill": "React", "project_name": "Analytics dashboard rebuild", "intent": "project depth", "reference_answer": "good answer", "difficulty": "medium", "priority_source": "recent_project", "rationale": "Analytics dashboard rebuild improved page performance by 32%."},
        {"text": "When you built the reusable design system, how did you decide component boundaries and API patterns across teams?", "category": "deep_dive", "focus_skill": "React", "project_name": "Reusable design system", "intent": "component architecture", "reference_answer": "good answer", "difficulty": "medium", "priority_source": "jd_resume_overlap", "rationale": "Reusable design system adopted across teams."},
        {"text": "Which rendering or state bottlenecks did you debug first in that dashboard, and what signals told you the fixes were working?", "category": "deep_dive", "focus_skill": "JavaScript", "project_name": "Analytics dashboard rebuild", "intent": "debugging", "reference_answer": "good answer", "difficulty": "medium", "priority_source": "resume_strength", "rationale": "Improved page performance by 32%."},
        {"text": "If the product scope doubled, how would you evolve the frontend architecture, state boundaries, and observability strategy without regressing UX?", "category": "architecture", "focus_skill": "Frontend Architecture", "project_name": "Analytics dashboard rebuild", "intent": "architecture", "reference_answer": "good answer", "difficulty": "medium", "priority_source": "architecture_signal", "rationale": "architecture and performance work"},
        {"text": "Describe a release where product expectations changed late. How did you reset scope with design or product partners and still ship a stable experience?", "category": "behavioral", "focus_skill": null, "project_name": null, "intent": "collaboration", "reference_answer": "good answer", "difficulty": "easy", "priority_source": "resume_strength", "rationale": "collaboration with product and design"}
      ]
    }
    """
    aiml_json = """
    {
      "questions": [
        {"text": "Please introduce yourself briefly, focusing on the ML product or pipeline where your contribution and measurable impact were strongest?", "category": "intro", "focus_skill": null, "project_name": null, "intent": "intro", "reference_answer": "good", "difficulty": "easy", "priority_source": "baseline", "rationale": "AIML intro"},
        {"text": "In the fraud detection pipeline, what features or model changes did you personally drive, and how did they improve precision or recall in production?", "category": "project", "focus_skill": "Machine Learning", "project_name": "Fraud detection pipeline", "intent": "ml impact", "reference_answer": "good answer", "difficulty": "medium", "priority_source": "recent_project", "rationale": "Improved fraud recall by 18% and reduced false positives by 11%."},
        {"text": "How did you choose between classical models and transformer-based approaches in your recent NLP work, and what trade-offs mattered most for the business constraint?", "category": "deep_dive", "focus_skill": "NLP", "project_name": "Support ticket triage model", "intent": "model choice", "reference_answer": "good answer", "difficulty": "hard", "priority_source": "jd_resume_overlap", "rationale": "Built NLP triage model for support workflows."},
        {"text": "When model quality drifted after deployment, what monitoring signals alerted you, how did you diagnose the root cause, and what remediation path did you take?", "category": "deep_dive", "focus_skill": "MLOps", "project_name": "Fraud detection pipeline", "intent": "mlops depth", "reference_answer": "good answer", "difficulty": "hard", "priority_source": "jd_resume_overlap", "rationale": "Managed ML pipeline monitoring and retraining triggers."},
        {"text": "If transaction volume increased 5x, how would you redesign the feature pipeline, model-serving path, and rollback strategy to keep latency and reliability under control?", "category": "architecture", "focus_skill": "ML Systems", "project_name": "Fraud detection pipeline", "intent": "ml system design", "reference_answer": "good answer", "difficulty": "hard", "priority_source": "architecture_signal", "rationale": "production ML pipeline architecture"},
        {"text": "Describe a time you had to explain a model trade-off to product, risk, or operations stakeholders and align on the final decision?", "category": "behavioral", "focus_skill": null, "project_name": null, "intent": "stakeholder communication", "reference_answer": "good answer", "difficulty": "easy", "priority_source": "resume_strength", "rationale": "cross-functional ML delivery"}
      ]
    }
    """
    leadership_first_bad = """
    {
      "questions": [
        {"text": "Please introduce yourself briefly and highlight your most relevant project?", "category": "intro", "focus_skill": null, "project_name": null, "intent": "intro", "reference_answer": "good", "difficulty": "easy", "priority_source": "baseline", "rationale": "generic"},
        {"text": "Walk me through your Databricks experience?", "category": "deep_dive", "focus_skill": "Databricks", "project_name": null, "intent": "generic", "reference_answer": "good", "difficulty": "medium", "priority_source": "jd_resume_overlap", "rationale": "generic"},
        {"text": "Walk me through your leadership experience?", "category": "behavioral", "focus_skill": null, "project_name": null, "intent": "generic", "reference_answer": "good", "difficulty": "easy", "priority_source": "resume_strength", "rationale": "generic"},
        {"text": "Walk me through your stakeholder experience?", "category": "behavioral", "focus_skill": null, "project_name": null, "intent": "generic", "reference_answer": "good", "difficulty": "easy", "priority_source": "resume_strength", "rationale": "generic"},
        {"text": "Walk me through your architecture experience?", "category": "deep_dive", "focus_skill": "Architecture", "project_name": null, "intent": "generic", "reference_answer": "good", "difficulty": "medium", "priority_source": "resume_strength", "rationale": "generic"},
        {"text": "Describe a conflict?", "category": "behavioral", "focus_skill": null, "project_name": null, "intent": "generic", "reference_answer": "good", "difficulty": "easy", "priority_source": "resume_strength", "rationale": "generic"}
      ]
    }
    """
    leadership_second_good = """
    {
      "questions": [
        {"text": "Please introduce yourself briefly, focusing on the Databricks or data-platform transformation where your leadership and business impact were strongest?", "category": "intro", "focus_skill": null, "project_name": null, "intent": "intro", "reference_answer": "good", "difficulty": "easy", "priority_source": "baseline", "rationale": "leadership intro"},
        {"text": "In the enterprise lakehouse modernization program, what operating model or platform decisions did you personally drive, and what measurable business or delivery outcomes followed?", "category": "project", "focus_skill": "Databricks", "project_name": "Enterprise lakehouse modernization program", "intent": "practice leadership", "reference_answer": "good answer", "difficulty": "hard", "priority_source": "recent_project", "rationale": "Scaled delivery across 6 accounts and improved platform adoption by 40%."},
        {"text": "As a practice head, how did you decide which Databricks capabilities or accelerators should become reusable offerings across accounts, and what trade-offs did you make between standardization and client flexibility?", "category": "leadership", "focus_skill": "Databricks", "project_name": "Databricks practice acceleration", "intent": "practice building", "reference_answer": "good answer", "difficulty": "hard", "priority_source": "leadership_signal", "rationale": "Built reusable offerings and mentored delivery leaders across accounts."},
        {"text": "When a large client needed architectural changes in the lakehouse platform, how did you evaluate design trade-offs around governance, cost, performance, and team capability before committing?", "category": "architecture", "focus_skill": "Lakehouse Architecture", "project_name": "Enterprise lakehouse modernization program", "intent": "architecture trade-offs", "reference_answer": "good answer", "difficulty": "hard", "priority_source": "architecture_signal", "rationale": "Owned governance, platform strategy, and delivery outcomes across accounts."},
        {"text": "Describe a situation where you had to align senior stakeholders, delivery leaders, and client teams around a difficult platform or staffing decision. What did you do and what changed?", "category": "leadership", "focus_skill": null, "project_name": null, "intent": "stakeholder leadership", "reference_answer": "good answer", "difficulty": "hard", "priority_source": "leadership_signal", "rationale": "Stakeholder alignment, team scaling, hiring, governance, and delivery outcomes across accounts."},
        {"text": "If this practice had to scale Databricks delivery across several new enterprise clients next quarter, what capabilities, governance mechanisms, and risk controls would you put in place first?", "category": "architecture", "focus_skill": "Databricks Practice", "project_name": "Databricks practice acceleration", "intent": "scaling strategy", "reference_answer": "good answer", "difficulty": "hard", "priority_source": "architecture_signal", "rationale": "Scaled delivery across 6 accounts and mentored leaders."}
      ]
    }
    """

    client = _SequencedClient([frontend_json, aiml_json, leadership_first_bad, leadership_second_good])
    monkeypatch.setattr("ai_engine.phase2.llm_question_generator._get_client", lambda: client)
    monkeypatch.setattr("ai_engine.phase2.llm_question_generator._llm_model", lambda: "fake-model")

    frontend = generate_llm_questions(
        jd_text="Frontend Engineer responsible for React, JavaScript, TypeScript, performance optimization, reusable components, and collaboration with product/design.",
        resume_text="""
        Frontend engineer with 4+ years of experience building product UIs.
        Skills: React, JavaScript, TypeScript, Performance Optimization.
        Projects: Analytics dashboard rebuild improved page performance by 32%; Reusable design system adopted across product teams.
        Experience: Built reusable component libraries, optimized rendering bottlenecks, and collaborated with product and design on releases.
        """,
        question_count=6,
        jd_title="Frontend Engineer",
        jd_skill_scores={"React": 10, "JavaScript": 9, "TypeScript": 8, "Performance Optimization": 8},
    )
    assert frontend["structured_input"]["role_family"] in {"engineer", "senior_engineer"}
    assert frontend["quality"]["retry_used"] is False

    aiml = generate_llm_questions(
        jd_text="AIML Engineer responsible for machine learning, NLP, MLOps, experimentation, model monitoring, and stakeholder communication.",
        resume_text="""
        AIML engineer with 5+ years of experience building ML products.
        Skills: Machine Learning, NLP, Python, MLOps.
        Projects: Fraud detection pipeline improved recall by 18% and reduced false positives by 11%; Support ticket triage model for enterprise operations.
        Experience: Built training pipelines, monitored drift, and partnered with product and risk teams on model deployment decisions.
        """,
        question_count=6,
        jd_title="AIML Engineer",
        jd_skill_scores={"Machine Learning": 10, "NLP": 9, "MLOps": 8, "Experimentation": 7},
    )
    assert aiml["structured_input"]["role_family"] in {"engineer", "senior_engineer", "lead"}
    assert aiml["quality"]["retry_used"] is False

    leadership = generate_llm_questions(
        jd_text="Databricks Practice Head responsible for Databricks strategy, lakehouse architecture, stakeholder leadership, governance, delivery excellence, capability building, and scaling multi-account practice outcomes.",
        resume_text="""
        Databricks practice head with 15+ years of experience in data engineering and delivery leadership.
        Skills: Databricks, Lakehouse, Stakeholder Management, Delivery Governance.
        Projects: Enterprise lakehouse modernization program scaled delivery across 6 accounts and improved platform adoption by 40%; Databricks practice acceleration initiative.
        Experience: Owned roadmap, stakeholder alignment, team scaling, hiring, governance, reusable offerings, and mentoring delivery leaders across accounts.
        """,
        question_count=6,
        jd_title="Databricks Practice Head",
        jd_skill_scores={"Databricks": 10, "Lakehouse Architecture": 9, "Stakeholder Management": 9, "Delivery Governance": 8},
    )
    assert leadership["structured_input"]["role_family"] == "practice_head"
    assert leadership["quality"]["retry_used"] is True
    assert any(q["category"] == "leadership" for q in leadership["questions"])
    assert any(q["category"] == "architecture" for q in leadership["questions"])


def test_generate_question_bundle_with_fallback_runtime_shape(monkeypatch):
    def _boom(*args, **kwargs):
        raise RuntimeError("llm down")

    monkeypatch.setattr("ai_engine.phase2.llm_question_generator.generate_llm_questions", _boom)

    bundle = generate_question_bundle_with_fallback(
        resume_text="""
        Backend engineer with 3+ years experience.
        Skills: Python, FastAPI, SQL.
        Projects: Internal ticketing service.
        Experience: Built APIs and fixed production issues.
        """,
        jd_title="Backend Engineer",
        jd_skill_scores={"Python": 10, "FastAPI": 9, "SQL": 8},
        question_count=6,
    )

    assert set(["questions", "total_questions", "project_count", "hr_count", "project_questions_count", "theory_questions_count", "intro_count", "projects", "meta"]).issubset(bundle.keys())
    assert len(bundle["questions"]) == 6


def test_generate_llm_questions_retries_on_missing_debugging_and_design(monkeypatch):
    first = """
    {
      "questions": [
        {"text": "Please introduce yourself briefly, focusing on the product area where your ownership was strongest?", "category": "intro", "focus_skill": null, "project_name": null, "intent": "intro", "reference_answer": "good answer", "difficulty": "easy", "priority_source": "baseline", "rationale": "intro"},
        {"text": "In the payments API revamp, what problem were you solving and what did you personally implement in FastAPI?", "category": "project", "focus_skill": "FastAPI", "project_name": "Payments API revamp", "intent": "project", "reference_answer": "good answer", "difficulty": "medium", "priority_source": "recent_project", "rationale": "Payments API revamp reduced failures by 23%."},
        {"text": "How did you collaborate with product on the payments API revamp roadmap?", "category": "behavioral", "focus_skill": null, "project_name": null, "intent": "collaboration", "reference_answer": "good answer", "difficulty": "easy", "priority_source": "resume_strength", "rationale": "collaboration"},
        {"text": "Which backend choices helped the service stay maintainable as usage increased?", "category": "deep_dive", "focus_skill": "Python", "project_name": null, "intent": "implementation", "reference_answer": "good answer", "difficulty": "medium", "priority_source": "jd_resume_overlap", "rationale": "backend service work"},
        {"text": "How did you approach integrating the service with external systems and data sources?", "category": "deep_dive", "focus_skill": "API Integration", "project_name": "Payments API revamp", "intent": "integration", "reference_answer": "good answer", "difficulty": "medium", "priority_source": "jd_resume_overlap", "rationale": "integration work"},
        {"text": "What kind of ownership did you take when deadlines became tight?", "category": "behavioral", "focus_skill": null, "project_name": null, "intent": "ownership", "reference_answer": "good answer", "difficulty": "easy", "priority_source": "resume_strength", "rationale": "ownership"}
      ]
    }
    """
    second = """
    {
      "questions": [
        {"text": "Please introduce yourself briefly, focusing on the backend project where your ownership and impact were strongest?", "category": "intro", "focus_skill": null, "project_name": null, "intent": "intro", "reference_answer": "good answer", "difficulty": "easy", "priority_source": "baseline", "rationale": "intro"},
        {"text": "In the payments API revamp, what problem were you solving, what did you personally own, and which outcome showed the redesign was working?", "category": "project", "focus_skill": "FastAPI", "project_name": "Payments API revamp", "intent": "project", "reference_answer": "good answer", "difficulty": "medium", "priority_source": "recent_project", "rationale": "Payments API revamp reduced failures by 23% and improved partner onboarding."},
        {"text": "When you redesigned the payments API revamp, how did you decide the service boundaries, request contracts, and data flow between internal and partner systems?", "category": "architecture", "focus_skill": "API Design", "project_name": "Payments API revamp", "intent": "design", "reference_answer": "good answer", "difficulty": "medium", "priority_source": "architecture_signal", "rationale": "API design and partner integration work."},
        {"text": "Describe a debugging or failure issue from the payments API revamp: what signal told you something was wrong, how did you isolate the root cause, and what prevented recurrence?", "category": "deep_dive", "focus_skill": "Debugging", "project_name": "Payments API revamp", "intent": "debugging", "reference_answer": "good answer", "difficulty": "medium", "priority_source": "resume_strength", "rationale": "Reduced failures by 23% after production issue remediation."},
        {"text": "If transaction volume doubled for the payments API revamp, what performance bottlenecks would you expect first and what scaling changes would you make?", "category": "deep_dive", "focus_skill": "Performance", "project_name": "Payments API revamp", "intent": "scaling", "reference_answer": "good answer", "difficulty": "medium", "priority_source": "jd_resume_overlap", "rationale": "Backend API scaling and reliability."},
        {"text": "Tell me about a release on the payments API revamp where you had to align engineering and product trade-offs while still keeping partner integrations stable.", "category": "behavioral", "focus_skill": null, "project_name": null, "intent": "leadership", "reference_answer": "good answer", "difficulty": "easy", "priority_source": "resume_strength", "rationale": "cross-functional release ownership"}
      ]
    }
    """
    client = _SequencedClient([first, second])
    monkeypatch.setattr("ai_engine.phase2.llm_question_generator._get_client", lambda: client)
    monkeypatch.setattr("ai_engine.phase2.llm_question_generator._llm_model", lambda: "fake-model")

    result = generate_llm_questions(
        jd_text="Backend Engineer role requiring Python, FastAPI, API design, debugging, integrations, and performance tuning.",
        resume_text="""
        Backend engineer with 3+ years of experience building APIs.
        Skills: Python, FastAPI, SQL, API Integration.
        Projects: Payments API revamp reduced failures by 23% and improved partner onboarding.
        Experience: Built backend services, handled partner integrations, debugged production issues, and improved service reliability.
        """,
        question_count=6,
        jd_title="Backend Engineer",
        jd_skill_scores={"Python": 10, "FastAPI": 9, "API Design": 8, "Performance": 8},
    )

    assert client.calls == 2
    assert result["quality"]["retry_used"] is True
    assert any("missing_failure_debugging_tradeoff_question" == issue for issue in result["quality"]["first_attempt_issues"])
    assert any(q["category"] == "architecture" for q in result["questions"])


def test_llm_client_prefers_ollama_model(monkeypatch):
    _resolve_llm_config.cache_clear()
    _get_client.cache_clear()
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.setenv("OLLAMA_MODEL", "qwen2.5-coder:3b")

    client = _get_client()

    assert client is not None
    assert _llm_provider() == "ollama"
    assert _llm_model() == "qwen2.5-coder:3b"

    _resolve_llm_config.cache_clear()
    _get_client.cache_clear()


def test_generate_answer_returns_candidate_style_text(monkeypatch):
    class _AnswerClient:
        def __init__(self, content: str):
            self.chat = type("_FakeChat", (), {"completions": _SequencedCompletions([content])})()

    monkeypatch.setattr(
        "services.llm_answer_generator._get_client",
        lambda: _AnswerClient(
            "I worked on a payments API revamp where partner failures were causing support escalations. I owned the FastAPI service changes, tightened request validation, and added better logging around partner callbacks so we could isolate bad payloads quickly. I chose to keep the first iteration simple with clearer service boundaries instead of introducing more infrastructure, because the immediate need was stability and faster onboarding. That reduced failures by 23%, improved partner onboarding, and gave us a cleaner base for later scaling."
        ),
    )
    monkeypatch.setattr("services.llm_answer_generator._llm_model", lambda: "fake-model")

    answer = generate_answer(
        "Tell me about a debugging issue in your payments API revamp.",
        "Projects: Payments API revamp reduced failures by 23%. Experience: Built FastAPI services, partner integrations, and debugging fixes.",
        "Backend Engineer role requiring API design, debugging, and integrations.",
    )

    assert "I " in answer
    assert "FastAPI" in answer
    assert "23%" in answer
