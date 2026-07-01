from datetime import datetime, timezone
from pathlib import Path

from devos.state import store

STATE_NAME = "tickets"


def _load() -> dict:
    return store.load(STATE_NAME, {"tickets": {}})


def _save(data: dict) -> None:
    store.save(STATE_NAME, data)


def register(key: str, branch: str, worktree_path: Path, source_repo: Path) -> dict:
    data = _load()
    entry = {
        "key": key,
        "branch": branch,
        "worktree_path": str(worktree_path),
        "source_repo": str(source_repo),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    data["tickets"][key] = entry
    _save(data)
    return entry


def deregister(key: str) -> None:
    data = _load()
    data["tickets"].pop(key, None)
    _save(data)


def get(key: str):
    return _load()["tickets"].get(key)


def list_all() -> dict:
    return _load()["tickets"]


def reconcile() -> list:
    """Drops registry entries whose worktree no longer exists on disk, so the
    registry never lies about filesystem reality. Returns dropped keys."""
    data = _load()
    dropped = []
    for key, entry in list(data["tickets"].items()):
        if not Path(entry["worktree_path"]).exists():
            dropped.append(key)
            del data["tickets"][key]
    if dropped:
        _save(data)
    return dropped
