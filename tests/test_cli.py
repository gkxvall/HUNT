from __future__ import annotations

import io
import unittest

from rich.console import Console

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


if __name__ == "__main__":
    unittest.main()
