"""Regression contract: autosave and project recovery retain authored seed data."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def test_seed_complete_snapshot_is_shared_by_save_autosave_and_export():
    source = (ROOT / "groovebox.py").read_text(encoding="utf-8")
    snapshot = source[source.index("def _project_snapshot_inner(self):"):source.index("def _on_master_global_eq_changed", source.index("def _project_snapshot_inner(self):"))]
    autosave = source[source.index("def _autosave_project(self):"):source.index("def _autosave_into_open_project", source.index("def _autosave_project(self):"))]
    assert '"seed": str(_seed_script)' in snapshot
    assert '"seed_state": _seed_state' in snapshot
    assert '"script": str(_seed_script)' in snapshot
    assert '"numeric_seed_t0"' in snapshot and '"values_t0"' in snapshot
    assert '"workspace_override"' in snapshot and '"engine_modes"' in snapshot
    assert "data = self._project_snapshot()" in autosave
    assert "_atomic_write_document(path, frozen)" in autosave


def test_seed_state_restore_prefers_authored_script_and_keeps_legacy_projects_compatible():
    source = (ROOT / "groovebox.py").read_text(encoding="utf-8")
    assert '_saved_seed_state.get("script", data.get("seed", ""))' in source
    assert '"seed_workspace_override", True' in source
    assert 'self._restored_seed_script_video_overrides = copy.deepcopy(_saved_video_overrides)' in source


def test_appliance_overlay_uses_the_same_seed_roundtrip_implementation():
    root = (ROOT / "groovebox.py").read_bytes()
    overlay = (ROOT / "BUILD_ISO" / "app-overlay-v35.22zz" / "groovebox.py").read_bytes()
    assert root == overlay
