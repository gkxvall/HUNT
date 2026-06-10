from __future__ import annotations

import unittest

from hunt.json_utils import (
    LLMJsonParseError,
    body_looks_invalid,
    clean_email_body,
    parse_email_output,
    parse_llm_json,
    sanitize_email_body,
    sanitize_llm_output,
)


class TestJsonUtils(unittest.TestCase):
    def test_pure_json_parses(self) -> None:
        self.assertEqual(parse_llm_json('{"subject": "Hi"}')["subject"], "Hi")

    def test_parse_email_output_extracts_body_from_json(self) -> None:
        parsed = parse_email_output('{"subject": "Internship", "body": "Dear Team"}')
        self.assertEqual(parsed["subject"], "Internship")
        self.assertEqual(parsed["body"], "Dear Team")

    def test_json_code_fence_parses(self) -> None:
        parsed = parse_llm_json('```json\n{"subject": "Hi"}\n```')
        self.assertEqual(parsed["subject"], "Hi")

    def test_text_before_and_after_json_parses(self) -> None:
        parsed = parse_llm_json('Here is JSON:\n{"subject": "Hi"}\nDone.')
        self.assertEqual(parsed["subject"], "Hi")

    def test_parse_email_output_unwraps_json_string_output(self) -> None:
        parsed = parse_email_output('"{\\"subject\\":\\"Internship\\",\\"body\\":\\"Dear Team\\"}"')
        self.assertEqual(parsed["subject"], "Internship")
        self.assertEqual(parsed["body"], "Dear Team")

    def test_parse_email_output_unwraps_nested_json_body(self) -> None:
        raw = (
            '{"subject": "Outer", "body": '
            '"{\\"subject\\":\\"Inner\\", \\"body\\":\\"Sayın Vispera Ekibi,\\"}"}'
        )
        parsed = parse_email_output(raw)
        self.assertEqual(parsed["subject"], "Outer")
        self.assertEqual(parsed["body"], "Sayın Vispera Ekibi,")

    def test_trailing_comma_is_repaired(self) -> None:
        parsed = parse_llm_json('{"subject": "Hi", "items": [1, 2,],}')
        self.assertEqual(parsed["items"], [1, 2])

    def test_python_dict_single_quotes_parses(self) -> None:
        parsed = parse_llm_json("{'subject': 'Hi', 'ok': True, 'missing': None}")
        self.assertEqual(parsed["subject"], "Hi")
        self.assertTrue(parsed["ok"])
        self.assertIsNone(parsed["missing"])

    def test_subject_email_fallback_parses(self) -> None:
        parsed = parse_email_output("Subject: Internship\n\nEmail:\nDear Team,\nHello.")
        self.assertEqual(parsed["subject"], "Internship")
        self.assertIn("Dear Team", parsed["body"])

    def test_turkish_labels_parse(self) -> None:
        parsed = parse_email_output("Konu: Staj Başvurusu\n\nE-posta:\nMerhaba,\nBaşvurmak isterim.")
        self.assertEqual(parsed["subject"], "Staj Başvurusu")
        self.assertIn("Merhaba", parsed["body"])

    def test_raw_email_body_uses_default_subject(self) -> None:
        parsed = parse_email_output("Dear Team,\nI would like to apply.\n\nBest regards,\nVall")
        self.assertEqual(parsed["subject"], "Internship Application")
        self.assertIn("I would like to apply", parsed["body"])

    def test_missing_required_keys_get_safe_defaults(self) -> None:
        parsed = parse_llm_json('{"body": "Hello"}', ["subject", "body"])
        self.assertEqual(parsed["subject"], "Internship Application")

    def test_empty_final_email_body_raises(self) -> None:
        with self.assertRaises(LLMJsonParseError) as context:
            parse_email_output('{"subject": "Internship Application"}')

        self.assertIn("Raw output preview", str(context.exception))
        self.assertIn("--debug-prompt", str(context.exception))

    def test_clean_email_body_removes_fences_and_duplicate_labels(self) -> None:
        body = clean_email_body("```text\nSubject: Internship\nEmail:\nDear Team,\n[Your Name]\n```")
        self.assertNotIn("```", body)
        self.assertNotIn("Subject:", body)
        self.assertNotIn("Email:", body)
        self.assertNotIn("[Your Name]", body)
        self.assertIn("Dear Team", body)

    def test_sanitize_llm_output_removes_control_tokens(self) -> None:
        cleaned = sanitize_llm_output("<|im_start|><|assistant|>Hello|im_start| im_start <|im_end|>")
        self.assertNotIn("im_start", cleaned)
        self.assertNotIn("<|assistant|>", cleaned)

    def test_sanitize_email_body_removes_labels_and_decodes_newlines(self) -> None:
        body = sanitize_email_body("Subject: X\\nEmail:\\nDear Team,\\nHello")
        self.assertIn("\n", body)
        self.assertNotIn("Subject:", body)
        self.assertNotIn("Email:", body)

    def test_body_looks_invalid_detects_raw_json_body(self) -> None:
        self.assertTrue(body_looks_invalid('{"subject":"X","body":"Y"}', "English"))

    def test_body_looks_invalid_detects_repeated_im_start_noise(self) -> None:
        self.assertTrue(body_looks_invalid("hello im_start im_start im_start", "English"))

    def test_body_looks_invalid_detects_chinese_junk_for_turkish(self) -> None:
        self.assertTrue(body_looks_invalid("以下是完整版本\nSayın ekip", "Turkish"))


if __name__ == "__main__":
    unittest.main()
