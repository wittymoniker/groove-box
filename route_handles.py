"""route_handles.py — GROOVEBOX_R123_ROUTE_HANDLES_20261119

One registry of every variable ("handle") and every route the project owns, so Autopilot, Randomize All,
Randomize Patch and Randomize Sequence all see the same, current set — including routes added after they were
written (sidechain targets, Patch Motion routes, Mod Matrix rows, patch cables, Markov Resampler spec,
automation lanes) and the canonical-owned entries.

Groups (key → what it covers)
  automation   every numeric leaf automation_bus discovers (FX, synth engine, geometrics, mixer, tuning,
               global panel states, sidechain_state, patch_motion_state, Multidim macros …)
  widgets      the global-panel controls the Mod Matrix can target (widget:…)
  cables       app.patch_connections (instrument → instrument patch cables, weight / curve / polarity)
  matrix       app.r99_mod_matrix rows (source × method → target, amount, rate, canonical blend)
  motion       app.patch_motion_state["routes"] (Patch Motion: source → destination, depth %, rate %)
  sidechain    app.sidechain_state (global amount / attack / release + per-instrument offsets)
  markov       app.markov_resampler_spec (Markov Resampler numeric parameters)
  lanes        app.r32_automation (automation lanes: amount, rate)

Every group can be locked (Autopilot ▸ HANDLES): a locked group is never written by Autopilot or by the
route-aware randomizers. Locks persist in QSettings("MathematiciansGroovebox", "UI") → "autopilot_locked".

Determinism: seed_handles(app, seed) derives every value from SHA-256(seed | group | key), so the same seed gives
the same handles on every machine. randomize_routes(app, rng) takes the caller's RNG (Randomize All's seeded one).
Topology is preserved (existing routes keep source and target) unless rewire=True; canonical-owned entries keep
their canonical flag and only move amount.
"""
from __future__ import annotations

import hashlib
import math
import random

GROUPS = ("automation", "widgets", "cables", "matrix", "motion", "sidechain", "markov", "lanes")
GROUP_LABELS = {
    "automation": "Automation targets (FX · synth · geometrics · mixer · tuning · panels)",
    "widgets": "Global-panel controls",
    "cables": "Patch cables",
    "matrix": "Mod Matrix rows",
    "motion": "Patch Motion routes",
    "sidechain": "Sidechain routing",
    "markov": "Markov Resampler",
    "lanes": "Automation lanes",
}
# Roots that Autopilot must never write blindly: tuning anchors and per-instrument synth params are owned by
# Configure Entire Project / Edit Synth (harmonic_freq is the tuning anchor).
_NEVER = ("global_tuning", "instrument_param_state")
_NEVER_WIDGETS = ("spin_base_frequency",)


# --------------------------------------------------------------------------- locks
def locked_groups(app):
    v = getattr(app, "_autopilot_locked_groups", None)
    if v is None:
        try:
            from PyQt6.QtCore import QSettings
            raw = str(QSettings("MathematiciansGroovebox", "UI").value("autopilot_locked", "") or "")
            v = {g for g in raw.split(",") if g in GROUPS}
        except Exception:
            v = set()
        app._autopilot_locked_groups = v
    return set(v)


def set_locked(app, group, locked):
    s = locked_groups(app)
    (s.add if locked else s.discard)(group)
    app._autopilot_locked_groups = s
    try:
        from PyQt6.QtCore import QSettings
        QSettings("MathematiciansGroovebox", "UI").setValue("autopilot_locked", ",".join(sorted(s)))
    except Exception:
        pass


# --------------------------------------------------------------------------- inventory
def _automation_targets(app):
    try:
        import automation_bus as ab
        return [t for t in ab.targets(app) if t.split("/")[0] not in _NEVER]
    except Exception:
        return []


def _widget_targets(app):
    try:
        import mod_matrix as mm
        # global tuning stays the user's choice, exactly like the automation roots in _NEVER
        return [n for n in mm.GLOBAL_WIDGETS if n not in _NEVER_WIDGETS and hasattr(getattr(app, n, None), "setValue")]
    except Exception:
        return []


def _list(app, attr):
    v = getattr(app, attr, None)
    return v if isinstance(v, list) else []


def _motion_routes(app):
    st = getattr(app, "patch_motion_state", None)
    return st.get("routes") if isinstance(st, dict) and isinstance(st.get("routes"), list) else []


def inventory(app):
    """{group: [handle description, …]} — what each group currently covers."""
    sc = getattr(app, "sidechain_state", None) or {}
    spec = getattr(app, "markov_resampler_spec", None) or {}
    return {
        "automation": _automation_targets(app),
        "widgets": ["widget:" + n for n in _widget_targets(app)],
        "cables": ["%s → %s" % (c.get("source"), c.get("target")) for c in _list(app, "patch_connections") if isinstance(c, dict)],
        "matrix": ["%s ×%s → %s" % (r.get("source"), r.get("method"), r.get("target")) for r in _list(app, "r99_mod_matrix") if isinstance(r, dict)],
        "motion": ["%s → %s" % (r.get("source"), r.get("destination")) for r in _motion_routes(app) if isinstance(r, dict)],
        "sidechain": (["global"] if isinstance(sc.get("global"), dict) else []) + sorted((sc.get("targets") or {}).keys()),
        "markov": [k for k, v in spec.items() if isinstance(v, (int, float)) and not isinstance(v, bool)],
        "lanes": [str(l.get("path")) for l in _list(app, "r32_automation") if isinstance(l, dict)],
    }


def counts(app):
    return {g: len(v) for g, v in inventory(app).items()}


def canonical_count(app):
    n = sum(1 for r in _list(app, "r99_mod_matrix") if isinstance(r, dict) and (r.get("canonical_entry") or float(r.get("canonical", 0) or 0) > 0))
    n += sum(1 for c in _list(app, "patch_connections") if isinstance(c, dict) and str(c.get("origin", "")).startswith(("generated", "canonical", "additive")))
    n += sum(1 for l in _list(app, "r32_automation") if isinstance(l, dict) and l.get("owner") == "canonical")
    return n


# --------------------------------------------------------------------------- writers
class _HashRng:
    """random.Random-compatible subset whose values depend only on (seed, label)."""

    def __init__(self, seed):
        self.seed = str(seed)

    def _u(self, label):
        d = hashlib.sha256(("%s|%s" % (self.seed, label)).encode("utf-8", "replace")).digest()
        return int.from_bytes(d[:8], "little") / 2.0 ** 64

    def uniform(self, a, b, label=""):
        return a + (b - a) * self._u(label)

    def choice(self, seq, label=""):
        seq = list(seq)
        return seq[min(len(seq) - 1, int(self._u(label) * len(seq)))] if seq else None


def _uni(rng, a, b, label):
    try:
        return rng.uniform(a, b, label)
    except TypeError:
        return rng.uniform(a, b)


def _pick(rng, seq, label):
    try:
        return rng.choice(seq, label)
    except TypeError:
        return rng.choice(seq)


def _write_automation(app, rng, amount):
    import automation_bus as ab
    n = 0
    for path in _automation_targets(app):
        d, k = ab._resolve(app, path)
        if d is None or k not in d or isinstance(d[k], bool):
            continue
        try:
            base = float(d[k])
        except (TypeError, ValueError):
            continue
        lo, hi = ab._span(k, base)
        if not (math.isfinite(lo) and math.isfinite(hi)) or hi <= lo:
            continue
        # move toward a random point of the span by `amount` (0..1), so a small amount is a gentle nudge
        v = base + (_uni(rng, lo, hi, "auto|" + path) - base) * amount
        v = min(hi, max(lo, v))
        d[k] = int(round(v)) if isinstance(d[k], int) else float(v)
        n += 1
    return n


def _write_widgets(app, rng, amount):
    n = 0
    for name in _widget_targets(app):
        w = getattr(app, name)
        try:
            lo, hi, cur = float(w.minimum()), float(w.maximum()), float(w.value())
        except Exception:
            continue
        v = cur + (_uni(rng, lo, hi, "widget|" + name) - cur) * amount
        try:
            w.setValue(type(w.value())(round(v) if isinstance(w.value(), int) else v))
            n += 1
        except Exception:
            pass
    return n


def _instrument_names(app):
    return list(getattr(app, "instrument_names_48", []) or [])


def _write_cables(app, rng, amount, rewire):
    cables = _list(app, "patch_connections")
    names = _instrument_names(app)
    n = 0
    for i, c in enumerate(cables):
        if not isinstance(c, dict):
            continue
        w = float(c.get("weight", 1.0) or 0.0)
        c["weight"] = round(min(1.0, max(0.0, w + (_uni(rng, 0.2, 1.0, "cable|%d" % i) - w) * amount)), 4)
        if rewire and names and not c.get("user_defined"):
            c["source"] = _pick(rng, names, "cable-src|%d" % i)
        n += 1
    return n


def _write_matrix(app, rng, amount):
    n = 0
    for i, r in enumerate(_list(app, "r99_mod_matrix")):
        if not isinstance(r, dict):
            continue
        a = float(r.get("amount", 0.0) or 0.0)
        r["amount"] = round(min(1.0, max(-1.0, a + (_uni(rng, -0.6, 0.6, "mm-amt|%d" % i) - a) * amount)), 4)
        rate = float(r.get("rate", 8.0) or 8.0)
        r["rate"] = round(min(64.0, max(0.25, rate * (2.0 ** (_uni(rng, -1.0, 1.0, "mm-rate|%d" % i) * amount)))), 4)
        r.pop("base", None)
        n += 1
    return n


def _write_motion(app, rng, amount):
    n = 0
    for i, r in enumerate(_motion_routes(app)):
        if not isinstance(r, dict):
            continue
        for key, lo, hi in (("depth_pct", -200.0, 200.0), ("rate_pct", 0.0, 400.0)):
            v = float(r.get(key, 0.0) or 0.0)
            r[key] = round(min(hi, max(lo, v + (_uni(rng, lo * 0.5, hi * 0.5, "pm-%s|%d" % (key, i)) - v) * amount)), 3)
        n += 1
    return n


def _write_sidechain(app, rng, amount):
    st = getattr(app, "sidechain_state", None)
    if not isinstance(st, dict):
        st = app.sidechain_state = {"global": {"enabled": True, "amount": 0.0, "source": "master",
                                               "attack_ms": 5.0, "release_ms": 120.0}, "targets": {}}
    g = st.setdefault("global", {})
    st.setdefault("targets", {})
    n = 0
    for key, lo, hi in (("amount", -1.0, 1.0), ("attack_ms", 0.5, 80.0), ("release_ms", 20.0, 900.0)):
        v = float(g.get(key, (lo + hi) / 2) or 0.0)
        g[key] = round(min(hi, max(lo, v + (_uni(rng, lo, hi, "sc|" + key) - v) * amount)), 4)
        n += 1
    for name, t in sorted((st.get("targets") or {}).items()):
        if isinstance(t, dict) and not t.get("inherit_global", True):
            v = float(t.get("amount", 0.0) or 0.0)
            t["amount"] = round(min(1.0, max(-1.0, v + (_uni(rng, -1.0, 1.0, "sc-t|" + name) - v) * amount)), 4)
            n += 1
    try:
        import panel_synth_deck as psd
        psd._write_state(app, st) if hasattr(psd, "_write_state") else None
    except Exception:
        pass
    return n


def _write_markov(app, rng, amount):
    spec = getattr(app, "markov_resampler_spec", None)
    if not isinstance(spec, dict):
        return 0
    try:
        import markov_resampler as mr
    except Exception:
        return 0
    ranges = {"locality": (0.0, 8.0), "self_weight": (0.0, 4.0), "euclid_bonus": (0.0, 4.0),
              "fractal_bonus": (0.0, 4.0), "coupling": (0.0, 1.0)}
    n = 0
    for key, (lo, hi) in ranges.items():
        v = float(spec.get(key, (lo + hi) / 2) or 0.0)
        spec[key] = v + (_uni(rng, lo, hi, "mk|" + key) - v) * amount
        n += 1
    app.markov_resampler_spec = mr.normalize_spec(spec)
    return n


def _write_lanes(app, rng, amount):
    n = 0
    for i, l in enumerate(_list(app, "r32_automation")):
        if not isinstance(l, dict):
            continue
        a = float(l.get("amount", 0.3) or 0.0)
        l["amount"] = round(min(1.0, max(0.0, a + (_uni(rng, 0.05, 0.8, "lane|%d" % i) - a) * amount)), 4)
        n += 1
    return n


def _apply(app, rng, amount, rewire, groups, locked):
    writers = {"automation": lambda: _write_automation(app, rng, amount),
               "widgets": lambda: _write_widgets(app, rng, amount),
               "cables": lambda: _write_cables(app, rng, amount, rewire),
               "matrix": lambda: _write_matrix(app, rng, amount),
               "motion": lambda: _write_motion(app, rng, amount),
               "sidechain": lambda: _write_sidechain(app, rng, amount),
               "markov": lambda: _write_markov(app, rng, amount),
               "lanes": lambda: _write_lanes(app, rng, amount)}
    out = {}
    for g in groups:
        if g in locked or g not in writers:
            out[g] = "locked" if g in locked else 0
            continue
        try:
            out[g] = writers[g]()
        except Exception as exc:
            out[g] = "error: %s" % exc
    broadcast(app)
    return out


def randomize_routes(app, rng=None, *, amount=1.0, rewire=False, groups=GROUPS, respect_locks=True):
    """Randomize every route group with the caller's RNG (Randomize All). Returns {group: count}."""
    rng = rng or random.Random()
    return _apply(app, rng, max(0.0, min(1.0, float(amount))), rewire, groups,
                  locked_groups(app) if respect_locks else set())


def seed_handles(app, seed, *, amount=0.6, groups=GROUPS):
    """Autopilot: write every unlocked handle deterministically from `seed` (same seed → same values)."""
    return _apply(app, _HashRng("autopilot-handles|%s" % seed), max(0.0, min(1.0, float(amount))), False,
                  groups, locked_groups(app))


# --------------------------------------------------------------------------- keep codependent views in sync
def broadcast(app):
    """Tell every open view that shared routing state changed (patch bay list, sidechain panel, Mod Matrix,
    Markov Resampler, Patch Motion). Each refresher is optional and guarded."""
    app._shared_mixdown_cache = {}
    for fn in (
        lambda: __import__("patch_bay_sync").refresh_open_views(app),
        lambda: __import__("panel_synth_deck").sync_sidechain_panel(app),
        lambda: getattr(app, "_markov_resampler_window", None) and app._markov_resampler_window._schedule(),
        lambda: getattr(app, "_r99_mod_matrix_refresh", None) and app._r99_mod_matrix_refresh(),
        lambda: getattr(app, "_invalidate_shared_mixdown", None) and app._invalidate_shared_mixdown(),
    ):
        try:
            fn()
        except Exception:
            pass


# --------------------------------------------------------------------------- route-aware sequences
def incoming_routes(app, name):
    """[(source instrument, weight, kind)] of every route that lands on `name` (cables, Patch Motion, sidechain)."""
    out = []
    for c in _list(app, "patch_connections"):
        if isinstance(c, dict) and c.get("target") == name and c.get("source") and c.get("source") != name:
            pol = str(c.get("polarity", ""))
            out.append((c["source"], float(c.get("weight", 1.0) or 0.0), "invert" if pol.startswith("Inverted") else "follow"))
    for r in _motion_routes(app):
        if isinstance(r, dict) and r.get("enabled", True):
            src = str(r.get("source", "")).replace(" Out", "")
            dst = str(r.get("destination", "")).replace(" In", "")
            if dst == name and src and src != name and src in _instrument_names(app):
                out.append((src, min(1.0, abs(float(r.get("depth_pct", 0.0) or 0.0)) / 100.0), "follow"))
    sc = getattr(app, "sidechain_state", None) or {}
    g = sc.get("global") or {}
    if g.get("enabled", True) and g.get("source") == "selected instrument":
        pass   # the selected instrument is the key itself; nothing to correlate against
    t = (sc.get("targets") or {}).get(name) or {}
    eff = float(t.get("amount", 0.0) if t and not t.get("inherit_global", True) else g.get("amount", 0.0) or 0.0)
    if eff > 0.05 and g.get("source") == "kick":
        for n in _instrument_names(app):
            if "kick" in n.lower() and n != name:
                out.append((n, min(1.0, eff), "avoid"))   # ducked by the kick → leave room for it
                break
    return out


def route_steps(app, name, steps, mem_of, rng_u):
    """Blend a fresh step list with the patterns of every instrument routed into `name`.
    follow → copy the source's hit with probability = weight; invert → the complement; avoid → clear where the
    source plays (sidechain ducking). `mem_of(name)` returns that instrument's sequence memory; `rng_u(i, j)`
    gives a deterministic 0..1 number. Returns (steps, [route descriptions used])."""
    used = []
    out = list(steps)
    for j, (src, w, kind) in enumerate(incoming_routes(app, name)[:8]):
        try:
            sm = mem_of(src) or {}
        except Exception:
            continue
        ss = [bool(x) for x in (sm.get("steps") or [])]
        if not any(ss):
            continue
        for i in range(len(out)):
            s = ss[i % len(ss)]
            if kind == "avoid":
                if s and rng_u(i, j) < w:
                    out[i] = False
            elif rng_u(i, j) < w:
                out[i] = (not s) if kind == "invert" else s
        used.append("%s %s %.2f" % (kind, src, w))
    return out, used


# --------------------------------------------------------------------------- parameter registry
def publish_registry(app):
    """Mirror the inventory into the persisted ParameterRegistry (groovebox_intelligence), so the project's
    self-description, the intelligence report and co-edit peers see every handle and route."""
    try:
        import groovebox_intelligence as gi
        import automation_bus as ab
    except Exception:
        return None
    reg = gi.registry_for_app(app)
    for path in _automation_targets(app):
        d, k = ab._resolve(app, path)
        if d is None:
            continue
        try:
            lo, hi = ab._span(k, float(d[k]))
        except Exception:
            lo = hi = None
        if lo is not None and hi is not None and lo > hi:
            lo, hi = hi, lo
        reg.register(path, owner=path.split("/")[0], minimum=lo, maximum=hi, destinations=("audio",),
                     metadata={"group": "automation"})
    for i, c in enumerate(_list(app, "patch_connections")):
        if isinstance(c, dict) and c.get("source") and c.get("target"):
            key = "patch:%s" % c["target"]
            if key not in reg.parameters:
                reg.register(key, owner="patch_connections", minimum=0.0, maximum=1.0, destinations=("audio",),
                             metadata={"group": "cables"})
            reg.add_route(key, "canonical" if not c.get("user_defined", True) else "manual", key,
                          metadata={"from": c["source"], "weight": c.get("weight")})
    for i, r in enumerate(_list(app, "r99_mod_matrix")):
        t = str((r or {}).get("target") or "")
        if t:
            if t not in reg.parameters:
                reg.register(t, owner="r99_mod_matrix", destinations=("audio",), metadata={"group": "matrix"})
            reg.add_route(t, "canonical" if r.get("canonical_entry") else "master_mod", t,
                          enabled=bool(r.get("enabled", True)), mode="add",
                          metadata={"row": i + 1, "source": r.get("source"), "method": r.get("method")})
    return gi.save_registry(app, reg)
