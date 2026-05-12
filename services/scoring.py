"""Central ATS scoring and ranking helpers.

This module keeps the practical weighted scoring model in one place so resume,
interview, ranking, analytics, and HR detail pages all use the same numbers.
"""

from __future__ import annotations

from statistics import mean

from ai_engine.phase1.scoring import _clamp_score, compute_answer_scorecard

STAGE_ORDER = {
    "applied": 1,
    "screening": 2,
    "shortlisted": 3,
    "interview_scheduled": 4,
    "interview_completed": 5,
    "selected": 6,
    "rejected": 0,
}

DEFAULT_WEIGHTS = {
    "resume": 0.35,
    "skills": 0.25,
    "interview": 0.25,
    "communication": 0.15,
}


def recommendation_for_score(final_score: float) -> str:
    if final_score >= 75:
        return "Select"
    if final_score >= 45:
        return "Shortlist"
    return "Weak"


def evaluate_answer(question: str, answer: str, *, allotted_seconds: int = 0, time_taken_seconds: int = 0, jd_skills=()):
    scorecard = compute_answer_scorecard(
        question,
        answer,
        allotted_seconds=allotted_seconds,
        time_taken_seconds=time_taken_seconds,
        jd_skills=jd_skills,
    )
    answer_text = (answer or "").strip()
    strengths: list[str] = []
    weaknesses: list[str] = []
    suggestions: list[str] = []

    if scorecard["relevance"] >= 70:
        strengths.append("Answer stayed relevant to the question.")
    else:
        weaknesses.append("Answer drifted away from the original question.")
        suggestions.append("Start by addressing the exact question directly.")

    if scorecard["completeness"] >= 70:
        strengths.append("Response included useful depth and substance.")
    else:
        weaknesses.append("Response lacked enough depth or examples.")
        suggestions.append("Add a concrete example, action, and outcome.")

    if scorecard["clarity"] >= 70:
        strengths.append("Explanation was clear and reasonably structured.")
    else:
        weaknesses.append("Explanation could be clearer and more structured.")
        suggestions.append("Use a simple structure: context, action, result.")

    confidence_score = _clamp_score((scorecard["clarity"] * 0.6) + (scorecard["time_fit"] * 0.4))
    technical_correctness = _clamp_score((scorecard["relevance"] * 0.7) + (scorecard["completeness"] * 0.3))
    overall_score = _clamp_score(
        (scorecard["relevance"] * 0.25)
        + (technical_correctness * 0.30)
        + (scorecard["clarity"] * 0.20)
        + (confidence_score * 0.15)
        + (scorecard["completeness"] * 0.10)
    )

    return {
        "relevance": scorecard["relevance"],
        "technical_correctness": technical_correctness,
        "clarity": scorecard["clarity"],
        "confidence_communication": confidence_score,
        "completeness": scorecard["completeness"],
        "overall_answer_score": overall_score,
        "strengths": strengths[:3],
        "weaknesses": weaknesses[:3],
        "improvement_suggestion": suggestions[0] if suggestions else "Keep using concrete examples and outcomes.",
        "score_breakdown": scorecard,
        "answer_present": bool(answer_text),
    }


def evaluate_answer_llm(question: str, answer: str, *, allotted_seconds: int = 0, time_taken_seconds: int = 0):
    """LLM-based answer evaluation - uses AI for better assessment.
    
    Falls back to local scoring if LLM is unavailable.
    """
    try:
        from services.llm.client import _get_client, _llm_model
        
        prompt = f"""You are a technical interview evaluator. Evaluate this answer and provide scores.

Question: {question}

Answer: {answer}

Evaluate on a scale of 0-100 for each dimension:
1. relevance - How well the answer addresses the question
2. completeness - Depth and substance of the answer
3. clarity - How clear and well-structured the answer is
4. technical_accuracy - Correctness of technical content

Also provide:
- One strength (1 sentence)
- One weakness (1 sentence)
- One improvement suggestion (1 sentence)

Return JSON:
{{"relevance": score, "completeness": score, "clarity": score, "technical_accuracy": score, "strength": "...", "weakness": "...", "suggestion": "..."}}"""
        
        client = _get_client()
        if client:
            response = client.create(
                model=_llm_model(),
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=500,
            )
            import json
            content = response.choices[0].message.content
            result = json.loads(content)
            
            overall_score = (result.get("relevance", 50) + result.get("completeness", 50) + 
                            result.get("clarity", 50) + result.get("technical_accuracy", 50)) / 4
            
            return {
                "relevance": result.get("relevance", 50),
                "technical_correctness": result.get("technical_accuracy", 50),
                "clarity": result.get("clarity", 50),
                "confidence_communication": result.get("clarity", 50),
                "completeness": result.get("completeness", 50),
                "overall_answer_score": overall_score,
                "strengths": [result.get("strength", "Answer provided.")],
                "weaknesses": [result.get("weakness", "Could be more detailed.")],
                "improvement_suggestion": result.get("suggestion", "Add more concrete examples."),
                "score_breakdown": result,
                "answer_present": bool(answer.strip()),
                "llm_evaluated": True,
            }
    except Exception:
        pass
    
    return evaluate_answer(question, answer, allotted_seconds=allotted_seconds, time_taken_seconds=time_taken_seconds)


def build_application_score(*, resume_score=0.0, skills_match_score=0.0, interview_score=0.0, communication_score=0.0, weights_json=None, missing_critical_skills: list[str] | None = None, skill_weights: dict[str, int] | None = None):
    """Build final weighted ATS score for one application.

    Args:
        resume_score: Resume screening score (0-100)
        skills_match_score: Skills match percentage (0-100)
        interview_score: Interview performance score (0-100)
        communication_score: Communication/confidence score (0-100)
        weights_json: Optional custom weights dict e.g., {"resume": 0.40, "skills": 0.20, "interview": 0.30, "communication": 0.10}
                       If not provided, uses DEFAULT_WEIGHTS
        missing_critical_skills: List of skills missing from resume that have weight >= 8
        skill_weights: Dict of skill weights to calculate penalty
    
    Missing Critical Skill Penalty:
        - Each missing skill with weight >= 8 reduces final score by up to 10 points
        - Penalty = sum of (weight / 20) * 10 for each missing critical skill
        - Max penalty: 25 points (if multiple critical skills missing)
    """
    weights = weights_json or DEFAULT_WEIGHTS

    resume_w = float(weights.get("resume", DEFAULT_WEIGHTS["resume"]))
    skills_w = float(weights.get("skills", DEFAULT_WEIGHTS["skills"]))
    interview_w = float(weights.get("interview", DEFAULT_WEIGHTS["interview"]))
    comm_w = float(weights.get("communication", DEFAULT_WEIGHTS["communication"]))

    total_weight = resume_w + skills_w + interview_w + comm_w
    if total_weight != 1.0:
        total_weight = 1.0

    raw_score = (
        (float(resume_score or 0.0) * resume_w)
        + (float(skills_match_score or 0.0) * skills_w)
        + (float(interview_score or 0.0) * interview_w)
        + (float(communication_score or 0.0) * comm_w)
    )

    missing_penalty = 0.0
    penalty_breakdown = []
    if missing_critical_skills and skill_weights:
        for skill in missing_critical_skills:
            weight = skill_weights.get(skill, 0)
            if weight >= 8:
                skill_penalty = min(10.0, (weight / 20.0) * 10.0)
                missing_penalty += skill_penalty
                penalty_breakdown.append({"skill": skill, "weight": weight, "penalty": round(skill_penalty, 2)})

    missing_penalty = min(25.0, missing_penalty)
    final_score = _clamp_score(raw_score - missing_penalty)

    return {
        "resume_jd_match_score": _clamp_score(resume_score),
        "skills_match_score": _clamp_score(skills_match_score),
        "interview_performance_score": _clamp_score(interview_score),
        "communication_behavior_score": _clamp_score(communication_score),
        "missing_skill_penalty": round(missing_penalty, 2),
        "penalty_breakdown": penalty_breakdown,
        "final_weighted_score": final_score,
        "recommendation": recommendation_for_score(final_score),
        "weights_used": weights,
    }


def summarize_interview(answer_evaluations: list[dict[str, object]]):
    if not answer_evaluations:
        return {
            "overall_interview_score": 0.0,
            "communication_score": 0.0,
            "strengths_summary": [],
            "weaknesses_summary": ["No valid answers were captured."],
            "hiring_recommendation": "Reject",
        }

    interview_score = mean(float(item.get("overall_answer_score") or 0.0) for item in answer_evaluations)
    communication_score = mean(float(item.get("confidence_communication") or 0.0) for item in answer_evaluations)
    strengths = []
    weaknesses = []
    for item in answer_evaluations:
        strengths.extend(item.get("strengths") or [])
        weaknesses.extend(item.get("weaknesses") or [])

    return {
        "overall_interview_score": _clamp_score(interview_score),
        "communication_score": _clamp_score(communication_score),
        "strengths_summary": list(dict.fromkeys(strengths))[:5],
        "weaknesses_summary": list(dict.fromkeys(weaknesses))[:5],
        "hiring_recommendation": recommendation_for_score(interview_score),
    }