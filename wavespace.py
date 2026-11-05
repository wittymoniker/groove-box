"""Wavespace: exact band-limited periodic waveforms for every Groovebox voice.

GROOVEBOX_R23R_WAVESPACE_20261031

A periodic waveform with fundamental phase ``phi`` and K harmonics is

    w(phi) = sum_{k=1..K} a_k sin(k phi) + b_k cos(k phi)

and, by Fourier's theorem, every square-integrable periodic waveform is the
limit of such sums; at a given pitch only the harmonics below Nyquist can be
heard, so the band-limited sum *is* the waveform the speaker can play.
This module evaluates that sum exactly (Chebyshev recurrence, no lookup
table, no interpolation, no aliasing) and supplies the coefficients from:

* the user: a drawn cycle (any shape) -> its exact discrete Fourier series;
* the canonical engines: a seeded point of waveform space.

Canonical coverage (why the canonical writer can reach any pitched timbre):
for the integer index n = seed*64 + slot, harmonic k gets

    u_k = frac(n*sqrt(P_k)),  v_k = frac(n*sqrt(P_{K+k})),  w = frac(n*sqrt(P_{2K+1}))

with P_j the j-th prime. The square roots of distinct primes are linearly
independent over the rationals together with 1, so by Weyl's equidistribution
theorem the points (u, v, w) are equidistributed in the unit cube as n runs.
Amplitude (2u_k-1)*k^-p, phase 2*pi*v_k and tilt p = 2.5*(1-w) therefore come
arbitrarily close to every harmonic spectrum whose partials do not exceed the
fundamental, i.e. the set of canonical timbres is dense in pitched waveform
space; low harmonics come first (most relevant first), higher ones refine.

The geometric synths are also instanced per voice here (same laws, slot-offset):
vector -> harmonic phase shear / odd-even balance / spectral tilt, ball ->
bounce-trajectory amplitude + brightness motion, cellular -> automaton density
deciding how many harmonics are active over time.
"""
from __future__ import annotations

import math

import numpy as np

WAVESPACE_HARMONICS = 64          # canonical coefficient count (before Nyquist)
DRAWN_WAVE_POINTS = 2048          # stored samples of one drawn cycle
DRAWN_MAX_HARMONICS = DRAWN_WAVE_POINTS // 2 - 1

_PHI_INV = (math.sqrt(5.0) - 1.0) / 2.0


def _primes(count):
    out, c = [], 2
    while len(out) < count:
        if all(c % p for p in out if p * p <= c):
            out.append(c)
        c += 1
    return out


_SQRT_PRIMES = np.sqrt(np.asarray(_primes(2 * WAVESPACE_HARMONICS + 2), dtype=np.float64))


def _wave_pool():
    """The app's shared compute pool when it exists (None on a single thread / outside the app)."""
    try:
        import groovebox as _g
        return _g._compute_pool()
    except Exception:
        return None


def fourier_wave(phase, a, b, weights=None):
    """Exact sum_k a[k-1] sin(k*phase) + b[k-1] cos(k*phase).

    Clenshaw recurrence on Chebyshev polynomials (x = cos phase):
        sum_k a_k sin(k phi) = sin(phi) * sum_k a_k U_{k-1}(x)
        sum_k b_k cos(k phi) = sum_k b_k T_k(x)
    both evaluated with y_k = c_k + 2x*y_{k+1} - y_{k+2} in place (one multiply
    and two adds per harmonic per sample). ``weights`` (optional) is a callable
    k -> per-sample gain for harmonic k (time-varying harmonic activity).
    """
    ph = np.asarray(phase, dtype=np.float64)
    a = np.asarray(a, dtype=np.float64).ravel()
    b = np.asarray(b, dtype=np.float64).ravel()
    K = int(min(a.size, b.size))
    if K <= 0 or ph.size == 0:
        return np.zeros(ph.shape, dtype=np.float64)
    nz = np.nonzero((a[:K] != 0.0) | (b[:K] != 0.0))[0]
    if nz.size == 0:
        return np.zeros(ph.shape, dtype=np.float64)
    K = int(nz[-1]) + 1
    x = np.cos(ph)
    two_x = 2.0 * x
    shape = ph.shape
    ws = [(weights(k) if weights is not None else None) for k in range(K, 0, -1)]   # called once per k, original order

    def _run(coef):                      # one Clenshaw recurrence (sine/U or cosine/T), identical ops either way
        y1 = np.zeros(shape); y2 = np.zeros(shape); tmp = np.empty(shape)
        for i, k in enumerate(range(K, 0, -1)):
            ck = coef[k - 1]; w = ws[i]
            np.multiply(two_x, y1, out=tmp); tmp -= y2
            if ck != 0.0:
                tmp += (ck * w) if w is not None else ck
            y2, y1, tmp = y1, tmp, y2
        return y1, y2
    pool = _wave_pool() if ph.size >= 50000 and K >= 4 else None   # WAVESPACE_THREADED_20261102
    if pool is not None:
        try:
            fut = pool.submit(_run, b)
            ys1, ys2 = _run(a)
            yc1, yc2 = fut.result()
        except Exception:
            ys1, ys2 = _run(a); yc1, yc2 = _run(b)
    else:
        ys1, ys2 = _run(a); yc1, yc2 = _run(b)
    # sum a_k U_{k-1}(x) = ys_1 ; sum_{k>=1} b_k T_k(x) = x*yc_1 - yc_2
    out = np.sin(ph) * ys1
    out += x * yc1 - yc2
    return out


def nyquist_harmonics(phase, sample_rate, cap):
    """Largest harmonic count that stays below Nyquist for this phase track."""
    ph = np.asarray(phase, dtype=np.float64).ravel()
    if ph.size < 2:
        return int(cap)
    dphi = float(np.max(np.abs(np.diff(ph))))
    if dphi <= 0.0:
        return int(cap)
    # k * dphi < pi  <=>  harmonic k below Nyquist.
    k = math.floor(math.pi / dphi)
    if k * dphi >= math.pi:       # exactly on Nyquist is not below it
        k -= 1
    return int(max(1, min(int(cap), k)))


def band_limit(a, b, k_max):
    a = np.array(a, dtype=np.float64, copy=True)
    b = np.array(b, dtype=np.float64, copy=True)
    k_max = max(0, int(k_max))
    a[k_max:] = 0.0
    b[k_max:] = 0.0
    return a, b


def _normalize_peak(a, b):
    grid = np.linspace(0.0, 2.0 * math.pi, 1024, endpoint=False)
    pk = float(np.max(np.abs(fourier_wave(grid, a, b)))) if np.any(a) or np.any(b) else 0.0
    if pk > 0.0:
        a = a / pk
        b = b / pk
    return a, b


def canonical_wavespace_coefficients(seed, slot=0, lane=0, harmonics=WAVESPACE_HARMONICS):
    """Seeded canonical point of waveform space (see module docstring)."""
    K = int(max(1, min(int(harmonics), WAVESPACE_HARMONICS)))
    n = (int(seed) % (1 << 24)) * 64 + (int(slot) % 48) + 4096 * (int(lane) % 4)
    n = max(1, n)
    u = np.mod(n * _SQRT_PRIMES[:K], 1.0)
    v = np.mod(n * _SQRT_PRIMES[K:2 * K], 1.0)
    w = float(np.mod(n * _SQRT_PRIMES[2 * K], 1.0))
    p = 2.5 * (1.0 - w)
    k = np.arange(1, K + 1, dtype=np.float64)
    amp = (2.0 * u - 1.0) * np.power(k, -p)
    amp[0] = 1.0                       # pitch identity: unit fundamental
    theta = 2.0 * math.pi * v
    theta[0] = 0.0
    a = amp * np.cos(theta)
    b = amp * np.sin(theta)
    return _normalize_peak(a, b)


def drawn_wave_coefficients(table, harmonics=DRAWN_MAX_HARMONICS):
    """Exact Fourier series of a drawn cycle (DC removed; peak-normalized)."""
    x = np.asarray(table, dtype=np.float64).ravel()
    if x.size < 4:
        return np.zeros(1), np.zeros(1)
    N = x.size
    X = np.fft.rfft(x)
    K = int(max(1, min(int(harmonics), X.size - 2)))
    # x[n] = X0/N + (2/N) sum Re(X_k e^{i k 2pi n/N}) for k < N/2
    a = -2.0 / N * np.imag(X[1:K + 1])
    b = 2.0 / N * np.real(X[1:K + 1])
    return _normalize_peak(a, b)


def apply_vector(a, b, x=0.0, y=0.0, z=0.0, depth=1.0):
    """Vector lane per voice: x shears harmonic phases, y balances odd/even, z tilts."""
    a = np.asarray(a, dtype=np.float64)
    b = np.asarray(b, dtype=np.float64)
    d = float(np.clip(depth, 0.0, 1.0))
    if d <= 0.0 or (x == 0.0 and y == 0.0 and z == 0.0):
        return a.copy(), b.copy()
    k = np.arange(1, a.size + 1, dtype=np.float64)
    rot = d * float(x) * (math.pi / 4.0) * (k - 1.0)
    cr, sr = np.cos(rot), np.sin(rot)
    a2 = a * cr - b * sr
    b2 = a * sr + b * cr
    odd = (k % 2.0) == 1.0
    bal = np.where(odd, 1.0 + 0.5 * d * float(y), 1.0 - 0.5 * d * float(y))
    bal[0] = 1.0
    tilt = np.power(k, -0.5 * d * float(z))
    g = bal * tilt
    return a2 * g, b2 * g


def ball_curves(ball_state, throw_ball):
    """Shared Ball trajectory curves (x, y, speed_norm, hit) over normalized time."""
    ball = dict(ball_state or {})
    steps = max(32, min(2048, int(ball.get("steps", 256) or 256)))
    coeff = ball.get("gravity_coefficients", None)
    if not isinstance(coeff, (list, tuple)) or not coeff:
        coeff = (0.0, 0.0, float(ball.get("gravity", .25)))
    traj = throw_ball(steps=steps, x=float(np.clip(ball.get("x", 0.0), -1.0, 1.0)),
                      y=float(np.clip(ball.get("y", 0.0), -1.0, 1.0)),
                      vx=float(ball.get("vx", .7)), vy=float(ball.get("vy", -.4)),
                      gravity_coefficients=coeff, radius=float(np.clip(ball.get("radius", 1.0), .01, 1.0)),
                      dt=float(np.clip(ball.get("dt", .025), .0001, .25)),
                      gravity_angle_degrees=float(ball.get("gravity_angle_degrees", 90.0)),
                      reverse_polarity_on_hit=bool(ball.get("reverse_polarity_on_hit", True)))
    samples = traj.get("samples", [])
    if not samples:
        return None
    xp = np.asarray([q["x"] for q in samples], dtype=np.float64)
    yp = np.asarray([q["y"] for q in samples], dtype=np.float64)
    speed = np.asarray([q["speed"] for q in samples], dtype=np.float64)
    hit = np.asarray([1.0 if q["collision"] else 0.0 for q in samples], dtype=np.float64)
    _smax = float(np.max(speed)) if speed.size else 0.0
    speed_norm = speed / _smax if _smax > 0.0 else np.zeros_like(speed)   # motionless = 0
    return {"x": xp, "y": yp, "speed_norm": speed_norm, "hit": hit}


def cellular_density(ca_state):
    """Shared cellular automaton density per generation (same law as the carrier)."""
    ca = dict(ca_state or {})
    width = max(4, min(64, int(ca.get("width", 16) or 16)))
    height = max(4, min(64, int(ca.get("height", 16) or 16)))
    states = max(2, min(8, int(ca.get("cell_types", 3) or 3)))
    generations = max(1, min(256, int(ca.get("generations", 16) or 16)))
    rule = max(0, min(255, int(ca.get("rule", 30) or 0)))
    neighborhood = str(ca.get("neighborhood", "moore")).lower()
    grid = np.fromfunction(lambda yy0, xx0: (((xx0 * 7 + yy0 * 13 + 3) % 17) == 0).astype(np.int16), (height, width), dtype=int)
    manual = ca.get("manual_cells", [])
    if isinstance(manual, (list, tuple)):
        for pos in manual:
            if isinstance(pos, (list, tuple)) and len(pos) >= 2:
                try:
                    xx0 = int(pos[0]); yy0 = int(pos[1])
                    if 0 <= xx0 < width and 0 <= yy0 < height:
                        grid[yy0, xx0] = 1
                except (TypeError, ValueError, OverflowError):
                    pass
    offsets = ((-1, -1), (0, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (0, 1), (1, 1)) if neighborhood == "moore" else ((0, -1), (-1, 0), (1, 0), (0, 1))
    density = [float(np.sum(grid, dtype=np.float64)) / (width * height * (states - 1))]
    for _ in range(generations):
        occupied = (grid > 0).astype(np.int16, copy=False)
        neighbours = np.zeros((height, width), dtype=np.int16)
        for dx, dy in offsets:
            neighbours += np.roll(occupied, shift=(dy, dx), axis=(0, 1))
        bit = (rule >> (neighbours % 8)) & 1
        grid = np.where(bit != 0, np.minimum(states - 1, grid + 1), np.maximum(0, grid - 1)).astype(np.int16, copy=False)
        density.append(float(np.sum(grid, dtype=np.float64)) / (width * height * (states - 1)))
    return np.asarray(density, dtype=np.float64)


def _curve_at(curve, u):
    c = np.asarray(curve, dtype=np.float64)
    if c.size == 1:
        return np.full(np.shape(u), float(c[0]))
    return np.interp(np.mod(u, 1.0) * (c.size - 1), np.arange(c.size, dtype=np.float64), c)


def geometric_voice(phase, abs_t, total_duration, slot, coeffs, *, sample_rate, harmonic_cap,
                    vector=None, ball=None, density=None, depths=None):
    """One voice through the per-instrument geometric synths.

    ``coeffs`` = (a, b) wavespace point; ``vector`` = (x, y, z) effective;
    ``ball`` = ball_curves() result; ``density`` = cellular_density() result;
    ``depths`` = {"vector","ball","cellular"} in [0,1] (Geometric Engine Mixer).
    With every depth 0 the output is exactly the band-limited wavespace cycle.
    """
    d = dict(depths or {})
    dv = float(np.clip(d.get("vector", 0.0), 0.0, 1.0))
    db = float(np.clip(d.get("ball", 0.0), 0.0, 1.0))
    dc = float(np.clip(d.get("cellular", 0.0), 0.0, 1.0))
    a, b = coeffs
    if vector is not None and dv > 0.0:
        a, b = apply_vector(a, b, *tuple(vector)[:3], depth=dv)
    k_max = nyquist_harmonics(phase, sample_rate, min(int(harmonic_cap), len(a)))
    a, b = band_limit(a, b, k_max)
    # Slot offset: every voice reads the same geometric field at its own
    # golden-ratio phase, so the ensemble moves together without unison copies.
    _td = float(total_duration)
    u = (np.asarray(abs_t, dtype=np.float64) / _td if _td > 0.0 else np.zeros_like(np.asarray(abs_t, dtype=np.float64))) + (int(slot) % 48) * _PHI_INV
    weights = None
    if density is not None and dc > 0.0 and k_max > 1:
        dens = np.clip(_curve_at(density, u), 0.0, 1.0)
        active = 1.0 + dens * (k_max - 1)        # harmonics switched on by the automaton

        def weights(k, _act=active, _dc=dc):
            if k == 1:
                return 1.0
            return (1.0 - _dc) + _dc * np.clip(_act - k + 1.0, 0.0, 1.0)
    out = fourier_wave(phase, a, b, weights)
    if ball is not None and db > 0.0:
        sp = _curve_at(ball["speed_norm"], u)
        hh = _curve_at(ball["hit"], u)
        out = out * ((1.0 - db) + db * np.clip(0.55 + 0.30 * sp + 0.15 * hh, 0.0, 1.0))
    return out


WAVETABLE_KNOB_DEFAULTS = {"phase": 0.0, "curvature": 0.5, "twist": 0.5, "fold": 0.2}


def apply_wavetable_knobs(a, b, phase=0.0, curvature=0.5, twist=0.5, fold=0.2):
    """Wavetable synth knobs as exact harmonic-domain transforms of the cycle.

    Identity at the defaults (phase 0, curvature .5, twist .5, fold .2), so a
    drawn cycle plays exactly as drawn until the knobs are moved.
      phase     rotates the whole cycle (k * 2*pi*phase on harmonic k);
      curvature spectral tilt k^(2*(curvature-.5)) (darker <-> brighter);
      twist     harmonic phase shear (k-1)*(twist-.5)*pi;
      fold      odd/even balance: odd harmonics x(1+2*(fold-.2)), even x(1-2*(fold-.2)).
    """
    a = np.asarray(a, dtype=np.float64)
    b = np.asarray(b, dtype=np.float64)
    k = np.arange(1, a.size + 1, dtype=np.float64)
    rot = k * 2.0 * math.pi * float(phase) + (k - 1.0) * (float(twist) - 0.5) * math.pi
    cr, sr = np.cos(rot), np.sin(rot)
    a2 = a * cr - b * sr
    b2 = a * sr + b * cr
    tilt = np.power(k, 2.0 * (float(curvature) - 0.5))
    f = float(np.clip(fold, 0.0, 1.0)) - 0.2
    bal = np.where((k % 2.0) == 1.0, 1.0 + 2.0 * f, np.clip(1.0 - 2.0 * f, 0.0, 2.0))
    bal[0] = 1.0
    g = tilt * bal
    return a2 * g, b2 * g


def instance_activity(abs_t, total_duration, slot, ball=None, density=None):
    """0..1 activity of an instance's Ball (speed) and Cellular (density) fields."""
    _td = float(total_duration)
    u = (np.asarray(abs_t, dtype=np.float64) / _td if _td > 0.0 else np.zeros_like(np.asarray(abs_t, dtype=np.float64))) + (int(slot) % 48) * _PHI_INV
    parts = []
    if ball is not None:
        parts.append(np.clip(_curve_at(ball["speed_norm"], u), 0.0, 1.0))
    if density is not None:
        parts.append(np.clip(_curve_at(density, u), 0.0, 1.0))
    if not parts:
        return None
    return sum(parts) / len(parts)
