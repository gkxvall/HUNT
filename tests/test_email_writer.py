from __future__ import annotations

import unittest

from hunt.config import (
    ApplicantEducation,
    ApplicantIdentity,
    ApplicantInternshipPreferences,
    ApplicantLinks,
    ApplicantProfile,
    ApplicantSkillsAndInterests,
    EmailStyleConfig,
)
from hunt.email_writer import (
    GeneratedEmail,
    build_email_prompt,
    merge_candidate_context,
    parse_generated_email,
    validate_generated_email,
)
from hunt.json_utils import LLMJsonParseError


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
        with self.assertRaises(LLMJsonParseError) as context:
            parse_generated_email("not-json")

        self.assertIn("Raw output preview", str(context.exception))

    def test_prompt_instructs_env_stable_info_to_override_cv(self) -> None:
        prompt = build_email_prompt(
            company_summary={"what_company_does": "Company builds AI tools."},
            candidate_summary={"full_name": "Old Name"},
            recipient_email="careers@example.com",
            applicant_profile=ApplicantProfile(
                identity=ApplicantIdentity(full_name="Vall"),
            ),
            internship_preferences=ApplicantInternshipPreferences(),
            email_style_config=EmailStyleConfig(),
        )

        self.assertIn('"full_name": "Vall"', prompt)
        self.assertIn("prefer them over extracted CV values", prompt)
        self.assertNotIn("Old Name", prompt)

    def test_prompt_contains_filled_applicant_variables(self) -> None:
        prompt = build_email_prompt(
            company_summary={"company_name": "Example"},
            candidate_summary={},
            recipient_email="careers@example.com",
            applicant_profile=ApplicantProfile(
                identity=ApplicantIdentity(full_name="Vall Test"),
                education=ApplicantEducation(
                    university="Ondokuz Mayıs University",
                    department="Computer Engineering",
                ),
                links=ApplicantLinks(github_url="https://github.com/gkxvall"),
            ),
            internship_preferences=ApplicantInternshipPreferences(mode="remote"),
            email_style_config=EmailStyleConfig(
                language="Turkish",
                academic_level="C",
                email_format="full",
                include_links=True,
            ),
        )

        self.assertIn("Vall Test", prompt)
        self.assertIn("Ondokuz Mayıs University", prompt)
        self.assertIn("Computer Engineering", prompt)
        self.assertIn("https://github.com/gkxvall", prompt)
        self.assertIn("Turkish", prompt)
        self.assertIn("academic level: C", prompt)
        self.assertIn("email format: full", prompt)

    def test_prompt_omits_empty_and_disabled_applicant_variables(self) -> None:
        prompt = build_email_prompt(
            company_summary={},
            candidate_summary={},
            recipient_email="careers@example.com",
            applicant_profile=ApplicantProfile(
                identity=ApplicantIdentity(current_location="Istanbul"),
                links=ApplicantLinks(github_url="https://github.com/gkxvall"),
            ),
            internship_preferences=ApplicantInternshipPreferences(),
            email_style_config=EmailStyleConfig(include_location=False, include_links=False),
        )

        self.assertNotIn('"current_location": "Istanbul"', prompt)
        self.assertNotIn("https://github.com/gkxvall", prompt)

    def test_merge_candidate_context_env_overrides_stable_cv_info(self) -> None:
        merged = merge_candidate_context(
            {
                "full_name": "Old Name",
                "university": "Old University",
                "technical_skills": ["Python"],
            },
            ApplicantProfile(
                identity=ApplicantIdentity(full_name="Vall"),
                education=ApplicantEducation(university="Ondokuz Mayıs University"),
            ),
            EmailStyleConfig(),
        )

        self.assertEqual(merged["full_name"], "Vall")
        self.assertEqual(merged["university"], "Ondokuz Mayıs University")
        self.assertEqual(merged["technical_skills"], ["Python"])

    def test_validation_warns_when_disabled_links_or_languages_appear(self) -> None:
        warnings = validate_generated_email(
            GeneratedEmail(
                subject="Internship Application",
                body="See https://github.com/gkxvall. I speak Turkish.",
            ),
            ApplicantProfile(
                links=ApplicantLinks(github_url="https://github.com/gkxvall"),
                skills=ApplicantSkillsAndInterests(languages=["Turkish"]),
            ),
            ApplicantInternshipPreferences(),
            EmailStyleConfig(include_links=False, include_languages=False),
        )

        self.assertTrue(any("Disabled link" in warning for warning in warnings))
        self.assertTrue(any("Disabled language" in warning for warning in warnings))


if __name__ == "__main__":
    unittest.main()
