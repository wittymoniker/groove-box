"""canonical_distributor.py — canonicals write DISTRIBUTED settings instead of condensing an effect into one control.

An effect the canonicals want (its size = budget × the active canonical level) is spread over every enabled
modulation pathway with a convolution kernel across the ordered target list, so many controls each move a little
toward the goal and no single control carries it. The result is a set of canonical mod-matrix rows (one per target).

You choose
  WHAT     scope: which pathway groups take part (global panel, each FX / module state, tuning, …)
  HOW      kernel: gaussian (smooth spread) · uniform (equal shares) · seed (weights read from the seed program) ·
           convolve (gaussian convolved with the seed weights); spread width; method per row (add / multiply / fm …)
  HOW MUCH budget (total movement shared by all targets), cap per target
  PROCESS  reading: which inputs decide the weights — seed, canonical level, current values (targets already far from
           centre get less), user ownership (user-touched targets are skipped) — and "only if it improves".

"Improves" is measured by a stated, cheap objective, not by listening:  J = coverage × (1 − concentration) × fit,
  coverage = share of enabled groups that receive any movement,
  concentration = Herfindahl index of the per-target amounts (1 = one control carries everything),
  fit = 1 − mean |current position − 0.5| over the moved targets (room to move without hitting a limit).
A new distribution replaces the old one only when its J is higher (or when "only if it improves" is off).
"""
from __future__ import annotations
import math
try:  # R132.10: project trig route — book isy/isx series when the Trigonometry Engine is ON (gb_trig)
    from gb_trig import sin as _tsin
except Exception:  # standalone use outside the app
    from math import sin as _tsin

DEFAULTS = {"enabled": True, "auto": True, "only_if_improves": True, "kernel": "convolve", "width": 0.18,
            "budget": 0.6, "cap": 0.25, "method": "add", "rate": 8.0,
            "read_seed": True, "read_level": True, "read_values": True, "skip_user": True, "groups": {}}


def settings(app):
    st = getattr(app, "r99_canon_dist", None)
    if not isinstance(st, dict):
        st = app.r99_canon_dist = {}
    for k, v in DEFAULTS.items():
        st.setdefault(k, v if not isinstance(v, dict) else dict(v))
    return st


def _groups(app):
    import mod_matrix as mm
    out = {}
    for t in mm.all_targets(app):
        g = "global panel" if t.startswith("widget:") else t.split("/")[0]
        out.setdefault(g, []).append(t)
    return out


def _pos(app, t):
    try:
        if t.startswith("widget:"):
            w = getattr(app, t[7:]); lo, hi = float(w.minimum()), float(w.maximum()); return (float(w.value()) - lo) / max(1e-9, hi - lo)
        import automation_bus as ab
        d, k = ab._resolve(app, t); v = float(d[k]); lo, hi = ab._span(k, v); return (v - lo) / max(1e-9, hi - lo)
    except Exception:
        return 0.5


def _seed_w(app, i, n):
    try:
        vals = app.get_seed_values(float(i) / max(1, n)) or [0.0]
        return 0.5 + 0.5 * _tsin(float(vals[i % len(vals)]) * 1.6180339887 + i)
    except Exception:
        return 0.5


def plan(app):
    """[(target, amount)] for the current settings (no state is changed)."""
    st = settings(app)
    groups = _groups(app)
    on = [g for g in groups if st["groups"].get(g, True)]
    targets = [t for g in on for t in groups[g]]
    if not targets:
        return []
    try:
        import r32_finish as rf
        level = float(rf.canonical_level(app)) if st["read_level"] else 1.0
    except Exception:
        level = 1.0
    budget = float(st["budget"]) * level
    if budget <= 0:
        return []
    n = len(targets)
    user = set()
    if st["skip_user"]:
        user = {str(r.get("target")) for r in (getattr(app, "r99_mod_matrix", None) or []) if not r.get("canonical_entry")}
    # centre of the effect: read from the seed (or the middle)
    c = (_seed_w(app, 0, n) if st["read_seed"] else 0.5) * (n - 1)
    w = max(0.01, float(st["width"])) * n
    kern = []
    for i, t in enumerate(targets):
        if t in user:
            kern.append(0.0); continue
        gk = math.exp(-0.5 * ((i - c) / w) ** 2)
        sk = _seed_w(app, i, n) if st["read_seed"] else 1.0
        k = {"gaussian": gk, "uniform": 1.0, "seed": sk, "convolve": gk * (0.25 + 0.75 * sk)}.get(st["kernel"], gk)
        if st["read_values"]:
            k *= max(0.05, 1.0 - 2.0 * abs(_pos(app, t) - 0.5))       # room to move
        kern.append(k)
    tot = sum(kern) or 1.0
    cap = float(st["cap"])
    out = [(t, min(cap, budget * k / tot)) for t, k in zip(targets, kern) if k > 0]
    return [(t, a) for t, a in out if a > 1e-4]


def objective(app, amounts):
    """J = coverage × (1 − concentration) × fit (see module doc)."""
    if not amounts:
        return 0.0
    st = settings(app); groups = _groups(app)
    on = [g for g in groups if st["groups"].get(g, True)] or list(groups)
    touched = {("global panel" if t.startswith("widget:") else t.split("/")[0]) for t, _ in amounts}
    coverage = len(touched & set(on)) / max(1, len(on))
    s = sum(a for _, a in amounts) or 1.0
    hhi = sum((a / s) ** 2 for _, a in amounts)
    fit = 1.0 - sum(abs(_pos(app, t) - 0.5) for t, _ in amounts) / len(amounts)
    return coverage * (1.0 - hhi) * fit


def current(app):
    return [(str(r.get("target")), float(r.get("amount", 0))) for r in (getattr(app, "r99_mod_matrix", None) or []) if r.get("canonical_entry")]


def distribute(app, force=False):
    """Write the distribution as canonical mod-matrix rows. Returns (applied, J_new, J_old, n)."""
    import mod_matrix as mm
    st = settings(app)
    if not st["enabled"] and not force:
        return False, 0.0, 0.0, 0
    new = plan(app); old = current(app)
    jn, jo = objective(app, new), objective(app, old)
    if st["only_if_improves"] and not force and old and jn <= jo + 1e-6:
        return False, jn, jo, len(new)
    mm.restore_bases(app)
    keep = [r for r in mm.rows(app) if not r.get("canonical_entry")]
    for t, a in new:
        keep.append({"source": "seed", "method": st["method"], "source2": "canonical", "target": t, "amount": round(a, 5),
                     "rate": float(st["rate"]), "canonical": 1.0, "enabled": True, "canonical_entry": True})
    app.r99_mod_matrix = keep
    app._shared_mixdown_cache = {}
    try:
        __import__("notify_center").notify(app, "Canonical distribution · %d targets · J %.3f → %.3f" % (len(new), jo, jn), "canonical",
                                           key="canon-dist", every_s=6)
    except Exception:
        pass
    return True, jn, jo, len(new)


def install(app):
    """Re-distribute after every canonical commit when 'auto' is on (cheap: arithmetic over the target list)."""
    settings(app)
    orig = getattr(app, "_ensure_perfect_unison", None)
    if not callable(orig) or getattr(orig, "_r99_dist", False):
        return

    def run(*a, **k):
        r = orig(*a, **k)
        try:
            st = settings(app)
            if st["enabled"] and st["auto"] and app._get_active_engine_set():
                distribute(app)
        except Exception:
            pass
        return r
    run._r99_dist = True
    app._ensure_perfect_unison = run


def panel(app, refresh=None):
    """The 'Canonical distribution' controls (embedded in the Mod Matrix window)."""
    from PyQt6.QtWidgets import (QGroupBox, QGridLayout, QCheckBox, QComboBox, QDoubleSpinBox, QPushButton, QLabel, QListWidget,
                                 QListWidgetItem)
    from PyQt6.QtCore import Qt
    import mod_matrix as mm
    st = settings(app)
    box = QGroupBox("CANONICAL DISTRIBUTION · spread the canonicals' effect over many controls")
    g = QGridLayout(box)

    def chk(text, key, r, c):
        w = QCheckBox(text); w.setChecked(bool(st[key])); w.toggled.connect(lambda v: st.__setitem__(key, bool(v))); g.addWidget(w, r, c); return w

    def spn(text, key, lo, hi, step, r, c):
        g.addWidget(QLabel(text), r, c)
        w = QDoubleSpinBox(); w.setRange(lo, hi); w.setSingleStep(step); w.setDecimals(3); w.setValue(float(st[key]))
        w.valueChanged.connect(lambda v: st.__setitem__(key, float(v))); g.addWidget(w, r, c + 1); return w
    chk("Enabled", "enabled", 0, 0); chk("Auto after every canonical commit", "auto", 0, 1); chk("Only if it improves (J)", "only_if_improves", 0, 2)
    g.addWidget(QLabel("Kernel"), 1, 0)
    kc = QComboBox(); kc.addItems(["convolve", "gaussian", "uniform", "seed"]); kc.setCurrentText(st["kernel"])
    kc.currentTextChanged.connect(lambda v: st.__setitem__("kernel", v)); g.addWidget(kc, 1, 1)
    g.addWidget(QLabel("Method"), 1, 2)
    mc = QComboBox(); mc.addItems(list(mm.METHODS)); mc.setCurrentText(st["method"]); mc.currentTextChanged.connect(lambda v: st.__setitem__("method", v))
    g.addWidget(mc, 1, 3)
    spn("Spread width", "width", 0.01, 1.0, 0.02, 2, 0); spn("Budget (total)", "budget", 0, 4, 0.05, 2, 2)
    spn("Cap per control", "cap", 0.01, 1.0, 0.01, 3, 0); spn("Rate (beats)", "rate", 0.25, 128, 0.5, 3, 2)
    chk("Read seed", "read_seed", 4, 0); chk("Read canonical level", "read_level", 4, 1); chk("Read current values", "read_values", 4, 2)
    chk("Skip targets you modulate yourself", "skip_user", 4, 3)
    lst = QListWidget(); lst.setMaximumHeight(110)
    for name in sorted(_groups(app)):
        it = QListWidgetItem(name); it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        it.setCheckState(Qt.CheckState.Checked if st["groups"].get(name, True) else Qt.CheckState.Unchecked); lst.addItem(it)
    lst.itemChanged.connect(lambda it: st["groups"].__setitem__(it.text(), it.checkState() == Qt.CheckState.Checked))
    g.addWidget(QLabel("Scope (what they affect)"), 5, 0); g.addWidget(lst, 5, 1, 1, 3)
    out = QLabel(""); out.setWordWrap(True); g.addWidget(out, 7, 0, 1, 4)
    bp = QPushButton("Preview"); bd = QPushButton("Distribute now"); bf = QPushButton("Distribute (ignore J)")

    def prev():
        p = plan(app)
        top = sorted(p, key=lambda x: -x[1])[:6]
        out.setText("%d targets · J %.3f (current %.3f) · largest share %.1f %% · %s" % (
            len(p), objective(app, p), objective(app, current(app)),
            100 * (max(a for _, a in p) / (sum(a for _, a in p) or 1)) if p else 0,
            ", ".join("%s %.3f" % (t.split("/")[-1], a) for t, a in top)))

    def do(force):
        ok, jn, jo, n = distribute(app, force=force)
        out.setText(("applied" if ok else "kept the current distribution (not better)") + " · %d targets · J %.3f → %.3f" % (n, jo, jn))
        if refresh: refresh()
    bp.clicked.connect(prev); bd.clicked.connect(lambda: do(False)); bf.clicked.connect(lambda: do(True))
    for i, b in enumerate((bp, bd, bf)): g.addWidget(b, 6, i)
    return box
