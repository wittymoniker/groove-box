"""automation_bus.py — GROOVEBOX_R32_AUTOMATION_BUS_20261110

Every numeric parameter of every R32 module is an automation target, user or CANONICAL.

  Targets   every numeric leaf of: local/global FX, time FX, synth engine, predictive FX, mod osc,
            layer EQ, sample generator layers, geometric mixer, ball / cellular / wavetable params,
            media expression matrix — discovered automatically, so a new module's state appears
            here with no edit (path strings like "r32_fx_state/global/eqr").
  Lanes     a lane = (target path, amount, rate in beats, shape, owner). Owner "canonical": the
            curve is the seed program itself (seed_lang at beat t, rank-normalised per lane, with
            a per-lane phase from the program signature) — deterministic, so the same project
            automates identically on every render. Owner "user": a breakpoint list [(beat, value)].
  Run       at 20 Hz while playing (GUI thread, cheap writes into the state dicts the render reads).
            A lane writes base + amount·(curve − 0.5)·span, clamped to the parameter's span.
  Persist   app.r32_automation (saved with the project by project_schema).
"""
from __future__ import annotations

import math
import time

ROOTS = ("r32_fx_state", "r32_time_fx", "r32_synth_engine", "r32_predictive", "r32_mod_osc", "r32_eq",
         "geometric_synth_mixer_state", "ball_synth_params", "cellular_synth_params", "wavetable_projector_state",
         "r32_expression_matrix", "r32_game_overrides", "r32_game_macros", "r32_inst_mix")
SPANS = {"hz": (0.01, 20000.0), "ms": (0.0, 2000.0), "unison": (1, 7), "echoes": (1, 8), "rule": (0, 255),
         "gravity": (-4.0, 4.0), "tilt": (-1.0, 1.0), "low": (-18, 18), "mid": (-18, 18), "high": (-18, 18)}


def targets(app):
    out = []

    def walk(prefix, d, depth=0):
        if depth > 4 or not isinstance(d, dict):
            return
        for k, v in d.items():
            p = "%s/%s" % (prefix, k)
            if isinstance(v, bool):
                continue
            if isinstance(v, (int, float)):
                out.append(p)
            elif isinstance(v, dict):
                walk(p, v, depth + 1)
    for r in ROOTS:
        walk(r, getattr(app, r, None))
    return out


def _resolve(app, path):
    parts = path.split("/")
    d = getattr(app, parts[0], None)
    for k in parts[1:-1]:
        if not isinstance(d, dict):
            return None, None
        d = d.get(k)
    return (d, parts[-1]) if isinstance(d, dict) else (None, None)


def _span(key, base):
    for k, s in SPANS.items():
        if key == k or key.endswith(k):
            return s
    return (0.0, 1.0) if 0.0 <= float(base) <= 1.0 else (float(base) * 0.25, float(base) * 4.0 + 1.0)


def lanes(app):
    l = getattr(app, "r32_automation", None)
    if not isinstance(l, list):
        l = app.r32_automation = []
    return l


def add_lane(app, path, amount=0.3, rate=16.0, owner="canonical"):
    d, k = _resolve(app, path)
    if d is None:
        return None
    lane = {"path": path, "amount": float(amount), "rate": float(rate), "owner": owner, "base": float(d.get(k, 0) or 0),
            "points": []}
    lanes(app).append(lane)
    return lane


def _canonical_curve(app, lane, beat):
    import seed_lang
    gb = __import__("groovebox")
    raw = app._seed_text() if hasattr(app, "_seed_text") else ""
    try:
        sig = int(app._seed_program_signature() or 1)
    except Exception:
        sig = 1
    ph = (hash(lane["path"]) ^ sig) % 1000 / 1000.0
    u = (beat / max(0.25, lane["rate"]) + ph) % 1.0
    tt = u * max(0.25, lane["rate"])
    cache = lane.setdefault("_cache", {})
    key = round(tt * 8) / 8.0
    if key not in cache:
        ev = seed_lang.evaluate(raw, gb._seed_script_env(t_scalar=float(key)))
        cache[key] = ev.values[0] if ev.values else 0.0
        if len(cache) > 512:
            cache.clear()
    vals = list(cache.values())
    lo, hi = min(vals), max(vals)
    return 0.5 if hi == lo else (cache[key] - lo) / (hi - lo)


def _user_curve(lane, beat):
    pts = sorted(lane.get("points") or [])
    if not pts:
        return 0.5
    b = beat % max(1e-6, pts[-1][0] or 1.0)
    for (b0, v0), (b1, v1) in zip(pts, pts[1:]):
        if b0 <= b <= b1:
            return v0 + (v1 - v0) * (b - b0) / max(1e-9, b1 - b0)
    return pts[-1][1]


def tick(app, beat):
    for lane in list(lanes(app)):
        d, k = _resolve(app, lane["path"])
        if d is None:
            continue
        c = _canonical_curve(app, lane, beat) if lane.get("owner") == "canonical" else _user_curve(lane, beat)
        lo, hi = _span(k, lane["base"])
        v = lane["base"] + lane["amount"] * (c - 0.5) * (hi - lo)
        v = max(lo, min(hi, v))
        d[k] = int(round(v)) if isinstance(d.get(k), int) and not isinstance(d.get(k), bool) else v


def render_tick(app, beat):
    """R32.8: called by the offline render at the start of every playlist row, so exports carry
    the same automation as live playback (row resolution; deterministic for canonical lanes)."""
    if not lanes(app):
        return False
    try:
        tick(app, float(beat))
        return True
    except Exception:
        return False


def restore_bases(app):
    """Put every automated parameter back to its lane base after an offline render."""
    for lane in list(lanes(app)):
        d, k = _resolve(app, lane["path"])
        if d is not None and "base" in lane:
            b = lane["base"]
            d[k] = int(round(b)) if isinstance(d.get(k), int) and not isinstance(d.get(k), bool) else b


def install(app):
    from PyQt6.QtCore import QTimer
    if getattr(app, "_r32_auto_timer", None) is not None:
        return
    t = app._r32_auto_timer = QTimer(app); t.setInterval(50)

    def _t():
        if not lanes(app) or not getattr(app, "is_playing", False):
            return
        try:
            sr = float(getattr(app, "play_sample_rate", 48000) or 48000)
            beat = float(getattr(app, "play_cursor", 0) or 0) / sr * float(app.spin_bpm.value()) / 60.0
        except Exception:
            beat = time.monotonic() * 2.0
        try:
            tick(app, beat)
        except Exception:
            pass
    t.timeout.connect(_t); t.start()


def open_window(app):
    _old = getattr(app, "_automation_window", None)          # R32.8 sweep: one window, not a new one per click
    try:
        if _old is not None:
            _old.show(); _old.raise_(); _old.activateWindow(); return _old
    except RuntimeError:
        pass
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QDoubleSpinBox, QPushButton, QListWidget, QLabel)
    install(app)
    w = QWidget(app, Qt.WindowType.Window); w.setWindowTitle("📈 Automation · every module parameter · canonical or user"); w.resize(760, 480)
    lay = QVBoxLayout(w)
    tg = QComboBox(); tg.setEditable(True); tg.addItems(targets(app))
    amt = QDoubleSpinBox(); amt.setRange(0, 1); amt.setValue(0.3); amt.setSingleStep(0.05)
    rate = QDoubleSpinBox(); rate.setRange(0.25, 256); rate.setValue(16); rate.setSuffix(" beats")
    own = QComboBox(); own.addItems(["canonical", "user"])
    row = QHBoxLayout()
    for x in (QLabel("Target"), tg, QLabel("Amount"), amt, QLabel("Cycle"), rate, own):
        row.addWidget(x)
    lay.addLayout(row)
    lst = QListWidget(); lay.addWidget(lst, 1)

    def fill():
        lst.clear()
        for l in lanes(app):
            lst.addItem("%s · %s · amount %.2f · every %.2f beats" % (l["path"], l["owner"], l["amount"], l["rate"]))

    def add():
        if add_lane(app, tg.currentText(), amt.value(), rate.value(), own.currentText()) is None:
            lst.addItem("✗ not a numeric parameter: " + tg.currentText())
        fill()

    def rem():
        i = lst.currentRow()
        if 0 <= i < len(lanes(app)):
            l = lanes(app).pop(i); d, k = _resolve(app, l["path"])
            if d is not None:
                d[k] = l["base"]
        fill()

    def canon_all():
        for p in targets(app)[:64]:
            if not any(l["path"] == p for l in lanes(app)):
                add_lane(app, p, 0.15, 16.0, "canonical")
        fill()
    row = QHBoxLayout()
    for cap, fn in (("Add lane", add), ("Remove", rem), ("Canonical lanes for everything (15 %)", canon_all),
                    ("Refresh targets", lambda: (tg.clear(), tg.addItems(targets(app))))):
        b = QPushButton(cap); b.clicked.connect(fn); row.addWidget(b)
    lay.addLayout(row); fill()
    app._automation_window = w; w.show(); return w
