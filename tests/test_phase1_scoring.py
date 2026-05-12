import unittest

from ai_engine.phase1.scoring import compute_answer_scorecard, compute_resume_scorecard


class ResumeScoringTests(unittest.TestCase):
    def test_weighted_skills_keep_strong_resume_competitive(self):
        scorecard = compute_resume_scorecard(
            resume_text=(
                "Skills: Python React SQL. Experience: 4 years building APIs. "
                "Projects: built dashboards and deployed production services. "
                "Education: Bachelor of Technology."
            ),
            jd_text="We need Python, React, and SQL for this backend role.",
            jd_skill_scores={"python": 5, "react": 3, "sql": 2},
            education_requirement="bachelor",
            experience_requirement=3,
            semantic_similarity=0.10,
        )

        self.assertGreaterEqual(scorecard["weighted_skill_score"], 90)
        self.assertGreater(scorecard["final_resume_score"], 70)
        self.assertEqual(scorecard["screening_band"], "strong_shortlist")

    def test_partial_penalties_do_not_zero_out_resume(self):
        scorecard = compute_resume_scorecard(
            resume_text=(
                "Skills: Python. Experience: 2 years in backend development. "
                "Projects: built APIs and fixed production issues. "
                "Education: Bachelor of Science."
            ),
            jd_text="Python engineer needed with 4 years of experience and a master's degree.",
            jd_skill_scores={"python": 5},
            education_requirement="master",
            experience_requirement=4,
            semantic_similarity=0.30,
        )

        self.assertEqual(scorecard["education_score"], 50.0)
        self.assertGreater(scorecard["experience_score"], 0.0)
        self.assertGreater(scorecard["final_resume_score"], 50.0)

    def test_short_resume_gets_low_quality_score(self):
        scorecard = compute_resume_scorecard(
            resume_text="Python developer",
            jd_text="Need Python developer",
            jd_skill_scores={"python": 5},
            education_requirement="",
            experience_requirement=0,
            semantic_similarity=0.50,
        )

        self.assertEqual(scorecard["resume_quality_score"], 0.0)
        self.assertIn("too short", scorecard["resume_quality_reason"].lower())


class AnswerScoringTests(unittest.TestCase):
    def test_structured_answer_outscores_keyword_stuffing(self):
        structured = compute_answer_scorecard(
            "How did you improve API reliability?",
            (
                "I designed retry logic, added monitoring, and reduced timeout errors by 35 percent. "
                "We deployed the fix in phases and measured the impact for two weeks."
            ),
            allotted_seconds=60,
            time_taken_seconds=45,
            jd_skills=("python", "monitoring"),
        )
        stuffed = compute_answer_scorecard(
            "How did you improve API reliability?",
            "api reliability api reliability api reliability python python python",
            allotted_seconds=60,
            time_taken_seconds=8,
            jd_skills=("python", "monitoring"),
        )

        self.assertGreater(structured["overall_score"], stuffed["overall_score"])
        self.assertGreater(structured["clarity"], stuffed["clarity"])

    def test_empty_answer_scores_zero(self):
        scorecard = compute_answer_scorecard(
            "Tell me about a project.",
            "",
            allotted_seconds=60,
            time_taken_seconds=0,
        )

        self.assertEqual(scorecard["overall_score"], 0.0)
        self.assertEqual(scorecard["time_fit"], 0.0)


if __name__ == "__main__":
    unittest.main()
