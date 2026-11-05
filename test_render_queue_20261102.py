import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"
import pytest


@pytest.fixture(scope="module")
def app():
    from PyQt6.QtWidgets import QApplication
    global _QA
    _QA = QApplication.instance() or QApplication([])
    import groovebox as g
    return g.MathematiciansGrooveboxApp()


def test_queue_runs_jobs_in_order_and_survives_a_failure(app, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox
    import render_queue as rq
    ran = []

    def fake_mix(fmt):
        ran.append(("audio", fmt, dict(app._export_preset or {}).get("path")))
        QMessageBox.information(app, "x", "done")        # per-export confirmation must not block the queue

    monkeypatch.setattr(app, "export_mixdown_dialog", fake_mix)
    monkeypatch.setattr(app, "export_project_mcc", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    app._render_queue_jobs = [
        {"family": "audio", "key": "wav", "ext": ".wav", "path": "/tmp/a.wav"},
        {"family": "project", "key": "mcc", "ext": ".MCC", "path": "/tmp/p.MCC", "make_current": False, "confirm": False},
        {"family": "audio", "key": "flac", "ext": ".flac", "path": "/tmp/b.flac"},
    ]
    shown = []
    monkeypatch.setattr(rq.QMessageBox, "information", staticmethod(lambda *a, **k: shown.append(a)))
    d = rq.RenderQueueDialog(app)
    d.run()
    assert [r[1] for r in ran] == ["wav", "flac"]
    assert ran[0][2] == "/tmp/a.wav" and app._export_preset is None
    assert [j['key'] for j in app._render_queue_jobs] == ['mcc'] and not app._render_queue_running   # RENDER_QUEUE_RESUME_20261102: the failed job stays queued for a retry
