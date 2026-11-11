"""SEED_CANONICAL_UI_R31: Spectral (audio) and Pixel (video) seed canonicals — analyse, generate, verify, use.

Audio: analyse any audio file → literal seed (.gbseed) · generate from any seed (literal or generative, any length)
       · verify the round trip · export 32-bit float WAV · load the result as the composition's carrier.
Video: analyse a video (decoded at a chosen size) → literal seed · generate from any seed · verify · export a
       lossless FFV1 .mkv (or MP4).
Heavy work runs on a worker thread; results come back through a Qt signal.
"""
from __future__ import annotations

import os
import subprocess
import threading
import time

import numpy as np
from PyQt6.QtCore import QObject, pyqtSignal, Qt
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QPlainTextEdit, QPushButton, QLabel,
                             QDoubleSpinBox, QSpinBox, QComboBox, QFileDialog, QFormLayout)

import spectral_canonical as sc
import video_canonical as vc


class _Bridge(QObject):
    done = pyqtSignal(object, object)


def _run(widget, label, fn, on_done):
    widget._status(label + "…")
    br = widget._bridge

    def work():
        try:
            res, err = fn(), None
        except Exception as exc:
            res, err = None, exc
        br.done.emit(lambda r=res, e=err: on_done(r, e), None)
    threading.Thread(target=work, name="seed-canonical", daemon=True).start()


class SeedCanonicalWindow(QWidget):
    def __init__(self, host=None):
        super().__init__(None, Qt.WindowType.Window)
        self.host = host
        self.setWindowTitle("Spectral & Pixel Seeds")
        self.resize(900, 620)
        self._bridge = _Bridge(self)
        self._bridge.done.connect(lambda cb, _x: cb())
        self._audio = None          # (signal (ch, n), sr)
        self._video = None          # (frames, fps)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Seeds of ANY length. A literal seed (MGLS1: / MGLV1:) holds exact coefficients and "
                             "rebuilds its source exactly; any other text or number generates a signal from all its bytes."))
        tabs = QTabWidget(); lay.addWidget(tabs, 1)
        tabs.addTab(self._audio_tab(), "🔊 Spectral (audio)")
        tabs.addTab(self._video_tab(), "🎞 Pixel (video)")
        self.lbl = QLabel(""); self.lbl.setWordWrap(True); lay.addWidget(self.lbl)

    def _status(self, t):
        self.lbl.setText(t)

    # ------------------------------------------------------------- audio
    def _audio_tab(self):
        w = QWidget(); v = QVBoxLayout(w)
        self.a_seed = QPlainTextEdit(); self.a_seed.setPlaceholderText("Seed: any text / number, or a literal MGLS1: seed")
        self.a_seed.setMaximumHeight(120); v.addWidget(self.a_seed)
        f = QFormLayout()
        self.a_secs = QDoubleSpinBox(); self.a_secs.setRange(0.1, 36000.0); self.a_secs.setValue(8.0); self.a_secs.setSuffix(" s")
        self.a_sr = QComboBox(); [self.a_sr.addItem(str(r), r) for r in (44100, 48000, 96000, 192000)]; self.a_sr.setCurrentIndex(1)
        self.a_ch = QSpinBox(); self.a_ch.setRange(1, 8); self.a_ch.setValue(2)
        f.addRow("Length (generative)", self.a_secs); f.addRow("Sample rate", self.a_sr); f.addRow("Channels", self.a_ch)
        v.addLayout(f)
        row = QHBoxLayout()
        for text, fn in (("Analyse audio file → seed…", self._a_analyse), ("Load seed file…", lambda: self._load_seed(self.a_seed)),
                         ("Save seed…", lambda: self._save_seed(self.a_seed)), ("▶ Generate", self._a_generate),
                         ("✓ Verify round trip", self._a_verify), ("Export float WAV…", self._a_export),
                         ("Use as carrier", self._a_carrier)):
            b = QPushButton(text); b.clicked.connect(fn); row.addWidget(b)
        v.addLayout(row); v.addStretch(1)
        return w

    def _seed_text(self, edit):
        return edit.toPlainText().strip()

    def _load_seed(self, edit):
        p, _ = QFileDialog.getOpenFileName(self, "Load seed", "", "Groovebox seed (*.gbseed);;All files (*)")
        if p:
            with open(p, "r", encoding="utf-8") as fh:
                edit.setPlainText(fh.read())
            self._status(f"Loaded seed ({os.path.getsize(p) / 1e6:.2f} MB).")

    def _save_seed(self, edit):
        p, _ = QFileDialog.getSaveFileName(self, "Save seed", "seed.gbseed", "Groovebox seed (*.gbseed)")
        if p:
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(self._seed_text(edit))
            self._status(f"Saved {p}")

    def _a_analyse(self):
        p, _ = QFileDialog.getOpenFileName(self, "Audio to analyse", "", "Audio (*.wav *.flac *.mp3 *.ogg *.opus *.aiff *.mcc *.MCC);;All files (*)")
        if not p:
            return
        host = self.host

        def work():
            if p.lower().endswith(".wav"):
                from scipy.io import wavfile
                sr, x = wavfile.read(p)
                x = np.asarray(x)
                if x.dtype.kind in "iu":
                    x = x.astype(np.float64) / float(np.iinfo(x.dtype).max)
                x = x.T if x.ndim == 2 else x
            else:
                x, sr = host._decode_media_audio(p)
            return sc.analyse(np.asarray(x, dtype=np.float64), int(sr)), np.asarray(x, dtype=np.float32), int(sr)

        def done(r, e):
            if e:
                self._status(f"Analyse failed: {e}"); return
            seed, x, sr = r
            self.a_seed.setPlainText(seed)
            self._audio = (x if x.ndim == 2 else x[None, :], sr)
            self._status(f"Literal seed: {len(seed) / 1e6:.2f} MB for {x.shape[-1] / sr:.1f} s. Save it with “Save seed…”.")
        _run(self, "Analysing", work, done)

    def _a_generate(self):
        seed = self._seed_text(self.a_seed)
        if not seed:
            self._status("Type a seed first."); return
        kw = {} if sc.is_literal(seed) else dict(seconds=self.a_secs.value(), sample_rate=int(self.a_sr.currentData()),
                                                 channels=self.a_ch.value())

        def done(r, e):
            if e:
                self._status(f"Generate failed: {e}"); return
            self._audio = r
            x, sr = r
            self._status(f"Generated {x.shape[0]} ch × {x.shape[1] / sr:.2f} s at {sr} Hz "
                         + ("(literal: exact)" if sc.is_literal(seed) else f"(generative, seed {len(seed)} chars)"))
        _run(self, "Generating", lambda: sc.synthesize(seed, **kw), done)

    def _a_verify(self):
        if self._audio is None:
            self._status("Generate or analyse first."); return
        x, sr = self._audio

        def done(r, e):
            self._status(f"Round trip max error {r:.2e} (float32 rounding ≈ 6e-8)" if e is None else f"Verify failed: {e}")
        _run(self, "Verifying", lambda: sc.roundtrip_error(x, sr), done)

    def _a_export(self):
        if self._audio is None:
            self._status("Generate first."); return
        p, _ = QFileDialog.getSaveFileName(self, "Export float WAV", "spectral.wav", "WAV (*.wav)")
        if not p:
            return
        x, sr = self._audio
        from scipy.io import wavfile
        wavfile.write(p, int(sr), np.ascontiguousarray(x.T.astype(np.float32)))
        self._status(f"Wrote 32-bit float WAV: {p}")

    def _a_carrier(self):
        if self._audio is None or self.host is None:
            self._status("Generate first."); return
        x, sr = self._audio
        try:
            d = self.host._audio_exports_dir()
        except Exception:
            import tempfile
            d = tempfile.gettempdir()
        p = os.path.join(d, time.strftime("spectral-seed-%Y%m%d-%H%M%S.wav"))
        from scipy.io import wavfile
        wavfile.write(p, int(sr), np.ascontiguousarray(x.T.astype(np.float32)))
        try:
            self.host._load_wav_path(p)
            self._status(f"Loaded as the composition's carrier: {os.path.basename(p)}")
        except Exception as exc:
            self._status(f"Carrier load failed: {exc}")

    # ------------------------------------------------------------- video
    def _video_tab(self):
        w = QWidget(); v = QVBoxLayout(w)
        self.v_seed = QPlainTextEdit(); self.v_seed.setPlaceholderText("Seed: any text / number, or a literal MGLV1: seed")
        self.v_seed.setMaximumHeight(120); v.addWidget(self.v_seed)
        f = QFormLayout()
        self.v_w = QSpinBox(); self.v_w.setRange(16, 7680); self.v_w.setValue(320)
        self.v_h = QSpinBox(); self.v_h.setRange(16, 4320); self.v_h.setValue(180)
        self.v_n = QSpinBox(); self.v_n.setRange(1, 1000000); self.v_n.setValue(96)
        self.v_fps = QSpinBox(); self.v_fps.setRange(1, 240); self.v_fps.setValue(24)
        self.v_detail = QSpinBox(); self.v_detail.setRange(2, 512); self.v_detail.setValue(24)
        for lab, wd in (("Width", self.v_w), ("Height", self.v_h), ("Frames (generative)", self.v_n), ("FPS", self.v_fps),
                        ("Detail (coefficients per side)", self.v_detail)):
            f.addRow(lab, wd)
        v.addLayout(f)
        row = QHBoxLayout()
        for text, fn in (("Analyse video file → seed…", self._v_analyse), ("Load seed file…", lambda: self._load_seed(self.v_seed)),
                         ("Save seed…", lambda: self._save_seed(self.v_seed)), ("▶ Generate", self._v_generate),
                         ("✓ Verify round trip", self._v_verify), ("Export video…", self._v_export)):
            b = QPushButton(text); b.clicked.connect(fn); row.addWidget(b)
        v.addLayout(row); v.addStretch(1)
        return w

    def _ffmpeg(self):
        try:
            return self.host._resolve_ffmpeg_binary()
        except Exception:
            import shutil
            return shutil.which("ffmpeg")

    def _v_analyse(self):
        p, _ = QFileDialog.getOpenFileName(self, "Video to analyse", "", "Video (*.mp4 *.mkv *.webm *.mov *.avi *.MCC *.mcc);;MCC media (*.MCC *.mcc);;All files (*)")
        if not p:
            return
        ff = self._ffmpeg()
        if not ff:
            self._status("Video analysis needs the Groovebox FFmpeg."); return
        w, h, fps = self.v_w.value(), self.v_h.value(), self.v_fps.value()

        def work():
            r = subprocess.run([ff, "-v", "error", "-i", p, "-vf", f"scale={w}:{h},fps={fps}", "-f", "rawvideo",
                                "-pix_fmt", "rgb24", "-"], capture_output=True, timeout=3600)
            fr = np.frombuffer(r.stdout, dtype=np.uint8)
            n = fr.size // (w * h * 3)
            fr = fr[:n * w * h * 3].reshape(n, h, w, 3)
            return vc.analyse(fr, fps), fr

        def done(r, e):
            if e:
                self._status(f"Analyse failed: {e}"); return
            seed, fr = r
            self.v_seed.setPlainText(seed); self._video = (fr, fps)
            self._status(f"Literal video seed: {len(seed) / 1e6:.2f} MB for {fr.shape[0]} frames at {w}×{h}.")
        _run(self, "Analysing video", work, done)

    def _v_generate(self):
        seed = self.v_seed.toPlainText().strip()
        if not seed:
            self._status("Type a seed first."); return
        kw = {} if vc.is_literal(seed) else dict(frames=self.v_n.value(), width=self.v_w.value(), height=self.v_h.value(),
                                                 fps=self.v_fps.value(), detail=self.v_detail.value())

        def done(r, e):
            if e:
                self._status(f"Generate failed: {e}"); return
            self._video = r
            self._status(f"Generated {r[0].shape[0]} frames {r[0].shape[2]}×{r[0].shape[1]} @ {r[1]} fps.")
        _run(self, "Generating video", lambda: vc.synthesize(seed, **kw), done)

    def _v_verify(self):
        if self._video is None:
            self._status("Generate or analyse first."); return
        fr, fps = self._video
        _run(self, "Verifying", lambda: vc.roundtrip_exact(fr, fps),
             lambda r, e: self._status(("Round trip EXACT (every pixel identical)" if r else "Round trip differs") if e is None else f"Verify failed: {e}"))

    def _v_export(self):
        if self._video is None:
            self._status("Generate first."); return
        p, _ = QFileDialog.getSaveFileName(self, "Export video", "pixel-seed.mkv", "Lossless MKV (*.mkv);;MP4 (*.mp4)")
        if not p:
            return
        ff = self._ffmpeg()
        if not ff:
            self._status("Video export needs the Groovebox FFmpeg."); return
        fr, fps = self._video
        n, h, w, _ = fr.shape
        codec = ["-c:v", "ffv1"] if p.lower().endswith(".mkv") else ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "16"]

        def work():
            r = subprocess.run([ff, "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}",
                                "-framerate", str(fps), "-i", "-", *codec, p], input=np.ascontiguousarray(fr).tobytes(),
                               capture_output=True, timeout=36000)
            if r.returncode != 0:
                raise RuntimeError(r.stderr.decode(errors="replace")[-300:])
            return p
        _run(self, "Exporting video", work, lambda r, e: self._status(f"Wrote {r}" if e is None else f"Export failed: {e}"))


def open_window(host=None):
    w = getattr(host, "_seed_canonical_window", None) if host is not None else None
    try:
        if w is not None:
            w.isVisible()
    except RuntimeError:
        w = None
    if w is None:
        w = SeedCanonicalWindow(host)
        if host is not None:
            host._seed_canonical_window = w
    w.show(); w.raise_()
    return w
