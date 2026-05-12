import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

TEST_DB_PATH = Path("test_question_generation_api_smoke.db")
if TEST_DB_PATH.exists():
    TEST_DB_PATH.unlink()

os.environ["DATABASE_URL"] = "sqlite:///./test_question_generation_api_smoke.db"

from database import SessionLocal, engine  # noqa: E402
from main import app  # noqa: E402
from models import Base, Candidate, Result  # noqa: E402


def _bundle_with_categories(*, total: int, fallback_used: bool, topped_up: bool) -> dict[str, object]:
    questions: list[dict[str, object]] = [
        {
            "text": "Please introduce yourself briefly and connect your background to this role.",
            "category": "intro",
            "type": "intro",
            "difficulty": "easy",
            "topic": "background",
            "metadata": {"category": "intro", "priority_source": "baseline"},
        },
        {
            "text": "In your most relevant project, what did you own and what measurable outcome did you drive?",
            "category": "project",
            "type": "project",
            "difficulty": "medium",
            "topic": "project",
            "metadata": {"category": "project", "priority_source": "recent_project"},
        },
        {
            "text": "Describe a production issue you debugged, how you found the root cause, and what changed after the fix.",
            "category": "deep_dive",
            "type": "project",
            "difficulty": "medium",
            "topic": "debugging",
            "metadata": {"category": "deep_dive", "priority_source": "jd_resume_overlap"},
        },
        {
            "text": "Describe a time requirements changed late and how you managed communication and delivery.",
            "category": "behavioral",
            "type": "behavioral",
            "difficulty": "easy",
            "topic": "collaboration",
            "metadata": {"category": "behavioral", "priority_source": "resume_strength"},
        },
    ]
    # Pad deterministically while retaining category diversity.
    idx = 0
    while len(questions) < total:
        source = questions[1 + (idx % 3)]
        questions.append(
            {
                **source,
                "text": f"{source['text']} (variant {idx + 1})",
            }
        )
        idx += 1
    return {
        "questions": questions,
        "meta": {
            "generation_mode": "fallback_dynamic_plan" if fallback_used else "llm_primary",
            "fallback_used": fallback_used,
            "llm_topped_up_with_fallback": topped_up,
        },
    }


def _coverage_flags(questions: list[dict[str, object]]) -> dict[str, bool]:
    categories = {
        str(item.get("category") or item.get("type") or "").strip().lower()
        for item in questions
        if isinstance(item, dict)
    }
    return {
        "has_intro": "intro" in categories,
        "has_project_like": bool(categories & {"project", "deep_dive", "architecture", "leadership"}),
        "has_behavioral": "behavioral" in categories,
    }


class QuestionGenerationApiSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        Base.metadata.drop_all(bind=engine)
        cls.client.close()
        engine.dispose()
        if TEST_DB_PATH.exists():
            TEST_DB_PATH.unlink()

    def setUp(self):
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        self.upload_dir_ctx = tempfile.TemporaryDirectory()
        self.upload_dir = Path(self.upload_dir_ctx.name)
        self.upload_patchers = [
            patch("routes.common.UPLOAD_DIR", self.upload_dir),
            patch("routes.hr.management.UPLOAD_DIR", self.upload_dir),
            patch("routes.candidate.workflow.UPLOAD_DIR", self.upload_dir),
        ]
        for upload_patcher in self.upload_patchers:
            upload_patcher.start()
        self.semantic_patcher = patch("ai_engine.phase1.scoring.calculate_semantic_score", return_value=0.25)
        self.semantic_patcher.start()

    def tearDown(self):
        self.semantic_patcher.stop()
        for upload_patcher in reversed(self.upload_patchers):
            upload_patcher.stop()
        self.upload_dir_ctx.cleanup()
        self.client.post("/api/auth/logout")

    def _signup(self, payload: dict[str, object]) -> dict[str, object]:
        response = self.client.post("/api/auth/signup", json=payload)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def _login(self, email: str, password: str) -> dict[str, object]:
        response = self.client.post("/api/auth/login", json={"email": email, "password": password})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def _logout(self) -> None:
        response = self.client.post("/api/auth/logout")
        self.assertEqual(response.status_code, 200, response.text)

    def _seed_hr_job_and_candidate(self) -> tuple[int, str]:
        self._signup(
            {
                "role": "hr",
                "name": "Hiring Team",
                "email": "smoke-hr@example.com",
                "password": "strongpass",
            }
        )
        self._login("smoke-hr@example.com", "strongpass")

        jd_response = self.client.post(
            "/api/hr/upload-jd",
            files={"jd_file": ("backend.txt", b"Python FastAPI SQL backend role", "text/plain")},
            data={
                "jd_title": "Backend Engineer",
                "education_requirement": "bachelor",
                "experience_requirement": "2",
            },
        )
        self.assertEqual(jd_response.status_code, 200, jd_response.text)

        confirm_response = self.client.post(
            "/api/hr/confirm-jd",
            json={"skill_scores": {"python": 5, "fastapi": 4, "sql": 3}},
        )
        self.assertEqual(confirm_response.status_code, 200, confirm_response.text)
        job_id = int(confirm_response.json()["job_id"])
        self._logout()

        self._signup(
            {
                "role": "candidate",
                "name": "Smoke Candidate",
                "email": "smoke-candidate@example.com",
                "password": "strongpass",
                "gender": "Female",
            }
        )
        self._login("smoke-candidate@example.com", "strongpass")
        return job_id, "smoke-candidate@example.com"

    def test_candidate_upload_generates_and_persists_question_bank(self):
        job_id, _ = self._seed_hr_job_and_candidate()
        mocked_bundle = _bundle_with_categories(total=8, fallback_used=False, topped_up=False)

        with patch("routes.candidate.workflow.build_question_bundle", return_value=mocked_bundle):
            resume_response = self.client.post(
                "/api/candidate/upload-resume",
                files={
                    "resume": (
                        "resume.txt",
                        (
                            b"Skills: Python FastAPI SQL. "
                            b"Projects: Payments API revamp reduced failures by 23 percent. "
                            b"Experience: Built backend services and debugged incidents."
                        ),
                        "text/plain",
                    )
                },
                data={"job_id": str(job_id)},
            )

        self.assertEqual(resume_response.status_code, 200, resume_response.text)
        payload = resume_response.json()
        self.assertGreaterEqual(int(payload.get("question_count") or 0), 6)

        result_id = int(payload["result"]["id"])
        with SessionLocal() as db:
            result = db.query(Result).filter(Result.id == result_id).first()
            self.assertIsNotNone(result)
            stored_questions = list(result.interview_questions or [])
            self.assertGreaterEqual(len(stored_questions), 6)

            coverage = _coverage_flags(stored_questions)
            self.assertTrue(coverage["has_intro"])
            self.assertTrue(coverage["has_project_like"])
            self.assertTrue(coverage["has_behavioral"])

            if any(isinstance(item, dict) and isinstance(item.get("metadata"), dict) for item in stored_questions):
                categories_from_metadata = {
                    str((item.get("metadata") or {}).get("category") or "").strip().lower()
                    for item in stored_questions
                    if isinstance(item, dict)
                }
                self.assertIn("intro", categories_from_metadata)
                self.assertIn("behavioral", categories_from_metadata)

    def test_interview_access_regenerates_stale_bank_and_uses_result_source_of_truth(self):
        job_id, _ = self._seed_hr_job_and_candidate()
        seed_bundle = _bundle_with_categories(total=8, fallback_used=False, topped_up=False)

        with patch("routes.candidate.workflow.build_question_bundle", return_value=seed_bundle):
            resume_response = self.client.post(
                "/api/candidate/upload-resume",
                files={
                    "resume": (
                        "resume.txt",
                        (
                            b"Skills: Python FastAPI SQL. "
                            b"Projects: Event API redesign improved reliability. "
                            b"Experience: Debugged production incidents and improved observability."
                        ),
                        "text/plain",
                    )
                },
                data={"job_id": str(job_id)},
            )
        self.assertEqual(resume_response.status_code, 200, resume_response.text)
        payload = resume_response.json()
        result_id = int(payload["result"]["id"])
        candidate_uid = str(payload["candidate"]["candidate_uid"])

        with SessionLocal() as db:
            result = db.query(Result).filter(Result.id == result_id).first()
            self.assertIsNotNone(result)
            # Force a stale/short legacy-like bank to trigger regeneration via runtime access.
            result.interview_questions = [
                {"text": "Think back to a recent challenge where your expertise in Python helped the team move forward."},
                {"text": "Think back to a recent challenge where your expertise in SQL helped the team move forward."},
            ]
            db.add(result)
            db.commit()

        regenerated_bundle = _bundle_with_categories(total=8, fallback_used=True, topped_up=True)
        with (
            patch("routes.interview.runtime.build_question_bundle", return_value=regenerated_bundle) as mocked_builder,
            self.assertLogs("routes.interview.runtime", level="INFO") as logs,
        ):
            access_response = self.client.get(f"/api/interview/{result_id}/access")

        self.assertEqual(access_response.status_code, 200, access_response.text)
        access_payload = access_response.json()
        self.assertTrue(access_payload["ok"])
        self.assertEqual(int(access_payload["result_id"]), result_id)
        self.assertGreaterEqual(int(access_payload["question_count"]), 6)
        mocked_builder.assert_called_once()

        log_blob = "\n".join(logs.output)
        self.assertIn("interview_question_bank_event", log_blob)
        self.assertIn('"fallback_used": true', log_blob)
        self.assertIn('"llm_topped_up_with_fallback": true', log_blob)

        with SessionLocal() as db:
            result = db.query(Result).filter(Result.id == result_id).first()
            self.assertIsNotNone(result)
            stored_questions = list(result.interview_questions or [])
            self.assertGreaterEqual(len(stored_questions), 6)
            coverage = _coverage_flags(stored_questions)
            self.assertTrue(coverage["has_intro"])
            self.assertTrue(coverage["has_project_like"])
            self.assertTrue(coverage["has_behavioral"])

            candidate = db.query(Candidate).filter(Candidate.id == result.candidate_id).first()
            self.assertIsNotNone(candidate)

        self._logout()
        self._login("smoke-hr@example.com", "strongpass")
        hr_detail_response = self.client.get(f"/api/hr/candidates/{candidate_uid}")
        self.assertEqual(hr_detail_response.status_code, 200, hr_detail_response.text)
        hr_payload = hr_detail_response.json()
        self.assertEqual(hr_payload["generated_questions_meta"]["source"], "result.interview_questions")
        self.assertEqual(int(hr_payload["generated_questions_meta"]["result_id"]), result_id)
        self.assertGreaterEqual(int(hr_payload["generated_questions_meta"]["total_questions"]), 6)
