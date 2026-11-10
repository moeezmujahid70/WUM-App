from pathlib import Path
import re
import unittest


class AppVersionTest(unittest.TestCase):
    def test_wum_reports_the_same_version_as_the_gmonster_release(self):
        # The login server requires an exact match with its latest version record
        # (type "main"), and GMonster and WUM ship together in one installer.
        source = Path("var.py").read_text(encoding="utf-8")
        match = re.search(r"^version = '([^']+)'$", source, re.MULTILINE)

        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), "3.0.1")


if __name__ == "__main__":
    unittest.main()
