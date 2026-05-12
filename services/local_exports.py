"""Helpers for creating local backup archives."""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import zipfile

from sqlalchemy.orm import Session

from database import engine
from models import Candidate, InterviewSession, JobDescription, Result

EXPORT_ROOT = Path("uploads") / "exports"
EXPORT_ROOT.mkdir(parents=True, exist_ok=True)


def _database_path() -> Path | None:
    database = engine.url.database
    if not database:
        return None
    path = Path(database)
    if not path.is_absolute():
        path = Path.cwd() / path
    return path.resolve()


def create_local_backup_archive(db: Session) -> Path:
    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
    archive_path = EXPORT_ROOT / f"interview_bot_local_backup_{timestamp}.zip"
    uploads_root = (Path.cwd() / "uploads").resolve()
    database_path = _database_path()
    manifest = {
        "created_at": datetime.utcnow().isoformat(),
        "database": str(database_path) if database_path else None,
        "counts": {
            "candidates": db.query(Candidate).count(),
            "jobs": db.query(JobDescription).count(),
            "results": db.query(Result).count(),
            "interview_sessions": db.query(InterviewSession).count(),
        },
    }

    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest, indent=2))
        if database_path and database_path.is_file():
            archive.write(database_path, arcname=f"database/{database_path.name}")
        if uploads_root.exists():
            for file_path in uploads_root.rglob("*"):
                if not file_path.is_file():
                    continue
                if EXPORT_ROOT.resolve() in file_path.resolve().parents:
                    continue
                archive.write(file_path, arcname=f"uploads/{file_path.relative_to(uploads_root).as_posix()}")

    return archive_path
