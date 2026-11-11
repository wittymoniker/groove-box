"""Export Window (EXPORT_WORKER_20261102): one non-modal place for every export.

Buttons start the existing export pipelines; the checkbox moves the heavy render into a separate
process (export_worker.py) so the main window stays smooth; the log shows what each export did.
"""
from __future__ import annotations

import os

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QCheckBox, QDialog, QGridLayout, QHBoxLayout, QLabel, QPlainTextEdit,
                             QPushButton, QScrollArea, QVBoxLayout, QWidget)

_GROUPS = (
    ("🎧 Audio", "#7dff9a", (("WAV", "wav"), ("FLAC", "flac"), ("MP3", "mp3"), ("MCC lossless", "mcc"),
                             ("OGG", "ogg"), ("Opus", "opus"), ("AIFF", "aiff"), ("CAF", "caf"))),
)


class ExportWindow(QDialog):
    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.setWindowTitle("Export Window")
        self.setModal(False)
        self.resize(640, 640)
        self.setMinimumSize(420, 420)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        body = QWidget(); scroll.setWidget(body); outer.addWidget(scroll)
        lay = QVBoxLayout(body)

        head = QLabel("Export Window")
        head.setStyleSheet("font-size:16pt;font-weight:800;color:#5ee0ff;")
        lay.addWidget(head)
        self.chk_worker = QCheckBox("Render exports in a separate process (keeps the main window smooth)")
        self.chk_worker.setToolTip("The project is packed and rendered by a helper process. Output is checked with "
                                   "'Verify worker output' below. If the helper fails the export renders in the window.")
        try:
            import compat_settings as cs
            self.chk_worker.setChecked(bool(cs.load().get("export_in_worker", True)))
        except Exception:
            pass
        self.chk_worker.toggled.connect(self._worker_toggled)
        lay.addWidget(self.chk_worker)
        # GROOVEBOX_R23R_SAVE_TO_DRIVE_20261103: export straight onto a USB stick / SD card.
        try:
            lay.addWidget(self.app._make_export_target_picker(self))
        except Exception:
            pass

        for title, color, items in _GROUPS:
            lbl = QLabel(title); lbl.setStyleSheet(f"font-weight:800;color:{color};")
            lay.addWidget(lbl)
            grid = QGridLayout()
            for i, (text, fmt) in enumerate(items):
                b = QPushButton(text); b.setMinimumHeight(34)
                b.setStyleSheet(f"border:2px solid {color};border-radius:6px;font-weight:700;")
                b.clicked.connect(lambda _c=False, f=fmt: self.app.export_mixdown_dialog(f))
                grid.addWidget(b, i // 4, i % 4)
            lay.addLayout(grid)

        others = (("🎞 Video + audio (.MCC lossless)", "#c58cff", lambda: self.app.export_video_mcc_dialog()),
                  ("🖼 Image frame (PNG / JPG / WebP / MCC)", "#ffd166", lambda: self.app.export_image_frame_dialog()),
                  ("🧊 Project → OBJ (3D song model · exact audio + project inside)", "#9be7ff", lambda: self.app.export_project_obj()),
                  ("📦 All formats…", "#5ee0ff", lambda: self.app.export_all_formats_dialog()),
                  ("🗂 Render Queue…", "#5ee0ff", lambda: self.app.render_queue_dialog()),
                  ("🔁 Convert MCC media…", "#ff8cf0", lambda: self.app.convert_mcc_media_dialog()))
        for text, color, fn in others:
            b = QPushButton(text); b.setMinimumHeight(36)
            b.setStyleSheet(f"border:2px solid {color};border-radius:6px;font-weight:700;text-align:left;padding-left:10px;")
            b.clicked.connect(lambda _c=False, f=fn: f())
            lay.addWidget(b)

        row = QHBoxLayout()
        b_verify = QPushButton("✔ Verify worker output"); b_verify.clicked.connect(self._verify)
        b_cancel = QPushButton("■ Cancel worker render"); b_cancel.clicked.connect(self._cancel)
        b_folder = QPushButton("📁 Exports folder"); b_folder.clicked.connect(self._open_folder)
        for b in (b_verify, b_cancel, b_folder):
            row.addWidget(b)
        lay.addLayout(row)

        lay.addWidget(QLabel("Log"))
        self.log = QPlainTextEdit(); self.log.setReadOnly(True); self.log.setMinimumHeight(150)
        lay.addWidget(self.log, 1)

    def refresh_log(self):
        self.log.setPlainText("\n".join(getattr(self.app, "_export_log_lines", []) or ["(no exports yet)"]))
        self.log.verticalScrollBar().setValue(self.log.verticalScrollBar().maximum())

    def _worker_toggled(self, on):
        try:
            import compat_settings as cs
            cur = cs.load(); cur["export_in_worker"] = bool(on); cs.save(cur); cs.apply_env(cur)
        except Exception:
            pass

    def _verify(self):
        self.app._export_log("Verifying worker output against this window (short render)…")
        try:
            same, text = self.app.verify_worker_parity()
        except Exception as exc:
            same, text = False, f"Verify failed: {exc}"
        self.app._export_log(text)

    def _cancel(self):
        fn = getattr(self.app, "_export_cancel_worker", None)
        if fn:
            fn()
            self.app._export_log("Worker render cancelled; the export will render in the window.")

    def _open_folder(self):
        try:
            from PyQt6.QtCore import QUrl
            from PyQt6.QtGui import QDesktopServices
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.app._exports_dir())))
        except Exception:
            pass
