"""r32_deck.py — GROOVEBOX_R32_DECK_20261110

Six compact panels in one collapsible top dock of the main window (drag it to any edge or
float it; each panel folds by its title):

  1 🎬 MEDIA EXPRESSION   source × target matrix (seed · canonical · geometry · multidim · fx ·
                          sample → video brightness / pulse, game pulse / gravity / speed), live
                          meters, mode: composition parameters ↔ audio samples (identical audio ⇒
                          identical video), "Feed audio file…"
  2 🧾 SIGNAL IDENTITY    the indices that make this project unique: project uid, seed program
                          signature, canonical mode, active engines, per-instrument seed index;
                          "Verify determinism" evaluates everything twice and compares
  3 🎚 SNAPSHOT MORPH     8 slots (store/recall); morph slider between any two (numeric state of
                          mixer, FX, time FX, synth engine, ball, cellular, wavetable)
  4 🎼 KEY & TRANSPOSE    key root + scale for the live keys (on top of the tuning lattice),
                          global transpose (semitones) for the key chart
  5 〰 SEEDED MOD OSC     sub-audio (controls, tempo-locked), audio-rate AM / FM / ring on voices,
                          super-audio (folds deterministically → heterodyne difference tones)
  6 📈 MONITOR            CPU-time share of the GUI thread (stall count), RSS, export jobs, worker
                          processes, site / relay status, MIDI ports
"""
from __future__ import annotations

import json
import math
import time

from PyQt6.QtCore import Qt, QTimer, QEvent, QObject
from PyQt6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QGridLayout, QGroupBox, QLabel, QSlider, QComboBox,
                             QPushButton, QDoubleSpinBox, QSpinBox, QDockWidget, QAbstractSlider, QAbstractSpinBox,
                             QApplication, QFileDialog, QProgressBar, QScrollArea)

BOX = ("QGroupBox{color:%s;background:#000000;border:1px solid %s;border-radius:7px;margin-top:6px;padding-top:10px;"
       "font-weight:900;}QLabel,QCheckBox{color:#ffffff;font-size:8pt;}")


def _box(title, color):
    b = QGroupBox(title); b.setStyleSheet(BOX % (color, color))
    try:
        import fx_panels
        fx_panels.make_collapsible(b)
    except Exception:
        pass
    return b


# 1 ---------------------------------------------------------------------------
def media_expression_panel(app):
    import media_expression as me
    me.install(app)
    b = _box("🎬 MEDIA EXPRESSION · audio ⇄ video ⇄ game", "#7dd3fc"); g = QGridLayout(b); g.setSpacing(2)
    m = me.matrix(app)
    for c, t in enumerate(me.TARGETS):
        lab = QLabel(t.replace("_", "\n")); lab.setAlignment(Qt.AlignmentFlag.AlignCenter); g.addWidget(lab, 0, c + 1)
    meters = {}
    for r, s in enumerate(me.SOURCES, 1):
        g.addWidget(QLabel(s), r, 0)
        for c, t in enumerate(me.TARGETS):
            sp = QDoubleSpinBox(); sp.setRange(0, 1); sp.setSingleStep(0.1); sp.setDecimals(1); sp.setMaximumWidth(54)
            sp.setValue(float(m.get("%s>%s" % (s, t), 0.0)))
            sp.valueChanged.connect(lambda v, k="%s>%s" % (s, t): m.__setitem__(k, float(v)))
            g.addWidget(sp, r, c + 1)
        bar = QProgressBar(); bar.setRange(0, 100); bar.setMaximumWidth(60); bar.setTextVisible(False); meters[s] = bar
        g.addWidget(bar, r, len(me.TARGETS) + 1)
    row = len(me.SOURCES) + 1
    mode = QComboBox(); mode.addItems(["from composition parameters", "from audio samples (identical audio ⇒ identical video)"])
    mode.setCurrentIndex(1 if getattr(app, "r32_expression_mode", "composition") == "audio" else 0)
    mode.currentIndexChanged.connect(lambda i: setattr(app, "r32_expression_mode", me.MODES[i]))
    g.addWidget(mode, row, 0, 1, 4)
    feed = QPushButton("Feed audio file…")

    def _feed():
        p, _ = QFileDialog.getOpenFileName(b, "Audio for the video / game expression", "", "Audio (*.wav *.flac *.mp3 *.ogg *.opus *.m4a *.MCC *.mcc);;MCC media (*.MCC *.mcc)")
        if p:
            import postprocess_window as pw
            y, sr = pw.read_audio(p); me.set_audio(app, y, sr); app.r32_expression_mode = "audio"; mode.setCurrentIndex(1)
    feed.clicked.connect(_feed); g.addWidget(feed, row, 4, 1, 2)
    live = QPushButton("Preview while stopped"); live.setCheckable(True)
    live.toggled.connect(lambda v: setattr(app, "_r32_expr_force", bool(v))); g.addWidget(live, row + 1, 0, 1, 3)

    def upd():
        now = getattr(app, "r32_expression_now", None)
        if now:
            for s, bar in meters.items():
                bar.setValue(int(100 * now[1].get(s, 0)))
    t = QTimer(b); t.setInterval(200); t.timeout.connect(lambda: upd() if b.isVisible() else None); t.start()   # R32.8 sweep
    return b


# 2 ---------------------------------------------------------------------------
def identity_panel(app):
    b = _box("🧾 SIGNAL IDENTITY · the indices", "#2ecc71"); lay = QVBoxLayout(b)
    lab = QLabel(""); lab.setWordWrap(True); lab.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse); lay.addWidget(lab)
    res = QLabel(""); res.setWordWrap(True); lay.addWidget(res)

    def ident():
        try:
            sig = app._seed_program_signature()
        except Exception:
            sig = 0
        try:
            eng = ",".join(sorted(app._get_active_engine_set())) or "none"
        except Exception:
            eng = "?"
        names = list(getattr(app, "instrument_names_48", []) or [])[:6]
        idx = []
        for i, n in enumerate(names):
            try:
                idx.append("%s:%08x" % (n[:8], app._instrument_seed_int(i, n)))
            except Exception:
                pass
        return {"project_uid": str(getattr(app, "_project_uid", "") or "unsaved"), "seed_signature": "%08x" % int(sig or 0),
                "canonical_mode": getattr(app, "canonical_mode", "protected"), "engines": eng,
                "divergence": float(getattr(app, "seed_divergence", 0.6) or 0.6), "instrument_seeds": idx}

    def show():
        d = ident()
        lab.setText("uid %s\nseed σ %s · mode %s · div %.2f\nengines %s\n%s" % (
            d["project_uid"][:16], d["seed_signature"], d["canonical_mode"], d["divergence"], d["engines"], "  ".join(d["instrument_seeds"])))

    def verify():
        try:
            import seed_lang
            seed_lang.clear_cache(); seed_lang._SIG_CACHE.clear()
        except Exception:
            pass
        a = json.dumps(ident(), sort_keys=True)
        try:
            import seed_lang
            seed_lang.clear_cache(); seed_lang._SIG_CACHE.clear()
        except Exception:
            pass
        bb = json.dumps(ident(), sort_keys=True)
        res.setText("✓ deterministic: two independent evaluations agree" if a == bb else "✗ MISMATCH — please report:\n" + a[:200])
    def sync():
        try:
            import project_schema
            ok, bad = project_schema.verify(app)
            m = project_schema.manifest(app)
            res.setText(("✓ all %d engine state keys survive save/load (schema %d)" % (len(m["keys"]), m["schema"])) if ok
                        else "✗ out of sync: " + ", ".join(bad))
        except Exception as exc:
            res.setText("sync check failed: %s" % exc)
    row = QHBoxLayout()
    for cap, fn in (("↻", show), ("Verify determinism", verify), ("Engine sync check", sync)):
        x = QPushButton(cap); x.clicked.connect(fn); row.addWidget(x)
    lay.addLayout(row); show()
    return b


# 3 ---------------------------------------------------------------------------
_MORPH_ATTRS = ("geometric_synth_mixer_state", "ball_synth_params", "cellular_synth_params", "wavetable_projector_state",
                "r32_fx_state", "r32_time_fx", "r32_synth_engine")


def _numeric(d):
    if isinstance(d, dict):
        return {k: _numeric(v) for k, v in d.items() if isinstance(v, (int, float, dict)) and not isinstance(v, bool)}
    return d


def _lerp(a, b, u):
    if isinstance(a, dict) and isinstance(b, dict):
        return {k: _lerp(a[k], b[k], u) if k in b else a[k] for k in a}
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        v = a + (b - a) * u
        return int(round(v)) if isinstance(a, int) and isinstance(b, int) else v
    return a if u < 0.5 else b


def snapshot_panel(app):
    b = _box("🎚 SNAPSHOT MORPH · 8 slots", "#f6c177"); g = QGridLayout(b); g.setSpacing(2)
    slots = app.__dict__.setdefault("r32_snapshots", {})
    btns = {}

    def store(k):
        slots[k] = {a: json.loads(json.dumps(_numeric(getattr(app, a, {}) or {}))) for a in _MORPH_ATTRS}
        btns[k].setText("%s●" % k)

    def recall(k, u=1.0, other=None):
        A = slots.get(k)
        if A is None:
            store(k); return
        for a in _MORPH_ATTRS:
            cur = getattr(app, a, None)
            if not isinstance(cur, dict):
                continue
            tgt = A.get(a, {}) if other is None else _lerp(slots[other].get(a, {}), A.get(a, {}), u)
            _deep_update(cur, tgt)
        getattr(app, "_r32_geo_refresh_soon", lambda: None)(); getattr(app, "_on_live_source_changed", lambda: None)()
    for i, k in enumerate("ABCDEFGH"):
        x = QPushButton(k + ("●" if k in slots else "")); x.setToolTip("Click: recall (empty: store) · right-click: store")
        x.clicked.connect(lambda _c=False, kk=k: recall(kk))
        x.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        x.customContextMenuRequested.connect(lambda _p, kk=k: store(kk))
        btns[k] = x; g.addWidget(x, i // 4, i % 4)
    ca, cb = QComboBox(), QComboBox()
    for c in (ca, cb):
        c.addItems(list("ABCDEFGH"))
    cb.setCurrentIndex(1)
    sl = QSlider(Qt.Orientation.Horizontal); sl.setRange(0, 1000)
    sl.valueChanged.connect(lambda v: (ca.currentText() in slots and cb.currentText() in slots) and recall(cb.currentText(), v / 1000.0, ca.currentText()))
    g.addWidget(ca, 2, 0); g.addWidget(sl, 2, 1, 1, 2); g.addWidget(cb, 2, 3)
    return b


def _deep_update(cur, tgt):
    for k, v in tgt.items():
        if isinstance(v, dict) and isinstance(cur.get(k), dict):
            _deep_update(cur[k], v)
        elif isinstance(v, (int, float)):
            cur[k] = v


# 4 ---------------------------------------------------------------------------
SCALES = {"chromatic": list(range(12)), "major": [0, 2, 4, 5, 7, 9, 11], "minor": [0, 2, 3, 5, 7, 8, 10],
          "dorian": [0, 2, 3, 5, 7, 9, 10], "pentatonic": [0, 2, 4, 7, 9], "minor pentatonic": [0, 3, 5, 7, 10],
          "whole tone": [0, 2, 4, 6, 8, 10], "harmonic minor": [0, 2, 3, 5, 7, 8, 11], "blues": [0, 3, 5, 6, 7, 10]}
ROOTS = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")


def key_panel(app):
    b = _box("🎼 KEY & TRANSPOSE · live keys", "#c4a7e7"); g = QGridLayout(b)
    root = QComboBox(); root.addItems(ROOTS); scale = QComboBox(); scale.addItems(list(SCALES)); scale.setCurrentText("chromatic")
    tr = QSpinBox(); tr.setRange(-24, 24); tr.setSuffix(" st")
    for r, (cap, w) in enumerate((("Root", root), ("Scale", scale), ("Transpose", tr))):
        g.addWidget(QLabel(cap), r, 0); g.addWidget(w, r, 1)
    if not getattr(app, "_r32_key_hooked", False):
        orig = app._keychart_ratio

        def _ratio(degree, _orig=orig):
            st = getattr(app, "r32_key", None)
            if not st or (st["scale"] == "chromatic" and st["root"] == 0 and st["transpose"] == 0):
                return _orig(degree)
            sc = SCALES.get(st["scale"], SCALES["chromatic"])
            o, k = divmod(int(degree), len(sc))
            semis = st["root"] + st["transpose"] + 12 * o + sc[k]
            return _orig(0) * 2.0 ** (semis / 12.0)
        app._keychart_ratio = _ratio; app._r32_key_hooked = True

    def upd(*_):
        app.r32_key = {"root": root.currentIndex(), "scale": scale.currentText(), "transpose": tr.value()}
    for w in (root, scale):
        w.currentIndexChanged.connect(upd)
    tr.valueChanged.connect(upd)
    return b


# 5 ---------------------------------------------------------------------------
class _Touch(QObject):
    def __init__(self, app):
        super().__init__(app); self.last = None

    def eventFilter(self, obj, ev):
        if ev.type() in (QEvent.Type.MouseButtonPress, QEvent.Type.Wheel) and isinstance(obj, (QAbstractSlider, QAbstractSpinBox)):
            self.last = obj
        return False


def _shared_touch(app):
    """R32.9: one app-wide 'last touched control' filter shared by every panel (each filter runs on every event)."""
    t = getattr(app, "_r32_touch", None)
    if t is None:
        t = app._r32_touch = _Touch(app); QApplication.instance().installEventFilter(t)
    return t


def lfo_panel(app):
    b = _box("〰 SEEDED LFO · modulate any control", "#9ece6a"); g = QGridLayout(b)
    touch = _shared_touch(app); b._touch = touch
    rate = QDoubleSpinBox(); rate.setRange(0.25, 64); rate.setValue(4); rate.setSuffix(" beats")
    depth = QDoubleSpinBox(); depth.setRange(0, 1); depth.setSingleStep(0.05); depth.setValue(0.25)
    lst = QLabel("no targets"); lst.setWordWrap(True)
    lfos = app.__dict__.setdefault("r32_lfos", [])
    for r, (cap, w) in enumerate((("Rate", rate), ("Depth", depth))):
        g.addWidget(QLabel(cap), r, 0); g.addWidget(w, r, 1)

    def assign():
        w = touch.last
        if w is None:
            lst.setText("touch a slider or spin box first"); return
        try:
            sig = int(app._seed_program_signature() or 1)
        except Exception:
            sig = 1
        lfos.append({"w": w, "rate": rate.value(), "depth": depth.value(), "base": float(w.value()),
                     "shape": sig % 3, "phase": (sig % 997) / 997.0})
        lst.setText("%d target(s)" % len(lfos))

    def clear():
        for d in lfos:
            try:
                d["w"].setValue(type(d["w"].value())(d["base"]))
            except Exception:
                pass
        lfos.clear(); lst.setText("no targets")
    x = QPushButton("Assign to last touched"); x.clicked.connect(assign); g.addWidget(x, 2, 0)
    y = QPushButton("Clear"); y.clicked.connect(clear); g.addWidget(y, 2, 1); g.addWidget(lst, 3, 0, 1, 2)

    def tick():
        if not lfos:
            return
        try:
            bpm = float(app.spin_bpm.value())
        except Exception:
            bpm = 120.0
        beat = time.monotonic() * bpm / 60.0
        for d in list(lfos):
            w = d["w"]
            try:
                u = (beat / d["rate"] + d["phase"]) % 1.0
                v = {0: math.sin(2 * math.pi * u), 1: 4 * abs(u - 0.5) - 1, 2: 1.0 if u < 0.5 else -1.0}[d["shape"]]
                span = float(w.maximum() - w.minimum())
                nv = max(w.minimum(), min(w.maximum(), d["base"] + v * d["depth"] * 0.5 * span))
                w.setValue(int(round(nv)) if isinstance(w, QAbstractSlider) or isinstance(w.value(), int) else nv)
            except RuntimeError:
                lfos.remove(d)
    t = QTimer(b); t.setInterval(60); t.timeout.connect(lambda: tick() if lfos else None); t.start()   # R32.8 sweep: idle = no work
    return b


def mod_osc_panel(app):
    import mod_osc
    touch = _shared_touch(app)
    b = mod_osc.make_panel(app, touch); b._touch = touch
    try:
        import fx_panels
        fx_panels.make_collapsible(b)
    except Exception:
        pass
    return b


# 6 ---------------------------------------------------------------------------
def monitor_panel(app):
    b = _box("📈 MONITOR", "#ffd166"); lay = QVBoxLayout(b)
    lab = QLabel(""); lab.setWordWrap(True); lay.addWidget(lab)
    # R32.8 DYNAMIC_RAM: memory budget (Auto = by machine tier); applies at once
    from PyQt6.QtWidgets import QSpinBox as _QSB
    rowb = QHBoxLayout(); rowb.addWidget(QLabel("RAM budget"))
    sp = _QSB(); sp.setRange(0, 90); sp.setSingleStep(5); sp.setSuffix(" %"); sp.setSpecialValueText("Auto")
    sp.setToolTip("Share of this machine's RAM Groovebox aims to stay under. Auto picks by size: 4–6 GB machines run lean "
                  "(1 export at a time, small video chunks), 32 GB machines get parallel exports and bigger caches. "
                  "Under system memory pressure everything halves automatically.")
    try:
        import resource_governor as _rg0
        sp.setValue(_rg0.budget_pct())
    except Exception:
        pass

    def _set_budget(v):
        try:
            import resource_governor as _rg1
            _rg1.set_budget_pct(int(v) if int(v) >= 25 else (0 if int(v) == 0 else 25))
        except Exception:
            pass
    sp.setKeyboardTracking(False); sp.valueChanged.connect(_set_budget)
    rowb.addWidget(sp); lay.addLayout(rowb)

    def upd():
        parts = []
        try:
            import resource_governor as rg
            rec = rg.recommend()
            parts.append("RAM %d MB / budget %d MB (%s%s) · free %d MB" % (
                rg.rss_mb(), rec["budget_mb"], rec["tier"], ", PRESSURE" if rec["pressure"] else "", rec["available_mb"]))
        except Exception:
            pass
        try:
            import ui_stall_watch as us
            parts.append("stalls %d" % us._STATE["count"])
        except Exception:
            pass
        try:
            sch = getattr(app, "_export_scheduler_obj", None)
            if sch is not None:
                run = [j for j in sch.jobs if j.state == "running"]
                parts.append("exports %d running · %d queued" % (len(run), sch.pending_count()))
        except Exception:
            pass
        try:
            import process_policy as pp
            parts.append("children %d" % pp.status()["live"])
        except Exception:
            pass
        s = getattr(app, "_groovebox_site", None)
        parts.append("site %s" % ("on" if s is not None and s.httpd else "off"))
        rm = getattr(app, "_relay_member", None)
        if rm is not None:
            parts.append("relay " + rm.state)
        h = getattr(app, "_midi_hub", None)
        if h is not None:
            parts.append("MIDI %d" % len(h.ports))
        lab.setText(" · ".join(parts))
    t = QTimer(b); t.setInterval(2000); t.timeout.connect(lambda: upd() if b.isVisible() else None); t.start(); upd()
    return b



# R32.8 MACRO_KNOBS: six dials on the top deck. Each drives one real parameter of the render chain;
# its "C" box hands the dial to a canonical automation lane (the seed program moves it,
# deterministically, in live play AND in exports). Defaults are neutral (0 = off / flat).
MACRO_KNOBS = (
    ("Drive", "r32_fx_state/global/hyper", 0.0, 1.0),
    ("Fractal", "r32_fx_state/global/fractal", 0.0, 1.0),
    ("Tilt", "r32_fx_state/global/tilt", -1.0, 1.0),
    ("Low", "r32_eq/global/low", -18.0, 18.0),
    ("High", "r32_eq/global/high", -18.0, 18.0),
    ("Mod", "r32_mod_osc/global/depth", 0.0, 1.0),
)


def macro_knobs_panel(app):
    from PyQt6.QtWidgets import QDial, QCheckBox
    try:
        import fx_panels; fx_panels.install_hooks(app)
    except Exception:
        pass
    for _m, _f in (("layer_mixer", "_eq_state"), ("mod_osc", "_state")):
        try:
            getattr(__import__(_m), _f)(app)          # make sure the target dicts exist
        except Exception:
            pass
    import automation_bus as ab
    b = _box("🎛 MACRO KNOBS", "#2ecc71"); g = QGridLayout(b); g.setSpacing(2); g.setContentsMargins(4, 10, 4, 4)
    dials = {}

    def lane_for(path):
        return next((l for l in ab.lanes(app) if l.get("path") == path and l.get("owner") == "canonical"), None)

    for col, (name, path, lo, hi) in enumerate(MACRO_KNOBS):
        d = QDial(); d.setRange(0, 1000); d.setNotchesVisible(True); d.setFixedSize(46, 46)
        d.setToolTip("%s → %s (%g … %g). C = canonical: the seed program automates it." % (name, path, lo, hi))
        lab = QLabel(name); lab.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        val = QLabel(""); val.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        c = QCheckBox("C"); c.setToolTip("Canonical: hand this knob to a seed-driven automation lane (exports follow it).")
        g.addWidget(lab, 0, col); g.addWidget(d, 1, col, Qt.AlignmentFlag.AlignHCenter); g.addWidget(val, 2, col); g.addWidget(c, 3, col, Qt.AlignmentFlag.AlignHCenter)

        def read(path=path):
            dd, k = ab._resolve(app, path)
            try:
                return float(dd.get(k, 0.0) or 0.0) if dd is not None else 0.0
            except Exception:
                return 0.0

        def to_dial(v, lo=lo, hi=hi):
            return int(round((v - lo) / (hi - lo) * 1000))

        def changed(i, path=path, lo=lo, hi=hi, val=val):
            v = lo + (hi - lo) * i / 1000.0
            dd, k = ab._resolve(app, path)
            if dd is not None:
                dd[k] = v
            ln = lane_for(path)
            if ln is not None:
                ln["base"] = v
            val.setText("%.2f" % v)

        def canon(on, path=path):
            ln = lane_for(path)
            if on and ln is None:
                ab.add_lane(app, path, amount=0.3, rate=16.0, owner="canonical")
            elif not on and ln is not None:
                ab.lanes(app).remove(ln)
                ab.restore_bases(app)
        d.blockSignals(True); d.setValue(to_dial(read())); d.blockSignals(False); val.setText("%.2f" % read())
        c.setChecked(lane_for(path) is not None)
        d.valueChanged.connect(changed); c.toggled.connect(canon)
        dials[path] = (d, c, read, to_dial, val)

    def sync():                      # follow project loads / automation without fighting the user
        for path, (d, c, read, to_dial, val) in dials.items():
            if d.isSliderDown():
                continue
            v = read(); d.blockSignals(True); d.setValue(to_dial(v)); d.blockSignals(False); val.setText("%.2f" % v)
            c.blockSignals(True); c.setChecked(lane_for(path) is not None); c.blockSignals(False)
    t = QTimer(b); t.setInterval(500); t.timeout.connect(lambda: sync() if b.isVisible() else None); t.start()
    am = QPushButton("Auto-map structure"); am.setToolTip("One canonical lane per part of the wave structure "
                                                         "(level·brightness·low energy·pitch motion·texture·rhythm → the six knobs).")
    am.clicked.connect(lambda: (__import__("r32_finish").auto_map(app), sync()))
    g.addWidget(am, 4, 0, 1, len(MACRO_KNOBS))
    return b

def install(app):
    if getattr(app, "_r32_deck", None) is not None:
        return app._r32_deck
    dock = QDockWidget("Groovebox deck · expression · identity · morph · key · mod osc · monitor", app)
    dock.setObjectName("R32Deck")
    holder = QWidget(); row = QHBoxLayout(holder); row.setContentsMargins(2, 2, 2, 2); row.setSpacing(4)
    def _mixer(a):
        import layer_mixer; b = layer_mixer.make_panel(a)
        try:
            import fx_panels; fx_panels.make_collapsible(b)
        except Exception:
            pass
        return b

    def _pred(a):
        import predictive_fx; b = predictive_fx.make_panel(a)
        try:
            import fx_panels; fx_panels.make_collapsible(b)
        except Exception:
            pass
        return b
    try:
        import automation_bus; automation_bus.install(app)
    except Exception:
        pass
    for fn in (macro_knobs_panel, media_expression_panel, identity_panel, snapshot_panel, key_panel, mod_osc_panel, _mixer, _pred, monitor_panel):
        try:
            p = fn(app)
            # R32.8: every panel stretches to fill its share of the screen width and the deck height.
            from PyQt6.QtWidgets import QSizePolicy
            p.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            p.setStyleSheet(p.styleSheet() + " QLabel,QCheckBox,QComboBox,QSpinBox,QDoubleSpinBox,QPushButton{font-size:7pt;}")
            row.addWidget(p, 2 if fn is media_expression_panel else 1)
        except Exception as exc:
            row.addWidget(QLabel("%s: %s" % (fn.__name__, exc)))
    from PyQt6.QtWidgets import QSizePolicy as _SP
    holder.setSizePolicy(_SP.Policy.Expanding, _SP.Policy.Expanding)
    # R32.8: 66 % of the former 300 px; the scroll area keeps every control reachable on small screens.
    sc = QScrollArea(); sc.setWidgetResizable(True); sc.setWidget(holder); sc.setMaximumHeight(200); sc.setMinimumHeight(120)
    sc.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    dock.setWidget(sc)
    dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable | QDockWidget.DockWidgetFeature.DockWidgetFloatable |
                     QDockWidget.DockWidgetFeature.DockWidgetClosable)
    app.addDockWidget(Qt.DockWidgetArea.TopDockWidgetArea, dock)
    app._r32_deck = dock
    app._r32_deck_scroll = sc
    QTimer.singleShot(0, lambda: into_splitter(app))
    return dock


# R32.8 THREE_PANES: the deck is the first pane of the main window's vertical splitter (deck · controls ·
# monitors/export). Every pane resizes by dragging the handles and scrolls on both axes; minimum heights
# are fractions of the screen: deck 1/28, middle 1/16, bottom 1/24.
PANE_MIN_FRACTIONS = (1 / 28.0, 1 / 16.0, 1 / 24.0)


def apply_pane_minimums(app):
    sp = getattr(app, "render_splitter", None)
    if sp is None:
        return
    try:
        scr = app.screen() or app.windowHandle().screen()
        h = scr.availableGeometry().height()
    except Exception:
        h = 1080
    for i, frac in enumerate(PANE_MIN_FRACTIONS):
        if i < sp.count():
            w = sp.widget(i)
            w.setMinimumHeight(max(24, int(h * frac)))
            w.setMaximumHeight(16777215)


def into_splitter(app, _tries=[0]):
    sp = getattr(app, "render_splitter", None); sc = getattr(app, "_r32_deck_scroll", None)
    dock = getattr(app, "_r32_deck", None)
    if sc is None:
        return
    if sp is None:
        _tries[0] += 1
        if _tries[0] < 40:
            QTimer.singleShot(250, lambda: into_splitter(app))
        return
    if sp.indexOf(sc) >= 0:
        return
    sc.setMaximumHeight(16777215)
    sc.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    sc.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    sp.insertWidget(0, sc)
    sp.setCollapsible(0, False)
    try:
        if dock is not None:
            dock.setWidget(QWidget()); dock.hide(); app.removeDockWidget(dock)
    except Exception:
        pass
    for i in range(sp.count()):
        sp.setCollapsible(i, False)
    apply_pane_minimums(app)
    try:
        sizes = sp.sizes(); total = sum(sizes) or 1200
        deck = max(sc.minimumHeight(), 200)
        rest = max(1, total - deck)
        sp.setSizes([deck, int(rest * 0.6), rest - int(rest * 0.6)])
    except Exception:
        pass
    try:
        app.windowHandle().screenChanged.connect(lambda *_: apply_pane_minimums(app))
    except Exception:
        pass
