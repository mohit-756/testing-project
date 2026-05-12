"""FAQ API endpoints for user Q&A system."""
import logging
from datetime import datetime

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import FAQQuestion, Candidate, HR
from routes.dependencies import require_role, require_any_role, SessionUser

router = APIRouter(prefix="/faq", tags=["FAQ"])
logger = logging.getLogger(__name__)


def get_user_name(user):
    """Get the name of a user (Candidate or HR)."""
    if user is None:
        return "Unknown"
    if hasattr(user, "name") and user.name:
        return user.name
    if hasattr(user, "email"):
        return user.email.split("@")[0]
    return "Unknown"


def serialize_question(q, include_user=False):
    """Serialize a FAQQuestion to dict."""
    data = {
        "id": q.id,
        "question": q.question,
        "answer": q.answer,
        "status": q.status,
        "job_id": q.job_id,
        "user_type": q.user_type,
        "user_id": q.user_id,
        "created_at": q.created_at.isoformat() if q.created_at else None,
        "answered_at": q.answered_at.isoformat() if q.answered_at else None,
    }
    if include_user:
        data["user_name"] = get_user_name_by_type(q.user_type, q.user_id)
    return data


def get_user_name_by_type(user_type, user_id):
    """Get user name by type and ID."""
    if user_type == "candidate":
        user = db.query(Candidate).filter(Candidate.id == user_id).first()
    elif user_type == "hr":
        user = db.query(HR).filter(HR.id == user_id).first()
    else:
        return "Unknown"
    return get_user_name(user)


@router.get("/questions")
def get_faq_questions(
    status: str | None = None,
    current_user: SessionUser = Depends(require_any_role("candidate", "hr")),
    db: Session = Depends(get_db),
) -> dict:
    """Get FAQ questions.
    
    Both candidates and HR can access this endpoint.
    Candidates see only their own answered questions.
    HR sees all answered questions for public display.
    """
    if current_user.role == "hr":
        query = db.query(FAQQuestion)
        if status == "pending":
            query = query.filter(FAQQuestion.status == "pending")
        elif status == "answered":
            query = query.filter(FAQQuestion.status == "answered")
        else:
            query = query.filter(FAQQuestion.status == "answered")
    else:
        query = db.query(FAQQuestion).filter(
            FAQQuestion.user_type == "candidate",
            FAQQuestion.user_id == current_user.user_id,
        )

    questions = query.order_by(FAQQuestion.created_at.desc()).all()

    return {
        "ok": True,
        "questions": [serialize_question(q) for q in questions],
    }


@router.post("/questions")
def submit_faq_question(
    payload: dict = Body(...),
    current_user: SessionUser = Depends(require_any_role("candidate", "hr")),
    db: Session = Depends(get_db),
) -> dict:
    """Submit a new question for FAQ. Both candidates and HR can submit."""
    question = payload.get("question")
    job_id = payload.get("job_id")

    if not question or not question.strip():
        raise HTTPException(status_code=400, detail="Question is required")

    faq_question = FAQQuestion(
        question=question.strip(),
        job_id=job_id,
        user_type=current_user.role,
        user_id=current_user.user_id,
        status="pending",
    )
    db.add(faq_question)
    db.commit()
    db.refresh(faq_question)

    logger.info(f"User {current_user.user_id} ({current_user.role}) submitted FAQ question: {question}")

    return {
        "ok": True,
        "message": "Question submitted! You'll be notified when answered.",
        "question": serialize_question(faq_question),
    }


@router.get("/admin/questions")
def get_all_questions_for_admin(
    status: str | None = None,
    current_user: SessionUser = Depends(require_role("hr")),
    db: Session = Depends(get_db),
) -> dict:
    """Get all questions for HR admin (pending and answered)."""
    query = db.query(FAQQuestion)
    if status == "pending":
        query = query.filter(FAQQuestion.status == "pending")
    elif status == "answered":
        query = query.filter(FAQQuestion.status == "answered")
    elif status == "dismissed":
        query = query.filter(FAQQuestion.status == "dismissed")

    questions = query.order_by(FAQQuestion.created_at.desc()).all()

    return {
        "ok": True,
        "questions": [serialize_question(q, include_user=True) for q in questions],
    }


@router.put("/questions/{question_id}")
def update_faq_question(
    question_id: int,
    payload: dict = Body(...),
    current_user: SessionUser = Depends(require_role("hr")),
    db: Session = Depends(get_db),
) -> dict:
    """Update an existing FAQ question (answer or status). HR only."""
    faq_question = db.query(FAQQuestion).filter(FAQQuestion.id == question_id).first()
    if not faq_question:
        raise HTTPException(status_code=404, detail="Question not found")

    answer = payload.get("answer")
    status = payload.get("status")

    if answer is not None:
        faq_question.answer = answer
        if faq_question.status == "pending":
            faq_question.status = "answered"
            faq_question.answered_by = current_user.user_id
            faq_question.answered_at = datetime.utcnow()

    if status is not None and status in ["pending", "answered", "dismissed"]:
        faq_question.status = status

    db.commit()

    logger.info(f"HR {current_user.user_id} updated FAQ question {question_id}")

    return {
        "ok": True,
        "message": "Question updated!",
        "question": serialize_question(faq_question),
    }


@router.post("/questions/{question_id}/answer")
def answer_faq_question(
    question_id: int,
    payload: dict = Body(...),
    current_user: SessionUser = Depends(require_role("hr")),
    db: Session = Depends(get_db),
) -> dict:
    """Answer a pending FAQ question."""
    faq_question = db.query(FAQQuestion).filter(FAQQuestion.id == question_id).first()
    if not faq_question:
        raise HTTPException(status_code=404, detail="Question not found")

    if faq_question.status not in ["pending", "answered"]:
        raise HTTPException(status_code=400, detail="Question cannot be answered")

    answer = payload.get("answer")
    if not answer or not answer.strip():
        raise HTTPException(status_code=400, detail="Answer is required")

    faq_question.answer = answer.strip()
    faq_question.status = "answered"
    faq_question.answered_by = current_user.user_id
    faq_question.answered_at = datetime.utcnow()

    db.commit()

    logger.info(f"HR {current_user.user_id} answered FAQ question {question_id}")

    return {
        "ok": True,
        "message": "Answer saved!",
        "question": serialize_question(faq_question),
    }


@router.post("/questions/{question_id}/dismiss")
def dismiss_faq_question(
    question_id: int,
    current_user: SessionUser = Depends(require_role("hr")),
    db: Session = Depends(get_db),
) -> dict:
    """Dismiss a pending question without answering."""
    faq_question = db.query(FAQQuestion).filter(FAQQuestion.id == question_id).first()
    if not faq_question:
        raise HTTPException(status_code=404, detail="Question not found")

    faq_question.status = "dismissed"
    db.commit()

    logger.info(f"HR {current_user.user_id} dismissed FAQ question {question_id}")

    return {
        "ok": True,
        "message": "Question dismissed.",
    }