"""Non-destructive mathematical pattern generator for Mathematician's Groovebox.

Standalone helper: generates editable event data and exports JSON/CSV. It never
changes the active project, transport, audio device, or canonical identity.
"""
from __future__ import annotations
import csv, json, math
from pathlib import Path

ENGINE_VERSION = "1.2.0-playlist-writer"


def euclidean_pattern(steps: int, pulses: int, rotation: int = 0) -> list[int]:
    steps = max(1, min(512, int(steps)))
    pulses = max(0, min(steps, int(pulses)))
    rotation = int(rotation) % steps
    if pulses == 0:
        base = [0] * steps
    elif pulses == steps:
        base = [1] * steps
    else:
        # Evenly distribute pulses; deterministic and handles all step counts.
        base = [int(((i + 1) * pulses) // steps != (i * pulses) // steps) for i in range(steps)]
    return base[-rotation:] + base[:-rotation] if rotation else base


def fibonacci_pattern(steps: int, modulus: int = 12) -> list[int]:
    steps, modulus = max(1, min(512, int(steps))), max(1, min(127, int(modulus)))
    a, b, out = 0, 1, []
    for _ in range(steps):
        out.append(a % modulus)
        a, b = b, a + b
    return out


def generate_pattern(kind="Euclidean rhythm", steps=16, pulses=5, rotation=0,
                     density=0.5, seed=1, modulus=12, swing=0.0, bars=1,
                     bpm=120.0, note=36, velocity=100, phase_shift=0.0,
                     eq_gain_db=0.0, eq_frequency=1000.0, eq_q=0.707,
                     sidechain_depth=0.0, phase_mod_depth=0.0,
                     probability_min=0.55, probability_max=1.0,
                     eq_gain_spread_db=0.0, sidechain_spread=0.0):
    """Return versioned, editable events in beat-relative time."""
    steps = max(1, min(512, int(steps)))
    bars = max(1, min(64, int(bars)))
    bpm = max(20.0, min(300.0, float(bpm)))
    note = max(0, min(127, int(note)))
    velocity = max(1, min(127, int(velocity)))
    density = max(0.0, min(1.0, float(density)))
    swing = max(-0.49, min(0.49, float(swing)))
    # Seed only rotates deterministic mathematical structures; it is never used
    # as an unobservable random draw during composition generation.
    seed_phase = int(seed) % steps
    probability_min = max(0.0, min(1.0, float(probability_min)))
    probability_max = max(probability_min, min(1.0, float(probability_max)))
    eq_gain_spread_db = max(0.0, min(24.0, float(eq_gain_spread_db)))
    sidechain_spread = max(0.0, min(1.0, float(sidechain_spread)))
    if kind == "Euclidean rhythm":
        values = euclidean_pattern(steps, pulses, rotation)
        hits = [bool(x) for x in values]
    elif kind == "Fibonacci contour":
        values = fibonacci_pattern(steps, modulus)
        hits = [True] * steps
    elif kind == "Fractal / recursive":
        # A bounded deterministic recursive binary subdivision pattern.
        values = [0] * steps
        def fill(lo, hi, depth):
            if lo >= hi: return
            mid = (lo + hi) // 2
            values[mid] = min(127, 48 + depth * 12)
            if depth < 8 and hi - lo > 2:
                fill(lo, mid, depth + 1); fill(mid + 1, hi, depth + 1)
        fill(0, steps, 0)
        hits = [v > 0 for v in values]
    elif kind in ("Probability / seeded", "Seeded deterministic density"):
        # A seeded Euclidean mask gives density without random draws. Runtime
        # probability is reserved for canonical-only omit/continue decisions.
        values = euclidean_pattern(steps, int(round(density * steps)), seed_phase)
        hits = [bool(x) for x in values]
    elif kind == "Polyrhythm overlay":
        other = max(1, min(steps, int(pulses) or 3))
        values = [int(((i + 1) * max(1, int(pulses))) // steps != (i * max(1, int(pulses))) // steps) for i in range(steps)]
        hits = [bool(x or (i % other == 0)) for i, x in enumerate(values)]
    else:
        raise ValueError("Unknown pattern kind")
    events = []
    beats_per_bar = 4.0
    total_beats = bars * beats_per_bar
    for bar in range(bars):
        for i, hit in enumerate(hits):
            if not hit: continue
            if kind == "Fibonacci contour":
                pitch = max(0, min(127, 60 + int(values[i]) - modulus // 2))
                vel = velocity
            elif kind == "Fractal / recursive":
                pitch = max(0, min(127, note + (i % 12)))
                vel = max(1, min(127, int(values[i]) if values[i] else velocity))
            else:
                pitch, vel = note, velocity
            beat = bar * beats_per_bar + (i / steps) * beats_per_bar
            if i % 2: beat += swing * (4.0 / steps)
            events.append({"beat": round(beat, 6), "duration_beats": round(min(0.5, 4.0 / steps), 6),
                           "note": pitch, "velocity": vel, "bar": bar + 1, "step": i + 1})
    step_defaults = {
        "phase_shift": max(-1.0, min(1.0, float(phase_shift))),
        "eq_gain_db": max(-24.0, min(24.0, float(eq_gain_db))),
        "eq_frequency": max(20.0, min(20000.0, float(eq_frequency))),
        "eq_q": max(0.1, min(20.0, float(eq_q))),
        "sidechain_depth": max(-1.0, min(1.0, float(sidechain_depth))),
        "phase_mod_depth": max(0.0, min(1.0, float(phase_mod_depth))),
    }
    step_automation = {key: [value] * steps for key, value in step_defaults.items()}
    # Deterministic control curves only. The historical probability range is
    # retained in the document schema for backward compatibility, but it never
    # becomes a runtime hit chance: each step gate is certain (1.0 / 100%).
    # Deliberate omissions are represented by the explicit event mask above.
    _denom = max(1, steps - 1)
    _phase = (seed_phase / max(1, steps)) * math.tau
    step_automation["trigger_probability"] = [1.0] * steps
    step_automation["deterministic_trigger_profile"] = [
        round(probability_min + (probability_max - probability_min) * (0.5 + 0.5 * math.sin(math.tau * i / steps + _phase)), 6)
        for i in range(steps)
    ]
    step_automation["eq_gain_db"] = [
        round(max(-24.0, min(24.0, float(eq_gain_db) + float(eq_gain_spread_db) * math.sin(math.tau * i / steps + _phase))), 4)
        for i in range(steps)
    ]
    step_automation["sidechain_depth"] = [
        round(max(0.0, min(1.0, float(sidechain_depth) + float(sidechain_spread) * (0.5 + 0.5 * math.cos(math.tau * i / steps + _phase)))), 6)
        for i in range(steps)
    ]
    for event in events:
        event["step_controls"] = {key: values[event["step"] - 1] for key, values in step_automation.items()}
        event["probability"] = 1.0  # compatibility field; never a stochastic gate
        event["deterministic_trigger_profile"] = event["step_controls"]["deterministic_trigger_profile"]
    return {"format": "groovebox-math-pattern", "version": 2, "sequencer_schema_version": 2,
            "ownership": {"layer": "userdata", "protect_from_canonical_overwrite": True},
            "parameters": {"kind": kind, "steps": steps, "pulses": int(pulses), "rotation": int(rotation),
                           "density": density, "seed": int(seed), "modulus": int(modulus), "swing": swing,
                           "bars": bars, "bpm": bpm, "note": note, "velocity": velocity,
                           "probability_min": probability_min, "probability_max": probability_max,
                           "eq_gain_spread_db": eq_gain_spread_db, "sidechain_spread": sidechain_spread,
                           **step_defaults},
            "step_automation": step_automation,
            "events": events, "event_count": len(events), "duration_beats": total_beats}




def generate_playlist_data(rows=32, algorithm="Balanced progression", heuristic="Balanced", seed=1,
                           density=0.65, variation=0.35, start_offset=0.0, row_spacing=1.0,
                           velocity=100, coverage=1.0, sequence_start=1, sequence_count=8,
                           script_tag="", domain_tag="", synth_tag="", patch_tag="",
                           auto_target="", auto_amount=0.0, direction="Forward",
                           multi_seq=True, protect_userdata=True):
    """Build deterministic, editable canonical-compatible playlist row data.

    Algorithm and heuristic parameters shape row timing, velocity, coverage,
    sequence selection, and modular tags. No random draws or runtime probability
    are used; seed is a deterministic phase/index offset.
    """
    rows=max(1,min(512,int(rows))); seed=int(seed); sequence_start=max(1,min(128,int(sequence_start)))
    sequence_count=max(1,min(128,int(sequence_count))); density=max(0.0,min(1.0,float(density)))
    variation=max(0.0,min(1.0,float(variation))); row_spacing=max(0.01,min(128.0,float(row_spacing)))
    start_offset=float(start_offset); velocity=max(1,min(127,int(velocity))); coverage=max(0.0,min(1.0,float(coverage)))
    auto_amount=max(-1.0,min(1.0,float(auto_amount)))
    out=[]
    for i in range(rows):
        phase=((i+seed) % max(2,sequence_count*2))/max(1,sequence_count*2-1)
        if algorithm == "Ascending / descending":
            rank=(i % max(2,sequence_count*2-2)); rank=rank if rank < sequence_count else max(0,sequence_count*2-2-rank)
        elif algorithm == "Fibonacci walk":
            a,b=0,1
            for _ in range((i+seed)%24): a,b=b,(a+b)%sequence_count
            rank=a % sequence_count
        elif algorithm == "Euclidean cycle":
            rank=((i * max(1,round(density*sequence_count))) + seed) % sequence_count
        elif algorithm == "Fractal / recursive":
            rank=((i ^ (i >> 1) ^ seed) % sequence_count)
        else:
            rank=(i + seed) % sequence_count
        if heuristic == "Sparse / conservative":
            row_coverage=coverage * (1.0-variation*0.5) if (i+seed)%3 else coverage*(1.0-variation)
            row_velocity=round(velocity*(0.82+0.18*(1.0-phase)))
        elif heuristic == "Aggressive / dense":
            row_coverage=min(1.0,coverage+(variation*0.25*(0.5+0.5*math.sin(math.tau*phase))))
            row_velocity=min(127,round(velocity*(1.0+0.18*variation*(0.5+0.5*math.cos(math.tau*phase)))))
        elif heuristic == "Arc / crescendo":
            row_coverage=min(1.0,coverage*(1.0-variation+variation*(i/max(1,rows-1))))
            row_velocity=max(1,min(127,round(velocity*(1.0-variation+variation*(i/max(1,rows-1))))))
        else:
            row_coverage=max(0.0,min(1.0,coverage*(1.0+variation*0.25*math.sin(math.tau*phase))))
            row_velocity=max(1,min(127,round(velocity*(1.0-variation*0.15+variation*0.15*math.cos(math.tau*phase)))))
        row={
            "position": round(start_offset+i*row_spacing,6), "time_marker": round(start_offset+i*row_spacing,6),
            "operators_csv":"", "script_tag":str(script_tag), "domain_tag":str(domain_tag),
            "synth_tag":str(synth_tag), "patch_tag":str(patch_tag), "velocity":row_velocity,
            "effect_target":str(auto_target), "auto_amount":round(auto_amount*(0.5+0.5*math.sin(math.tau*phase)),6),
            "direction_vector":str(direction), "multi_seq":bool(multi_seq), "coverage":round(row_coverage,6),
            "blend_partner":"", "live_parametrics":"", "sequence_ref":sequence_start+rank,
            "sequence_attack":round(max(0.0,variation*phase),6), "sequence_release":round(max(0.0,variation*(1.0-phase)),6),
            "pitch_ratio":round(2.0**((rank % 12)/12.0),6),
            "provenance":{"writer":"mathematical_composition_lab","algorithm":algorithm,"heuristic":heuristic,
                          "seed":seed,"row_index":i,"deterministic":True,"layer":"userdata",
                          "protect_from_canonical_overwrite":bool(protect_userdata)},
            "sequence_mapping":"auto", "paint_tempo_mode":"row_loop",
        }
        out.append(row)
    return {"format":"groovebox-math-playlist","version":1,"ownership":{"layer":"userdata",
            "protect_from_canonical_overwrite":bool(protect_userdata)},"parameters":{
            "rows":rows,"algorithm":algorithm,"heuristic":heuristic,"seed":seed,"density":density,
            "variation":variation,"start_offset":start_offset,"row_spacing":row_spacing,
            "velocity":velocity,"coverage":coverage,"sequence_start":sequence_start,
            "sequence_count":sequence_count},"rows_data":out}

def apply_pattern_to_memory(pattern, memory):
    """Project a generated math pattern into a schema-v2 sequencer memory.

    This pure helper is used by the UI's explicit Apply action and is testable
    without a Qt session. All canonical STEP lanes repeat across bars; events
    set gate, velocity and relative pitch while probabilities remain per-step.
    """
    from sequencer_schema import normalize_sequence_memory, STEP_LANES
    params = pattern.get("parameters", {}) if isinstance(pattern, dict) else {}
    steps_per_bar = max(1, int(params.get("steps", 16) or 16))
    bars = max(1, int(params.get("bars", 1) or 1))
    length = max(1, min(512, steps_per_bar * bars))
    mem = normalize_sequence_memory(memory, target_length=length)
    mem["pattern_length"] = length
    mem["steps"] = [False] * length
    mem["gates"] = [True] * length
    mem["amplitudes"] = [1.0] * length
    mem["pitches"] = [1.0] * length
    mem["probabilities"] = [100] * length
    mem["offsets"] = [0.0] * length
    controls = mem.setdefault("step_controls", {})
    automation = pattern.get("step_automation", {}) if isinstance(pattern, dict) else {}
    automation = automation if isinstance(automation, dict) else {}
    for lane, default in STEP_LANES.items():
        base = automation.get(lane, [default] * steps_per_bar)
        if not isinstance(base, list): base = [base] * steps_per_bar
        lane_values = []
        for idx in range(length):
            value = base[idx % steps_per_bar] if (idx % steps_per_bar) < len(base) else default
            try: value = float(value)
            except (TypeError, ValueError): value = float(default)
            if not math.isfinite(value): value = float(default)
            lane_values.append(value)
        controls[lane] = lane_values
    for event in pattern.get("events", []) if isinstance(pattern, dict) else []:
        if not isinstance(event, dict): continue
        try: idx = (int(event.get("bar", 1)) - 1) * steps_per_bar + (int(event.get("step", 1)) - 1)
        except (TypeError, ValueError): continue
        if not 0 <= idx < length: continue
        mem["steps"][idx] = True
        try: mem["amplitudes"][idx] = max(0.0, min(1.0, float(event.get("velocity", 100)) / 127.0))
        except (TypeError, ValueError): pass
        try:
            base_note = float(params.get("note", 36)); event_note = float(event.get("note", base_note))
            mem["pitches"][idx] = max(0.25, min(4.0, 2.0 ** ((event_note - base_note) / 12.0)))
        except (TypeError, ValueError, OverflowError): pass
    mem["probabilities"] = [int(round(max(0.0, min(1.0, float(v))) * 100.0)) for v in controls.get("trigger_probability", [1.0] * length)]
    mem["user_owned"] = True
    mem["user_owned_pattern_source"] = "mathematical_composition_lab"
    mem["canonical_owner"] = "user:mathematical_composition_lab"
    return mem

def export_pattern(pattern, path):
    path = Path(path)
    if path.suffix.lower() == ".csv":
        fields = ["beat", "duration_beats", "note", "velocity", "bar", "step",
                  "phase_shift", "eq_gain_db", "eq_frequency", "eq_q",
                  "sidechain_depth", "phase_mod_depth", "trigger_probability"]
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            rows = []
            for event in pattern.get("events", []):
                row = {key: event.get(key, "") for key in fields[:6]}
                controls = event.get("step_controls", {})
                if isinstance(controls, dict):
                    row.update({key: controls.get(key, "") for key in fields[6:]})
                rows.append(row)
            writer.writerows(rows)
    else:
        path.write_text(json.dumps(pattern, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def open_math_composition_lab(parent=None):
    """Open a self-contained UI. Imports Qt only when invoked by the application."""
    from PyQt6.QtWidgets import (QDialog, QWidget, QScrollArea, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel,
        QComboBox, QSpinBox, QDoubleSpinBox, QPushButton, QPlainTextEdit, QFileDialog, QMessageBox, QCheckBox, QGroupBox, QLineEdit)
    dlg = QDialog(parent); dlg.setWindowTitle("Mathematical Composition Lab"); dlg.setMinimumSize(540, 420); dlg.resize(760, 680); dlg.setSizeGripEnabled(True)
    dlg_layout = QVBoxLayout(dlg)
    scroll = QScrollArea(dlg)
    scroll.setObjectName("mathCompositionScrollArea")
    scroll.setWidgetResizable(True)
    # The entire form, preview, and action row live in this viewport. Explicitly
    # allow the content widget to shrink to the viewport width on small screens,
    # leaving vertical overflow to the scroll bars rather than clipping controls.
    content_policy = __import__('PyQt6.QtWidgets', fromlist=['QSizePolicy']).QSizePolicy
    scroll.setMinimumSize(320, 260)
    scroll.setFrameShape(__import__('PyQt6.QtWidgets', fromlist=['QFrame']).QFrame.Shape.StyledPanel)
    scroll.setHorizontalScrollBarPolicy(__import__('PyQt6.QtCore', fromlist=['Qt']).Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    scroll.setVerticalScrollBarPolicy(__import__('PyQt6.QtCore', fromlist=['Qt']).Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    content = QWidget()
    content.setSizePolicy(content_policy.Policy.Expanding, content_policy.Policy.Preferred)
    content.setMinimumWidth(0)
    root = QVBoxLayout(content)
    root.setContentsMargins(10, 10, 10, 10)
    root.setSpacing(8)
    scroll.setWidget(content)
    dlg_layout.addWidget(scroll)
    intro = QLabel("Generate editable mathematical patterns. Preview/export are non-destructive. Commit stores the pattern in project userdata; protect it from Canonical Overwrite by default.")
    intro.setWordWrap(True); root.addWidget(intro)
    form = QFormLayout(); root.addLayout(form)
    kind = QComboBox(); kind.addItems(["Euclidean rhythm", "Polyrhythm overlay", "Fibonacci contour", "Fractal / recursive", "Seeded deterministic density"]); form.addRow("Pattern family", kind)
    kind.setToolTip("All structures are deterministic. The seed only rotates mathematical structure. Generated hits carry a certain 100% trigger gate; no stochastic/probability trial is introduced in playback.")
    def spin(lo, hi, value):
        w=QSpinBox(); w.setRange(lo,hi); w.setValue(value); return w
    steps=spin(1,128,16); pulses=spin(0,128,5); rotation=spin(-128,128,0); bars=spin(1,64,4); seed=spin(0,2147483647,1); modulus=spin(1,48,12); note=spin(0,127,36); velocity=spin(1,127,100)
    density=QDoubleSpinBox(); density.setRange(0,1); density.setSingleStep(.05); density.setValue(.5)
    swing=QDoubleSpinBox(); swing.setRange(-.49,.49); swing.setSingleStep(.05); swing.setValue(0)
    bpm=QDoubleSpinBox(); bpm.setRange(20,300); bpm.setValue(120)
    phase_shift=QDoubleSpinBox(); phase_shift.setRange(-1.0,1.0); phase_shift.setSingleStep(0.05); phase_shift.setValue(0.0)
    eq_gain=QDoubleSpinBox(); eq_gain.setRange(-24.0,24.0); eq_gain.setSingleStep(0.5); eq_gain.setValue(0.0)
    eq_freq=QDoubleSpinBox(); eq_freq.setRange(20.0,20000.0); eq_freq.setSingleStep(10.0); eq_freq.setValue(1000.0)
    eq_q=QDoubleSpinBox(); eq_q.setRange(0.1,20.0); eq_q.setSingleStep(0.1); eq_q.setValue(0.707)
    sidechain=QDoubleSpinBox(); sidechain.setRange(-1.0,1.0); sidechain.setSingleStep(0.05); sidechain.setValue(0.0)
    phase_mod=QDoubleSpinBox(); phase_mod.setRange(0.0,1.0); phase_mod.setSingleStep(0.05); phase_mod.setValue(0.0)
    probability_min=QDoubleSpinBox(); probability_min.setRange(0.0,1.0); probability_min.setSingleStep(0.05); probability_min.setValue(0.55)
    probability_max=QDoubleSpinBox(); probability_max.setRange(0.0,1.0); probability_max.setSingleStep(0.05); probability_max.setValue(1.0)
    eq_spread=QDoubleSpinBox(); eq_spread.setRange(0.0,24.0); eq_spread.setSingleStep(0.5); eq_spread.setValue(0.0)
    sidechain_spread=QDoubleSpinBox(); sidechain_spread.setRange(0.0,1.0); sidechain_spread.setSingleStep(0.05); sidechain_spread.setValue(0.0)
    for label,w in [("Steps per bar",steps),("Pulses / overlay cycle",pulses),("Rotation",rotation),("Bars",bars),("Deterministic phase seed",seed),("Pitch modulus",modulus),("Base MIDI note",note),("Velocity",velocity),("Probability density",density),("Swing",swing),("Tempo (BPM)",bpm),
                       ("STEP Phase Shift",phase_shift),("STEP EQ Gain (dB)",eq_gain),
                       ("STEP EQ Frequency (Hz)",eq_freq),("STEP EQ Q",eq_q),
                       ("STEP Sidechain Depth",sidechain),("STEP Phase Mod Depth",phase_mod),
                       ("Deterministic profile minimum (no chance gate)",probability_min),("Deterministic profile maximum (no chance gate)",probability_max),
                       ("Per-step EQ gain spread ± dB",eq_spread),("Per-step sidechain spread ±",sidechain_spread)]: form.addRow(label,w)
    protect_userdata=QCheckBox("Protect math-writer userdata from Canonical Overwrite")
    protect_userdata.setChecked(True)
    protect_userdata.setToolTip("ON: the committed pattern survives Canonical Overwrite. OFF: the next Canonical Overwrite may clear this math-writer userdata artifact.")
    # Playlist writer: shared Algorithm + Heuristic style controls.
    playlist_box=QGroupBox("Playlist Writer · Algorithm + Heuristic")
    playlist_layout=QVBoxLayout(playlist_box)
    playlist_intro=QLabel("Generate editable playlist rows across timing, sequence references, tags, automation, coverage, blend, and provenance. Preview/export is non-destructive; Apply writes only when explicitly requested.")
    playlist_intro.setWordWrap(True); playlist_layout.addWidget(playlist_intro)
    pf=QFormLayout(); playlist_layout.addLayout(pf)
    playlist_algorithm=QComboBox(); playlist_algorithm.addItems(["Balanced progression","Ascending / descending","Fibonacci walk","Euclidean cycle","Fractal / recursive"]); pf.addRow("Algorithm",playlist_algorithm)
    playlist_heuristic=QComboBox(); playlist_heuristic.addItems(["Balanced","Sparse / conservative","Aggressive / dense","Arc / crescendo"]); pf.addRow("Heuristic",playlist_heuristic)
    playlist_rows=spin(1,512,32); playlist_seed=spin(0,2147483647,1); sequence_start=spin(1,128,1); sequence_count=spin(1,128,8)
    playlist_density=QDoubleSpinBox(); playlist_density.setRange(0,1); playlist_density.setSingleStep(.05); playlist_density.setValue(.65)
    playlist_variation=QDoubleSpinBox(); playlist_variation.setRange(0,1); playlist_variation.setSingleStep(.05); playlist_variation.setValue(.35)
    playlist_start=QDoubleSpinBox(); playlist_start.setRange(-100000,100000); playlist_start.setDecimals(3); playlist_start.setValue(0)
    playlist_spacing=QDoubleSpinBox(); playlist_spacing.setRange(.01,128); playlist_spacing.setDecimals(3); playlist_spacing.setValue(1)
    playlist_velocity=spin(1,127,100)
    playlist_coverage=QDoubleSpinBox(); playlist_coverage.setRange(0,1); playlist_coverage.setSingleStep(.05); playlist_coverage.setValue(1)
    script_tag_edit=QLineEdit(); domain_tag_edit=QLineEdit(); synth_tag_edit=QLineEdit(); patch_tag_edit=QLineEdit()
    auto_target_edit=QLineEdit(); auto_target_edit.setPlaceholderText("e.g. Filter Cutoff, EQ Mid, Pitch")
    auto_amount_spin=QDoubleSpinBox(); auto_amount_spin.setRange(-1,1); auto_amount_spin.setSingleStep(.05); auto_amount_spin.setValue(0)
    direction_combo=QComboBox(); direction_combo.addItems(["Forward","Reverse","Ping-Pong","Drift"])
    multi_seq_check=QCheckBox("Allow multi-sequence row references"); multi_seq_check.setChecked(True)
    for label,w in [("Playlist rows",playlist_rows),("Deterministic seed / phase",playlist_seed),("Sequence start",sequence_start),("Sequence span",sequence_count),("Density bias",playlist_density),("Variation",playlist_variation),("Start offset",playlist_start),("Row spacing",playlist_spacing),("Base velocity",playlist_velocity),("Coverage",playlist_coverage),("Script tag",script_tag_edit),("Domain tag",domain_tag_edit),("Synth tag",synth_tag_edit),("Patch tag",patch_tag_edit),("Automation target",auto_target_edit),("Automation amount",auto_amount_spin),("Direction",direction_combo)]: pf.addRow(label,w)
    playlist_layout.addWidget(multi_seq_check)
    playlist_preview=QPlainTextEdit(); playlist_preview.setReadOnly(True); playlist_preview.setMinimumHeight(100); playlist_preview.setMaximumHeight(220); playlist_layout.addWidget(playlist_preview)
    playlist_state={"document":None}
    def build_playlist():
        try:
            doc=generate_playlist_data(rows=playlist_rows.value(),algorithm=playlist_algorithm.currentText(),heuristic=playlist_heuristic.currentText(),seed=playlist_seed.value(),density=playlist_density.value(),variation=playlist_variation.value(),start_offset=playlist_start.value(),row_spacing=playlist_spacing.value(),velocity=playlist_velocity.value(),coverage=playlist_coverage.value(),sequence_start=sequence_start.value(),sequence_count=sequence_count.value(),script_tag=script_tag_edit.text(),domain_tag=domain_tag_edit.text(),synth_tag=synth_tag_edit.text(),patch_tag=patch_tag_edit.text(),auto_target=auto_target_edit.text(),auto_amount=auto_amount_spin.value(),direction=direction_combo.currentText(),multi_seq=multi_seq_check.isChecked(),protect_userdata=protect_userdata.isChecked() if 'protect_userdata' in locals() else True)
            playlist_state["document"]=doc
            preview_rows=[f"{len(doc['rows_data'])} rows · {doc['parameters']['algorithm']} · {doc['parameters']['heuristic']} · deterministic", "Row  Time  Seq  Vel  Coverage  Pitch ratio  Tags"]
            for i,r in enumerate(doc['rows_data'][:80]): preview_rows.append(f"{i+1:>3}  {r['time_marker']:>7.3f}  Q{r['sequence_ref']:<3} {r['velocity']:>3}  {r['coverage']:.3f}     {r['pitch_ratio']:.3f}    {r['script_tag']}/{r['domain_tag']}/{r['synth_tag']}/{r['patch_tag']}")
            if len(doc['rows_data'])>80: preview_rows.append(f"… {len(doc['rows_data'])-80} more rows in export")
            playlist_preview.setPlainText("\n".join(preview_rows))
        except Exception as exc: QMessageBox.warning(dlg,"Playlist generation error",str(exc))
    def export_playlist():
        if playlist_state["document"] is None: build_playlist()
        doc=playlist_state["document"]
        if not doc: return
        path,_=QFileDialog.getSaveFileName(dlg,"Export generated playlist","groovebox-playlist.json","Playlist JSON (*.json);;Playlist CSV (*.csv)")
        if not path:return
        try:
            if path.lower().endswith('.csv'):
                keys=list(doc['rows_data'][0].keys()) if doc['rows_data'] else []
                with open(path,'w',newline='',encoding='utf-8') as f:
                    writer=csv.DictWriter(f,fieldnames=keys); writer.writeheader()
                    for row in doc['rows_data']:
                        writer.writerow({k:(json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v) for k,v in row.items()})
            else:
                Path(path).write_text(json.dumps(doc,indent=2,ensure_ascii=False),encoding='utf-8')
            QMessageBox.information(dlg,"Playlist exported",f"Exported {len(doc['rows_data'])} editable playlist rows to:\n{path}")
        except Exception as exc: QMessageBox.critical(dlg,"Playlist export failed",str(exc))
    def apply_playlist():
        if playlist_state["document"] is None: build_playlist()
        doc=playlist_state["document"]; owner=parent
        if not doc or owner is None or not hasattr(owner,"master_playlist_data"):
            QMessageBox.warning(dlg,"Apply playlist","No compatible Groovebox playlist host is available. Export JSON/CSV instead."); return
        try:
            mode=QMessageBox.question(dlg,"Apply playlist","Replace the current playlist? Choose No to append generated rows.",QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No|QMessageBox.StandardButton.Cancel,QMessageBox.StandardButton.Cancel)
            if mode==QMessageBox.StandardButton.Cancel:return
            new_rows=json.loads(json.dumps(doc['rows_data']))
            if mode==QMessageBox.StandardButton.Yes: owner.master_playlist_data=new_rows
            else: owner.master_playlist_data=list(owner.master_playlist_data or [])+new_rows
            owner.math_playlist_userdata={"format":doc["format"],"version":doc["version"],"parameters":doc["parameters"],"ownership":doc["ownership"]}
            protection=getattr(owner,"userdata_protection",None)
            if not isinstance(protection,dict): protection={"schema":1}
            protection["playlist_math_writer"]={"layer":"userdata","protect_from_canonical_overwrite":bool(protect_userdata.isChecked())}
            owner.userdata_protection=protection
            try:
                if hasattr(owner,"_sync_project_state"): owner._sync_project_state()
                if hasattr(owner,"_push_restored_playlist_to_table"): owner._push_restored_playlist_to_table()
                if hasattr(owner,"_sync_playlist_paint_table_from_memory"): owner._sync_playlist_paint_table_from_memory()
                if hasattr(owner,"_refresh_canonical_fingerprint"): owner._refresh_canonical_fingerprint()
            except Exception: pass
            QMessageBox.information(dlg,"Playlist applied",f"Applied {len(new_rows)} rows ({'replaced' if mode==QMessageBox.StandardButton.Yes else 'appended'}). Save the project to persist the arrangement.")
        except Exception as exc: QMessageBox.critical(dlg,"Playlist apply failed",str(exc))
    playlist_actions=QHBoxLayout()
    make_playlist=QPushButton("Generate Playlist"); make_playlist.clicked.connect(build_playlist)
    export_playlist_btn=QPushButton("Export Playlist JSON / CSV"); export_playlist_btn.clicked.connect(export_playlist)
    apply_playlist_btn=QPushButton("Apply Playlist to Project…"); apply_playlist_btn.clicked.connect(apply_playlist)
    playlist_actions.addWidget(make_playlist); playlist_actions.addWidget(export_playlist_btn); playlist_actions.addWidget(apply_playlist_btn)
    playlist_layout.addLayout(playlist_actions)
    root.addWidget(playlist_box)
    root.addWidget(protect_userdata)
    preview=QPlainTextEdit(); preview.setReadOnly(True); preview.setMinimumHeight(140); preview.setMaximumHeight(280); preview.setSizePolicy(__import__('PyQt6.QtWidgets', fromlist=['QSizePolicy']).QSizePolicy.Policy.Expanding, __import__('PyQt6.QtWidgets', fromlist=['QSizePolicy']).QSizePolicy.Policy.Preferred); root.addWidget(preview)
    state={"pattern":None}
    def build():
        try:
            p=generate_pattern(kind.currentText(),steps.value(),pulses.value(),rotation.value(),density.value(),seed.value(),modulus.value(),swing.value(),bars.value(),bpm.value(),note.value(),velocity.value(),phase_shift.value(),eq_gain.value(),eq_freq.value(),eq_q.value(),sidechain.value(),phase_mod.value(),probability_min.value(),probability_max.value(),eq_spread.value(),sidechain_spread.value())
            state["pattern"]=p
            rows=[f"{p['parameters']['kind']} · {p['event_count']} events · {p['duration_beats']:.1f} beats · {p['parameters']['bpm']:.1f} BPM", ""]
            rows.append("Bar  Step  Beat     MIDI  Vel  Certain gate / deterministic profile")
            rows.extend(f"{e['bar']:>3}  {e['step']:>4}  {e['beat']:>7.3f}  {e['note']:>4}  {e['velocity']:>3}  {e.get('probability',1.0):.2f} / {e.get('deterministic_trigger_profile',1.0):.2f}" for e in p['events'][:400])
            if len(p['events'])>400: rows.append(f"… {len(p['events'])-400} more events (included in export)")
            preview.setPlainText("\n".join(rows))
        except Exception as exc: QMessageBox.warning(dlg,"Pattern error",str(exc))
    def save():
        if state["pattern"] is None: build()
        if state["pattern"] is None: return
        path,_=QFileDialog.getSaveFileName(dlg,"Export mathematical pattern","groovebox-pattern.json","Pattern JSON (*.json);;Event CSV (*.csv)")
        if not path: return
        try:
            state["pattern"]["ownership"]={"layer":"userdata","protect_from_canonical_overwrite":bool(protect_userdata.isChecked())}
            export_pattern(state["pattern"],path); QMessageBox.information(dlg,"Pattern exported",f"Saved editable event data to:\n{path}")
        except Exception as exc: QMessageBox.critical(dlg,"Export failed",str(exc))
    def apply_to_selected_sequence():
        if state["pattern"] is None: build()
        if state["pattern"] is None: return
        owner=parent
        if owner is None or not hasattr(owner, "_current_sequence_mem"):
            QMessageBox.warning(dlg, "Apply pattern", "No active Groovebox sequencer is available. Export JSON/CSV instead.")
            return
        try:
            pattern=json.loads(json.dumps(state["pattern"]))
            params=pattern.get("parameters", {})
            length=max(1,min(512,int(params.get("steps",16) or 16)*max(1,int(params.get("bars",1) or 1))))
            inst=owner._current_instrument_name() if hasattr(owner,"_current_instrument_name") else owner.instrument_selector_dropdown.currentText()
            sid=owner._current_sequence_index(inst) if hasattr(owner,"_current_sequence_index") else 1
            mem=apply_pattern_to_memory(pattern, owner._current_sequence_mem(inst))
            bank=(getattr(owner,"instrument_sequence_banks",{}) or {}).setdefault(inst,{})
            bank[sid]=mem
            owner.instrument_sequencer_memory[inst]=mem
            if hasattr(owner,"_canonical_write_sequence_runtime"): owner._canonical_write_sequence_runtime(inst,sid)
            if hasattr(owner,"_refresh_canonical_fingerprint"): owner._refresh_canonical_fingerprint()
            if hasattr(owner,"reload_active_instrument_sequencer_ui"): owner.reload_active_instrument_sequencer_ui()
            if hasattr(owner,"_sync_project_state"): owner._sync_project_state()
            QMessageBox.information(dlg,"Pattern applied",f"Applied {pattern.get('event_count',0)} event(s) to {inst} · Sequence {sid} · {length} steps. Canonical runtime and project state were updated; audio/video/game renders use the shared canonical render.")
        except Exception as exc:
            QMessageBox.critical(dlg,"Apply failed",str(exc))

    def commit_userdata():
        if state["pattern"] is None: build()
        if state["pattern"] is None: return
        owner=parent
        if owner is None or not hasattr(owner,"_project_snapshot"):
            QMessageBox.warning(dlg,"Commit userdata","No Groovebox project host is available. Export JSON/CSV instead.")
            return
        pattern=json.loads(json.dumps(state["pattern"]))
        pattern["sequencer_schema_version"] = 2
        pattern["ownership"]={"layer":"userdata","protect_from_canonical_overwrite":bool(protect_userdata.isChecked())}
        owner.math_writer_userdata=pattern
        current=getattr(owner,"userdata_protection",None)
        if not isinstance(current,dict): current={"schema":1}
        current["playlist_math_writer"]={"layer":"userdata","protect_from_canonical_overwrite":bool(protect_userdata.isChecked())}
        owner.userdata_protection=current
        try:
            # A separate userdata branch avoids collision with canonical engine
            # projections; the normal project snapshot now persists this field.
            if hasattr(owner,"_sync_project_state"): owner._sync_project_state()
        except Exception: pass
        QMessageBox.information(dlg,"Math Writer userdata",f"Committed {pattern.get('event_count',0)} event(s) to project userdata. Canonical Overwrite protection: {'ON' if protect_userdata.isChecked() else 'OFF'}.")
    row=QHBoxLayout(); gen=QPushButton("Generate / Refresh"); gen.clicked.connect(build); out=QPushButton("Export JSON / CSV"); out.clicked.connect(save); commit=QPushButton("Commit to Project Userdata"); commit.setToolTip("Store this pattern separately from canonical engine state and save its overwrite-protection choice."); commit.clicked.connect(commit_userdata); close=QPushButton("Close"); close.clicked.connect(dlg.close)
    apply_btn=QPushButton("Apply to Selected Sequence"); apply_btn.setToolTip("Write steps, amp, pitch, phase shift, EQ, sidechain and probability lanes into the selected canonical sequence and project state."); apply_btn.clicked.connect(apply_to_selected_sequence)
    row.addWidget(gen); row.addWidget(out); row.addWidget(apply_btn); row.addWidget(commit); row.addStretch(1); row.addWidget(close); root.addLayout(row)
    # Every control, including action buttons and the long preview, lives inside
    # the same scroll viewport so smaller displays can reach the bottom actions.
    build(); dlg.exec()


# GROOVEBOX_R23R_NONMODAL_DIALOGS_20261103: no dialog may block other windows.
try:
    import nonmodal_dialogs as _gb_nonmodal
    _gb_nonmodal.install()
except Exception:
    pass
