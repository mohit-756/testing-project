"""Health and authentication endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from collections import defaultdict, deque
import time
import secrets
import os
import shutil
import logging
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)

from auth import hash_password, password_needs_upgrade, verify_password
from core.config import config
from database import get_db
from models import Candidate, HR, PasswordResetToken, UserPreferences
from routes.common import ensure_candidate_profile, get_candidate_or_404, get_hr_or_404
from routes.dependencies import SessionUser, get_current_user
from routes.schemas import LoginBody, SignupBody
from services.rate_limit import limiter

router = APIRouter()

# ── Rate Limiting ─────────────────────────────────────────────────────────────
# FastAPI-Limiter for distributed rate limiting (requires Redis)
# In-memory fallback for local dev (from sessions.py original)
# Tracks failed attempts per IP address.
_rate_limit_store: dict[str, deque] = defaultdict(deque)
RATE_LIMIT_WINDOW = 300  # 5 minutes
RATE_LIMIT_MAX = 10       # max attempts per window

# ── Account Lockout ───────────────────────────────────────────────────────
# In-memory store for locked accounts (email -> unlock_time)
_locked_accounts: dict[str, datetime] = {}
# Track failed attempts per email
_failed_attempts: dict[str, int] = {}
LOCKOUT_DURATION = 30  # minutes
MAX_FAILED_ATTEMPTS = 5   # lock after this many failed attempts

def _check_rate_limit(client_ip: str) -> None:
    now = time.time()
    attempts = _rate_limit_store[client_ip]
    # Remove expired entries
    while attempts and attempts[0] < now - RATE_LIMIT_WINDOW:
        attempts.popleft()
    if len(attempts) >= RATE_LIMIT_MAX:
        raise HTTPException(
            status_code=429,
            detail=f"Too many login attempts. Please try again in {RATE_LIMIT_WINDOW // 60} minutes.",
        )
    attempts.append(now)

def _get_client_ip(request: Request) -> str:
    return request.headers.get("x-forwarded-for", request.client.host).split(",")[0].strip()


def _check_account_lockout(email: str) -> None:
    """Check if account is locked and raise HTTPException if so."""
    unlock_time = _locked_accounts.get(email)
    if unlock_time and unlock_time > datetime.utcnow():
        remaining = int((unlock_time - datetime.utcnow()).total_seconds() / 60) + 1
        raise HTTPException(
            status_code=423,
            detail=f"Account locked due to too many failed attempts. Try again in {remaining} minutes.",
        )
    elif unlock_time:
        del _locked_accounts[email]


def _record_failed_attempt(email: str) -> None:
    """Record failed login attempt and lock account if threshold reached."""
    global _failed_attempts
    count = _failed_attempts.get(email, 0) + 1
    _failed_attempts[email] = count
    if count >= MAX_FAILED_ATTEMPTS:
        unlock_time = datetime.utcnow() + timedelta(minutes=LOCKOUT_DURATION)
        _locked_accounts[email] = unlock_time
        logger.warning(f"Account locked: {email}")


def _clear_failed_attempts(email: str) -> None:
    """Clear failed attempts counter on successful login."""
    global _failed_attempts
    _failed_attempts.pop(email, None)


@router.get("/health")
def health() -> dict[str, object]:
    return {"ok": True, "status": "healthy"}


# LLM provider health check endpoint.
# Kept at /health/groq for backward compatibility with existing frontend calls.
@router.get("/health/groq")
@router.get("/health/llm")
def llm_health() -> dict[str, object]:
    """Check configured LLM provider reachability without failing the endpoint."""
    provider = config.LLM_PROVIDER

    if provider == "ollama":
        ollama_url = config.OLLAMA_CHAT_URL
        ollama_model = config.OLLAMA_MODEL
        try:
            response = requests.post(
                ollama_url,
                json={
                    "model": ollama_model,
                    "messages": [{"role": "user", "content": "ping"}],
                    "stream": False,
                    "options": {"num_predict": 2},
                },
                timeout=10,
            )
            response.raise_for_status()
            return {
                "ok": True,
                "provider": "ollama",
                "status": "reachable",
                "degraded": False,
                "model": ollama_model,
                "message": "Ollama is reachable and ready.",
            }
        except Exception as exc:
            return {
                "ok": True,
                "provider": "ollama",
                "status": "unreachable",
                "degraded": True,
                "model": ollama_model,
                "message": f"Ollama health check failed: {str(exc)[:200]}",
            }

    if provider == "groq":
        api_key = config.GROQ_API_KEY
        if not api_key:
            return {
                "ok": True,
                "provider": "groq",
                "status": "unconfigured",
                "degraded": True,
                "message": "GROQ_API_KEY is not set.",
            }
        try:
            from groq import Groq

            client = Groq(api_key=api_key)
            models = client.models.list()
            model_ids = [m.id for m in (models.data or [])]
            return {
                "ok": True,
                "provider": "groq",
                "status": "reachable",
                "degraded": False,
                "models_available": len(model_ids),
                "message": "Groq API is reachable and ready.",
            }
        except Exception as exc:
            return {
                "ok": True,
                "provider": "groq",
                "status": "unreachable",
                "degraded": True,
                "message": f"Groq health check failed: {str(exc)[:200]}",
            }

    return {
        "ok": True,
        "provider": provider or "unknown",
        "status": "unsupported",
        "degraded": True,
        "message": "Unsupported LLM_PROVIDER. Expected 'ollama' or 'groq'.",
    }
    
# Add these two routes to routes/auth/sessions.py

# ── PUT /api/auth/profile ────────────────────────────────────────────────────
# Allows a logged-in user to update their display name.

from pydantic import BaseModel as _BaseModel

class ProfileUpdateBody(_BaseModel):
    name: str
    linkedin_url: str | None = None
    github_url: str | None = None

@router.put("/auth/profile")
def update_profile(
    payload: ProfileUpdateBody,
    current_user: SessionUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"PUT /auth/profile user={current_user.user_id} role={current_user.role}")

    name = (payload.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name cannot be empty")

    if current_user.role == "candidate":
        user = db.query(Candidate).filter(Candidate.id == current_user.user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        user.name = name
        if payload.linkedin_url is not None:
            user.linkedin_url = payload.linkedin_url.strip() if payload.linkedin_url else None
        if payload.github_url is not None:
            user.github_url = payload.github_url.strip() if payload.github_url else None
    else:
        user = db.query(HR).filter(HR.id == current_user.user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        user.company_name = name

    db.commit()
    return {"ok": True, "name": name, "linkedin_url": payload.linkedin_url, "github_url": payload.github_url}


# ── POST /api/auth/change-password ──────────────────────────────────────────
# Allows a logged-in user to change their password after verifying current one.

class ChangePasswordBody(_BaseModel):
    current_password: str
    new_password: str

@router.post("/auth/change-password")
def change_password(
    payload: ChangePasswordBody,
    current_user: SessionUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"POST /auth/change-password user={current_user.user_id} role={current_user.role}")

    if len(payload.new_password) < 6:
        raise HTTPException(status_code=400, detail="New password must be at least 6 characters")

    if current_user.role == "candidate":
        user = db.query(Candidate).filter(Candidate.id == current_user.user_id).first()
    else:
        user = db.query(HR).filter(HR.id == current_user.user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not verify_password(payload.current_password, user.password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    user.password = hash_password(payload.new_password)
    db.commit()
    return {"ok": True, "message": "Password updated successfully"}



@router.post("/auth/signup")
def signup(payload: SignupBody, db: Session = Depends(get_db)) -> dict[str, object]:
    role = payload.role.strip().lower()
    if role not in {"candidate", "hr"}:
        raise HTTPException(status_code=400, detail="Role must be candidate or hr")

    existing = db.query(Candidate).filter(Candidate.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    existing_hr = db.query(HR).filter(HR.email == payload.email).first()
    if existing_hr:
        raise HTTPException(status_code=400, detail="Email already registered")

    if role == "candidate":
        user = Candidate(
            name=payload.name,
            email=payload.email,
            password=hash_password(payload.password),
            gender=payload.gender,
        )
        ensure_candidate_profile(user, db)
    else:
        user = HR(
            company_name=payload.name,
            email=payload.email,
            password=hash_password(payload.password),
        )

    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Email already registered")
    db.refresh(user)
    return {"ok": True, "id": user.id, "role": role}


@router.post("/auth/login", dependencies=[dep for dep in [limiter("10/minute")] if dep is not None])
def login(
    payload: LoginBody,
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    import uuid
    requested_role = (payload.role or "").strip().lower()
    if requested_role and requested_role not in {"candidate", "hr"}:
        raise HTTPException(status_code=400, detail="role must be candidate or hr")

    logger.info(f"Login attempt for: {payload.email}")
    client_ip = _get_client_ip(request)
    _check_rate_limit(client_ip)
    _check_account_lockout(payload.email)

    candidate = db.query(Candidate).filter(Candidate.email == payload.email).first()
    logger.info(f"[DEBUG] Candidate lookup for '{payload.email}': found={candidate is not None}")
    if candidate:
        logger.info(f"[DEBUG] Stored password hash (first 20 chars): '{candidate.password[:20] if candidate.password else 'None'}'")
        pw_check = verify_password(payload.password, candidate.password)
        logger.info(f"[DEBUG] Password verification result: {pw_check}")
    if candidate and verify_password(payload.password, candidate.password):
        if requested_role and requested_role != "candidate":
            raise HTTPException(status_code=403, detail="This email belongs to a candidate account. Switch to Candidate login.")
        if password_needs_upgrade(candidate.password):
            candidate.password = hash_password(payload.password)
            db.commit()
        # Regenerate session ID to prevent session fixation
        request.session.clear()
        request.session["user_id"] = candidate.id
        request.session["role"] = "candidate"
        request.session["session_id"] = str(uuid.uuid4())
        _clear_failed_attempts(payload.email)
        logger.info(f"Candidate login success: {payload.email}")
        return {"ok": True, "role": "candidate", "user_id": candidate.id}

    hr_user = db.query(HR).filter(HR.email == payload.email).first()
    if hr_user and verify_password(payload.password, hr_user.password):
        if requested_role and requested_role != "hr":
            raise HTTPException(status_code=403, detail="This email belongs to an HR account. Switch to HR login.")
        if password_needs_upgrade(hr_user.password):
            hr_user.password = hash_password(payload.password)
            db.commit()
        # Regenerate session ID to prevent session fixation
        request.session.clear()
        request.session["user_id"] = hr_user.id
        request.session["role"] = "hr"
        request.session["session_id"] = str(uuid.uuid4())
        _clear_failed_attempts(payload.email)
        logger.info(f"HR login success: {payload.email}")
        return {"ok": True, "role": "hr", "user_id": hr_user.id}

    # Record failed attempt
    _record_failed_attempt(payload.email)
    logger.warning(f"Login failed for: {payload.email} from {client_ip}")
    raise HTTPException(status_code=401, detail="Invalid credentials")


@router.post("/auth/logout")
def logout(request: Request) -> dict[str, object]:
    request.session.clear()
    return {"ok": True}


@router.get("/auth/me")
def me(
    request: Request,
    current_user: SessionUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"GET /auth/me user={current_user.user_id} role={current_user.role}")

    if current_user.role == "candidate":
        candidate = get_candidate_or_404(db, current_user.user_id)
        return {
            "ok": True,
            "user_id": candidate.id,
            "candidate_uid": candidate.candidate_uid,
            "role": "candidate",
            "name": candidate.name,
            "email": candidate.email,
            "linkedin_url": candidate.linkedin_url,
            "github_url": candidate.github_url,
        }
    hr_user = get_hr_or_404(db, current_user.user_id)
    return {
        "ok": True,
        "user_id": hr_user.id,
        "role": "hr",
        "name": hr_user.company_name,
        "email": hr_user.email,
    }


# ── POST /api/auth/forgot-password ──────────────────────────────────────────
class ForgotPasswordBody(_BaseModel):
    email: str

@router.post("/auth/forgot-password")
def forgot_password(payload: ForgotPasswordBody, db: Session = Depends(get_db)) -> dict:
    user = db.query(Candidate).filter(Candidate.email == payload.email).first()
    if not user:
        user = db.query(HR).filter(HR.email == payload.email).first()
    if not user:
        return {"ok": True, "message": "If an account exists with that email, a reset link has been sent."}

    db.query(PasswordResetToken).filter(
        PasswordResetToken.email == payload.email,
        PasswordResetToken.used == False
    ).update({"used": True})

    token = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(hours=1)
    reset_token = PasswordResetToken(email=payload.email, token=token, expires_at=expires_at)
    db.add(reset_token)
    db.commit()

    frontend_url = config.FRONTEND_URL.rstrip("/")
    reset_link = f"{frontend_url}/#/reset-password/{token}"

    email_addr = config.EMAIL_ADDRESS
    email_pass = config.EMAIL_PASSWORD
    if email_addr and email_pass:
        try:
            msg = MIMEText(f"Click this link to reset your password:\n{reset_link}\n\nThis link expires in 1 hour.")
            msg["Subject"] = "Password Reset — InterviewBot"
            msg["From"] = email_addr
            msg["To"] = payload.email
            with smtplib.SMTP("smtp.gmail.com", 587) as server:
                server.starttls()
                server.login(email_addr, email_pass)
                server.sendmail(email_addr, payload.email, msg.as_string())
        except Exception:
            pass

    return {"ok": True, "message": "If an account exists with that email, a reset link has been sent."}


# ── POST /api/auth/reset-password ───────────────────────────────────────────
class ResetPasswordBody(_BaseModel):
    token: str
    new_password: str

@router.post("/auth/reset-password")
def reset_password(payload: ResetPasswordBody, db: Session = Depends(get_db)) -> dict:
    reset_token = db.query(PasswordResetToken).filter(
        PasswordResetToken.token == payload.token,
        PasswordResetToken.used == False
    ).first()
    if not reset_token:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")
    if reset_token.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Reset token has expired")

    user = db.query(Candidate).filter(Candidate.email == reset_token.email).first()
    if not user:
        user = db.query(HR).filter(HR.email == reset_token.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if len(payload.new_password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

    user.password = hash_password(payload.new_password)
    reset_token.used = True
    db.commit()
    return {"ok": True, "message": "Password reset successfully"}


# ── GET/POST /api/auth/preferences ──────────────────────────────────────────
class PreferencesBody(_BaseModel):
    preferences: dict

@router.get("/auth/preferences")
def get_preferences(current_user: SessionUser = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    pref = db.query(UserPreferences).filter(
        UserPreferences.user_id == current_user.user_id,
        UserPreferences.role == current_user.role
    ).first()
    if not pref:
        return {"ok": True, "preferences": {}}
    return {"ok": True, "preferences": pref.preferences_json or {}}


@router.post("/auth/preferences")
def save_preferences(payload: PreferencesBody, current_user: SessionUser = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    pref = db.query(UserPreferences).filter(
        UserPreferences.user_id == current_user.user_id,
        UserPreferences.role == current_user.role
    ).first()
    if pref:
        pref.preferences_json = payload.preferences
        pref.updated_at = datetime.utcnow()
    else:
        pref = UserPreferences(
            user_id=current_user.user_id,
            role=current_user.role,
            preferences_json=payload.preferences
        )
        db.add(pref)
    db.commit()
    return {"ok": True, "message": "Preferences saved"}


# ── POST /api/auth/avatar ───────────────────────────────────────────────────
@router.post("/auth/avatar")
def upload_avatar(
    file: UploadFile = File(...),
    current_user: SessionUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else "jpg"
    if ext not in {"jpg", "jpeg", "png", "gif", "webp"}:
        raise HTTPException(status_code=400, detail="Invalid image format")

    file.file.seek(0, 2)
    file_size = file.file.tell()
    file.file.seek(0)
    max_size_bytes = config.MAX_UPLOAD_SIZE_MB * 1_000_000
    if file_size > max_size_bytes:
        raise HTTPException(status_code=400, detail=f"Avatar file exceeds {config.MAX_UPLOAD_SIZE_MB}MB limit")

    avatar_dir = os.path.join("uploads", "avatars")
    os.makedirs(avatar_dir, exist_ok=True)
    filename = f"{current_user.role}_{current_user.user_id}.{ext}"
    filepath = os.path.join(avatar_dir, filename)

    with open(filepath, "wb") as f:
        shutil.copyfileobj(file.file, f)

    avatar_path = f"/uploads/avatars/{filename}"
    if current_user.role == "candidate":
        user = db.query(Candidate).filter(Candidate.id == current_user.user_id).first()
    else:
        user = db.query(HR).filter(HR.id == current_user.user_id).first()

    if user:
        user.avatar_path = avatar_path
        db.commit()

    return {"ok": True, "avatar_url": avatar_path}
