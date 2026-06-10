from __future__ import annotations

import unittest
from unittest.mock import patch

from hunt.config import (
    ApplicantProfile,
    EmailStyleConfig,
    build_signature_context,
    load_config,
    normalize_academic_level,
    parse_bool,
)


class TestConfig(unittest.TestCase):
    def test_parse_bool(self) -> None:
        self.assertTrue(parse_bool("true", False))
        self.assertTrue(parse_bool("1", False))
        self.assertTrue(parse_bool("YES", False))
        self.assertFalse(parse_bool("false", True))
        self.assertFalse(parse_bool("0", True))
        self.assertFalse(parse_bool("off", True))
        self.assertTrue(parse_bool("unclear", True))

    def test_normalize_academic_level(self) -> None:
        self.assertEqual(normalize_academic_level("a"), "A")
        self.assertEqual(normalize_academic_level("B"), "B")
        self.assertEqual(normalize_academic_level(" c "), "C")
        self.assertEqual(normalize_academic_level("doctoral"), "B")

    def test_load_config_defaults(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            config = load_config()

        self.assertEqual(config.ollama_model, "llama3.1:8b")
        self.assertEqual(config.email_style.language, "English")
        self.assertEqual(config.email_style.academic_level, "B")
        self.assertEqual(config.email_style.tone, "professional")
        self.assertEqual(config.email_style.max_words, 180)
        self.assertTrue(config.email_style.include_links)
        self.assertFalse(config.email_style.include_phone)
        self.assertFalse(config.email_style.include_location)
        self.assertEqual(config.email_style.signature_style, "compact")
        self.assertEqual(config.applicant_profile.to_prompt_dict(config.email_style), {})

    def test_profile_prompt_dict_omits_empty_or_disabled_fields(self) -> None:
        profile = ApplicantProfile(
            full_name="Vall",
            phone="",
            github_url="https://github.com/gkxvall",
            linkedin_url="",
        )
        style = EmailStyleConfig(include_links=True, include_phone=True)

        self.assertEqual(
            profile.to_prompt_dict(style),
            {
                "full_name": "Vall",
                "github_url": "https://github.com/gkxvall",
            },
        )

    def test_signature_context_respects_style_and_enabled_fields(self) -> None:
        profile = ApplicantProfile(
            full_name="Vall",
            personal_email="vall@example.com",
            phone="+90 555 000 0000",
            location="Istanbul, Turkey",
            github_url="https://github.com/gkxvall",
        )
        style = EmailStyleConfig(
            include_links=True,
            include_phone=False,
            include_location=True,
            signature_style="detailed",
        )

        self.assertEqual(
            build_signature_context(profile, style),
            {
                "style": "detailed",
                "full_name": "Vall",
                "personal_email": "vall@example.com",
                "location": "Istanbul, Turkey",
                "links": {"github_url": "https://github.com/gkxvall"},
            },
        )


if __name__ == "__main__":
    unittest.main()
