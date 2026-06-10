from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from hunt.cv_reader import read_cv
from hunt.utils import HuntError


class TestCvReader(unittest.TestCase):
    def test_missing_file_raises_helpful_error(self) -> None:
        with self.assertRaises(HuntError) as context:
            read_cv("/tmp/hunt-definitely-missing-cv.pdf")

        self.assertIn("CV file not found", str(context.exception))

    def test_reads_txt_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "cv.txt"
            path.write_text("Python\n\nMachine learning project", encoding="utf-8")

            self.assertEqual(read_cv(str(path)), "Python Machine learning project")


if __name__ == "__main__":
    unittest.main()
