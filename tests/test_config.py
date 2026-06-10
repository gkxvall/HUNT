from __future__ import annotations

import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

from hunt.config import (
    ApplicantContact,
    ApplicantEducation,
    ApplicantIdentity,
    ApplicantInternshipPreferences,
    ApplicantProfile,
    ApplicantSkillsAndInterests,
    EmailStyleConfig,
    build_signature_context,
    clean_env,
    load_config,
    normalize_academic_level,
    normalize_choice,
    parse_bool,
    parse_csv,
)


class TestConfig(unittest.TestCase):
    def test_clean_env_removes_empty_and_placeholder_values(self) -> None:
        self.assertIsNone(clean_env(""))
        self.assertIsNone(clean_env("   "))
        self.assertIsNone(clean_env("N/A"))
        self.assertIsNone(clean_env("None"))
        self.assertIsNone(clean_env("your_email@gmail.com"))
        self.assertIsNone(clean_env("your_name"))
        self.assertEqual(clean_env(" Vall "), "Vall")

    def test_parse_bool(self) -> None:
        self.assertTrue(parse_bool("true", False))
        self.assertTrue(parse_bool("1", False))
        self.assertTrue(parse_bool("YES", False))
        self.assertFalse(parse_bool("false", True))
        self.assertFalse(parse_bool("0", True))
        self.assertFalse(parse_bool("off", True))
        self.assertTrue(parse_bool("unclear", True))

    def test_parse_csv(self) -> None:
        self.assertEqual(
            parse_csv(" Python, ML, Python, , FastAPI "),
            ["Python", "ML", "FastAPI"],
        )

    def test_normalize_choice_defaults_invalid_choices(self) -> None:
        self.assertEqual(normalize_choice("REMOTE", {"remote", "hybrid"}, "hybrid"), "remote")
        self.assertEqual(normalize_choice("office", {"remote", "hybrid"}, "hybrid"), "hybrid")

    def test_normalize_academic_level(self) -> None:
        self.assertEqual(normalize_academic_level("a"), "A")
        self.assertEqual(normalize_academic_level("B"), "B")
        self.assertEqual(normalize_academic_level(" c "), "C")
        self.assertEqual(normalize_academic_level("doctoral"), "B")

    def test_load_config_defaults_and_word_clamping(self) -> None:
        with patch("hunt.config.load_environment", return_value=None), patch.dict("os.environ", {}, clear=True):
            config = load_config()

        self.assertEqual(config.ollama_model, "qwen2.5:3b-instruct")
        self.assertEqual(config.email_style.language, "English")
        self.assertEqual(config.email_style.academic_level, "B")
        self.assertEqual(config.email_style.tone, "professional")
        self.assertEqual(config.email_style.length, "medium")
        self.assertEqual(config.email_style.max_words, 350)
        self.assertTrue(config.email_style.include_links)
        self.assertFalse(config.email_style.include_phone)
        self.assertFalse(config.email_style.include_location)
        self.assertEqual(config.email_style.signature_style, "compact")
        self.assertEqual(config.applicant_profile.to_prompt_dict(config.email_style), {})

        with patch("hunt.config.load_environment", return_value=None), patch.dict("os.environ", {"EMAIL_MAX_WORDS": "20"}, clear=True):
            self.assertEqual(load_config().email_style.max_words, 80)

        with patch("hunt.config.load_environment", return_value=None), patch.dict("os.environ", {"EMAIL_MAX_WORDS": "900"}, clear=True):
            self.assertEqual(load_config().email_style.max_words, 700)

    def test_env_loading_from_project_root_and_reload_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = Path(tmpdir) / ".env"
            env_path.write_text(
                "APPLICANT_FULL_NAME=First Name\nEMAIL_LANGUAGE=Turkish\n",
                encoding="utf-8",
            )
            with patch("hunt.config.find_dotenv", return_value=str(env_path)):
                first = load_config()
                self.assertEqual(first.applicant_profile.identity.full_name, "First Name")
                self.assertEqual(first.email_style.language, "Turkish")

                env_path.write_text(
                    "APPLICANT_FULL_NAME=Second Name\nEMAIL_LANGUAGE=French\n",
                    encoding="utf-8",
                )
                second = load_config()
                self.assertEqual(second.applicant_profile.identity.full_name, "Second Name")
                self.assertEqual(second.email_style.language, "French")

    def test_optional_fields_are_omitted_from_prompt_dicts(self) -> None:
        profile = ApplicantProfile(
            identity=ApplicantIdentity(full_name="Vall"),
            contact=ApplicantContact(phone=None),
        )
        style = EmailStyleConfig(include_links=True, include_phone=True)

        self.assertEqual(profile.to_prompt_dict(style), {"identity": {"full_name": "Vall"}})

    def test_disabled_phone_location_gpa_languages_are_omitted(self) -> None:
        profile = ApplicantProfile(
            identity=ApplicantIdentity(current_location="Istanbul, Turkey"),
            contact=ApplicantContact(phone="+90 555 000 0000"),
            education=ApplicantEducation(gpa="3.7", gpa_scale="4.0"),
            skills=ApplicantSkillsAndInterests(languages=["English", "Turkish"]),
        )
        style = EmailStyleConfig(
            include_phone=False,
            include_location=False,
            include_gpa=False,
            include_languages=False,
            signature_style="detailed",
        )

        prompt_dict = profile.to_prompt_dict(style)
        signature_dict = profile.to_signature_dict(style)
        self.assertNotIn("contact", prompt_dict)
        self.assertNotIn("gpa", prompt_dict.get("education", {}))
        self.assertNotIn("languages", prompt_dict.get("skills_and_interests", {}))
        self.assertNotIn("phone", signature_dict)
        self.assertNotIn("location", signature_dict)

    def test_enabled_phone_location_gpa_languages_are_included_when_provided(self) -> None:
        profile = ApplicantProfile(
            identity=ApplicantIdentity(current_location="Istanbul, Turkey"),
            contact=ApplicantContact(phone="+90 555 000 0000"),
            education=ApplicantEducation(gpa="3.7", gpa_scale="4.0"),
            skills=ApplicantSkillsAndInterests(languages=["English", "Turkish"]),
        )
        style = EmailStyleConfig(
            include_phone=True,
            include_location=True,
            include_gpa=True,
            include_languages=True,
            signature_style="detailed",
        )

        prompt_dict = profile.to_prompt_dict(style)
        signature_dict = profile.to_signature_dict(style)
        self.assertEqual(prompt_dict["contact"]["phone"], "+90 555 000 0000")
        self.assertEqual(prompt_dict["education"]["gpa"], "3.7")
        self.assertEqual(prompt_dict["skills_and_interests"]["languages"], ["English", "Turkish"])
        self.assertEqual(signature_dict["phone"], "+90 555 000 0000")
        self.assertEqual(signature_dict["location"], "Istanbul, Turkey")

    def test_internship_preferences_respect_enabled_fields(self) -> None:
        preferences = ApplicantInternshipPreferences(
            availability_start="2026-07-01",
            remote_reason="I can collaborate across time zones.",
        )

        disabled = preferences.to_prompt_dict(
            EmailStyleConfig(include_availability=False, include_remote_reason=False)
        )
        self.assertNotIn("availability_start", disabled)
        self.assertNotIn("remote_reason", disabled)

        enabled = preferences.to_prompt_dict(
            EmailStyleConfig(include_availability=True, include_remote_reason=True)
        )
        self.assertEqual(enabled["availability_start"], "2026-07-01")
        self.assertEqual(enabled["remote_reason"], "I can collaborate across time zones.")

    def test_signature_context_respects_style_and_enabled_fields(self) -> None:
        profile = ApplicantProfile(
            identity=ApplicantIdentity(full_name="Vall", current_location="Istanbul, Turkey"),
            contact=ApplicantContact(
                personal_email="vall@example.com",
                phone="+90 555 000 0000",
            ),
        )
        style = EmailStyleConfig(
            include_phone=False,
            include_location=True,
            signature_style="detailed",
        )

        self.assertEqual(
            build_signature_context(profile, style),
            {
                "style": "detailed",
                "name": "Vall",
                "email": "vall@example.com",
                "location": "Istanbul, Turkey",
            },
        )

    def test_env_example_contains_option_comments(self) -> None:
        text = Path(".env.example").read_text(encoding="utf-8")
        option_variables = [
            "INTERNSHIP_MODE",
            "INTERNSHIP_TYPE",
            "INTERNSHIP_RELOCATION_OPEN",
            "INTERNSHIP_UNIVERSITY_REQUIREMENT",
            "INTERNSHIP_INSURANCE_COVERED_BY_UNIVERSITY",
            "EMAIL_ACADEMIC_LEVEL",
            "EMAIL_TONE",
            "EMAIL_LENGTH",
            "EMAIL_FORMAT",
            "EMAIL_GREETING_STYLE",
            "EMAIL_SIGNATURE_STYLE",
            "EMAIL_INCLUDE_SUBJECT_KEYWORDS",
            "EMAIL_INCLUDE_CV_ATTACHMENT_NOTE",
            "EMAIL_INCLUDE_UNIVERSITY_REQUIREMENT",
            "EMAIL_INCLUDE_INSURANCE_NOTE",
            "EMAIL_INCLUDE_LINKS",
            "EMAIL_INCLUDE_PHONE",
            "EMAIL_INCLUDE_LOCATION",
            "EMAIL_INCLUDE_GPA",
            "EMAIL_INCLUDE_LANGUAGES",
            "EMAIL_INCLUDE_AVAILABILITY",
            "EMAIL_INCLUDE_REMOTE_REASON",
        ]
        for variable in option_variables:
            line = next(line for line in text.splitlines() if line.startswith(f"{variable}="))
            self.assertIn("# options:", line)

    def test_env_example_does_not_contain_real_personal_data(self) -> None:
        text = Path(".env.example").read_text(encoding="utf-8")
        for line in text.splitlines():
            if not line.startswith("APPLICANT_") or "=" not in line:
                continue
            value = line.split("=", 1)[1].split("#", 1)[0].strip()
            self.assertEqual(value, "")


if __name__ == "__main__":
    unittest.main()
