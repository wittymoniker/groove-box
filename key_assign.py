"""GROOVEBOX_R23R_KEY_ASSIGN_20261103 — Keyboard Assign: one binding per key.

Each key of the key chart (Z row … number row) can stay on [Selected Instrument]
(the original chart behaviour) or be hardened to:

  instrument · sequence # (0 = a single note; N = play that sequence of the
  instrument as a one-row phrase) · Hz (0 = the chart degree of the instrument's
  base) · pitch shift in semitones (432 Hz-unit 2^(n/12)) · volume % · phase
  shift ° · note length.

Bound keys are rendered once into RAM (a background thread renders every bound
key after an edit; a key whose instrument settings changed is re-rendered on its
next press) so live playing is a buffer hand-off, not a synthesis.

Bindings are saved with the project ("key_bindings").
"""
from __future__ import annotations

import hashlib
import json
import math
import random
import threading

import numpy as np

KEY_SR = 44100
KEY_GAIN = 0.28            # the Trigger Note / key chart voice gain (NO_FADE_NO_LIMIT_20261102)
SELECTED = ""              # "" = [Selected Instrument]


def default_binding():
    return {"inst": SELECTED, "seq": 0, "hz": 0.0, "pitch": 0.0, "vol": 100, "phase": 0, "dur": 0.35,
            "pkp": 0.5, "pan": 0, "octave": 0}


def is_default(b):
    d = default_binding()
    return all(b.get(k, d[k]) == d[k] for k in d)


def _sig(host, inst, b, degree):
    st = (getattr(host, "instrument_param_state", {}) or {}).get(inst, {})
    rec = (getattr(host, "instrument_media_samples", {}) or {}).get(inst)
    try:
        base = float(host.spin_base_frequency.value())
    except Exception:
        base = 432.0
    try:
        bpm = float(host.spin_bpm.value())
    except Exception:
        bpm = 120.0
    seq_part = None
    if int(b.get("seq", 0) or 0) > 0:
        seq_part = _sequence_mem(host, inst, int(b["seq"]))
    blob = json.dumps([inst, b, degree, base, bpm, int(getattr(host, "_keychart_steps", 12)), st, seq_part,
                       id(rec) if rec is not None else 0], sort_keys=True, default=str)
    return hashlib.blake2b(blob.encode("utf-8", "replace"), digest_size=12).hexdigest()


def _sequence_mem(host, inst, seq_no):
    """Sequence #seq_no of an instrument: its bank entry, or (#1 without banks) the live pattern."""
    banks = (getattr(host, "instrument_sequence_banks", {}) or {}).get(inst) or {}
    mem = None
    if isinstance(banks, dict):
        mem = banks.get(seq_no) or banks.get(str(seq_no))
    if mem is None and seq_no == 1:
        mem = (getattr(host, "instrument_sequencer_memory", {}) or {}).get(inst)
    return mem if isinstance(mem, dict) else None


def _voice(host, inst, hz, n, phase_rad):
    t = np.arange(int(n), dtype=np.float64) / KEY_SR
    v = np.asarray(host._audition_voice(inst, float(hz), t, KEY_SR, phase0=float(phase_rad)), dtype=np.float64)
    rec = (getattr(host, "instrument_media_samples", {}) or {}).get(inst)
    if isinstance(rec, dict) and rec.get("waveform") is not None:
        try:
            raw = host._sample_native_layer(np.asarray(rec["waveform"], dtype=np.float32),
                                            int(rec.get("sample_rate", KEY_SR) or KEY_SR), t)
            v = 0.5 * v + 0.5 * np.asarray(raw, dtype=np.float64)
        except Exception:
            pass
    return np.nan_to_num(v, nan=0.0, posinf=0.0, neginf=0.0)


def render_key(host, ch, degree, b, inst):
    """The key's sound (float32 @ KEY_SR). No fade, no limiter."""
    shift = 2.0 ** (float(b.get("pitch", 0.0) or 0.0) / 12.0)
    vol = max(0.0, float(b.get("vol", 100) or 0) / 100.0)
    ph = math.radians(float(b.get("phase", 0) or 0))
    base = float(host._keychart_base_hz(inst))
    seq_no = int(b.get("seq", 0) or 0)
    if seq_no > 0:
        mem = _sequence_mem(host, inst, seq_no)
        if mem:
            steps = list(mem.get("steps") or [])
            pits = list(mem.get("pitches") or [])
            amps = list(mem.get("amplitudes") or [])
            pat = max(1, int(mem.get("pattern_length", len(steps) or 1) or 1))
            try:
                bpm = float(host.spin_bpm.value())
            except Exception:
                bpm = 120.0
            beats = 4.0
            for attr in ("spin_row_beats", "spin_playlist_beats"):
                w = getattr(host, attr, None)
                if w is not None:
                    try:
                        beats = float(w.value()); break
                    except Exception:
                        pass
            row = (60.0 / bpm * beats) if bpm > 0 else 0.0     # tempo 0 = no time passes: empty phrase
            sd = row / pat
            n_row = int(round(row * KEY_SR))
            out = np.zeros(n_row, dtype=np.float64)
            hz0 = (float(b["hz"]) if float(b.get("hz", 0) or 0) > 0 else base * host._keychart_ratio(degree)) * shift
            for s in range(pat):
                if not (s < len(steps) and steps[s]):
                    continue
                i0 = int(s * sd * KEY_SR)
                m = min(n_row - i0, int(sd * KEY_SR))
                if m <= 0:
                    continue
                hz = min(20000.0, hz0 * (float(pits[s]) if s < len(pits) else 1.0))
                a = float(amps[s]) if s < len(amps) else 1.0
                out[i0:i0 + m] += a * _voice(host, inst, hz, m, ph)
            return (KEY_GAIN * vol * out).astype(np.float32)
    hz = float(b["hz"]) if float(b.get("hz", 0) or 0) > 0 else base * host._keychart_ratio(degree)
    # Per-key octave
    octv = int(b.get("octave", 0) or 0)
    if octv:
        hz *= 2.0 ** octv
    hz = min(20000.0, hz * shift)
    n = max(64, int(float(b.get("dur", 0.35) or 0.35) * KEY_SR))
    voice = _voice(host, inst, hz, n, ph)
    # PKP envelope: 0 = pluck, 0.5 = held, 1 = swell
    try:
        pkp = float(b.get("pkp", 0.5) or 0.5)
        t = np.arange(n, dtype=np.float64) / KEY_SR
        dur = n / float(KEY_SR)
        if hasattr(host, "_pkp_boost_envelope"):
            env = host._pkp_boost_envelope(t, dur, pkp)
            voice = voice * np.asarray(env, dtype=np.float64)
    except Exception:
        pass
    # Pan: -100..100 → simple stereo gain (mono buffer gets a constant scale)
    try:
        pan = float(b.get("pan", 0) or 0) / 100.0
        # Keep mono; pan is stored for hosts that mix stereo later
        voice = voice * (1.0 - 0.3 * abs(pan))
    except Exception:
        pass
    return (KEY_GAIN * vol * voice).astype(np.float32)


class KeyBank:
    """Bindings + the RAM cache of rendered keys."""

    def __init__(self, host):
        self.host = host
        self.bindings = {}
        self.cache = {}            # ch -> (signature, buffer)
        self.lock = threading.Lock()
        self._job = None

    def binding(self, ch):
        b = default_binding()
        b.update(self.bindings.get(ch, {}) or {})
        return b

    def set(self, ch, b):
        if is_default(b):
            self.bindings.pop(ch, None)
        else:
            self.bindings[ch] = dict(b)
        with self.lock:
            self.cache.pop(ch, None)

    def inst_for(self, b):
        inst = b.get("inst") or ""
        if not inst:
            try:
                inst = str(self.host.instrument_selector_dropdown.currentText())
            except Exception:
                inst = ""
        return inst

    def buffer(self, ch, degree, binding_override=None):
        """Cached buffer for a bound key; optional recorded binding supports exact Jam pattern replay."""
        if binding_override is None and ch not in self.bindings:
            return None
        b = dict(binding_override) if isinstance(binding_override, dict) else self.binding(ch)
        inst = self.inst_for(b)
        if not inst:
            return None
        sig = _sig(self.host, inst, b, degree)
        with self.lock:
            hit = self.cache.get(ch)
        if hit and hit[0] == sig:
            return hit[1]
        buf = render_key(self.host, ch, degree, b, inst)
        with self.lock:
            self.cache[ch] = (sig, buf)
        return buf

    def prerender(self, order, done=None):
        """Render every bound key into RAM on a worker thread."""
        keys = [(ch, order.find(ch)) for ch in list(self.bindings) if order.find(ch) >= 0]

        def work():
            n = 0
            for ch, deg in keys:
                try:
                    self.buffer(ch, deg); n += 1
                except Exception:
                    pass
            if done is not None:
                done(n)
        t = threading.Thread(target=work, name="key-prerender", daemon=True)
        t.start()
        self._job = t
        return t

    def ram_bytes(self):
        with self.lock:
            return sum(int(v[1].nbytes) for v in self.cache.values())

    def randomize(self, order, instruments, *, inst=True, pitch=True, vol=True, phase=True, seq=False, seed=None):
        rng = random.Random(seed)
        for ch in order:
            b = self.binding(ch)
            if inst and instruments:
                b["inst"] = rng.choice(instruments)
            if pitch:
                b["pitch"] = float(rng.randint(-12, 12))
            if vol:
                b["vol"] = int(rng.randint(60, 120))
            if phase:
                b["phase"] = int(rng.choice((0, 45, 90, 135, 180, 225, 270, 315)))
            if seq:
                bank = (getattr(self.host, "instrument_sequence_banks", {}) or {}).get(b["inst"] or "") or {}
                ids = sorted(int(k) for k in bank.keys() if str(k).isdigit()) if isinstance(bank, dict) else []
                b["seq"] = rng.choice([0] + ids) if ids else 0
            self.set(ch, b)

    def to_json(self):
        return {ch: dict(b) for ch, b in self.bindings.items()}

    def load_json(self, data):
        self.bindings = {}
        with self.lock:
            self.cache.clear()
        for ch, b in dict(data or {}).items():
            if isinstance(b, dict) and len(str(ch)) == 1:
                d = default_binding(); d.update({k: b[k] for k in d if k in b})
                self.set(str(ch), d)


def open_key_assign(host):
    from PyQt6.QtCore import Qt, QTimer
    from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QComboBox, QSpinBox,
                                 QDoubleSpinBox, QPushButton, QLabel, QCheckBox, QHeaderView)
    import groovebox as gb
    order = gb.KEYCHART_ORDER
    bank = host._key_bank()
    dlg = getattr(host, "_key_assign_dialog", None)
    try:
        if dlg is not None:
            dlg.isVisible()
    except RuntimeError:
        dlg = None
    if dlg is not None:
        dlg._reload(); dlg.show(); dlg.raise_(); dlg.activateWindow()
        return dlg
    dlg = QDialog(host)
    dlg.setWindowTitle("⌨ Keyboard Assign — a sound per key")
    dlg.setModal(False)
    dlg.resize(1180, 640)
    lay = QVBoxLayout(dlg)
    head = QLabel("Each key plays [Selected Instrument] on the key chart unless you harden it here. "
                  "Sequence # > 0 plays that sequence of the instrument as a phrase. Hz 0 = the chart degree. "
                  "Bound keys are pre-rendered into RAM so they fire instantly.")
    head.setWordWrap(True)
    lay.addWidget(head)
    insts = list(getattr(host, "instrument_names_48", []) or [])
    cols = ["Key", "Instrument", "Seq #", "Hz (0 = chart)", "Pitch st", "Vol %", "Phase °", "Length s", "PKP", "Pan", "Oct", ""]
    table = QTableWidget(len(order), len(cols))
    table.setHorizontalHeaderLabels(cols)
    table.verticalHeader().setVisible(False)
    table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
    lay.addWidget(table, 1)
    widgets = {}

    def changed(ch):
        if dlg._loading:
            return
        w = widgets[ch]
        b = {"inst": "" if w["inst"].currentIndex() == 0 else w["inst"].currentText(),
             "seq": int(w["seq"].value()), "hz": float(w["hz"].value()), "pitch": float(w["pitch"].value()),
             "vol": int(w["vol"].value()), "phase": int(w["phase"].value()), "dur": float(w["dur"].value()),
             "pkp": float(w["pkp"].value()), "pan": int(w["pan"].value()), "octave": int(w["octave"].value())}
        bank.set(ch, b)
        dlg._dirty.start()

    for r, ch in enumerate(order):
        it = gb.QTableWidgetItem(ch); it.setFlags(Qt.ItemFlag.ItemIsEnabled)
        table.setItem(r, 0, it)
        c_inst = QComboBox(); c_inst.addItem("[Selected Instrument]"); c_inst.addItems(insts)
        s_seq = QSpinBox(); s_seq.setRange(0, 999); s_seq.setToolTip("0 = single note; N = play sequence N as a phrase")
        s_hz = QDoubleSpinBox(); s_hz.setRange(0.0, 20000.0); s_hz.setDecimals(2); s_hz.setSingleStep(1.0)
        s_pitch = QDoubleSpinBox(); s_pitch.setRange(-48.0, 48.0); s_pitch.setDecimals(2); s_pitch.setSingleStep(1.0)
        s_vol = QSpinBox(); s_vol.setRange(0, 200)
        s_phase = QSpinBox(); s_phase.setRange(0, 359); s_phase.setWrapping(True)
        s_dur = QDoubleSpinBox(); s_dur.setRange(0.05, 8.0); s_dur.setDecimals(2); s_dur.setSingleStep(0.05)
        s_pkp = QDoubleSpinBox(); s_pkp.setRange(0.0, 1.0); s_pkp.setDecimals(2); s_pkp.setSingleStep(0.05)
        s_pkp.setToolTip("PKP envelope: 0 = pluck · 0.5 = held · 1 = swell")
        s_pan = QSpinBox(); s_pan.setRange(-100, 100); s_pan.setToolTip("Pan −100..100")
        s_oct = QSpinBox(); s_oct.setRange(-2, 2); s_oct.setToolTip("Octave offset")
        b_test = QPushButton("▶"); b_test.setFixedWidth(34); b_test.setToolTip("Play this key")
        b_test.clicked.connect(lambda _c=False, c=ch: host._keychart_trigger(order.find(c), c))
        for col, w in enumerate((c_inst, s_seq, s_hz, s_pitch, s_vol, s_phase, s_dur, s_pkp, s_pan, s_oct, b_test), start=1):
            table.setCellWidget(r, col, w)
        widgets[ch] = {"inst": c_inst, "seq": s_seq, "hz": s_hz, "pitch": s_pitch, "vol": s_vol,
                       "phase": s_phase, "dur": s_dur, "pkp": s_pkp, "pan": s_pan, "octave": s_oct}
        c_inst.currentIndexChanged.connect(lambda *_a, c=ch: changed(c))
        for w in (s_seq, s_hz, s_pitch, s_vol, s_phase, s_dur, s_pkp, s_pan, s_oct):
            w.valueChanged.connect(lambda *_a, c=ch: changed(c))

    def reload():
        dlg._loading = True
        try:
            for ch in order:
                b = bank.binding(ch); w = widgets[ch]
                i = w["inst"].findText(b["inst"]) if b["inst"] else 0
                w["inst"].setCurrentIndex(max(0, i))
                w["seq"].setValue(int(b["seq"])); w["hz"].setValue(float(b["hz"]))
                w["pitch"].setValue(float(b["pitch"])); w["vol"].setValue(int(b["vol"]))
                w["phase"].setValue(int(b["phase"])); w["dur"].setValue(float(b["dur"]))
                w["pkp"].setValue(float(b.get("pkp", 0.5))); w["pan"].setValue(int(b.get("pan", 0)))
                w["octave"].setValue(int(b.get("octave", 0)))
        finally:
            dlg._loading = False
    dlg._reload = reload
    dlg._loading = False

    # randomize + tools
    tools = QHBoxLayout()
    b_rand = QPushButton("🎲 Randomize Keys")
    b_rand.setToolTip("Random instrument / pitch / volume / phase (and sequence) per key — ticked parts only")
    r_inst = QCheckBox("instrument"); r_inst.setChecked(True)
    r_pitch = QCheckBox("pitch"); r_pitch.setChecked(True)
    r_vol = QCheckBox("volume"); r_vol.setChecked(True)
    r_phase = QCheckBox("phase"); r_phase.setChecked(True)
    r_seq = QCheckBox("sequence")
    r_used = QCheckBox("only instruments with steps"); r_used.setChecked(True)
    b_reset = QPushButton("Reset all to [Selected Instrument]")
    b_pre = QPushButton("⚡ Pre-render now")
    for w in (b_rand, r_inst, r_pitch, r_vol, r_phase, r_seq, r_used):
        tools.addWidget(w)
    tools.addStretch(1)
    tools.addWidget(b_reset); tools.addWidget(b_pre)
    lay.addLayout(tools)
    opts = QHBoxLayout()
    chk_keys = QCheckBox("Keys play notes"); chk_keys.setChecked(bool(getattr(host, "_keychart_enabled", True)))
    chk_keys.toggled.connect(lambda on: (setattr(host, "_keychart_enabled", bool(on)),
                                         host._install_keychart() if on else None))
    chk_bg = QCheckBox("Prepare Play / Export in the background when idle")
    chk_bg.setToolTip("After the project has been unchanged for a few seconds, the full mix is rendered on a "
                      "worker and kept in RAM, so Play and Export start from a ready buffer.")
    chk_bg.setChecked(bool(getattr(host, "background_prerender", True)))
    chk_bg.toggled.connect(lambda on: setattr(host, "background_prerender", bool(on)))
    lbl_ram = QLabel("")
    opts.addWidget(chk_keys); opts.addWidget(chk_bg); opts.addStretch(1); opts.addWidget(lbl_ram)
    lay.addLayout(opts)

    def status(n=None):
        mb = bank.ram_bytes() / 1e6
        lbl_ram.setText(f"{len(bank.bindings)} keys bound · {mb:.1f} MB in RAM" + (f" · {n} rendered" if n is not None else ""))

    def prerender():
        lbl_ram.setText("pre-rendering…")
        bank.prerender(order, done=lambda n: QTimer.singleShot(0, lambda: status(n)))

    def randomize():
        pool = insts
        if r_used.isChecked():
            mem = getattr(host, "instrument_sequencer_memory", {}) or {}
            used = [n for n in insts if any((mem.get(n) or {}).get("steps") or [])]
            pool = used or insts
        bank.randomize(order, pool, inst=r_inst.isChecked(), pitch=r_pitch.isChecked(), vol=r_vol.isChecked(),
                       phase=r_phase.isChecked(), seq=r_seq.isChecked())
        reload(); prerender()

    def reset():
        for ch in order:
            bank.set(ch, default_binding())
        reload(); status()
    b_rand.clicked.connect(randomize)
    b_reset.clicked.connect(reset)
    b_pre.clicked.connect(prerender)
    dlg._dirty = QTimer(dlg); dlg._dirty.setSingleShot(True); dlg._dirty.setInterval(700)
    dlg._dirty.timeout.connect(prerender)
    reload(); status()
    host._key_assign_dialog = dlg
    dlg.show(); dlg.raise_(); dlg.activateWindow()
    return dlg
