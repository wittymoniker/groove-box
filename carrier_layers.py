"""carrier_layers.py — LAYERS for the global carrier and for every instrument carrier.

Each import is a layer placed on the playlist: start row, length in rows (0 = its natural length), time-stretch
(phase vocoder, pitch kept), pitch shift, gain, offset into the file, loop, reverse, fade, mute / solo. Layers are
mixed relative to each other into one carrier per target (the global carrier, or an instrument's carrier sample)
and that mix is what the existing carrier paths render, so Play, Live Player and every export hear the same layers.
State: app.r99_carrier_layers = {"global": [layer…], "<instrument>": [layer…]} (saved with the project).
"""
from __future__ import annotations
import os
import numpy as np

SR = 48000


def state(app):
    st = getattr(app, "r99_carrier_layers", None)
    if not isinstance(st, dict):
        st = app.r99_carrier_layers = {}
    return st


def _row_seconds(app):
    try:
        return float(app.spin_row_beats.value()) * 60.0 / max(1.0, float(app.spin_bpm.value()))
    except Exception:
        return 2.0


_DEC = {}


def _decode(app, path):
    key = (path, os.path.getmtime(path) if os.path.isfile(path) else 0)
    if key not in _DEC:
        a, sr = app._decode_media_audio(path)
        a = np.asarray(a, dtype=np.float32)
        a = a.mean(axis=1) if a.ndim > 1 else a
        if int(sr) != SR and a.size > 1:
            n = int(round(a.size * SR / float(sr)))
            a = np.interp(np.linspace(0, a.size - 1, n), np.arange(a.size), a).astype(np.float32)
        if len(_DEC) > 16:
            _DEC.clear()
        _DEC[key] = a
    return _DEC[key]


def render_layer(app, L, total):
    import audio_tools as at
    a = _decode(app, L["path"])
    off = int(float(L.get("offset_s", 0.0)) * SR)
    a = a[max(0, off):]
    if L.get("reverse"):
        a = a[::-1]
    st = float(L.get("stretch", 1.0) or 1.0)
    if abs(st - 1.0) > 1e-3 and a.size > 4096:
        a = at.stretch(a, 1.0 / st).astype(np.float32)      # stretch 2.0 = twice as long
    ps = float(L.get("pitch", 0.0) or 0.0)
    if abs(ps) > 1e-3 and a.size > 4096:
        a = at.pitch_shift(a, ps).astype(np.float32)
    rs = _row_seconds(app)
    start = int(float(L.get("start_row", 0)) * rs * SR)
    length = int(float(L.get("rows", 0) or 0) * rs * SR) or a.size
    if L.get("loop") and a.size:
        reps = int(np.ceil(length / a.size)); a = np.tile(a, max(1, reps))
    a = a[:length]
    fade = int(float(L.get("fade_s", 0.01)) * SR)
    if fade > 0 and a.size > 2 * fade:
        r = np.linspace(0, 1, fade, dtype=np.float32); a = a.copy(); a[:fade] *= r; a[-fade:] *= r[::-1]
    out = np.zeros(total, dtype=np.float32)
    end = min(total, start + a.size)
    if end > start:
        out[start:end] = a[:end - start] * float(L.get("gain", 1.0))
    return out


def mix(app, target):
    layers = [L for L in state(app).get(target, []) if L.get("path") and os.path.isfile(L["path"])]
    if not layers:
        return None
    solo = [L for L in layers if L.get("solo")]
    use = [L for L in (solo or layers) if not L.get("mute")]
    rs = _row_seconds(app)
    rows = max([float(L.get("start_row", 0)) + (float(L.get("rows", 0) or 0) or len(_decode(app, L["path"])) / SR / rs) for L in layers] + [1.0])
    total = int(rows * rs * SR) + SR
    y = np.zeros(total, dtype=np.float32)
    for L in use:
        y += render_layer(app, L, total)
    pk = float(np.max(np.abs(y))) if y.size else 0.0
    if pk > 1.0:
        y /= pk
    return y


def apply(app, target=None):
    """Mix the layers of one target (or all) into the carrier the renderer already reads."""
    targets = [target] if target else list(state(app))
    done = []
    for t in targets:
        y = mix(app, t)
        if y is None:
            continue
        if t == "global":
            app.imported_waveform = y; app.imported_sample_rate = SR; app.imported_wav_path = "layers://global"
            try: app._refresh_after_file_input(reason="carrier_layers")
            except Exception: pass
        else:
            prev = (getattr(app, "instrument_media_samples", {}) or {}).get(t, {}) or {}
            app.instrument_media_samples[t] = {**prev, "path": "layers://" + t, "sample_rate": SR, "waveform": y,
                                               "user_owned": True, "source_kind": "audio"}
        done.append(t)
    app._shared_mixdown_cache = {}
    try: app._on_live_source_changed()
    except Exception: pass
    return done


def open_window(app):
    from PyQt6.QtCore import Qt, QRectF
    from PyQt6.QtGui import QPainter, QColor
    from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QComboBox, QPushButton, QTableWidget, QDoubleSpinBox,
                                 QCheckBox, QFileDialog, QLabel, QWidget, QHeaderView, QTableWidgetItem)
    d = QDialog(app); d.setWindowTitle("🎞 Carrier layers"); d.resize(1180, 600); d.setWindowModality(Qt.WindowModality.NonModal)
    lay = QVBoxLayout(d)
    top = QHBoxLayout(); lay.addLayout(top)
    tgt = QComboBox(); tgt.addItem("Global carrier", "global")
    for n in getattr(app, "instrument_names_48", []) or []:
        tgt.addItem("Instrument · " + (app.instrument_label(n) if hasattr(app, "instrument_label") else n), n)
    top.addWidget(QLabel("Layers of")); top.addWidget(tgt, 1)
    b_add = QPushButton("＋ Import layer…"); b_del = QPushButton("− Remove selected"); b_apply = QPushButton("✔ Mix into carrier")
    for b in (b_add, b_del, b_apply): top.addWidget(b)

    class Lanes(QWidget):
        def paintEvent(self, _e):
            p = QPainter(self); p.fillRect(self.rect(), QColor("#0b1622"))
            rows_n = max(1, len([r for r in (app.master_playlist_data or []) if r]))
            W, H = self.width(), self.height(); cw = W / rows_n
            p.setPen(QColor("#1d3446"))
            for i in range(rows_n + 1): p.drawLine(int(i * cw), 0, int(i * cw), H)
            ls = state(app).get(tgt.currentData(), [])
            lh = H / max(1, len(ls))
            rs = _row_seconds(app)
            for i, L in enumerate(ls):
                n = float(L.get("rows", 0) or 0)
                if not n:
                    try: n = len(_decode(app, L["path"])) / SR / rs * float(L.get("stretch", 1.0))
                    except Exception: n = 1
                col = QColor.fromHsv((i * 67) % 360, 160 if not L.get("mute") else 40, 220)
                p.fillRect(QRectF(float(L.get("start_row", 0)) * cw, i * lh + 2, max(3, n * cw), lh - 4), col)
                p.setPen(QColor("#06121c")); p.drawText(QRectF(float(L.get("start_row", 0)) * cw + 4, i * lh + 2, 400, lh - 4),
                                                       Qt.AlignmentFlag.AlignVCenter, os.path.basename(L["path"]))
            p.end()
    lanes = Lanes(); lanes.setMinimumHeight(160); lay.addWidget(lanes)
    cols = ("file", "start row", "rows (0 = natural)", "stretch ×", "pitch st", "gain", "offset s", "fade s", "loop", "reverse", "mute", "solo")
    tab = QTableWidget(0, len(cols)); tab.setHorizontalHeaderLabels(cols); tab.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    lay.addWidget(tab, 1)
    info = QLabel("Stretch keeps pitch; pitch keeps length. Layers mix relative to each other, then the mix is the carrier."); lay.addWidget(info)

    def fill():
        ls = state(app).get(tgt.currentData(), []); tab.setRowCount(0)
        for i, L in enumerate(ls):
            tab.insertRow(i); tab.setItem(i, 0, QTableWidgetItem(os.path.basename(L["path"])))
            for c, (key, lo, hi, step) in enumerate((("start_row", 0, 100000, 0.25), ("rows", 0, 100000, 0.25), ("stretch", 0.1, 8, 0.05),
                                                     ("pitch", -24, 24, 0.5), ("gain", 0, 4, 0.05), ("offset_s", 0, 36000, 0.1), ("fade_s", 0, 30, 0.01)), start=1):
                sp = QDoubleSpinBox(); sp.setRange(lo, hi); sp.setSingleStep(step); sp.setDecimals(3)
                sp.setValue(float(L.get(key, {"stretch": 1.0, "gain": 1.0, "fade_s": 0.01}.get(key, 0.0))))
                sp.valueChanged.connect(lambda v, L=L, key=key: (L.__setitem__(key, float(v)), lanes.update()))
                tab.setCellWidget(i, c, sp)
            for c, key in enumerate(("loop", "reverse", "mute", "solo"), start=8):
                ck = QCheckBox(); ck.setChecked(bool(L.get(key))); ck.toggled.connect(lambda v, L=L, key=key: (L.__setitem__(key, bool(v)), lanes.update()))
                tab.setCellWidget(i, c, ck)
        lanes.update()

    def add():
        paths, _ = QFileDialog.getOpenFileNames(d, "Import layers", os.path.expanduser("~"), "Media (*.wav *.flac *.mp3 *.ogg *.m4a *.aiff *.mp4 *.mov *.mkv *.webm *.MCC *.mcc)")
        if not paths: return
        try: app._push_undo("Add carrier layers")
        except Exception: pass
        ls = state(app).setdefault(tgt.currentData(), [])
        nxt = max([float(L.get("start_row", 0)) + float(L.get("rows", 0) or 0) for L in ls] + [0.0])
        for p in paths:
            ls.append({"path": p, "start_row": nxt, "rows": 0.0, "stretch": 1.0, "pitch": 0.0, "gain": 1.0, "offset_s": 0.0, "fade_s": 0.01})
        fill()

    def rem():
        rows_sel = sorted({i.row() for i in tab.selectedIndexes()}, reverse=True)
        ls = state(app).get(tgt.currentData(), [])
        for r in rows_sel:
            if r < len(ls): ls.pop(r)
        fill()

    def do_apply():
        try:
            app._push_undo("Mix carrier layers")
        except Exception:
            pass
        try:
            done = apply(app, tgt.currentData()); info.setText("mixed into: %s" % (", ".join(done) or "nothing (no layers)"))
        except Exception as exc:
            info.setText("⚠ %s" % exc)
    tgt.currentIndexChanged.connect(lambda *_: fill()); b_add.clicked.connect(add); b_del.clicked.connect(rem); b_apply.clicked.connect(do_apply)
    fill(); d.show(); app._carrier_layers_dialog = d
    return d
