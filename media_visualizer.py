"""Audio visualizer + native .MCC video player for Groovebox player windows.

GROOVEBOX_R23R_PLAYER_VISUALIZER_MCC_20261103

AudioVisualizer   — waveform overview with playhead, live oscilloscope and a
                    log-frequency spectrum, driven by any clock callable
                    (Qt player position, mpv time-pos, host file-player cursor).
MccVideoPlayer    — plays a media .MCC video exactly as written (lossless RGB
                    frames, decoded lazily) with its embedded audio on the
                    Groovebox output device; no FFmpeg needed.
"""
from __future__ import annotations

import os
import threading
import time

import numpy as np
from qt_painting import owned_painter
from PyQt6.QtCore import QObject, QPointF, QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QImage, QLinearGradient, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QSlider, QVBoxLayout, QWidget


class _DecodeBridge(QObject):
    done = pyqtSignal(object, int, str)


class AudioVisualizer(QWidget):
    """Waveform overview + scope + spectrum for an audio buffer."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(320, 180)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self._x = None            # mono float32
        self._sr = 0
        self._overview = None     # (min, max) per column bucket
        self._clock = None
        self._title = ""
        self._msg = "No audio loaded"
        self._spec_smooth = None
        self._bridge = _DecodeBridge()
        self._bridge.done.connect(self._on_decoded)
        self._gen = 0
        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self.update)
        self._win = np.hanning(2048).astype(np.float32)

    # ------------------------------------------------------------ loading
    def set_clock(self, fn):
        """fn() -> seconds (float) or None when stopped."""
        self._clock = fn
        if not self._timer.isActive():
            self._timer.start()

    def set_audio(self, x, sr, title=""):
        x = np.asarray(x, dtype=np.float32)
        if x.ndim == 2:
            x = x.mean(axis=1) if x.shape[1] > 1 else x[:, 0]
        self._x = np.ascontiguousarray(x)
        self._sr = int(sr)
        self._title = title
        self._msg = ""
        self._overview = None
        self._spec_smooth = None
        self.update()

    def load_path(self, path, decoder, title=None):
        """Decode on a worker thread; decoder(path) -> (array, sr)."""
        self._gen += 1
        gen = self._gen
        self._msg = f"Analysing {os.path.basename(path)} …"
        self._x = None
        self.update()
        br = self._bridge

        def run():
            try:
                x, sr = decoder(path)
                br.done.emit((gen, x, title or os.path.basename(path)), int(sr), "")
            except Exception as e:
                br.done.emit((gen, None, ""), 0, str(e))
        threading.Thread(target=run, daemon=True, name="groovebox-visualizer-decode").start()

    def _on_decoded(self, payload, sr, err):
        gen, x, title = payload
        if gen != self._gen:
            return
        if err or x is None:
            self._msg = f"Visualizer: {err or 'no audio'}"
            self.update()
            return
        self.set_audio(x, sr, title)

    def clear(self, msg="No audio loaded"):
        self._gen += 1
        self._x = None
        self._msg = msg
        self.update()

    def showEvent(self, e):
        super().showEvent(e)
        if self._clock is not None and not self._timer.isActive():
            self._timer.start()

    def hideEvent(self, e):
        self._timer.stop()
        super().hideEvent(e)

    # ------------------------------------------------------------ painting
    def _ensure_overview(self, cols):
        if self._x is None:
            return None
        ov = self._overview
        if ov is not None and ov[0].size == cols:
            return ov
        n = self._x.size
        if n == 0 or cols <= 0:
            return None
        edges = np.linspace(0, n, cols + 1).astype(np.int64)
        mins = np.empty(cols, np.float32); maxs = np.empty(cols, np.float32)
        for i in range(cols):
            seg = self._x[edges[i]:max(edges[i] + 1, edges[i + 1])]
            mins[i] = seg.min(); maxs[i] = seg.max()
        self._overview = (mins, maxs)
        return self._overview

    def paintEvent(self, _e):
        with owned_painter(self) as p:
            if p is None:
                return
            try:
                p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                r = self.rect()
                p.fillRect(r, QColor("#05090e"))
                W, H = r.width(), r.height()
                if self._x is None or self._x.size == 0 or not self._sr:
                    p.setPen(QColor("#6f8a99"))
                    p.drawText(r, Qt.AlignmentFlag.AlignCenter, self._msg)
                    return
                pos = None
                try:
                    pos = self._clock() if self._clock is not None else None
                except Exception:
                    pos = None
                dur = self._x.size / float(self._sr)
                t = 0.0 if pos is None else max(0.0, min(dur, float(pos)))
                idx = int(t * self._sr)
                # --- overview (top 28 %)
                oh = int(H * 0.28)
                ov = self._ensure_overview(max(1, W))
                if ov is not None:
                    mid = oh / 2.0
                    p.setPen(QPen(QColor("#2f6f8a"), 1))
                    mins, maxs = ov
                    for xpx in range(0, W):
                        p.drawLine(QPointF(xpx, mid - maxs[xpx] * mid * 0.95), QPointF(xpx, mid - mins[xpx] * mid * 0.95))
                    px = W * (t / dur if dur > 0 else 0)
                    p.fillRect(QRectF(0, 0, px, oh), QColor(0, 255, 200, 28))
                    p.setPen(QPen(QColor("#00ffcc"), 2)); p.drawLine(QPointF(px, 0), QPointF(px, oh))
                # --- oscilloscope (middle 30 %)
                sy, sh = oh + 4, int(H * 0.30)
                n = 2048
                seg = self._x[idx:idx + n]
                if seg.size < n:
                    seg = np.pad(seg, (0, n - seg.size))
                p.setPen(QPen(QColor("#1b2a35"), 1)); p.drawLine(0, sy + sh // 2, W, sy + sh // 2)
                step = max(1, n // max(1, W))
                pts = seg[::step][:W]
                path = QPainterPath()
                for i, v in enumerate(pts):
                    yy = sy + sh / 2.0 - float(v) * sh * 0.48
                    (path.moveTo if i == 0 else path.lineTo)(QPointF(i * W / max(1, len(pts) - 1), yy))
                p.setPen(QPen(QColor("#7fd8ff"), 1.4)); p.drawPath(path)
                # --- spectrum (bottom)
                by = sy + sh + 6
                bh = H - by - 18
                if bh > 10:
                    spec = np.abs(np.fft.rfft(seg * self._win))
                    freqs = np.fft.rfftfreq(n, 1.0 / self._sr)
                    bands = 64
                    edges = np.geomspace(30.0, min(20000.0, self._sr / 2.0), bands + 1)
                    vals = np.zeros(bands, np.float32)
                    for b in range(bands):
                        m = (freqs >= edges[b]) & (freqs < edges[b + 1])
                        vals[b] = spec[m].max() if m.any() else 0.0
                    _lin = vals / (n / 4.0)
                    with np.errstate(divide="ignore"):
                        db = 20.0 * np.log10(_lin)          # exact; silence = -inf dB
                    db = np.where(np.isfinite(db), db, -120.0)   # drawn at the bottom of the scale
                    lvl = np.clip((db + 72.0) / 72.0, 0.0, 1.0)
                    if self._spec_smooth is None or self._spec_smooth.size != bands:
                        self._spec_smooth = lvl
                    else:
                        self._spec_smooth = np.maximum(lvl, self._spec_smooth * 0.86)
                    bw = W / float(bands)
                    g = QLinearGradient(0, by + bh, 0, by)
                    g.setColorAt(0.0, QColor("#0d6e8a")); g.setColorAt(0.6, QColor("#00ffcc")); g.setColorAt(1.0, QColor("#ffd166"))
                    for b in range(bands):
                        hgt = float(self._spec_smooth[b]) * bh
                        p.fillRect(QRectF(b * bw + 1, by + bh - hgt, max(1.0, bw - 2), hgt), g)
                # --- caption
                p.setPen(QColor("#9fb8c6"))
                mm = lambda s: f"{int(s // 60)}:{int(s % 60):02d}"
                p.drawText(QRectF(6, H - 16, W - 12, 14), Qt.AlignmentFlag.AlignLeft,
                           f"{self._title}  ·  {mm(t)} / {mm(dur)}  ·  {self._sr / 1000:g} kHz")
            finally:
                p.end()


class _FrameView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.img = None
        self.setMinimumSize(320, 180)

    def set_frame(self, rgb):
        frame = np.asarray(rgb)
        if frame.ndim != 3 or frame.shape[2] < 3:
            raise ValueError("Video preview expects an H x W x 3 RGB image")
        h, w = frame.shape[:2]
        if h < 1 or w < 1:
            return
        frame = np.ascontiguousarray(frame[:, :, :3], dtype=np.uint8)
        # Own the pixels independently of decoder buffers and the next frame.
        self.img = QImage(frame.data, w, h, 3 * w, QImage.Format.Format_RGB888).copy()
        self.update()

    def paintEvent(self, _e):
        with owned_painter(self) as p:
            if p is None:
                return
            p.fillRect(self.rect(), QColor("#000"))
            if self.img is not None:
                s = self.img.size().scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio)
                x = (self.width() - s.width()) // 2; y = (self.height() - s.height()) // 2
                p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
                p.drawImage(QRectF(x, y, s.width(), s.height()), self.img)
            p.end()


class MccVideoPlayer(QDialog):
    """Native player for media .MCC video: exact frames + embedded audio."""

    def __init__(self, path, parent=None, host=None, volume_pct=100, play_audio=None, stop_audio=None):
        super().__init__(parent)
        import mcc_media as mm
        self._mm = mm
        self.path = str(path)
        self.host = host
        self._play_audio = play_audio      # fn(host, x, sr, path, vol) -> str
        self._stop_audio = stop_audio
        self.hdr = mm.read_header(self.path)
        self.fps = float(self.hdr.get("fps", 24.0) or 24.0)
        self.setWindowTitle(f"Groovebox MCC player · {os.path.basename(self.path)}")
        self.resize(860, 560)
        lay = QVBoxLayout(self)
        self.view = _FrameView(self); lay.addWidget(self.view, 1)
        row = QHBoxLayout()
        self.btn = QPushButton("⏸ Pause"); row.addWidget(self.btn)
        self.btn_restart = QPushButton("⏮ Restart"); row.addWidget(self.btn_restart)
        self.pos = QSlider(Qt.Orientation.Horizontal); self.pos.setEnabled(False); row.addWidget(self.pos, 1)
        self.time = QLabel("0:00"); row.addWidget(self.time)
        self.info = QLabel(""); self.info.setWordWrap(True); lay.addWidget(self.info)
        self._vol_lbl = QLabel("Vol"); row.addWidget(self._vol_lbl)
        self._vol_sl = QSlider(Qt.Orientation.Horizontal)
        self._vol_sl.setRange(0, 100); self._vol_sl.setMaximumWidth(90)
        self._vol_sl.setToolTip("Playback volume (0–100 %)")
        row.addWidget(self._vol_sl)
        lay.addLayout(row)
        self.btn.clicked.connect(self._toggle)
        self.btn_restart.clicked.connect(self.restart)
        self._vol = int(volume_pct)
        self._vol_sl.setValue(self._vol)
        self._vol_sl.valueChanged.connect(self._on_vol)
        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.setInterval(max(5, int(500 / self.fps)))
        self._timer.timeout.connect(self._tick)
        self._audio = None
        self._has_audio = bool(self.hdr.get("audio_rate"))
        self.info.setText(f"{self.hdr.get('width')}×{self.hdr.get('height')} @ {self.fps:g} fps · lossless MCC · "
                          + ("embedded audio on the Groovebox output" if self._has_audio else "no audio track"))
        self.restart()

    def _on_vol(self, v):
        self._vol = int(v)

    def _load_audio(self):
        if not self._has_audio or self._play_audio is None:
            return
        try:
            if self._audio is None:
                self._audio = self._mm.decode_audio(self.path)[:2]
            x, sr = self._audio
            note = self._play_audio(self.host, x, sr, self.path, self._vol)
            self.info.setText(self.info.text().split(" ‖ ")[0] + " ‖ " + str(note))
        except Exception as e:
            self.info.setText(self.info.text().split(" ‖ ")[0] + f" ‖ audio failed: {e}")

    def restart(self):
        self._frames = self._mm.iter_video_frames(self.path)
        self._shown = -1
        self._paused = False
        self._t0 = time.monotonic()
        self._pause_at = None
        self.btn.setText("⏸ Pause")
        self._load_audio()
        self._timer.start()

    def _elapsed(self):
        if self._pause_at is not None:
            return self._pause_at - self._t0
        return time.monotonic() - self._t0

    def _tick(self):
        want = int(self._elapsed() * self.fps)
        frame = None
        try:
            while self._shown < want:
                frame = next(self._frames)
                self._shown += 1
        except StopIteration:
            self._timer.stop()
            self.btn.setText("▶ Play again")
            self._paused = True
            self._frames = None
        except Exception as e:
            self._timer.stop()
            self.info.setText(f"MCC decode error: {e}")
        if frame is not None:
            self.view.set_frame(frame)
        s = self._elapsed()
        self.time.setText(f"{int(s // 60)}:{int(s % 60):02d}")

    def _toggle(self):
        if self._frames is None:
            self.restart()
            return
        from_file_player = None
        try:
            import performance as _pf
            from_file_player = _pf._GB_FILE_PLAYER
        except Exception:
            pass
        if self._paused:
            if self._pause_at is not None:
                self._t0 += time.monotonic() - self._pause_at
            self._pause_at = None; self._paused = False
            if from_file_player is not None:
                from_file_player.paused = False
            self._timer.start(); self.btn.setText("⏸ Pause")
        else:
            self._pause_at = time.monotonic(); self._paused = True
            if from_file_player is not None:
                from_file_player.paused = True
            self._timer.stop(); self.btn.setText("▶ Play")

    def closeEvent(self, e):
        self._timer.stop()
        if self._stop_audio is not None and self._has_audio:
            try:
                self._stop_audio()
            except Exception:
                pass
        super().closeEvent(e)
