from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from routes.interview.runtime import _is_stale_question_bank


def test_stale_bank_detects_legacy_repetition_and_missing_coverage():
    stale, reason = _is_stale_question_bank(
        [
            {"text": "Think back to a recent challenge where your expertise in Python helped the team move forward."},
            {"text": "Think back to a recent challenge where your expertise in SQL helped the team move forward."},
            {"text": "Tell me about your most relevant project and the tools you used X end to end."},
        ]
    )

    assert stale is True
    assert reason in {"legacy_pattern", "duplicate_prefix", "missing_debugging", "missing_design"}


def test_stale_bank_accepts_debugging_and_design_coverage():
    stale, reason = _is_stale_question_bank(
        [
            {"text": "Please introduce yourself briefly and connect your background to the role."},
            {"text": "Walk me through the frontend UI system and the project outcome you owned."},
            {"text": "Describe a UI or API integration bug you debugged, how you found the root cause, and what changed after the fix."},
            {"text": "If the frontend UI system had to scale, what architecture or observability trade-offs would you revisit first?"},
            {"text": "Describe a time requirements changed late and how you aligned stakeholders while shipping."},
        ]
    )

    assert stale is False
    assert reason == "ok"
