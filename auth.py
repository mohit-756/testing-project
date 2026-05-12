"""Authentication helpers for password hashing."""

import os
import warnings

from dotenv import load_dotenv
from passlib.context import CryptContext
from passlib.exc import PasswordValueError, UnknownHashError

# ---------------------------
# Auth Config
# ---------------------------
from core.config import config

SECRET_KEY = config.SECRET_KEY

# Use bcrypt_sha256 to avoid bcrypt's 72-byte password limit while keeping
# compatibility with older bcrypt hashes if they already exist in DB.
pwd_context = CryptContext(schemes=["bcrypt_sha256", "bcrypt"], deprecated="auto")

# ---------------------------
# Password Helpers
# ---------------------------
def hash_password(password: str):
    """Hash a plain-text password before storing in DB."""
    return pwd_context.hash(password)

def verify_password(plain_password: str, stored_password: str | None) -> bool:
    """Validate login password against stored hash.

    Legacy fallback:
    If an existing row contains non-hash/plain-text password data, avoid a 500
    and allow equality match so login can continue and be rehashed.
    """
    if not stored_password:
        return False
    try:
        return pwd_context.verify(plain_password, stored_password)
    except (UnknownHashError, PasswordValueError, TypeError, ValueError):
        return plain_password == stored_password


def password_needs_upgrade(stored_password: str | None) -> bool:
    """Return True when password should be re-hashed with current policy."""
    if not stored_password:
        return True
    try:
        scheme = pwd_context.identify(stored_password)
        if not scheme:
            return True
        return bool(pwd_context.needs_update(stored_password))
    except (UnknownHashError, PasswordValueError, TypeError, ValueError):
        return True
