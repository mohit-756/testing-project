"""Database engine and session wiring for SQLAlchemy."""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

# ---------------------------
# SQLAlchemy Base + Config
# ---------------------------
from core.config import config

# ---------------------------
# SQLAlchemy Base + Config
# ---------------------------
# Base class used by all ORM models in models.py
Base = declarative_base()

DATABASE_URL = config.DATABASE_URL

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is not set. "
        "Provide it via environment variable (Render dashboard) or in .env for local dev. "
        "Example: postgresql://user:password@host:5432/dbname"
    )

# SQLAlchemy requires 'postgresql://' but many platforms (Render, Heroku) provide 'postgres://'
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Render PostgreSQL URLs need sslmode=require for secure connections.
# Only add sslmode for remote hosts — skip for localhost/local dev.
if DATABASE_URL.startswith("postgresql://") and "sslmode" not in DATABASE_URL:
    if "localhost" not in DATABASE_URL and "127.0.0.1" not in DATABASE_URL:
        separator = "&" if "?" in DATABASE_URL else "?"
        DATABASE_URL = f"{DATABASE_URL}{separator}sslmode=require"

# Engine handles low-level DB connections.
# For SQLite, check_same_thread=False is needed. For Postgres, it is not.
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args
)

# ---------------------------
# Session Dependency
# ---------------------------
# SessionLocal is injected in routes using Depends(get_db).
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
def get_db():
    """Provide one DB session per request and close safely."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
