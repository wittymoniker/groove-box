from pathlib import Path
import file_tools
import groovebox_paths


def test_hidden_toggle_never_scans_protected_groovebox_store(tmp_path, monkeypatch):
    root = tmp_path / "volume"
    store = root / ".gb-system-store"
    user = root / "User Library"
    store.mkdir(parents=True)
    user.mkdir()
    (store / "private-state.dat").write_bytes(b"secret")
    (user / "project.MCC").write_bytes(b"project")
    monkeypatch.setattr(groovebox_paths, "system_root", lambda: store)

    paths = list(file_tools._iter_files(str(root), include_hidden=True))
    assert str(user / "project.MCC") in paths
    assert str(store / "private-state.dat") not in paths


def test_selected_protected_root_is_skipped(tmp_path, monkeypatch):
    store = tmp_path / "protected"
    store.mkdir()
    (store / "secret.bin").write_bytes(b"secret")
    monkeypatch.setattr(groovebox_paths, "system_root", lambda: store)
    errors = []

    paths = list(file_tools._iter_files(str(store), include_hidden=True, errors=errors))
    assert paths == []
    assert errors and "protected" in errors[0]["error"]
