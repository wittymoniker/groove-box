"""postprocess_window.py — GROOVEBOX_R32_POSTPROCESS_20261109

The Post-Process window: offline finishing with the five hardcoded FX only.

  * Load one or many files (WAV/FLAC/AIFF via soundfile, anything else via ffmpeg), the
    last export, or a Live Player take (``finish_take(path)``).
  * Chain in fixed order: PKP Envelope → Fractallizer (+tilt) → EQR → ∞M HyperDrive →
    Master Hard Clipper, each with its own control; all 0 = exact bypass.
  * Tools: measure (peak / RMS / crest / DC / clip density), remove DC, trim silence,
    peak-normalize, book-isn fades; a before/after loudness compare; A/B audition.
  * Batch mode: the same settings over every loaded file, rendered in the thread pool
    (never on the GUI thread), written next to the source as ``<name>.post.<ext>``.
  * Presets save/load as JSON; the "Take finisher" preset is what Live Player applies.

Only hardcoded_fx is used for DSP (audit-clean).
"""
from __future__ import annotations

import json
import os
import subprocess
import time

import numpy as np
from PyQt6.QtCore import Qt, QObject, pyqtSignal, QRunnable, QThreadPool, QTimer
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton, QListWidget,
                             QDoubleSpinBox, QCheckBox, QGroupBox, QFileDialog, QTextEdit, QComboBox, QProgressBar,
                             QSlider)

import hardcoded_fx as hfx

TAKE_FINISHER = {"pkp": 0.0, "fractal": 0.12, "tilt": 0.1, "eqr": 0.18, "hyper": 0.08, "volume": 1.0,
                 "clip_ratio": 8.0, "dc": True, "trim": True, "normalize": True, "target_peak": 0.97,
                 "fade_in": 0.004, "fade_out": 0.08}
DEFAULTS = {"pkp": 0.0, "pkp_div": 0.25, "pkp_decay": 0.5, "fractal": 0.0, "tilt": 0.0, "eqr": 0.0,
            "hyper": 0.0, "hyper_res": 0.0595, "volume": 1.0, "clip_ratio": 0.0,
            "dc": True, "trim": False, "normalize": False, "target_peak": 0.98, "fade_in": 0.0, "fade_out": 0.0}
CONTROLS = (
    ("pkp", "PKP Envelope depth", 0.0, 1.0, 0.05), ("pkp_div", "PKP division (beats)", 0.0625, 4.0, 0.0625),
    ("pkp_decay", "PKP decay", 0.0, 1.0, 0.05), ("fractal", "Fractallizer amount", 0.0, 1.0, 0.05),
    ("tilt", "Fractal tilt (sub ↔ super)", -1.0, 1.0, 0.05), ("eqr", "EQR activation", 0.0, 1.0, 0.05),
    ("hyper", "∞M HyperDrive", 0.0, 1.0, 0.05), ("hyper_res", "HyperDrive resonance", 0.0, 1.0, 0.01),
    ("volume", "Master volume", 0.0, 4.0, 0.05), ("clip_ratio", "Hard clip ratio %", 0.0, 100.0, 1.0),
    ("target_peak", "Normalize target peak", 0.1, 1.0, 0.01), ("fade_in", "Fade in (s)", 0.0, 10.0, 0.01),
    ("fade_out", "Fade out (s)", 0.0, 30.0, 0.05),
)


# ---------------------------------------------------------------------------
# IO
# ---------------------------------------------------------------------------
def read_audio(path):
    """(float32 array [n] or [n, ch], sr).  soundfile first, ffmpeg fallback."""
    try:
        import soundfile as sf
        data, sr = sf.read(path, dtype="float32", always_2d=False)
        return np.asarray(data, dtype=np.float32), int(sr)
    except Exception:
        pass
    ff = _ffmpeg()
    if not ff:
        raise RuntimeError("cannot read %s (no soundfile, no ffmpeg)" % path)
    pr = subprocess.run([ff, "-v", "quiet", "-i", path, "-f", "f32le", "-ac", "2", "-ar", "48000", "-"],
                        capture_output=True, timeout=600)
    a = np.frombuffer(pr.stdout, dtype=np.float32).reshape(-1, 2)
    return a.copy(), 48000


def write_audio(path, data, sr, subtype=None):
    import soundfile as sf
    ext = os.path.splitext(path)[1].lower()
    if ext not in (".wav", ".flac", ".aiff", ".aif", ".ogg"):
        path = os.path.splitext(path)[0] + ".wav"
    sf.write(path, np.asarray(data, dtype=np.float32), int(sr), subtype=subtype or ("PCM_24" if ext != ".ogg" else None))
    return path


def _ffmpeg():
    import shutil
    return shutil.which("ffmpeg") or ""


def _measure_lufs_like(x, sr):
    """RMS-based loudness in dBFS plus the hardcoded_fx report (no SciPy)."""
    rep = hfx.measure(x, sr)
    rms = rep["rms"]
    rep["loudness_db"] = 20.0 * np.log10(rms) if rms > 0 else -120.0
    return rep


def process(data, sr, settings, bpm=120.0, z_fn=None):
    """The whole post pass → (audio, report).  Pure function; safe on worker threads."""
    s = dict(DEFAULTS)
    s.update(settings or {})
    x = np.asarray(data, dtype=np.float32)
    before = _measure_lufs_like(x, sr)
    if s.get("dc"):
        x = hfx.remove_dc(x)
    if s.get("trim"):
        x, _, _ = hfx.trim_silence(x, sr)
    chain = {k: float(s.get(k, 0.0)) for k in ("pkp", "pkp_div", "pkp_decay", "fractal", "tilt", "eqr", "hyper", "hyper_res", "volume", "clip_ratio")}
    if any(chain[k] > 0 for k in ("pkp", "fractal", "eqr", "hyper")) or chain["volume"] != 1.0 or chain["clip_ratio"] > 0:
        x = hfx.render_chain(x, sr, chain, z_fn=z_fn, bpm=bpm)
    if s.get("normalize"):
        x, _g = hfx.peak_normalize(x, float(s.get("target_peak", 0.98)))
    if float(s.get("fade_in", 0)) > 0 or float(s.get("fade_out", 0)) > 0:
        x = hfx.isn_fade(x, sr, float(s.get("fade_in", 0)), float(s.get("fade_out", 0)))
    after = _measure_lufs_like(x, sr)
    return np.asarray(x, dtype=np.float32), {"before": before, "after": after,
                                             "delta_db": after["loudness_db"] - before["loudness_db"]}


def finish_take(path, settings=None, out_path=None, bpm=120.0):
    """Live Player take finisher: apply the Take Finisher preset to a file; returns (out_path, report)."""
    data, sr = read_audio(path)
    y, rep = process(data, sr, settings or TAKE_FINISHER, bpm=bpm)
    base, ext = os.path.splitext(path)
    out = out_path or (base + ".post" + (ext if ext.lower() in (".wav", ".flac", ".aiff") else ".wav"))
    out = write_audio(out, y, sr)
    rep["out"] = out
    return out, rep


# ---------------------------------------------------------------------------
# worker plumbing
# ---------------------------------------------------------------------------
class _Sig(QObject):
    done = pyqtSignal(object, object)       # (index, result dict)
    fail = pyqtSignal(object, str)


class _Job(QRunnable):
    def __init__(self, idx, path, settings, bpm, sig, write):
        super().__init__()
        self.setAutoDelete(True)
        self.idx, self.path, self.settings, self.bpm, self.sig, self.write = idx, path, dict(settings), bpm, sig, write

    def run(self):
        try:
            data, sr = read_audio(self.path)
            y, rep = process(data, sr, self.settings, bpm=self.bpm)
            out = ""
            if self.write:
                base, ext = os.path.splitext(self.path)
                out = write_audio(base + ".post" + (ext if ext.lower() in (".wav", ".flac", ".aiff") else ".wav"), y, sr)
            rep["out"] = out
            rep["sr"] = sr
            rep["audio"] = y if not self.write else None
            self.sig.done.emit(self.idx, rep)
        except Exception as exc:
            self.sig.fail.emit(self.idx, str(exc))


# ---------------------------------------------------------------------------
# window
# ---------------------------------------------------------------------------
class PostProcessWindow(QWidget):
    """Non-modal tool window (window_manager makes it a first-class OS window)."""

    def __init__(self, app=None, parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        self.app = app
        self.setWindowTitle("🧰 Post-Process · hardcoded FX finishing")
        self.resize(980, 640)
        self.settings = dict(DEFAULTS)
        self._sig = _Sig(self)
        self._sig.done.connect(self._on_done)
        self._sig.fail.connect(self._on_fail)
        self._pending = 0
        self._last_audio = None
        self._last_sr = 48000
        root = QHBoxLayout(self)
        # left: files
        left = QVBoxLayout()
        left.addWidget(QLabel("Files (drop, add, or take the last export)"))
        self.files = QListWidget()
        self.files.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.setAcceptDrops(True)
        left.addWidget(self.files, 1)
        fr = QHBoxLayout()
        for cap, fn in (("＋ Add…", self.add_files), ("Last export", self.add_last_export), ("－ Remove", self.remove_selected), ("Clear", self.files.clear)):
            b = QPushButton(cap); b.clicked.connect(fn); fr.addWidget(b)
        left.addLayout(fr)
        root.addLayout(left, 2)
        # middle: chain controls
        mid = QVBoxLayout()
        grp = QGroupBox("Chain · PKP → Fractallizer → EQR → ∞M HyperDrive → Hard Clipper (0 = bypass)")
        g = QGridLayout(grp)
        self.spins = {}
        for r, (key, cap, lo, hi, step) in enumerate(CONTROLS):
            lab = QLabel(cap)
            sp = QDoubleSpinBox(); sp.setRange(lo, hi); sp.setSingleStep(step); sp.setDecimals(3 if step < 0.05 else 2)
            sp.setValue(float(self.settings.get(key, 0.0))); sp.setKeyboardTracking(False)
            sp.valueChanged.connect(lambda v, k=key: self.settings.__setitem__(k, float(v)))
            self.spins[key] = sp
            g.addWidget(lab, r, 0); g.addWidget(sp, r, 1)
        mid.addWidget(grp)
        tools = QGroupBox("Tools")
        tl = QGridLayout(tools)
        self.chks = {}
        for i, (key, cap) in enumerate((("dc", "Remove DC"), ("trim", "Trim silence"), ("normalize", "Peak-normalize"))):
            c = QCheckBox(cap); c.setChecked(bool(self.settings.get(key))); c.toggled.connect(lambda v, k=key: self.settings.__setitem__(k, bool(v)))
            self.chks[key] = c; tl.addWidget(c, 0, i)
        self.cmb_preset = QComboBox(); self.cmb_preset.addItems(["Neutral", "Take finisher", "Loud master", "Gentle polish", "Rhythmic gate"])
        self.cmb_preset.currentTextChanged.connect(self._preset)
        tl.addWidget(QLabel("Preset"), 1, 0); tl.addWidget(self.cmb_preset, 1, 1)
        bsave = QPushButton("Save preset…"); bsave.clicked.connect(self.save_preset)
        bload = QPushButton("Load preset…"); bload.clicked.connect(self.load_preset)
        tl.addWidget(bsave, 1, 2); tl.addWidget(bload, 2, 2)
        self.spin_bpm = QDoubleSpinBox(); self.spin_bpm.setRange(20, 400); self.spin_bpm.setValue(float(getattr(app, "bpm", 120.0) or 120.0) if app is not None and isinstance(getattr(app, "bpm", None), (int, float)) else 120.0)
        tl.addWidget(QLabel("BPM for PKP"), 2, 0); tl.addWidget(self.spin_bpm, 2, 1)
        mid.addWidget(tools)
        act = QHBoxLayout()
        self.b_measure = QPushButton("📏 Measure"); self.b_measure.clicked.connect(lambda: self.run(write=False))
        self.b_render = QPushButton("▶ Render selected"); self.b_render.clicked.connect(lambda: self.run(write=True, selected=True))
        self.b_batch = QPushButton("⏩ Batch all"); self.b_batch.clicked.connect(lambda: self.run(write=True, selected=False))
        self.b_ab = QPushButton("🎧 A/B last"); self.b_ab.clicked.connect(self.audition)
        for b in (self.b_measure, self.b_render, self.b_batch, self.b_ab):
            act.addWidget(b)
        mid.addLayout(act)
        self.progress = QProgressBar(); self.progress.setRange(0, 100); mid.addWidget(self.progress)
        root.addLayout(mid, 3)
        # right: report
        right = QVBoxLayout()
        right.addWidget(QLabel("Before / after"))
        self.report = QTextEdit(); self.report.setReadOnly(True)
        self.report.setStyleSheet("font-family: Consolas, monospace; font-size: 9pt;")
        right.addWidget(self.report, 1)
        root.addLayout(right, 3)

    # -- files --------------------------------------------------------------
    def dragEnterEvent(self, ev):
        if ev.mimeData().hasUrls():
            ev.acceptProposedAction()

    def dropEvent(self, ev):
        for u in ev.mimeData().urls():
            p = u.toLocalFile()
            if p and os.path.isfile(p):
                self.files.addItem(p)

    def add_files(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Audio files", "", "Audio (*.wav *.flac *.aiff *.aif *.mp3 *.ogg *.opus *.m4a *.mkv *.mp4 *.MCC);;All (*)")
        for p in paths:
            self.files.addItem(p)

    def add_paths(self, paths):
        for p in paths or []:
            if p and os.path.isfile(p):
                self.files.addItem(p)

    def add_last_export(self):
        app = self.app
        cands = []
        try:
            for fn in ("_audio_exports_dir", "_exports_dir"):
                d = str(getattr(app, fn)())
                for root, _ds, fs in os.walk(d):
                    for f in fs:
                        if f.lower().endswith((".wav", ".flac", ".aiff", ".mp3", ".ogg", ".opus")) and ".post." not in f:
                            cands.append(os.path.join(root, f))
        except Exception:
            pass
        if cands:
            cands.sort(key=os.path.getmtime)
            self.files.addItem(cands[-1])
        else:
            self.report.setPlainText("No export found yet.")

    def remove_selected(self):
        for it in self.files.selectedItems():
            self.files.takeItem(self.files.row(it))

    # -- presets --------------------------------------------------------------
    def _preset(self, name):
        table = {
            "Neutral": DEFAULTS,
            "Take finisher": TAKE_FINISHER,
            "Loud master": {**DEFAULTS, "fractal": 0.2, "eqr": 0.3, "hyper": 0.25, "volume": 1.4, "clip_ratio": 35.0, "normalize": True, "target_peak": 0.99},
            "Gentle polish": {**DEFAULTS, "fractal": 0.08, "eqr": 0.1, "normalize": True, "target_peak": 0.9, "fade_in": 0.01, "fade_out": 0.5},
            "Rhythmic gate": {**DEFAULTS, "pkp": 0.7, "pkp_div": 0.25, "pkp_decay": 0.35, "hyper": 0.1},
        }
        self.set_settings(table.get(name, DEFAULTS))

    def set_settings(self, s):
        self.settings = dict(DEFAULTS); self.settings.update(s or {})
        for k, sp in self.spins.items():
            sp.blockSignals(True); sp.setValue(float(self.settings.get(k, 0.0))); sp.blockSignals(False)
        for k, c in self.chks.items():
            c.blockSignals(True); c.setChecked(bool(self.settings.get(k))); c.blockSignals(False)

    def save_preset(self):
        p, _ = QFileDialog.getSaveFileName(self, "Save post-process preset", "", "JSON (*.json)")
        if p:
            with open(p, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, indent=2)

    def load_preset(self):
        p, _ = QFileDialog.getOpenFileName(self, "Load post-process preset", "", "JSON (*.json)")
        if p:
            try:
                with open(p, encoding="utf-8") as f:
                    self.set_settings(json.load(f))
            except Exception as exc:
                self.report.setPlainText("Preset failed: %s" % exc)

    # -- run ------------------------------------------------------------------
    def run(self, write=True, selected=True):
        items = self.files.selectedItems() if selected else [self.files.item(i) for i in range(self.files.count())]
        if not items and self.files.count():
            items = [self.files.item(0)]
        if not items:
            self.report.setPlainText("Add a file first.")
            return
        self._pending = len(items)
        self._total = len(items)
        self.progress.setValue(0)
        self._reports = {}
        pool = __import__("r32_pool").pool()
        for i, it in enumerate(items):
            pool.start(_Job(i, it.text(), self.settings, float(self.spin_bpm.value()), self._sig, write))
        self.report.setPlainText("Rendering %d file(s) in the thread pool…" % len(items))

    def _on_done(self, idx, rep):
        self._pending -= 1
        self._reports[idx] = rep
        if rep.get("audio") is not None:
            self._last_audio, self._last_sr = rep["audio"], rep.get("sr", 48000)
        self.progress.setValue(int(100 * (self._total - self._pending) / max(1, self._total)))
        if self._pending <= 0:
            self._show_reports()

    def _on_fail(self, idx, msg):
        self._pending -= 1
        self._reports[idx] = {"error": msg}
        if self._pending <= 0:
            self._show_reports()

    def _show_reports(self):
        lines = []
        for idx in sorted(self._reports):
            r = self._reports[idx]
            if "error" in r:
                lines.append("#%d  ERROR  %s" % (idx + 1, r["error"]))
                continue
            b, a = r["before"], r["after"]
            lines.append("#%d  %s" % (idx + 1, os.path.basename(r.get("out") or "(measured)")))
            lines.append("     loudness  %7.2f dB → %7.2f dB   (Δ %+.2f dB)" % (b["loudness_db"], a["loudness_db"], r["delta_db"]))
            lines.append("     peak      %7.3f    → %7.3f" % (b["peak"], a["peak"]))
            lines.append("     crest     %6.2f dB → %6.2f dB" % (b["crest_db"], a["crest_db"]))
            lines.append("     DC        %+.5f   → %+.5f" % (b["dc"], a["dc"]))
            lines.append("     clipped   %5.2f %%  → %5.2f %%   length %.2fs → %.2fs" % (100 * b["clip_density"], 100 * a["clip_density"], b["seconds"], a["seconds"]))
        self.report.setPlainText("\n".join(lines) or "nothing")

    def audition(self):
        if self._last_audio is None:
            self.report.append("\nMeasure first (A/B uses the last measured file).")
            return
        try:
            import sounddevice as sd
            sd.stop()
            sd.play(self._last_audio, self._last_sr)
        except Exception as exc:
            self.report.append("\nAudition unavailable: %s" % exc)


def open_window(app):
    """Singleton accessor used by menus / quick rack."""
    win = getattr(app, "_postprocess_window", None)
    try:
        if win is not None:
            win.isVisible()
    except RuntimeError:
        win = None
    if win is None:
        win = app._postprocess_window = PostProcessWindow(app, app)
    win.show(); win.raise_(); win.activateWindow()
    return win
