"""RENDER_QUEUE_20261102: schedule several exports from the main window and run them one after another.

Each entry is a preset from the unified Export dialog (audio, video, MCC, project ...). The queue runs on the
main thread exactly like a single export (the export pipelines already keep the UI responsive), one job at a
time. Every job after the first reuses the shared mixdown cache, so N formats of the same project render the
audio once. Run one queue at a time; running exports in parallel would fight for the CPU and the audio device.
"""
import json
import os
import time
from PyQt6.QtCore import QTimer, QObject, QEvent
from PyQt6.QtWidgets import (QDialog, QCheckBox, QVBoxLayout, QHBoxLayout, QListWidget, QPushButton, QLabel, QMessageBox,
                             QApplication)


def describe(p):
    return "%s  ->  %s" % (p.get("key", "?"), os.path.basename(p.get("path") or "") or "(asks for a file when it runs)")


# RENDER_QUEUE_ESTIMATE_IDLE_20261102: estimates come from how long this kind of job actually took on this
# machine before (an average of the last few runs per export type); with no history there is no estimate.
IDLE_SECONDS = 30.0
_last_input = [time.monotonic()]


class _InputWatch(QObject):
    def eventFilter(self, obj, ev):
        if ev.type() in (QEvent.Type.KeyPress, QEvent.Type.MouseButtonPress, QEvent.Type.MouseMove, QEvent.Type.Wheel):
            _last_input[0] = time.monotonic()
        return False


def _fmt_secs(x):
    x = int(round(x))
    return "%dh %02dm" % (x // 3600, (x % 3600) // 60) if x >= 3600 else "%dm %02ds" % (x // 60, x % 60)


class RenderQueueDialog(QDialog):
    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.setWindowTitle("Render Queue")
        self.setMinimumWidth(560)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Exports run one after another. Formats of the same project share one render of the audio."))
        self.listw = QListWidget(); lay.addWidget(self.listw)
        row = QHBoxLayout()
        self.btn_add = QPushButton("Add export…"); self.btn_add.clicked.connect(self.add)
        self.btn_remove = QPushButton("Remove selected"); self.btn_remove.clicked.connect(self.remove)
        self.btn_run = QPushButton("Run queue"); self.btn_run.clicked.connect(self.run)
        self.btn_close = QPushButton("Close"); self.btn_close.clicked.connect(self.accept)
        for b in (self.btn_add, self.btn_remove, self.btn_run, self.btn_close):
            row.addWidget(b)
        lay.addLayout(row)
        self.chk_idle = QCheckBox("Run when idle (starts after %d s without keyboard or mouse use, and not while playing)" % int(IDLE_SECONDS))
        self.chk_idle.toggled.connect(self._idle_toggled); lay.addWidget(self.chk_idle)
        self.status = QLabel(""); lay.addWidget(self.status)
        self._idle_timer = QTimer(self); self._idle_timer.setInterval(5000)
        self._idle_timer.timeout.connect(self._idle_tick)
        self._watch = _InputWatch(self)
        QApplication.instance().installEventFilter(self._watch)
        self._load()
        self._refresh()

    # RENDER_QUEUE_RESUME_20261102: the queue is saved after every change and after every finished job, so a
    # crash or closed session resumes with whatever has not run yet. Failed jobs stay queued for a retry.
    def _queue_file(self):
        try:
            return os.path.join(str(self.app._exports_dir()), ".render_queue.json")
        except Exception:
            return ""

    def _load(self):
        path = self._queue_file()
        if not path or self.jobs or not os.path.isfile(path):
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                self.jobs.extend(j for j in data if isinstance(j, dict))
                if self.jobs:
                    self.status = self.status if hasattr(self, "status") else None
                    self.status.setText("Resumed %d unfinished job(s) from the last session." % len(self.jobs))
        except Exception:
            pass

    def _save(self):
        path = self._queue_file()
        if not path:
            return
        try:
            if self.jobs:
                tmp = path + ".tmp"
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(self.jobs, f)
                os.replace(tmp, path)
            elif os.path.isfile(path):
                os.remove(path)
        except Exception:
            pass

    def _hist_file(self):
        q = self._queue_file()
        return os.path.join(os.path.dirname(q), ".render_queue_history.json") if q else ""

    def _history(self):
        try:
            with open(self._hist_file(), "r", encoding="utf-8") as f:
                d = json.load(f)
            return d if isinstance(d, dict) else {}
        except Exception:
            return {}

    def _record(self, key, secs):
        h = self._history(); lst = [float(x) for x in h.get(key, [])][-4:] + [float(secs)]
        h[key] = lst
        try:
            with open(self._hist_file(), "w", encoding="utf-8") as f:
                json.dump(h, f)
        except Exception:
            pass

    def estimate(self, p):
        v = self._history().get(p.get("key", "?"))
        return sum(v) / len(v) if v else None

    def _idle_toggled(self, on):
        if on:
            self._idle_timer.start()
            self.status.setText("Waiting for idle: the queue starts after %d s of no input." % int(IDLE_SECONDS))
        else:
            self._idle_timer.stop()

    def _idle_tick(self):
        app = self.app
        if not self.jobs or getattr(app, "_render_queue_running", False) or getattr(app, "is_playing", False):
            return
        if time.monotonic() - _last_input[0] >= IDLE_SECONDS:
            self.chk_idle.setChecked(False)
            self.run()

    @property
    def jobs(self):
        return self.app.__dict__.setdefault("_render_queue_jobs", [])

    def _refresh(self):
        self.listw.clear()
        for i, p in enumerate(self.jobs):
            e = self.estimate(p)
            self.listw.addItem("%d. %s   [%s]" % (i + 1, describe(p), "about " + _fmt_secs(e) if e else "no estimate yet"))
        ests = [self.estimate(p) for p in self.jobs]
        if self.jobs and all(ests):
            self.status.setText("Estimated total: about %s (from earlier runs on this computer)." % _fmt_secs(sum(ests)))
        self.btn_run.setEnabled(bool(self.jobs))
        self._save()

    def add(self):
        from export_dialog import ExportAllDialog
        try:
            folder = self.app._audio_exports_dir()
        except Exception:
            folder = ""
        dlg = ExportAllDialog(self.app, self, initial_format="wav", default_dir=folder)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.jobs.append(dlg.result_preset())
            self._refresh()

    def remove(self):
        r = self.listw.currentRow()
        if 0 <= r < len(self.jobs):
            del self.jobs[r]
            self._refresh()

    def run(self):
        app = self.app
        if getattr(app, "_render_queue_running", False) or not self.jobs:
            return
        app._render_queue_running = True
        jobs = list(self.jobs)
        done, failed = [], []
        shown = []
        orig_info = QMessageBox.information
        QMessageBox.information = staticmethod(lambda *a, **k: shown.append(str(a[2]) if len(a) > 2 else ""))
        try:
            for i, p in enumerate(jobs):
                self.status.setText("Running %d of %d: %s" % (i + 1, len(jobs), describe(p)))
                QApplication.processEvents()
                try:
                    _t0 = time.monotonic()
                    app._run_export_preset(p)
                    self._record(p.get("key", "?"), time.monotonic() - _t0)
                    done.append(describe(p))
                    if p in self.jobs:
                        self.jobs.remove(p)
                    self._save()
                except Exception as exc:
                    failed.append("%s: %s" % (describe(p), exc))
        finally:
            QMessageBox.information = orig_info
            app._render_queue_running = False
        self._refresh()
        msg = "Finished %d of %d.\n" % (len(done), len(jobs)) + "\n".join(done)
        if failed:
            msg += "\n\nFailed:\n" + "\n".join(failed)
        self.status.setText("Queue finished.")
        QMessageBox.information(self, "Render Queue", msg)
