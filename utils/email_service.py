"""Professional SMTP helper for Quadrant Technologies Recruitment correspondence."""

import os
import smtplib
from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText
from urllib.parse import quote_plus
from zoneinfo import ZoneInfo
from core.config import config

SMTP_SERVER = config.SMTP_SERVER
SMTP_PORT = config.SMTP_PORT

FRONTEND_URL = config.FRONTEND_URL.rstrip("/")

QUADRANT_SIGNATURE = """
Best Regards,
Recruitment Team | Quadrant Technologies

M : +91 9154077551
Email: recruit@quadranttechnologies.com
www.quadranttechnologies.com

Building No. 21, 4th floor, Raheja Mindspace IT Park, 
Hitech City, Madhapur, Hyderabad, Telangana 500081

An E-Verified Company
"""


def _interview_timezone() -> ZoneInfo:
    tz_name = str(getattr(config, "INTERVIEW_DEFAULT_TIMEZONE", "Asia/Kolkata") or "Asia/Kolkata")
    try:
        return ZoneInfo(tz_name)
    except Exception:
        return ZoneInfo("UTC")


def _coerce_interview_datetime(interview_datetime):
    if isinstance(interview_datetime, str):
        try:
            interview_datetime = datetime.fromisoformat(interview_datetime.replace("Z", "+00:00"))
        except Exception:
            return None
    if not interview_datetime:
        return None
    if interview_datetime.tzinfo is None:
        return interview_datetime.replace(tzinfo=timezone.utc)
    return interview_datetime.astimezone(timezone.utc)


def _format_interview_datetime(interview_datetime):
    dt_utc = _coerce_interview_datetime(interview_datetime)
    if not dt_utc:
        return "TBD"
    tz = _interview_timezone()
    tz_name = str(tz.key) if hasattr(tz, 'key') else str(tz)
    tz_abbrev = {"Asia/Kolkata": "IST", "UTC": "UTC", "America/New_York": "ET"}.get(tz_name, tz_name[-4:] if len(tz_name) > 4 else tz_name)
    return dt_utc.astimezone(tz).strftime(f"%A, %B %d, %Y at %I:%M %p") + f" ({tz_abbrev})"


def _build_google_calendar_link(interview_datetime, role_title, interview_link):
    """Build Google Calendar direct link."""
    dt_utc = _coerce_interview_datetime(interview_datetime)
    if not dt_utc:
        dt_utc = datetime.now(timezone.utc)

    end_dt_utc = dt_utc + timedelta(hours=1)
    start_time = dt_utc.strftime("%Y%m%dT%H%M%SZ")
    end_time = end_dt_utc.strftime("%Y%m%dT%H%M%SZ")

    title = quote_plus(f"Interview - {role_title}")
    details = quote_plus(f"Join Link: {interview_link}\n\nPlease join 5 minutes before the scheduled time.")

    return f"https://calendar.google.com/calendar/render?action=TEMPLATE&text={title}&dates={start_time}/{end_time}&details={details}"

def _send_generic_email(to_email, subject, body):
    """Internal helper to send a standardized email using Quadrant branding."""
    email_address = config.EMAIL_ADDRESS
    email_password = config.EMAIL_PASSWORD
    if not email_address or not email_password:
        raise ValueError("EMAIL_ADDRESS / EMAIL_PASSWORD is missing in environment.")

    # Combine body with the professional signature
    full_body = f"{body}\n\n{QUADRANT_SIGNATURE}"
    
    msg = MIMEText(full_body)
    msg["Subject"] = subject
    msg["From"] = f"Quadrant Technologies Recruitment <{email_address}>"
    msg["To"] = to_email

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(email_address, email_password)
            server.send_message(msg)
        return True
    except Exception as e:
        print(f"Failed to send email to {to_email}: {e}")
        return False

def send_interview_email(to_email, candidate_name, interview_date, interview_link):
    """Send formal interview invitation."""
    subject = f"Interview Invitation - {candidate_name} | Quadrant Technologies"
    body = f"""Hello {candidate_name},

Congratulations! Your application has been shortlisted for the next stage.

Your Interview Details:
Date & Time: {interview_date}
Interview Link: {interview_link}

Please ensure you join the link 5 minutes prior to your scheduled time with a stable internet connection.

We look forward to speaking with you!"""
    return _send_generic_email(to_email, subject, body)

def send_selection_email(to_email, candidate_name, role_title):
    """Send formal selection/offer notice."""
    subject = f"Congratulations! Selection Notice - {role_title} | Quadrant Technologies"
    body = f"""Hello {candidate_name},

It gives us great pleasure to inform you that you have been selected for the position of {role_title} at Quadrant Technologies.

Our team was highly impressed with your interview performance and technical capabilities. We will be reaching out shortly with further details regarding the next steps in the onboarding process.

Welcome to the team!"""
    return _send_generic_email(to_email, subject, body)

def send_rejection_email(to_email, candidate_name, role_title):
    """Send polite rejection notice."""
    subject = f"Application Update - {role_title} | Quadrant Technologies"
    body = f"""Hello {candidate_name},

Thank you for the time and effort you invested in interviewing with Quadrant Technologies for the {role_title} position.

While we were impressed with your background, we have decided to move forward with other candidates whose profiles more closely align with our current requirements at this time.

We appreciate your interest in our organization and wish you the very best in your future endeavors."""
    return _send_generic_email(to_email, subject, body)

def send_performance_feedback_email(to_email, candidate_name, role_title, strengths: list, areas_for_improvement: list, overall_score: float):
    """Send performance feedback summary to candidate after interview review."""
    subject = f"Your Interview Feedback - {role_title} | Quadrant Technologies"

    strengths_text = "\n".join(f"  ✓ {s}" for s in strengths) if strengths else "  ✓ Strong overall communication"
    improvements_text = "\n".join(f"  • {a}" for a in areas_for_improvement) if areas_for_improvement else "  • Continue building domain depth"

    body = f"""Hello {candidate_name},

Thank you for completing your interview for the {role_title} position at Quadrant Technologies.

We have reviewed your interview responses and wanted to share some constructive feedback to help you grow professionally.

— OVERALL INTERVIEW SCORE: {overall_score:.0f}/100 —

STRENGTHS OBSERVED:
{strengths_text}

AREAS FOR IMPROVEMENT:
{improvements_text}

We appreciate the time and effort you put into the interview process. Regardless of the outcome, we hope this feedback helps you in your ongoing career journey.

Thank you once again for your interest in Quadrant Technologies."""

    return _send_generic_email(to_email, subject, body)
def send_eligibility_email(to_email, candidate_name, role_title, is_eligible, feedback, dashboard_url):
    """Send eligibility status email with feedback."""
    if is_eligible:
        subject = f"Application Update - Shortlisted for {role_title} | Quadrant Technologies"
        body = f"""Hello {candidate_name},

Congratulations! Your application for the {role_title} position at Quadrant Technologies has been shortlisted.

Your application passed our initial screening criteria and we would like to proceed with the next step.

Next Steps:
- Open the interview calendar page
- Log in if prompted, then select a convenient date and time

Calendar Link: {dashboard_url}

We look forward to speaking with you!"""
    else:
        subject = f"Application Update - {role_title} | Quadrant Technologies"
        feedback_text = "\n".join([f"• {f}" for f in feedback]) if feedback else "• Your profile did not meet the current requirements"
        body = f"""Hello {candidate_name},

Thank you for your interest in the {role_title} position at Quadrant Technologies.

After reviewing your application, we regret to inform you that your profile does not match our current requirements at this time.

Feedback on your application:
{feedback_text}

We encourage you to:
- Update your skills and gain more experience in the relevant areas
- Apply for future positions that align with your expertise

We appreciate your interest in Quadrant Technologies and wish you the best in your career journey.

Dashboard Link: {dashboard_url}"""
    
    return _send_generic_email(to_email, subject, body)


def send_interview_confirmation_email(to_email, candidate_name, role_title, interview_datetime, interview_link, is_reschedule=False):
    """Send enhanced interview confirmation with Google Calendar link."""
    formatted_date = _format_interview_datetime(interview_datetime)
    
    google_calendar_link = _build_google_calendar_link(
        interview_datetime,
        role_title,
        interview_link
    )
    
    action = "Rescheduled" if is_reschedule else "Scheduled"
    subject = f"Interview {action} - {role_title} | Quadrant Technologies"
    
    body = f"""Hello {candidate_name},

Your interview for the {role_title} position has been {action.lower()}.

INTERVIEW DETAILS:
Date & Time: {formatted_date}
Role: {role_title}
Join Link: {interview_link}

ADD TO CALENDAR:
Google Calendar: {google_calendar_link}

IMPORTANT REMINDERS:
• Please join the interview 5 minutes before the scheduled time
• Ensure you have a stable internet connection
• Test your microphone and camera before the interview
• You will receive reminder emails 24 hours and 1 hour before the interview

We look forward to speaking with you!

Best Regards,
Recruitment Team | Quadrant Technologies"""
    
    return _send_generic_email(to_email, subject, body)


def send_reminder_24h_email(to_email, candidate_name, role_title, interview_datetime, interview_link):
    """Send 24-hour interview reminder."""
    formatted_date = _format_interview_datetime(interview_datetime)
    
    google_calendar_link = _build_google_calendar_link(
        interview_datetime,
        role_title,
        interview_link
    )
    
    subject = f"Reminder: Your Interview is Tomorrow - {role_title} | Quadrant Technologies"
    
    body = f"""Hello {candidate_name},

This is a friendly reminder that your interview for the {role_title} position is scheduled for tomorrow.

INTERVIEW DETAILS:
Date & Time: {formatted_date}
Role: {role_title}
Join Link: {interview_link}

Add to Calendar (if not done yet): {google_calendar_link}

PRE-INTERVIEW CHECKLIST:
• Test your microphone and camera
• Ensure stable internet connection
• Find a quiet, well-lit space
• Review the job requirements one more time

If you need to reschedule, please do so at least 2 hours before the interview time.

See you tomorrow!

Best Regards,
Recruitment Team | Quadrant Technologies"""
    
    return _send_generic_email(to_email, subject, body)


def send_reminder_1h_email(to_email, candidate_name, role_title, interview_datetime, interview_link):
    """Send 1-hour interview reminder."""
    formatted_date = _format_interview_datetime(interview_datetime)
    
    subject = f"Starting in 1 Hour - Interview for {role_title} | Quadrant Technologies"
    
    body = f"""Hello {candidate_name},

Your interview for the {role_title} position starts in 1 hour!

INTERVIEW DETAILS:
Date & Time: {formatted_date}
Join Link: {interview_link}

Please:
• Join the link now to ensure everything works
• Have your resume ready for reference
• Be in a quiet place

See you soon!

Best Regards,
Recruitment Team | Quadrant Technologies"""
    
    return _send_generic_email(to_email, subject, body)


def send_result_email(to_email, candidate_name, role_title, is_selected, score=None, feedback=None):
    """Send post-interview result email."""
    if is_selected:
        subject = f"Congratulations! You've Been Selected - {role_title} | Quadrant Technologies"
        body = f"""Hello {candidate_name},

Congratulations! We are pleased to inform you that you have been selected for the {role_title} position at Quadrant Technologies.

{"Your Interview Score: " + str(round(score)) + "/100" if score else ""}

Our HR team will reach out to you shortly with further details regarding the next steps, including offer letter and onboarding process.

We are excited to have you join our team!

Best Regards,
Recruitment Team | Quadrant Technologies"""
    else:
        subject = f"Application Update - {role_title} | Quadrant Technologies"
        feedback_text = ""
        if feedback:
            feedback_text = f"""

INTERVIEW FEEDBACK:
"""
            if isinstance(feedback, dict):
                if feedback.get('strengths'):
                    feedback_text += "\nStrengths:\n" + "\n".join([f"  ✓ {s}" for s in feedback['strengths']])
                if feedback.get('areas_for_improvement'):
                    feedback_text += "\n\nAreas for Improvement:\n" + "\n".join([f"  • {a}" for a in feedback['areas_for_improvement']])
            elif isinstance(feedback, list):
                feedback_text += "\n".join([f"  • {f}" for f in feedback])
        
        body = f"""Hello {candidate_name},

Thank you for taking the time to interview for the {role_title} position at Quadrant Technologies.

After careful consideration, we have decided to move forward with other candidates whose profiles more closely align with our current requirements.{feedback_text}

We appreciate your interest in Quadrant Technologies and wish you the very best in your career journey.

Please feel free to apply for future positions that match your expertise.

Best Regards,
Recruitment Team | Quadrant Technologies"""
    
    return _send_generic_email(to_email, subject, body)
