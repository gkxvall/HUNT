from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rich.console import Console
from typer.testing import CliRunner

from hunt import cli
from hunt.config import AppConfig, EmailStyleConfig


class TestCliPreview(unittest.TestCase):
    def test_no_secrets_appear_in_preview(self) -> None:
        original_console = cli.console
        capture_console = Console(file=io.StringIO(), record=True, width=120)
        cli.console = capture_console
        try:
            cli._render_preview(
                website="https://example.com",
                recipient_email="careers@example.com",
                subject="Internship Application",
                body="Dear Team,\nHello.",
                config=AppConfig(
                    email_address="student@example.com",
                    email_app_password="super-secret-password",
                    email_style=EmailStyleConfig(),
                ),
            )
            output = capture_console.export_text()
        finally:
            cli.console = original_console

        self.assertNotIn("super-secret-password", output)
        self.assertNotIn("student@example.com", output)
        self.assertIn("s***t@example.com", output)

    def test_config_command_masks_secrets(self) -> None:
        runner = CliRunner()
        config = AppConfig(
            email_address="student@example.com",
            email_app_password="super-secret-password",
            email_style=EmailStyleConfig(),
        )
        with patch("hunt.cli.load_config", return_value=config):
            result = runner.invoke(cli.app, ["config"])

        self.assertEqual(result.exit_code, 0)
        self.assertNotIn("super-secret-password", result.output)
        self.assertNotIn("student@example.com", result.output)
        self.assertIn("s***t@example.com", result.output)

    def test_debug_prompt_writes_files_without_secrets(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("hunt.cli.DATA_DIR", Path(tmpdir)):
                prompt_path, snapshot_path = cli._write_debug_files(
                    prompt="Prompt without secrets",
                    snapshot={
                        "config": {
                            "sender_email_masked": "s***t@example.com",
                        }
                    },
                )

            prompt_text = prompt_path.read_text(encoding="utf-8")
            snapshot_text = snapshot_path.read_text(encoding="utf-8")
            snapshot = json.loads(snapshot_text)

        self.assertEqual(prompt_text, "Prompt without secrets")
        self.assertEqual(snapshot["config"]["sender_email_masked"], "s***t@example.com")
        self.assertNotIn("super-secret-password", snapshot_text)
        self.assertNotIn("student@example.com", snapshot_text)

    def test_debug_llm_output_writes_raw_and_parsed_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("hunt.cli.DATA_DIR", Path(tmpdir)):
                debug_dir = cli._write_llm_debug_outputs(
                    {
                        "company_raw": "raw company",
                        "company_parsed": {"company_name": "Example"},
                        "candidate_raw": "raw candidate",
                        "candidate_parsed": {"full_name": "Vall"},
                        "email_raw": "raw email",
                        "email_parsed": {"subject": "Internship", "body": "Hello"},
                    }
                )

            self.assertEqual((debug_dir / "company_raw.txt").read_text(encoding="utf-8"), "raw company")
            email_parsed = json.loads((debug_dir / "email_parsed.json").read_text(encoding="utf-8"))

        self.assertEqual(email_parsed["subject"], "Internship")


if __name__ == "__main__":
    unittest.main()
