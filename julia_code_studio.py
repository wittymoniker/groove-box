"""JuliaCode IDE: opt-in Julia authoring, syntax checking and isolated execution."""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QObject, QRunnable, Qt, QThreadPool, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDialog, QFileDialog, QHBoxLayout, QLabel, QMessageBox, QPlainTextEdit,
    QPushButton, QSplitter, QVBoxLayout,
)

import julia_code

_TEMPLATE = '''# JuliaCode — MATGROOVEBOX developer workspace
# Julia is optional. The project-local DSP package is available as:
# using GrooveboxMeumOT

using Printf

println("JuliaCode is running")
@printf("Julia version: %s\\n", VERSION)
'''


class _TaskSignals(QObject):
    finished = pyqtSignal(int, object)


class _JuliaTask(QRunnable):
    def __init__(self, task_id: int, action: str, source: str, filename: str):
        super().__init__()
        self.task_id = task_id
        self.action = action
        self.source = source
        self.filename = filename
        self.signals = _TaskSignals()
        self.setAutoDelete(False)

    def run(self):
        if self.action == "check":
            result = julia_code.check_source(self.source, filename=self.filename)
        elif self.action == "status":
            result = julia_code.runtime_status()
        else:
            result = julia_code.run_source(self.source, filename=self.filename)
        self.signals.finished.emit(self.task_id, result)


class JuliaCodeWindow(QDialog):
    def __init__(self, host=None):
        super().__init__(host, Qt.WindowType.Window)
        self.host = host
        self.path: Path | None = None
        self._task_id = 0
        self._active: dict[int, _JuliaTask] = {}
        self.setWindowTitle("JuliaCode IDE · MATGROOVEBOX Developer Tools")
        self.resize(1050, 760)
        root = QVBoxLayout(self)
        intro = QLabel(
            "JuliaCode is shared by the DSP bridge and developer overlay. "
            "Syntax checks only parse source; Run starts a separate Julia process. "
            "Julia scripts execute with your user permissions—run only code you trust."
        )
        intro.setWordWrap(True)
        root.addWidget(intro)

        top = QHBoxLayout()
        self.open_button = QPushButton("Open .jl…")
        self.save_button = QPushButton("Save")
        self.save_as_button = QPushButton("Save as…")
        self.check_button = QPushButton("Check syntax")
        self.run_button = QPushButton("▶ Run Julia")
        self.status_button = QPushButton("Check Julia runtime")
        self.clear_button = QPushButton("Clear output")
        for button in (self.open_button, self.save_button, self.save_as_button,
                       self.check_button, self.run_button, self.status_button,
                       self.clear_button):
            top.addWidget(button)
        top.addStretch(1)
        root.addLayout(top)

        split = QSplitter(Qt.Orientation.Vertical, self)
        self.editor = QPlainTextEdit(split)
        self.editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        font = QFont("Consolas")
        font.setStyleHint(QFont.StyleHint.Monospace)
        font.setPointSize(10)
        self.editor.setFont(font)
        self.editor.setTabStopDistance(4 * self.editor.fontMetrics().horizontalAdvance(" "))
        self.editor.setPlainText(_TEMPLATE)
        self.output = QPlainTextEdit(split)
        self.output.setReadOnly(True)
        self.output.setMaximumBlockCount(8000)
        self.output.setFont(font)
        split.addWidget(self.editor)
        split.addWidget(self.output)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 2)
        root.addWidget(split, 1)
        self.status = QLabel("Checking Julia availability…")
        self.status.setWordWrap(True)
        root.addWidget(self.status)

        self.open_button.clicked.connect(self.open_file)
        self.save_button.clicked.connect(self.save)
        self.save_as_button.clicked.connect(self.save_as)
        self.check_button.clicked.connect(lambda: self.submit("check"))
        self.run_button.clicked.connect(lambda: self.submit("run"))
        self.status_button.clicked.connect(lambda: self.submit("status"))
        self.clear_button.clicked.connect(self.output.clear)
        self.submit("status")

    def _set_busy(self, busy: bool):
        self.check_button.setEnabled(not busy)
        self.run_button.setEnabled(not busy)
        self.status_button.setEnabled(not busy)

    def submit(self, action: str):
        if self._active:
            self.status.setText("A Julia task is already running; wait for it to finish.")
            return
        self._task_id += 1
        task_id = self._task_id
        source = self.editor.toPlainText()
        filename = self.path.name if self.path else "untitled.jl"
        task = _JuliaTask(task_id, action, source, filename)
        task.signals.finished.connect(self._task_finished)
        self._active[task_id] = task
        self._set_busy(True)
        self.status.setText({"check": "Parsing Julia source in a background process…",
                             "run": "Running Julia in a separate process…",
                             "status": "Detecting Julia runtime…"}.get(action, "Working…"))
        QThreadPool.globalInstance().start(task)

    def _task_finished(self, task_id: int, result):
        self._active.pop(task_id, None)
        self._set_busy(bool(self._active))
        if isinstance(result, dict):
            available = result.get("available", False)
            self.status.setText(result.get("message", "Julia runtime unavailable."))
            self.output.appendPlainText(
                ("Julia runtime available" if available else "Julia runtime unavailable") +
                f"\nExecutable: {result.get('executable') or 'not found'}\n"
                f"Version: {result.get('version') or 'unknown'}\n"
                f"Project: {result.get('project') or julia_code.PROJECT_DIR}\n"
            )
            return
        data = result.to_dict() if hasattr(result, "to_dict") else dict(result)
        action = data.get("action", "Julia")
        passed = bool(data.get("ok"))
        state = "PASS" if passed else "FAILED"
        self.status.setText(f"{action.title()} {state} · {data.get('elapsed_seconds', 0.0):.2f}s")
        details = [f"[{action.upper()} {state}]", f"Exit code: {data.get('returncode')}"]
        if data.get("timed_out"):
            details.append("Timed out; the child process was stopped by the runner.")
        if data.get("error"):
            details.append(str(data["error"]))
        if data.get("stdout"):
            details += ["--- stdout ---", data["stdout"]]
        if data.get("stderr"):
            details += ["--- stderr ---", data["stderr"]]
        self.output.appendPlainText("\n".join(details) + "\n")

    def open_file(self):
        start = str(self.path.parent if self.path else julia_code.workspace_dir())
        name, _ = QFileDialog.getOpenFileName(self, "Open Julia source", start,
                                              "Julia source (*.jl);;All files (*)")
        if not name:
            return
        try:
            text = Path(name).read_text(encoding="utf-8")
            if len(text.encode("utf-8")) > julia_code.MAX_SOURCE_BYTES:
                raise ValueError("File exceeds the 1 MB editor limit.")
            self.editor.setPlainText(text)
            self.path = Path(name)
            self.setWindowTitle(f"JuliaCode IDE · {self.path.name}")
            self.status.setText(f"Opened {self.path}")
        except Exception as exc:
            QMessageBox.warning(self, "Open Julia file", str(exc))

    def save(self):
        if self.path is None:
            return self.save_as()
        try:
            text = self.editor.toPlainText()
            if len(text.encode("utf-8")) > julia_code.MAX_SOURCE_BYTES:
                raise ValueError("Source exceeds the 1 MB editor limit.")
            tmp = self.path.with_name(self.path.name + ".part")
            tmp.write_text(text, encoding="utf-8", newline="\n")
            tmp.replace(self.path)
            self.status.setText(f"Saved {self.path}")
            return str(self.path)
        except Exception as exc:
            QMessageBox.warning(self, "Save Julia file", str(exc))
            return None

    def save_as(self):
        name, _ = QFileDialog.getSaveFileName(
            self, "Save Julia source", str(julia_code.workspace_dir() / "untitled.jl"),
            "Julia source (*.jl);;All files (*)")
        if not name:
            return None
        target = Path(name)
        if not target.suffix:
            target = target.with_suffix(".jl")
        self.path = target
        return self.save()


_WINDOW = None


def open_window(host=None):
    global _WINDOW
    candidate = getattr(host, "_groovebox_juliacode_window", None) if host is not None else _WINDOW
    try:
        if candidate is not None:
            candidate.isVisible()
    except RuntimeError:
        candidate = None
    if candidate is None:
        candidate = JuliaCodeWindow(host)
        if host is not None:
            host._groovebox_juliacode_window = candidate
        else:
            _WINDOW = candidate
    candidate.show()
    candidate.raise_()
    candidate.activateWindow()
    return candidate
