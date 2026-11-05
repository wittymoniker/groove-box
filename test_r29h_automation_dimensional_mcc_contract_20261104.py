from pathlib import Path

ROOT = Path(__file__).resolve().parent


def test_mcc_integrity_is_shipped_in_active_overlay_and_sync_manifest():
    assert (ROOT / "mcc_integrity.py").is_file()
    assert (ROOT / "BUILD_ISO/app-overlay-v35.22zz/mcc_integrity.py").is_file()
    manifest = (ROOT / "BUILD_ISO/sync_overlay_from_root.sh").read_text()
    assert "mcc_integrity.py" in manifest


def test_automation_row_uses_source_scope_and_teleport_guard():
    source = (ROOT / "groovebox.py").read_text()
    refresh = source.split("    def _refresh_sequencer_automation_row(self):", 1)[1].split("    def _position_step_editor", 1)[0]
    teleport = source.split("    def _teleport_to_sequencer_automation_point(self, point, reposition=True):", 1)[1].split("    def _toggle_sequencer_automation_step", 1)[0]
    assert "_selected_automation_source_instrument" in refresh
    assert "_selected_automation_source_sequence" in refresh
    assert "_automator_teleporting = True" in teleport
    assert "finally:" in teleport


def test_dimensional_workspace_is_display_bounded_and_geometric_rails_are_scrollable():
    source = (ROOT / "multidim_ui.py").read_text()
    # R40 keeps the arc workspace within one display and gives the four full
    # geometric editors independently scrollable side rails, as requested.
    assert "min(1420" in source
    assert "min(880" in source
    assert "QScrollArea(panel)" in source
    assert "scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)" in source
    assert "panel._scroll = scroll" in source
    assert "_md_intended_height = min(880, max(620" in source
