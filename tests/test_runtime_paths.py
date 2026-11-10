import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

from runtime_paths import (
    initialize_wum_defaults,
    open_sheets_folder,
    resolve_runtime_paths,
    resolve_wum_api_base,
)


class RuntimePathsTest(unittest.TestCase):

    def test_first_run_uses_shared_gmonster_api_when_wum_config_is_missing(self):
        with tempfile.TemporaryDirectory() as directory:
            data_dir = Path(directory)
            config_dir = data_dir / "gmonster_config"
            config_dir.mkdir()
            (config_dir / "config.json").write_text(
                json.dumps({"config": {"api": "https://server.example"}}),
                encoding="utf-8",
            )

            self.assertEqual(
                resolve_wum_api_base(data_dir),
                "https://server.example/",
            )

    def test_first_run_uses_safe_default_api_without_any_config(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(
                resolve_wum_api_base(Path(directory)),
                "https://dev-enzim.pythonanywhere.com/",
            )

    def test_open_sheets_folder_creates_and_opens_the_shared_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            opened = []
            data_dir = Path(directory) / "GMonster" / "data"

            result = open_sheets_folder(data_dir, opened.append)

            self.assertEqual(result, data_dir / "sheets")
            self.assertTrue(result.is_dir())
            self.assertEqual(opened, [result])

    def test_first_run_seeds_safe_wum_templates_without_overwriting_user_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data_dir = root / "data"
            defaults_dir = root / "defaults"
            default_config_dir = defaults_dir / "wum_config"
            default_config_dir.mkdir(parents=True)
            (default_config_dir / "config.json").write_text(
                json.dumps({"config": {"openai_api_key": ""}}),
                encoding="utf-8",
            )
            (default_config_dir / "PROMPT1.txt").write_text(
                "safe prompt", encoding="utf-8"
            )
            (default_config_dir / "EMAIL1.txt").write_text(
                "safe email", encoding="utf-8"
            )

            existing_config_dir = data_dir / "wum_config"
            existing_config_dir.mkdir(parents=True)
            (existing_config_dir / "EMAIL1.txt").write_text(
                "customer email", encoding="utf-8"
            )

            initialize_wum_defaults(data_dir, defaults_dir)

            self.assertEqual(
                json.loads(
                    (existing_config_dir / "config.json").read_text(encoding="utf-8")
                )["config"]["openai_api_key"],
                "",
            )
            self.assertEqual(
                (existing_config_dir / "PROMPT1.txt").read_text(encoding="utf-8"),
                "safe prompt",
            )
            self.assertEqual(
                (existing_config_dir / "EMAIL1.txt").read_text(encoding="utf-8"),
                "customer email",
            )

    def test_distributed_wum_defaults_contain_no_openai_key(self):
        repository_root = Path(__file__).resolve().parents[1]
        defaults_dir = repository_root / "wum_defaults" / "wum_config"
        config = json.loads(
            (defaults_dir / "config.json").read_text(encoding="utf-8")
        )

        self.assertEqual(config["config"]["openai_api_key"], "")
        for filename in (
            "PROMPT1.txt",
            "PROMPT2.txt",
            "EMAIL1.txt",
            "EMAIL2.txt",
            "subject.txt",
            "body.txt",
        ):
            self.assertTrue((defaults_dir / filename).is_file(), filename)
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
