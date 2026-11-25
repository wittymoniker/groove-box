"""artifacts_view.py (R132): every buffer in RAM, how complete it is, and raw / WAV export — even when incomplete.

Rows: the play buffer (filled length vs. the composition length → completion %), the shared mixdown cache, per-
instrument caches, the live scenograph frame, the latest scope chunk, every export job with its progress, and the
markers / change point. "Export raw" writes float32 little-endian (+ a .json sidecar with rate / channels / filled
samples) — nothing is lost when a render stopped half way; "Export WAV" writes 32-bit float WAV of what exists.
"""
from __future__ import annotations

import json
import os
import time

import numpy as np


def _composition_seconds(app):
    try:
        return float(app._composition_length_seconds())
    except Exception:
        return 0.0


def buffers(app):
    """[(key, label, array or None, completion 0..1 or None, note)]"""
    rows = []
    sr = int(getattr(app, "play_sample_rate", 0) or getattr(app, "sample_rate", 48000) or 48000)
    total = _composition_seconds(app) * sr
    buf = getattr(app, "play_buffer", None)
    if buf is not None:
        a = np.asarray(buf); n = int(a.shape[0])
        nz = int(np.flatnonzero(np.abs(a).reshape(n, -1).max(axis=1) > 1e-7)[-1] + 1) if n and np.any(a) else 0
        comp = min(1.0, nz / total) if total > 0 else (1.0 if n else 0.0)
        rows.append(("play", f"🔊 Play buffer · {n / sr:.1f} s allocated · {nz / sr:.1f} s with sound · {sr} Hz", a, comp,
                     f"cursor {int(getattr(app, 'play_cursor', 0) or 0) / sr:.1f} s"))
    cache = getattr(app, "_shared_mixdown_cache", None)
    if isinstance(cache, dict):
        for k, v in list(cache.items())[:12]:
            arr = v if isinstance(v, np.ndarray) else (v.get("audio") if isinstance(v, dict) else None)
            if isinstance(arr, np.ndarray):
                rows.append((f"mix:{k}", f"🎚 Mixdown cache {str(k)[:24]} · {len(arr) / sr:.1f} s", arr,
                             min(1.0, len(arr) / total) if total > 0 else None, ""))
    for attr, label in (("_instrument_render_cache", "🎹 Instrument cache"), ("_stem_cache", "🎼 Stem cache")):
        c = getattr(app, attr, None)
        if isinstance(c, dict):
            for k, v in list(c.items())[:24]:
                if isinstance(v, np.ndarray) and v.size:
                    rows.append((f"{attr}:{k}", f"{label} · {str(k)[:28]} · {len(v) / sr:.1f} s", v,
                                 min(1.0, len(v) / total) if total > 0 else None, ""))
    chunk = getattr(app, "_last_scope_chunk", None)
    if chunk is not None:
        rows.append(("scope", "〰 Scope chunk (latest)", np.asarray(chunk), None, ""))
    viewer = getattr(app, "video_synth_viewer", None)
    frame = getattr(viewer, "_frame", None) if viewer is not None else None
    if frame is not None:
        rows.append(("frame", f"🖼 Scenograph frame · {frame.shape[1]}×{frame.shape[0]}", np.asarray(frame), None, ""))
    sch = getattr(app, "_export_scheduler_obj", None)
    for j in list(getattr(sch, "jobs", []) or [])[-20:]:
        rows.append((f"job:{id(j)}", f"⬇ Export · {j.label} · {j.state}", None, max(0, min(100, int(j.progress or 0))) / 100.0,
                     (j.message or "")[:60]))
    cp = int(getattr(app, "_buffer_change_point", 0) or 0)
    if cp:
        rows.append(("cp", f"✂ Change point · {cp / sr:.2f} s", None, None, ""))
    return rows, sr


def export_raw(arr, sr, path):
    a = np.ascontiguousarray(np.asarray(arr, dtype="<f4"))
    a.tofile(path)
    meta = {"format": "float32 little-endian, interleaved", "sample_rate": sr, "shape": list(a.shape),
            "channels": int(a.shape[1]) if a.ndim > 1 else 1, "written": time.strftime("%Y-%m-%d %H:%M:%S")}
    json.dump(meta, open(path + ".json", "w"), indent=1)
    return path


def export_wav(arr, sr, path):
    import soundfile as sf
    a = np.asarray(arr, dtype=np.float32)
    sf.write(path, a, sr, subtype="FLOAT")
    return path


def open_window(app):
    from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, QPushButton, QLabel, QProgressBar, QHeaderView
    from PyQt6.QtCore import QTimer
    d = QDialog(app); d.setWindowTitle("🗂 Artifacts · every buffer in RAM · completion · raw export"); d.resize(860, 460)
    v = QVBoxLayout(d)
    v.addWidget(QLabel("Everything Groovebox holds in RAM. Incomplete buffers can still be exported (raw float32 + .json, "
                       "or float WAV) — the completion column says how much of the composition they cover."))
    tab = QTableWidget(0, 3); tab.setHorizontalHeaderLabels(["Buffer", "Completion", "Note"])
    tab.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch); v.addWidget(tab, 1)
    msg = QLabel(""); v.addWidget(msg)
    st = {"rows": [], "sr": 48000}

    def fill():
        st["rows"], st["sr"] = buffers(app)
        tab.setRowCount(0)
        for i, (_k, label, _a, comp, note) in enumerate(st["rows"]):
            tab.insertRow(i); tab.setItem(i, 0, QTableWidgetItem(label))
            if comp is not None:
                bar = QProgressBar(); bar.setValue(int(round(comp * 100))); tab.setCellWidget(i, 1, bar)
            else:
                tab.setItem(i, 1, QTableWidgetItem("—"))
            tab.setItem(i, 2, QTableWidgetItem(note))
        if not st["rows"]:
            msg.setText("Nothing in RAM yet. Play or render to fill the buffers.")

    def chosen():
        r = tab.currentRow()
        if r < 0 or r >= len(st["rows"]) or st["rows"][r][2] is None:
            msg.setText("Pick a row that holds data (audio / frame)."); return None
        return st["rows"][r]

    def save(kind):
        row = chosen()
        if row is None:
            return
        key, label, arr, comp, _n = row
        base = os.path.join(str(app._exports_dir()), "artifact_%s_%d" % (key.replace(":", "_")[:30], int(time.time())))
        try:
            p = export_raw(arr, st["sr"], base + ".f32") if kind == "raw" else export_wav(arr, st["sr"], base + ".wav")
            msg.setText(f"saved {p} ({'complete' if comp in (None, 1.0) else f'{comp * 100:.0f} % complete'})")
        except Exception as exc:
            msg.setText(f"export failed: {exc}")
    row = QHBoxLayout(); v.addLayout(row)
    for cap, fn in (("↻ Refresh", fill), ("💾 Export WAV (float)", lambda: save("wav")), ("🧱 Export raw float32", lambda: save("raw"))):
        b = QPushButton(cap); b.clicked.connect(lambda _c=False, f=fn: f()); row.addWidget(b)
    auto = QTimer(d); auto.setInterval(1500); auto.timeout.connect(lambda: fill() if d.isVisible() else None); auto.start()
    fill(); d.show()
    return d
