import subprocess
from pathlib import Path

from devos.config.loader import load_config

DEFAULT_WORKTREES_DIR = "~/worktrees"


class WorktreeError(RuntimeError):
    pass


def worktrees_root() -> Path:
    config = load_config()
    path = Path(config.get("worktrees_dir") or DEFAULT_WORKTREES_DIR).expanduser()
    path.mkdir(parents=True, exist_ok=True)
    return path


def _run_git(args: list, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)


def resolve_source_repo(start_dir: Path) -> Path:
    result = _run_git(["rev-parse", "--show-toplevel"], cwd=start_dir)
    if result.returncode != 0:
        raise WorktreeError(f"Not inside a git repository: {start_dir} ({result.stderr.strip()})")
    return Path(result.stdout.strip())


def worktree_path_for(key: str) -> Path:
    return worktrees_root() / key


def create_worktree(source_repo: Path, key: str) -> Path:
    path = worktree_path_for(key)
    if path.exists():
        raise WorktreeError(f"Worktree path already exists: {path}")

    result = _run_git(["worktree", "add", "-b", key, str(path)], cwd=source_repo)
    if result.returncode != 0:
        raise WorktreeError(f"git worktree add failed: {result.stderr.strip()}")
    return path


def remove_worktree(source_repo: Path, path: Path, *, force: bool = False) -> None:
    args = ["worktree", "remove", str(path)]
    if force:
        args.append("--force")
    result = _run_git(args, cwd=source_repo)
    if result.returncode != 0:
        raise WorktreeError(f"git worktree remove failed: {result.stderr.strip()}")


def has_uncommitted_changes(path: Path) -> bool:
    result = _run_git(["status", "--porcelain"], cwd=path)
    return bool(result.stdout.strip())


def delete_branch(source_repo: Path, branch: str, *, force: bool = False) -> None:
    """Safe delete (-d) by default: git refuses if the branch isn't merged,
    preserving abandoned work. Pass force=True (-D) to delete regardless."""
    flag = "-D" if force else "-d"
    result = _run_git(["branch", flag, branch], cwd=source_repo)
    if result.returncode != 0:
        raise WorktreeError(f"git branch delete failed: {result.stderr.strip()}")


def list_worktrees(source_repo: Path) -> list:
    result = _run_git(["worktree", "list", "--porcelain"], cwd=source_repo)
    paths = []
    for line in result.stdout.splitlines():
        if line.startswith("worktree "):
            paths.append(Path(line[len("worktree "):]))
    return paths
