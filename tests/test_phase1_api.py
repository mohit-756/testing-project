import os
import tempfile
import unittest
from pathlib import Path
import zipfile
from unittest.mock import patch

from fastapi.testclient import TestClient

TEST_DB_PATH = Path("test_phase1_api.db")
if TEST_DB_PATH.exists():
    TEST_DB_PATH.unlink()

os.environ["DATABASE_URL"] = "sqlite:///./test_phase1_api.db"

from database import engine  # noqa: E402
from main import app  # noqa: E402
from models import Base  # noqa: E402


class Phase1ApiTests(unittest.TestCase):
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

    def signup(self, payload):
        response = self.client.post("/api/auth/signup", json=payload)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def login(self, email, password):
        response = self.client.post("/api/auth/login", json={"email": email, "password": password})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def logout(self):
        response = self.client.post("/api/auth/logout")
        self.assertEqual(response.status_code, 200, response.text)

    def test_resume_scoring_and_interview_review_payload(self):
        self.signup(
            {
                "role": "hr",
                "name": "Acme Hiring",
                "email": "hr@example.com",
                "password": "strongpass",
            }
        )
        self.login("hr@example.com", "strongpass")

        jd_response = self.client.post(
            "/api/hr/upload-jd",
            files={"jd_file": ("backend.txt", b"Python React SQL backend role", "text/plain")},
            data={
                "jd_title": "Backend Engineer",
                "education_requirement": "master",
                "experience_requirement": "3",
            },
        )
        self.assertEqual(jd_response.status_code, 200, jd_response.text)

        confirm_response = self.client.post(
            "/api/hr/confirm-jd",
            json={"skill_scores": {"python": 5, "react": 3, "sql": 2}},
        )
        self.assertEqual(confirm_response.status_code, 200, confirm_response.text)
        job_id = confirm_response.json()["job_id"]
        self.logout()

        self.signup(
            {
                "role": "candidate",
                "name": "Jane Candidate",
                "email": "candidate@example.com",
                "password": "strongpass",
                "gender": "Female",
            }
        )
        self.login("candidate@example.com", "strongpass")

        resume_response = self.client.post(
            "/api/candidate/upload-resume",
            files={
                "resume": (
                    "resume.txt",
                    (
                        b"Skills: Python React SQL. Experience: 4 years building APIs and dashboards. "
                        b"Projects: built monitoring and deployed services that improved reliability by 30 percent. "
                        b"Education: Bachelor of Technology."
                    ),
                    "text/plain",
                )
            },
            data={"job_id": str(job_id)},
        )
        self.assertEqual(resume_response.status_code, 200, resume_response.text)
        resume_payload = resume_response.json()
        self.assertTrue(resume_payload["candidate"]["candidate_uid"].startswith("CAND-"))
        explanation = resume_payload["result"]["explanation"]
        self.assertEqual(explanation["score_version"], "v2")
        self.assertIn("screening_band", explanation)
        self.assertIn("weighted_skill_score", explanation)
        self.assertIn("resume_advice", resume_payload)
        self.assertTrue(resume_payload["resume_advice"]["rewrite_tips"])

        result_id = resume_payload["result"]["id"]
        resume_score = float(resume_payload["result"]["score"])
        self.assertTrue(resume_payload["result"]["shortlisted"])

        practice_response = self.client.get("/api/candidate/practice-kit")
        self.assertEqual(practice_response.status_code, 200, practice_response.text)
        practice_payload = practice_response.json()
        self.assertTrue(practice_payload["practice"]["questions"])
        self.assertIn("resume_advice", practice_payload)

        schedule_response = self.client.post(
            "/api/candidate/select-interview-date",
            json={"result_id": result_id, "interview_date": "2026-03-14T10:30"},
        )
        self.assertEqual(schedule_response.status_code, 200, schedule_response.text)

        start_response = self.client.post(
            "/api/interview/start",
            json={"result_id": result_id, "consent_given": True},
        )
        self.assertEqual(start_response.status_code, 200, start_response.text)
        start_payload = start_response.json()
        self.assertTrue(start_payload["ok"])
        session_id = start_payload["session_id"]
        question_id = start_payload["current_question"]["id"]

        answer_response = self.client.post(
            "/api/interview/answer",
            json={
                "session_id": session_id,
                "question_id": question_id,
                "answer_text": (
                    "I built a Python API, added monitoring, and reduced failures by 20 percent "
                    "after improving retries and deployment checks."
                ),
                "time_taken_sec": 45,
                "skipped": False,
            },
        )
        self.assertEqual(answer_response.status_code, 200, answer_response.text)
        self.logout()

        self.login("hr@example.com", "strongpass")
        interview_score_response = self.client.post(
            "/api/hr/interview-score",
            json={"result_id": result_id, "technical_score": 88},
        )
        self.assertEqual(interview_score_response.status_code, 200, interview_score_response.text)
        score_payload = interview_score_response.json()
        self.assertAlmostEqual(score_payload["resume_score_used"], resume_score, places=2)
        self.assertIn("final_score", score_payload)

        dashboard_response = self.client.get("/api/hr/dashboard", params={"job_id": job_id})
        self.assertEqual(dashboard_response.status_code, 200, dashboard_response.text)
        dashboard_payload = dashboard_response.json()
        self.assertIn("analytics", dashboard_payload)
        self.assertIn("pipeline", dashboard_payload["analytics"])

        detail_response = self.client.get(f"/api/hr/interviews/{session_id}")
        self.assertEqual(detail_response.status_code, 200, detail_response.text)
        detail_payload = detail_response.json()
        self.assertTrue(detail_payload["questions"])
        first_question = detail_payload["questions"][0]
        self.assertIn("ai_answer_score", first_question)
        self.assertIn("score_breakdown", first_question)
        self.assertIn("relevance", first_question["score_breakdown"])

    def test_hr_candidate_search_and_delete(self):
        self.signup(
            {
                "role": "hr",
                "name": "Acme Hiring",
                "email": "hr2@example.com",
                "password": "strongpass",
            }
        )
        self.login("hr2@example.com", "strongpass")

        jd_response = self.client.post(
            "/api/hr/upload-jd",
            files={"jd_file": ("backend.txt", b"Python backend role", "text/plain")},
            data={
                "jd_title": "Backend Engineer",
                "education_requirement": "bachelor",
                "experience_requirement": "1",
            },
        )
        self.assertEqual(jd_response.status_code, 200, jd_response.text)
        confirm_response = self.client.post(
            "/api/hr/confirm-jd",
            json={"skill_scores": {"python": 5}},
        )
        self.assertEqual(confirm_response.status_code, 200, confirm_response.text)
        job_id = confirm_response.json()["job_id"]
        self.logout()

        self.signup(
            {
                "role": "candidate",
                "name": "Delete Me",
                "email": "delete@example.com",
                "password": "strongpass",
                "gender": "Female",
            }
        )
        self.login("delete@example.com", "strongpass")
        resume_response = self.client.post(
            "/api/candidate/upload-resume",
            files={
                "resume": (
                    "resume.txt",
                    b"Skills: Python. Experience: 2 years. Projects: built APIs. Education: Bachelor of Science.",
                    "text/plain",
                )
            },
            data={"job_id": str(job_id)},
        )
        self.assertEqual(resume_response.status_code, 200, resume_response.text)
        resume_payload = resume_response.json()
        candidate_uid = resume_payload["candidate"]["candidate_uid"]
        resume_path = Path(resume_payload["candidate"]["resume_path"])
        self.assertTrue(resume_path.exists())
        self.logout()

        self.login("hr2@example.com", "strongpass")
        list_response = self.client.get(
            "/api/hr/candidates",
            params={"q": candidate_uid, "status": "all", "sort": "newest", "page": 1},
        )
        self.assertEqual(list_response.status_code, 200, list_response.text)
        list_payload = list_response.json()
        self.assertEqual(list_payload["total_results"], 1)
        self.assertEqual(list_payload["candidates"][0]["candidate_uid"], candidate_uid)

        detail_response = self.client.get(f"/api/hr/candidates/{candidate_uid}")
        self.assertEqual(detail_response.status_code, 200, detail_response.text)
        detail_payload = detail_response.json()
        self.assertEqual(detail_payload["candidate"]["candidate_uid"], candidate_uid)
        self.assertIn("skill_gap", detail_payload)
        self.assertIn("resume_advice", detail_payload)

        backup_response = self.client.get("/api/hr/local-backup")
        self.assertEqual(backup_response.status_code, 200, backup_response.text)
        self.assertEqual(backup_response.headers["content-type"], "application/zip")
        with tempfile.TemporaryDirectory() as temp_dir:
            archive_path = Path(temp_dir) / "backup.zip"
            archive_path.write_bytes(backup_response.content)
            with zipfile.ZipFile(archive_path) as archive:
                self.assertIn("manifest.json", archive.namelist())

        delete_response = self.client.post(f"/api/hr/candidates/{candidate_uid}/delete")
        self.assertEqual(delete_response.status_code, 200, delete_response.text)
        self.assertFalse(resume_path.exists())

        after_delete_response = self.client.get(
            "/api/hr/candidates",
            params={"q": candidate_uid},
        )
        self.assertEqual(after_delete_response.status_code, 200, after_delete_response.text)
        self.assertEqual(after_delete_response.json()["total_results"], 0)


if __name__ == "__main__":
    unittest.main()
