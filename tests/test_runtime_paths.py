from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

from runtime_paths import resolve_runtime_paths


class RuntimePathsTest(unittest.TestCase):
    def test_spec_adds_certificate_as_analysis_data(self):
        repository_root = Path(__file__).resolve().parents[1]
        spec = (repository_root / "WUM.spec").read_text(encoding="utf-8")

        self.assertIsNone(re.search(r"a\.datas\s*\+=\s*\[", spec))
        self.assertIn("datas += [(certifi.where(), 'default-data')]", spec)

    def test_windows_build_workflow_runs_for_develop_pushes(self):
        repository_root = Path(__file__).resolve().parents[1]
        workflow = (
            repository_root / ".github" / "workflows" / "build-windows-exe.yml"
        ).read_text(encoding="utf-8")

        self.assertIn("      - develop", workflow)

    def test_frozen_windows_uses_shared_gmonster_data_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            paths = resolve_runtime_paths(
                frozen=True,
                platform_name="win32",
                executable=root / "Program Files" / "GMonster" / "WUM.exe",
                working_dir=root / "ignored",
                local_app_data=root / "Users" / "A" / "AppData" / "Local",
            )

            self.assertEqual(
                paths.data_dir,
                root / "Users" / "A" / "AppData" / "Local" / "GMonster" / "data",
            )

    def test_var_smoke_test_exits_without_loading_gui_dependencies(self):
        repository_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [sys.executable, str(repository_root / "var.py"), "--smoke-test"],
                cwd=directory,
                capture_output=True,
                text=True,
            )

        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
