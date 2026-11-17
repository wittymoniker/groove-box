"""Instrument Designer — fast macro authoring for per-instrument synth voices and sequences.

Templates are deterministic UI-level presets. Applying one writes ordinary instrument
parameter state and the existing synth-engine panel state; optional sequence fill writes
only the selected instrument's currently selected user sequence.
"""
from __future__ import annotations

import math

TEMPLATES = {
    "Percussion": {"waveform":"isn", "am_depth":0.08, "fm_depth":0.34, "pm_depth":0.12, "meum_depth":0.18,
                   "engine":{"unison":1,"detune":0.0,"drift":0.12,"sub":0.18,"oct":0.0,"fifth":0.0,"fold":0.32,"attack_ms":0.0,"release_ms":180.0,"velocity":0.22,"quality2x":False,"mode":"user"},
                   "steps":16,"pulses":4,"note":36,"pattern":"Euclidean"},
    "Pad": {"waveform":"isn", "am_depth":0.22, "fm_depth":0.08, "pm_depth":0.28, "meum_depth":0.36,
            "engine":{"unison":5,"detune":12.0,"drift":0.18,"sub":0.0,"oct":0.12,"fifth":0.18,"fold":0.08,"attack_ms":480.0,"release_ms":1600.0,"velocity":0.1,"quality2x":False,"mode":"user"},
            "steps":16,"pulses":3,"note":60,"pattern":"Sparse"},
    "Keys": {"waveform":"isn", "am_depth":0.04, "fm_depth":0.12, "pm_depth":0.06, "meum_depth":0.1,
             "engine":{"unison":2,"detune":3.0,"drift":0.03,"sub":0.0,"oct":0.0,"fifth":0.0,"fold":0.04,"attack_ms":8.0,"release_ms":260.0,"velocity":0.18,"quality2x":False,"mode":"user"},
             "steps":16,"pulses":8,"note":60,"pattern":"Euclidean"},
}


def macro_state(kind: str, tone: float, motion: float, body: float) -> dict:
    """Map TONE/MOTION/BODY into voice parameters with bounded, predictable ranges."""
    base = TEMPLATES.get(str(kind), TEMPLATES["Keys"])
    tone, motion, body = (max(0.0, min(1.0, float(x))) for x in (tone, motion, body))
    eng = dict(base["engine"])
    eng.update({"detune": round(eng["detune"] + 18.0 * tone, 3),
                "drift": round(min(1.0, eng["drift"] + 0.25 * motion), 4),
                "fold": round(min(1.0, eng["fold"] + 0.55 * body), 4),
                "attack_ms": round(max(0.0, eng["attack_ms"] * (0.35 + 1.65 * body)), 2),
                "release_ms": round(max(0.0, eng["release_ms"] * (0.35 + 1.65 * body)), 2)})
    return {"waveform":base["waveform"], "am_depth":base["am_depth"] * (0.5 + motion),
            "fm_depth":base["fm_depth"] * (0.5 + tone), "pm_depth":base["pm_depth"] * (0.5 + motion),
            "meum_depth":base["meum_depth"] * (0.5 + body), "engine":eng}


def fill_sequence(memory: dict, kind: str, steps=16, pulses=4, note=60, seed=1):
    """Fill only the supplied user-owned sequence memory; returns the same dict."""
    steps = max(1, min(512, int(steps))); pulses = max(0, min(steps, int(pulses)))
    memory = memory if isinstance(memory, dict) else {}
    mask = [int(((i + 1) * pulses) // steps != (i * pulses) // steps) for i in range(steps)] if pulses else [0] * steps
    if str(kind) == "Sparse":
        mask = [int(v and ((i + int(seed)) % 3 != 1)) for i, v in enumerate(mask)]
    elif str(kind) == "Arpeggio":
        mask = [1] * steps
    pitches = [max(0, min(127, int(note) + (0, 4, 7, 12)[(i + int(seed)) % 4])) for i in range(steps)]
    memory["steps"] = mask
    memory["gates"] = [1.0 if v else 0.0 for v in mask]
    memory["amplitudes"] = [0.82 if v else 0.0 for v in mask]
    memory["pitches"] = pitches
    memory["probabilities"] = [1.0] * steps
    memory["offsets"] = [0.0] * steps
    memory["pattern_length"] = steps
    memory["sequence_length_user_owned"] = True
    memory["instrument_designer"] = {"kind":str(kind),"seed":int(seed),"generated":True}
    return memory


def apply_to_host(host, kind, tone, motion, body, fill=False, steps=16, pulses=4, note=60):
    name = host._current_instrument_name() if hasattr(host, "_current_instrument_name") else host.instrument_selector_dropdown.currentText()
    state = macro_state(kind, tone, motion, body)
    params = getattr(host, "instrument_param_state", None)
    if not isinstance(params, dict): params = host.instrument_param_state = {}
    rec = dict(params.get(name, {}) or {})
    rec.update({k:v for k,v in state.items() if k != "engine"})
    params[name] = rec
    import synth_engine_panel as engine
    local = engine._state(host, "local", str(name)); local.update(state["engine"])
    engine.install(host)
    if fill:
        mem = host._current_sequence_mem(name)
        fill_sequence(mem, "Arpeggio" if kind == "Keys" else ("Sparse" if kind == "Pad" else "Euclidean"), steps, pulses, note,
                      int(getattr(host, "_seed_program_signature", lambda: 1)() or 1))
        host.instrument_sequencer_memory[name] = mem
        try:
            sid = host._current_sequence_index(name)
            host.instrument_sequence_banks.setdefault(name, {})[sid] = mem
            if hasattr(host, "_canonical_write_sequence_runtime"):
                host._canonical_write_sequence_runtime(name, sid)
        except Exception:
            pass
    try: host._on_live_source_changed()
    except Exception: pass
    try: host._schedule_ui_after_canonical_write("instrument-designer")
    except Exception: pass
    return name, state


def open_window(host):
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QFormLayout,QLabel,QComboBox,QSlider,
                                 QPushButton,QCheckBox,QSpinBox,QGroupBox)
    dlg = getattr(host, "_instrument_designer_dialog", None)
    if dlg is not None:
        try: dlg.show(); dlg.raise_(); dlg.activateWindow(); return dlg
        except RuntimeError: pass
    dlg = QDialog(host); dlg.setWindowTitle("Instrument Designer · Blueprint Macros"); dlg.resize(620,520)
    root = QVBoxLayout(dlg)
    intro = QLabel("Build percussion, pads, and keys from TONE · MOTION · BODY macros. Apply to the selected instrument; optionally fill its current sequence.")
    intro.setWordWrap(True); root.addWidget(intro)
    form = QFormLayout(); root.addLayout(form)
    kind = QComboBox(); kind.addItems(list(TEMPLATES)); form.addRow("Instrument family", kind)
    sliders = {}
    for key, title, default in (("tone","TONE · harmonic colour",0.45),("motion","MOTION · modulation",0.35),("body","BODY · envelope / weight",0.4)):
        row = QHBoxLayout(); lab = QLabel("0.45")
        sl = QSlider(Qt.Orientation.Horizontal); sl.setRange(0,1000); sl.setValue(int(default*1000))
        sl.valueChanged.connect(lambda v,l=lab: l.setText(f"{v/1000:.3f}"))
        row.addWidget(sl,1); row.addWidget(lab); form.addRow(title,row); sliders[key]=sl
    seq = QGroupBox("Sequence Blueprint · selected instrument / selected sequence")
    seqform = QFormLayout(seq)
    fill = QCheckBox("Fill current sequence when applying"); fill.setChecked(False)
    nsteps = QSpinBox(); nsteps.setRange(1,512); nsteps.setValue(16)
    pulses = QSpinBox(); pulses.setRange(0,512); pulses.setValue(4)
    note = QSpinBox(); note.setRange(0,127); note.setValue(60)
    seqform.addRow(fill); seqform.addRow("Steps",nsteps); seqform.addRow("Pulses",pulses); seqform.addRow("Base MIDI note",note); root.addWidget(seq)
    preview = QLabel(); preview.setWordWrap(True); root.addWidget(preview)
    def refresh(*_):
        st=macro_state(kind.currentText(),*(sliders[k].value()/1000 for k in ("tone","motion","body")))
        e=st["engine"]; preview.setText(f"Preview · unison {e['unison']} · detune {e['detune']:.1f} cents · fold {e['fold']:.2f} · attack {e['attack_ms']:.0f} ms · release {e['release_ms']:.0f} ms")
    kind.currentTextChanged.connect(refresh)
    for sl in sliders.values(): sl.valueChanged.connect(refresh)
    row=QHBoxLayout(); apply=QPushButton("Apply to Selected Instrument"); close=QPushButton("Close")
    apply.clicked.connect(lambda: (apply_to_host(host,kind.currentText(),*(sliders[k].value()/1000 for k in ("tone","motion","body")),fill.isChecked(),nsteps.value(),pulses.value(),note.value()), preview.setText(preview.text()+" · Applied")))
    close.clicked.connect(dlg.close); row.addWidget(apply); row.addWidget(close); root.addLayout(row)
    refresh(); host._instrument_designer_dialog=dlg; dlg.show(); dlg.raise_(); dlg.activateWindow(); return dlg
