"""audio_editor.py (R132): a direct, Audacity-style audio editor — select, cut, process, listen — tied to the canonicals.

Open a WAV / FLAC / OGG / AIFF (soundfile) or anything ffmpeg reads; drag on the waveform to select (no selection =
whole file). Edit: cut, copy, paste, delete, trim to selection, insert silence, undo / redo (30 steps).
Soft FX on the selection: gain, normalize, fade in / out, reverse, speed (resample), low-pass / high-pass,
echo, reverb, gate, compressor, bit crush, tremolo. 🎲 Canonicalize: the canonical composition matrix (seed + active
canonical engines) picks the FX chain settings — amount 0..1 blends from your settings to the matrix's; "Explain"
lists which engine set which value. Export WAV / FLAC; "→ Clip Studio" puts the result on the timeline.

All DSP is numpy / scipy (float32, never touches the original file until you export under a new name).
"""
from __future__ import annotations

import os

import numpy as np

# R132: the project's own trig (MATHEMATICS.md / trig_series), routed through gb_trig.
from gb_trig import sin as _sin, cos as _cos, nsin as _nsin, ncos as _ncos   # R132.10: book isy/isx, Trigonometry Engine toggle

FX_SPEC = {   # the parameters the canonical matrix sets (name: low, high, curve)
    "gain_db": (-9.0, 6.0, "lin"), "cutoff_hz": (300.0, 16000.0, "log"), "echo_ms": (60.0, 700.0, "log"),
    "echo_fb": (0.0, 0.6, "lin"), "reverb": (0.0, 0.5, "lin"), "trem_hz": (0.5, 12.0, "log"),
    "trem_depth": (0.0, 0.6, "lin"), "drive": (1.0, 4.0, "log"), "fade_ms": (0.0, 400.0, "lin"),
}


# ------------------------------------------------------------------ I/O
def load(path):
    """(float32 array (n, ch), sample rate)."""
    try:
        import soundfile as sf
        x, sr = sf.read(path, dtype="float32", always_2d=True)
        return x, int(sr)
    except Exception:
        import subprocess, shutil
        ff = shutil.which("ffmpeg")
        if not ff:
            raise
        raw = subprocess.run([ff, "-v", "error", "-i", path, "-f", "f32le", "-ac", "2", "-ar", "48000", "-"],
                             capture_output=True, check=True, timeout=600).stdout
        return np.frombuffer(raw, dtype=np.float32).reshape(-1, 2).copy(), 48000


def save(path, x, sr):
    import soundfile as sf
    sf.write(path, np.clip(x, -1, 1), sr, subtype="PCM_24" if path.lower().endswith((".wav", ".flac")) else None)
    return path


# ------------------------------------------------------------------ DSP (pure functions on (n, ch) float32)
def gain(x, db):
    return (x * 10 ** (db / 20.0)).astype(np.float32)


def normalize(x, peak=0.98):
    m = float(np.max(np.abs(x))) if x.size else 0.0
    return x if m < 1e-9 else (x * (peak / m)).astype(np.float32)


def fade(x, sr, ms, direction="in"):
    n = min(len(x), int(sr * ms / 1000.0))
    if n < 2:
        return x
    y = x.copy(); ramp = np.linspace(0, 1, n, dtype=np.float32)[:, None]
    if direction == "in":
        y[:n] *= ramp
    else:
        y[-n:] *= ramp[::-1]
    return y


def reverse(x):
    return x[::-1].copy()


def speed(x, factor):
    """Resample: factor 2 = twice as fast (an octave up)."""
    n = max(2, int(len(x) / max(0.05, factor)))
    idx = np.linspace(0, len(x) - 1, n)
    return np.stack([np.interp(idx, np.arange(len(x)), x[:, c]) for c in range(x.shape[1])], axis=1).astype(np.float32)


def _sos(kind, hz, sr):
    from scipy.signal import butter
    return butter(4, min(hz, sr * 0.45) / (sr / 2), btype=kind, output="sos")


def lowpass(x, sr, hz):
    from scipy.signal import sosfilt
    return sosfilt(_sos("lowpass", hz, sr), x, axis=0).astype(np.float32)


def highpass(x, sr, hz):
    from scipy.signal import sosfilt
    return sosfilt(_sos("highpass", hz, sr), x, axis=0).astype(np.float32)


def echo(x, sr, ms, fb=0.4, mix=0.35):
    d = max(1, int(sr * ms / 1000.0)); y = x.copy()
    tail = np.zeros((len(x) + d * 6, x.shape[1]), np.float32); tail[:len(x)] = x
    out = tail.copy()
    for k in range(1, 7):
        out[d * k:] += tail[:len(tail) - d * k] * (fb ** k)
    y = x * (1 - mix) + out[:len(x)] * mix
    return y.astype(np.float32)


def reverb(x, sr, mix=0.3):
    """Schroeder: 4 parallel combs + 2 allpasses per channel."""
    from scipy.signal import lfilter
    out = np.zeros_like(x)
    for c in range(x.shape[1]):
        s = x[:, c]; acc = np.zeros_like(s)
        for ms, g in ((29.7, .80), (37.1, .78), (41.1, .76), (43.7, .74)):
            d = int(sr * ms / 1000) + c * 7
            a = np.zeros(d + 1); a[0] = 1; a[d] = -g
            acc += lfilter([1.0], a, s)
        for ms, g in ((5.0, .7), (1.7, .7)):
            d = int(sr * ms / 1000)
            b = np.zeros(d + 1); b[0] = -g; b[d] = 1; a = np.zeros(d + 1); a[0] = 1; a[d] = -g
            acc = lfilter(b, a, acc)
        out[:, c] = acc / 4.0
    return (x * (1 - mix) + out * mix).astype(np.float32)


def gate(x, sr, thresh_db=-45.0, hold_ms=40.0):
    env = np.abs(x).max(axis=1)
    k = max(1, int(sr * hold_ms / 1000))
    env = np.convolve(env, np.ones(k) / k, mode="same")
    m = (env > 10 ** (thresh_db / 20)).astype(np.float32)
    m = np.convolve(m, np.ones(k) / k, mode="same")
    return (x * m[:, None]).astype(np.float32)


def compress(x, sr, thresh_db=-18.0, ratio=4.0, attack_ms=5.0, release_ms=120.0, makeup_db=4.0):
    lvl = 20 * np.log10(np.maximum(1e-6, np.abs(x).max(axis=1)))
    over = np.maximum(0.0, lvl - thresh_db); target = -over * (1 - 1 / ratio)
    from scipy.signal import lfilter
    from scipy.ndimage import minimum_filter1d
    # attack: look-ahead minimum over the attack window (gain drops in time); release: one-pole smoothing (vectorised)
    k = max(1, int(sr * attack_ms / 1000))
    t2 = minimum_filter1d(target, size=k, origin=-(k // 2) if k > 1 else 0)
    r = np.exp(-1.0 / (sr * release_ms / 1000))
    g = lfilter([1 - r], [1, -r], t2)
    g = np.minimum(g, t2 * 0 + g)
    return (x * (10 ** ((g + makeup_db) / 20))[:, None]).astype(np.float32)


def crush(x, bits=8, down=4):
    lv = 2 ** (bits - 1); y = np.round(x * lv) / lv
    y = np.repeat(y[::max(1, int(down))], max(1, int(down)), axis=0)[:len(x)]
    return y.astype(np.float32)


def tremolo(x, sr, hz=5.0, depth=0.5):
    t = np.arange(len(x)) / sr
    return (x * (1 - depth * 0.5 * (1 + _nsin(2 * np.pi * hz * t)))[:, None]).astype(np.float32)


def drive(x, amount=2.0):
    return (np.tanh(x * amount) / np.tanh(amount)).astype(np.float32)


def canonical_chain(x, sr, p):
    """The chain the canonical matrix controls, in a fixed musical order."""
    y = gain(x, p["gain_db"]); y = drive(y, p["drive"]); y = lowpass(y, sr, p["cutoff_hz"])
    y = tremolo(y, sr, p["trem_hz"], p["trem_depth"]); y = echo(y, sr, p["echo_ms"], p["echo_fb"])
    y = reverb(y, sr, p["reverb"]); y = fade(fade(y, sr, p["fade_ms"], "in"), sr, p["fade_ms"], "out")
    return np.clip(y, -1, 1).astype(np.float32)


# ------------------------------------------------------------------ editor model (selection + undo)
class Doc:
    def __init__(self, x, sr, path=""):
        self.x, self.sr, self.path = np.asarray(x, np.float32), int(sr), path
        self.sel = (0, len(self.x)); self.undo, self.redo = [], []; self.clip = None

    def _push(self):
        self.undo.append(self.x.copy()); del self.undo[:-30]; self.redo.clear()

    def selection(self):
        a, b = self.sel
        a, b = max(0, min(a, b)), min(len(self.x), max(a, b))
        return (a, b) if b - a > 1 else (0, len(self.x))

    def apply(self, fn):
        a, b = self.selection(); self._push()
        seg = fn(self.x[a:b])
        self.x = np.concatenate([self.x[:a], np.asarray(seg, np.float32), self.x[b:]])
        self.sel = (a, a + len(seg))

    def cut(self):
        a, b = self.selection(); self._push(); self.clip = self.x[a:b].copy()
        self.x = np.concatenate([self.x[:a], self.x[b:]]); self.sel = (a, a)

    def copy(self):
        a, b = self.selection(); self.clip = self.x[a:b].copy()

    def paste(self):
        if self.clip is None:
            return
        a, _b = self.sel; self._push()
        self.x = np.concatenate([self.x[:a], self.clip, self.x[a:]]); self.sel = (a, a + len(self.clip))

    def delete(self):
        a, b = self.selection(); self._push(); self.x = np.concatenate([self.x[:a], self.x[b:]]); self.sel = (a, a)

    def trim(self):
        a, b = self.selection(); self._push(); self.x = self.x[a:b].copy(); self.sel = (0, len(self.x))

    def silence(self, seconds):
        a, _b = self.sel; self._push()
        z = np.zeros((int(self.sr * seconds), self.x.shape[1]), np.float32)
        self.x = np.concatenate([self.x[:a], z, self.x[a:]]); self.sel = (a, a + len(z))

    def do_undo(self):
        if self.undo:
            self.redo.append(self.x); self.x = self.undo.pop(); self.sel = (0, len(self.x))

    def do_redo(self):
        if self.redo:
            self.undo.append(self.x); self.x = self.redo.pop(); self.sel = (0, len(self.x))


# ------------------------------------------------------------------ window
def open_window(app=None, path=None):
    from PyQt6.QtCore import Qt, QRectF, QPointF
    from PyQt6.QtGui import QPainter, QColor, QPen
    from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QFileDialog, QWidget,
                                 QComboBox, QDoubleSpinBox, QSlider, QPlainTextEdit, QMessageBox)

    d = QDialog(app); d.setWindowTitle("🎧 Audio Editor · select · cut · process · canonicalize"); d.resize(1100, 640)
    v = QVBoxLayout(d)
    st = {"doc": None, "drag": None}
    info = QLabel("Open a sound file (or drop one here). Drag on the waveform to select; no selection = the whole file.")
    v.addWidget(info)

    class Wave(QWidget):
        def __init__(self):
            super().__init__(); self.setMinimumHeight(220); self.setMouseTracking(True)

        def _x2i(self, px):
            doc = st["doc"]
            return 0 if doc is None else int(max(0, min(1, px / max(1, self.width()))) * len(doc.x))

        def mousePressEvent(self, e):
            if st["doc"] is not None:
                st["drag"] = self._x2i(e.position().x()); st["doc"].sel = (st["drag"], st["drag"]); self.update()

        def mouseMoveEvent(self, e):
            if st["drag"] is not None and st["doc"] is not None:
                st["doc"].sel = (st["drag"], self._x2i(e.position().x())); self.update(); status()

        def mouseReleaseEvent(self, _e):
            st["drag"] = None

        def paintEvent(self, _e):
            qp = QPainter(self)
            try:
                qp.fillRect(self.rect(), QColor(8, 14, 22)); doc = st["doc"]
                if doc is None or not len(doc.x):
                    qp.setPen(QColor(150, 170, 200)); qp.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "no audio"); return
                W, H = self.width(), self.height(); mono = doc.x.mean(axis=1)
                cols = np.array_split(mono, max(1, W))
                a, b = doc.sel
                if abs(b - a) > 1:
                    x0, x1 = sorted((a / len(doc.x) * W, b / len(doc.x) * W))
                    qp.fillRect(QRectF(x0, 0, x1 - x0, H), QColor(60, 110, 170, 90))
                qp.setPen(QPen(QColor(90, 220, 190), 1))
                for i, c in enumerate(cols):
                    if c.size:
                        qp.drawLine(QPointF(i, H / 2 - c.max() * H * 0.45), QPointF(i, H / 2 - c.min() * H * 0.45))
            finally:
                qp.end()

    wave = Wave(); v.addWidget(wave, 1)

    def status():
        doc = st["doc"]
        if doc is None:
            return
        a, b = doc.selection(); sec = lambda n: n / doc.sr
        info.setText(f"{os.path.basename(doc.path) or 'untitled'} · {sec(len(doc.x)):.2f} s · {doc.sr} Hz · "
                     f"{doc.x.shape[1]} ch · selection {sec(a):.3f}–{sec(b):.3f} s ({sec(b - a):.3f} s)")

    def refresh():
        wave.update(); status()

    def need():
        if st["doc"] is None:
            QMessageBox.information(d, "Audio Editor", "Open a sound file first."); return False
        return True

    def do_open(p=None):
        p = p or QFileDialog.getOpenFileName(d, "Open audio", os.path.expanduser("~"),
                                             "Audio (*.wav *.flac *.ogg *.aif *.aiff *.mp3 *.m4a *.opus);;All files (*)")[0]
        if p:
            x, sr = load(p); st["doc"] = Doc(x, sr, p); refresh()

    def do_save():
        if not need():
            return
        p, _f = QFileDialog.getSaveFileName(d, "Export", os.path.splitext(st["doc"].path or "edit")[0] + ".edit.wav",
                                            "WAV (*.wav);;FLAC (*.flac)")
        if p:
            save(p, st["doc"].x, st["doc"].sr); info.setText("saved " + p); d._last_export = p

    row = QHBoxLayout(); v.addLayout(row)
    for cap, fn in (("📂 Open", do_open), ("💾 Export", do_save)):
        b = QPushButton(cap); b.clicked.connect(lambda _c=False, f=fn: f()); row.addWidget(b)
    edits = (("✂ Cut", "cut"), ("⧉ Copy", "copy"), ("📋 Paste", "paste"), ("⌫ Delete", "delete"),
             ("⤢ Trim to selection", "trim"), ("↶ Undo", "do_undo"), ("↷ Redo", "do_redo"))
    for cap, m in edits:
        b = QPushButton(cap); b.clicked.connect(lambda _c=False, mm=m: need() and (getattr(st["doc"], mm)(), refresh())); row.addWidget(b)
    b = QPushButton("＋ 1 s silence"); b.clicked.connect(lambda _c=False: need() and (st["doc"].silence(1.0), refresh())); row.addWidget(b)
    row.addStretch(1)

    fx = QHBoxLayout(); v.addLayout(fx)
    combo = QComboBox(); val = QDoubleSpinBox(); val.setRange(-1000, 20000); val.setDecimals(2)
    FX = {"Gain (dB)": (3.0, lambda x, sr, a: gain(x, a)), "Normalize": (0.98, lambda x, sr, a: normalize(x, a)),
          "Fade in (ms)": (300, lambda x, sr, a: fade(x, sr, a, "in")), "Fade out (ms)": (300, lambda x, sr, a: fade(x, sr, a, "out")),
          "Reverse": (0, lambda x, sr, a: reverse(x)), "Speed ×": (1.5, lambda x, sr, a: speed(x, a)),
          "Low-pass (Hz)": (2000, lambda x, sr, a: lowpass(x, sr, a)), "High-pass (Hz)": (150, lambda x, sr, a: highpass(x, sr, a)),
          "Echo (ms)": (300, lambda x, sr, a: echo(x, sr, a)), "Reverb (mix)": (0.3, lambda x, sr, a: reverb(x, sr, a)),
          "Gate (dB)": (-45, lambda x, sr, a: gate(x, sr, a)), "Compressor (thresh dB)": (-18, lambda x, sr, a: compress(x, sr, a)),
          "Bit crush (bits)": (8, lambda x, sr, a: crush(x, int(a))), "Tremolo (Hz)": (5, lambda x, sr, a: tremolo(x, sr, a)),
          "Drive": (2.5, lambda x, sr, a: drive(x, a))}
    combo.addItems(list(FX)); combo.currentTextChanged.connect(lambda k: val.setValue(FX[k][0])); val.setValue(FX[combo.currentText()][0])
    b_fx = QPushButton("Apply to selection")
    b_fx.clicked.connect(lambda _c=False: need() and (st["doc"].apply(lambda seg: FX[combo.currentText()][1](seg, st["doc"].sr, val.value())), refresh()))
    for w_ in (QLabel("Effect"), combo, val, b_fx):
        fx.addWidget(w_)
    fx.addSpacing(20)
    amt = QSlider(Qt.Orientation.Horizontal); amt.setRange(0, 100); amt.setValue(100); amt.setMaximumWidth(140)
    b_can = QPushButton("🎲 Canonicalize selection"); b_exp = QPushButton("Explain")
    b_can.setToolTip("The canonical composition matrix (seed + active canonical engines) sets drive, filter, tremolo, "
                     "echo, reverb and fades for the selection. Same seed + engines = same result.")

    def canon():
        if not need():
            return
        import canonical_matrix as cm
        p = cm.params(app, "audio_editor", FX_SPEC, amount=amt.value() / 100.0,
                      base={"gain_db": 0.0, "cutoff_hz": 16000.0, "echo_fb": 0.0, "reverb": 0.0, "trem_depth": 0.0,
                            "drive": 1.0, "fade_ms": 0.0, "echo_ms": 300.0, "trem_hz": 4.0})
        st["doc"].apply(lambda seg: canonical_chain(seg, st["doc"].sr, p)); refresh()

    def explain():
        import canonical_matrix as cm
        log.setPlainText(cm.explain(app, "audio_editor", FX_SPEC))
    b_can.clicked.connect(lambda _c=False: canon()); b_exp.clicked.connect(lambda _c=False: explain())
    for w_ in (QLabel("Amount"), amt, b_can, b_exp):
        fx.addWidget(w_)
    try:   # R132: encode / decode into the other editors
        __import__("editor_bridge").install_audio_editor(d, fx, app)
    except Exception as _eb_exc:
        print(f"[Audio Editor] bridge unavailable: {_eb_exc}")
    fx.addStretch(1)
    log = QPlainTextEdit(); log.setReadOnly(True); log.setMaximumHeight(110); v.addWidget(log)
    d._doc = st; d._fx = FX
    if path:
        do_open(path)
    d.show()
    return d
