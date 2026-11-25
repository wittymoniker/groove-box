"""audio_tools.py — loudness (EBU R128 / ITU-R BS.1770), true peak, normalisation, time-stretch and pitch-shift.

Loudness   K-weighting (the BS.1770 high-shelf + high-pass pair, designed for the file's sample rate) applied to the
           power spectrum of each 400 ms block (75 % overlap; Parseval), absolute gate −70 LUFS, relative gate −10 LU:
           integrated loudness (LUFS), maximum short-term (3 s) loudness, loudness range (LRA, 10th–95th percentile of
           short-term values above −70 LUFS and −20 LU relative).
True peak  4× oversampling (band-limited, FFT) per chunk → dBTP.
Normalise  gain to a target (−14 streaming, −16 podcast/Apple, −23 broadcast) with a −1 dBTP ceiling (the Live master
           limiter), written as a 24-bit WAV.
Stretch    phase vocoder (2048 / 512, Hann): tempo change without pitch change; pitch-shift = stretch + resample, so
           pitch changes without tempo change. Everything is NumPy, deterministic, and runs off the UI thread.
"""
from __future__ import annotations

import math
import os
import threading

import numpy as np


def _biquad_mag2(b, a, f, sr):
    w = 2.0 * np.pi * f / sr
    z1, z2 = np.exp(-1j * w), np.exp(-2j * w)
    h = (b[0] + b[1] * z1 + b[2] * z2) / (a[0] + a[1] * z1 + a[2] * z2)
    return np.abs(h) ** 2


def k_weight_power(f, sr):
    """|K(f)|² for BS.1770 at sample rate sr (shelf: +4 dB, 1681.97 Hz, Q 0.7072; high-pass: 38.135 Hz, Q 0.5003)."""
    G, fc, Q = 3.99984385397, 1681.9744509555319, 0.7071752369554193
    K = math.tan(math.pi * fc / sr); Vh = 10 ** (G / 20.0); Vb = Vh ** 0.499666774155
    a0 = 1 + K / Q + K * K
    b = [(Vh + Vb * K / Q + K * K) / a0, 2 * (K * K - Vh) / a0, (Vh - Vb * K / Q + K * K) / a0]
    a = [1.0, 2 * (K * K - 1) / a0, (1 - K / Q + K * K) / a0]
    fc2, Q2 = 38.13547087613982, 0.5003270373253953
    K2 = math.tan(math.pi * fc2 / sr)
    a02 = 1 + K2 / Q2 + K2 * K2
    b2 = [1.0, -2.0, 1.0]
    a2 = [1.0, 2 * (K2 * K2 - 1) / a02, (1 - K2 / Q2 + K2 * K2) / a02]
    return _biquad_mag2(b, a, f, sr) * _biquad_mag2(b2, a2, f, sr)


def _block_ms(x, sr, block_s, hop_s):
    """Mean-square K-weighted power per block (summed over channels)."""
    n, hop = int(block_s * sr), int(hop_s * sr)
    if x.shape[0] < n:
        x = np.vstack([x, np.zeros((n - x.shape[0], x.shape[1]))])
    kw = k_weight_power(np.fft.rfftfreq(n, 1.0 / sr), sr)
    out = []
    for s in range(0, x.shape[0] - n + 1, hop):
        seg = x[s:s + n]
        P = np.abs(np.fft.rfft(seg, axis=0)) ** 2
        P[1:-1] *= 2.0                                          # one-sided spectrum (Parseval)
        out.append(float(np.sum(P * kw[:, None]) / (n * n)))
    return np.asarray(out)


def _lufs(ms):
    return -0.691 + 10.0 * np.log10(np.maximum(ms, 1e-20))


def loudness(x, sr):
    """{"integrated", "short_term_max", "lra", "true_peak_dbtp", "sample_peak_db"} of an array (frames × channels)."""
    x = np.asarray(x, dtype=np.float64)
    if x.ndim == 1:
        x = x[:, None]
    m = _block_ms(x, sr, 0.4, 0.1)
    L = _lufs(m)
    g = m[L > -70.0]
    if g.size:
        rel = _lufs(np.mean(g)) - 10.0
        g2 = m[(L > -70.0) & (L > rel)]
        integrated = float(_lufs(np.mean(g2))) if g2.size else float("-inf")
    else:
        integrated = float("-inf")
    st = _lufs(_block_ms(x, sr, 3.0, 1.0))
    st_ok = st[st > -70.0]
    lra = 0.0
    if st_ok.size:
        st_rel = st_ok[st_ok > (float(_lufs(np.mean(10 ** ((st_ok + 0.691) / 10.0)))) - 20.0)]
        if st_rel.size > 1:
            lra = float(np.percentile(st_rel, 95) - np.percentile(st_rel, 10))
    return {"integrated": integrated, "short_term_max": float(st.max()) if st.size else float("-inf"), "lra": lra,
            "true_peak_dbtp": true_peak_db(x), "sample_peak_db": 20 * math.log10(max(1e-12, float(np.max(np.abs(x)))))}


def true_peak_db(x, chunk=65536):
    x = np.asarray(x, dtype=np.float64)
    if x.ndim == 1:
        x = x[:, None]
    pk = 0.0
    m = 2048                                   # guard band: chunk edges ring after FFT oversampling; measure centres only
    for s in range(0, x.shape[0], chunk):
        a0, a1 = max(0, s - m), min(x.shape[0], s + chunk + m)
        seg = x[a0:a1]
        n = seg.shape[0]
        if n < 4:
            continue
        S = np.fft.rfft(seg * np.hanning(n)[:, None] if n > 2 * m else seg, axis=0)
        up = np.fft.irfft(S, n=4 * n, axis=0) * 4.0
        lo, hi = 4 * (s - a0), 4 * (min(x.shape[0], s + chunk) - a0)
        win = np.hanning(n)
        wup = np.interp(np.arange(4 * n) / 4.0, np.arange(n), win) if n > 2 * m else np.ones(4 * n)
        core = up[lo:hi] / np.maximum(wup[lo:hi, None], 1e-3)
        pk = max(pk, float(np.max(np.abs(core))) if core.size else 0.0)
    return 20 * math.log10(max(pk, 1e-12))


def normalize(x, sr, target_lufs=-14.0, ceiling_dbtp=-1.0):
    info = loudness(x, sr)
    if not math.isfinite(info["integrated"]):
        return np.asarray(x, dtype=np.float64), info
    gain = 10 ** ((target_lufs - info["integrated"]) / 20.0)
    y = np.asarray(x, dtype=np.float64) * gain
    if true_peak_db(y) > ceiling_dbtp:
        import live_master as _lm
        y = _lm.master_audio(y, sr, target_rms_db=20 * math.log10(max(1e-9, float(np.sqrt(np.mean(y * y))))),
                             ceiling_db=ceiling_dbtp - 0.3, max_gain_db=0.0)
    return y, info


def stretch(x, rate, n_fft=2048, hop=512):
    """Phase-vocoder time-stretch: rate > 1 = faster (shorter), < 1 = slower. Pitch is unchanged."""
    x = np.asarray(x, dtype=np.float64)
    if x.ndim > 1:
        return np.stack([stretch(x[:, c], rate, n_fft, hop) for c in range(x.shape[1])], axis=1)
    rate = float(max(0.25, min(4.0, rate)))
    win = np.hanning(n_fft)
    pad = np.concatenate([np.zeros(n_fft), x, np.zeros(n_fft)])
    frames = [np.fft.rfft(win * pad[i:i + n_fft]) for i in range(0, len(pad) - n_fft, hop)]
    if len(frames) < 2:
        return x.copy()
    S = np.array(frames)
    steps = np.arange(0, S.shape[0] - 1, rate)
    omega = 2 * np.pi * hop * np.arange(S.shape[1]) / n_fft
    phase = np.angle(S[0])
    out = np.zeros(int(len(steps) * hop + n_fft))
    norm = np.zeros_like(out)
    for k, t in enumerate(steps):
        i = int(t); frac = t - i
        mag = (1 - frac) * np.abs(S[i]) + frac * np.abs(S[i + 1])
        frame = np.fft.irfft(mag * np.exp(1j * phase), n_fft) * win
        out[k * hop:k * hop + n_fft] += frame
        norm[k * hop:k * hop + n_fft] += win * win
        dphi = np.angle(S[i + 1]) - np.angle(S[i]) - omega
        dphi -= 2 * np.pi * np.round(dphi / (2 * np.pi))
        phase = phase + omega + dphi
    out = out / np.maximum(norm, 1e-8)
    trim = int(n_fft / rate)
    y = out[trim: trim + int(round(len(x) / rate))]
    return y


def pitch_shift(x, semitones):
    """Change pitch by `semitones` without changing duration (stretch by the ratio, then resample back)."""
    x = np.asarray(x, dtype=np.float64)
    r = 2.0 ** (float(semitones) / 12.0)
    y = stretch(x, 1.0 / r)
    n = x.shape[0]
    src = np.linspace(0, y.shape[0] - 1, n)
    if y.ndim == 1:
        return np.interp(src, np.arange(y.shape[0]), y)
    return np.stack([np.interp(src, np.arange(y.shape[0]), y[:, c]) for c in range(y.shape[1])], axis=1)


def open_window(app=None):
    from PyQt6.QtCore import QObject, Qt, pyqtSignal
    from PyQt6.QtWidgets import (QComboBox, QDoubleSpinBox, QFileDialog, QHBoxLayout, QLabel, QPushButton, QTextEdit,
                                 QVBoxLayout, QWidget)

    class _S(QObject):
        msg = pyqtSignal(str)
    w = QWidget(app, Qt.WindowType.Window) if app is not None else QWidget()
    w.setWindowTitle("📏 Loudness · true peak · normalise · time-stretch · pitch-shift"); w.resize(700, 420)
    lay = QVBoxLayout(w)
    state = {"path": None}
    row = QHBoxLayout(); lay.addLayout(row)
    b_open = QPushButton("Open audio…"); b_buf = QPushButton("📼 Live buffer"); lbl = QLabel("no file")
    for x in (b_open, b_buf, lbl):
        row.addWidget(x)
    row.addStretch(1)
    out = QTextEdit(); out.setReadOnly(True); lay.addWidget(out, 1)
    r2 = QHBoxLayout(); lay.addLayout(r2)
    tgt = QComboBox(); tgt.addItems(["-14 LUFS (streaming)", "-16 LUFS (podcast / Apple)", "-23 LUFS (broadcast)"])
    b_norm = QPushButton("Normalise → WAV")
    tempo = QDoubleSpinBox(); tempo.setRange(25, 400); tempo.setValue(100); tempo.setSuffix(" % tempo")
    semi = QDoubleSpinBox(); semi.setRange(-24, 24); semi.setValue(0); semi.setSuffix(" semitones")
    b_str = QPushButton("Stretch / pitch → WAV")
    for x in (tgt, b_norm, tempo, semi, b_str):
        r2.addWidget(x)
    sig = _S(w); sig.msg.connect(out.append)

    def _load():
        import live_master as _lm
        sr, x = _lm._load_audio(state["path"])
        return sr, x

    def _bg(fn):
        threading.Thread(target=lambda: _safe(fn), name="audio-tools", daemon=True).start()

    def _safe(fn):
        try:
            fn()
        except Exception as exc:
            sig.msg.emit("⚠ %s" % exc)

    def _measure():
        sr, x = _load()
        i = loudness(x, sr)
        sig.msg.emit("%s\n  integrated %.1f LUFS · short-term max %.1f LUFS · LRA %.1f LU · true peak %.2f dBTP · "
                     "sample peak %.2f dBFS · %.1f s" % (os.path.basename(state["path"]), i["integrated"],
                                                         i["short_term_max"], i["lra"], i["true_peak_dbtp"],
                                                         i["sample_peak_db"], x.shape[0] / float(sr)))

    def _set(path):
        state["path"] = path; lbl.setText(os.path.basename(path)); out.append("measuring…"); _bg(_measure)

    def _open():
        p, _f = QFileDialog.getOpenFileName(w, "Audio", os.path.expanduser("~"),
                                            "Audio (*.wav *.flac *.mp3 *.ogg *.mgr *.m4a);;All files (*)")
        if p:
            _set(p)

    def _buf():
        try:
            import live_buffer as _lb
            p = _lb.current_path(app)
        except Exception:
            p = None
        if p:
            wav = p + ".wav"
            import live_buffer as _lb, live_master as _lm
            x, sr = _lb.read_raw(p); _lm._write_wav24(wav, sr, x); _set(wav)
        else:
            out.append("the live buffer is not ready yet")

    def _norm():
        t = float(tgt.currentText().split()[0])
        def job():
            import live_master as _lm
            sr, x = _load()
            y, info = normalize(x, sr, t)
            dst = os.path.splitext(state["path"])[0] + "_%dLUFS.wav" % int(-t)
            _lm._write_wav24(dst, sr, y)
            sig.msg.emit("✔ %s (was %.1f LUFS)" % (dst, info["integrated"]))
        if state["path"]:
            _bg(job)

    def _stretch():
        rt, st = tempo.value() / 100.0, semi.value()
        def job():
            import live_master as _lm
            sr, x = _load()
            y = stretch(x, rt) if abs(rt - 1.0) > 1e-6 else np.asarray(x, dtype=np.float64)
            if abs(st) > 1e-6:
                y = pitch_shift(y, st)
            dst = os.path.splitext(state["path"])[0] + "_t%d_p%+g.wav" % (int(rt * 100), st)
            _lm._write_wav24(dst, sr, np.clip(y, -1.0, 1.0))
            sig.msg.emit("✔ %s" % dst)
        if state["path"]:
            _bg(job)
    b_open.clicked.connect(_open); b_buf.clicked.connect(_buf); b_norm.clicked.connect(_norm); b_str.clicked.connect(_stretch)
    w.show()
    if app is not None:
        app._audio_tools_window = w
    return w
