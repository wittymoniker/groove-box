"""GROOVEBOX_R124_SCENE_PADS: whole-scene snapshots on LIVE DECK pads.

A scene = mix (master volume + per-instrument gains), routes, Mod Path field state, BPM and the master
chain. ``store(app, slot)`` / ``recall(app, slot, morph_s=None)``: recall morphs numeric values over the
Global Morph Bridge time (or ``morph_s``) with a QTimer at 30 Hz; non-numeric values switch at the end.
Scenes persist in QSettings ("MathematiciansGroovebox", "UI") key ``scene_pads`` (JSON).
"""
from __future__ import annotations

import copy
import json

SLOTS = 8
_KEY = "scene_pads"


def _settings():
    from PyQt6.QtCore import QSettings
    return QSettings("MathematiciansGroovebox", "UI")


def load_all():
    try:
        return json.loads(str(_settings().value(_KEY, "{}") or "{}"))
    except Exception:
        return {}


def save_all(d):
    try:
        _settings().setValue(_KEY, json.dumps(d, default=str))
    except Exception:
        pass


def _val(app, attr):
    w = getattr(app, attr, None)
    try:
        return float(w.value())
    except Exception:
        return None


def capture(app):
    sc = {"bpm": _val(app, "spin_bpm"), "master_vol": _val(app, "slider_master_vol")}
    gains = {}
    for name, (sl, _lab) in (getattr(app, "geometric_engine_mix_sliders", {}) or {}).items():
        try:
            gains[name] = float(sl.value())
        except Exception:
            pass
    sc["geo_mix"] = gains
    for attr in ("instrument_routes", "route_handles"):
        v = getattr(app, attr, None)
        if v is not None:
            try:
                sc[attr] = json.loads(json.dumps(v, default=str))
            except Exception:
                pass
    try:
        import mm_fields
        sc["mod_path"] = copy.deepcopy(dict(mm_fields.settings(app)))
    except Exception:
        pass
    try:
        import master_chain
        sc["master_chain"] = master_chain.load()
    except Exception:
        pass
    return sc


def store(app, slot):
    d = load_all(); d[str(slot)] = capture(app); save_all(d)
    return d[str(slot)]


def _morph_seconds(app, morph_s):
    if morph_s is not None:
        return max(0.0, float(morph_s))
    for attr in ("spin_morph_time", "spin_global_morph_time", "global_morph_time_s"):
        v = getattr(app, attr, None)
        try:
            return max(0.0, float(v.value() if hasattr(v, "value") else v))
        except Exception:
            continue
    return 0.5


def _set(app, attr, v):
    w = getattr(app, attr, None)
    try:
        if v is not None and w is not None:
            w.setValue(type(w.value())(v))
    except Exception:
        pass


def recall(app, slot, morph_s=None):
    sc = load_all().get(str(slot))
    if not sc:
        return False
    start = capture(app)
    secs = _morph_seconds(app, morph_s)

    def apply(t):
        lerp = lambda a, b: (b if a is None else a + (b - a) * t) if b is not None else a
        _set(app, "spin_bpm", lerp(start.get("bpm"), sc.get("bpm")))
        _set(app, "slider_master_vol", lerp(start.get("master_vol"), sc.get("master_vol")))
        for name, v in (sc.get("geo_mix") or {}).items():
            pair = (getattr(app, "geometric_engine_mix_sliders", {}) or {}).get(name)
            if pair:
                try:
                    pair[0].setValue(int(round(lerp((start.get("geo_mix") or {}).get(name), v))))
                except Exception:
                    pass
        if t >= 1.0:
            for attr in ("instrument_routes", "route_handles"):
                if attr in sc and getattr(app, attr, None) is not None:
                    try:
                        cur = getattr(app, attr)
                        if isinstance(cur, dict):
                            cur.clear(); cur.update(sc[attr])
                    except Exception:
                        pass
            try:
                import mm_fields
                st = mm_fields.settings(app)
                if "mod_path" in sc:
                    st.clear(); st.update(sc["mod_path"])
            except Exception:
                pass
            try:
                import master_chain
                if "master_chain" in sc:
                    master_chain.save(sc["master_chain"])
            except Exception:
                pass

    if secs <= 0.0:
        apply(1.0)
        return True
    from PyQt6.QtCore import QTimer, QElapsedTimer
    clock = QElapsedTimer(); clock.start()
    timer = QTimer(app); timer.setInterval(33)

    def tick():
        t = min(1.0, clock.elapsed() / (secs * 1000.0))
        apply(t)
        if t >= 1.0:
            timer.stop(); timer.deleteLater()
    timer.timeout.connect(tick); timer.start()
    app._r124_scene_timer = timer
    return True


def build_row(app):
    """A row of SLOTS scene pads: click = recall (morph), Shift+click or right-click = store."""
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QApplication
    row = QWidget(); lay = QHBoxLayout(row); lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(4)
    btns = []

    def label(i):
        return f"Scene {i}\n{'●' if str(i) in load_all() else '○'}"

    for i in range(1, SLOTS + 1):
        b = QPushButton(label(i)); b.setToolTip("Click: recall (morphs over the Morph Bridge time) · Shift+click or right-click: store")
        b.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

        def on_click(_c=False, i=i, b=b):
            if QApplication.keyboardModifiers() & Qt.KeyboardModifier.ShiftModifier:
                store(app, i)
            else:
                recall(app, i)
            b.setText(label(i))
        b.clicked.connect(on_click)
        b.customContextMenuRequested.connect(lambda _p, i=i, b=b: (store(app, i), b.setText(label(i))))
        lay.addWidget(b); btns.append(b)
    row._scene_buttons = btns
    return row
