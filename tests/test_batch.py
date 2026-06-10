from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from hunt.batch import (
    BatchRow,
    is_valid_email,
    is_valid_website,
    process_batch,
    quality_check_email,
    read_batch_csv,
    select_rows,
    update_results_csv,
    validate_batch_rows,
    _apply_row_context,
    _config_for_row,
)
from hunt.config import AppConfig


class TestBatchMode(unittest.TestCase):
    def test_csv_validation_missing_required_columns(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "companies.csv"
            path.write_text("company_name,email\nExample,careers@example.com\n", encoding="utf-8")

            with self.assertRaises(Exception) as context:
                read_batch_csv(path)

        self.assertIn("missing required columns", str(context.exception))

    def test_invalid_email_and_website_detection(self) -> None:
        self.assertFalse(is_valid_email("not-email"))
        self.assertFalse(is_valid_website("example.com"))
        self.assertTrue(is_valid_email("careers@example.com"))
        self.assertTrue(is_valid_website("https://example.com"))

    def test_duplicate_detection(self) -> None:
        rows = [
            BatchRow(0, "A", "https://example.com", "careers@example.com"),
            BatchRow(1, "B", "https://example.com", "careers@example.com"),
        ]
        validated = validate_batch_rows(rows)
        self.assertEqual(validated[1].status, "duplicate")

    def test_limit_and_start_at_behavior(self) -> None:
        rows = [BatchRow(i, f"C{i}", f"https://e{i}.com", f"c{i}@e.com") for i in range(5)]
        selected = select_rows(rows, start_at=2, limit=2)
        self.assertEqual([row.row_index for row in selected], [2, 3])

    def test_row_context_overrides_language_and_mode(self) -> None:
        row = BatchRow(
            0,
            "Example",
            "https://example.com",
            "careers@example.com",
            role="AI Intern",
            language="Turkish",
            internship_mode="hybrid",
        )
        config = _config_for_row(AppConfig(), row)
        summary = _apply_row_context({}, row)

        self.assertEqual(config.email_style.language, "Turkish")
        self.assertEqual(config.internship_preferences.mode, "hybrid")
        self.assertEqual(summary["target_role"], "AI Intern")

    def test_results_csv_updates(self) -> None:
        from hunt.batch import BatchResult

        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "results.csv"
            db_path = Path(tmpdir) / "batch.db"
            update_results_csv(
                output,
                [BatchResult(0, "Example", "https://example.com", "careers@example.com", "drafted", "Subject")],
            )
            with output.open(encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))

        self.assertEqual(rows[0]["status"], "drafted")

    def test_dry_run_does_not_call_ollama(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "companies.csv"
            cv_path = Path(tmpdir) / "cv.txt"
            output = Path(tmpdir) / "results.csv"
            db_path = Path(tmpdir) / "batch.db"
            csv_path.write_text("website,email\nhttps://example.com,careers@example.com\n", encoding="utf-8")
            cv_path.write_text("CV", encoding="utf-8")

            with patch("hunt.batch.summarize_company") as summarize:
                summary = process_batch(str(csv_path), str(cv_path), AppConfig(), dry_run=True, output=str(output), db_path=db_path)

        summarize.assert_not_called()
        self.assertEqual(summary.results[0].status, "pending")

    def test_draft_only_does_not_send_and_reads_cv_once(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "companies.csv"
            cv_path = Path(tmpdir) / "cv.txt"
            output = Path(tmpdir) / "results.csv"
            db_path = Path(tmpdir) / "batch.db"
            csv_path.write_text(
                "website,email\nhttps://one.com,one@example.com\nhttps://two.com,two@example.com\n",
                encoding="utf-8",
            )
            cv_path.write_text("CV", encoding="utf-8")

            with patch("hunt.batch.read_cv", return_value="CV") as read_cv:
                with patch("hunt.batch.summarize_candidate", return_value={}):
                    with patch("hunt.batch.extract_website_text", return_value="Website"):
                        with patch("hunt.batch.summarize_company", return_value={}):
                            with patch("hunt.batch.write_email", return_value=("Subject", "Dear Team,\nHello.")):
                                with patch("hunt.batch.send_email") as send_email:
                                    summary = process_batch(
                                        str(csv_path),
                                        str(cv_path),
                                        AppConfig(),
                                        draft_only=True,
                                        output=str(output),
                                        db_path=db_path,
                                    )

        read_cv.assert_called_once()
        send_email.assert_not_called()
        self.assertEqual(len(summary.results), 2)

    def test_low_quality_generated_email_is_not_sent(self) -> None:
        row = BatchRow(0, "Example", "https://example.com", "careers@example.com")
        errors, _ = quality_check_email("Subject", '{"subject":"x","body":"y"}', row, AppConfig())
        self.assertTrue(errors)

    def test_skip_existing_skips_already_sent_companies(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "companies.csv"
            cv_path = Path(tmpdir) / "cv.txt"
            output = Path(tmpdir) / "results.csv"
            db_path = Path(tmpdir) / "batch.db"
            csv_path.write_text("website,email\nhttps://example.com,careers@example.com\n", encoding="utf-8")
            cv_path.write_text("CV", encoding="utf-8")

            with patch("hunt.batch.application_exists", return_value=True):
                with patch("hunt.batch.read_cv", return_value="CV"):
                    with patch("hunt.batch.summarize_candidate", return_value={}):
                        summary = process_batch(str(csv_path), str(cv_path), AppConfig(), output=str(output), db_path=db_path)

        self.assertEqual(summary.results[0].status, "skipped")

    def test_keyboard_interrupt_saves_partial_progress(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "companies.csv"
            cv_path = Path(tmpdir) / "cv.txt"
            output = Path(tmpdir) / "results.csv"
            db_path = Path(tmpdir) / "batch.db"
            csv_path.write_text("website,email\nhttps://example.com,careers@example.com\n", encoding="utf-8")
            cv_path.write_text("CV", encoding="utf-8")

            with patch("hunt.batch.read_cv", side_effect=KeyboardInterrupt):
                summary = process_batch(str(csv_path), str(cv_path), AppConfig(), output=str(output), db_path=db_path)

            self.assertTrue(summary.stopped)
            self.assertTrue(output.exists())


if __name__ == "__main__":
    unittest.main()
