import pytest

from devos.state import store


@pytest.fixture(autouse=True)
def isolated_state_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "load_config", lambda: {"state_dir": str(tmp_path)})
    yield tmp_path


def test_load_missing_file_returns_default():
    assert store.load("tickets", {"tickets": {}}) == {"tickets": {}}


def test_save_then_load_roundtrips():
    data = {"tickets": {"JIRA-1": {"branch": "JIRA-1"}}}
    store.save("tickets", data)
    assert store.load("tickets", {"tickets": {}}) == data


def test_state_survives_simulated_process_restart(isolated_state_dir):
    store.save("tunnels", {"tunnels": {"jumpbox": {"pid": 123}}})

    # Simulate a fresh process: nothing in memory, load straight from disk.
    reloaded = store.load("tunnels", {"tunnels": {}})

    assert reloaded == {"tunnels": {"jumpbox": {"pid": 123}}}


def test_corrupt_file_is_quarantined_and_default_returned(isolated_state_dir):
    state_path = isolated_state_dir / "tickets.json"
    state_path.write_text("{not valid json")

    result = store.load("tickets", {"tickets": {}})

    assert result == {"tickets": {}}
    assert not state_path.exists()
    quarantined = list(isolated_state_dir.glob("tickets.json.corrupt-*"))
    assert len(quarantined) == 1


def test_save_is_atomic_no_leftover_tmp_file(isolated_state_dir):
    store.save("tickets", {"tickets": {}})
    leftover_tmp = list(isolated_state_dir.glob("*.tmp"))
    assert leftover_tmp == []
