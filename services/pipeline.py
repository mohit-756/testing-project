"""ATS application stage helpers shared across screening, interview, and HR review."""

from __future__ import annotations

from datetime import datetime

from models import APPLICATION_STAGES, ApplicationStageHistory, Result

STAGE_META = {
    "applied": {"key": "applied", "label": "Applied", "tone": "secondary"},
    "screening": {"key": "screening", "label": "Screening", "tone": "primary"},
    "shortlisted": {"key": "shortlisted", "label": "Shortlisted", "tone": "success"},
    "interview_scheduled": {"key": "interview_scheduled", "label": "Interview Scheduled", "tone": "warning"},
    "interview_completed": {"key": "interview_completed", "label": "Interview Completed", "tone": "dark"},
    "selected": {"key": "selected", "label": "Selected", "tone": "success"},
    "rejected": {"key": "rejected", "label": "Rejected", "tone": "danger"},
}


def normalize_stage(value: str | None) -> str:
    stage = str(value or "applied").strip().lower().replace(" ", "_")
    return stage if stage in APPLICATION_STAGES else "applied"


def stage_payload(stage: str | None) -> dict[str, str]:
    return STAGE_META[normalize_stage(stage)]


# 1) What this does: records ATS stage movement in one shared place.
# 2) Why needed: candidate detail pages and audits need visible stage history.
# 3) How it works: normalizes the stage, updates the result row, and appends history.
def record_stage_change(
    db,
    result: Result,
    *,
    stage: str,
    changed_by_role: str | None,
    changed_by_user_id: int | None,
    note: str | None = None,
):
    normalized = normalize_stage(stage)
    result.stage = normalized
    result.stage_updated_at = datetime.utcnow()
    history = ApplicationStageHistory(
        result_id=result.id,
        stage=normalized,
        note=(note or "").strip() or None,
        changed_by_role=changed_by_role,
        changed_by_user_id=changed_by_user_id,
    )
    db.add(history)
    return history
