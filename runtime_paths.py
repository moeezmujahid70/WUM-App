"""Runtime path resolution for development and installed WUM builds."""

from dataclasses import dataclass
from pathlib import Path


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
