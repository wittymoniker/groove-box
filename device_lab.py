"""GROOVEBOX_R171_DEVICE_LAB — Device Lab

Audio and MIDI device probe on an isolated I/O thread.

Opened via taskbar_launch / open_extra_window. Heavy work must use the
named worker pool from thread_isolation_opt (never the GUI thread).
"""
from __future__ import annotations
from typing import Any, Optional

_KIND = "device_lab"


def open_window(main: Any = None) -> Optional[Any]:
    try:
        from PyQt6.QtWidgets import (
            QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QTextEdit
        )
    except Exception:
        return None

    existing = getattr(main, f"_win_{0}".format(_KIND), None) if main is not None else None
    try:
        if existing is not None and existing.isVisible():
            existing.raise_()
            existing.activateWindow()
            return existing
    except RuntimeError:
        pass

    parent = main if main is not None else None
    dlg = QDialog(parent)
    dlg.setWindowTitle('Device Lab')
    dlg.setModal(False)
    dlg.resize(640, 420)
    lay = QVBoxLayout(dlg)
    lay.addWidget(QLabel("<b>" + 'Device Lab' + "</b>"))
    body = QLabel('Audio and MIDI device probe on an isolated I/O thread.')
    body.setWordWrap(True)
    lay.addWidget(body)
    try:  # R132.10: the working tool body (taskpad_tools) — live data + the real feature behind this window
        import taskpad_tools as _tpt
        _tpt.build(_KIND, main, dlg, lay)
    except Exception as _tp_exc:
        lay.addWidget(QLabel(f"tool body unavailable: {_tp_exc}"))
    log = QTextEdit()
    log.setReadOnly(True)
    log.setPlaceholderText("Status / worker notes…")
    lay.addWidget(log, 1)

    def _refresh():
        lines = [f"kind={_KIND}", "pool=device_io"]
        try:
            import thread_isolation_opt as tio
            lines.append(tio.pool_status_line('device_io'))
        except Exception as exc:
            lines.append(f"pool status: {exc}")
        log.setPlainText("\n".join(lines))

    row = QHBoxLayout()
    b = QPushButton("Refresh")
    b.clicked.connect(_refresh)
    row.addWidget(b)
    c = QPushButton("Close")
    c.clicked.connect(dlg.close)
    row.addWidget(c)
    lay.addLayout(row)
    _refresh()

    if main is not None:
        attr = f"_win_{0}".format(_KIND)
        try:
            setattr(main, attr, dlg)

            def _clear(*_, a=attr, d=dlg, m=main):
                if getattr(m, a, None) is d:
                    setattr(m, a, None)

            dlg.destroyed.connect(_clear)
        except Exception:
            pass
    dlg.show()
    dlg.raise_()
    try:
        dlg.activateWindow()
    except Exception:
        pass
    return dlg
