"""CLIP_STUDIO_R31: richer controls + a Performance tab for the Multitrack Clip Studio.

TimelineStrip   painted overview of every clip by track; click selects the table row
ClipInspector   sliders / spin boxes bound to the selected row (no cell typing needed)
ClipPerformancePanel  clip-launcher pads, in-window preview, record pad hits into the timeline

All UI-thread work is light: painting a few rectangles and editing table items. Media
preview uses QMediaPlayer (its own decode threads); nothing here blocks or waits.
"""
from __future__ import annotations

import os
import time

from PyQt6.QtCore import Qt, QTimer, QRectF, QUrl, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QPen, QFont
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QFormLayout, QLabel, QPushButton,
                             QSlider, QDoubleSpinBox, QComboBox, QCheckBox, QGroupBox, QSpinBox, QSizePolicy)

# Column indices in ClipTimelineStudio.COLS
C_PATH, C_KIND, C_START, C_IN, C_OUT, C_TRACK, C_GAIN, C_OPAC, C_MUTE, C_PAN, C_WIDTH, C_BLEND = range(12)
TRACK_COLORS = ["#35b8ad", "#9b6cff", "#f2d17a", "#ff7a9c", "#5aa8ff", "#8ef07a", "#ffa94d", "#d07aff"]


def _f(studio, r, c, default=0.0):
    it = studio.table.item(r, c)
    try:
        return float(it.text()) if it is not None and it.text().strip() else default
    except ValueError:
        return default


def _set(studio, r, c, value):
    it = studio.table.item(r, c)
    if it is not None:
        it.setText(value if isinstance(value, str) else ("%g" % round(float(value), 4)))


class TimelineStrip(QWidget):
    """Clips drawn as bars on their tracks. Click a bar to select its table row."""

    def __init__(self, studio):
        super().__init__()
        self.studio = studio
        self.setMinimumHeight(110)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._rects = []
        self.playhead = None
        studio.table.itemChanged.connect(lambda *_: self.update())
        studio.table.itemSelectionChanged.connect(self.update)
        studio.table.model().rowsInserted.connect(lambda *_: self.update())
        studio.table.model().rowsRemoved.connect(lambda *_: self.update())

    def _span(self):
        t = self.studio.table
        end = float(self.studio.duration.value())
        for r in range(t.rowCount()):
            end = max(end, _f(self.studio, r, C_START) + max(0.0, _f(self.studio, r, C_OUT) - _f(self.studio, r, C_IN)))
        return max(1.0, end)

    def paintEvent(self, _ev):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(6, 14, 24, 230))
        t = self.studio.table
        n = t.rowCount()
        span = self._span()
        tracks = sorted({max(1, int(_f(self.studio, r, C_TRACK, 1))) for r in range(n)}) or [1]
        lane_h = max(14.0, (self.height() - 18) / max(1, len(tracks)))
        w = max(1, self.width() - 8)
        # time ruler
        p.setPen(QPen(QColor(60, 100, 130), 1))
        p.setFont(QFont("Sans", 7))
        step = max(1.0, round(span / 10.0))
        x = 0.0
        while x <= span:
            px = 4 + w * x / span
            p.drawLine(int(px), 0, int(px), self.height())
            p.drawText(int(px) + 2, 10, "%gs" % x)
            x += step
        sel = {i.row() for i in t.selectedIndexes()}
        self._rects = []
        for r in range(n):
            tr = max(1, int(_f(self.studio, r, C_TRACK, 1)))
            lane = tracks.index(tr)
            start = _f(self.studio, r, C_START)
            dur = max(0.05, _f(self.studio, r, C_OUT) - _f(self.studio, r, C_IN))
            rect = QRectF(4 + w * start / span, 14 + lane * lane_h + 1, max(3.0, w * dur / span), lane_h - 2)
            col = QColor(TRACK_COLORS[(tr - 1) % len(TRACK_COLORS)])
            muted = (t.item(r, C_MUTE).text().lower() in ("yes", "true", "1")) if t.item(r, C_MUTE) else False
            col.setAlpha(70 if muted else 190)
            p.fillRect(rect, col)
            p.setPen(QPen(QColor("#ffffff") if r in sel else QColor(0, 0, 0, 160), 2 if r in sel else 1))
            p.drawRect(rect)
            p.setPen(QColor("#06121c"))
            name = os.path.basename(t.item(r, C_PATH).text()) if t.item(r, C_PATH) else ""
            p.drawText(rect.adjusted(3, 0, -2, 0), Qt.AlignmentFlag.AlignVCenter, name)
            self._rects.append((rect, r))
        if self.playhead is not None:
            px = 4 + w * self.playhead / span
            p.setPen(QPen(QColor("#ff5050"), 2)); p.drawLine(int(px), 0, int(px), self.height())
        p.end()

    def mousePressEvent(self, ev):
        pos = ev.position()
        for rect, r in reversed(self._rects):
            if rect.contains(pos):
                self.studio.table.selectRow(r); return
        self.studio.table.clearSelection()


class ClipInspector(QGroupBox):
    """Edit the selected clip with real controls; writes back into the table cells."""

    def __init__(self, studio):
        super().__init__("Selected clip")
        self.studio = studio
        self._loading = False
        form = QFormLayout(self)
        self.name = QLabel("—"); self.name.setWordWrap(True); form.addRow(self.name)

        def dspin(lo, hi, step, suffix="", dec=3):
            s = QDoubleSpinBox(); s.setRange(lo, hi); s.setSingleStep(step); s.setDecimals(dec); s.setSuffix(suffix)
            return s
        self.start = dspin(0, 86400, 0.1, " s"); self.src_in = dspin(0, 86400, 0.1, " s"); self.src_out = dspin(0.01, 86400, 0.1, " s")
        self.track = QSpinBox(); self.track.setRange(1, 64)
        self.gain = QSlider(Qt.Orientation.Horizontal); self.gain.setRange(-600, 120)      # tenths of dB
        self.gain_lbl = QLabel("0.0 dB")
        self.pan = QSlider(Qt.Orientation.Horizontal); self.pan.setRange(-100, 100)
        self.width_s = QSlider(Qt.Orientation.Horizontal); self.width_s.setRange(0, 100)
        self.opac = QSlider(Qt.Orientation.Horizontal); self.opac.setRange(0, 100)
        self.blend = QComboBox(); self.blend.addItems(list(studio.BLENDS))
        self.mute = QCheckBox("Mute")
        g = QHBoxLayout(); g.addWidget(self.gain, 1); g.addWidget(self.gain_lbl)
        for label, w in (("Timeline start", self.start), ("Source in", self.src_in), ("Source out", self.src_out),
                         ("Track / layer", self.track)):
            form.addRow(label, w)
        form.addRow("Gain", g); form.addRow("Pan L↔R", self.pan); form.addRow("Stereo width", self.width_s)
        form.addRow("Opacity", self.opac); form.addRow("Video blend", self.blend); form.addRow(self.mute)
        row = QGridLayout(); row.setSpacing(4)
        for i, (text, fn, tip) in enumerate((("◀ 0.1 s", lambda: self.nudge(-0.1), "Move earlier"), ("0.1 s ▶", lambda: self.nudge(0.1), "Move later"),
                              ("▲ Layer", lambda: self.layer(+1), "Composite higher"), ("▼ Layer", lambda: self.layer(-1), "Composite lower"),
                              ("⇥ After previous clip", self.snap_after_previous, "Start right after the previous clip on this track"))):
            b = QPushButton(text); b.setToolTip(tip); b.clicked.connect(fn); b.setStyleSheet("padding:4px 6px;")
            row.addWidget(b, i // 2, i % 2, 1, 2 if i == 4 else 1)
        form.addRow(row)
        for w in (self.start, self.src_in, self.src_out):
            w.valueChanged.connect(self._write)
        self.track.valueChanged.connect(self._write)
        for s in (self.gain, self.pan, self.width_s, self.opac):
            s.valueChanged.connect(self._write)
        self.blend.currentTextChanged.connect(self._write); self.mute.toggled.connect(self._write)
        studio.table.itemSelectionChanged.connect(self.load)
        self.setEnabled(False)

    def row(self):
        rows = sorted({i.row() for i in self.studio.table.selectedIndexes()})
        return rows[0] if rows else -1

    def load(self):
        r = self.row()
        self.setEnabled(r >= 0)
        if r < 0:
            self.name.setText("—"); return
        s, t = self.studio, self.studio.table
        self._loading = True
        try:
            self.name.setText(os.path.basename(t.item(r, C_PATH).text()))
            self.start.setValue(_f(s, r, C_START)); self.src_in.setValue(_f(s, r, C_IN)); self.src_out.setValue(_f(s, r, C_OUT, 1))
            self.track.setValue(int(_f(s, r, C_TRACK, 1)))
            self.gain.setValue(int(round(_f(s, r, C_GAIN) * 10))); self.gain_lbl.setText("%.1f dB" % _f(s, r, C_GAIN))
            self.pan.setValue(int(round(_f(s, r, C_PAN) * 100))); self.width_s.setValue(int(round(_f(s, r, C_WIDTH, 1) * 100)))
            self.opac.setValue(int(round(_f(s, r, C_OPAC, 1) * 100)))
            b = t.item(r, C_BLEND).text() if t.item(r, C_BLEND) else "over"
            self.blend.setCurrentText(b if b in s.BLENDS else "over")
            self.mute.setChecked(t.item(r, C_MUTE).text().lower() in ("yes", "true", "1") if t.item(r, C_MUTE) else False)
        finally:
            self._loading = False

    def _write(self, *_):
        if self._loading:
            return
        r = self.row()
        if r < 0:
            return
        s = self.studio
        if self.src_out.value() <= self.src_in.value():
            self.src_out.setValue(self.src_in.value() + 0.05)
        s.table.blockSignals(True)
        try:
            _set(s, r, C_START, self.start.value()); _set(s, r, C_IN, self.src_in.value()); _set(s, r, C_OUT, self.src_out.value())
            _set(s, r, C_TRACK, str(self.track.value())); _set(s, r, C_GAIN, self.gain.value() / 10.0)
            _set(s, r, C_PAN, self.pan.value() / 100.0); _set(s, r, C_WIDTH, self.width_s.value() / 100.0)
            _set(s, r, C_OPAC, self.opac.value() / 100.0); _set(s, r, C_BLEND, self.blend.currentText())
            _set(s, r, C_MUTE, "Yes" if self.mute.isChecked() else "No")
        finally:
            s.table.blockSignals(False)
        self.gain_lbl.setText("%.1f dB" % (self.gain.value() / 10.0))
        s._update_estimate()
        if getattr(s, "strip", None) is not None:
            s.strip.update()

    def nudge(self, d):
        self.start.setValue(max(0.0, self.start.value() + d))

    def layer(self, d):
        self.track.setValue(max(1, self.track.value() + d))

    def snap_after_previous(self):
        r = self.row()
        if r < 0:
            return
        s = self.studio
        tr, me = int(_f(s, r, C_TRACK, 1)), _f(s, r, C_START)
        ends = [_f(s, o, C_START) + _f(s, o, C_OUT) - _f(s, o, C_IN) for o in range(s.table.rowCount())
                if o != r and int(_f(s, o, C_TRACK, 1)) == tr and _f(s, o, C_START) <= me]
        self.start.setValue(max(ends) if ends else 0.0)


class _Pad(QPushButton):
    def __init__(self, idx):
        super().__init__()
        self.idx = idx
        self.setMinimumSize(120, 70)
        self.setMaximumHeight(120)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)


class ClipPerformancePanel(QWidget):
    """Clip launcher: pads per timeline clip, live preview, record hits into new timeline rows."""
    hit = pyqtSignal(int)

    def __init__(self, studio):
        super().__init__()
        self.studio = studio
        self._rec = False
        self._rec_t0 = 0.0
        self._events = []
        self._stop_at = None
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("PERFORMANCE · launch clips live. Arm ⏺ Record to write every pad hit into the timeline "
                             "at the moment you played it (originals stay untouched)."))
        top = QHBoxLayout()
        self.b_rec = QPushButton("⏺ Record performance"); self.b_rec.setCheckable(True); self.b_rec.toggled.connect(self._rec_toggled)
        self.b_rec.setStyleSheet("QPushButton:checked{background:#c0283c;color:white;}")
        self.b_stop = QPushButton("■ Stop preview"); self.b_stop.clicked.connect(self.stop)
        self.quant = QDoubleSpinBox(); self.quant.setRange(0.0, 8.0); self.quant.setSingleStep(0.125); self.quant.setDecimals(3)
        self.quant.setSuffix(" s grid"); self.quant.setSpecialValueText("no quantize")
        self.track_base = QSpinBox(); self.track_base.setRange(1, 64); self.track_base.setValue(10); self.track_base.setPrefix("rec → track ")
        self.choke = QCheckBox("Choke (one clip at a time)"); self.choke.setChecked(True)
        self.rec_lbl = QLabel("")
        # R32.5: loop, follow actions, BPM-synced grid, pad gain.
        from PyQt6.QtWidgets import QComboBox
        self.loop = QCheckBox("Loop clip"); self.loop.setToolTip("Restart the clip at its out point")
        self.follow = QComboBox(); self.follow.addItems(["follow: stop", "follow: next", "follow: previous", "follow: random", "follow: same"])
        self.bpm = QDoubleSpinBox(); self.bpm.setRange(0, 300); self.bpm.setSpecialValueText("grid in s"); self.bpm.setSuffix(" BPM")
        self.bpm.setToolTip("With a BPM, the quantize grid is in beats instead of seconds")
        self.gain = QSlider(Qt.Orientation.Horizontal); self.gain.setRange(0, 150); self.gain.setValue(100); self.gain.setMaximumWidth(90)
        self.gain.setToolTip("Pad gain (recorded with each hit)")
        for w in (self.b_rec, self.b_stop, self.quant, self.track_base, self.choke, self.loop, self.follow, self.bpm, self.gain, self.rec_lbl):
            top.addWidget(w)
        top.addStretch(1)
        lay.addLayout(top)
        body = QHBoxLayout()
        self.grid_holder = QWidget(); self.grid = QGridLayout(self.grid_holder); self.grid.setSpacing(6)
        _gcol = QVBoxLayout(); _gcol.addWidget(self.grid_holder); _gcol.addStretch(1)
        body.addLayout(_gcol, 3)
        self.preview_box = QVBoxLayout()
        self._player = self._video = self._audio = None
        try:
            from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
            from PyQt6.QtMultimediaWidgets import QVideoWidget
            self._player = QMediaPlayer(self); self._audio = QAudioOutput(self); self._player.setAudioOutput(self._audio)
            self._video = QVideoWidget(); self._video.setMinimumSize(320, 180); self._player.setVideoOutput(self._video)
            self.preview_box.addWidget(self._video, 1)
        except Exception as exc:
            self.preview_box.addWidget(QLabel("Preview unavailable (%s). Pads still record." % exc))
        self.vol = QSlider(Qt.Orientation.Horizontal); self.vol.setRange(0, 100); self.vol.setValue(80)
        self.vol.valueChanged.connect(lambda v: self._audio.setVolume(v / 100.0) if self._audio else None)
        self.preview_box.addWidget(QLabel("Preview volume")); self.preview_box.addWidget(self.vol)
        body.addLayout(self.preview_box, 2)
        lay.addLayout(body, 1)
        self._tick = QTimer(self); self._tick.setInterval(40); self._tick.timeout.connect(self._on_tick)
        studio.table.model().rowsInserted.connect(lambda *_: QTimer.singleShot(0, self.rebuild))
        studio.table.model().rowsRemoved.connect(lambda *_: QTimer.singleShot(0, self.rebuild))
        self._keys = "1234567890QWERTYUIOPASDFGHJKL"
        self.rebuild()

    def rebuild(self):
        while self.grid.count():
            w = self.grid.takeAt(0).widget()
            if w is not None:
                w.deleteLater()
        t = self.studio.table
        cols = 4
        for r in range(t.rowCount()):
            pad = _Pad(r)
            key = self._keys[r] if r < len(self._keys) else ""
            name = os.path.basename(t.item(r, C_PATH).text()) if t.item(r, C_PATH) else "clip"
            pad.setText("%s\n%s" % (key, name[:22]))
            tr = max(1, int(_f(self.studio, r, C_TRACK, 1)))
            pad.setStyleSheet("QPushButton{background:%s;color:#06121c;font-weight:800;border-radius:10px;}"
                              "QPushButton:pressed{background:white;}" % TRACK_COLORS[(tr - 1) % len(TRACK_COLORS)])
            pad.clicked.connect(lambda _c=False, i=r: self.launch(i))
            self.grid.addWidget(pad, r // cols, r % cols)
        if t.rowCount() == 0:
            self.grid.addWidget(QLabel("Add media on the Timeline tab; each clip becomes a pad here."), 0, 0)

    def keyPressEvent(self, ev):
        k = ev.text().upper()
        if k and k in self._keys and not ev.isAutoRepeat():
            i = self._keys.index(k)
            if i < self.studio.table.rowCount():
                self.launch(i); return
        super().keyPressEvent(ev)

    def launch(self, r):
        s = self.studio
        path = s.table.item(r, C_PATH).text() if s.table.item(r, C_PATH) else ""
        src_in, src_out = _f(s, r, C_IN), _f(s, r, C_OUT, 1)
        self._current = r
        if self._player is not None and os.path.isfile(path):
            try:
                self._audio.setVolume(self.vol.value() / 100.0 * self.gain.value() / 100.0)
            except Exception:
                pass
            self._player.stop()      # one preview player: a new launch always replaces the last one
            self._player.setSource(QUrl.fromLocalFile(path))
            self._player.setPosition(int(src_in * 1000))
            self._player.play()
            self._stop_at = src_out
            self._tick.start()
        if self._rec:
            at = time.monotonic() - self._rec_t0
            q = float(self.quant.value())
            if q > 0 and float(self.bpm.value()) > 0:
                q = q * 60.0 / float(self.bpm.value())          # grid in beats
            if q > 0:
                at = round(at / q) * q
            self._events.append((r, at))
            self._gains = getattr(self, "_gains", {}); self._gains[len(self._events) - 1] = self.gain.value() / 100.0
            self.rec_lbl.setText("%d hits recorded" % len(self._events))
        self.hit.emit(r)

    def _on_tick(self):
        if self._player is None:
            return
        pos = self._player.position() / 1000.0
        if self._stop_at is not None and pos >= self._stop_at:
            cur = getattr(self, "_current", None)
            n = self.studio.table.rowCount()
            fa = self.follow.currentIndex()
            if self.loop.isChecked() and cur is not None:
                self.launch(cur); return
            if fa and cur is not None and n:
                import random as _r
                nxt = {1: (cur + 1) % n, 2: (cur - 1) % n, 3: _r.randrange(n), 4: cur}[fa]
                self.launch(nxt); return
            self._player.pause(); self._tick.stop()
        if self._rec and getattr(self.studio, "strip", None) is not None:
            self.studio.strip.playhead = time.monotonic() - self._rec_t0; self.studio.strip.update()

    def stop(self):
        if self._player is not None:
            self._player.stop()
        self._tick.stop()

    def _rec_toggled(self, on):
        if on:
            self._events = []; self._rec_t0 = time.monotonic(); self._rec = True
            self.rec_lbl.setText("recording…"); self._tick.start()
            return
        self._rec = False
        s = self.studio
        base = int(self.track_base.value())
        recs = []
        for r, at in self._events:
            try:
                rec = s._row_data(r)
            except Exception:
                continue
            rec = dict(rec); rec["start"] = round(max(0.0, at), 3); rec["track"] = base
            try:
                _gi = self._events.index((r, at))
                if "gain" in rec or True:
                    rec["gain"] = float(getattr(self, "_gains", {}).get(_gi, 1.0)) * float(rec.get("gain", 1.0) or 1.0)
            except Exception:
                pass
            recs.append(rec)
        # a later hit on the same track cuts the earlier clip short (choke)
        if self.choke.isChecked():
            recs.sort(key=lambda d: d["start"])
            for a, b in zip(recs, recs[1:]):
                a["out"] = max(a["in"] + 0.05, min(a["out"], a["in"] + (b["start"] - a["start"])))
        for rec in recs:
            s._add_row(rec)
        if recs:
            end = max(d["start"] + d["out"] - d["in"] for d in recs)
            if end > s.duration.value():
                s.duration.setValue(round(end + 0.5, 3))
        if getattr(s, "strip", None) is not None:
            s.strip.playhead = None; s.strip.update()
        self.rec_lbl.setText("Wrote %d clip(s) to track %d" % (len(recs), base))
