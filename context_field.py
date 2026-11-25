"""context_field.py — CONTEXT_FIELD_20261112: the one law behind Party Mode (UI) and the video context effects.

    z' = lambda z,   lambda = a(2 sigma - 1) + i omega,   time-tau map  z -> z e^(lambda tau)

sigma in [0, 1] is significance. Every visual is a reading of that field, and every channel tells you something
about the composition rather than being decoration:

=====================  ==================================================================================
channel                what it encodes
=====================  ==================================================================================
curvature              kappa = 2 sigma - 1 > 0: a sensitive, consequential change bends rings / meshes and
                       pushes material out (source). sigma < 1/2: concentric, material spirals in (sink).
light / dark           the mesh is the image of a grid under the flow map; each cell is lit by the change of
                       area, brightness ~ 1/|det J| (light gathers where the flow compresses, thins where it
                       spreads). Pure rotation (sigma = 1/2) preserves area: no light change.
hue                    the pitch class: key-chart degree / steps * 360 deg (same colour = same degree).
tint regions           the spectrum: one soft region per band, low = warm, high = cool, opacity = band
                       energy. They only move (the neutral orbit z' = i omega z) and morph, never flash.
textures               snippets of the recent material carried by the flow (in-and-vanish / out-and-scatter).
=====================  ==================================================================================

Pure numpy; Qt and PIL are optional and only used by the drawing helpers in the callers.
"""
from __future__ import annotations

import cmath
try:  # R132.10: project trig route — book isy/isx series when the Trigonometry Engine is ON (gb_trig)
    from gb_trig import cos as _tcos, nsin as _tnsin, sin as _tsin
except Exception:  # standalone use outside the app
    from math import cos as _tcos, sin as _tsin
    from numpy import sin as _tnsin
import math

import numpy as np

FLOW_A = 0.9          # |Re lambda| at the extremes (1/s)
FLOW_W = 0.8          # Im lambda: the spiral (rad/s)
TAU = 0.6             # the field is shown as its time-TAU map
BAND_HUES = (18.0, 48.0, 150.0, 215.0)     # low -> high: warm -> cool


def flow_lambda(sigma: float) -> complex:
    s = max(0.0, min(1.0, float(sigma)))
    return complex(FLOW_A * (2.0 * s - 1.0), FLOW_W)


def curvature(sigma: float) -> float:
    return max(0.0, 2.0 * float(sigma) - 1.0)


def calmness(sigma: float) -> float:
    return max(0.0, 1.0 - 2.0 * float(sigma))


def logistic(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-max(-40.0, min(40.0, x))))


def hue_for_degree(degree: float, steps: int) -> float:
    return (360.0 * (float(degree) % max(1, int(steps))) / max(1, int(steps))) % 360.0


def degree_of_frequency(freq: float, base_hz: float, steps: int, ratio_fn=None) -> int:
    """Nearest key-chart degree of ``freq`` folded into [base, 2 base). The default chart is the program's linear
    one (ratio = 1 + degree / steps); pass ``ratio_fn(degree)`` (e.g. the app's ``_keychart_ratio``, which the
    composition tunings replace) to invert whatever tuning is active."""
    if not (freq > 0 and base_hz > 0):
        return 0
    steps = max(1, int(steps))
    r = freq / base_hz
    while r >= 2.0:
        r *= 0.5
    while r < 1.0:
        r *= 2.0
    if ratio_fn is not None:
        try:
            best, err = 0, float("inf")
            lr = math.log2(r)
            for d in range(steps + 1):
                q = float(ratio_fn(d))
                if q > 0:
                    e = abs(math.log2(q) - lr)
                    if e < err:
                        best, err = d, e
            return best % steps
        except Exception:
            pass
    return int(round((r - 1.0) * steps)) % steps


def analyse(samples, sr: float = 48000.0, base_hz: float = 432.0, steps: int = 12, prev_spectrum=None, ratio_fn=None) -> dict:
    """Read a block of audio: band energies (4), dominant degree + hue, spectral centroid (0..1), RMS energy,
    novelty (positive spectral flux, 0..1) and the spectrum for the next call."""
    x = np.nan_to_num(np.asarray(samples if samples is not None else [], dtype=np.float64).ravel())
    out = {"bands": [0.0] * 4, "degree": 0, "hue": 0.0, "centroid": 0.5, "energy": 0.0, "novelty": 0.0, "spectrum": None}
    if x.size < 32 or not (sr and sr > 0):
        return out
    x = np.clip(np.nan_to_num(x[-4096:], nan=0.0, posinf=0.0, neginf=0.0), -1e3, 1e3)   # ZERO_GUARD_R7: NaN / inf / huge audio
    out["energy"] = min(1.0, 3.0 * float(np.sqrt(np.mean(x * x))))
    spec = np.abs(np.fft.rfft(x * np.hanning(x.size)))
    freqs = np.fft.rfftfreq(x.size, 1.0 / sr)
    tot = float(spec.sum())
    if tot <= 1e-12:
        return out
    edges = (20.0, 250.0, 1000.0, 4000.0, sr / 2.0)
    bands = [float(spec[(freqs >= lo) & (freqs < hi)].sum()) / tot for lo, hi in zip(edges[:-1], edges[1:])]
    out["bands"] = bands
    k = int(np.argmax(spec[1:])) + 1
    out["degree"] = degree_of_frequency(float(freqs[k]), base_hz, steps, ratio_fn)
    out["hue"] = hue_for_degree(out["degree"], steps)
    c = float((spec * freqs).sum() / tot)
    out["centroid"] = max(0.0, min(1.0, math.log2(max(20.0, c) / 20.0) / math.log2(max(40.0, sr / 2.0) / 20.0)))
    norm = spec / tot
    if prev_spectrum is not None and len(prev_spectrum) == len(norm):
        out["novelty"] = max(0.0, min(1.0, float(np.maximum(0.0, norm - prev_spectrum).sum()) * 2.0))
    out["spectrum"] = norm
    return out


def regions(t: float, sigma: float, w: float, h: float, bands=None, centre=None) -> list:
    """Tint regions (one per spectral band). They follow the neutral orbit z' = i omega z about the centre and
    morph; sigma only changes their orbit radius (sink: drawn in; source: spread out)."""
    bands = list(bands) if bands is not None else [0.25] * 4
    cx, cy = centre if centre is not None else (w * 0.5, h * 0.5)
    lam = flow_lambda(sigma)
    spread = math.exp(0.5 * lam.real)                          # sink < 1 < source
    m = min(w, h)
    out = []
    for i, e in enumerate(bands[:4]):
        R = m * (0.18 + 0.12 * i) * spread
        z = complex(R, 0.0) * cmath.exp(1j * (FLOW_W * 0.35 * t * (1 if i % 2 == 0 else -1) + i * 1.7))
        base = m * (0.22 + 0.10 * (3 - i) / 3.0)
        out.append({"cx": cx + z.real, "cy": cy + 0.75 * z.imag,
                    "rx": base * (1.0 + 0.32 * _tsin(0.9 * t + 2.1 * i)),
                    "ry": base * (1.0 + 0.32 * _tcos(0.7 * t + 1.3 * i)) * 0.8,
                    "angle": math.degrees(0.35 * t * (1 if i % 2 else -1) + i),
                    "hue": BAND_HUES[i], "alpha": max(0.0, min(1.0, 0.15 + 1.6 * float(e)))})
    return out


def displacement(X, Y, fields=(), pulses=(), tau: float = TAU):
    """Displacement (dx, dy) of points (X, Y) under the time-tau flow map of each field, windowed by a gaussian.

    fields: (cx, cy, lambda, R, s); pulses: (cx, cy, age 0..1, strength) -> radial ripple."""
    X = np.asarray(X, dtype=np.float64); Y = np.asarray(Y, dtype=np.float64)
    dx = np.zeros_like(X); dy = np.zeros_like(Y)
    for (cx, cy, lam, R, s) in fields:
        zx, zy = X - cx, Y - cy
        g = float(s) * np.exp(-(zx * zx + zy * zy) / max(1.0, float(R)) ** 2)
        m = cmath.exp(complex(lam) * tau) - 1.0
        dx += (m.real * zx - m.imag * zy) * g
        dy += (m.real * zy + m.imag * zx) * g
    for (cx, cy, age, s) in pulses:
        zx, zy = X - cx, Y - cy
        r = np.sqrt(zx * zx + zy * zy) + 1e-6
        amp = 14.0 * float(s) * (1.0 - float(age))
        wv = amp * _tnsin(r / 22.0 - float(age) * 12.0) * np.exp(-r / 320.0)
        dx += wv * zx / r; dy += wv * zy / r
    return dx, dy


def mesh(w: float, h: float, nx: int, ny: int, fields=(), pulses=(), tau: float = TAU):
    """(PX, PY, light): displaced grid points ((ny+1) x (nx+1)) and per-cell light in [-1, 1].
    light = clip(-log(area' / area)): compressed cells are lit (> 0), spread cells are dark (< 0)."""
    # ZERO_GUARD_R7: a collapsed (0 px) window or a 0-cell grid used to divide by zero.
    nx, ny = max(1, int(nx)), max(1, int(ny))
    w, h = max(1.0, float(w) if math.isfinite(float(w)) else 1.0), max(1.0, float(h) if math.isfinite(float(h)) else 1.0)
    xs = np.linspace(0.0, float(w), nx + 1); ys = np.linspace(0.0, float(h), ny + 1)
    X, Y = np.meshgrid(xs, ys)
    dx, dy = displacement(X, Y, fields, pulses, tau)
    PX, PY = np.nan_to_num(X + dx, nan=0.0), np.nan_to_num(Y + dy, nan=0.0)
    a0 = max(1e-9, (w / nx) * (h / ny))
    # shoelace on each displaced quad (p00, p01, p11, p10)
    x00, y00, x01, y01 = PX[:-1, :-1], PY[:-1, :-1], PX[:-1, 1:], PY[:-1, 1:]
    x11, y11, x10, y10 = PX[1:, 1:], PY[1:, 1:], PX[1:, :-1], PY[1:, :-1]
    area = 0.5 * np.abs((x00 * y01 - x01 * y00) + (x01 * y11 - x11 * y01) + (x11 * y10 - x10 * y11) + (x10 * y00 - x00 * y10))
    light = np.clip(-np.log(np.maximum(area, 1e-6) / a0) * 2.5, -1.0, 1.0)
    return PX, PY, light


def flow_point(z0: complex, lam: complex, t: float, period: float) -> tuple:
    """Position of a texture that started at z0, at time t (cycled every ``period`` s), and its visibility 0..1.
    Sink: born on the rim, spirals in and fades at the point. Source: born at the point, spirals out and fades."""
    u = (t % period)
    if lam.real <= 0:
        z = z0 * cmath.exp(lam * u)
        vis = min(1.0, abs(z) / max(1e-9, abs(z0)) * 1.6) * min(1.0, u * 2.0)
    else:
        z = (z0 * 0.06) * cmath.exp(complex(lam.real * 3.0, lam.imag) * u)
        vis = max(0.0, 1.0 - abs(z) / max(1e-9, abs(z0) * 1.4)) * min(1.0, u * 3.0)
    return z, max(0.0, min(1.0, vis))


# ------------------------------------------------------------------ video
def _hsv(h: float, s: float = 0.75, v: float = 1.0) -> np.ndarray:
    h = (h % 360.0) / 60.0
    c = v * s; x = c * (1 - abs(h % 2 - 1)); m = v - c
    r, g, b = [(c, x, 0), (x, c, 0), (0, c, x), (0, x, c), (x, 0, c), (c, 0, x)][int(h) % 6]
    return np.array([r + m, g + m, b + m], dtype=np.float32)


def _upsample(a: np.ndarray, H: int, W: int) -> np.ndarray:
    """Bilinear resize of a small 2-D array to H x W (pure numpy)."""
    a = np.asarray(a, dtype=np.float32)
    gy = np.linspace(0, a.shape[0] - 1, H); gx = np.linspace(0, a.shape[1] - 1, W)
    y0 = np.floor(gy).astype(int); x0 = np.floor(gx).astype(int)
    y1 = np.minimum(y0 + 1, a.shape[0] - 1); x1 = np.minimum(x0 + 1, a.shape[1] - 1)
    fy = (gy - y0)[:, None].astype(np.float32); fx = (gx - x0)[None, :].astype(np.float32)
    top = a[y0][:, x0] * (1 - fx) + a[y0][:, x1] * fx
    bot = a[y1][:, x0] * (1 - fx) + a[y1][:, x1] * fx
    return top * (1 - fy) + bot * fy


def video_state(engine, samples, sr: float, base_hz: float = 432.0, steps: int = 12, ratio_fn=None) -> dict:
    """Per-frame context for video: analyse the frame's audio, smooth sigma from novelty (significance of
    the music's change) and keep the spectrum on the engine for the next frame."""
    prev = getattr(engine, "_ctx_prev_spectrum", None)
    a = analyse(samples, sr, base_hz, steps, prev, ratio_fn)
    try:
        engine._ctx_prev_spectrum = a["spectrum"]
    except Exception:
        pass
    target = logistic(7.0 * (a["novelty"] - 0.22) + 2.0 * (a["energy"] - 0.5))
    s = float(getattr(engine, "_ctx_sigma", 0.25))
    s += (target - s) * 0.35
    try:
        engine._ctx_sigma = s
    except Exception:
        pass
    a["sigma"] = s
    return a


def apply_frame(img: np.ndarray, t: float, ctx: dict, strength: float = 0.5) -> np.ndarray:
    """Context effects on a finished RGB frame: flow warp (curvature), Jacobian light/dark mesh, spectral tint
    regions (soft light) and flow textures. ``ctx`` comes from ``video_state`` / ``analyse`` + 'sigma'."""
    k = max(0.0, min(1.0, float(strength)))
    src = np.asarray(img)
    if src.ndim == 3 and src.shape[2] == 4:                  # RGBA: the effect touches colour only, alpha is kept
        rgb = apply_frame(src[:, :, :3], t, ctx, strength)
        return np.concatenate([rgb, np.ascontiguousarray(src[:, :, 3:4], dtype=np.uint8)], axis=2)
    if src.ndim == 2:
        src = np.repeat(src[:, :, None], 3, axis=2)
    img = np.ascontiguousarray(src[:, :, :3], dtype=np.uint8)
    if k <= 0.0:
        return img.copy()
    H, W = img.shape[:2]
    if H < 8 or W < 8:
        return img.copy()
    sigma = float(ctx.get("sigma", 0.25)); lam = flow_lambda(sigma)
    energy = float(ctx.get("energy", 0.0))
    cx = W * (0.25 + 0.5 * float(ctx.get("centroid", 0.5)))      # the field's centre sits at the spectral centroid
    cy = H * 0.5
    R = 0.42 * min(W, H) * (1.0 + 0.5 * energy)
    fields = [(cx, cy, lam, R, k * (0.6 + 0.6 * energy))]
    for rg in regions(t, sigma, W, H, ctx.get("bands"), (W * 0.5, H * 0.5)):
        fields.append((rg["cx"], rg["cy"], complex(0.0, FLOW_W), 0.6 * (rg["rx"] + rg["ry"]), 0.35 * k * rg["alpha"]))
    # coarse grid -> warp + light
    gx, gy = 48, max(8, int(round(48 * H / max(1, W))))
    PX, PY, light = mesh(W, H, gx, gy, fields)
    xs = np.linspace(0, W, gx + 1); ys = np.linspace(0, H, gy + 1)
    X, Y = np.meshgrid(xs, ys)
    DX = _upsample(PX - X, H, W); DY = _upsample(PY - Y, H, W)
    jj = np.clip((np.arange(W)[None, :] - DX).round().astype(np.int64), 0, W - 1)
    ii = np.clip((np.arange(H)[:, None] - DY).round().astype(np.int64), 0, H - 1)
    out = img[ii, jj].astype(np.float32)
    L = _upsample(light, H, W)
    out *= (1.0 + 0.55 * k * L)[:, :, None]
    # tint regions: soft light, opacity by band energy
    yy, xx = np.mgrid[0:H:4, 0:W:4]
    tint = np.zeros(yy.shape + (3,), dtype=np.float32); wsum = np.zeros(yy.shape, dtype=np.float32)
    for rg in regions(t, sigma, W, H, ctx.get("bands"), (W * 0.5, H * 0.5)):
        a = math.radians(rg["angle"]); ca, sa = _tcos(a), _tsin(a)
        u = ((xx - rg["cx"]) * ca + (yy - rg["cy"]) * sa) / max(1.0, rg["rx"])
        v = (-(xx - rg["cx"]) * sa + (yy - rg["cy"]) * ca) / max(1.0, rg["ry"])
        m = np.exp(-(u * u + v * v) * 1.6) * rg["alpha"]
        tint += m[:, :, None] * _hsv(rg["hue"] + 0.0 * t)[None, None, :]; wsum += m
    deg_col = _hsv(float(ctx.get("hue", 0.0)), 0.6)
    tint = tint / np.maximum(wsum, 1e-6)[:, :, None]
    alpha = np.clip(wsum, 0, 1) * 0.55 * k
    tint_f = _upsample(alpha, H, W)[:, :, None]
    tint_c = np.stack([_upsample(tint[:, :, c], H, W) for c in range(3)], axis=2)
    tint_c = 0.8 * tint_c + 0.2 * deg_col[None, None, :]                # pitch-class colour runs through every tint
    base = out / 255.0
    soft = np.where(tint_c < 0.5, 2 * base * tint_c + base * base * (1 - 2 * tint_c),
                    2 * base * (1 - tint_c) + np.sqrt(np.clip(base, 0, 1)) * (2 * tint_c - 1))
    out = (base * (1 - tint_f) + soft * tint_f) * 255.0
    # textures carried by the flow
    n_tex = int(10 + 30 * k)
    col = _hsv(float(ctx.get("hue", 0.0)) + 180.0 * curvature(sigma), 0.5) * 255.0
    period = 2.6 + 1.2 * calmness(sigma)
    golden = 0.6180339887
    for i in range(n_tex):
        f1 = (i * golden) % 1.0; f2 = (i * golden * golden) % 1.0
        z0 = complex(_tcos(2 * math.pi * f2), 0.72 * _tsin(2 * math.pi * f2)) * R * (0.75 + 0.35 * f1)
        z, vis = flow_point(z0, lam, t + period * f1, period)
        if vis <= 0.03:
            continue
        ang = math.atan2(z.imag, z.real) + math.pi / 2
        Ls = 6 + 18 * (1 - calmness(sigma))
        for s in np.linspace(-0.5, 0.5, 9):
            px = int(cx + z.real + s * Ls * _tcos(ang)); py = int(cy + z.imag + s * Ls * _tsin(ang))
            if 1 <= px < W - 1 and 1 <= py < H - 1:
                out[py - 1:py + 2, px - 1:px + 2] = out[py - 1:py + 2, px - 1:px + 2] * (1 - 0.6 * vis * k) + col * 0.6 * vis * k
    return np.clip(out, 0, 255).astype(np.uint8)


def _upsample_rgb(img: np.ndarray, H: int, W: int) -> np.ndarray:
    """Bilinear resize of an RGB uint8 frame to H x W."""
    img = np.asarray(img)
    if img.shape[0] == H and img.shape[1] == W:
        return np.ascontiguousarray(img[:, :, :3], dtype=np.uint8)
    return np.clip(np.stack([_upsample(img[:, :, c].astype(np.float32), H, W) for c in range(3)], axis=2), 0, 255).astype(np.uint8)
