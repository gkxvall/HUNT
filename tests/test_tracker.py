from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from hunt.tracker import list_applications, save_application, update_status


class TestTracker(unittest.TestCase):
    def test_insert_list_and_update_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "applications.db"
            application_id = save_application(
                company_website="https://example.com",
                recipient_email="careers@example.com",
                subject="Internship Application",
                body="Dear Team,\nHello.",
                db_path=db_path,
            )

            records = list_applications(db_path)
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0].id, application_id)
            self.assertEqual(records[0].status, "previewed")

            update_status(application_id, "sent", db_path)
            updated = list_applications(db_path)
            self.assertEqual(updated[0].status, "sent")


if __name__ == "__main__":
    unittest.main()
