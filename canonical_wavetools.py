"""canonical_wavetools.py — GROOVEBOX_R32_WAVETOOLS_20261110

Three canonical tools, one window (Quick Rack ▸ 🌊 Wave Tools, File Studio ▸ Samples):

  WAVE SYNCER   fits a sample to the project: detects its fundamental and length, then
                (a) tunes it to the nearest harmonic of the project base frequency (or the
                    seed's degree), and (b) stretches/resamples its length to a whole number of
                    beats or bars at the project tempo. Report shows before → after.
  WAVE FOLDER   deterministic sine wavefolding with fold count, symmetry and a seeded drift of
                the fold threshold (canonical) — synthesis, not a filter.
  RESAMPLER     band-limited resampling (windowed-sinc, Kaiser β=8.6, 32 zero-crossings) to any
                rate; pitch-preserving length change by overlap-add of isn-windowed grains.

Pure NumPy; deterministic; outputs are new files beside the source (originals untouched).
"""
from __future__ import annotations

import math
import os

import numpy as np


# ---------------------------------------------------------------------------
# DSP
# ---------------------------------------------------------------------------
def detect_f0(x, sr, lo=40.0, hi=2000.0):
    x = np.asarray(x, dtype=np.float64)
    if x.ndim == 2:
        x = x.mean(axis=1)
    n = min(x.size, int(sr * 0.5))
    if n < 256:
        return 0.0
    seg = x[x.size // 2 - n // 2: x.size // 2 + n // 2] if x.size > n else x
    seg = seg - seg.mean()
    N = 1 << int(math.ceil(math.log2(2 * seg.size)))
    f = np.fft.rfft(seg, N)
    ac = np.fft.irfft(np.abs(f) ** 2, N)[: seg.size]
    a, b = int(sr / hi), min(seg.size - 1, int(sr / lo))
    if b <= a + 2:
        return 0.0
    k = a + int(np.argmax(ac[a:b]))
    if 0 < k < ac.size - 1:                       # parabolic refinement
        y0, y1, y2 = ac[k - 1], ac[k], ac[k + 1]
        den = (y0 - 2 * y1 + y2)
        k = k + (0.5 * (y0 - y2) / den if den else 0.0)
    return float(sr / k) if k > 0 else 0.0


def sinc_resample(x, ratio, zeros=32, beta=8.6):
    """y[n] = Σ x[k]·h(n/ratio − k): band-limited (cutoff = min(1, ratio)·Nyquist)."""
    x = np.asarray(x, dtype=np.float64)
    if x.ndim == 2:
        return np.stack([sinc_resample(x[:, c], ratio, zeros, beta) for c in range(x.shape[1])], axis=1)
    ratio = float(ratio)
    if abs(ratio - 1.0) < 1e-12:
        return x.copy()
    n_out = int(round(x.size * ratio))
    cut = min(1.0, ratio)
    pos = np.arange(n_out) / ratio
    out = np.zeros(n_out)
    chunk = 8192
    win_n = zeros / cut
    for s in range(0, n_out, chunk):
        p = pos[s:s + chunk]
        k0 = np.floor(p - win_n).astype(np.int64)
        taps = int(2 * win_n) + 2
        k = k0[:, None] + np.arange(taps)[None, :]
        d = p[:, None] - k
        w = np.where(np.abs(d) < win_n, np.i0(beta * np.sqrt(np.clip(1 - (d / win_n) ** 2, 0, 1))) / np.i0(beta), 0.0)
        h = cut * np.sinc(cut * d) * w
        valid = (k >= 0) & (k < x.size)
        out[s:s + chunk] = (np.where(valid, x[np.clip(k, 0, x.size - 1)], 0.0) * h).sum(axis=1)
    return out


def ola_stretch(x, factor, sr, grain_s=0.06):
    """Change length by `factor` keeping pitch (isn-windowed overlap-add, deterministic)."""
    x = np.asarray(x, dtype=np.float64)
    if x.ndim == 2:
        return np.stack([ola_stretch(x[:, c], factor, sr, grain_s) for c in range(x.shape[1])], axis=1)
    g = max(64, int(grain_s * sr)); hop_out = g // 2; hop_in = hop_out / float(factor)
    n_out = int(round(x.size * factor)); out = np.zeros(n_out + g); norm = np.zeros(n_out + g)
    w = np.sin(np.linspace(0, math.pi, g)) ** 2
    i = 0
    while i * hop_out < n_out:
        a = int(round(i * hop_in))
        seg = x[a:a + g]
        if seg.size < g:
            seg = np.pad(seg, (0, g - seg.size))
        o = i * hop_out
        out[o:o + g] += seg * w; norm[o:o + g] += w
        i += 1
    return (out / np.maximum(norm, 1e-9))[:n_out]


def wavefold(x, folds=2.0, symmetry=0.0, drift=0.0, seed=1, sr=48000):
    x = np.asarray(x, dtype=np.float64)
    k = 1.0 + max(0.0, float(folds))
    th = 1.0
    if drift:
        rng = np.random.default_rng(int(seed) & 0x7FFFFFFF)
        knots = rng.uniform(-1, 1, 16)
        th = 1.0 + drift * np.interp(np.linspace(0, 15, x.shape[0]), np.arange(16), knots)
        if x.ndim == 2:
            th = th[:, None]
    y = np.sin((x + float(symmetry)) * k * math.pi / 2.0 / th)
    return y / max(1.0, float(np.max(np.abs(y))) or 1.0)


# ---------------------------------------------------------------------------
# syncer
# ---------------------------------------------------------------------------
def sync_to_project(x, sr, base_hz=432.0, bpm=120.0, unit="beat", tune=True, fit=True):
    f0 = detect_f0(x, sr)
    rep = {"f0_in": f0, "seconds_in": x.shape[0] / sr}
    y = np.asarray(x, dtype=np.float64)
    if tune and f0 > 0:
        h = max(1, round(f0 / base_hz)) if f0 >= base_hz else 1.0 / max(1, round(base_hz / f0))
        target = base_hz * h
        y = sinc_resample(y, f0 / target)           # pitch moves by target/f0 (length too)
        rep["f0_out"] = target; rep["harmonic"] = h
    if fit:
        beat = 60.0 / max(20.0, float(bpm)); u = beat * (4 if unit == "bar" else 1)
        cur = y.shape[0] / sr
        n_units = max(1, round(cur / u))
        y = ola_stretch(y, n_units * u / cur, sr)
        rep["seconds_out"] = y.shape[0] / sr; rep["units"] = n_units; rep["unit"] = unit
    return y.astype(np.float32), rep


# ---------------------------------------------------------------------------
# window
# ---------------------------------------------------------------------------
def open_window(app, path=None):
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QPushButton, QLabel, QLineEdit, QDoubleSpinBox,
                                 QComboBox, QCheckBox, QFileDialog, QFormLayout, QSpinBox)
    import postprocess_window as pw
    w = QWidget(app, Qt.WindowType.Window); w.setWindowTitle("🌊 Wave Tools · syncer · folder · resampler"); w.resize(640, 420)
    lay = QVBoxLayout(w)
    row = QHBoxLayout(); src = QLineEdit(path or ""); b = QPushButton("Choose…")
    b.clicked.connect(lambda: src.setText(QFileDialog.getOpenFileName(w, "Sample", "", "Audio (*.wav *.flac *.aiff *.mp3 *.ogg *.opus *.MCC *.mcc);;MCC media (*.MCC *.mcc)")[0] or src.text()))
    row.addWidget(QLabel("Source")); row.addWidget(src, 1); row.addWidget(b); lay.addLayout(row)
    tabs = QTabWidget(); lay.addWidget(tabs); out = QLabel(""); out.setWordWrap(True); lay.addWidget(out)
    base = float(getattr(getattr(app, "spin_base_frequency", None), "value", lambda: 432.0)())
    bpm = float(getattr(getattr(app, "spin_bpm", None), "value", lambda: 120.0)())

    def _io(fn, tag):
        p = src.text().strip()
        if not os.path.isfile(p):
            out.setText("choose a source file"); return
        x, sr = pw.read_audio(p)
        y, rep = fn(x, sr)
        dst = pw.write_audio(os.path.splitext(p)[0] + "." + tag + ".wav", y, sr)
        out.setText("%s → %s\n%s" % (os.path.basename(p), os.path.basename(dst), ", ".join("%s %s" % (k, (round(v, 3) if isinstance(v, float) else v)) for k, v in rep.items())))

    t = QWidget(); f = QFormLayout(t); tabs.addTab(t, "Syncer")
    bh = QDoubleSpinBox(); bh.setRange(20, 2000); bh.setValue(base); bp = QDoubleSpinBox(); bp.setRange(20, 400); bp.setValue(bpm)
    un = QComboBox(); un.addItems(["beat", "bar"]); tu = QCheckBox("Tune to a harmonic of the base"); tu.setChecked(True)
    fi = QCheckBox("Fit length to whole beats / bars"); fi.setChecked(True)
    for cap, x in (("Base Hz", bh), ("Tempo", bp), ("Unit", un)):
        f.addRow(cap, x)
    f.addRow(tu); f.addRow(fi)
    go = QPushButton("Sync"); go.clicked.connect(lambda: _io(lambda x, sr: sync_to_project(x, sr, bh.value(), bp.value(), un.currentText(), tu.isChecked(), fi.isChecked()), "synced"))
    f.addRow(go)

    t = QWidget(); f = QFormLayout(t); tabs.addTab(t, "Folder")
    fo = QDoubleSpinBox(); fo.setRange(0, 16); fo.setValue(2); sy = QDoubleSpinBox(); sy.setRange(-1, 1); sy.setSingleStep(0.05)
    dr = QDoubleSpinBox(); dr.setRange(0, 0.9); dr.setSingleStep(0.05)
    for cap, x in (("Folds", fo), ("Symmetry", sy), ("Seeded threshold drift (canonical)", dr)):
        f.addRow(cap, x)

    def _fold(x, sr):
        try:
            sd = int(app._seed_program_signature() or 1)
        except Exception:
            sd = 1
        return wavefold(x, fo.value(), sy.value(), dr.value(), sd, sr).astype(np.float32), {"folds": fo.value(), "drift": dr.value()}
    go = QPushButton("Fold"); go.clicked.connect(lambda: _io(_fold, "folded")); f.addRow(go)

    t = QWidget(); f = QFormLayout(t); tabs.addTab(t, "Resampler")
    rate = QSpinBox(); rate.setRange(8000, 384000); rate.setValue(48000)
    ln = QDoubleSpinBox(); ln.setRange(0.25, 4.0); ln.setValue(1.0); ln.setSingleStep(0.05)
    pp = QCheckBox("Keep pitch when changing length"); pp.setChecked(True)
    f.addRow("Output rate", rate); f.addRow("Length ×", ln); f.addRow(pp)

    def _rs(x, sr):
        y = sinc_resample(x, rate.value() / float(sr)); r2 = rate.value()
        if abs(ln.value() - 1) > 1e-6:
            y = ola_stretch(y, ln.value(), r2) if pp.isChecked() else sinc_resample(y, ln.value())
        return y.astype(np.float32), {"rate_in": sr, "rate_out": r2, "length": ln.value()}

    def _go_rs():
        p = src.text().strip()
        if not os.path.isfile(p):
            out.setText("choose a source file"); return
        x, sr = pw.read_audio(p); y, rep = _rs(x, sr)
        dst = pw.write_audio(os.path.splitext(p)[0] + ".resampled.wav", y, rate.value())
        out.setText("→ %s · %s" % (os.path.basename(dst), rep))
    go = QPushButton("Resample"); go.clicked.connect(_go_rs); f.addRow(go)
    app._wavetools_window = w; w.show(); return w
