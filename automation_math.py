"""Math-first automation transforms and source-aware canonical indexing.

Values are dimensionless/linear data. This module intentionally has no
music-theory vocabulary or assumptions: users choose the mathematical mapping.
"""
from __future__ import annotations
import math

TRANSFORMS = ("linear", "quadratic", "cubic", "exponential", "polynomial", "sqrt", "log", "power", "x^x", "smoothstep", "sine", "inverse", "xth-root",
              "inverse-root", "reciprocal", "sigmoid", "absolute", "modulo", "fold")

def _clamp01(value):
    try: return min(1.0, max(0.0, float(value)))
    except (TypeError, ValueError, OverflowError): return 0.0

def transform(value, mode="linear", *, exponent=2.0, coefficients=None):
    """Map normalized x to normalized y; stable at endpoints and finite inputs."""
    x = _clamp01(value); mode = str(mode or "linear").lower()
    if mode == "linear": y = x
    elif mode == "quadratic": y = x*x
    elif mode == "cubic": y = x*x*x
    elif mode in ("sqrt", "square-root"): y = math.sqrt(x)
    elif mode == "exponential": y = (math.exp(5.0*x)-1.0)/(math.exp(5.0)-1.0)
    elif mode == "log": y = math.log1p(9.0*x)/math.log(10.0)
    elif mode == "power":
        p = max(0.05, min(32.0, float(exponent)))
        y = x**p
    elif mode in ("xth-root", "nth-root", "root"):
        degree = max(0.05, min(32.0, float(exponent)))
        y = x**(1.0 / degree)
    elif mode == "x^x":
        # Define the left endpoint as 0 to keep the control lane anchored at 0;
        # the interior follows the actual x^x function.
        y = 0.0 if x <= 0.0 else x**x
    elif mode == "smoothstep":
        y = x*x*(3.0-2.0*x)
    elif mode == "sine":
        y = 0.5-0.5*math.cos(math.pi*x)
    elif mode == "inverse":
        y = 1.0-x
    elif mode == "inverse-root":
        degree = max(0.05, min(32.0, float(exponent)))
        y = 1.0 - (1.0 - x) ** (1.0 / degree)
    elif mode == "reciprocal":
        k = max(0.05, min(32.0, float(exponent)))
        y = (1.0 - 1.0 / (1.0 + k * x)) / (1.0 - 1.0 / (1.0 + k))
    elif mode == "sigmoid":
        k = max(0.05, min(32.0, float(exponent))) * 2.0
        lo, hi = 1.0 / (1.0 + math.exp(k * 0.5)), 1.0 / (1.0 + math.exp(-k * 0.5))
        y = (1.0 / (1.0 + math.exp(-k * (x - 0.5))) - lo) / (hi - lo)
    elif mode == "absolute":
        y = abs(2.0 * x - 1.0)
    elif mode == "modulo":
        n = max(1.0, min(32.0, float(exponent)))
        y = (x * n) % 1.0 if x < 1.0 else 1.0
    elif mode == "fold":
        n = max(1.0, min(32.0, float(exponent)))
        v = (x * n) % 2.0
        y = v if v <= 1.0 else 2.0 - v
    elif mode == "polynomial":
        coeff = list(coefficients or (0.0, 1.0))
        y = sum(float(c)*(x**i) for i,c in enumerate(coeff))
    else: y = x
    return _clamp01(y) if math.isfinite(float(y)) else 0.0

def ideal_representation(values):
    """Choose a compact mathematical description for normalized source data.

    Returns a ranked description rather than rewriting source values. It is
    designed to run beside seed/canonical/user composition and is safe to
    refresh whenever those source vectors change.
    """
    xs = [_clamp01(v) for v in (values or [])]
    if not xs: return {"mode":"linear", "score":0.0, "count":0}
    n=len(xs); candidates=[]
    for mode in TRANSFORMS:
        # Compare the data's first differences with each candidate's shape.
        predicted=[transform(i/max(1,n-1), mode) for i in range(n)]
        mean=sum(xs)/n
        # Best affine fit y ~= a*p+b, then normalized squared error.
        pm=sum(predicted)/n
        den=sum((p-pm)**2 for p in predicted)
        a=(sum((p-pm)*(v-mean) for p,v in zip(predicted,xs))/den) if den>1e-12 else 0.0
        b=mean-a*pm
        err=sum((v-(a*p+b))**2 for p,v in zip(predicted,xs))/n
        candidates.append((err,mode))
    err,mode=min(candidates)
    return {"mode":mode, "score":float(max(0.0,1.0-err)), "error":float(err), "count":n}

def index_source_layers(seed=None, canonical=None, user=None):
    """Describe the combined indexing shape without changing any source layer."""
    layers={"seed":list(seed or []), "canonical":list(canonical or []), "user":list(user or [])}
    combined=[]
    for layer in layers.values(): combined.extend(layer)
    return {"layers":{k:ideal_representation(v) for k,v in layers.items()},
            "combined":ideal_representation(combined), "sample_count":len(combined)}


def transform_ex(value, mode="linear", *, exponent=2.0, coefficients=None, depth=1, resolution=0):
    """transform() applied `depth` times (iteration depth), then quantised to `resolution` levels (0 = continuous)."""
    y = _clamp01(value)
    for _ in range(max(1, min(64, int(depth or 1)))):
        y = transform(y, mode, exponent=exponent, coefficients=coefficients)
    r = int(resolution or 0)
    if r >= 2:
        y = round(y * (r - 1)) / (r - 1)
    return y


def preview(values, mode="linear", **kw):
    """Mapped copy of `values` (the source list is never modified)."""
    return [transform_ex(v, mode, **kw) for v in list(values or [])]


def recommend(values, max_error=1e-4):
    """Most efficient representation that preserves the data: the cheapest transform (fewest parameters) whose
    affine fit is within max_error; otherwise the explicit list (lossless). Returns a description dict."""
    xs = [_clamp01(v) for v in (values or [])]
    if not xs:
        return {"representation": "empty", "parameters": 0, "lossless": True}
    if max(xs) - min(xs) < 1e-12:
        return {"representation": "constant", "value": xs[0], "parameters": 1, "lossless": True}
    cost = {"linear": 2, "inverse": 2, "quadratic": 2, "cubic": 2, "sqrt": 2, "log": 2, "exponential": 2,
            "smoothstep": 2, "sine": 2, "absolute": 2, "x^x": 2}
    n = len(xs); best = None
    for mode in TRANSFORMS:
        if mode not in cost:
            continue
        pr = [transform(i / max(1, n - 1), mode) for i in range(n)]
        pm = sum(pr) / n; mean = sum(xs) / n
        den = sum((p - pm) ** 2 for p in pr)
        a = (sum((p - pm) * (v - mean) for p, v in zip(pr, xs)) / den) if den > 1e-12 else 0.0
        b = mean - a * pm
        err = max(abs(v - (a * p + b)) for p, v in zip(pr, xs))
        cand = (cost[mode], err, mode, a, b)
        if err <= max_error and (best is None or cand < best):
            best = cand
    if best is not None:
        return {"representation": best[2], "scale": best[3], "offset": best[4], "max_error": best[1],
                "parameters": best[0], "lossless": best[1] <= 1e-9, "original_count": n}
    # periodic? smallest period that repeats exactly
    for per in range(1, n // 2 + 1):
        if all(abs(xs[i] - xs[i % per]) <= max_error for i in range(n)):
            return {"representation": "periodic", "period": per, "cycle": xs[:per], "parameters": per,
                    "lossless": True, "original_count": n}
    return {"representation": "list", "parameters": n, "lossless": True, "original_count": n}


def analyse_layers(seed=None, canonical=None, user=None):
    """Per-layer + combined analysis with recommendations (advisory, read-only)."""
    out = index_source_layers(seed, canonical, user)
    out["recommend"] = {k: recommend(v) for k, v in (("seed", seed), ("canonical", canonical), ("user", user))}
    comb = list(seed or []) + list(canonical or []) + list(user or [])
    out["recommend"]["combined"] = recommend(comb)
    return out
