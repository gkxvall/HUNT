from __future__ import annotations

import unittest

from hunt.config import (
    ApplicantIdentity,
    ApplicantInternshipPreferences,
    ApplicantProfile,
    EmailStyleConfig,
)
from hunt.email_writer import build_email_prompt, parse_generated_email
from hunt.utils import HuntError


class TestEmailWriter(unittest.TestCase):
    def test_parse_json_email(self) -> None:
        generated = parse_generated_email(
            '{"subject": "Internship Application - AI", "body": "Dear Team,\\nI would like to apply."}'
        )

        self.assertEqual(generated.subject, "Internship Application - AI")
        self.assertIn("Dear Team", generated.body)

    def test_parse_json_email_with_extra_text(self) -> None:
        generated = parse_generated_email(
            'Here is the email:\n{"subject": "Internship", "body": "Hello"}\nThanks'
        )

        self.assertEqual(generated.subject, "Internship")
        self.assertEqual(generated.body, "Hello")

    def test_fallback_parse_subject_and_body(self) -> None:
        generated = parse_generated_email(
            "Subject: Internship Application - AI\n\n"
            "Email:\n"
            "Dear Team,\n\nI would like to apply.\n\nBest,\nCandidate"
        )

        self.assertEqual(generated.subject, "Internship Application - AI")
        self.assertIn("Dear Team", generated.body)

    def test_parse_invalid_format_raises(self) -> None:
        with self.assertRaises(HuntError) as context:
            parse_generated_email("Hello there")

        self.assertIn("Raw model output", str(context.exception))

    def test_prompt_instructs_env_stable_info_to_override_cv(self) -> None:
        prompt = build_email_prompt(
            company_summary="Company builds AI tools.",
            candidate_summary="CV says the candidate is named Old Name.",
            recipient_email="careers@example.com",
            applicant_profile=ApplicantProfile(
                identity=ApplicantIdentity(full_name="Vall"),
            ),
            internship_preferences=ApplicantInternshipPreferences(),
            email_style_config=EmailStyleConfig(),
        )

        self.assertIn('"full_name": "Vall"', prompt)
        self.assertIn("prefer the applicant profile fields over the CV summary", prompt)
        self.assertIn("Old Name", prompt)


if __name__ == "__main__":
    unittest.main()
