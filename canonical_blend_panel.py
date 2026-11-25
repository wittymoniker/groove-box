"""GROOVEBOX_R171 panel — Canonical Blend"""
from __future__ import annotations
from typing import Any, Optional

def open_panel(main: Any = None) -> Optional[Any]:
    try:
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton
    except Exception:
        return None
    dlg = QDialog(main if main is not None else None)
    dlg.setWindowTitle('Canonical Blend')
    dlg.setModal(False)
    dlg.resize(360, 220)
    lay = QVBoxLayout(dlg)
    lay.addWidget(QLabel("<b>" + 'Canonical Blend' + "</b>"))
    lab = QLabel('Read-only view of blend strengths (no engine writes).')
    lab.setWordWrap(True)
    lay.addWidget(lab)
    try:  # R132.10: the working tool body (taskpad_tools) — live data + the real feature behind this window
        import taskpad_tools as _tpt
        _tpt.build('canonical_blend', main, dlg, lay)
    except Exception as _tp_exc:
        lay.addWidget(QLabel(f"tool body unavailable: {_tp_exc}"))
    status = QLabel("")
    status.setWordWrap(True)
    lay.addWidget(status)

    def refresh():
        try:
            import thread_isolation_opt as tio
            status.setText("\n".join(tio.snapshot().values()))
        except Exception as exc:
            status.setText(str(exc))

    b = QPushButton("Refresh"); b.clicked.connect(refresh); lay.addWidget(b)
    refresh()
    dlg.show()
    return dlg

def open_window(main=None):
    return open_panel(main)
