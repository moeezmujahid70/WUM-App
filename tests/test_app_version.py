from pathlib import Path
import re
import unittest


def _assignment(name):
    source = Path("var.py").read_text(encoding="utf-8")
    match = re.search(r"^{} = '([^']+)'$".format(name), source, re.MULTILINE)
    return match.group(1) if match else None


class AppVersionTest(unittest.TestCase):
    def test_wum_update_check_uses_the_wum_release_version(self):
        # verify/wum_version compares against the WUM record on the server.
        self.assertEqual(_assignment("version"), "1.1r")

    def test_login_uses_the_gmonster_release_version(self):
        # verify/login (type "main") requires the GMonster version, since
        # GMonster and WUM ship together in one installer.
        self.assertEqual(_assignment("login_version"), "3.0.1")

    def test_login_request_sends_login_version(self):
        source = Path("dialog.py").read_text(encoding="utf-8")
        self.assertIn("'version': var.login_version", source)


if __name__ == "__main__":
    unittest.main()
