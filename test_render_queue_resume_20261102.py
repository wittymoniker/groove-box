import os, sys, tempfile, json
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PyQt6.QtWidgets import QApplication, QMainWindow
import render_queue as rq
_qa = QApplication.instance() or QApplication([])


class _App(QMainWindow):
    def __init__(self, d):
        super().__init__(); self.d = d; self.ran = []
    def _exports_dir(self): return self.d
    def _run_export_preset(self, p):
        if p["key"] == "bad": raise RuntimeError("boom")
        self.ran.append(p["key"])


def test_queue_persists_resumes_and_keeps_failed(monkeypatch):
    from PyQt6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))
    d = tempfile.mkdtemp(); app = _App(d)
    q = rq.RenderQueueDialog(app)
    q.jobs.extend([{"key": "wav", "path": "a.wav"}, {"key": "bad"}, {"key": "flac"}]); q._refresh()
    assert json.load(open(os.path.join(d, ".render_queue.json")))[0]["key"] == "wav"
    q.run()
    _drain_queue(app)
    assert app.ran == ["wav", "flac"] and [j["key"] for j in q.jobs] == ["bad"]
    app2 = _App(d); q2 = rq.RenderQueueDialog(app2)
    assert [j["key"] for j in q2.jobs] == ["bad"]


def _drain_queue(app, timeout=10.0):
    """R30+: the render queue dispatches one job per event-loop turn; let it finish."""
    import time as _t
    from PyQt6.QtWidgets import QApplication
    end = _t.monotonic() + timeout
    QApplication.processEvents()
    while getattr(app, "_render_queue_running", False) and _t.monotonic() < end:
        QApplication.processEvents()
