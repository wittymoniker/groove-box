"""mod_matrix.py — MASTER MOD MATRIX: any source × any method → any target, with canonical direction in unison.

Row = {source, source2, method, target, amount, rate, canonical, enabled}
Sources  lfo:sine|triangle|saw|square|random (rate in beats) · seed (the seed program over time) · canonical
         (the active canonicals' level) · automation:<target path> (the current value of any automation target,
         normalised) · row:<n> (the OUTPUT of another matrix row — the matrix is its own patch bay; evaluated in row
         order, so earlier rows feed later ones) · patch:<instrument> (that instrument's patch-bay fan-in weight) ·
         midi:cc<n> (last value of a MIDI CC) · playhead (0..1 over the song) · const
Methods  add · multiply · ring (bipolar product) · min · max · crossfade (source2 by source) · fm (phase-modulate
         source by source2) · fold · sample-hold (source sampled when source2 crosses up) · gate (source where
         source2 > 0.5) · quantize (source to source2·16+1 steps)
Canonical direction  each row's `canonical` 0..1 blends its output with the seed-program curve of the same target
         (automation_bus._canonical_curve), so canonical and user modulation move in unison rather than fighting.
Targets  every automation_bus target (any numeric leaf of the R32 module states, tuning, mixer, FX …).
Runs at the automation tick (20 Hz while playing) and per row in the offline render, through automation_bus, so
live play and every export agree. Bases are restored after an offline render.
"""
from __future__ import annotations
import math

SOURCES_FIXED = ("lfo:sine", "lfo:triangle", "lfo:saw", "lfo:square", "lfo:random", "seed", "canonical", "playhead", "const",
                 "seq:summative", "const:Q", "const:B", "const:M")
METHODS = ("add", "multiply", "ring", "min", "max", "crossfade", "fm", "fold", "sample-hold", "gate", "quantize",
           # R101, after "Scientific Theories and Inventions" (N. G. King): signal components as modulation methods
           "biode", "transratio", "tr-nand", "evaluatum")


def rows(app):
    r = getattr(app, "r99_mod_matrix", None)
    if not isinstance(r, list):
        r = app.r99_mod_matrix = []
    return r


def sources(app):
    out = list(SOURCES_FIXED)
    out += ["row:%d" % (i + 1) for i in range(len(rows(app)))]
    out += ["patch:%s" % n for n in (getattr(app, "instrument_names_48", []) or [])[:48]]
    out += ["midi:cc%d" % i for i in (1, 2, 7, 10, 11, 64, 71, 74)]
    try:
        import mm_governor
        out += mm_governor.carrier_sources(app)        # R101: carrier envelopes as sources
    except Exception:
        pass
    try:
        import automation_bus as ab
        out += ["automation:" + t for t in ab.targets(app)[:400]]
    except Exception:
        pass
    return out


GLOBAL_WIDGETS = ("slider_eqr", "slider_fractalizer", "slider_pkp_envelope", "slider_pkp_boost", "slider_pkp_boost_pitch",
                  "slider_pkp_boost_mod", "slider_pkp_boost_prob", "spin_global_convolve", "spin_canonical_convolve",
                  "spin_canonical_live_overblend", "spin_canonical_resonance", "spin_engine_strength", "spin_seed_reach",
                  "spin_seed_divergence_menu", "spin_global_detune_cents", "spin_global_stretch", "spin_unison_blend",
                  "gp_mix_slider", "gp_script_slider", "gp_domain_slider", "gp_wire_slider", "spin_hyperdrive_drive",
                  "spin_hyperdrive_resonance", "dial_track_energy", "dial_track_harmonic", "spin_base_frequency")


def all_targets(app):
    """Every modulation pathway: automation targets (R32 modules, FX panels, global panel states, tuning) and the
    global panel's own controls (widget:…)."""
    try:
        import automation_bus as ab
        out = list(ab.targets(app))
    except Exception:
        out = []
    out += ["widget:" + n for n in GLOBAL_WIDGETS if getattr(app, n, None) is not None and hasattr(getattr(app, n), "setValue")]
    return out


def canonical_entries(app):
    """One canonical row per pathway group (global panel, each FX panel / module state) that has no row yet:
    source = the seed program, canonical = 1, small amount — the canonicals then drive every pathway in unison."""
    have = {str(r.get("target")) for r in rows(app)}
    groups = {}
    for t in all_targets(app):
        g = t.split("/")[0] if not t.startswith("widget:") else "global panel"
        groups.setdefault(g, []).append(t)
    n = 0
    for g, ts in groups.items():
        for t in ts[:4]:
            if t in have:
                continue
            rows(app).append({"source": "seed", "method": "add", "source2": "const", "target": t, "amount": 0.15,
                              "rate": 8.0, "canonical": 1.0, "enabled": True, "group": g, "canonical_entry": True})
            n += 1
    return n


def _hash01(*a):
    return (hash(a) & 0xFFFFFF) / float(0xFFFFFF)


def _src(app, name, beat, outs, row):
    rate = max(0.0625, float(row.get("rate", 4.0) or 4.0))
    u = (beat / rate) % 1.0
    if name.startswith("lfo:"):
        k = name[4:]
        if k == "sine": return 0.5 + 0.5 * math.sin(2 * math.pi * u)
        if k == "triangle": return 1.0 - abs(2 * u - 1)
        if k == "saw": return u
        if k == "square": return 1.0 if u < 0.5 else 0.0
        if k == "random": return _hash01(int(beat / rate), id(row) & 0xFFFF)
    if name == "seed":
        try:
            import automation_bus as ab
            return ab._canonical_curve(app, row.setdefault("_seed_lane", {"path": "seed:" + str(row.get("target")), "rate": rate}), beat)
        except Exception:
            return 0.5
    if name == "canonical":
        try:
            import r32_finish as rf
            return float(rf.canonical_level(app))
        except Exception:
            return 0.0
    if name == "playhead":
        try:
            n = max(1, len([r for r in app.master_playlist_data if r])); rb = float(app.spin_row_beats.value())
            return min(1.0, beat / max(1e-6, n * rb))
        except Exception:
            return 0.0
    if name.startswith("row:"):
        try: return outs[int(name[4:]) - 1]
        except Exception: return 0.5
    if name.startswith("patch:"):
        inst = name[6:]
        w = [float(c.get("weight", c.get("gain", 1.0)) or 0.0) for c in (getattr(app, "patch_connections", []) or [])
             if isinstance(c, dict) and c.get("target") == inst]
        return max(0.0, min(1.0, sum(w) / max(1, len(w)))) if w else 0.0
    if name == "seq:summative":     # summative branching sequence 0,1,2,6,24,120,720 (log-normalised, one step per rate)
        n = int(beat / rate) % 7
        return math.log1p(math.factorial(n) if n else 0) / math.log1p(720)
    if name.startswith("const:"):   # Eski constants as fixed modulation levels (fractional parts)
        try:
            import eski_constants as ek
            return getattr(ek, name[6:]) % 1.0
        except Exception:
            return 0.5
    if name.startswith("carrier:"):
        try:
            import mm_governor
            return mm_governor.carrier_env(app, name[8:], beat)
        except Exception:
            return 0.0
    if name.startswith("midi:cc"):
        return float((getattr(app, "_r99_cc_values", {}) or {}).get(int(name[7:]), 0)) / 127.0
    if name.startswith("automation:"):
        try:
            import automation_bus as ab
            d, k = ab._resolve(app, name[11:])
            v = float(d[k]); lo, hi = ab._span(k, v)
            return max(0.0, min(1.0, (v - lo) / max(1e-9, hi - lo)))
        except Exception:
            return 0.5
    return float(row.get("const", 0.5) or 0.5)


def _combine(m, a, b, row):
    if m == "add": return a + b - 0.5
    if m == "multiply": return a * b
    if m == "ring": return 0.5 + 0.5 * (2 * a - 1) * (2 * b - 1)
    if m == "min": return min(a, b)
    if m == "max": return max(a, b)
    if m == "crossfade": return (1 - a) * 0.5 + a * b
    if m == "fm": return 0.5 + 0.5 * math.sin(2 * math.pi * (a + 0.5 * (b - 0.5)))
    if m == "fold":
        v = (a + b) % 2.0; return v if v <= 1 else 2 - v
    if m == "sample-hold":
        last_b = row.get("_last_b", 0.0); row["_last_b"] = b
        if b >= 0.5 > last_b or "_held" not in row: row["_held"] = a
        return row["_held"]
    if m == "gate": return a if b > 0.5 else 0.5
    if m == "quantize":
        n = int(1 + b * 16); return round(a * n) / n
    if m == "biode":          # one input, two outputs: halve, then re-compare the dual halves (split by b)
        return 0.5 * a + 0.5 * (a * b + (1 - a) * (1 - b)) - 0.25
    if m == "transratio":     # two inputs, proportional split; unbiased base = one half to each output
        return a / (a + b) if (a + b) > 1e-9 else 0.5
    if m == "tr-nand":        # NAND from a transratiometer splitting the combined A + B (Fig. 9)
        return 1.0 - min(1.0, (a + b) / 2.0) ** 2
    if m == "evaluatum":      # 16.5 % B / 83.5 % Si: strongly inhibits until a sharp breakthrough point
        thr = 0.835 * (0.5 + b) if b > 0 else 0.835
        return 1.0 / (1.0 + math.exp(-40.0 * (a - min(0.99, thr))))
    return a


def master(app):
    """Canonical authority over the whole matrix (0..1). While canonicals are active every row's output is blended
    toward the canonical (seed-program) curve of its target by at least master × the active canonical level."""
    try:
        return float(getattr(app, "r99_mod_matrix_canonical", 0.5))
    except Exception:
        return 0.5


def evaluate(app, beat):
    outs = []
    try:
        import r32_finish as _rf
        _lv = float(_rf.canonical_level(app)) * master(app)
    except Exception:
        _lv = 0.0
    for row in rows(app):
        if not row.get("enabled", True):
            outs.append(0.5); continue
        a = _src(app, str(row.get("source", "lfo:sine")), beat, outs, row)
        b = _src(app, str(row.get("source2", "const")), beat, outs, row)
        v = max(0.0, min(1.0, _combine(str(row.get("method", "add")), a, b, row)))
        c = max(float(row.get("canonical", 0.0) or 0.0), _lv)
        if c > 0:
            try:
                import automation_bus as ab
                cv = ab._canonical_curve(app, row.setdefault("_canon_lane", {"path": str(row.get("target")), "rate": float(row.get("rate", 4.0) or 4.0)}), beat)
                v = (1 - c) * v + c * cv
            except Exception:
                pass
        outs.append(v)
    app._r101_mm_raw = list(outs)
    try:                                   # R101: trigonometric response + fair carrier-dynamic governor
        import mm_governor
        return mm_governor.govern(app, rows(app), outs, beat)
    except Exception:
        return outs


def _apply(app, row, t, v, base_key="base"):
    """Write one modulated value into a target (widget or automation path); only when it really moves."""
    import automation_bus as ab
    bases = row if base_key == "base" else row.setdefault("_route_base", {})
    bk = "base" if base_key == "base" else t
    if t.startswith("widget:"):
        w = getattr(app, t[7:], None)
        if w is None or not hasattr(w, "setValue"):
            return
        if bk not in bases:
            bases[bk] = float(w.value())
        lo, hi = float(w.minimum()), float(w.maximum())
        x = max(lo, min(hi, bases[bk] + float(row.get("amount", 0.5)) * (v - 0.5) * (hi - lo)))
        cur = w.value()
        nv = int(round(x)) if isinstance(cur, int) else x
        # R101: only write when the value really moves (handlers used to fire every tick, ~20/s per row)
        if isinstance(cur, int):
            if nv == cur:
                return
        else:
            try:
                step = float(w.singleStep()) if hasattr(w, "singleStep") else 0.0
            except Exception:
                step = 0.0
            if abs(nv - float(cur)) <= max(1e-9, 0.25 * step if step > 0 else 1e-6 * (hi - lo)):
                return
        w.setValue(nv)
        return
    d, k = ab._resolve(app, t)
    if d is None or k not in d or isinstance(d.get(k), bool):
        return
    if bk not in bases:
        bases[bk] = float(d[k])
    lo, hi = ab._span(k, bases[bk])
    x = max(lo, min(hi, bases[bk] + float(row.get("amount", 0.5)) * (v - 0.5) * (hi - lo)))
    nx = int(round(x)) if isinstance(d.get(k), int) else x
    if d.get(k) != nx:
        d[k] = nx


def tick(app, beat):
    rs = rows(app)
    if not rs:
        return
    outs = evaluate(app, beat)
    raw = getattr(app, "_r101_mm_raw", outs)
    try:
        import mm_governor
        gph = float(mm_governor.effective(app, beat).get("phase_offset", 0.0))
    except Exception:
        mm_governor = None; gph = 0.0
    for idx, (row, v) in enumerate(zip(rs, outs)):
        t = str(row.get("target") or "")
        if not row.get("enabled", True):
            continue
        if t:
            _apply(app, row, t, v)
        if mm_governor is not None and row.get("route"):      # R101 carrier router: rotating trig family
            for rt, rv in mm_governor.routed(row, raw[idx] if idx < len(raw) else v, gph):
                _apply(app, row, rt, rv, base_key="route")


def restore_bases(app):
    import automation_bus as ab
    for row in rows(app):
        t = str(row.get("target") or "")
        if "base" in row and t.startswith("widget:"):
            w = getattr(app, t[7:], None)
            if w is not None and hasattr(w, "setValue"):
                w.setValue(int(round(row["base"])) if isinstance(w.value(), int) else row["base"])
            continue
        if "base" in row:
            d, k = ab._resolve(app, str(row.get("target") or ""))
            if d is not None and k in d:
                d[k] = int(round(row["base"])) if isinstance(d.get(k), int) else row["base"]
    for row in rows(app):                  # R101: router targets
        for t, b in list((row.get("_route_base") or {}).items()):
            if t.startswith("widget:"):
                w = getattr(app, t[7:], None)
                if w is not None and hasattr(w, "setValue"):
                    w.setValue(int(round(b)) if isinstance(w.value(), int) else b)
            else:
                d, k = ab._resolve(app, t)
                if d is not None and k in d:
                    d[k] = int(round(b)) if isinstance(d.get(k), int) else b
        row.pop("_route_base", None)


def install(app):
    rows(app)
    try:
        import canonical_distributor as _cd
        _cd.install(app)
    except Exception:
        pass
    try:
        import midi_io
        def cc(msg):
            if msg and len(msg) >= 3 and (msg[0] & 0xF0) == 0xB0:
                app.__dict__.setdefault("_r99_cc_values", {})[int(msg[1])] = int(msg[2])
        midi_io.hub(app).bridge.message.connect(cc)
    except Exception:
        pass


def open_window(app):
    """The Master Mod Path Matrix: its own window. Left: governor · canonical distribution · Multidim lanes.
    Centre: the 3.5-D stage over the row editor (draggable split). Right: reroute/perspective fields · row response ·
    panel settings. One instance; reopening raises it."""
    from PyQt6.QtCore import Qt, QTimer
    from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QTableWidget, QComboBox, QDoubleSpinBox, QCheckBox, QPushButton,
                                 QHBoxLayout, QLabel, QHeaderView, QSplitter, QToolBox, QScrollArea, QWidget, QFrame,
                                 QSizePolicy)
    old = getattr(app, "_mod_matrix_dialog", None)
    try:
        if old is not None and old.isVisible():
            old.raise_(); old.activateWindow(); return old
    except RuntimeError:
        pass
    try:
        import mm_mirror as _mir
        css = _mir.DIALOG_CSS
    except Exception:
        _mir, css = None, ""
    d = QDialog(app); d.setObjectName("mpmWindow"); d.setWindowTitle("🧬 Master Mod Path Matrix · Mod Path Bay ⇄ Multidim")
    d.setStyleSheet(css + """
QDialog#mpmWindow { background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #050a16, stop:0.55 #0b0d22, stop:1 #150b2a); }
QLabel#mpmTitle { color:#9fe8ff; font-size:17pt; font-weight:900; }
QLabel#mpmSub { color:#9fb3d6; font-size:9pt; }
QLabel#mpmStat { color:#c9b8ff; font-weight:800; background: rgba(40,30,80,170); border:1px solid rgba(150,120,255,120);
                 border-radius:9px; padding:4px 10px; }
QFrame#mpmHeader, QFrame#mpmCol { background: rgba(10,16,30,200); border:1px solid rgba(120,150,255,90); border-radius:14px; }
QSplitter::handle { background: rgba(120,150,255,60); border-radius:2px; }
QSplitter::handle:horizontal { width:6px; } QSplitter::handle:vertical { height:6px; }
""")
    d.setWindowModality(Qt.WindowModality.NonModal); d.resize(1640, 1000); d.setMinimumSize(1100, 700)
    root = QVBoxLayout(d); root.setContentsMargins(10, 10, 10, 10); root.setSpacing(8)

    # ---------------------------------------------------------------- header
    head = QFrame(); head.setObjectName("mpmHeader"); hl = QVBoxLayout(head); hl.setContentsMargins(14, 10, 14, 10)
    top = QHBoxLayout(); hl.addLayout(top)
    title = QLabel("🧬 Master Mod Path Matrix"); title.setObjectName("mpmTitle"); top.addWidget(title)
    stat = QLabel(""); stat.setObjectName("mpmStat"); top.addWidget(stat); top.addStretch(1)
    sub = QLabel("Any source × any method → any target. Rows can feed later rows (row:n), so the matrix is its own patch bay. "
                 "'Canonical' blends a row with its target's seed curve, in unison. Runs live and in every export.")
    sub.setObjectName("mpmSub"); sub.setWordWrap(True); hl.addWidget(sub)
    btns = QHBoxLayout(); hl.addLayout(btns)
    root.addWidget(head)

    # ---------------------------------------------------------------- three columns
    cols3 = QSplitter(Qt.Orientation.Horizontal); cols3.setChildrenCollapsible(False); root.addWidget(cols3, 1)

    def column(min_w):
        fr = QFrame(); fr.setObjectName("mpmCol"); fr.setMinimumWidth(min_w)
        v = QVBoxLayout(fr); v.setContentsMargins(8, 8, 8, 8); v.setSpacing(6)
        return fr, v

    def scrolled(widget):
        sa = QScrollArea(); sa.setWidgetResizable(True); sa.setFrameShape(QFrame.Shape.NoFrame); sa.setWidget(widget)
        return sa

    left, lv = column(300); centre, cv = column(620); right, rv = column(300)
    cols3.addWidget(left); cols3.addWidget(centre); cols3.addWidget(right)
    cols3.setStretchFactor(0, 0); cols3.setStretchFactor(1, 1); cols3.setStretchFactor(2, 0); cols3.setSizes([360, 920, 360])
    lbox = QToolBox(); lv.addWidget(lbox, 1)
    rbox = QToolBox(); rv.addWidget(rbox, 1)

    # centre: stage over the row editor
    vsplit = QSplitter(Qt.Orientation.Vertical); vsplit.setChildrenCollapsible(False); cv.addWidget(vsplit, 1)
    try:                                   # 3.5-D grid · GOAVA shapes · L-systems
        import mm_visual
        stage = mm_visual.make_widget(app, d); stage.setMinimumHeight(260)
        vsplit.addWidget(stage)
    except Exception as _vexc:
        print("[Mod Matrix] stage unavailable:", _vexc)
    editor = QWidget(); ev = QVBoxLayout(editor); ev.setContentsMargins(0, 0, 0, 0); ev.setSpacing(6); vsplit.addWidget(editor)
    vsplit.setSizes([380, 520])

    cols = ("on", "source", "method", "source 2", "target", "amount", "rate (beats)", "canonical",
            "response", "resp freq", "resp phase", "route (+targets)", "spread")
    tab = QTableWidget(0, len(cols)); tab.setHorizontalHeaderLabels(cols); tab.setAlternatingRowColors(True); tab.setMinimumHeight(200)
    tab.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
    tab.horizontalHeader().setStretchLastSection(True); tab.verticalHeader().setDefaultSectionSize(30)
    for i, w_ in enumerate((40, 130, 110, 120, 220, 80, 90, 80, 100, 80, 80, 170, 70)):
        tab.setColumnWidth(i, w_)
    ev.addWidget(tab, 1)
    srcs = sources(app)
    targets = all_targets(app)

    def combo(items, cur, cb):
        c = QComboBox(); c.addItems(items); c.setEditable(True); c.setCurrentText(str(cur)); c.currentTextChanged.connect(cb); return c

    def spin(lo, hi, v, cb, step=0.05):
        s_ = QDoubleSpinBox(); s_.setRange(lo, hi); s_.setSingleStep(step); s_.setDecimals(3); s_.setValue(float(v)); s_.valueChanged.connect(cb); return s_

    def fill():
        tab.setRowCount(0)
        for i, row in enumerate(rows(app)):
            tab.insertRow(i)
            def setter(key, row=row):
                def f(v): row[key] = v; row.pop("base", None) if key == "target" else None; app._shared_mixdown_cache = {}
                return f
            ck = QCheckBox(); ck.setChecked(bool(row.get("enabled", True))); ck.toggled.connect(setter("enabled"))
            tab.setCellWidget(i, 0, ck)
            tab.setCellWidget(i, 1, combo(srcs, row.get("source", "lfo:sine"), setter("source")))
            tab.setCellWidget(i, 2, combo(list(METHODS), row.get("method", "add"), setter("method")))
            tab.setCellWidget(i, 3, combo(srcs, row.get("source2", "const"), setter("source2")))
            tab.setCellWidget(i, 4, combo(targets, row.get("target", ""), setter("target")))
            tab.setCellWidget(i, 5, spin(-2, 2, row.get("amount", 0.5), setter("amount")))
            tab.setCellWidget(i, 6, spin(0.0625, 256, row.get("rate", 4.0), setter("rate"), 0.25))
            tab.setCellWidget(i, 7, spin(0, 1, row.get("canonical", 0.0), setter("canonical")))
            try:
                import mm_governor as _g
                tab.setCellWidget(i, 8, combo(list(_g.RESPONSES), row.get("response", "linear"), setter("response")))
            except Exception:
                pass
            tab.setCellWidget(i, 9, spin(0.0625, 16, row.get("resp_freq", 1.0), setter("resp_freq"), 0.25))
            tab.setCellWidget(i, 10, spin(0, 1, row.get("resp_phase", 0.0), setter("resp_phase")))
            rc = combo([""] + targets, ", ".join(row.get("route") or []) if isinstance(row.get("route"), list) else str(row.get("route") or ""),
                       lambda txt, row=row: row.__setitem__("route", [x.strip() for x in str(txt).split(",") if x.strip()]))
            rc.setToolTip("Extra targets, comma-separated: the row fans out as a rotating trigonometric family (phase offset by spread)")
            tab.setCellWidget(i, 11, rc)
            tab.setCellWidget(i, 12, spin(0, 1, row.get("spread", 0.25), setter("spread")))

    for text, fn in (("＋ Row", lambda: (rows(app).append({"source": "lfo:sine", "method": "add", "source2": "const", "target": targets[0] if targets else "",
                                                          "amount": 0.5, "rate": 4.0, "canonical": 0.0, "enabled": True}), fill())),
                     ("− Last row", lambda: (rows(app) and rows(app).pop(), restore_bases(app), fill())),
                     ("⟲ Restore targets", lambda: restore_bases(app)),
                     ("⚙ Canonical entries (every pathway)", lambda: (canonical_entries(app), fill())),
                     ("⊕ Multidim lanes", lambda: (multidim_lanes(app), fill()))):
        b = QPushButton(text); b.clicked.connect(fn); btns.addWidget(b)
    cm = QDoubleSpinBox(); cm.setRange(0, 1); cm.setSingleStep(0.05); cm.setValue(master(app)); cm.setPrefix("Canonical authority ")
    cm.setToolTip("While canonicals are active, every row blends toward the canonical curve by at least this × their level")
    cm.valueChanged.connect(lambda v: setattr(app, "r99_mod_matrix_canonical", float(v))); btns.addWidget(cm)
    btns.addStretch(1); fill()
    try:                                   # row tools: duplicate · solo · amounts · invert
        __import__("jam_tools").matrix_accessories(app, ev, fill)
    except Exception as _ra_exc:
        print("[Mod Matrix] row tools unavailable:", _ra_exc)

    # ---------------------------------------------------------------- left column
    gov_page = None
    try:                                   # governor (with fair canonical share), column layout
        gov_page = _mir._governor_page(app) if _mir is not None else _governor_panel(app)
        lbox.addItem(scrolled(gov_page), "⚖ Governor · budget · slew · canonical share")
    except Exception as _gexc:
        lbox.addItem(QLabel("governor unavailable: %s" % _gexc), "⚖ Governor")
    try:
        import canonical_distributor as _cd
        lbox.addItem(scrolled(_cd.panel(app, refresh=fill)), "🜂 Canonical distribution")
    except Exception as _cd_exc:
        lbox.addItem(QLabel("canonical distribution unavailable: %s" % _cd_exc), "🜂 Canonical distribution")
    lanes = QWidget(); lnl = QVBoxLayout(lanes); info = QLabel("Route this instrument's Multidim macros (morph · chaos · fold · lattice) "
                                                               "into the matrix as lanes."); info.setWordWrap(True); lnl.addWidget(info)
    def _lanes():
        try:
            n = multidim_lanes(app, app.instrument_selector_dropdown.currentText())
        except Exception:
            n = multidim_lanes(app)
        info.setText("added %d Multidim lanes" % n if n else "this instrument's Multidim macros are already routed (or it has none yet)"); fill()
    lb = QPushButton("⊕ Multidim lanes for the selected instrument"); lb.clicked.connect(_lanes); lnl.addWidget(lb); lnl.addStretch(1)
    lbox.addItem(lanes, "⊕ Multidim lanes")

    # ---------------------------------------------------------------- right column
    try:                                   # reroute (2-D poles) · perspective (3-D rotation + magnitude), one section each
        _rp, _pp = __import__("mm_fields").make_pads(app)
        rbox.addItem(scrolled(_mir._reroute_page(app, _rp)), "🧭 Reroute field · 2-D poles")
        rbox.addItem(scrolled(_mir._perspective_page(app, _pp)), "🌐 Perspective field · 3-D view + magnitude")
    except Exception as _fexc:
        try:
            rbox.addItem(scrolled(__import__("mm_fields").make_panel(app)), "🧭 Reroute · 🌐 perspective fields")
        except Exception:
            rbox.addItem(QLabel("fields unavailable: %s" % _fexc), "🧭 Fields")
    if _mir is not None:
        try:
            rbox.addItem(scrolled(_mir._response_page(app)), "∿ Row response · routing spread")
        except Exception as _rexc:
            print("[Mod Matrix] row response page unavailable:", _rexc)
        try:
            def _apply_panels():
                for fn in (getattr(app, "_r102_mpb_apply", None),):
                    if callable(fn):
                        fn()
            rbox.addItem(scrolled(_mir._mirror_page(app, _apply_panels)), "🪞 Side panels · ring view + Multidim window")
        except Exception as _pexc:
            print("[Mod Matrix] panel settings unavailable:", _pexc)

    # ---------------------------------------------------------------- live status
    def refresh():
        if not d.isVisible():
            return
        v_ = getattr(app, "_r101_governor_view", None) or {}
        n = len(rows(app)); on = sum(1 for r in rows(app) if r.get("enabled", True))
        txt = "rows %d · on %d" % (n, on)
        if v_:
            txt += " · depth %.2f · canonical ×%.2f · user ×%.2f" % (v_.get("depth", 1.0), v_.get("scale_canonical", 1.0), v_.get("scale_user", 1.0))
        stat.setText(txt)
        if v_ and gov_page is not None and hasattr(gov_page, "_r101_view"):
            gov_page._r101_view.setText("depth %.2f · canonical ×%.2f · user ×%.2f · canonical weight %.2f"
                                        % (v_["depth"], v_["scale_canonical"], v_["scale_user"], v_["canonical_weight"]))
    tm = QTimer(d); tm.setInterval(300); tm.timeout.connect(refresh); tm.start(); refresh()
    d.show(); app._mod_matrix_dialog = d
    return d


def _governor_panel(app):
    """Trigonometric response carrier-dynamic governor: budget · knee · slew · carrier follow · canonical share."""
    from PyQt6.QtCore import QTimer
    from PyQt6.QtWidgets import QGroupBox, QHBoxLayout, QCheckBox, QDoubleSpinBox, QComboBox, QLabel
    import mm_governor as G
    g = G.settings(app)
    box = QGroupBox("Governor · trigonometric response · carrier dynamics · fair canonical control"); h = QHBoxLayout(box)
    on = QCheckBox("On"); on.setChecked(bool(g["enabled"])); on.toggled.connect(lambda v: g.__setitem__("enabled", bool(v))); h.addWidget(on)

    def sp(key, lo, hi, step, label, tip):
        s = QDoubleSpinBox(); s.setRange(lo, hi); s.setSingleStep(step); s.setDecimals(3); s.setValue(float(g[key]))
        s.setPrefix(label + " "); s.setToolTip(tip); s.valueChanged.connect(lambda v: g.__setitem__(key, float(v))); h.addWidget(s); return s
    sp("budget", 0.05, 16, 0.1, "budget", "Total modulation depth the whole matrix may use (sum of |deviation| × amount)")
    sp("knee", 0.05, 1.0, 0.05, "knee", "Where the sine soft-knee starts (fraction of the budget)")
    sp("slew", 0.1, 60, 0.5, "slew/s", "Fastest change per second of any row output")
    sp("carrier_follow", 0, 1, 0.05, "carrier follow", "Depth breathes with the chosen carrier's envelope")
    cc = QComboBox(); cc.addItems([s[8:] for s in G.carrier_sources(app)]); cc.setEditable(True); cc.setCurrentText(str(g["carrier"]))
    cc.currentTextChanged.connect(lambda v: g.__setitem__("carrier", v)); h.addWidget(cc)
    sp("canonical_share", 0, 1, 0.05, "canonical share",
       "Fair canonical control: canonical rows own this part of the budget, user rows the rest; while canonicals are "
       "active they also steer budget, slew, carrier follow and response phase by share × canonical level")
    view = QLabel(""); h.addWidget(view, 1)

    def upd():
        v = getattr(app, "_r101_governor_view", None)
        if v:
            view.setText("depth %.2f · canonical ×%.2f · user ×%.2f · canonical weight %.2f"
                         % (v["depth"], v["scale_canonical"], v["scale_user"], v["canonical_weight"]))
    t = QTimer(box); t.setInterval(250); t.timeout.connect(lambda: upd() if box.isVisible() else None); t.start()
    return box


def multidim_lanes(app, name=None):
    """R101 Mod Path Bay: one row per Multidim macro of an instrument (default: the Multidim window's), seeded from
    the Eski constants (Q · B · M as sources) and canonically shared so the seed keeps its say."""
    if name is None:
        w = getattr(app, "_multidim_window", None)
        try:
            name = w.cmb_inst.currentText() if w is not None else app.instrument_selector_dropdown.currentText()
        except Exception:
            name = None
    st = ((getattr(app, "instrument_param_state", {}) or {}).get(name) or {}) if name else {}
    clones = st.get("md_clones") or {}
    if not isinstance(clones, dict) or not clones:
        return 0
    clone, values = next(((k, v) for k, v in clones.items() if isinstance(v, dict) and "morph" in v),
                         ("", clones) if "morph" in clones else (None, None))
    if values is None:
        return 0
    base = "instrument_param_state/%s/md_clones" % name + ("/%s" % clone if clone else "")
    plan = (("morph", "const:Q", "quetta"), ("chaos", "seed", "sine"), ("fold_depth", "const:M", "metta"),
            ("harmonic_lattice", "const:B", "betta"), ("harmonic_freq", "lfo:sine", "harmonic"))
    have = {str(r.get("target")) for r in rows(app)}; n = 0
    for key, src, resp in plan:
        t = "%s/%s" % (base, key)
        if key in values and t not in have:
            rows(app).append({"source": src, "method": "add", "source2": "const", "target": t, "amount": 0.2 if key != "harmonic_freq" else 0.02,
                              "rate": 16.0, "canonical": 0.5, "enabled": True, "response": resp, "group": "Multidim · %s" % name})
            n += 1
    return n
