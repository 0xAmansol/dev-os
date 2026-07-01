import json
import os
import time
from pathlib import Path

from devos.config.loader import load_config

DEFAULT_STATE_DIR = "~/.dev-os/state"


def state_dir() -> Path:
    config = load_config()
    path = Path(config.get("state_dir") or DEFAULT_STATE_DIR).expanduser()
    path.mkdir(parents=True, exist_ok=True)
    return path


def _path_for(name: str) -> Path:
    return state_dir() / f"{name}.json"


def load(name: str, default: dict) -> dict:
    """Reads name.json from the state dir. Missing file returns default;
    a corrupt file is quarantined (never silently deleted) and default returned."""
    path = _path_for(name)
    if not path.exists():
        return default
    try:
        with path.open() as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        _quarantine(path)
        return default


def save(name: str, data: dict) -> None:
    """Atomic write: temp file + rename, so a crash mid-write can't corrupt state."""
    path = _path_for(name)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w") as f:
        json.dump(data, f, indent=2, sort_keys=True)
    os.replace(tmp_path, path)


def _quarantine(path: Path) -> None:
    quarantine_path = path.with_name(f"{path.name}.corrupt-{int(time.time())}")
    path.rename(quarantine_path)
