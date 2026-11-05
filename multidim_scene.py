"""GROOVEBOX_R23R_MULTIDIM_SCENE_20261103 — the multidimensional synth as a shared 3-D world.

The synth's four dimensions are deterministic and exactly addressable at any time t (the CA from
its certified orbit, the ball from its certified cycle), so video and games can read the SAME
(recorded by the audio render — loud/quiet decisions and domain weight included)
world the audio plays — no separate simulation, no drift:

  state(params, seed, slot, t)  →  CA generation + history, ball height, vector, partial table,
                                    fixed-resonator heights, domain weight (structure ↔ flow)

VIDEO component  — render_layer(img, states, t, opacity): a perspective 3-D layer drawn into the
                   frame (numpy only): CA generations as a voxel stack receding in depth, the ball,
                   the vector beam, partial pillars on a ring, fixed-resonator halos. One cell per
                   instrument programme, arranged around the frame centre.
GAME component   — entities(states, t): the same world as game objects —
                   'platform' (live CA cells), 'bouncer' (the ball), 'wind' (the vector),
                   'pillar' (partials), 'portal' (fixed resonators: zones at fixed heights),
                   'pulse' (domain weight: structure ↔ flow).
"""
from __future__ import annotations

import math

import numpy as np

import multidim_synth as md


def state(params, seed_int, slot, t, sr=48000.0, row_dur=None):
    """The synth's world at time t (seconds) — exact lookup (no stepping), on the AUDIO's own clock:
    the audio restarts its world at every playlist row (row-relative time), its control blocks are a
    whole number of samples at the render rate (blk = round(block_ms · sr)), and the ball steps by
    exactly blk / sr. Using the same three facts here keeps picture and sound in lock-step forever."""
    p = params
    sr = float(sr)
    blk = max(16, int(round(float(p.get("block_ms", 12.0)) * 1e-3 * sr)))
    tt = float(t)
    if row_dur is not None and float(row_dur) > 0:
        tt = tt % float(row_dur)                       # row-relative, like the render
    b = max(0, int(tt * sr) // blk)                    # whole samples → block (no float drift)
    dt = blk / sr
    seed_cells = np.array([((int(seed_int) >> (k % 31)) & 1) ^ ((int(slot) + k) % 2) for k in range(md.H)], dtype=np.uint8)
    if not seed_cells.any():
        seed_cells[md.H // 2] = 1
    states_, mu, period = md._ca_orbit(p.get("ca_rule", 90), seed_cells)    # exact rows from the orbit, O(1)
    bs = np.arange(max(0, b - 15), b + 1)
    idx = np.where(bs < len(states_), bs, mu + (bs - mu) % max(1, period))
    hist = states_[np.minimum(idx, len(states_) - 1)]
    h = md.ball_at(b, dt, p.get("gravity", 9.8), p.get("restitution", 0.8))   # exact, O(1), same dt as audio
    tb = b * dt                                        # the audio's block start time (vector steps per block)
    vx, vy, vz = (list(p.get("vector") or [0.5, 0.5, 0.5]) + [0.5] * 3)[:3]
    rot = float(p.get("rot_hz", 0.1)) * math.tau * tb
    vec = (vx * math.cos(rot) - vy * math.sin(rot), vz * math.cos(0.5 * rot), vx * math.sin(rot) + vy * math.cos(rot))
    try:
        amps = md.table_amplitudes(p.get("script", "1/k"))
    except Exception:
        amps = np.zeros(md.H)
    m = float(np.max(np.abs(amps))) if amps.size else 0.0
    amps = amps / m if m > 0 else amps
    ratios = ()
    for part in str(p.get("resonators", "harmonic")).split("+"):
        ratios = ratios + tuple(r for r in md.RESONATOR_RULES.get(part.strip(), ()) if r not in ratios)
    live = float(hist[-1].mean()) if len(hist) else 0.0
    # GROOVEBOX_R23R_WORLD_RECORD_20261103: prefer the audio's recorded world when it exists
    # (loud/quiet decisions and domain weight were decided during the render).
    wr = md.world_at(p, seed_int, slot, b)
    domain = 0.5
    loud = False
    quiet = False
    amp = 0.0
    if wr is not None:
        domain = wr["domain"]
        loud = wr["loud"]
        quiet = wr["quiet"]
        amp = wr["amp"]
        # use recorded dimensions when present (bit-identical to the render)
        if "ball" in wr:
            h = wr["ball"]
        if "vector" in wr:
            vec = wr["vector"]
        if "live" in wr:
            live = wr["live"]
        if wr.get("ca_row") is not None and len(hist):
            hist = hist.copy()
            hist[-1] = wr["ca_row"]
    return {"block": b, "ca": hist, "ball": h, "vector": vec, "amps": amps, "resonators": ratios,
            "live": live, "preset": p.get("preset", ""), "slot": int(slot),
            "domain": domain, "loud": loud, "quiet": quiet, "amp": amp}


# ---------------------------------------------------------------------------- video
def _project(P, yaw, pitch, dist, cx, cy, f):
    P = np.asarray(P, dtype=np.float64).reshape(-1, 3)
    cyw, syw, cp, sp = math.cos(yaw), math.sin(yaw), math.cos(pitch), math.sin(pitch)
    x = cyw * P[:, 0] - syw * P[:, 2]
    z = syw * P[:, 0] + cyw * P[:, 2]
    y = cp * P[:, 1] - sp * z
    z = sp * P[:, 1] + cp * z + dist
    ok = z > 0.05
    zs = np.where(ok, z, 1.0)
    return np.stack([cx + f * x / zs, cy - f * y / zs], axis=1), z, ok


def _disc(img, x, y, r, col, alpha):
    h, w = img.shape[:2]
    r = max(1.0, float(r))
    x0, x1 = int(max(0, x - r)), int(min(w, x + r + 1))
    y0, y1 = int(max(0, y - r)), int(min(h, y + r + 1))
    if x0 >= x1 or y0 >= y1:
        return
    yy, xx = np.mgrid[y0:y1, x0:x1]
    d2 = (xx - x) ** 2 + (yy - y) ** 2
    m = np.clip(1.0 - d2 / (r * r), 0.0, 1.0)[..., None] * float(alpha)
    img[y0:y1, x0:x1, :3] = img[y0:y1, x0:x1, :3] * (1.0 - m) + np.asarray(col, dtype=np.float32) * m


def _line(img, p0, p1, col, alpha, width=1.5):
    n = int(max(2, min(400, math.hypot(p1[0] - p0[0], p1[1] - p0[1]))))
    for i in range(0, n, 2):
        u = i / float(n - 1)
        _disc(img, p0[0] + u * (p1[0] - p0[0]), p0[1] + u * (p1[1] - p0[1]), width, col, alpha)


def _hsv(hdeg, s, v):
    import colorsys
    r, g, b = colorsys.hsv_to_rgb((hdeg % 360) / 360.0, s, v)
    return (255 * r, 255 * g, 255 * b)


def render_layer(img, states, t, opacity=0.5):
    """Draw the multidimensional world(s) into a float RGB frame (in place) and return it.
    ``states``: list of state() dicts (one per instrument programme, up to 4 drawn)."""
    if not states or opacity <= 0.0:
        return img
    h, w = img.shape[:2]
    k = min(4, len(states))
    yaw, pitch = 0.6 + 0.15 * float(t), 0.42
    for i, st in enumerate(states[:k]):
        # one world per programme: arranged around the centre (one = centred)
        if k == 1:
            cx, cy, f = w / 2, h / 2, min(w, h) * 0.55
        elif k == 2:
            cx, cy, f = w / 2 + (-0.25 if i == 0 else 0.25) * w, h / 2, min(w, h) * 0.5
        else:
            ang = math.tau * i / k
            cx, cy, f = w / 2 + 0.24 * w * math.cos(ang), h / 2 + 0.22 * h * math.sin(ang), min(w, h) * 0.32
        a = float(opacity)
        # fixed resonators: halos at fixed heights
        rs = st["resonators"]
        if rs:
            rmax = max(rs)
            for r in rs:
                yy = -1.0 + 2.0 * (math.log(r) / math.log(rmax) if rmax > 1 else 0.5)
                angs = np.linspace(0, math.tau, 28)
                ring = np.stack([1.1 * np.cos(angs), np.full_like(angs, yy), 1.1 * np.sin(angs)], axis=1)
                S, _z, ok = _project(ring, yaw, pitch, 4.2, cx, cy, f)
                for j in range(len(angs)):
                    if ok[j]:
                        _disc(img, S[j][0], S[j][1], 1.6, (255, 209, 102), 0.5 * a)
        # partial pillars on the floor ring
        for j, amp in enumerate(st["amps"]):
            ang = math.tau * j / md.H + 0.2 * float(t)
            x, z = 0.95 * math.cos(ang), 0.95 * math.sin(ang)
            S, _z, ok = _project([[x, -1.0, z], [x, -1.0 + 1.6 * abs(float(amp)), z]], yaw, pitch, 4.2, cx, cy, f)
            if ok.all():
                _line(img, S[0], S[1], _hsv(200 + 12 * j, 0.7, 1.0), 0.8 * a, 1.6)
        # CA generations: voxel stack in depth (front = now)
        hist = st["ca"]
        for d in range(len(hist)):
            row = hist[-1 - d]
            zz = -0.9 + 1.8 * d / 16.0
            for c in np.flatnonzero(row):
                xx = -0.9 + 1.8 * c / (md.H - 1)
                S, Z, ok = _project([[xx, 0.85, zz]], yaw, pitch, 4.2, cx, cy, f)
                if ok[0]:
                    _disc(img, S[0][0], S[0][1], max(1.2, 6.0 / float(Z[0])), (120, 255, 200), a * (1.0 - d / 16.0))
        # the ball (and its shadow)
        S, Z, ok = _project([[0.0, -1.0 + 1.8 * st["ball"], 0.0], [0.0, -1.0, 0.0]], yaw, pitch, 4.2, cx, cy, f)
        if ok.all():
            _disc(img, S[1][0], S[1][1], max(2.0, 10.0 / float(Z[1])), (20, 20, 25), 0.35 * a)
            ball_col = (255, 107, 154)
            ball_r = max(3.0, 16.0 / float(Z[0]))
            # domain weight: structure (warm) ↔ flow (cool); loud/quiet scale the event
            dom = float(st.get("domain", 0.5))
            if st.get("loud"):
                ball_col = (255, 180, 80)
                ball_r *= 1.35
            elif st.get("quiet"):
                ball_col = (140, 180, 255)
                ball_r *= 0.7
            # tint by domain (1 = structure / warm, 0 = flow / cool)
            ball_col = tuple(int(c * (0.65 + 0.35 * dom) + (255 - c) * (1.0 - dom) * 0.25) for c in ball_col)
            _disc(img, S[0][0], S[0][1], ball_r, ball_col, a)
            # domain ring
            if abs(dom - 0.5) > 0.05:
                ring_r = ball_r * (1.4 + 0.6 * abs(dom - 0.5))
                _disc(img, S[0][0], S[0][1], ring_r, (255 * dom, 200, 255 * (1 - dom)), 0.35 * a)
        # the vector beam
        v = np.asarray(st["vector"], dtype=np.float64)
        nv = float(np.linalg.norm(v))
        if nv > 0:
            S, _z, ok = _project([[0, 0, 0], (0.9 / nv) * v], yaw, pitch, 4.2, cx, cy, f)
            if ok.all():
                _line(img, S[0], S[1], (125, 211, 252), a, 2.2)
    return img


# ---------------------------------------------------------------------------- game
def entities(states, t):
    """The same worlds as game objects (positions in a unit cube per programme, programme i offset
    along x by 3 units). Deterministic in t."""
    out = []
    for i, st in enumerate(states or []):
        ox = 3.0 * i
        row = st["ca"][-1] if len(st["ca"]) else []
        for c in np.flatnonzero(row):
            out.append({"kind": "platform", "pos": (ox - 0.9 + 1.8 * c / (md.H - 1), 0.85, 0.0), "slot": st["slot"]})
        out.append({"kind": "bouncer", "pos": (ox, -1.0 + 1.8 * st["ball"], 0.0), "height": st["ball"],
                     "domain": float(st.get("domain", 0.5)), "loud": bool(st.get("loud", False)),
                     "quiet": bool(st.get("quiet", False)), "amp": float(st.get("amp", 0.0)), "slot": st["slot"]})
        out.append({"kind": "wind", "dir": tuple(float(x) for x in st["vector"]), "origin": (ox, 0.0, 0.0), "slot": st["slot"]})
        for j, amp in enumerate(st["amps"]):
            ang = math.tau * j / md.H
            out.append({"kind": "pillar", "pos": (ox + 0.95 * math.cos(ang), -1.0, 0.95 * math.sin(ang)),
                        "height": 1.6 * abs(float(amp)), "partial": j + 1, "slot": st["slot"]})
        rs = st["resonators"]
        if rs:
            rmax = max(rs)
            for r in rs:
                yy = -1.0 + 2.0 * (math.log(r) / math.log(rmax) if rmax > 1 else 0.5)
                out.append({"kind": "portal", "pos": (ox, yy, 0.0), "radius": 1.1, "ratio": float(r), "slot": st["slot"]})
        out.append({"kind": "pulse", "value": float(st.get("domain", st.get("live", 0.0))), "live": float(st.get("live", 0.0)), "slot": st["slot"]})
    return out


def host_clock(host):
    """(render sample rate, playlist row duration) — exactly what the render uses."""
    try:
        sr = int(getattr(host, "preferred_sample_rate", 0) or 0) or 48000
        sr = max(44100, min(192000, sr))
    except Exception:
        sr = 48000
    try:
        bpm = float(host.spin_bpm.value())
    except Exception:
        bpm = 120.0
    beats = 4.0
    for attr in ("spin_row_beats", "spin_playlist_beats"):
        w = getattr(host, attr, None)
        if w is not None:
            try:
                beats = float(w.value()); break
            except Exception:
                pass
    beats = max(0.25, min(64.0, beats))
    return float(sr), ((60.0 / bpm) * beats if bpm > 0 else 2.0)


def states_for_host(host, t, max_programmes=4):
    """state() for the instruments that currently play (selected first), on the render's clock."""
    names = list(getattr(host, "instrument_names_48", []) or [])
    try:
        sel = host.instrument_selector_dropdown.currentText()
    except Exception:
        sel = names[0] if names else ""
    mem = getattr(host, "instrument_sequencer_memory", {}) or {}
    playing = [n for n in names if any((mem.get(n) or {}).get("steps") or [])]
    order = [sel] + [n for n in playing if n != sel]
    out = []
    for n in order[:max_programmes]:
        if not n:
            continue
        try:
            slot = host._instance_slot(n)
            p, seed_int = host._md_params(n, slot)
            sr, row_dur = host_clock(host)
            out.append(state(p, seed_int, slot, t, sr=sr, row_dur=row_dur))
        except Exception:
            continue
    return out
