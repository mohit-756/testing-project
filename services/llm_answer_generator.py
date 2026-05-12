"""LLM answer generator - produces candidate-style first-person responses to interview questions."""
from __future__ import annotations

import logging

from services.llm.client import _get_client, _llm_model

logger = logging.getLogger(__name__)

_ANSWER_SYSTEM_PROMPT = (
    "You are a candidate in a technical interview. "
    "Read the interview question below and generate a concise, first-person answer "
    "that demonstrates practical knowledge and real-world experience. "
    "Base your answer on the candidate's resume background. "
    "Do NOT include meta-commentary. Start directly with the answer."
)


def generate_answer(question: str, resume_text: str, jd_text: str) -> str:
    """Generate a candidate-style answer to an interview question.

    Args:
        question: The interview question to answer.
        resume_text: The candidate's resume text for context.
        jd_text: The job description for context.

    Returns:
        A first-person candidate answer string.
    """
    user_prompt = (
        f"Question: {question}\n\n"
        f"Candidate Resume:\n{resume_text}\n\n"
        f"Job Description:\n{jd_text}\n\n"
        "Generate a concise, first-person answer as if you are this candidate."
    )

    try:
        client = _get_client()
        resp = client.create(
            messages=[
                {"role": "system", "content": _ANSWER_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
            max_tokens=500,
            model=_llm_model(),
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"generate_answer failed: {e}")
        return ""
