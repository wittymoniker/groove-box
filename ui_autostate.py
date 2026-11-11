"""ui_autostate.py — GROOVEBOX_R32_UI_AUTOSTATE_20261110

Save / Load now keeps EVERY workspace control, not only the ~70 named in _collect_project_ui_state.

A save-and-reload round trip that changed all 310 main-window controls found 234 coming back at
their defaults (deck panels, flow rows, synth lanes, MD clone rack, context equations, …) because
the project kept an explicit list of controls written years ago.  This captures every input
control of the main window (spin boxes, sliders, dials, check boxes, radio buttons, combo boxes,
line edits) keyed by a stable path in the widget tree, and restores it on load through the
control's own handlers, exactly as if the user had set it.

Not persisted (derived, device or transient state):
  * hardware volume (the device's own level)            * the MD control rack (canonical outputs)
  * the windows-bar / workspace find field              * read-only or disabled controls
  * any widget with property grooveboxNoPersist = True
Order: the instrument selector is restored first, so per-instrument panels land on the right one.
"""
from __future__ import annotations

EXCLUDE = ("HardwareVolumeWidget", "mainDimensionalControlRack", "grooveboxWorkstationTools", "qt_spinbox_lineedit",
           "_OTNumericOverlay", "AuthorNumeric", "OTNumberGlyph")     # Math Symbols overlay internals
FIRST = ("instrument_selector_dropdown",)


def _kinds():
    from PyQt6.QtWidgets import (QSpinBox, QDoubleSpinBox, QComboBox, QCheckBox, QRadioButton, QSlider, QDial,
                                 QLineEdit)
    return (QSpinBox, QDoubleSpinBox, QComboBox, QCheckBox, QRadioButton, QSlider, QDial, QLineEdit)


def _path(w, root):
    parts = []
    while w is not None and w is not root:
        p = w.parentWidget()
        name = w.objectName() or type(w).__name__
        if p is not None:
            t = type(w)
            sibs = [c for c in p.children() if isinstance(c, t)]      # direct children only: O(children), same order
            if w in sibs:
                name += "[%d]" % sibs.index(w)
        parts.append(name); w = p
    return "/".join(reversed(parts))


def _controls(app):
    from PyQt6.QtWidgets import QWidget, QLineEdit, QAbstractSpinBox, QComboBox
    K = _kinds(); out = {}
    for w in app.findChildren(QWidget):
        if not isinstance(w, K):
            continue
        try:
            if w.window() is not app or not w.isEnabled() or w.property("grooveboxNoPersist"):
                continue
            if isinstance(w, QLineEdit) and (w.isReadOnly() or isinstance(w.parentWidget(), (QAbstractSpinBox, QComboBox))):
                continue
            p = _path(w, app)
            if any(x in p for x in EXCLUDE):
                continue
            out[p] = w
        except RuntimeError:
            continue
    return out


def value(w):
    from PyQt6.QtWidgets import QComboBox, QCheckBox, QRadioButton, QLineEdit
    if isinstance(w, QComboBox):
        return {"t": w.currentText(), "i": w.currentIndex()}
    if isinstance(w, (QCheckBox, QRadioButton)):
        return bool(w.isChecked())
    if isinstance(w, QLineEdit):
        return w.text()
    return w.value()


def collect(app):
    try:
        return {"v": 1, "controls": {p: value(w) for p, w in _controls(app).items()}}
    except Exception:
        return {}


def _set(w, v):
    from PyQt6.QtWidgets import QComboBox, QCheckBox, QRadioButton, QLineEdit, QSpinBox, QSlider, QDial
    if isinstance(w, QComboBox) and isinstance(v, dict):
        i = w.findText(str(v.get("t", "")))
        if i < 0 and 0 <= int(v.get("i", -1)) < w.count():
            i = int(v["i"])
        if i >= 0 and i != w.currentIndex():
            w.setCurrentIndex(i); return True
        if i < 0 and w.isEditable() and v.get("t"):
            w.setEditText(str(v["t"])); return True
        return False
    if isinstance(w, (QCheckBox, QRadioButton)) and isinstance(v, bool):
        if w.isChecked() != v:
            w.setChecked(v); return True
        return False
    if isinstance(w, QLineEdit) and isinstance(v, str):
        if w.text() != v:
            w.setText(v)
            try:
                w.editingFinished.emit()
            except Exception:
                pass
            return True
        return False
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        if isinstance(w, (QSpinBox, QSlider, QDial)):
            v = int(round(v))
        if w.value() != v and w.minimum() <= v <= w.maximum():
            w.setValue(v); return True
    return False


def restore(app, state, qa=None):
    """Set every saved control that exists and differs. Returns (restored, skipped)."""
    if not isinstance(state, dict) or not isinstance(state.get("controls"), dict):
        return 0, 0
    saved = state["controls"]
    done = skipped = 0
    for name in FIRST:                       # the instrument selector first (per-instrument panels follow it)
        w = getattr(app, name, None)
        if w is not None:
            try:
                p = _path(w, app)
                if p in saved and _set(w, saved[p]):
                    done += 1
                    if qa is not None:
                        qa.processEvents()
            except Exception:
                pass
    live = _controls(app)
    from PyQt6.QtWidgets import QComboBox
    # selectors first (scope / mode combos re-load the panels whose other fields depend on them)
    order = sorted(saved.items(), key=lambda kv: 0 if isinstance(live.get(kv[0]), QComboBox) else 1)
    for p, v in order:
        w = live.get(p)
        if w is None:
            skipped += 1; continue
        try:
            if _set(w, v):
                done += 1
        except Exception:
            skipped += 1
    return done, skipped
