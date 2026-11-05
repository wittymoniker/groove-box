"""GROOVEBOX_R23R_FI_BENCHMARKS_20261103 — six benchmarks: old foundations vs the new trigonometric and
finite-infinity (FI) foundations. Each pair is checked for equal results BEFORE it is timed; a benchmark
whose results differ fails (an optimisation that changes the answer is not an optimisation).

  1  partial sum        12 × sin(kθ+ψ)                    vs  Im Σ a_k e^{iψ}(e^{iθ})^k       (trig identity)
  2  synth body          samples × partials matrix         vs  block grid + pooled scratch     (same synth)
  3  CA timeline         step the automaton per block      vs  FI orbit lookup                 (pigeonhole cycle)
  4  ball at time t      simulate from 0 to t              vs  FI certified cycle lookup       (repeated state)
  5  repeated row        synthesise again                  vs  FI playlist memo                (equal inputs)
  6  world at frame t    re-simulate CA + ball to t        vs  exact O(1) state()              (audio-clock sync)

Run:  python benchmark_multidim_fi.py          (prints a table; exit code 1 if any pair disagrees)
"""
from __future__ import annotations

import math
import time

import numpy as np

import multidim_synth as md
import multidim_scene as sc


def _best(fn, repeat=3):
    best = float("inf")
    out = None
    for _ in range(repeat):
        t0 = time.perf_counter()
        out = fn()
        best = min(best, time.perf_counter() - t0)
    return best, out


# ---------------------------------------------------------------- old foundations (reference)
def old_partial_sum(theta, amps, psi):
    return np.sum(amps[None, :] * np.sin(np.outer(theta, np.arange(1, len(amps) + 1)) + psi[None, :]), axis=1)


def new_partial_sum(theta, amps, psi):
    z = np.exp(1j * theta)
    zk = np.ones_like(z)
    y = np.zeros(theta.size)
    e = np.exp(1j * psi)
    for k in range(len(amps)):
        zk *= z
        y += amps[k] * (zk * e[k]).imag
    return y


def old_synth_body(step, mult, turn, amps_b, blk, n):
    """The first implementation: per-sample (samples × partials) amplitude matrix, fresh arrays."""
    amps = np.repeat(amps_b, blk, axis=0)[:n]
    mult_s = np.repeat(mult, blk)[:n]
    nb = len(mult)
    cum = np.concatenate([[0.0], np.cumsum(turn)])
    ramp = (np.arange(nb * blk) % blk) / float(blk)
    phi = (np.repeat(cum[:-1], blk) + np.repeat(turn, blk) * ramp)[:n]
    theta = np.cumsum(step * mult_s) + phi
    kk = np.arange(1, amps_b.shape[1] + 1, dtype=np.float64)
    psi = (kk * 2.399963229728653) % math.tau
    Y = np.sum(amps * np.sin(np.outer(theta, kk) + psi), axis=1)
    S = np.sum(np.abs(amps), axis=1)
    return np.divide(Y, S, out=np.zeros_like(Y), where=S != 0)


def old_ca_rows(rule, nb, seed):
    table = np.array([(rule >> i) & 1 for i in range(8)], dtype=np.uint8)
    rows = np.zeros((nb, md.H), dtype=np.uint8)
    cur = np.asarray(seed, dtype=np.uint8)
    for b in range(nb):
        if not cur.any():
            cur = np.asarray(seed, dtype=np.uint8)
        rows[b] = cur
        idx = (np.roll(cur, 1) << 2) | (cur << 1) | np.roll(cur, -1)
        cur = table[idx]
    return rows


def old_ball(nb, dt, g, e):
    hs = np.zeros(nb)
    h, v = 1.0, 0.0
    g = abs(g); e = min(0.99, max(0.0, e))
    for b in range(nb):
        v -= g * dt
        h += v * dt
        if h <= 0.0:
            h = 0.0; v = -v * e
            if v < 0.05 * g * dt * 10:
                v = math.sqrt(2.0 * g) if g > 0 else 0.0
        hs[b] = min(1.0, h)
    return hs


class _Pool:
    def __init__(self):
        self.d = {}

    def borrow_vector(self, kind, n, dtype, fill=None):
        key = (kind, int(n), np.dtype(dtype).str)
        a = self.d.get(key)
        if a is None:
            a = self.d[key] = np.empty(int(n), dtype=dtype)
        if fill is not None:
            a.fill(fill)
        return a


# ---------------------------------------------------------------- the six benchmarks
def run(sr=48000, seconds=2.0):
    rows = []
    n = int(sr * seconds)
    t = np.arange(n) / sr
    theta = 2 * np.pi * 220.0 * t
    amps = 1.0 / np.arange(1, md.H + 1)
    psi = (np.arange(1, md.H + 1) * 2.399963229728653) % math.tau

    # 1 partial sum
    a1, r_old = _best(lambda: old_partial_sum(theta, amps, psi))
    b1, r_new = _best(lambda: new_partial_sum(theta, amps, psi))
    rows.append(("1 partial sum (trig identity)", a1, b1, float(np.max(np.abs(r_old - r_new))), 1e-9))

    # 2 synth body (same controls, old matrix vs new grid)
    p = md.preset_params("Cellular choir")
    blk = max(16, int(round(p["block_ms"] * 1e-3 * sr)))
    nb = (n + blk - 1) // blk
    step = np.full(n, 2 * np.pi * 220.0 / sr)
    mult = 1.0 + 0.1 * np.sin(np.arange(nb) * 0.3)
    turn = 0.05 * np.cos(np.arange(nb) * 0.2)
    amps_b = np.abs(np.sin(np.arange(nb)[:, None] * 0.1 + np.arange(md.H)[None, :])) / np.arange(1, md.H + 1)
    old2 = lambda: old_synth_body(step, mult, turn, amps_b, blk, n)

    def new2():
        pool = _Pool()
        N = nb * blk
        st = pool.borrow_vector("s", N, np.float64); st[:n] = step; st[n:] = 0
        th = pool.borrow_vector("th", N, np.float64)
        np.multiply(st.reshape(nb, blk), mult[:, None], out=th.reshape(nb, blk)); np.cumsum(th, out=th)
        cum = np.concatenate([[0.0], np.cumsum(turn)])
        th.reshape(nb, blk)[:] += cum[:-1, None] + turn[:, None] * (np.arange(blk) / float(blk))[None, :]
        z = pool.borrow_vector("z", N, np.complex128); np.cos(th, out=z.real); np.sin(th, out=z.imag)
        zk = pool.borrow_vector("zk", N, np.complex128); zk.fill(1)
        Y = pool.borrow_vector("Y", N, np.float64); Y.fill(0)
        tmp = pool.borrow_vector("t", N, np.float64); tmp2 = pool.borrow_vector("t2", N, np.float64)
        kk = np.arange(1, md.H + 1); ps = (kk * 2.399963229728653) % math.tau
        for k in range(md.H):
            np.multiply(zk, z, out=zk)
            np.multiply(zk.imag, math.cos(ps[k]), out=tmp); np.multiply(zk.real, math.sin(ps[k]), out=tmp2); tmp += tmp2
            tmp.reshape(nb, blk)[:] *= amps_b[:, k, None]
            Y += tmp
        S = np.sum(np.abs(amps_b), axis=1)
        Y2 = Y.reshape(nb, blk)
        np.divide(Y2, S[:, None], out=Y2, where=S[:, None] != 0)
        return Y[:n].copy()
    a2, r_old = _best(old2)
    b2, r_new = _best(new2)
    rows.append(("2 synth body (block grid + pool)", a2, b2, float(np.max(np.abs(r_old - r_new))), 1e-9))

    # 3 CA timeline (10 minutes of 12 ms blocks)
    seed = np.array([1, 0, 1, 1, 0, 0, 1, 0, 1, 0, 0, 1], dtype=np.uint8)
    nbl = int(600.0 / 0.012)
    md._ORBIT_CACHE.clear()
    a3, r_old = _best(lambda: old_ca_rows(110, nbl, seed), repeat=1)
    b3, r_new = _best(lambda: md._ca_rows(110, nbl, seed))
    rows.append(("3 CA 10-min timeline (FI orbit)", a3, b3, float(np.sum(r_old != r_new)), 0.0))

    # 4 ball at a deep time (200 random queries up to 10 minutes in)
    rng = np.random.default_rng(3)
    qs = rng.integers(0, nbl, 200)
    dt = blk / sr
    a4, r_old = _best(lambda: np.array([old_ball(int(b) + 1, dt, 9.8, 0.8)[-1] for b in qs[:20]]), repeat=1)
    md._BALL_ORBITS.clear()
    b4, r_new = _best(lambda: np.array([md.ball_at(int(b), dt, 9.8, 0.8) for b in qs[:20]]))
    rows.append(("4 ball at time t (FI cycle)", a4, b4, float(np.max(np.abs(r_old - r_new))), 0.0))

    # 5 repeated playlist row
    md.memo_clear()
    inc = np.full(n, 2 * np.pi * 220.0 / sr)
    ph = np.cumsum(inc)
    md.voice(ph, sr, p, seed_int=7, slot=3, step=inc)                       # first occurrence (fills memo)
    def old5():
        md.memo_clear()
        return md.voice(ph + 9.87, sr, p, seed_int=7, slot=3, step=inc)
    a5, r_old = _best(old5)
    md.voice(ph, sr, p, seed_int=7, slot=3, step=inc)
    b5, r_new = _best(lambda: md.voice(ph + 9.87, sr, p, seed_int=7, slot=3, step=inc))
    rows.append(("5 repeated row (FI playlist memo)", a5, b5, float(np.max(np.abs(r_old - r_new))), 0.0))

    # 6 the world at a video frame 10 minutes into a row-long timeline (no row reset, worst case)
    tq = 600.0
    bq = int(tq * sr) // blk
    def old6():
        rows_ = old_ca_rows(p["ca_rule"], bq + 1, np.array([((7 >> (k % 31)) & 1) ^ ((3 + k) % 2) for k in range(md.H)], dtype=np.uint8))
        hb = old_ball(bq + 1, blk / sr, p["gravity"], p["restitution"])
        return np.concatenate([rows_[-1].astype(float), [hb[-1]]])
    def new6():
        s_ = sc.state(p, 7, 3, tq, sr=sr, row_dur=None)
        return np.concatenate([s_["ca"][-1].astype(float), [s_["ball"]]])
    a6, r_old = _best(old6, repeat=1)
    b6, r_new = _best(new6)
    rows.append(("6 world at frame t=10 min (exact state)", a6, b6, float(np.max(np.abs(r_old - r_new))), 0.0))
    return rows


def main():
    rows = run()
    ok = True
    print(f"{'benchmark':42s} {'old':>11s} {'new':>11s} {'speed-up':>9s}  max |old−new|  agree")
    for name, a, b, err, tol in rows:
        agree = err <= tol
        ok &= agree
        print(f"{name:42s} {a*1000:9.2f}ms {b*1000:9.2f}ms {a/b if b > 0 else float('inf'):8.1f}×  {err:12.3g}  {'yes' if agree else 'NO'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
