"""Background job for sending interview reminders."""

import logging
import secrets
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from database import get_db, engine
from models import Result, Candidate, JobDescription
from utils.email_service import send_reminder_24h_email, send_reminder_1h_email
from routes.common import interview_entry_url

logger = logging.getLogger(__name__)


def process_reminders():
    """Process and send interview reminders (24h and 1h before)."""
    db = Session(engine)
    
    try:
        now = datetime.utcnow()
        
        results = db.query(Result).filter(
            Result.interview_datetime.isnot(None),
            Result.shortlisted == True,
            Result.interview_link.isnot(None),
        ).all()
        
        sent_count_24h = 0
        sent_count_1h = 0
        
        for result in results:
            if not result.interview_datetime:
                continue

            if not (result.interview_token or "").strip():
                result.interview_token = secrets.token_urlsafe(24)

            if not (result.interview_link or "").strip():
                result.interview_link = interview_entry_url(result.id, result.interview_token)
            
            candidate = db.query(Candidate).filter(Candidate.id == result.candidate_id).first()
            job = db.query(JobDescription).filter(JobDescription.id == result.job_id).first()
            
            if not candidate or not job:
                continue
            
            time_diff = result.interview_datetime - now
            hours_until = time_diff.total_seconds() / 3600
            
            # Wider windows make reminders reliable even when cron drifts by a few minutes.
            if 23.0 <= hours_until <= 25.0 and not result.reminder_24h_sent:
                try:
                    send_reminder_24h_email(
                        to_email=candidate.email,
                        candidate_name=candidate.name or "Candidate",
                        role_title=job.title or "the position",
                        interview_datetime=result.interview_datetime,
                        interview_link=result.interview_link
                    )
                    result.reminder_24h_sent = True
                    sent_count_24h += 1
                    logger.info(f"Sent 24h reminder to {candidate.email} for interview at {result.interview_datetime}")
                except Exception as e:
                    logger.error(f"Failed to send 24h reminder to {candidate.email}: {e}")
            
            elif 0.5 <= hours_until <= 1.5 and not result.reminder_1h_sent:
                try:
                    send_reminder_1h_email(
                        to_email=candidate.email,
                        candidate_name=candidate.name or "Candidate",
                        role_title=job.title or "the position",
                        interview_datetime=result.interview_datetime,
                        interview_link=result.interview_link
                    )
                    result.reminder_1h_sent = True
                    sent_count_1h += 1
                    logger.info(f"Sent 1h reminder to {candidate.email} for interview at {result.interview_datetime}")
                except Exception as e:
                    logger.error(f"Failed to send 1h reminder to {candidate.email}: {e}")
        
        db.commit()
        logger.info(f"Reminder job completed: 24h={sent_count_24h}, 1h={sent_count_1h}")
        return {"sent_24h": sent_count_24h, "sent_1h": sent_count_1h}
    
    except Exception as e:
        logger.error(f"Reminder job failed: {e}")
        db.rollback()
        return {"error": str(e)}
    finally:
        db.close()


if __name__ == "__main__":
    result = process_reminders()
    print(f"Reminder job result: {result}")