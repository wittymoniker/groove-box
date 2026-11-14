"""synth_macros.py — GROOVEBOX_R32_SIMPLE_SYNTH_MACROS_20261109

Three macros per Edit Synth rack unit — TONE · MOTION · BODY — so a voice is shaped with
three moves instead of five sliders, while the five sliders stay the truth (macros write
them; moving a slider by hand leaves the macros where they are).

    TONE    0..1  Harmonic Frequency (log sweep 55 Hz → 3.5 kHz) + Harmonic Lattice tilt
    MOTION  0..1  Morph Rate (0.05 → 8×) + Feedback/Chaos blend
    BODY    0..1  Recursive Fold Depth (1 → 16) + Harmonic Lattice amount

Everything is a fixed, hardcoded mapping (no filters, no new DSP): the macros are a
precise, smaller set of inputs over the parameters the rack already renders.
"""
from __future__ import annotations

import math

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QSlider, QPushButton, QGroupBox

MACROS = (("TONE", "#7dd3fc", "Harmonic frequency + lattice tilt"),
          ("MOTION", "#f6c177", "Morph rate + feedback / chaos"),
          ("BODY", "#9ece6a", "Fold depth + lattice amount"))


def _set_row(row, value):
    """DoubleNumericSliderRow / QDoubleSpinBox compatible setter."""
    for name in ("setValue", "set_value"):
        fn = getattr(row, name, None)
        if callable(fn):
            try:
                fn(float(value))
                return True
            except Exception:
                continue
    return False


def _get_row(row, default=0.0):
    for name in ("value", "get_value"):
        fn = getattr(row, name, None)
        if callable(fn):
            try:
                return float(fn())
            except Exception:
                continue
    return default


def apply_macros(unit, tone, motion, body):
    """Write the three macro values (0..1) into the rack unit's five parameter rows."""
    tone, motion, body = (max(0.0, min(1.0, float(v))) for v in (tone, motion, body))
    # TONE: log sweep 55 → 3520 Hz
    _set_row(unit.param2, 55.0 * (2.0 ** (tone * 6.0)))
    # MOTION: morph rate log 0.05 → 8, chaos blend linear with a soft knee
    _set_row(unit.param1, 0.05 * (160.0 ** motion))
    _set_row(unit.param3, motion ** 1.4)
    # BODY: fold depth 1 → 16 and lattice 0 → 1 with tone tilting the lattice a little
    _set_row(unit.param4, 1.0 + 15.0 * body)
    _set_row(unit.param_fractal, max(0.0, min(1.0, 0.85 * body + 0.15 * tone)))


def read_macros(unit):
    """Best inverse of apply_macros from the current slider values (for display)."""
    f = max(55.0, min(3520.0, _get_row(unit.param2, 880.0)))
    tone = math.log2(f / 55.0) / 6.0
    r = max(0.05, min(8.0, _get_row(unit.param1, 1.2)))
    motion = math.log(r / 0.05) / math.log(160.0)
    d = max(1.0, min(16.0, _get_row(unit.param4, 4.0)))
    body = (d - 1.0) / 15.0
    return tuple(max(0.0, min(1.0, v)) for v in (tone, motion, body))


class MacroStrip(QGroupBox):
    def __init__(self, unit, parent=None):
        super().__init__("SIMPLE SYNTH · TONE / MOTION / BODY", parent)
        self.unit = unit
        self.setStyleSheet("QGroupBox{color:#c9d1d9;font-weight:700;border:1px solid #2e2e42;border-radius:6px;margin-top:8px;}"
                           "QGroupBox::title{subcontrol-origin:margin;left:8px;padding:0 4px;}")
        lay = QHBoxLayout(self)
        self.sliders = []
        t, m, b = read_macros(unit)
        for (name, color, tip), val in zip(MACROS, (t, m, b)):
            lab = QLabel(name); lab.setStyleSheet("color:%s;font-weight:900;border:none;" % color); lab.setToolTip(tip)
            sl = QSlider(Qt.Orientation.Horizontal); sl.setRange(0, 1000); sl.setValue(int(round(val * 1000)))
            sl.setToolTip(tip)
            sl.setStyleSheet("QSlider::groove:horizontal{background:#1d2a33;height:6px;border-radius:3px;}"
                             "QSlider::sub-page:horizontal{background:%s;height:6px;border-radius:3px;}"
                             "QSlider::handle:horizontal{background:%s;border:1px solid #f6f6f6;width:14px;margin:-5px 0;border-radius:7px;}" % (color, color))
            sl.valueChanged.connect(self._changed)
            lay.addWidget(lab); lay.addWidget(sl, 1)
            self.sliders.append(sl)
        b_sync = QPushButton("⟲ from sliders"); b_sync.setToolTip("Read the macro positions back from the five sliders")
        b_sync.clicked.connect(self.sync_from_unit)
        lay.addWidget(b_sync)

    def values(self):
        return tuple(s.value() / 1000.0 for s in self.sliders)

    def _changed(self, *_):
        apply_macros(self.unit, *self.values())

    def sync_from_unit(self):
        for sl, v in zip(self.sliders, read_macros(self.unit)):
            sl.blockSignals(True); sl.setValue(int(round(v * 1000))); sl.blockSignals(False)


def install(unit, layout=None):
    """Add the macro strip under a SynthRackUnitWidget (idempotent)."""
    if getattr(unit, "_macro_strip", None) is not None:
        return unit._macro_strip
    strip = MacroStrip(unit, unit)
    lay = layout or unit.layout()
    if lay is not None:
        lay.insertWidget(min(2, lay.count()), strip)
    unit._macro_strip = strip
    return strip
