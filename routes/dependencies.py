"""Reusable auth/session dependencies for role-protected API routes."""
from dataclasses import dataclass
from typing import Union
from fastapi import Depends, HTTPException, Request

@dataclass
class SessionUser:
    """Authenticated user details stored in session cookies."""

    user_id: int
    role: str


def get_current_user(request: Request) -> SessionUser:
    """Load logged-in user from session, enforce expiry, and reject anonymous requests."""

    # Session expiry enforcement (1 hour)
    from datetime import datetime, timedelta
    created_at = request.session.get("created_at")
    if created_at:
        try:
            created_dt = datetime.fromisoformat(created_at)
            if datetime.utcnow() - created_dt > timedelta(hours=1):
                raise HTTPException(status_code=401, detail="Session expired")
        except Exception:
            # If timestamp malformed, treat as expired
            raise HTTPException(status_code=401, detail="Session expired")

    user_id = request.session.get("user_id")
    role = request.session.get("role")
    if not user_id or not role:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return SessionUser(user_id=int(user_id), role=str(role))


def require_role(role: str):
    """Factory dependency to enforce role-based access on route handlers."""

    def _dependency(current_user: SessionUser = Depends(get_current_user)) -> SessionUser:
        if current_user.role != role:
            raise HTTPException(status_code=403, detail=f"{role} access required")
        return current_user

    return _dependency


def require_any_role(*roles: str):
    """Factory dependency to allow access to users with any of the specified roles."""

    def _dependency(current_user: SessionUser = Depends(get_current_user)) -> SessionUser:
        if current_user.role not in roles:
            allowed = ", ".join(roles)
            raise HTTPException(status_code=403, detail=f"Any of [{allowed}] access required")
        return current_user

    return _dependency
