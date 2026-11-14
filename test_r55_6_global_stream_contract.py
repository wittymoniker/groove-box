"""Static source-contract checks for R55.6; intentionally not executed in this handoff."""
from pathlib import Path
ROOT = Path(__file__).resolve().parent

def test_global_policy_has_explicit_precedence_and_no_worker_creation():
    src = (ROOT / "global_intelligence.py").read_text(encoding="utf-8")
    for lane in ("audio_rt", "gui", "device_io", "visual_preview", "edit_together", "export", "background"):
        assert lane in src
    assert "def sniff(" in src and "def huff(" in src and "def plan(" in src

def test_viewport_resize_is_debounced_and_latest_only():
    src = (ROOT / "groovebox.py").read_text(encoding="utf-8")
    assert "_resize_render_timer.setInterval(65)" in src
    assert "def _render_current_viewport(" in src
    assert "int(generation) == int(self._render_generation)" in src

def test_edit_together_protocol_is_preserved_and_integrated():
    coedit = (ROOT / "coedit.py").read_text(encoding="utf-8")
    ui = (ROOT / "live_edit_ui.py").read_text(encoding="utf-8")
    assert 'gi.huff("edit_together"' in coedit
    assert 'gi.plan({"edit_together"' in ui
    assert "def local_tick(" in coedit and "def handle(" in coedit
