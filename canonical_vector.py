"""canonical_vector.py — CANON_VECTOR_R7: one vectorized read / understand / write path for the canonicals.

The instrument toolkit is treated as one normalized vector x ∈ [0,1]^n (every spin, dial, slider and store key the
canonicals own; log scale for frequencies).  The seed gives a target t ∈ [0,1]^n.  "Understanding" is a small
feature map J (k × n, k ≪ n): energy, brightness, complexity, space, motion, geometry — what you hear and see,
not individual knobs.

Every canonical write is one minimum-norm step

    d  = t − x
    P  = D Jᵀ (J D Jᵀ + λI)⁻¹ J          (weighted projector onto the feature row-space, D = diag(1/cost))
    Δ  = P d + β (I − P) d                 features are matched first; the exact values drift in slowly
    Δ ← Δ · min(1, cap / ‖Δ‖∞)             trust region: no control moves more than ``cap`` per step
    Δ ← floor step                         always writes: if Δ is tiny but x ≠ t, it still moves ``eps``

Minimum L2 norm spreads one feature change over the most variables, with the smallest change to each.  So the
canonicals always write, they touch many controls, and each control moves only a little.  The step is pure numpy
and deterministic (no RNG; the seed only enters through t).

Ownership: a value differing from what the canonical last wrote (or any signalled edit) is a user edit.  Its target
becomes your value (protected, frozen), halfway (global50, 4× cost) or the seed (direct), so the feature step never
pushes other controls to cancel what you set.
Integer controls keep a continuous internal position, so many small steps never stall on rounding.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, Sequence

import numpy as np

FEATURES = ("energy", "brightness", "complexity", "space", "motion", "geometry")
CAP = 0.08          # largest per-variable change in one refresh step (normalized units)
CAP_MODE = 0.25     # explicit mode change / seed change
EPS = 0.004         # floor step so a write always moves something
BETA = 0.35         # share of the exact (null-space) remainder taken per step
LAMBDA = 1e-6
TOUCH_TOL = 0.006   # normalized difference that counts as a user edit
USER_COST = {"protected": math.inf, "global50": 4.0, "direct": 1.0}
USER_SHARE = {"protected": 0.0, "global50": 0.5, "direct": 1.0}   # how far a user-owned value is pulled to the seed


@dataclass
class Var:
    name: str
    get: Callable[[], float]
    set: Callable[[float], None]
    lo: float
    hi: float
    tags: dict = field(default_factory=dict)      # feature -> weight
    integer: bool = False
    log: bool = False
    track: bool = True          # False: another system owns user detection (e.g. geometry lanes)
    quantum: float = 0.0        # smallest representable step of the control (1 for integers, 10^-decimals)

    def norm(self, v):
        try:
            v = float(v)
        except (TypeError, ValueError):
            return 0.0
        if not math.isfinite(v):                  # ZERO_GUARD_R7: NaN / inf never enter the vector
            return 0.0 if v != v or v < 0 else 1.0
        if self.log:
            lo, hi = math.log(max(self.lo, 1e-9)), math.log(max(self.hi, 1e-9))
            v = math.log(max(v, 1e-9))
        else:
            lo, hi = self.lo, self.hi
        return 0.0 if hi <= lo else min(1.0, max(0.0, (v - lo) / (hi - lo)))

    def denorm(self, u):
        u = float(u)
        u = 0.0 if u != u else min(1.0, max(0.0, u))
        if self.log:
            lo, hi = math.log(max(self.lo, 1e-9)), math.log(max(self.hi, 1e-9))
            v = math.exp(lo + u * (hi - lo))
        else:
            v = self.lo + u * (self.hi - self.lo)
        if self.integer:
            return int(round(v))
        if self.quantum > 0:
            v = round(round(v / self.quantum) * self.quantum, 9)
        return round(v, 6)

    def snap(self, u):
        """Normalized value of what the control can actually show."""
        return self.norm(self.denorm(u))


# ------------------------------------------------------------------ adaptors
def _mark_user(st, name):
    st.setdefault("user", set()).add(name)
    st.setdefault("anchor", {}).pop(name, None)       # re-anchor at the new value on the next read

def widget_var(app, attr, tags, *, log=False, lo=None, hi=None, track=True):
    w = getattr(app, attr, None)
    if w is None or not hasattr(w, "value") or not hasattr(w, "setValue"):
        return None
    try:
        wlo = float(w.minimum()) if lo is None else float(lo)
        whi = float(w.maximum()) if hi is None else float(hi)
    except Exception:
        return None
    integer = isinstance(w.value(), int)
    quantum = 1.0 if integer else (10.0 ** -int(w.decimals()) if hasattr(w, "decimals") else 0.0)
    st = _state(app)
    if track and attr not in st.setdefault("hooked", set()):
        # Canonical writes block signals, so any valueChanged is a person (or a project load): that control is theirs.
        try:
            w.valueChanged.connect(lambda *_a, st=st, attr=attr: _mark_user(st, attr))
            st["hooked"].add(attr)
        except Exception:
            pass

    def _set(v, w=w):
        try:
            w.blockSignals(True)
            w.setValue(int(v) if integer else float(v))
        finally:
            w.blockSignals(False)
    return Var(attr, lambda w=w: float(w.value()), _set, max(wlo, float(w.minimum())), min(whi, float(w.maximum())),
               dict(tags), integer, log, track, quantum)


def dict_var(store, key, lo, hi, tags, name=None, integer=False):
    if not isinstance(store, dict):
        return None
    return Var(name or key, lambda: float(store.get(key, lo) or 0.0), lambda v: store.__setitem__(key, v),
               float(lo), float(hi), dict(tags), integer)


# ------------------------------------------------------------------ math
def feature_matrix(vars_: Sequence[Var]):
    J = np.zeros((len(FEATURES), len(vars_)))
    for j, v in enumerate(vars_):
        for f, w in v.tags.items():
            if f in FEATURES:
                J[FEATURES.index(f), j] = float(w)
    n = np.linalg.norm(J, axis=1, keepdims=True)
    keep = n[:, 0] > 0
    return J[keep] / n[keep], [f for f, k in zip(FEATURES, keep) if k]


def min_norm_step(x, t, J, cost=None, *, cap=CAP, eps=EPS, beta=BETA, lam=LAMBDA):
    """Return Δ (same shape as x).  cost[i] = inf freezes variable i."""
    x = np.nan_to_num(np.asarray(x, float), nan=0.0, posinf=1.0, neginf=0.0)
    t = np.nan_to_num(np.asarray(t, float), nan=0.0, posinf=1.0, neginf=0.0)
    n = x.size
    cost = np.ones(n) if cost is None else np.asarray(cost, float)
    free = np.isfinite(cost) & (cost > 0)          # cost 0 / negative / NaN / inf: never divided by, never moved
    delta = np.zeros(n)
    if not free.any():
        return delta
    d = (t - x)[free]
    Jf = J[:, free] if J.size else np.zeros((0, int(free.sum())))
    Dinv = 1.0 / cost[free]
    if Jf.shape[0]:
        A = (Jf * Dinv) @ Jf.T + lam * np.eye(Jf.shape[0])
        try:
            Pd = Dinv * (Jf.T @ np.linalg.solve(A, Jf @ d))
        except np.linalg.LinAlgError:              # singular / ill-posed features: least-squares instead
            Pd = Dinv * (Jf.T @ np.linalg.lstsq(A, Jf @ d, rcond=None)[0])
        if not np.all(np.isfinite(Pd)):
            Pd = np.zeros_like(d)
    else:
        Pd = np.zeros_like(d)
    step = Pd + beta * (d - Pd)
    m = float(np.max(np.abs(step))) if step.size else 0.0
    if m > cap:
        step *= cap / m
    dm = float(np.max(np.abs(d))) if d.size else 0.0
    if dm > 1e-9 and float(np.max(np.abs(step))) < min(eps, dm):
        step = d * (min(eps, dm) / dm)             # floor: always move toward the canonical value
    xf = np.clip(x[free] + step, 0.0, 1.0)
    delta[free] = xf - x[free]
    return delta


def spread(delta):
    """Participation ratio in [0,1]: 1 = the change is shared evenly by every variable."""
    a = np.abs(np.asarray(delta, float))
    s2 = float((a * a).sum())
    return 0.0 if s2 <= 0 else float(a.sum() ** 2 / (a.size * s2))


# ------------------------------------------------------------------ engine
def _state(app):
    st = getattr(app, "_canon_vec_state", None)
    if not isinstance(st, dict):
        st = {"pos": {}, "written": {}, "last": {}, "user": set(), "hooked": set()}
        try:
            app._canon_vec_state = st
        except Exception:
            pass
    # A project load replaces app._canon_user_owned: adopt it exactly and restart value-diff detection
    # (the loaded values are the project's, not edits against the last canonical write).
    owned = getattr(app, "_canon_user_owned", None) if app is not None else None
    if isinstance(owned, list) and id(owned) != st.get("owned_ref"):
        st["user"] = {str(n) for n in owned}
        st["written"] = {}; st["pos"] = {}; st["anchor"] = {}
        st["owned_ref"] = id(owned)
    return st


def _publish_owned(app, st):
    if app is None:
        return
    lst = sorted(st.get("user", ()))
    cur = getattr(app, "_canon_user_owned", None)
    if cur != lst:
        try:
            app._canon_user_owned = lst
            st["owned_ref"] = id(lst)
        except Exception:
            pass


def read(vars_, app=None):
    """Normalized vector of the live values, plus the ownership mask (True = the user changed it)."""
    st = _state(app) if app is not None else {"pos": {}, "written": {}}
    x = np.zeros(len(vars_)); user = np.zeros(len(vars_), bool)
    for i, v in enumerate(vars_):
        try:
            live = v.norm(v.get())
        except Exception:
            live = 0.0
        if not v.track:
            x[i] = live
            continue
        if v.name in st.get("user", ()):
            user[i] = True
        w = st["written"].get(v.name)
        if w is not None and abs(live - v.norm(v.denorm(w))) > TOUCH_TOL:
            user[i] = True
            _mark_user(st, v.name)
            st["pos"].pop(v.name, None)
        if user[i] and v.name not in st.setdefault("anchor", {}):
            st["anchor"][v.name] = live                # the value you set: the user end of the blend
        p = st["pos"].get(v.name)
        x[i] = p if (p is not None and not user[i]) else live
    return x, user


def write(vars_, x_new, app=None, mask=None):
    st = _state(app) if app is not None else {"pos": {}, "written": {}}
    n = 0
    for i, v in enumerate(vars_):
        if mask is not None and not mask[i]:
            continue
        try:
            v.set(v.denorm(x_new[i]))
            st["pos"][v.name] = float(x_new[i]); st["written"][v.name] = float(x_new[i]); n += 1
        except Exception:
            pass
    return n


def step(app, vars_, targets, mode="protected", *, cap=CAP, owner=None):
    """Read → understand → one minimum-norm write.  Returns a small report (also kept as app._canon_vec_state['last'])."""
    vars_ = [v for v in vars_ if v is not None]
    t = np.array([v.snap(targets[v.name]) for v in vars_], float) if vars_ else np.zeros(0)
    x, user = read(vars_, app)
    if owner is not None:                       # caller-known user ownership (lane locks, protected keys)
        user |= np.array([bool(owner(v.name)) for v in vars_], bool)
    ucost = USER_COST.get(mode, math.inf)
    cost = np.where(user, ucost, 1.0)
    # A user edit is part of the intent, not an error to compensate: its target is (partly) the user's value,
    # so the features never push other controls against what you set.
    st = _state(app) if app is not None else {}
    anc = np.array([st.get("anchor", {}).get(v.name, x[i]) for i, v in enumerate(vars_)], float) if vars_ else x
    t = np.where(user, anc + USER_SHARE.get(mode, 0.0) * (t - anc), t)
    J, feats = feature_matrix(vars_)
    delta = min_norm_step(x, t, J, cost, cap=cap)
    x2 = x + delta
    for i, v in enumerate(vars_):          # quantized controls: a step that rounds away moves one quantum
        if (v.integer or v.quantum > 0) and not v.track and np.isfinite(cost[i]):
            cur, want, got = v.denorm(x[i]), v.denorm(t[i]), v.denorm(x2[i])
            if got == cur and want != cur:
                q = 1 if v.integer else v.quantum
                x2[i] = v.norm(cur + (q if want > cur else -q))
        if not v.track:
            x2[i] = v.snap(x2[i])           # untracked: what the control will show is the state
    delta = x2 - x
    n = write(vars_, x2, app, mask=np.isfinite(cost))
    rep = {"vars": len(vars_), "written": n, "user_owned": int(user.sum()), "mode": mode,
           "features": feats,
           "feature_gap_before": [round(float(g), 4) for g in (J @ (t - x))] if J.size else [],
           "feature_gap_after": [round(float(g), 4) for g in (J @ (t - x2))] if J.size else [],
           "max_change": round(float(np.max(np.abs(delta))) if delta.size else 0.0, 4),
           "l2_change": round(float(np.linalg.norm(delta)), 4),
           "spread": round(spread(delta), 3),
           "worst": (vars_[int(np.argmax(np.where(np.isfinite(cost), np.abs(t - x2), -1)))].name if vars_ else ""),
           "remaining": round(float(np.max(np.abs((t - x2)[np.isfinite(cost)]))) if np.isfinite(cost).any() else 0.0, 4)}
    if app is not None:
        st = _state(app)
        st["last"] = rep
        _publish_owned(app, st)
    return rep


def owned_by_user(app):
    return sorted(_state(app).get("user", ()))


def release(app, names=None):
    """Give controls back to the canonicals (all of them when names is None); they glide to the seed values."""
    st = _state(app)
    u = st.setdefault("user", set())
    gone = set(u) if names is None else (set(names) & u)
    u -= gone
    for n in gone:
        st["written"].pop(n, None); st["pos"].pop(n, None); st.get("anchor", {}).pop(n, None)
    _publish_owned(app, st)
    return sorted(gone)


def explain(app):
    rep = (_state(app).get("last") or {}) if app is not None else {}
    if not rep:
        return "Canonical vector: no write yet."
    gaps = ", ".join(f"{f} {g:+.3f}" for f, g in zip(rep["features"], rep["feature_gap_after"]))
    return (f"Canonical vector ({rep['mode']}): wrote {rep['written']}/{rep['vars']} controls, "
            f"{rep['user_owned']} yours; largest move {rep['max_change']:.3f}, spread {rep['spread']:.2f}; "
            f"feature gap {gaps}; remaining {rep['remaining']:.3f}")
