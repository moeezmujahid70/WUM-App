"""Runtime path resolution for development and installed WUM builds."""

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Callable


DEFAULT_WUM_API_BASE = "https://dev-enzim.pythonanywhere.com/"


@dataclass(frozen=True)
class RuntimePaths:
    app_dir: Path
    data_dir: Path
    is_frozen_windows: bool


RUNTIME_DATA_DIRECTORIES = (
    "gmonster_config",
    "wum_config",
    "sheets",
    "logs/wum",
)


def resolve_runtime_paths(
    *,
    frozen: bool,
    platform_name: str,
    executable: str | Path,
    working_dir: str | Path,
    local_app_data: str | Path,
) -> RuntimePaths:
    """Use shared GMonster data for installed Windows builds only."""
    is_frozen_windows = frozen and platform_name == "win32"
    app_dir = Path(executable).resolve().parent if frozen else Path(working_dir).resolve()
    data_dir = (
        Path(local_app_data).resolve() / "GMonster" / "data"
        if is_frozen_windows
        else app_dir / "data"
    )
    return RuntimePaths(app_dir, data_dir, is_frozen_windows)


def initialize_runtime_data(data_dir: str | Path) -> None:
    """Create the shared directories WUM needs without touching user files."""
    root = Path(data_dir)
    for relative_dir in RUNTIME_DATA_DIRECTORIES:
        (root / relative_dir).mkdir(parents=True, exist_ok=True)


def resolve_wum_api_base(data_dir: str | Path) -> str:
    """Use GMonster's shared API setting, with a safe first-run fallback."""
    config_path = Path(data_dir) / "gmonster_config" / "config.json"
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
        api_base = str(payload.get("config", {}).get("api", "")).strip()
    except (OSError, ValueError, TypeError):
        api_base = ""

    api_base = api_base or DEFAULT_WUM_API_BASE
    return api_base if api_base.endswith("/") else api_base + "/"


def open_sheets_folder(
    data_dir: str | Path, open_directory: Callable[[Path], None]
) -> Path:
    """Ensure the shared sheets directory exists and open it."""
    sheets_dir = Path(data_dir) / "sheets"
    sheets_dir.mkdir(parents=True, exist_ok=True)
    open_directory(sheets_dir)
    return sheets_dir
