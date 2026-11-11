"""canonical_view.py — R32.10.3: see what the canonical engines actually change.

Canonical values are applied at render time (the ownership rule: an untouched control is 100 % canonical,
a touched one 50 / 50), so the controls themselves keep showing the user's or factory value. This window lists,
for every canonical-governed value, the stored (shown) value next to the effective value the render uses, and
which engines are on. Read-only; nothing here changes the project.
"""
import json

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget,
                             QTableWidgetItem, QHeaderView, QCheckBox)

_SOURCES = (
    ("Modulation (XMOD / window mod)", "global_mod_state", "_effective_mod_state"),
    ("Master Vector x / y / z", "master_vector_state", "_master_vector_effective"),
    ("Geometric synths (vector · wavetable · ball · cellular)", None, "_effective_geometric_states"),
)


def _flat(v, path=""):
    out = {}
    if isinstance(v, dict):
        for k in sorted(v, key=str):
            out.update(_flat(v[k], f"{path}/{k}" if path else str(k)))
    elif isinstance(v, (list, tuple)) and v and all(isinstance(x, (int, float)) for x in v):
        for i, x in enumerate(v):
            out[f"{path}[{'xyz'[i] if len(v) == 3 else i}]"] = x
    elif isinstance(v, (int, float)) and not isinstance(v, bool):
        out[path] = float(v)
    return out


def rows(app):
    """[(group, key, stored, effective)] for every canonical-governed numeric value."""
    out = []
    for group, stored_attr, eff_fn in _SOURCES:
        try:
            eff = _flat(getattr(app, eff_fn)())
        except Exception:
            continue
        stored = {}
        if stored_attr:
            st = getattr(app, stored_attr, {}) or {}
            if group.startswith("Master Vector"):
                stored = {f"[{k}]": float(st.get(k, 0.0) or 0.0) for k in "xyz"}
            else:
                stored = _flat(st)
        else:
            try:
                import copy
                geo = {"vector": dict(getattr(app, "master_vector_state", {}) or {}),
                       "wavetable": dict(getattr(app, "wavetable_projector_state", {}) or {}),
                       "ball": dict(getattr(app, "ball_synth_params", {}) or {}),
                       "cellular": dict(getattr(app, "cellular_synth_params", {}) or {})}
                stored = _flat(copy.deepcopy(geo))
            except Exception:
                stored = {}
        for k, e in eff.items():
            out.append((group, k, stored.get(k), e))
    return out


class CanonicalView(QDialog):
    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.setWindowTitle("Canonical values: what the engines change")
        self.resize(760, 560)
        lay = QVBoxLayout(self)
        self.lbl = QLabel(""); self.lbl.setWordWrap(True)
        lay.addWidget(self.lbl)
        self.tab = QTableWidget(0, 4)
        self.tab.setHorizontalHeaderLabels(["Group", "Value", "Shown (yours / default)", "Used by the render"])
        self.tab.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        lay.addWidget(self.tab, 1)
        row = QHBoxLayout()
        self.chk_changed = QCheckBox("Only values the engines change"); self.chk_changed.setChecked(True)
        self.chk_changed.toggled.connect(self.refresh)
        b = QPushButton("↻ Refresh"); b.clicked.connect(self.refresh)
        self.chk_live = QCheckBox("Live (1 s)"); self.chk_live.toggled.connect(lambda on: self._t.start() if on else self._t.stop())
        for w in (self.chk_changed, self.chk_live, b):
            row.addWidget(w)
        row.addStretch(1)
        lay.addLayout(row)
        self._t = QTimer(self); self._t.setInterval(1000); self._t.timeout.connect(self.refresh)
        self.refresh()

    def refresh(self):
        app = self.app
        try:
            active = sorted(app._active_engine_sources())
        except Exception:
            active = []
        data = rows(app)
        changed = [r for r in data if r[2] is None or abs(float(r[3]) - float(r[2])) > 1e-9]
        show = changed if self.chk_changed.isChecked() else data
        self.lbl.setText(
            f"Engines on: {', '.join(active) or 'none'}  ·  {len(changed)} of {len(data)} values differ from what the "
            "controls show. Canonical values apply at render time: an untouched control uses the canonical value, a "
            "control you moved blends 50 / 50. The controls keep showing your value, so they never jump.")
        self.tab.setRowCount(len(show))
        for i, (g, k, s, e) in enumerate(show):
            for c, v in enumerate((g, k, "—" if s is None else f"{s:.4f}", f"{e:.4f}")):
                self.tab.setItem(i, c, QTableWidgetItem(v))


def open_window(app):
    w = getattr(app, "_canonical_view_window", None)
    try:
        if w is not None:
            w.isVisible()
    except RuntimeError:
        w = None
    if w is None:
        w = CanonicalView(app)
        app._canonical_view_window = w
    w.refresh(); w.show(); w.raise_()
    return w
