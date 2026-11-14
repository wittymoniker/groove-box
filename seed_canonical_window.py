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
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QTabWidget, QPlainTextEdit, QPushButton, QLabel, QGridLayout,
                             QDoubleSpinBox, QSpinBox, QComboBox, QFileDialog, QFormLayout)

import spectral_canonical as sc
import video_canonical as vc

_WINDOW = None   # strong ref when opened without a host (otherwise the window is garbage-collected at once)


def _button_grid(items, cols=4):
    g = QGridLayout(); g.setHorizontalSpacing(6); g.setVerticalSpacing(6)
    for i, (text, fn) in enumerate(items):
        b = QPushButton(text); b.clicked.connect(fn); g.addWidget(b, i // cols, i % cols)
    for c in range(cols):
        g.setColumnStretch(c, 1)
    return g


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
        tabs.addTab(self._algebra_tab(), "🧩 Seed algebra")
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
        v.addLayout(_button_grid((("Analyse audio file → seed…", self._a_analyse), ("Load seed file…", lambda: self._load_seed(self.a_seed)),
                                  ("Save seed…", lambda: self._save_seed(self.a_seed)), ("▶ Generate", self._a_generate),
                                  ("✓ Verify round trip", self._a_verify), ("Export float WAV…", self._a_export),
                                  ("Use as carrier", self._a_carrier))))
        v.addStretch(1)
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
            x = None
            if host is not None and not p.lower().endswith((".wav", ".wave")):
                try:
                    x, sr = host._decode_media_audio(p)
                    x, sr = sc.coerce_signal(x, int(sr))      # (ch, n) float, any dtype / layout
                except Exception:
                    x = None
            if x is None:                                       # wav (any int/float dtype, uint8 centred) or FFmpeg
                import seed_tools
                x, sr, _ = seed_tools.load_signal(p)
            return sc.analyse(x, int(sr)), np.asarray(x, dtype=np.float32), int(sr)

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

    # ------------------------------------------------------------- seed algebra
    def _algebra_tab(self):
        w = QWidget(); v = QVBoxLayout(w)
        info = QLabel("Every file is a seed and every seed is a file. Exact seeds (MGLB1:) rebuild any file bit-for-bit; "
                      "the common seed is the timbre all chosen files share (fuzzy AND of their spectra); a difference "
                      "seed (MGLD1:) holds exactly what changed from A to B and where.")
        info.setWordWrap(True); v.addWidget(info)
        self.g_seed = QPlainTextEdit(); self.g_seed.setPlaceholderText("Result seed appears here (any seed can be pasted too)")
        self.g_seed.setMaximumHeight(140); v.addWidget(self.g_seed)
        v.addLayout(_button_grid((("File → exact seed…", self._g_file_seed), ("File → signal seed…", lambda: self._g_file_seed("signal")),
                                  ("Exact seed → file…", self._g_seed_file), ("Common seed of files…", self._g_common),
                                  ("Difference seed A → B…", self._g_diff), ("Apply difference to A…", self._g_apply),
                                  ("Send to audio tab", self._g_to_audio), ("Save seed…", lambda: self._save_seed(self.g_seed)),
                                  ("🎬 Seed → 1080p video + sound…", self._g_render_av)), cols=4))
        self.g_info = QPlainTextEdit(); self.g_info.setReadOnly(True); self.g_info.setMaximumHeight(110)
        v.addWidget(self.g_info); v.addStretch(1)
        return w

    def _g_done(self, label):
        def done(r, e):
            if e:
                self._status(f"{label} failed: {e}"); return
            seed, info = r
            if seed is not None:
                self.g_seed.setPlainText(seed)
            self.g_info.setPlainText(info); self._status(f"{label}: done.")
        return done

    def _g_file_seed(self, mode="exact"):
        p, _ = QFileDialog.getOpenFileName(self, "Any file", "", "All files (*)")
        if not p:
            return
        import seed_tools

        def work():
            s = seed_tools.file_to_seed(p, mode=mode)
            return s, f"{os.path.basename(p)}: {os.path.getsize(p):,} bytes → {seed_tools.seed_kind(s)} seed of {len(s):,} characters"
        _run(self, "File → seed", work, self._g_done("File → seed"))

    def _g_seed_file(self):
        seed = self._seed_text(self.g_seed)
        d = QFileDialog.getExistingDirectory(self, "Rebuild the file into…") if seed else ""
        if not d:
            self._status("Paste an MGLB1: seed and choose a folder."); return
        import seed_tools
        _run(self, "Seed → file", lambda: (None, "Rebuilt (SHA-256 verified): " + seed_tools.seed_to_file(seed, d)),
             self._g_done("Seed → file"))

    def _g_common(self):
        ps, _ = QFileDialog.getOpenFileNames(self, "Files to intersect (2 or more)", "", "All files (*)")
        if not ps:
            return
        import seed_tools
        secs = float(self.a_secs.value())

        def work():
            c = seed_tools.find_common(ps, seconds=min(secs, 600.0))
            return c["seed"], (f"{c['inputs']} files · shared spectral energy {c['shared_energy'] * 100:.1f} % · "
                               f"strongest common partial {c['peak_hz']:.0f} Hz · {min(secs, 600.0):.1f} s literal seed")
        _run(self, "Common seed", work, self._g_done("Common seed"))

    def _g_diff(self):
        a, _ = QFileDialog.getOpenFileName(self, "File A (before)", "", "All files (*)")
        b, _ = QFileDialog.getOpenFileName(self, "File B (after)", os.path.dirname(a), "All files (*)") if a else ("", "")
        if not (a and b):
            return
        import seed_tools
        _run(self, "Difference seed", lambda: (lambda r: (r[0], f"A → B differs at {r[1]}"))(seed_tools.diff_to_seed(a, b)),
             self._g_done("Difference seed"))

    def _g_apply(self):
        seed = self._seed_text(self.g_seed)
        a, _ = QFileDialog.getOpenFileName(self, "File A to apply the difference to", "", "All files (*)") if seed else ("", "")
        if not a:
            self._status("Paste an MGLD1: seed and choose A."); return
        import seed_tools

        def work():
            r = seed_tools.apply_diff(a, seed)
            root, ext = os.path.splitext(a)
            if isinstance(r, bytes):
                out = root + ".patched" + ext
                with open(out, "wb") as f:
                    f.write(r)
            else:
                from scipy.io import wavfile
                x, sr = r; out = root + ".patched.wav"
                wavfile.write(out, int(sr), np.ascontiguousarray(x.T.astype(np.float32)))
                self._audio = (x.astype(np.float32), sr)
            return None, "Wrote " + out
        _run(self, "Apply difference", work, self._g_done("Apply difference"))

    def _g_render_av(self):
        """SEED_AV_RENDER_R6: the seed (or any text) → 1080p30 MP4 with sound, with the context field reading the music."""
        seed = self._seed_text(self.g_seed) or self._seed_text(self.a_seed)
        if not seed:
            self._status("Paste or generate a seed first."); return
        import seed_tools
        if seed_tools.seed_kind(seed) in ("difference", "literal-bytes", "literal-audio", "literal-video"):
            self._status("Use a generative seed (or any text) for a rendered video."); return
        p, _ = QFileDialog.getSaveFileName(self, "Save video", "seed-video.mp4", "MP4 video (*.mp4)")
        if not p:
            return
        secs = max(2.0, min(120.0, float(self.a_secs.value())))

        def work():
            r = seed_tools.render_av(seed, p, seconds=secs, size=(1920, 1080), fps=30)
            return None, f"Wrote {r['path']} · {r['frames']} frames · 1920×1080 · {r['seconds']:.1f} s · seed {r['seed_sha256']}"
        _run(self, "Rendering 1080p video", work, self._g_done("Render video"))

    def _g_to_audio(self):
        seed = self._seed_text(self.g_seed)
        if not seed:
            return
        import seed_tools
        kind = seed_tools.seed_kind(seed)
        if kind == "difference":
            self._status("A difference seed needs its A — use “Apply difference to A…”."); return
        if kind == "literal-bytes":                     # the file's bytes, read as a signal → exact spectral seed
            _run(self, "Converting", lambda: sc.analyse(*seed_tools.load_signal(seed)[:2]),
                 lambda r, e: (self.a_seed.setPlainText(r), self._status("Byte seed converted to a spectral seed — press ▶ Generate."))
                 if e is None else self._status(f"Convert failed: {e}"))
            return
        self.a_seed.setPlainText(seed); self._status("Seed copied to the Spectral tab — press ▶ Generate there.")

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
        v.addLayout(_button_grid((("Analyse video file → seed…", self._v_analyse), ("Load seed file…", lambda: self._load_seed(self.v_seed)),
                                  ("Save seed…", lambda: self._save_seed(self.v_seed)), ("▶ Generate", self._v_generate),
                                  ("✓ Verify round trip", self._v_verify), ("Export video…", self._v_export)), cols=3))
        v.addStretch(1)
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
        codec = ["-c:v", "ffv1"] if p.lower().endswith(".mkv") else \
            ["-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "16"]   # yuv420p needs even sizes

        def work():
            r = subprocess.run([ff, "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}",
                                "-framerate", str(fps), "-i", "-", *codec, p], input=np.ascontiguousarray(fr).tobytes(),
                               capture_output=True, timeout=36000)
            if r.returncode != 0:
                raise RuntimeError(r.stderr.decode(errors="replace")[-300:])
            return p
        _run(self, "Exporting video", work, lambda r, e: self._status(f"Wrote {r}" if e is None else f"Export failed: {e}"))


def open_window(host=None):
    global _WINDOW
    w = getattr(host, "_seed_canonical_window", None) if host is not None else _WINDOW
    try:
        if w is not None:
            w.isVisible()
    except RuntimeError:
        w = None
    if w is None:
        w = SeedCanonicalWindow(host)
        if host is not None:
            host._seed_canonical_window = w
        else:
            _WINDOW = w
    w.show(); w.raise_()
    return w
