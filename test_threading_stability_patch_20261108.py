"""Source-level regression checks for the 2026-11-08 stability patch."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def test_project_load_suppresses_transient_boost_activation():
    source = (ROOT / "groovebox.py").read_text(encoding="utf-8")
    start = source.index("def _apply_project_snapshot(self, data):")
    end = source.index("def _apply_project_snapshot_inner", start)
    block = source[start:end]
    assert "self._project_loading = True" in block
    assert "self.pkp_boost_active = False" in block
    assert "self._project_loading = False" in block
    arm = source[source.index("def _arm_pkp_boost_beats"):source.index("def _reschedule_pkp_boost_timer")]
    assert 'getattr(self, "_project_loading", False)' in arm


def test_multidim_model_sync_is_not_in_40ms_animation_tick():
    source = (ROOT / "multidim_ui.py").read_text(encoding="utf-8")
    tick = source[source.index("    def _tick(self):", source.index("class MainMDPanel")):
                  source.index("    def enterEvent", source.index("class MainMDPanel"))]
    assert "self.view.tick(0.04)" in tick
    assert "self.clone_rack.sync_from_host" not in tick
    assert "def _sync_host_state(self):" in source
    assert "self._sync_timer.setInterval(120)" in source


def test_render_queue_does_not_pump_nested_events():
    source = (ROOT / "render_queue.py").read_text(encoding="utf-8")
    assert not __import__("re").search(r"(?m)^\\s*QApplication\\.processEvents\\(\\)", source)
    assert "QTimer.singleShot(0, self._run_next_queue_item)" in source
