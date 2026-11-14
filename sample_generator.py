"""sample_generator.py — GROOVEBOX_R32_SAMPLE_GENERATOR_20261110

The left-hand "SAMPLE ▸ GENERATOR" panel: dedicated generated samples that can layer into
the synths and take part in modulation routing.

Kinds
  NOISE        white · pink (−3 dB/oct by octave summation, no filters) · brown (integrated)
  STATIC       sparse crackle / impulses (Poisson, deterministic)
  OBFUSCATED   the selected instrument's own voice, block-shuffled and sign-scrambled by the
               seed (recognisably *its* spectrum, unrecognisable as a phrase)
  STRUCTURED   non-noise: seeded additive partial sets on the project base frequency
               (harmonic · Meum · golden · prime ratios), with a seeded amplitude contour
All kinds are deterministic from (seed signature, slot, kind): same project, same sample.

Layering: ``layer_amount`` (0..1) adds the sample into the selected instrument's voice
(local) or into every voice (global).

Modulation routes (I/O): sources {sample_env, sample_rms, global_<param>} → destinations
{pitch, amp, morph, fractal, eqr, hyper, sample_level, sample_rate}.  Global parameters
can be sources AND destinations, so a route can read/write them; every route has an
amount and an "owner": user or canonical (canonical routes are derived from the seed and
follow the canonical mode).
"""
from __future__ import annotations

import math

import numpy as np

KINDS = ("noise_white", "noise_pink", "noise_brown", "static", "obfuscated", "structured")
SOURCES = ("sample_env", "sample_rms", "global_energy", "global_bpm", "global_seed", "global_master_level")
DESTS = ("pitch", "amp", "morph", "fractal", "eqr", "hyper", "sample_level", "sample_rate", "global_energy")
RATIO_SETS = {"harmonic": [1, 2, 3, 4, 5, 6, 7, 8], "meum": [2 ** (k / 12) for k in (0, 3, 7, 12, 15, 19, 24)],
              "golden": [1.61803398875 ** k for k in range(6)], "prime": [1, 2, 3, 5, 7, 11, 13]}


def _rng(seed, slot, kind):
    try:
        import groovebox as gb
        return np.random.default_rng(gb.seed_child(seed, "sample", int(slot), kind))
    except Exception:
        return np.random.default_rng((int(seed) * 1000003 + int(slot) * 7919 + hash(kind)) & 0x7FFFFFFF)


def generate(kind, seconds, sr, seed=0, slot=0, base_hz=432.0, source=None, ratio_set="harmonic"):
    n = max(1, int(seconds * sr))
    r = _rng(seed, slot, kind)
    if kind == "noise_white":
        y = r.standard_normal(n)
    elif kind == "noise_pink":
        y = np.zeros(n)
        for o in range(8):                         # Voss–McCartney octave summation
            step = 2 ** o
            vals = r.standard_normal(n // step + 2)
            y += np.repeat(vals, step)[:n]
        y /= 8.0
    elif kind == "noise_brown":
        y = np.cumsum(r.standard_normal(n))
        y -= np.linspace(y[0], y[-1], n)           # remove drift deterministically
    elif kind == "static":
        y = np.zeros(n)
        k = max(1, int(n / sr * 40))
        pos = r.integers(0, n, k)
        y[pos] = r.uniform(-1, 1, k)
        y = np.convolve(y, np.exp(-np.arange(64) / 6.0), mode="same")
    elif kind == "obfuscated" and source is not None and np.asarray(source).size > 512:
        s = np.asarray(source, dtype=np.float64).ravel()
        blk = 512
        blocks = [s[i:i + blk] for i in range(0, s.size - blk + 1, blk)]
        order = r.permutation(len(blocks))
        signs = np.where(r.random(len(blocks)) > 0.5, 1.0, -1.0)
        y = np.concatenate([blocks[i][::(1 if signs[j] > 0 else -1)] * signs[j] for j, i in enumerate(order)])
        y = np.resize(y, n)
    else:                                          # structured (also obfuscated without a source)
        t = np.arange(n) / sr
        ratios = RATIO_SETS.get(ratio_set, RATIO_SETS["harmonic"])
        y = np.zeros(n)
        for k, q in enumerate(ratios):
            amp = r.uniform(0.2, 1.0) / (k + 1)
            ph = r.uniform(0, 2 * math.pi)
            f = base_hz * q
            if f < sr / 2:
                y += amp * np.sin(2 * math.pi * f * t + ph)
        contour = np.interp(np.linspace(0, 1, n), np.linspace(0, 1, 9), r.uniform(0.2, 1.0, 9))
        y *= contour
    pk = float(np.max(np.abs(y))) or 1.0
    return (y / pk * 0.8).astype(np.float32)


def envelope(x, sr, ms=20.0):
    blk = max(1, int(sr * ms / 1000.0))
    a = np.abs(np.asarray(x, dtype=np.float32))
    n = a.size // blk * blk
    if n == 0:
        return np.zeros(1, dtype=np.float32)
    return a[:n].reshape(-1, blk).max(axis=1)


class SampleGenerator:
    """State + routing for one scope (local per instrument, or global)."""

    def __init__(self):
        self.kind = "structured"
        self.seconds = 2.0
        self.layer = 0.0
        self.ratio_set = "harmonic"
        self.routes = []        # dicts: {"src","dst","amount","owner"}
        self.buffer = None
        self.sr = 44100

    def render(self, app, slot=0, source=None):
        try:
            seed = int(app._seed_program_signature() or 0) or int(abs(float(app.get_numeric_seed())) * 1000) or 1
        except Exception:
            seed = 1
        base = float(getattr(app, "global_base_frequency_hz", 432.0) or 432.0)
        self.buffer = generate(self.kind, self.seconds, self.sr, seed, slot, base, source, self.ratio_set)
        return self.buffer

    def canonical_routes(self, app, slot=0):
        r = _rng(int(getattr(app, "_seed_program_signature", lambda: 1)() or 1), slot, "routes")
        k = int(r.integers(1, 4))
        return [{"src": SOURCES[int(r.integers(0, len(SOURCES)))], "dst": DESTS[int(r.integers(0, len(DESTS)))],
                 "amount": float(np.round(r.uniform(0.05, 0.4), 3)), "owner": "canonical"} for _ in range(k)]

    def source_value(self, app, src, t_norm=0.0):
        if src in ("sample_env", "sample_rms") and self.buffer is not None and self.buffer.size:
            env = envelope(self.buffer, self.sr)
            if src == "sample_rms":
                return float(np.sqrt(np.mean(self.buffer.astype(np.float64) ** 2)))
            return float(env[min(env.size - 1, int(max(0.0, min(1.0, t_norm)) * env.size))])
        gm = getattr(app, "r32_global_params", {}) or {}
        if src == "global_bpm":
            return float(getattr(app, "global_bpm", 120.0) or 120.0) / 240.0
        if src == "global_seed":
            return (int(getattr(app, "_seed_program_signature", lambda: 0)() or 0) % 1000) / 1000.0
        return float(gm.get(src[7:], 0.5)) if src.startswith("global_") else 0.0

    def modulations(self, app, t_norm=0.0, slot=0):
        """{dest: delta} from every route (user + canonical, per canonical mode)."""
        routes = list(self.routes)
        mode = getattr(app, "canonical_mode", "protected")
        if mode in ("protected", "direct") or not routes:
            routes += self.canonical_routes(app, slot)
        out = {}
        for rt in routes:
            v = self.source_value(app, rt["src"], t_norm)
            out[rt["dst"]] = out.get(rt["dst"], 0.0) + float(rt["amount"]) * (v - 0.5) * 2.0
        # destinations that are global parameters are written back (I/O)
        gm = app.__dict__.setdefault("r32_global_params", {})
        for d, dv in out.items():
            if d.startswith("global_"):
                gm[d[7:]] = float(np.clip(0.5 + dv, 0.0, 1.0))
        return out


def install_hooks(app):
    """Layer the generated sample into voices (wraps _render_instrument_voice once more)."""
    if getattr(app, "_r32_sample_hooked", False):
        return
    app.r32_sample_local = {}
    app.r32_sample_global = SampleGenerator()
    orig = getattr(app, "_render_instrument_voice", None)
    if callable(orig):
        def _voice(name, hz, t, dur, sr, _orig=orig):
            out = _orig(name, hz, t, dur, sr)
            try:
                arr = np.asarray(out)
                for gen in (app.r32_sample_local.get(str(name)), app.r32_sample_global):
                    if gen is None or gen.buffer is None or arr.ndim != 1:
                        continue
                    try:
                        import r32_rowctx
                        _ov = r32_rowctx.num("sample_layer", None, 0.0, 1.0)
                    except Exception:
                        _ov = None
                    if (gen.layer if _ov is None else _ov) <= 0:
                        continue
                    mods = gen.modulations(app, 0.0)
                    lvl = (gen.layer if _ov is None else _ov) * (1.0 + mods.get("sample_level", 0.0))
                    if lvl <= 0:
                        continue
                    rate = max(0.25, 1.0 + mods.get("sample_rate", 0.0)) * (gen.sr / float(sr))
                    idx = (np.arange(arr.size) * rate) % gen.buffer.size
                    arr = arr + lvl * np.interp(idx, np.arange(gen.buffer.size), gen.buffer).astype(arr.dtype)
                    amp = 1.0 + mods.get("amp", 0.0)
                    arr = arr * amp
                out = arr
            except Exception:
                pass
            return out
        app._render_instrument_voice = _voice
    app._r32_sample_hooked = True


def make_panel(app):
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import (QGroupBox, QGridLayout, QLabel, QComboBox, QSlider, QPushButton, QDoubleSpinBox,
                                 QListWidget, QCheckBox)
    install_hooks(app)
    box = QGroupBox("SAMPLE ▸ GENERATOR · noise / static / obfuscated / structured")
    box.setStyleSheet("QGroupBox{color:#9ece6a;background:#000000;border:1px solid #9ece6a;border-radius:7px;margin-top:6px;"
                      "padding-top:10px;font-weight:900;}QLabel,QCheckBox{color:#ffffff;font-size:8pt;}")
    g = QGridLayout(box); g.setContentsMargins(5, 9, 5, 4)
    scope = QComboBox(); scope.addItems(["Local (selected instrument)", "Global (every voice)"])
    kind = QComboBox(); kind.addItems(KINDS); kind.setCurrentText("structured")
    ratios = QComboBox(); ratios.addItems(list(RATIO_SETS))
    secs = QDoubleSpinBox(); secs.setRange(0.1, 30.0); secs.setValue(2.0); secs.setSuffix(" s")
    layer = QSlider(Qt.Orientation.Horizontal); layer.setRange(0, 100)
    info = QLabel("")
    routes = QListWidget(); routes.setMaximumHeight(90)
    src = QComboBox(); src.addItems(SOURCES); dst = QComboBox(); dst.addItems(DESTS)
    amt = QDoubleSpinBox(); amt.setRange(-1.0, 1.0); amt.setSingleStep(0.05); amt.setValue(0.25)
    canon = QCheckBox("canonical route")

    def gen():
        if scope.currentIndex() == 1:
            return app.r32_sample_global
        name = app.instrument_selector_dropdown.currentText() if hasattr(app, "instrument_selector_dropdown") else ""
        return app.r32_sample_local.setdefault(name, SampleGenerator())

    def refresh():
        gn = gen()
        routes.clear()
        for rt in gn.routes:
            routes.addItem("%s → %s  %+.2f  (%s)" % (rt["src"], rt["dst"], rt["amount"], rt["owner"]))
        for rt in gn.canonical_routes(app):
            routes.addItem("⟡ %s → %s  %+.2f  (canonical)" % (rt["src"], rt["dst"], rt["amount"]))

    def do_render():
        gn = gen(); gn.kind = kind.currentText(); gn.seconds = secs.value(); gn.ratio_set = ratios.currentText()
        source = None
        if gn.kind == "obfuscated":
            try:
                name = app.instrument_selector_dropdown.currentText()
                t = np.arange(int(gn.sr * gn.seconds)) / gn.sr
                source = app._render_instrument_voice(name, 220.0, t, gn.seconds, gn.sr)
            except Exception:
                source = None
        b = gn.render(app, source=source)
        info.setText("%s · %.1f s · peak %.2f" % (gn.kind, b.size / gn.sr, float(np.max(np.abs(b)))))

    def do_audition():
        gn = gen()
        if gn.buffer is None:
            do_render()
        try:
            app._pkp_poly_submit(gn.buffer, gn.sr)
        except Exception:
            pass

    def add_route():
        gen().routes.append({"src": src.currentText(), "dst": dst.currentText(), "amount": float(amt.value()),
                             "owner": "canonical" if canon.isChecked() else "user"})
        refresh()

    def del_route():
        r = routes.currentRow(); gn = gen()
        if 0 <= r < len(gn.routes):
            del gn.routes[r]
        refresh()

    layer.valueChanged.connect(lambda v: setattr(gen(), "layer", v / 100.0))
    scope.currentIndexChanged.connect(lambda *_: (layer.setValue(int(gen().layer * 100)), refresh()))
    rows = (("Scope", scope), ("Kind", kind), ("Ratios", ratios), ("Length", secs), ("Layer into synth", layer))
    for i, (cap, w) in enumerate(rows):
        g.addWidget(QLabel(cap), i, 0); g.addWidget(w, i, 1, 1, 3)
    r0 = len(rows)
    for j, (cap, fn) in enumerate((("⟳ Generate", do_render), ("▶ Audition", do_audition))):
        b = QPushButton(cap); b.clicked.connect(fn); g.addWidget(b, r0, j * 2, 1, 2)
    g.addWidget(info, r0 + 1, 0, 1, 4)
    g.addWidget(QLabel("Modulation routes (source → destination)"), r0 + 2, 0, 1, 4)
    g.addWidget(routes, r0 + 3, 0, 1, 4)
    g.addWidget(src, r0 + 4, 0); g.addWidget(dst, r0 + 4, 1); g.addWidget(amt, r0 + 4, 2); g.addWidget(canon, r0 + 4, 3)
    b_add = QPushButton("+ route"); b_add.clicked.connect(add_route); g.addWidget(b_add, r0 + 5, 0, 1, 2)
    b_del = QPushButton("− route"); b_del.clicked.connect(del_route); g.addWidget(b_del, r0 + 5, 2, 1, 2)
    if hasattr(app, "instrument_selector_dropdown"):
        app.instrument_selector_dropdown.currentIndexChanged.connect(lambda *_: refresh())
    refresh()
    return box
