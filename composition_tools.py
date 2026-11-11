"""composition_tools.py — GROOVEBOX_R32_COMPOSITION_TOOLS_20261110

Four tools that work together on the main creation suite, plus playback styles:

  SEED MORPH       blend two seed programs: the result is ONE program that evaluates both
                   (each wrapped as a function) and returns (1-m)·A + m·B, element-wise;
                   m can itself follow time ("morph over the song").
  SONG FORM        a section plan (intro / A / B / bridge / outro …) derived from the seed
                   program's signature; written as playlist row tags (section, row
                   transpose, row level) through the ordinary row fields.
  TUNING LATTICE   the live key scale: linear (legacy), 12-EDO, just intonation, Meum,
                   golden, harmonic series, Bohlen–Pierce; replaces _keychart_ratio.
  DIVERSITY METER  how different the current seed's engine data is from the last seeds
                   used (signature Hamming distance + value-curve correlation), 0–100 %.
  PLAYBACK STYLES  forward · reverse · ping-pong · seeded shuffle · section loop · random
                   walk (seeded) — applied to the frozen render playlist only, never to
                   the stored rows (so they are reversible and export-identical per seed).
"""
from __future__ import annotations

import math

import numpy as np

# ---------------------------------------------------------------------------
# Seed morph
# ---------------------------------------------------------------------------
def _as_function(name, text):
    body = str(text or "0").strip("\n").split("\n")
    return ["def %s():" % name] + ["    " + ln for ln in body] + ["    return None"]


def morph_program(a, b, amount=0.5, over_time=False):
    m = "clamp(t_norm, 0, 1)" if over_time else repr(float(max(0.0, min(1.0, amount))))
    lines = ["# Seed morph · A ↔ B (%s)" % ("over the song" if over_time else "m = %s" % m)]
    lines += _as_function("_seed_a", a) + _as_function("_seed_b", b)
    lines += ["_va = _seed_a()", "_vb = _seed_b()",
              "_la = list(_va) if isinstance(_va, (list, tuple)) else [_va if _va is not None else 0.0]",
              "_lb = list(_vb) if isinstance(_vb, (list, tuple)) else [_vb if _vb is not None else 0.0]",
              "_m = %s" % m, "_n = max(len(_la), len(_lb))",
              "return [(1 - _m) * float(_la[i % len(_la)]) + _m * float(_lb[i % len(_lb)]) for i in range(_n)]"]
    out = "\n".join(lines)
    return out if out.count("\n") < 256 else "\n".join(lines[:255])


# ---------------------------------------------------------------------------
# Song form
# ---------------------------------------------------------------------------
FORMS = (("intro", "A", "A", "B", "A", "outro"), ("intro", "A", "B", "A", "B", "bridge", "B", "outro"),
         ("A", "B", "A", "C", "A"), ("intro", "build", "drop", "break", "drop", "outro"),
         ("A", "A", "B", "B", "A", "C", "A"))
SECTION_SHAPE = {"intro": (0, 0.7), "outro": (0, 0.6), "A": (0, 1.0), "B": (5, 1.0), "C": (7, 0.95),
                 "bridge": (-2, 0.85), "build": (2, 0.9), "drop": (0, 1.1), "break": (-5, 0.7)}


def song_form(signature, n_rows):
    rng = np.random.default_rng(int(signature) & 0x7FFFFFFF or 1)
    form = FORMS[int(rng.integers(0, len(FORMS)))]
    n_rows = max(1, int(n_rows))
    w = rng.uniform(0.6, 1.4, len(form)); w /= w.sum()
    bounds = np.round(np.cumsum(w) * n_rows).astype(int)
    plan, start = [], 0
    for sec, end in zip(form, bounds):
        end = max(start + 1, min(n_rows, int(end)))
        tr, lv = SECTION_SHAPE.get(sec, (0, 1.0))
        plan.append({"section": sec, "start": start, "end": end, "transpose": tr, "level": lv})
        start = end
        if start >= n_rows:
            break
    return plan


def apply_song_form(app):
    rows = getattr(app, "master_playlist_data", None) or []
    sig = int(getattr(app, "_seed_program_signature", lambda: 0)() or 1)
    plan = song_form(sig, len(rows))
    for sec in plan:
        for i in range(sec["start"], min(sec["end"], len(rows))):
            if isinstance(rows[i], dict):
                rows[i]["section"] = sec["section"]
                rows[i]["row_transpose_semitones"] = float(sec["transpose"])
                rows[i]["row_level"] = float(sec["level"])
    app.r32_song_form = plan
    f = getattr(app, "_on_live_source_changed", None)
    if callable(f):
        f()
    return plan


# ---------------------------------------------------------------------------
# Tuning lattice
# ---------------------------------------------------------------------------
JUST = (1, 16 / 15, 9 / 8, 6 / 5, 5 / 4, 4 / 3, 45 / 32, 3 / 2, 8 / 5, 5 / 3, 9 / 5, 15 / 8)
TUNINGS = ("linear (legacy)", "12-EDO", "just", "meum", "golden", "harmonic", "bohlen-pierce")


def tuning_ratio(kind, degree, steps=12):
    d = int(degree)
    if kind == "12-EDO":
        return 2.0 ** (d / 12.0)
    if kind == "just":
        o, k = divmod(d, 12)
        return JUST[k] * 2.0 ** o
    if kind == "meum":
        return (2.0 ** (1 / 12.0)) ** (d * 7 % 12 + 12 * (d // 12))       # circle-of-fifths Meum steps
    if kind == "golden":
        return 1.61803398875 ** (d / 5.0)
    if kind == "harmonic":
        o, k = divmod(d, 8)
        return (8 + k) / 8.0 * 2.0 ** o
    if kind == "bohlen-pierce":
        return 3.0 ** (d / 13.0)
    return 1.0 + float(d) / float(max(1, steps))


def install_tuning(app):
    if getattr(app, "_r32_tuning_hooked", False):
        return
    orig = app._keychart_ratio

    def _ratio(degree, _orig=orig):
        kind = getattr(app, "r32_tuning", "linear (legacy)")
        if kind == "linear (legacy)":
            return _orig(degree)
        return tuning_ratio(kind, degree, int(getattr(app, "_keychart_steps", 12)))
    app._keychart_ratio = _ratio
    app._r32_tuning_hooked = True


# ---------------------------------------------------------------------------
# Diversity meter
# ---------------------------------------------------------------------------
def _curve(app, text):
    import seed_lang
    gb = __import__("groovebox")
    vals = []
    for tt in np.linspace(0, 16, 33):
        ev = seed_lang.evaluate(text, gb._seed_script_env(t_scalar=float(tt)))
        vals.append(ev.values[0] if ev.values else 0.0)
    return np.asarray(vals, dtype=np.float64)


def diversity(app):
    """(percent, details) for the current seed vs the history of seeds used this session."""
    text = app._seed_text()
    hist = app.__dict__.setdefault("r32_seed_history", [])
    cur_sig = int(app._seed_program_signature() or 0)
    cur = _curve(app, text)
    if not hist:
        hist.append((text, cur_sig, cur))
        return 100.0, "first seed of the session"
    scores = []
    for _t, sig, c in hist[-8:]:
        ham = bin((cur_sig ^ sig) & 0x7FFFFFFF).count("1") / 31.0
        a, b = cur - cur.mean(), c - c.mean()
        den = float(np.sqrt((a * a).sum() * (b * b).sum()))
        corr = float((a * b).sum() / den) if den > 1e-12 else (1.0 if np.allclose(cur, c) else 0.0)
        scores.append(0.5 * ham + 0.5 * (1.0 - abs(corr)))
    if hist[-1][1] != cur_sig:
        hist.append((text, cur_sig, cur))
        del hist[:-16]
    pct = 100.0 * min(scores)
    return pct, "closest of the last %d seeds: %.0f %% different" % (len(scores), pct)


# ---------------------------------------------------------------------------
# Playback styles (render playlist only)
# ---------------------------------------------------------------------------
STYLES = ("forward", "reverse", "ping-pong", "seeded shuffle", "section loop", "random walk")


def styled_rows(app, rows):
    style = getattr(app, "r32_playback_style", "forward")
    rows = list(rows or [])
    n = len(rows)
    if n < 2 or style == "forward":
        return rows
    sig = int(getattr(app, "_seed_program_signature", lambda: 0)() or 1)
    rng = np.random.default_rng(sig)
    if style == "reverse":
        return rows[::-1]
    if style == "ping-pong":
        return rows + rows[-2:0:-1]
    if style == "seeded shuffle":
        return [rows[i] for i in rng.permutation(n)]
    if style == "section loop":
        plan = getattr(app, "r32_song_form", None) or song_form(sig, n)
        out = []
        for sec in plan:
            seg = rows[sec["start"]:sec["end"]]
            out += seg * (2 if sec["section"] in ("A", "drop") else 1)
        return out or rows
    if style == "random walk":
        i, out = 0, []
        for _ in range(n):
            out.append(rows[i]); i = int(np.clip(i + rng.choice((-1, 1, 1)), 0, n - 1))
        return out
    return rows


# ---------------------------------------------------------------------------
# window
# ---------------------------------------------------------------------------
def open_window(app):
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QGroupBox, QGridLayout, QLabel, QTextEdit, QPushButton,
                                 QDoubleSpinBox, QCheckBox, QComboBox, QProgressBar)
    install_tuning(app)
    w = getattr(app, "_composition_tools_window", None)
    try:
        if w is not None:
            w.show(); w.raise_(); return w
    except RuntimeError:
        pass
    w = QWidget(app, Qt.WindowType.Window); w.setWindowTitle("🧬 Composition Tools · morph · form · tuning · diversity · playback")
    w.resize(760, 760); lay = QVBoxLayout(w)
    # morph
    mg = QGroupBox("Seed Morph"); ml = QGridLayout(mg)
    ea, eb = QTextEdit(), QTextEdit()
    ea.setPlainText(app._seed_text()); eb.setPlaceholderText("seed B (any program)")
    for e in (ea, eb):
        e.setStyleSheet("font-family:Consolas,monospace;font-size:9pt;"); e.setMaximumHeight(110)
    amt = QDoubleSpinBox(); amt.setRange(0, 1); amt.setSingleStep(0.05); amt.setValue(0.5)
    over = QCheckBox("morph over the song (m = t_norm)")
    bm = QPushButton("Write morph into the seed field")
    bm.clicked.connect(lambda: app.input_seed_val.setPlainText(morph_program(ea.toPlainText(), eb.toPlainText(), amt.value(), over.isChecked())))
    ml.addWidget(QLabel("A"), 0, 0); ml.addWidget(ea, 0, 1); ml.addWidget(QLabel("B"), 1, 0); ml.addWidget(eb, 1, 1)
    ml.addWidget(QLabel("m"), 2, 0); ml.addWidget(amt, 2, 1); ml.addWidget(over, 3, 1); ml.addWidget(bm, 4, 1)
    lay.addWidget(mg)
    # form
    fg = QGroupBox("Song Form"); fl = QVBoxLayout(fg)
    fout = QLabel("—"); fout.setWordWrap(True)
    bf = QPushButton("Write the seed's song form into the playlist rows")
    bf.clicked.connect(lambda: fout.setText(" · ".join("%s %d–%d (%+d st, ×%.2f)" % (s["section"], s["start"] + 1, s["end"], s["transpose"], s["level"]) for s in apply_song_form(app))))
    fl.addWidget(bf); fl.addWidget(fout); lay.addWidget(fg)
    # tuning + playback
    tg = QGroupBox("Tuning lattice · Playback style"); tl = QGridLayout(tg)
    ct = QComboBox(); ct.addItems(TUNINGS); ct.setCurrentText(getattr(app, "r32_tuning", "linear (legacy)"))
    ct.currentTextChanged.connect(lambda v: setattr(app, "r32_tuning", v))
    cs = QComboBox(); cs.addItems(STYLES); cs.setCurrentText(getattr(app, "r32_playback_style", "forward"))
    cs.currentTextChanged.connect(lambda v: (setattr(app, "r32_playback_style", v), app._on_live_source_changed()))
    tl.addWidget(QLabel("Key tuning"), 0, 0); tl.addWidget(ct, 0, 1)
    tl.addWidget(QLabel("Playback / export style"), 1, 0); tl.addWidget(cs, 1, 1)
    lay.addWidget(tg)
    # diversity
    dg = QGroupBox("Diversity meter"); dl = QVBoxLayout(dg)
    bar = QProgressBar(); bar.setRange(0, 100); dlab = QLabel("")
    bd = QPushButton("Measure current seed")

    def _measure():
        try:
            p, txt = diversity(app); bar.setValue(int(round(p))); dlab.setText(txt)
        except Exception as exc:
            dlab.setText("failed: %s" % exc)
    bd.clicked.connect(_measure)
    dl.addWidget(bar); dl.addWidget(dlab); dl.addWidget(bd); lay.addWidget(dg)
    lay.addStretch(1)
    app._composition_tools_window = w
    w.show(); return w
