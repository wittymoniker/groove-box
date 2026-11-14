import os, sys
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PyQt6.QtWidgets import QApplication
import render_queue as rq
_qa = QApplication.instance() or QApplication([])


class _App(__import__("PyQt6.QtWidgets", fromlist=["QWidget"]).QWidget):
    is_playing = False
    def __init__(self, d):
        super().__init__(); self.d = d; self.ran = []
    def _exports_dir(self): return self.d
    def _run_export_preset(self, p): self.ran.append(p)


def test_estimate_history_and_idle(tmp_path, monkeypatch):
    app = _App(str(tmp_path)); app._render_queue_jobs = [{"key": "wav", "path": "a.wav"}]
    dlg = rq.RenderQueueDialog(app)
    assert "no estimate yet" in dlg.listw.item(0).text()
    dlg._record("wav", 60); dlg._record("wav", 120)
    assert dlg.estimate({"key": "wav"}) == 90
    dlg._refresh()
    assert "about 1m 30s" in dlg.listw.item(0).text() and "Estimated total" in dlg.status.text()
    dlg.chk_idle.setChecked(True)
    rq._last_input[0] = rq.time.monotonic()
    dlg._idle_tick(); assert not app.ran                     # not idle yet
    rq._last_input[0] -= 100
    app.is_playing = True; dlg._idle_tick(); assert not app.ran   # playing blocks it
    app.is_playing = False
    monkeypatch.setattr(rq.QMessageBox, "information", staticmethod(lambda *a, **k: None))
    dlg._idle_tick()
    from PyQt6.QtWidgets import QApplication
    for _ in range(50): QApplication.processEvents()          # R30+: queue runs on event-loop turns
    assert len(app.ran) == 1 and not dlg.jobs
