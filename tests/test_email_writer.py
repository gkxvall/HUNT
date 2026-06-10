from __future__ import annotations

import unittest

from hunt.email_writer import parse_generated_email
from hunt.utils import HuntError


class TestEmailWriter(unittest.TestCase):
    def test_parse_subject_and_body(self) -> None:
        generated = parse_generated_email(
            "Subject: Internship Application - AI\n\n"
            "Email:\n"
            "Dear Team,\n\nI would like to apply.\n\nBest,\nCandidate"
        )

        self.assertEqual(generated.subject, "Internship Application - AI")
        self.assertIn("Dear Team", generated.body)

    def test_parse_invalid_format_raises(self) -> None:
        with self.assertRaises(HuntError):
            parse_generated_email("Hello there")


if __name__ == "__main__":
    unittest.main()
