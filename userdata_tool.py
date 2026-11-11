"""userdata_tool.py — GROOVEBOX_R32_USERDATA_TOOL_20261110

Bug: booted / loaded instruments could be recorded as *userdata* (in _canonical_field_touched)
without any user edit, which made them stop following the canonicals.
  prune_untouched(app): drops every touched mark whose current value equals the convolution
  default (nothing was really changed). Called after startup and project load.
  open_window(app): lists every userdata entry; select → highlight, Revert (back to canonical)
  or Keep; "Prune unchanged" runs the fix by hand.
"""
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QListWidget, QPushButton, QHBoxLayout, QLabel

_LANES = {"ball": "ball_synth_params", "cellular": "cellular_synth_params", "wavetable": "wavetable_projector_state",
          "vector": "master_vector_state"}


def _value(app, mark):
    lane, _, key = str(mark).partition(":")
    d = getattr(app, _LANES.get(lane, ""), None)
    return (d or {}).get(key) if isinstance(d, dict) else None


def _default(app, mark):
    lane, _, key = str(mark).partition(":")
    try:
        return app._geometric_convolution_defaults()[lane][key]
    except Exception:
        return None


def prune_untouched(app):
    t = set(getattr(app, "_canonical_field_touched", None) or set())
    keep, dropped = set(), []
    for m in t:
        v, d = _value(app, m), _default(app, m)
        try:
            same = v is not None and d is not None and abs(float(v) - float(d)) < 1e-9
        except Exception:
            same = v == d and v is not None
        (dropped.append(m) if same else keep.add(m))
    app._canonical_field_touched = keep
    return dropped


def revert(app, mark):
    lane, _, key = str(mark).partition(":")
    d, dv = getattr(app, _LANES.get(lane, ""), None), _default(app, mark)
    if isinstance(d, dict) and dv is not None:
        d[key] = dv
    t = set(getattr(app, "_canonical_field_touched", None) or set()); t.discard(mark)
    app._canonical_field_touched = t
    for fn in ("_geo_refresh_widgets", "_r32_geo_refresh_soon", "_refresh_canonical_ownership_labels", "_on_live_source_changed"):
        f = getattr(app, fn, None)
        if callable(f):
            try: f()
            except Exception: pass


def open_window(app):
    w = QWidget(app, Qt.WindowType.Window); w.setWindowTitle("👤 Userdata · keep or revert"); w.resize(520, 420)
    lay = QVBoxLayout(w); lay.addWidget(QLabel("Fields marked as YOUR data (not following the canonicals):"))
    lst = QListWidget(); lay.addWidget(lst, 1)

    def fill():
        lst.clear()
        for m in sorted(getattr(app, "_canonical_field_touched", None) or set()):
            lst.addItem("%s   = %r   (canonical %r)" % (m, _value(app, m), _default(app, m)))
    row = QHBoxLayout()
    for cap, fn in (("↺ Revert selected", lambda: [revert(app, i.text().split()[0]) for i in lst.selectedItems()]),
                    ("↺ Revert all", lambda: [revert(app, m) for m in list(getattr(app, "_canonical_field_touched", set()) or [])]),
                    ("🧹 Prune unchanged", lambda: prune_untouched(app))):
        b = QPushButton(cap); b.clicked.connect(lambda _=False, f=fn: (f(), fill())); row.addWidget(b)
    lay.addLayout(row); fill(); w.show(); app._userdata_window = w
    return w


def install(app):
    QTimer.singleShot(1500, lambda: prune_untouched(app))
