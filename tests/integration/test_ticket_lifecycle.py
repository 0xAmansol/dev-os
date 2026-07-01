import subprocess
from pathlib import Path

import pytest

from devos.state import store
from devos.tickets import registry, worktree


@pytest.fixture(autouse=True)
def isolated_state(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "load_config", lambda: {"state_dir": str(tmp_path / "state")})


@pytest.fixture(autouse=True)
def isolated_worktrees_dir(tmp_path, monkeypatch):
    wt_dir = tmp_path / "worktrees"
    monkeypatch.setattr(worktree, "load_config", lambda: {"worktrees_dir": str(wt_dir)})
    return wt_dir


@pytest.fixture
def source_repo(tmp_path):
    repo = tmp_path / "source-repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    (repo / "README.md").write_text("hello\n")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "initial"], cwd=repo, check=True)
    return repo


def branch_exists(repo: Path, branch: str) -> bool:
    result = subprocess.run(
        ["git", "branch", "--list", branch], cwd=repo, capture_output=True, text=True
    )
    return branch in result.stdout


def test_full_ticket_lifecycle_create_list_close(source_repo):
    key = "JIRA-1"

    path = worktree.create_worktree(source_repo, key)
    registry.register(key, branch=key, worktree_path=path, source_repo=source_repo)

    assert path.exists()
    assert registry.get(key)["branch"] == key
    assert key in registry.list_all()

    dropped = registry.reconcile()
    assert dropped == []

    worktree.remove_worktree(source_repo, path)
    worktree.delete_branch(source_repo, key)
    registry.deregister(key)

    assert not path.exists()
    assert registry.get(key) is None
    assert not branch_exists(source_repo, key)


def test_close_preserves_unmerged_branch_until_forced(source_repo):
    key = "JIRA-2"
    path = worktree.create_worktree(source_repo, key)
    registry.register(key, branch=key, worktree_path=path, source_repo=source_repo)

    (path / "wip.txt").write_text("work in progress\n")
    subprocess.run(["git", "add", "."], cwd=path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "wip"], cwd=path, check=True)

    worktree.remove_worktree(source_repo, path)
    assert not path.exists()

    with pytest.raises(worktree.WorktreeError):
        worktree.delete_branch(source_repo, key)
    assert branch_exists(source_repo, key)

    worktree.delete_branch(source_repo, key, force=True)
    assert not branch_exists(source_repo, key)


def test_reconcile_self_heals_when_worktree_deleted_outside_devos(source_repo):
    key = "JIRA-3"
    path = worktree.create_worktree(source_repo, key)
    registry.register(key, branch=key, worktree_path=path, source_repo=source_repo)

    worktree.remove_worktree(source_repo, path, force=True)

    dropped = registry.reconcile()
    assert dropped == [key]
    assert registry.get(key) is None


def test_three_concurrent_worktrees_are_independent(source_repo):
    keys = ["JIRA-10", "JIRA-11", "JIRA-12"]
    for key in keys:
        path = worktree.create_worktree(source_repo, key)
        registry.register(key, branch=key, worktree_path=path, source_repo=source_repo)

    tickets = registry.list_all()
    assert set(tickets.keys()) == set(keys)
    for key in keys:
        assert Path(tickets[key]["worktree_path"]).exists()

    for key in keys:
        entry = registry.get(key)
        worktree.remove_worktree(source_repo, Path(entry["worktree_path"]))
        worktree.delete_branch(source_repo, entry["branch"])
        registry.deregister(key)

    assert registry.list_all() == {}
