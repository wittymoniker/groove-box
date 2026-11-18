"""seed_atlas.py — the SEED ATLAS: a bounded, deterministic fractal of the ways numbers / logic in a seed become media.

Address   seed ▸ reading ▸ domain ▸ method [▸ reading ▸ domain ▸ method …]   e.g.  "value/sound/fm/orbit/image/julia"
          Every node is reproducible from (seed text, address): the same address always renders the same media.
Readings  how the seed is read as numbers before any medium is chosen
          value   the evaluated seed program's numbers (what the composer uses)
          text    the seed's characters / bytes (any text is a seed)
          orbit   the seed program evaluated over time t ∈ [0, 1) — its trajectory
          digits  the decimal digits of the evaluated value (number theory reading)
Domains × methods (each is a small, exact numerical construction; all are NumPy)
          sound   additive · fm · karplus (plucked string) · granular · orbit (logistic / Mandelbrot orbit as a wave) ·
                  ca-rhythm (elementary cellular automaton as a beat) · lsystem (L-system melody)
          image   mandelbrot · julia · ifs (iterated-function fractal) · ca (automaton space-time) · lsystem (turtle) ·
                  spectrogram (of this node's sound sibling: cross-domain)
          game    maze (seeded depth-first) · terrain (diamond-square heightmap) · cave (CA level) · chart (rhythm-game
                  chart from the CA rhythm) · platformer (L-system level)
          shape   torus-knot · terrain-mesh · lsystem-tree (OBJ meshes)
          app     any external app / script from the Apps & scripts hub, given this node's seed as GROOVEBOX_SEED
Fractal   every node's parameters are read from a child seed = H(parent seed, address), so a child node is the same
          construction one level down, read through its parent: the tree is self-similar and unbounded in principle.
Limit     depth ≤ max_depth (default 4), media bounded (sound 4 s at 22.05 kHz, images 256×256, levels 48×32, meshes ≤
          4096 vertices) and the tree is expanded lazily, so it never grows past what you open.
"""
from __future__ import annotations

import hashlib, json, math, os, struct, time
import numpy as np

READINGS = ("value", "text", "orbit", "digits")
DOMAINS = {
    "sound": ("additive", "fm", "karplus", "granular", "orbit", "ca-rhythm", "lsystem"),
    "image": ("mandelbrot", "julia", "ifs", "ca", "lsystem", "spectrogram"),
    "game": ("maze", "terrain", "cave", "chart", "platformer"),
    "shape": ("torus-knot", "terrain-mesh", "lsystem-tree"),
    "app": ("external",),
}
SR = 22050
MAX_DEPTH = 4


# ---------------------------------------------------------------- seed reading
def _h(*parts):
    return hashlib.blake2b("|".join(str(p) for p in parts).encode("utf-8", "replace"), digest_size=32).digest()


def child_seed(seed, address):
    return _h("atlas", seed, address).hex()[:24]


def _eval(seed_text, t=0.0):
    try:
        import groovebox as gb
        return [float(v) for v in (gb._eval_seed_python(seed_text, t_value=t, allow_scrape=False) or [])]
    except Exception:
        return []


def read(seed_text, reading, n=32):
    """n floats in [0, 1) from the seed, through one reading."""
    if reading == "value":
        v = _eval(seed_text) or [int.from_bytes(_h(seed_text)[:8], "big") / 2 ** 64]
        out = [(abs(x) * 0.6180339887 + i * 0.4142135) % 1.0 for i, x in enumerate((v * (n // max(1, len(v)) + 1))[:n])]
    elif reading == "orbit":
        out = []
        for i in range(n):
            v = _eval(seed_text, t=i / float(n))
            out.append((abs(v[0]) * 0.6180339887) % 1.0 if v else (i * 0.6180339887) % 1.0)
    elif reading == "digits":
        v = _eval(seed_text)
        s = "".join(c for c in ("%.17g" % (v[0] if v else 0.0)) if c.isdigit()) or "0"
        s = (s * (n // len(s) + 2))[:n + 1]
        out = [(int(s[i]) * 10 + int(s[i + 1])) / 100.0 for i in range(n)]
    else:   # text
        b = b"".join(_h(seed_text, k) for k in range(n // 32 + 1))
        out = [b[i] / 256.0 + b[i + 1] / 65536.0 for i in range(n)]
    lo = [min(0.999999, max(0.0, float(x))) for x in out]
    return np.array(lo, dtype=np.float64)


def parse(address):
    parts = [p for p in str(address).strip("/").split("/") if p]
    nodes = []
    for i in range(0, len(parts) - 2, 3):
        r, d, m = parts[i:i + 3]
        if r in READINGS and d in DOMAINS and m in DOMAINS[d]:
            nodes.append((r, d, m))
    return nodes


def node_seed(seed, address):
    """The seed a node is rendered from: the root seed for depth 1, a child seed one level further down."""
    nodes = parse(address); s = seed
    for k in range(1, len(nodes)):
        s = child_seed(s, "/".join("/".join(n) for n in nodes[:k]))
    return s


# ---------------------------------------------------------------- sound
def _norm(y):
    y = np.nan_to_num(np.asarray(y, dtype=np.float64)); p = float(np.max(np.abs(y))) or 1.0
    return (0.89 * y / p).astype(np.float32)


def sound(method, p, dur=4.0):
    n = int(SR * dur); t = np.arange(n) / SR
    f0 = 55.0 * 2 ** (p[0] * 4)
    env = np.minimum(1, t / 0.01) * np.exp(-t * (0.3 + 3 * p[1]))
    if method == "additive":
        y = sum((p[2 + k] ** 1.5) / (k + 1) * np.sin(2 * np.pi * f0 * (k + 1) * (1 + 0.002 * p[10 + k] * k) * t) for k in range(8))
        return _norm(y * env)
    if method == "fm":
        ratio = 0.5 + round(p[2] * 7) / 2; idx = 8 * p[3] * np.exp(-t * p[4] * 2)
        return _norm(np.sin(2 * np.pi * f0 * t + idx * np.sin(2 * np.pi * f0 * ratio * t)) * env)
    if method == "karplus":
        y = np.zeros(n); per = max(2, int(SR / f0)); rng = np.random.default_rng(int(p[5] * 1e9))
        buf = rng.uniform(-1, 1, per); damp = 0.990 + 0.0095 * p[6]; step = int(SR * (0.15 + 0.5 * p[7]))
        for s0 in range(0, n, step):
            b = buf.copy()
            for i in range(s0, min(n, s0 + step)):
                j = (i - s0) % per; y[i] = b[j]; b[j] = damp * 0.5 * (b[j] + b[(j + 1) % per])
        return _norm(y)
    if method == "granular":
        rng = np.random.default_rng(int(p[8] * 1e9)); y = np.zeros(n); g = int(SR * (0.01 + 0.08 * p[9]))
        win = np.hanning(g); dens = int(40 + 400 * p[2])
        for _ in range(dens):
            s0 = int(rng.uniform(0, n - g)); f = f0 * 2 ** rng.integers(0, 4) * (1 + 0.03 * rng.standard_normal())
            y[s0:s0 + g] += win * np.sin(2 * np.pi * f * np.arange(g) / SR + rng.uniform(0, 6.28))
        return _norm(y)
    if method == "orbit":
        r = 3.57 + 0.43 * p[2]; x = 0.1 + 0.8 * p[3]; per = max(8, int(SR / f0)); cyc = np.empty(per)
        for i in range(per):
            x = r * x * (1 - x); cyc[i] = x
        cyc -= cyc.mean()
        return _norm(np.tile(cyc, n // per + 1)[:n] * env)
    if method == "ca-rhythm":
        rule = int(p[2] * 256) & 255; w = 16; row = (np.arange(w) == w // 2).astype(int); hits = []
        for _ in range(16):
            hits.append(row.copy()); idx = (np.roll(row, 1) << 2) | (row << 1) | np.roll(row, -1); row = (rule >> idx) & 1
        y = np.zeros(n); step = n // 64
        for k in range(64):
            on = hits[k % 16][k % w] or hits[(k + 3) % 16][(k * 5) % w]
            if on:
                m = min(step * 2, n - k * step); tt = np.arange(m) / SR
                y[k * step:k * step + m] += np.sin(2 * np.pi * (f0 * (1 + (k % 4))) * tt) * np.exp(-tt * 30) if k % 3 else \
                    np.random.default_rng(k).uniform(-1, 1, m) * np.exp(-tt * 60)
        return _norm(y)
    if method == "lsystem":
        word = _lsystem(p, 4)[:64] or "F"; y = np.zeros(n); step = n // len(word); deg = 0
        scale = [0, 2, 4, 5, 7, 9, 11]
        for k, c in enumerate(word):
            if c == "+": deg += 1
            elif c == "-": deg -= 1
            elif c == "F":
                hz = f0 * 2 ** ((scale[deg % 7] + 12 * (deg // 7)) / 12.0); m = min(step, n - k * step); tt = np.arange(m) / SR
                y[k * step:k * step + m] += np.sin(2 * np.pi * hz * tt) * np.minimum(1, tt / 0.005) * np.exp(-tt * 6)
        return _norm(y)
    return np.zeros(n, dtype=np.float32)


def _lsystem(p, iters):
    rules = ["F+F-F", "FF-[-F+F]+[+F-F]", "F[+F]F[-F]F", "F-F++F-F", "F+F--F+F"]
    rule = rules[int(p[11] * len(rules)) % len(rules)]
    w = "F"
    for _ in range(iters):
        w = "".join(rule if c == "F" else c for c in w)
        if len(w) > 4000: break
    return w


# ---------------------------------------------------------------- image
def image(method, p, N=256, sib_sound=None):
    if method in ("mandelbrot", "julia"):
        ys, xs = np.mgrid[-1.4:1.4:N * 1j, -2.0:1.0:N * 1j] if method == "mandelbrot" else np.mgrid[-1.5:1.5:N * 1j, -1.5:1.5:N * 1j]
        zoom = 1.0 / (1 + 6 * p[4] ** 2); cx, cy = (-0.75 + 0.5 * (p[5] - 0.5), 0.3 * (p[6] - 0.5)) if method == "mandelbrot" else (0, 0)
        z = (xs * zoom + cx) + 1j * (ys * zoom + cy)
        c = z.copy() if method == "mandelbrot" else complex(-0.8 + 1.6 * p[2], -0.8 + 1.6 * p[3])
        it = np.zeros(z.shape); m = np.ones(z.shape, bool)
        for k in range(64):
            z[m] = z[m] ** 2 + (c[m] if method == "mandelbrot" else c); esc = np.abs(z) > 2; it[m & esc] = k; m &= ~esc
        v = it / 64.0
    elif method == "ifs":
        rng = np.random.default_rng(int(p[7] * 1e9)); maps = [(p[i % 32] * 1.2 - 0.6, p[(i + 1) % 32] - 0.5, p[(i + 2) % 32] - 0.5, p[(i + 3) % 32] * 1.2 - 0.6,
                                                            p[(i + 4) % 32] - 0.5, p[(i + 5) % 32] - 0.5) for i in range(0, 12, 4)]
        x = y = 0.0; v = np.zeros((N, N)); pts = []
        for k in range(60000):
            a, b, c2, d, e, f = maps[rng.integers(0, len(maps))]
            k_ = 0.8 / max(0.8, abs(a) + abs(b), abs(c2) + abs(d))      # contractive: the attractor always exists
            x, y = k_ * (a * x + b * y) + e, k_ * (c2 * x + d * y) + f
            if k > 20: pts.append((x, y))
        pts = np.array(pts); pts = pts[np.all(np.isfinite(pts), axis=1)]
        pts = (pts - pts.min(0)) / (np.ptp(pts, 0) + 1e-9) * (N - 1)
        np.add.at(v, (pts[:, 1].astype(int), pts[:, 0].astype(int)), 1); v = np.log1p(v); v /= v.max() or 1
    elif method == "ca":
        rule = int(p[2] * 256) & 255; row = np.zeros(N, int); row[N // 2] = 1; v = np.zeros((N, N))
        for i in range(N):
            v[i] = row; idx = (np.roll(row, 1) << 2) | (row << 1) | np.roll(row, -1); row = (rule >> idx) & 1
    elif method == "lsystem":
        v = np.zeros((N, N)); x, y, a = N / 2, N - 4.0, -math.pi / 2; st = []; ang = 0.3 + 0.6 * p[3]; L = 2 + 3 * p[4]
        for ch in _lsystem(p, 4)[:20000]:
            if ch == "F":
                nx, ny = x + L * math.cos(a), y + L * math.sin(a)
                for s in np.linspace(0, 1, 4):
                    xi, yi = int(x + (nx - x) * s), int(y + (ny - y) * s)
                    if 0 <= xi < N and 0 <= yi < N: v[yi, xi] = 1
                x, y = nx, ny
            elif ch == "+": a += ang
            elif ch == "-": a -= ang
            elif ch == "[": st.append((x, y, a))
            elif ch == "]" and st: x, y, a = st.pop()
    else:   # spectrogram of the sibling sound
        s = sib_sound if sib_sound is not None else sound("fm", p)
        hop = max(1, len(s) // N); fr = [np.abs(np.fft.rfft(s[i:i + 512] * np.hanning(512)))[:N] for i in range(0, len(s) - 512, hop)][:N]
        v = np.log1p(np.array(fr).T[::-1]); v /= v.max() or 1
        if v.shape != (N, N):
            out = np.zeros((N, N)); out[:v.shape[0], :v.shape[1]] = v[:N, :N]; v = out
    hue = p[9]
    rgb = np.stack([np.clip(np.sin(2 * np.pi * (v * 0.9 + hue + o)) * 0.5 + 0.5, 0, 1) * (v > 0) for o in (0.0, 0.33, 0.66)], -1)
    return (rgb * 255).astype(np.uint8)


# ---------------------------------------------------------------- game
def game(method, p, W=48, H=32):
    rng = np.random.default_rng(int(p[12] * 1e9))
    if method == "maze":
        g = np.ones((H, W), int); stack = [(1, 1)]; g[1, 1] = 0
        while stack:
            y, x = stack[-1]; nb = [(y + dy, x + dx, dy, dx) for dy, dx in ((0, 2), (2, 0), (0, -2), (-2, 0))
                                    if 0 < y + dy < H - 1 and 0 < x + dx < W - 1 and g[y + dy, x + dx]]
            if not nb: stack.pop(); continue
            ny, nx, dy, dx = nb[rng.integers(0, len(nb))]; g[y + dy // 2, x + dx // 2] = 0; g[ny, nx] = 0; stack.append((ny, nx))
        return {"kind": "maze", "grid": g.tolist(), "start": [1, 1], "goal": [H - 2 - (H % 2 == 0), W - 2 - (W % 2 == 0)]}
    if method == "terrain":
        n = 33; h = np.zeros((n, n)); h[0, 0], h[0, -1], h[-1, 0], h[-1, -1] = p[13:17]; s = n - 1; r = 0.5 + 0.4 * p[17]
        while s > 1:
            hs = s // 2
            for y in range(hs, n, s):
                for x in range(hs, n, s):
                    h[y, x] = (h[y - hs, x - hs] + h[y - hs, x + hs] + h[y + hs, x - hs] + h[y + hs, x + hs]) / 4 + rng.uniform(-r, r)
            for y in range(0, n, hs):
                for x in range((y + hs) % s, n, s):
                    vals = [h[yy, xx] for yy, xx in ((y - hs, x), (y + hs, x), (y, x - hs), (y, x + hs)) if 0 <= yy < n and 0 <= xx < n]
                    h[y, x] = sum(vals) / len(vals) + rng.uniform(-r, r)
            s = hs; r *= 0.5 + 0.2 * p[18]
        h = (h - h.min()) / (np.ptp(h) or 1)
        return {"kind": "terrain", "height": np.round(h, 4).tolist(), "water": round(float(0.25 + 0.3 * p[19]), 3)}
    if method == "cave":
        g = (rng.random((H, W)) < 0.42 + 0.1 * p[13]).astype(int)
        for _ in range(5):
            nb = sum(np.roll(np.roll(g, dy, 0), dx, 1) for dy in (-1, 0, 1) for dx in (-1, 0, 1)) - g; g = ((nb >= 5) | ((g == 1) & (nb >= 4))).astype(int)
        g[0, :] = g[-1, :] = g[:, 0] = g[:, -1] = 1
        return {"kind": "cave", "grid": g.tolist()}
    if method == "chart":
        rule = int(p[2] * 256) & 255; row = np.zeros(8, int); row[3] = 1; notes = []
        for beat in range(128):
            for lane in range(4):
                if row[(lane * 2 + beat) % 8]: notes.append({"beat": beat / 2.0, "lane": lane})
            idx = (np.roll(row, 1) << 2) | (row << 1) | np.roll(row, -1); row = (rule >> idx) & 1
        return {"kind": "rhythm-chart", "bpm": int(80 + 100 * p[20]), "notes": notes}
    word = _lsystem(p, 3)[:W * 2]; plats = []; x = 0; y = H // 2
    for c in word:
        if c == "F": plats.append([x, y]); x += 1
        elif c == "+": y = max(2, y - 1)
        elif c == "-": y = min(H - 2, y + 1)
        elif c == "[": x += 2
    return {"kind": "platformer", "platforms": plats[:W * 4], "width": max(W, x + 2), "height": H}


# ---------------------------------------------------------------- shape (OBJ text)
def shape(method, p):
    V, F = [], []
    if method == "torus-knot":
        P, Q = 2 + int(p[2] * 4), 3 + int(p[3] * 5); seg, ring, r = 256, 8, 0.12
        for i in range(seg):
            u = 2 * math.pi * i / seg
            c = np.array([(2 + math.cos(Q * u)) * math.cos(P * u), (2 + math.cos(Q * u)) * math.sin(P * u), math.sin(Q * u)])
            for j in range(ring):
                a = 2 * math.pi * j / ring; V.append(c + r * np.array([math.cos(a), math.sin(a), 0.5 * math.cos(a)]))
        for i in range(seg):
            for j in range(ring):
                a, b = i * ring + j, ((i + 1) % seg) * ring + j; F.append((a, b, ((i + 1) % seg) * ring + (j + 1) % ring, i * ring + (j + 1) % ring))
    elif method == "terrain-mesh":
        h = np.array(game("terrain", p)["height"]); n = h.shape[0]
        for y in range(n):
            for x in range(n): V.append((x / n * 4 - 2, h[y, x] * (0.5 + p[4]), y / n * 4 - 2))
        for y in range(n - 1):
            for x in range(n - 1): F.append((y * n + x, y * n + x + 1, (y + 1) * n + x + 1, (y + 1) * n + x))
    else:
        x = np.zeros(3); a = 0.0; st = []; ang = 0.3 + 0.6 * p[3]
        for ch in _lsystem(p, 3)[:3000]:
            if ch == "F":
                nx = x + np.array([math.sin(a) * 0.1, 0.12, math.cos(a) * 0.1 * p[5]]); V += [x, nx]; F.append((len(V) - 2, len(V) - 1)); x = nx
            elif ch == "+": a += ang
            elif ch == "-": a -= ang
            elif ch == "[": st.append((x.copy(), a))
            elif ch == "]" and st: x, a = st.pop()
    lines = ["# Groovebox seed atlas · %s" % method] + ["v %.5f %.5f %.5f" % tuple(v) for v in V[:4096]]
    for f in F:
        if max(f) < min(len(V), 4096):
            lines.append(("l " if len(f) == 2 else "f ") + " ".join(str(i + 1) for i in f))
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- render a node
def render(seed, address):
    """{'domain', 'method', 'seed', 'data'} for the node at address (the deepest triple decides the medium)."""
    nodes = parse(address)
    if not nodes:
        raise ValueError("address must be reading/domain/method[/…], e.g. value/sound/fm")
    if len(nodes) > MAX_DEPTH:
        raise ValueError("deeper than the atlas limit (%d levels)" % MAX_DEPTH)
    s = node_seed(seed, address); r, d, m = nodes[-1]
    p = read(s, r)
    if d == "sound": data = sound(m, p)
    elif d == "image": data = image(m, p, sib_sound=sound("fm", p) if m == "spectrogram" else None)
    elif d == "game": data = game(m, p)
    elif d == "shape": data = shape(m, p)
    else: data = {"seed": s, "address": address}
    return {"domain": d, "method": m, "seed": s, "params": [round(float(x), 6) for x in p[:12]], "data": data, "address": address}


def children(address):
    """Every child address one level down (lazy: only computed when a node is opened)."""
    if len(parse(address)) >= MAX_DEPTH:
        return []
    return ["%s/%s/%s/%s" % (address.strip("/"), r, d, m) if address else "%s/%s/%s" % (r, d, m)
            for r in READINGS for d, ms in DOMAINS.items() for m in ms]


def save(node, folder):
    os.makedirs(folder, exist_ok=True)
    base = os.path.join(folder, "atlas-%s-%s-%s" % (node["domain"], node["method"], node["seed"][:8]))
    d = node["data"]
    if node["domain"] == "sound":
        import wave
        with wave.open(base + ".wav", "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((np.clip(d, -1, 1) * 32767).astype("<i2").tobytes())
        return base + ".wav"
    if node["domain"] == "image":
        from PyQt6.QtGui import QImage
        h, w = d.shape[:2]; QImage(np.ascontiguousarray(d).data, w, h, 3 * w, QImage.Format.Format_RGB888).copy().save(base + ".png"); return base + ".png"
    if node["domain"] == "shape":
        open(base + ".obj", "w").write(d); return base + ".obj"
    __import__("safe_io").atomic_write_json(base + ".json", d); return base + ".json"


# ---------------------------------------------------------------- window
def open_window(app):
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QImage, QPixmap
    from PyQt6.QtWidgets import (QDialog, QHBoxLayout, QVBoxLayout, QTreeWidget, QTreeWidgetItem, QLabel, QPushButton, QLineEdit,
                                 QPlainTextEdit, QSplitter, QWidget, QComboBox)
    d = QDialog(app); d.setWindowTitle("🌌 Seed Atlas · every way a seed becomes media"); d.resize(1180, 720)
    d.setWindowModality(Qt.WindowModality.NonModal)
    lay = QVBoxLayout(d)
    top = QHBoxLayout(); lay.addLayout(top)
    seed_box = QLineEdit(app._seed_text() if hasattr(app, "_seed_text") else "1"); top.addWidget(QLabel("Seed")); top.addWidget(seed_box, 1)
    addr = QLineEdit("value/sound/fm"); top.addWidget(QLabel("Address")); top.addWidget(addr, 1)
    b_go = QPushButton("Render"); top.addWidget(b_go)
    split = QSplitter(); lay.addWidget(split, 1)
    tree = QTreeWidget(); tree.setHeaderLabel("reading ▸ domain ▸ method (open a node to go one level down)"); split.addWidget(tree)
    right = QWidget(); rl = QVBoxLayout(right); split.addWidget(right); split.setSizes([420, 760])
    view = QLabel("Pick a node."); view.setMinimumSize(380, 300); view.setAlignment(Qt.AlignmentFlag.AlignCenter); rl.addWidget(view, 1)
    info = QPlainTextEdit(); info.setReadOnly(True); info.setMaximumHeight(140); rl.addWidget(info)
    row = QHBoxLayout(); rl.addLayout(row)
    b_play = QPushButton("▶ Play"); b_save = QPushButton("💾 Save"); b_use = QPushButton("⇢ Use in project"); b_seed = QPushButton("🌱 Child seed → Global Seed")
    apps = QComboBox(); b_app = QPushButton("🧩 Send to app")
    for w in (b_play, b_save, b_use, b_seed, apps, b_app): row.addWidget(w)
    row2 = QHBoxLayout(); rl.addLayout(row2)
    b_inst = QPushButton("🎹 Node sound → selected instrument's voice"); b_vid = QPushButton("🎬 Music video from this image node")
    b_game = QPushButton("🎮 Play this game node"); b_hear = QPushButton("🔊 Hear any node (its paired sonification)")
    for w in (b_inst, b_vid, b_game, b_hear): row2.addWidget(w)
    try:
        import app_hub
        for a in app_hub.list_apps()[:200]: apps.addItem(a.get("name", "?"), a)
    except Exception:
        pass
    cur = {"node": None, "path": None}

    def add_children(item, address):
        if item.childCount() or len(parse(address)) >= MAX_DEPTH: return
        by = {}
        for ch in children(address):
            r, dd, m = ch.split("/")[-3:]
            rk = by.get(r)
            if rk is None:
                rk = by[r] = QTreeWidgetItem([r]); item.addChild(rk) if item is not None else tree.addTopLevelItem(rk); rk._dom = {}
            dk = rk._dom.get(dd)
            if dk is None:
                dk = rk._dom[dd] = QTreeWidgetItem([dd]); rk.addChild(dk)
            leaf = QTreeWidgetItem([m]); leaf.setData(0, Qt.ItemDataRole.UserRole, ch); leaf.addChild(QTreeWidgetItem(["…"])); dk.addChild(leaf)
    root = QTreeWidgetItem(["seed"]); tree.addTopLevelItem(root); add_children(root, ""); root.setExpanded(True)

    def expanded(item):
        a = item.data(0, Qt.ItemDataRole.UserRole)
        if a and item.childCount() == 1 and item.child(0).text(0) == "…":
            item.takeChild(0); add_children(item, a)
    tree.itemExpanded.connect(expanded)

    def show(address):
        try:
            node = render(seed_box.text(), address)
        except Exception as exc:
            info.setPlainText("⚠ %s" % exc); return
        cur["node"] = node; cur["path"] = None; addr.setText(address)
        dd = node["data"]
        if node["domain"] == "image":
            h, w = dd.shape[:2]; img = QImage(np.ascontiguousarray(dd).data, w, h, 3 * w, QImage.Format.Format_RGB888).copy()
            view.setPixmap(QPixmap.fromImage(img).scaled(view.size(), Qt.AspectRatioMode.KeepAspectRatio))
        elif node["domain"] == "sound":
            wav = dd[::max(1, len(dd) // 380)]; img = QImage(len(wav), 160, QImage.Format.Format_RGB888); img.fill(0x0b1622)
            from PyQt6.QtGui import QPainter, QColor
            pnt = QPainter(img); pnt.setPen(QColor("#7fe0ff"))
            for i, v in enumerate(wav): pnt.drawLine(i, 80, i, int(80 - 75 * float(v)))
            pnt.end(); view.setPixmap(QPixmap.fromImage(img).scaled(view.size(), Qt.AspectRatioMode.KeepAspectRatio))
        elif node["domain"] == "game" and "grid" in dd:
            g = np.array(dd["grid"], dtype=np.uint8); rgb = np.stack([g * 30 + 10, g * 60 + 20, g * 90 + 30], -1).astype(np.uint8)
            rgb = np.repeat(np.repeat(rgb, 8, 0), 8, 1); h, w = rgb.shape[:2]
            view.setPixmap(QPixmap.fromImage(QImage(np.ascontiguousarray(rgb).data, w, h, 3 * w, QImage.Format.Format_RGB888).copy()))
        else:
            view.setText(str(dd)[:1200] if node["domain"] != "shape" else "OBJ mesh · %d lines (Save / Use in project → 3D video)" % dd.count("\n"))
        info.setPlainText("address  %s\nnode seed %s\nreading → params %s\n%s" % (address, node["seed"], node["params"],
                          "child seeds are H(parent, address): open the node to go one level down (limit %d)" % MAX_DEPTH))

    tree.itemClicked.connect(lambda it, _c: it.data(0, Qt.ItemDataRole.UserRole) and show(it.data(0, Qt.ItemDataRole.UserRole)))
    b_go.clicked.connect(lambda: show(addr.text()))

    def ensure_saved():
        if cur["path"] is None and cur["node"] is not None:
            cur["path"] = save(cur["node"], os.path.join(str(app._exports_dir()), "seed-atlas"))
        return cur["path"]

    def play():
        n = cur["node"]
        if n and n["domain"] == "sound":
            try:
                import sounddevice as sd; sd.play(n["data"], SR)
            except Exception as exc:
                info.appendPlainText("playback: %s" % exc)

    def use():
        n = cur["node"]; p = ensure_saved()
        if not n: return
        try:
            if n["domain"] == "sound":
                app._load_wav_path(p); info.appendPlainText("→ global carrier")
            elif n["domain"] == "image":
                import compat_settings as cs; cs.update(window_background_image=p); info.appendPlainText("→ window background")
            elif n["domain"] == "shape":
                app.video_obj_path = p; app.video_obj_paths = [p] + list(getattr(app, "video_obj_paths", None) or [])[:12]; info.appendPlainText("→ video OBJ centrepiece")
            elif n["domain"] == "game":
                info.appendPlainText("level saved: %s (Features ▸ Games exports a standalone game)" % p)
        except Exception as exc:
            info.appendPlainText("⚠ %s" % exc)

    def to_seed():
        n = cur["node"]
        if n and hasattr(app, "input_seed_val"):
            try: app._push_undo("Seed Atlas child seed")
            except Exception: pass
            app.input_seed_val.setPlainText(n["seed"]); info.appendPlainText("Global Seed ← " + n["seed"])

    def to_app():
        n = cur["node"]; a = apps.currentData()
        if not n or not a: return
        p = ensure_saved()
        try:
            import app_hub
            env = dict(os.environ); env.update(app_hub.script_env(app, os.path.dirname(p or os.path.expanduser("~"))))
            env.update(GROOVEBOX_SEED=n["seed"], GROOVEBOX_ATLAS_ADDRESS=addr.text(), GROOVEBOX_ATLAS_FILE=p or "")
            import subprocess
            argv = app_hub._clean_exec(a["exec"]) + ([p] if p else [])
            import app_limits
            app_limits.popen(argv, env=env, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            info.appendPlainText("sent to %s" % a.get("name"))
        except Exception as exc:
            info.appendPlainText("⚠ %s" % exc)
    def to_inst():
        n = cur["node"]
        if not n: return
        try:
            app._push_undo("Seed Atlas voice")
        except Exception:
            pass
        name = app._current_instrument_name()
        y = node_sound(seed_box.text(), addr.text(), dur=6.0, sr=48000)
        prev = (getattr(app, "instrument_media_samples", {}) or {}).get(name, {}) or {}
        app.instrument_media_samples[name] = {**prev, "path": "atlas://" + addr.text(), "sample_rate": 48000, "waveform": y,
                                              "user_owned": True, "source_kind": "audio"}
        app._shared_mixdown_cache = {}
        try: app._on_live_source_changed()
        except Exception: pass
        info.appendPlainText("→ %s now layers the node's sound (the voice keeps its pitch and sequence)" % name)

    def to_video():
        n = cur["node"]
        if not n or n["domain"] != "image":
            info.appendPlainText("pick an image node"); return
        out = os.path.join(str(app._exports_dir()), "seed-atlas", "atlas-video-%s.MCC" % n["seed"][:8])
        os.makedirs(os.path.dirname(out), exist_ok=True)
        import threading
        info.appendPlainText("rendering 12 s music video in the background…")

        def run():
            try:
                animate(seed_box.text(), addr.text(), out)
                info.appendPlainText("music video: " + out)
            except Exception as exc:
                info.appendPlainText("⚠ video: %s" % exc)
        threading.Thread(target=run, name="atlas-video", daemon=True).start()

    def hear():
        try:
            import sounddevice as sd; sd.play(node_sound(seed_box.text(), addr.text()), SR)
        except Exception as exc:
            info.appendPlainText("playback: %s" % exc)
    b_inst.clicked.connect(to_inst); b_vid.clicked.connect(to_video); b_hear.clicked.connect(hear)
    b_game.clicked.connect(lambda: cur["node"] and cur["node"]["domain"] == "game" and open_game(app, cur["node"]))
    b_play.clicked.connect(play); b_save.clicked.connect(lambda: info.appendPlainText("saved " + str(ensure_saved())))
    b_use.clicked.connect(use); b_seed.clicked.connect(to_seed); b_app.clicked.connect(to_app)
    d.show(); app._seed_atlas = d
    return d


# ================================================================ R99 engines: the atlas drives sound, video and games
SOUND_FOR = {"mandelbrot": "orbit", "julia": "fm", "ifs": "granular", "ca": "ca-rhythm", "lsystem": "lsystem",
             "spectrogram": "fm", "maze": "karplus", "terrain": "additive", "cave": "granular", "chart": "ca-rhythm",
             "platformer": "lsystem", "torus-knot": "fm", "terrain-mesh": "additive", "lsystem-tree": "lsystem"}


def node_sound(seed, address, dur=4.0, sr=None):
    """The sound of any node: a sound node is itself; any other node is sonified by its paired method, read from
    the same node seed and reading — so every picture, level and shape has its own soundtrack."""
    global SR
    nodes = parse(address); r, d, m = nodes[-1]
    s = node_seed(seed, address); p = read(s, r)
    old = SR
    try:
        if sr: SR = int(sr)
        return sound(m if d == "sound" else SOUND_FOR.get(m, "fm"), p, dur)
    finally:
        SR = old


def animate(seed, address, out_path, seconds=12.0, fps=24, size=480, progress=None):
    """MUSIC VIDEO from any image node: the seed reading moves through time (child seed of the node at t), every
    frame is the same construction one step further, and the node's own sound is the audio track. Lossless .MCC."""
    import mcc_media as mm
    nodes = parse(address); r, d, m = nodes[-1]
    if d != "image":
        raise ValueError("animate an image node (reading/image/method)")
    s = node_seed(seed, address); p0 = read(s, r); p1 = read(child_seed(s, "motion"), r)
    n = int(seconds * fps)
    audio = node_sound(seed, address, dur=seconds, sr=44100)
    vw = mm.VideoWriter(out_path, size, size, fps, audio_rate=44100, audio_channels=1)
    for i in range(n):
        u = i / max(1, n - 1)
        p = p0 + (p1 - p0) * (0.5 - 0.5 * math.cos(math.pi * u))          # smooth path between two readings
        p = np.clip(p, 0, 0.999999)
        vw.write(image(m, p, N=size, sib_sound=audio[int(u * (len(audio) - 4096)):][:44100] if m == "spectrogram" else None))
        if progress and i % 12 == 0: progress(i / n)
    vw.write_audio(audio.astype(np.float32))
    vw.close()
    return out_path


def open_game(app, node):
    """Play a game node in a window: maze / cave (reach the goal), platformer (run and jump), rhythm chart
    (D F J K on the falling notes, with the node's own sound). Keys follow Features ▸ Games ▸ input mapping."""
    from PyQt6.QtCore import Qt, QTimer, QRectF
    from PyQt6.QtGui import QPainter, QColor
    from PyQt6.QtWidgets import QWidget
    data = node["data"]; kind = data.get("kind")
    try:
        import compat_settings as cs
        km = cs.load().get("game_input_map") or {}
    except Exception:
        km = {}
    keymap = {a: str(km.get(a, dflt)).lower() for a, dflt in (("left", "A"), ("right", "D"), ("up", "W"), ("down", "S"), ("jump", "Space"))}

    class G(QWidget):
        def __init__(self):
            super().__init__(None, Qt.WindowType.Window); self.setWindowTitle("🎮 Atlas game · %s" % kind); self.resize(860, 600)
            self.setFocusPolicy(Qt.FocusPolicy.StrongFocus); self.msg = ""; self.t0 = None; self.score = 0
            if kind in ("maze", "cave"):
                self.g = np.array(data["grid"]); free = np.argwhere(self.g == 0)
                self.pos = list(data.get("start") or free[0]); self.goal = list(data.get("goal") or free[-1])
            elif kind == "platformer":
                self.plats = {tuple(p) for p in data["platforms"]}; self.x, self.y, self.vy = 0.0, float(data["platforms"][0][1] - 1), 0.0
                self.W, self.H = data["width"], data["height"]
            elif kind == "rhythm-chart":
                self.notes = [dict(n) for n in data["notes"]]; self.bpm = data["bpm"]
                try:
                    import sounddevice as sd; sd.play(node_sound(app._seed_text(), node["address"], dur=min(60, 128 * 30 / self.bpm)), SR)
                except Exception:
                    pass
                import time as _t; self.t0 = _t.monotonic()
            self.timer = QTimer(self); self.timer.setInterval(16); self.timer.timeout.connect(self.step); self.timer.start()

        def _key(self, e):
            name = e.text().lower() or {Qt.Key.Key_Space: "space", Qt.Key.Key_Left: "a", Qt.Key.Key_Right: "d", Qt.Key.Key_Up: "w", Qt.Key.Key_Down: "s"}.get(e.key(), "")
            return next((a for a, k in keymap.items() if k == name), name)

        def keyPressEvent(self, e):
            a = self._key(e)
            if kind in ("maze", "cave"):
                dy, dx = {"up": (-1, 0), "down": (1, 0), "left": (0, -1), "right": (0, 1)}.get(a, (0, 0))
                ny, nx = self.pos[0] + dy, self.pos[1] + dx
                if 0 <= ny < self.g.shape[0] and 0 <= nx < self.g.shape[1] and self.g[ny, nx] == 0: self.pos = [ny, nx]
                if self.pos == self.goal: self.msg = "★ goal reached"
            elif kind == "platformer":
                if a == "left": self.x = max(0, self.x - 0.6)
                if a == "right": self.x += 0.6
                if a in ("jump", "up") and (int(round(self.x)), int(self.y + 1)) in self.plats: self.vy = -0.9
            elif kind == "rhythm-chart":
                lane = {"d": 0, "f": 1, "j": 2, "k": 3}.get(e.text().lower())
                if lane is not None:
                    import time as _t; beat = (_t.monotonic() - self.t0) * self.bpm / 60.0
                    for n in self.notes:
                        if n["lane"] == lane and not n.get("hit") and abs(n["beat"] - beat) < 0.25:
                            n["hit"] = True; self.score += 1; break
            self.update()

        def step(self):
            if kind == "platformer":
                self.vy = min(0.8, self.vy + 0.06); ny = self.y + self.vy
                if self.vy > 0 and (int(round(self.x)), int(ny + 1)) in self.plats: ny = float(int(ny)); self.vy = 0
                self.y = ny
                if self.y > self.H + 2: self.msg = "fell · restart"; self.x, self.y, self.vy = 0.0, 1.0, 0.0
                if self.x >= self.W - 2: self.msg = "★ level complete"
            self.update()

        def paintEvent(self, _e):
            p = QPainter(self); p.fillRect(self.rect(), QColor("#0a141e"))
            if kind in ("maze", "cave"):
                h, w = self.g.shape; c = min(self.width() / w, self.height() / h)
                for y in range(h):
                    for x in range(w):
                        if self.g[y, x]: p.fillRect(QRectF(x * c, y * c, c, c), QColor("#2a4a66"))
                p.fillRect(QRectF(self.goal[1] * c, self.goal[0] * c, c, c), QColor("#ffd166"))
                p.fillRect(QRectF(self.pos[1] * c, self.pos[0] * c, c, c), QColor("#5cf2b0"))
            elif kind == "platformer":
                c = min(self.width() / 40.0, self.height() / self.H); ox = max(0.0, self.x - 12)
                for (x, y) in self.plats:
                    if ox <= x <= ox + 40: p.fillRect(QRectF((x - ox) * c, y * c, c, c * 0.4), QColor("#4a8ab8"))
                p.fillRect(QRectF((self.x - ox) * c, self.y * c, c * 0.8, c), QColor("#5cf2b0"))
            elif kind == "rhythm-chart":
                import time as _t; beat = (_t.monotonic() - self.t0) * self.bpm / 60.0; lw = self.width() / 4
                p.fillRect(QRectF(0, self.height() - 60, self.width(), 4), QColor("#ffd166"))
                for n in self.notes:
                    y = self.height() - 60 - (n["beat"] - beat) * 120
                    if -20 < y < self.height() and not n.get("hit"):
                        p.fillRect(QRectF(n["lane"] * lw + 8, y - 10, lw - 16, 20), QColor.fromHsv(n["lane"] * 80, 180, 240))
                self.msg = "score %d / %d · keys D F J K" % (self.score, len(self.notes))
            p.setPen(QColor("#e8f7ff")); p.drawText(12, 22, self.msg or "arrows / mapped keys")
            p.end()
    w = G(); w.show(); w.setFocus(); app.__dict__.setdefault("_atlas_games", []).append(w)
    return w
