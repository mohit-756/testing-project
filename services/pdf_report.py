from __future__ import annotations
import logging
from datetime import datetime
from io import BytesIO
from typing import Any
from fpdf import FPDF
from sqlalchemy.orm import Session
from models import InterviewSession, Candidate, Result, InterviewQuestion, ProctorEvent

logger = logging.getLogger(__name__)

def sanitize_text(text: str) -> str:
    """Replace Unicode characters not supported by FPDF core fonts with ASCII equivalents."""
    if not isinstance(text, str):
        text = str(text)
    # Replace common Unicode characters with ASCII equivalents
    replacements = {
        '\u2014': '-',   # em dash
        '\u2013': '-',   # en dash
        '\u2018': "'",   # left single quote
        '\u2019': "'",   # right single quote
        '\u201c': '"',   # left double quote
        '\u201d': '"',   # right double quote
        '\u2026': '...', # ellipsis
        '\u00ae': '(R)', # registered sign
        '\u00a9': '(C)', # copyright sign
        '\u2122': '(TM)', # trademark sign
    }
    for unicode_char, ascii_char in replacements.items():
        text = text.replace(unicode_char, ascii_char)
    # Remove any remaining non-Latin-1 characters
    return text.encode('latin-1', errors='ignore').decode('latin-1')

def _upload_to_s3_via_lambda(file_bytes: bytes, key: str, content_type: str = "application/pdf") -> str:
    """Upload to S3 using Lambda-generated presigned URL."""
    try:
        import requests
        from core.config import config
        resp = requests.get(
            config.LAMBDA_S3_URL,
            params={"fileName": key.split("/")[-1], "fileType": content_type},
            timeout=30
        )
        resp.raise_for_status()
        data = resp.json()
        upload_url = data["uploadUrl"]
        file_url = data["fileUrl"]
        
        put_resp = requests.put(upload_url, data=file_bytes, headers={"Content-Type": content_type}, timeout=60)
        put_resp.raise_for_status()
        
        logger.info(f"PDF uploaded to S3 via Lambda: {key}")
        return file_url
    except Exception as e:
        logger.error(f"PDF S3 upload via Lambda failed for {key}: {e}")
        raise

class InterviewReportPDF(FPDF):
    def header(self):
        self.set_font("helvetica", "B", 15)
        self.cell(0, 10, "AI Interview Platform - Candidate Dossier", border=False, ln=True, align="C")
        self.set_font("helvetica", "I", 10)
        self.cell(0, 10, f"Generated on {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC", border=False, ln=True, align="R")
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font("helvetica", "I", 8)
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}}", align="C")

def generate_interview_pdf(session: InterviewSession, db: Session, return_s3_url: bool = False) -> BytesIO | tuple[BytesIO, str]:
    """Generate a professional PDF report for an interview session.
    
    Args:
        session: The interview session
        db: Database session
        return_s3_url: If True, also upload to S3 and return (BytesIO, s3_url)
    
    Returns:
        BytesIO PDF buffer, or tuple (BytesIO, s3_url) if return_s3_url=True
    """
    """Generate a professional PDF report for an interview session."""
    candidate = db.query(Candidate).filter(Candidate.id == session.candidate_id).first()
    result = db.query(Result).filter(Result.id == session.result_id).first()
    questions = db.query(InterviewQuestion).filter(InterviewQuestion.session_id == session.id).order_by(InterviewQuestion.id.asc()).all()
    proctor_events = db.query(ProctorEvent).filter(ProctorEvent.session_id == session.id).all()
    
    pdf = InterviewReportPDF()
    pdf.set_margins(left=10, top=10, right=10)
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.alias_nb_pages()
    pdf.add_page()
    
    # 1. Candidate Info
    pdf.set_font("helvetica", "B", 14)
    pdf.set_fill_color(240, 240, 240)
    pdf.cell(0, 10, "1. Candidate Information", ln=True, fill=True)
    pdf.set_font("helvetica", "", 11)
    pdf.ln(2)
    pdf.cell(50, 8, f"Name:", border=0)
    name = sanitize_text(candidate.name if candidate else 'N/A')
    pdf.cell(0, 8, f"{name}", border=0, ln=True)
    pdf.cell(50, 8, f"Email:", border=0)
    email = sanitize_text(candidate.email if candidate else 'N/A')
    pdf.cell(0, 8, f"{email}", border=0, ln=True)
    pdf.cell(50, 8, f"Status:", border=0)
    pdf.cell(0, 8, f"{session.status.upper()}", border=0, ln=True)
    pdf.cell(50, 8, f"Final Weighted Score:", border=0)
    pdf.set_font("helvetica", "B", 11)
    pdf.cell(0, 8, f"{result.final_score if result and result.final_score is not None else 'N/A'} / 100", border=0, ln=True)
    pdf.ln(5)

    # 2. Executive Summary
    pdf.set_font("helvetica", "B", 14)
    pdf.cell(0, 10, "2. Executive Summary", ln=True, fill=True)
    pdf.set_font("helvetica", "", 10)
    pdf.ln(2)
    
    eval_summary = session.evaluation_summary_json or {}
    pdf.set_x(pdf.l_margin)
    recommendation = sanitize_text(result.recommendation or 'N/A')
    pdf.multi_cell(0, 6, f"AI Recommendation: {recommendation}")
    pdf.ln(2)
    pdf.cell(50, 6, "Overall Interview Score:")
    pdf.cell(0, 6, f"{eval_summary.get('overall_interview_score', 'N/A')}", ln=True)
    pdf.cell(50, 6, "Communication Score:")
    pdf.cell(0, 6, f"{eval_summary.get('communication_score', 'N/A')}", ln=True)
    pdf.cell(50, 6, "Technical Depth:")
    pdf.cell(0, 6, f"{eval_summary.get('technical_depth_score', 'N/A')}", ln=True)
    pdf.ln(5)

    # 3. Interview Transcript
    pdf.set_font("helvetica", "B", 14)
    pdf.cell(0, 10, "3. Interview Transcript", ln=True, fill=True)
    pdf.ln(2)
    
    for i, q in enumerate(questions, 1):
        # Question Header
        pdf.set_font("helvetica", "B", 10)
        pdf.set_text_color(50, 50, 150)
        pdf.set_x(pdf.l_margin)
        question_text = sanitize_text(q.text)
        pdf.multi_cell(0, 6, f"Q{i} [{q.question_type.upper()}]: {question_text}")
        pdf.set_text_color(0, 0, 0)
        
        # Answer
        pdf.set_font("helvetica", "I", 10)
        ans_text = q.answer_text if q.answer_text else "(No answer provided or skipped)"
        if q.skipped:
            ans_text = "(Skipped)"
        # Truncate very long answers to prevent rendering issues
        if len(ans_text) > 500:
            ans_text = ans_text[:500] + "... (truncated)"
        ans_text = sanitize_text(ans_text)
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(0, 6, f"Candidate Answer: {ans_text}")
        
        # AI Feedback
        if q.llm_feedback:
            pdf.set_font("helvetica", "", 9)
            pdf.set_text_color(80, 80, 80)
            feedback_text = (q.llm_feedback[:500] + "...") if len(q.llm_feedback) > 500 else q.llm_feedback
            feedback_text = sanitize_text(feedback_text)
            pdf.set_x(pdf.l_margin)
            pdf.multi_cell(0, 5, f"AI Feedback: {feedback_text}")
            pdf.set_text_color(0, 0, 0)
            
        pdf.ln(4)
        if pdf.get_y() > 250:
            pdf.add_page()

    # 4. Proctoring & Compliance
    if pdf.get_y() > 200:
        pdf.add_page()
    pdf.set_font("helvetica", "B", 14)
    pdf.cell(0, 10, "4. Proctoring & Compliance", ln=True, fill=True)
    pdf.set_font("helvetica", "", 10)
    pdf.ln(2)
    
    suspicious_events = [e for e in proctor_events if e.event_type in {"no_face", "multi_face", "face_mismatch", "tab_switch", "paste_detected"}]
    pdf.cell(60, 6, f"Total Warnings Issued:")
    pdf.cell(0, 6, f"{session.warning_count}", ln=True)
    pdf.cell(60, 6, f"Suspicious Events Detected:")
    pdf.cell(0, 6, f"{len(suspicious_events)}", ln=True)
    
    if suspicious_events:
        pdf.ln(2)
        pdf.set_font("helvetica", "B", 9)
        pdf.cell(40, 6, "Timestamp", border=1)
        pdf.cell(60, 6, "Event Type", border=1)
        pdf.cell(0, 6, "Details", border=1, ln=True)
        pdf.set_font("helvetica", "", 8)
        for e in suspicious_events[:15]:  # Limit to 15 in PDF
            pdf.cell(40, 6, f"{e.created_at.strftime('%H:%M:%S')}", border=1)
            pdf.cell(60, 6, f"{e.event_type}", border=1)
            detail = (e.meta_json or {}).get("detail", "N/A")
            pdf.cell(0, 6, f"{str(detail)[:60]}", border=1, ln=True)
    
    # Save to buffer
    output = BytesIO()
    pdf_bytes = pdf.output()
    output.write(pdf_bytes)
    output.seek(0)
    
    if return_s3_url:
        try:
            from core.config import config
            candidate = db.query(Candidate).filter(Candidate.id == session.candidate_id).first()
            safe_name = (candidate.name or "candidate").replace(" ", "_")
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            s3_key = f"{config.S3_REPORT_PREFIX}/session_{session.id}/{safe_name}_{timestamp}.pdf"
            s3_url = _upload_to_s3_via_lambda(pdf_bytes, s3_key, "application/pdf")
            return output, s3_url
        except Exception as e:
            logger.warning(f"Failed to upload PDF to S3: {e}")
    
    return output
