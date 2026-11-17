"""project_obj.py — R32.11: Project ⇄ OBJ, and OBJ meshes in the video.

Project → OBJ
    A normal Wavefront OBJ any 3D program opens: a tube whose rings follow the song's loudness envelope
    (one ring per slice of audio, radius = 0.25 + 0.75·RMS/peak), coloured by nothing — pure geometry. Inside it,
    as OBJ comments, it carries the exact song: the master audio (float32, zlib + base64, bit-exact) and the
    whole project document. So the file is both a 3D model of the song and a lossless container of it.

OBJ → audio / project  (reverse engineer)
    * A Groovebox OBJ gives back the exact audio and the project.
    * Any other OBJ is sonified: the vertices in file order become a waveform (y coordinate, 1 ms per vertex,
      linear in between), normalised to −1 dB. A model therefore always imports as sound.

OBJs in the video
    * Sample meshes (on by default): every video frame shows a small vase-like mesh built from that frame's
      own audio window, so there are 3D objects in the picture even when no OBJ is loaded.
    * A loaded OBJ (video_obj_path) is drawn large in the centre with a bright outline and a label, so it is
      unmistakable next to the sample meshes.
    Both are deterministic: they depend only on the audio window and the frame index.
"""
from __future__ import annotations

import base64
import json
import math
import os
import zlib

import numpy as np

MAGIC = "# groovebox-obj 1"
_CHUNK = 1 << 16
_LINE = 4096


# --------------------------------------------------------------------- meshes
def _mesh(v, t):
    v = np.asarray(v, dtype=np.float64)
    v -= (v.max(axis=0) + v.min(axis=0)) / 2.0
    r = float(np.max(np.linalg.norm(v, axis=1))) if len(v) else 0.0
    if r > 0:
        v /= r
    t = np.asarray(t, dtype=np.int64)
    uv = np.stack([0.5 + np.arctan2(v[:, 2], v[:, 0]) / (2 * math.pi),
                   0.5 + np.arcsin(np.clip(v[:, 1], -1, 1)) / math.pi], axis=1)
    return {"v": v, "t": t, "uv": uv, "tu": t.copy(), "texture": None}


def tube(radii, seg=12, height=2.0):
    """Closed-side tube: ring i at y = height·i/(n−1), radius radii[i]. Returns (vertices, triangles)."""
    radii = np.asarray(radii, dtype=np.float64).ravel()
    n = max(2, radii.size)
    if radii.size < 2:
        radii = np.full(2, float(radii[0]) if radii.size else 0.5)
    ang = np.linspace(0.0, 2 * math.pi, seg, endpoint=False)
    ys = np.linspace(-height / 2, height / 2, n)
    v = np.empty((n * seg, 3))
    for i in range(n):
        v[i * seg:(i + 1) * seg, 0] = radii[i] * np.cos(ang)
        v[i * seg:(i + 1) * seg, 1] = ys[i]
        v[i * seg:(i + 1) * seg, 2] = radii[i] * np.sin(ang)
    t = []
    for i in range(n - 1):
        for j in range(seg):
            a, b = i * seg + j, i * seg + (j + 1) % seg
            c, d = a + seg, b + seg
            t.append((a, c, b)); t.append((b, c, d))
    return v, np.asarray(t, dtype=np.int64)


def envelope_radii(y, rings):
    y = np.asarray(y, dtype=np.float64).ravel()
    if y.size == 0:
        return np.full(max(2, rings), 0.5)
    rings = max(2, min(int(rings), y.size))
    edges = np.linspace(0, y.size, rings + 1).astype(np.int64)
    rms = np.array([math.sqrt(float(np.mean(y[a:b] ** 2))) if b > a else 0.0 for a, b in zip(edges[:-1], edges[1:])])
    pk = float(rms.max()) or 1.0
    return 0.25 + 0.75 * rms / pk


def sample_mesh(wave, rings=16, seg=12):
    """A small mesh from one frame's audio window (256 samples): ring radius follows |sample| envelope."""
    w = np.asarray(wave if wave is not None else np.zeros(256), dtype=np.float64).ravel()
    v, t = tube(envelope_radii(w, rings), seg=seg, height=1.6)
    return _mesh(v, t)


# ------------------------------------------------------------- project → OBJ
def _b64z(raw: bytes) -> str:
    return base64.b64encode(zlib.compress(raw, 6)).decode("ascii")


def write_obj(path, audio, sr, project_doc=None, rings=None, seg=24):
    """Write the song as an OBJ (envelope tube) with the exact audio and the project inside."""
    y = np.asarray(audio, dtype=np.float32).ravel()
    rings = int(rings or max(16, min(4096, y.size // 2048 or 16)))
    v, t = tube(envelope_radii(y, rings), seg=seg, height=2.4)     # a vase you can see, at any song length
    tmp = path + ".part"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(MAGIC + "\n")
        fh.write("# Mathematician's Groovebox song as a 3D model: rings follow the loudness envelope.\n")
        fh.write("# The exact audio and project are stored below as comments; Groovebox imports them back.\n")
        fh.write("# gbmeta %s\n" % json.dumps({"sr": int(sr), "samples": int(y.size), "dtype": "float32",
                                                "chunk": _CHUNK, "rings": rings, "seg": seg}))
        for i in range(0, y.size, _CHUNK):
            enc = _b64z(np.ascontiguousarray(y[i:i + _CHUNK], dtype="<f4").tobytes())
            for j in range(0, len(enc), _LINE):
                fh.write("# gbaudio %d %d %s\n" % (i // _CHUNK, j // _LINE, enc[j:j + _LINE]))
        if project_doc is not None:
            enc = _b64z(json.dumps(project_doc, default=str, separators=(",", ":")).encode("utf-8"))
            for j in range(0, len(enc), _LINE):
                fh.write("# gbproject %d %s\n" % (j // _LINE, enc[j:j + _LINE]))
        fh.write("o groovebox_song\n")
        for p in v:
            fh.write("v %.6f %.6f %.6f\n" % (p[0], p[1], p[2]))
        for a, b, c in t:
            fh.write("f %d %d %d\n" % (a + 1, b + 1, c + 1))
    os.replace(tmp, path)
    return {"path": path, "samples": int(y.size), "sr": int(sr), "vertices": int(len(v)), "faces": int(len(t)),
            "bytes": os.path.getsize(path), "project": project_doc is not None}


def export_project(app, path):
    """The project's master audio (the same buffer and master stage as an audio export) → OBJ."""
    buf, sr = app._get_shared_mixdown_buffer(None, "Project → OBJ")
    y = np.nan_to_num(np.asarray(buf, dtype=np.float32).ravel())
    try:
        y, _ = app._master_hardclip(y, sr, apply_master_vol=True)
    except Exception:
        pass
    doc = None
    try:
        doc = app._project_snapshot()
    except Exception:
        doc = None
    return write_obj(path, y, sr, doc)


# ------------------------------------------------------------- OBJ → audio
def read_obj(path, vertex_ms=1.0, sr=48000):
    """{'audio', 'sr', 'project', 'exact'} from any OBJ. Groovebox OBJs are exact; others are sonified."""
    meta, audio_parts, proj_parts, verts = None, {}, {}, []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for ln in fh:
            if ln.startswith("# gbmeta "):
                meta = json.loads(ln[9:])
            elif ln.startswith("# gbaudio "):
                _, _, a, b, data = ln.split(" ", 4)
                audio_parts.setdefault(int(a), {})[int(b)] = data.strip()
            elif ln.startswith("# gbproject "):
                _, _, b, data = ln.split(" ", 3)
                proj_parts[int(b)] = data.strip()
            elif ln.startswith("v "):
                p = ln.split()
                if len(p) >= 4:
                    try:
                        verts.append((float(p[1]), float(p[2]), float(p[3])))
                    except ValueError:
                        pass
    if meta and audio_parts:
        chunks = []
        for a in sorted(audio_parts):
            enc = "".join(audio_parts[a][b] for b in sorted(audio_parts[a]))
            chunks.append(np.frombuffer(zlib.decompress(base64.b64decode(enc)), dtype="<f4"))
        y = np.concatenate(chunks) if chunks else np.zeros(0, np.float32)
        doc = None
        if proj_parts:
            doc = json.loads(zlib.decompress(base64.b64decode("".join(proj_parts[b] for b in sorted(proj_parts)))))
        return {"audio": y.astype(np.float32), "sr": int(meta.get("sr", sr)), "project": doc, "exact": True,
                "vertices": len(verts)}
    if not verts:
        raise ValueError(f"{os.path.basename(path)}: no vertices to turn into sound")
    v = np.asarray(verts, dtype=np.float64)
    sig = v[:, 1] - float(np.mean(v[:, 1]))
    step = max(1, int(round(sr * vertex_ms / 1000.0)))
    n = max(2, len(sig) * step)
    y = np.interp(np.arange(n) / float(step), np.arange(len(sig)), sig)
    pk = float(np.max(np.abs(y))) or 1.0
    y = (y / pk * 10 ** (-1 / 20)).astype(np.float32)
    return {"audio": y, "sr": sr, "project": None, "exact": False, "vertices": len(verts)}


def import_as_audio(app, obj_path, out_dir=None):
    """Decode an OBJ to a WAV and load it as the carrier (the app's normal WAV import)."""
    r = read_obj(obj_path)
    import media_transmuter as mt
    out_dir = out_dir or str(app._audio_exports_dir())
    os.makedirs(out_dir, exist_ok=True)
    wav = os.path.join(out_dir, os.path.splitext(os.path.basename(obj_path))[0] + "-from-obj.wav")
    mt._write_audio(wav, r["audio"], r["sr"])
    try:
        app._load_wav_path(wav)
    except Exception as exc:
        print("[OBJ] carrier load:", exc)
    r["wav"] = wav
    return r


def import_as_project(app, obj_path):
    r = read_obj(obj_path)
    if r.get("project"):
        app._apply_project_snapshot(r["project"])
        try:
            app._refresh_after_file_input(reason="project_load")
        except Exception:
            pass
    else:
        import_as_audio(app, obj_path)        # any other OBJ: its sound becomes the project's carrier
    return r


# --------------------------------------------------------------- video layer
_LOADED = {"path": None, "mesh": None, "err": ""}


def _song_rings(path):
    """Ring radii of a Groovebox song OBJ (ring-major tube), or None for any other OBJ."""
    meta = None
    with open(path, encoding="utf-8", errors="replace") as fh:
        for _ in range(8):
            ln = fh.readline()
            if ln.startswith("# gbmeta "):
                meta = json.loads(ln[9:]); break
    if not meta or "rings" not in meta:
        return None
    rings, seg = int(meta["rings"]), int(meta.get("seg", 24))
    radii, k = [], 0
    with open(path, encoding="utf-8", errors="replace") as fh:
        for ln in fh:
            if ln.startswith("v "):
                if k % seg == 0:
                    p = ln.split()
                    radii.append(math.hypot(float(p[1]), float(p[3])))
                k += 1
    return np.asarray(radii[:rings], dtype=np.float64) if radii else None


def _loaded_mesh(path):
    if _LOADED["path"] != path:
        _LOADED.update(path=path, mesh=None, err="", radii=None)
        try:
            import obj_scene
            radii = _song_rings(path)
            if radii is not None and radii.size >= 2:
                # A song OBJ: a solid display tube from its own rings (96 rings × 16 sides), animated per frame.
                idx = np.linspace(0, radii.size - 1, min(96, radii.size))
                _LOADED["radii"] = np.interp(idx, np.arange(radii.size), radii)
                v, t = tube(_LOADED["radii"], seg=16, height=2.4)
                _LOADED["mesh"] = _mesh(v, t)
                return _LOADED["mesh"]

            m = obj_scene.load_obj(path)
            if len(m["t"]) > 4000:                          # keep the per-frame rasteriser fast
                keep = np.linspace(0, len(m["t"]) - 1, 4000).astype(np.int64)
                m = dict(m, t=m["t"][keep], tu=m["tu"][keep])
            _LOADED["mesh"] = m
        except Exception as exc:
            _LOADED["err"] = str(exc)
    return _LOADED["mesh"]


# ------------------------------------------------- the video OBJ travels with the project (R32.11.5)
_EMBED_CACHE = {"key": None, "data": None}


def embed_state(app):
    """A compact copy of the video OBJ for the project document, so partners (Edit Together), export workers
    and other computers show it even without the file: a song OBJ travels as its ring radii (< 1 KB); any other
    OBJ as its display mesh (≤ 4000 triangles, float32 + int32, zlib + base64). Without a file, the copy that
    arrived with the project is kept and passed on."""
    path = str(getattr(app, "video_obj_path", "") or "")
    if not path:
        return None
    if not os.path.isfile(path):
        return getattr(app, "_video_obj_embed", None)
    try:
        key = (path, os.path.getmtime(path), os.path.getsize(path))
    except OSError:
        key = (path, 0, 0)
    if _EMBED_CACHE["key"] == key:
        return _EMBED_CACHE["data"]
    mesh = _loaded_mesh(path)
    name = os.path.basename(path)
    if _LOADED.get("radii") is not None:
        data = {"kind": "song", "name": name, "radii": [round(float(x), 5) for x in _LOADED["radii"]]}
    elif mesh is not None:
        v = np.ascontiguousarray(mesh["v"], dtype="<f4"); t = np.ascontiguousarray(mesh["t"], dtype="<i4")
        data = {"kind": "mesh", "name": name, "nv": int(len(v)), "nt": int(len(t)),
                "v": _b64z(v.tobytes()), "t": _b64z(t.tobytes())}
    else:
        data = None
    _EMBED_CACHE.update(key=key, data=data)
    return data


def restore_embed(app, data):
    app._video_obj_embed = data if isinstance(data, dict) else None
    _EMBEDDED["key"] = None


_EMBEDDED = {"key": None, "mesh": None, "radii": None}


def _embedded_mesh(data):
    """(mesh, radii) from an embedded copy."""
    key = json.dumps(data, sort_keys=True)[:256] + str(len(json.dumps(data)))
    if _EMBEDDED["key"] == key:
        return _EMBEDDED["mesh"], _EMBEDDED["radii"]
    mesh = radii = None
    try:
        if data.get("kind") == "song":
            radii = np.asarray(data["radii"], dtype=np.float64)
            v, t = tube(radii, seg=16, height=2.4); mesh = _mesh(v, t)
        elif data.get("kind") == "mesh":
            v = np.frombuffer(zlib.decompress(base64.b64decode(data["v"])), dtype="<f4").reshape(-1, 3)
            t = np.frombuffer(zlib.decompress(base64.b64decode(data["t"])), dtype="<i4").reshape(-1, 3)
            mesh = _mesh(v.astype(np.float64), t.astype(np.int64))
    except Exception:
        mesh = radii = None
    _EMBEDDED.update(key=key, mesh=mesh, radii=radii)
    return mesh, radii


def _video_obj(app):
    """(mesh, radii, name) for the video OBJ, preferring the live file and then the embedded project copy."""
    path = str(getattr(app, "video_obj_path", "") or "") if app is not None else ""
    if path and os.path.isfile(path):
        mesh = _loaded_mesh(path)
        if mesh is not None:
            return mesh, _LOADED.get("radii"), os.path.basename(path)
    data = getattr(app, "_video_obj_embed", None) if app is not None else None
    if isinstance(data, dict):
        mesh, radii = _embedded_mesh(data)
        if mesh is not None:
            return mesh, radii, str(data.get("name") or "Embedded OBJ")
    return None, None, ""



def _blend(img, rgba, x0, y0, alpha=1.0, mode="normal"):
    """Composite an RGBA layer: mode normal (translucent over), screen (glow) or add."""
    h, w = rgba.shape[:2]
    H, W = img.shape[:2]
    x1, y1 = min(W, x0 + w), min(H, y0 + h)
    if x1 <= x0 or y1 <= y0:
        return
    sub = rgba[: y1 - y0, : x1 - x0]
    a = (sub[:, :, 3:4].astype(np.float32) / 255.0) * float(alpha)
    dst = img[y0:y1, x0:x1, :3].astype(np.float32)
    src = sub[:, :, :3].astype(np.float32)
    if mode == "screen":
        mix = 255.0 - (255.0 - dst) * (255.0 - src) / 255.0
    elif mode == "add":
        mix = dst + src
    else:
        mix = src
    img[y0:y1, x0:x1, :3] = np.clip(dst * (1 - a) + mix * a, 0, 255).astype(np.uint8)


def wire_layer(mesh, w, h, t_sec, params=None, color=(140, 235, 255), width=1):
    """RGBA wireframe of a mesh, projected exactly like obj_scene.render_frame (same spin / tilt / scale)."""
    import obj_scene
    from PIL import Image, ImageDraw
    prm = dict(params or {})
    spin = math.radians(float(prm.get("spin_deg_s", 30.0))) * t_sec + math.radians(float(prm.get("yaw_deg", 0.0)))
    tilt = math.radians(float(prm.get("tilt_deg", 15.0)))
    scale = float(prm.get("scale", 0.8))
    v = (mesh["v"] @ obj_scene._rot(spin, tilt).T) * scale
    z = v[:, 2] + 2.6
    f = 0.5 * min(w, h) * 1.6
    sx = w / 2.0 + f * v[:, 0] / z
    sy = h / 2.0 - f * v[:, 1] / z
    t = mesh["t"]
    e = np.concatenate([t[:, [0, 1]], t[:, [1, 2]], t[:, [2, 0]]])
    e = np.unique(np.sort(e, axis=1), axis=0)
    if len(e) > 6000:
        e = e[np.linspace(0, len(e) - 1, 6000).astype(np.int64)]
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    depth = z[e].mean(axis=1)
    zmin, zmax = float(depth.min()), float(depth.max()) or 1.0
    for (a, b), dz in zip(e, depth):
        k = 1.0 - 0.6 * (dz - zmin) / max(1e-9, zmax - zmin)          # far edges fainter
        d.line([(sx[a], sy[a]), (sx[b], sy[b])], fill=color + (int(255 * k),), width=width)
    return np.asarray(im)


def _outline(rgba, color=(255, 236, 120), px=3):
    """A bright outline round the mesh's silhouette (makes a loaded OBJ unmistakable)."""
    m = rgba[:, :, 3] > 0
    grown = m.copy()
    for dy in range(-px, px + 1):
        for dx in range(-px, px + 1):
            if dx * dx + dy * dy <= px * px:
                grown |= np.roll(np.roll(m, dy, axis=0), dx, axis=1)
    ring = grown & ~m
    out = rgba.copy()
    out[ring, :3] = color
    out[ring, 3] = 255
    return out


def _obj_glow(rgba, color=(100, 205, 255), radius=12, strength=0.42):
    """Soft deterministic halo derived from the silhouette; never changes mesh pixels."""
    try:
        from PIL import Image, ImageFilter
        alpha = Image.fromarray(np.asarray(rgba[:, :, 3], dtype=np.uint8), mode="L")
        blur = alpha.filter(ImageFilter.GaussianBlur(radius=max(1, int(radius))))
        halo = np.zeros_like(rgba)
        halo[:, :, :3] = np.asarray(color, dtype=np.uint8)
        halo[:, :, 3] = (np.asarray(blur, dtype=np.float32) * float(np.clip(strength, 0.0, 1.0))).astype(np.uint8)
        return halo
    except Exception:
        return np.zeros_like(rgba)


def _obj_orbit_fx(w, h, t_sec, energy=0.0, strength=0.65):
    """Deterministic orbital sparks and harmonic rings around the centred OBJ."""
    from PIL import Image, ImageDraw
    im = Image.new("RGBA", (int(w), int(h)), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    cx, cy = w * 0.5, h * 0.5
    base = min(w, h) * (0.37 + 0.015 * min(1.0, max(0.0, energy)))
    a0 = float(t_sec) * 0.22
    alpha = int(150 * float(np.clip(strength, 0.0, 1.0)))
    for ring, factor in enumerate((0.78, 1.0, 1.18)):
        rr = base * factor
        d.ellipse((cx-rr, cy-rr*0.72, cx+rr, cy+rr*0.72), outline=(95, 190, 255, int(alpha*(0.55 if ring != 1 else 0.85))), width=1)
    for i in range(18):
        phase = a0 * (1.0 + (i % 3) * 0.17) + i * (math.tau / 18.0)
        rr = base * (0.78 + 0.20 * math.sin(i * 1.7))
        x = cx + math.cos(phase) * rr
        y = cy + math.sin(phase) * rr * 0.72
        r = 1 + (i % 3 == 0)
        col = ((115, 220, 255, alpha), (255, 205, 135, int(alpha*0.82)), (190, 160, 255, int(alpha*0.72)))[i % 3]
        d.ellipse((x-r, y-r, x+r, y+r), fill=col)
    return np.asarray(im)


_FX_CACHE = {"key": None, "F": None}


def _lsystem_word_contour(bands=32):
    """A plain L-system (A→AB, B→A: the Fibonacci word) as a ±1 contour over `bands`, lightly smoothed to [−1, 1]."""
    w = "A"
    while len(w) < bands:
        w = "".join("AB" if ch == "A" else "A" for ch in w)
    x = np.array([1.0 if ch == "A" else -1.0 for ch in w[:bands]])
    x = np.convolve(x, np.array([0.25, 0.5, 0.25]), mode="same")
    x = x - x.mean()
    m = float(np.max(np.abs(x))) or 1.0
    return x / m


def _fractal_contour(app, bands=32):
    """The Fractal Seed L-system pitch contour over `bands` slices, in [−1, 1] (cached per seed)."""
    try:
        key = (str(app._seed_text() if hasattr(app, "_seed_text") else ""), bands)
    except Exception:
        key = ("", bands)
    if _FX_CACHE["key"] == key:
        return _FX_CACHE["F"]
    F = None
    try:
        from groovebox_v3.fractal_seed_engine import rasterize_sequence
        ras = rasterize_sequence(app._fractal_seed_event_plan(), bands)
        F = np.array([max(-1.0, min(1.0, math.log2(float(p)) if float(p) > 0 else -1.0)) for p in ras["pitches"]])
    except Exception:
        F = None
    if F is None or not np.any(np.abs(F) > 1e-9):
        F = _lsystem_word_contour(bands)   # no (or a flat) Fractal Seed plan: the effect still shapes the mesh
    _FX_CACHE.update(key=key, F=F)
    return F


def _goava_curve(app, bands, t_sec):
    """GOAVA getNote along the bands (assigned = band + 1, step moves with time), normalised to [−1, 1]."""
    try:
        import groovebox as gb
        nums = list(app.get_seed_values(t_value=0.0) or []) or [gb.MEUM]
        g = np.array([gb.goava_get_note(float(i + 1), (t_sec * 0.25 + i / bands) * gb.MEUM, nums) for i in range(bands)])
        g = g - g.mean()
        m = float(np.max(np.abs(g))) or 1.0
        return g / m
    except Exception:
        return None


def deform(app, mesh, t_sec):
    """GOAVA and L-system effects on any mesh: the mesh is cut into 32 horizontal bands (by height); GOAVA's curve
    swells / pinches each band (moving with time) and the Fractal Seed L-system contour displaces and twists it."""
    if app is None:
        return mesh
    goava_on = bool(getattr(app, "video_goava_shapes", True)) or bool(
        getattr(app, "btn_goava", None) is not None and app.btn_goava.isChecked())
    # The L-system is a video effect on by default (video_lsystem), like GOAVA shapes — not tied to the
    # FRACTAL SEED audio engine toggle.
    fractal_on = bool(getattr(app, "video_lsystem", True))
    if not goava_on and not fractal_on:
        return mesh
    v = np.array(mesh["v"], dtype=np.float64, copy=True)
    bands = 32
    y = v[:, 1]
    lo, hi = float(y.min()), float(y.max())
    b = np.clip(((y - lo) / max(1e-9, hi - lo) * (bands - 1)).round().astype(np.int64), 0, bands - 1)
    scale = np.ones(len(v))
    twist = np.zeros(len(v))
    if goava_on:
        G = _goava_curve(app, bands, t_sec)
        if G is not None:
            scale *= 1.0 + 0.22 * G[b]
    if fractal_on:
        F = _fractal_contour(app, bands)
        if F is not None:
            scale *= 1.0 + 0.18 * F[b]
            twist += 0.6 * np.cumsum(F)[b] / bands * math.pi
    c, s_ = np.cos(twist), np.sin(twist)
    x, z = v[:, 0] * scale, v[:, 2] * scale
    v[:, 0], v[:, 2] = x * c - z * s_, x * s_ + z * c
    return dict(mesh, v=v)


_EXTRA_MESH = {}


def _extra_objs(app, img, W, H, t_sec, ctx, cd, main_path="", engine=None):
    """MULTIPLE OBJs: the 3D Studio scene (app.video_obj_scene: arrangement, per-OBJ keyframes, instrument binding,
    shots per playlist row, lights, material) or, without a scene, app.video_obj_paths orbiting the centrepiece."""
    import obj_scene
    try:
        import scene3d as _s3
    except Exception:
        _s3 = None
    sc = _s3.scene(app) if (_s3 is not None and getattr(app, "video_obj_scene", None)) else None
    if sc and sc.get("items"):
        items = [it for it in sc["items"] if os.path.isfile(str(it.get("path", "")))][:12]
    else:
        items = [{"path": p} for p in (getattr(app, "video_obj_paths", None) or [])
                 if p and p != main_path and os.path.isfile(str(p))][:8]
    if not items:
        return
    pal = ((150, 230, 255), (255, 170, 120), (190, 255, 150), (255, 140, 210), (255, 230, 120), (160, 170, 255),
           (120, 255, 220), (255, 200, 160))
    seed = _s3._seed(app) if _s3 else "0"
    ph = float(getattr(engine, "playhead", 0.0) or 0.0) if engine is not None else 0.0
    wave = getattr(engine, "wave", None) if engine is not None else None
    sr = getattr(engine, "sr", None) if engine is not None else None
    kind = str((sc or {}).get("arrangement", "ring"))
    smul, ang_add = _s3.shot(app, ph, seed) if (_s3 and (sc or {}).get("shots", True)) else (1.0, 0.0)
    n = len(items)
    for i, it in enumerate(items):
        pth = str(it["path"])
        try:
            m = _EXTRA_MESH.get(pth)
            if m is None:
                if len(_EXTRA_MESH) > 16:
                    _EXTRA_MESH.clear()
                m = _EXTRA_MESH[pth] = obj_scene.load_obj(pth)
            mesh = flow_deform(deform(app, m, t_sec + i), ctx)
            bx, by = _s3.arrange(kind, i, n, t_sec * cd["speed"], seed) if _s3 else (0.5, 0.5)
            st = {"x": float(it.get("x", bx)), "y": float(it.get("y", by)), "scale": float(it.get("scale", 0.22)),
                  "spin": float(it.get("spin", 30.0))}
            if "x" not in it:
                st["x"], st["y"] = bx, by
            if _s3 is not None:
                st = _s3.interp(it.get("keys"), ph, st)
            cx, cy = (st["x"] - 0.5), (st["y"] - 0.5)
            ca, sa = math.cos(ang_add), math.sin(ang_add)
            cx, cy = 0.5 + (cx * ca - cy * sa) * smul, 0.5 + (cx * sa + cy * ca) * smul
            lvl = _s3.bound_level(app, it, wave, sr) if _s3 is not None else None
            grow = 1.0 + (0.6 * lvl if lvl is not None and it.get("bind_mode", "loudness") != "pitch" else 0.0)
            s2 = max(24, int(min(H, W) * st["scale"] * smul * grow))
            x0 = int(max(0, min(W - s2, cx * W - s2 / 2))); y0 = int(max(0, min(H - s2, cy * H - s2 / 2)))
            col = pal[i % len(pal)]
            if lvl is not None and it.get("bind_mode") == "pitch":
                col = (int(120 + 135 * lvl), 200, int(255 - 135 * lvl))
            prm = {"spin_deg_s": st["spin"] * cd["speed"], "tilt_deg": 15.0, "scale": 0.9, "color": col}
            if _s3 is not None:
                prm = _s3.render_params(app, prm)
            rgba = _outline(obj_scene.render_frame(mesh, s2, s2, t_sec + i, params=prm), px=max(1, s2 // 120))
            a = 0.7 * _opacity(app) * cd["alpha"] * (1.0 + 0.4 * lvl if lvl is not None else 1.0)
            _blend(img, rgba, x0, y0, alpha=min(1.0, a))
            _label(img, (str(it.get("bind")) + " · " if it.get("bind") else "") + os.path.basename(pth)[:22], x0 + 4, y0 + 4)
        except Exception:
            continue


def _canon_drive(app):
    """How the active canonical engines animate the overlay (Live Player ▸ 🎨 Visuals follow canonicals, default on):
    each active engine adds speed (SEEDED / RAND), drift (EUCLIDEAN / GOAVA), size (FRACTAL) and steadiness (LOCK)."""
    out = {"alpha": 1.0, "speed": 1.0, "drift": 1.0, "size": 1.0}
    if app is None or not bool(getattr(app, "live_visuals_follow_canonicals", True)):
        return out
    try:
        act = set(app._get_active_engine_set())
    except Exception:
        return out
    out["speed"] += 0.35 * ("seeded" in act) + 0.5 * ("randomizer" in act)
    out["drift"] += 0.6 * ("euclidean" in act) + 0.5 * ("goava" in act)
    out["size"] += 0.08 * ("fractal_seed" in act)
    if "phase_lock" in act:
        out["drift"] *= 0.5; out["speed"] *= 0.8
    out["alpha"] = min(1.15, 0.9 + 0.05 * len(act))
    return out


def overlay(engine, img, frame_index=None):
    """Draw the sample meshes and the loaded OBJ onto a finished video frame (uint8 RGB, h × w × 3)."""
    app = getattr(engine, "app", None)
    sample_on = bool(getattr(app, "video_sample_objs", True)) if app is not None else True
    obj_path = str(getattr(app, "video_obj_path", "") or "") if app is not None else ""
    ctx_on = _context_on(app)
    if not sample_on and not obj_path and not ctx_on:
        return img
    import obj_scene
    img = np.ascontiguousarray(img[:, :, :3], dtype=np.uint8).copy()
    H, W = img.shape[:2]
    fi = int(frame_index) if frame_index is not None else int(getattr(engine, "frame_counter", 0) or 0)
    t_sec = fi / 24.0
    if ctx_on and fi == 0:                 # CONTEXT_DETERMINISM_R6: every render starts from the same state
        engine._ctx_sigma = 0.25; engine._ctx_prev_spectrum = None
    ctx = _context_state(engine, app) if ctx_on else None
    if ctx is not None:
        engine._ctx_last = {k: v for k, v in ctx.items() if k != "spectrum"}
    cd = _canon_drive(app)
    if sample_on:
        wave = getattr(engine, "wave", None)
        mesh = flow_deform(deform(app, sample_mesh(wave), t_sec), ctx)
        s = max(24, int(min(H, W) * 0.22 * cd["size"]))
        e = float(np.sqrt(np.mean(np.square(np.asarray(wave if wave is not None else [0.0], dtype=np.float64)))))
        col = (int(120 + 100 * min(1.0, e * 3)), 200, 255)
        prm = {"spin_deg_s": 40.0 * cd["speed"], "tilt_deg": 20.0, "scale": 0.9, "color": col}
        x0, y0 = W - s - max(4, W // 40), H - s - max(4, H // 30)
        rgba = obj_scene.render_frame(mesh, s, s, t_sec, params=prm)
        _blend(img, rgba, x0, y0, alpha=min(1.0, 0.6 * _opacity(app) * cd["alpha"]))
        if _wire_on(app):
            _blend(img, wire_layer(mesh, s, s, t_sec, prm, color=(150, 240, 255)), x0, y0, alpha=0.55, mode="screen")
    vmesh, vradii, vname = _video_obj(app) if obj_path else (None, None, "")
    if vmesh is not None:
        mesh = vmesh
        if vradii is not None:
            # The song plays along the vase: a bulge travels with the playhead, the whole vase pulses with the
            # frame's loudness. Rings are bottom (start of the song) → top (end).
            radii = vradii; n = radii.size
            ph = float(np.clip(getattr(engine, "playhead", 0.0) or 0.0, 0.0, 1.0))
            wave = np.asarray(getattr(engine, "wave", None) if getattr(engine, "wave", None) is not None else [0.0], dtype=np.float64)
            e = min(1.0, 3.0 * math.sqrt(float(np.mean(wave ** 2))))
            pos = np.linspace(0.0, 1.0, n)
            r = radii * (1.0 + 0.45 * np.exp(-((pos - ph) / 0.04) ** 2)) * (1.0 + 0.12 * e)
            v, t = tube(r, seg=16, height=2.4)
            mesh = _mesh(v, t)
        if mesh is not None:
            mesh = flow_deform(deform(app, mesh, t_sec), ctx)
            # CENTREPIECE MOTION: the OBJ is the centre of the picture and moves — a slow Lissajous drift around the
            # centre (periods 13 s / 17 s), a breathing size with the frame's loudness, faster with active canonicals.
            _w = np.asarray(getattr(engine, "wave", None) if getattr(engine, "wave", None) is not None else [0.0], dtype=np.float64)
            _e = min(1.0, 3.0 * math.sqrt(float(np.mean(_w ** 2)))) if _w.size else 0.0
            s = max(32, int(min(H, W) * 0.62 * (1.0 + 0.06 * _e) * cd["size"]))
            s = min(s, min(H, W))
            prm = {"spin_deg_s": 24.0 * cd["speed"], "tilt_deg": 12.0 + 6.0 * math.sin(t_sec * 0.37), "scale": 0.95,
                   "color": (255, 214, 150)}
            try:
                import scene3d as _s3c
                prm = _s3c.render_params(app, prm)
                if _s3c.scene(app).get("shots", True):
                    _sm, _aa = _s3c.shot(app, float(getattr(engine, "playhead", 0.0) or 0.0), _s3c._seed(app))
                    s = min(min(H, W), max(32, int(s * _sm)))
                    prm["spin_deg_s"] = prm["spin_deg_s"] + math.degrees(_aa) * 0.05
            except Exception:
                pass
            # The loaded OBJ is centre-anchored in Live Player by default. Orbit is
            # an explicit optional effect; canonicals may animate geometry/lighting
            # without silently displacing the model from the screen centre.
            if bool(getattr(app, "video_obj_drift", False)):
                _dx = 0.035 * W * cd["drift"] * math.sin(2.0 * math.pi * t_sec / 13.0)
                _dy = 0.025 * H * cd["drift"] * math.sin(2.0 * math.pi * t_sec / 17.0 + 1.1)
            else:
                _dx = _dy = 0.0
            x0 = int(round((W - s) * 0.5 + _dx))
            y0 = int(round((H - s) * 0.5 + _dy))
            rgba = obj_scene.render_frame(mesh, s, s, t_sec, params=prm)
            # Cinematic aura and orbit graphics are separate compositing layers,
            # so the OBJ's original alpha, texture and silhouette remain intact.
            _fx_strength = float(np.clip(getattr(app, "video_obj_fx_strength", 0.72), 0.0, 1.0)) if app is not None else 0.72
            if bool(getattr(app, "video_obj_glow", True)):
                _halo = _obj_glow(rgba, color=(90, 190, 255), radius=max(3, s // 34), strength=0.62 * _fx_strength)
                _blend(img, _halo, x0, y0, alpha=0.9, mode="screen")
            if bool(getattr(app, "video_obj_particles", True)):
                _blend(img, _obj_orbit_fx(W, H, t_sec, _e, _fx_strength), 0, 0, alpha=0.8, mode="screen")
            rgba = _outline(rgba, px=max(2, s // 120))
            _blend(img, rgba, x0, y0, alpha=min(1.0, 0.92 * _opacity(app) * cd["alpha"]))
            if _wire_on(app):
                _blend(img, wire_layer(mesh, s, s, t_sec, prm, color=(255, 240, 170), width=max(1, s // 300)),
                       x0, y0, alpha=0.7, mode="screen")
            _extra_objs(app, img, W, H, t_sec, ctx, cd, obj_path, engine)
            try:
                _label(img, "OBJ · " + vname, x0 + 6, y0 + 6)
            except Exception:
                pass
    if ctx is not None:
        # CONTEXT_FIELD_20261112: the Party Mode law on the whole frame — curvature = musical significance
        # (novelty), hue = dominant key-chart degree, tint regions = spectral bands, light/dark = 1/|det J|.
        import context_field
        img = context_field.apply_frame(img, t_sec, ctx, _context_strength(app))
    return img


def _context_on(app):
    """Party Mode in the video (OBJ system). Off by default so existing exports stay bit-identical."""
    return bool(getattr(app, "video_context_fx", False)) if app is not None else False


def _context_strength(app):
    try:
        return float(np.clip(float(getattr(app, "video_context_strength", 0.5)), 0.0, 1.0))
    except Exception:
        return 0.5


def _context_state(engine, app):
    """Per-frame context from this frame's audio (engine.wave): bands, degree/hue, centroid, energy, novelty → σ."""
    import context_field
    try:
        import party_sound
        base, steps = party_sound.tuning(app)
    except Exception:
        base, steps = 432.0, 12
    sr = float(getattr(app, "play_sample_rate", 0) or getattr(engine, "sample_rate", 0) or 48000)
    return context_field.video_state(engine, getattr(engine, "wave", None), sr, base, steps,
                                     getattr(app, "_keychart_ratio", None) if app is not None else None)


def flow_deform(mesh, ctx, tau=None):
    """The same flow map on a mesh: vertices (x, z) about the vertical axis are mapped by z → z·e^(λτ), height-
    windowed, so a comfortable passage spirals the model in (concentric) and a significant change curves it out."""
    if ctx is None or mesh is None:
        return mesh
    import context_field
    lam = context_field.flow_lambda(float(ctx.get("sigma", 0.25)))
    tau = context_field.TAU if tau is None else float(tau)
    v = np.array(mesh["v"], dtype=np.float64, copy=True)
    y = v[:, 1]
    lo, hi = float(y.min()), float(y.max())
    hgt = (y - lo) / max(1e-9, hi - lo)                    # 0 bottom … 1 top: the map grows along the height
    m = np.exp(lam.real * tau * hgt) * np.exp(1j * lam.imag * tau * hgt)
    zc = (v[:, 0] + 1j * v[:, 2]) * m
    v[:, 0], v[:, 2] = zc.real, zc.imag
    kap = context_field.curvature(float(ctx.get("sigma", 0.25)))
    if kap > 0:                                           # destabilising curvature: a bend that grows with height
        v[:, 0] += 0.25 * kap * np.sin(np.pi * hgt) * (hi - lo)
    return dict(mesh, v=v)


def _wire_on(app):
    return bool(getattr(app, "video_obj_wire", True)) if app is not None else True


def _opacity(app):
    try:
        return float(np.clip(float(getattr(app, "video_obj_opacity", 1.0)), 0.0, 1.0))
    except Exception:
        return 1.0


def _label(img, text, x, y):
    from PIL import Image, ImageDraw
    im = Image.fromarray(img)
    d = ImageDraw.Draw(im)
    d.rectangle([x - 3, y - 2, x + 7 * len(text) + 4, y + 14], fill=(20, 16, 6))
    d.text((x, y), text, fill=(255, 236, 120))
    img[:, :, :] = np.asarray(im)


# -------------------------------------------------------------------- window
def open_window(app):
    from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QPushButton, QLabel, QCheckBox, QFileDialog)
    w = getattr(app, "_project_obj_window", None)
    try:
        if w is not None:
            w.isVisible()
    except RuntimeError:
        w = None
    if w is not None:
        w.show(); w.raise_(); return w
    dlg = QDialog(app); dlg.setWindowTitle("🧊 Project ⇄ OBJ")
    lay = QVBoxLayout(dlg)
    info = QLabel("Export the whole song as a 3D model (loudness tube) that also carries the exact audio and the "
                  "project. Import any OBJ as sound, or a Groovebox OBJ back as the project. In the video, meshes "
                  "built from the audio appear on every frame; a loaded OBJ is drawn large with a bright outline.")
    info.setWordWrap(True); lay.addWidget(info)
    status = QLabel(""); status.setWordWrap(True)

    def do_export():
        job = app.export_project_obj()           # the background export worker, listed in Export Jobs
        if job is not None:
            status.setText("Queued in Export Jobs: " + os.path.basename(job.out_file))

    def pick_obj(title):
        p, _ = QFileDialog.getOpenFileName(dlg, title, "", "Wavefront OBJ (*.obj);;All files (*)")
        return p

    def do_audio():
        p = pick_obj("OBJ → audio")
        if p:
            try:
                r = import_as_audio(app, p)
                status.setText(("✔ exact song" if r["exact"] else "✔ sonified %d vertices" % r["vertices"])
                               + " → carrier: " + os.path.basename(r["wav"]))
            except Exception as exc:
                status.setText(f"Import failed: {exc}")

    def do_project():
        p = pick_obj("OBJ → project")
        if p:
            try:
                r = import_as_project(app, p)
                status.setText("✔ project restored from the OBJ" if r.get("project") else
                               "No project inside — the OBJ's sound was loaded as the carrier")
            except Exception as exc:
                status.setText(f"Import failed: {exc}")

    def do_use_project():
        p = os.path.join(str(app._exports_dir()), "project-video.obj")
        status.setText("Rendering the song into an OBJ for the video…")
        from ui_runtime import submit_ui_task
        def done(r):
            app.video_obj_path = r["path"]
            status.setText("✔ The video now shows this project's OBJ (%s); it plays along with the song."
                           % os.path.basename(r["path"]))
        submit_ui_task(dlg, lambda: export_project(app, p), on_result=done,
                       on_error=lambda e: status.setText(f"Could not make the project OBJ: {e}"), key="project-obj-video")

    def do_show():
        p = pick_obj("Show an OBJ in the video")
        if p:
            app.video_obj_path = p
            status.setText("Video shows: " + os.path.basename(p))

    for cap, fn in (("⬇ Export project → OBJ (audio + project inside)", do_export),
                    ("🔊 Import OBJ → audio (as carrier)", do_audio),
                    ("📂 Import OBJ → project", do_project),
                    ("🎬 Use this project as the video OBJ (plays along with the song)", do_use_project),
                    ("🧊 Show an OBJ in the video…", do_show),
                    ("✖ Stop showing the loaded OBJ", lambda: (setattr(app, "video_obj_path", ""), status.setText("No OBJ in the video")))):
        b = QPushButton(cap); b.clicked.connect(fn); lay.addWidget(b)
    c1 = QCheckBox("Meshes from the audio in every video frame"); c1.setChecked(bool(getattr(app, "video_sample_objs", True)))
    c1.toggled.connect(lambda on: setattr(app, "video_sample_objs", bool(on)))
    c2 = QCheckBox("GOAVA shapes in the video (GOAVA's sound stays off unless GOAVA is on)")
    c2.setChecked(bool(getattr(app, "video_goava_shapes", True)))
    c2.toggled.connect(lambda on: setattr(app, "video_goava_shapes", bool(on)))
    c4 = QCheckBox("L-system (Fractal Seed) shaping of the video meshes")
    c4.setChecked(bool(getattr(app, "video_lsystem", True)))
    c4.toggled.connect(lambda on: setattr(app, "video_lsystem", bool(on)))
    lay.addWidget(c4)
    c3 = QCheckBox("Wireframe second layer (screen-blended glow)"); c3.setChecked(_wire_on(app))
    c3.toggled.connect(lambda on: setattr(app, "video_obj_wire", bool(on)))
    c6 = QCheckBox("Cinematic blue aura / soft glow"); c6.setChecked(bool(getattr(app, "video_obj_glow", True)))
    c6.toggled.connect(lambda on: setattr(app, "video_obj_glow", bool(on)))
    c7 = QCheckBox("Harmonic orbital rings and moving sparks"); c7.setChecked(bool(getattr(app, "video_obj_particles", True)))
    c7.toggled.connect(lambda on: setattr(app, "video_obj_particles", bool(on)))
    c8 = QCheckBox("Allow gentle Lissajous orbit (off = locked to screen centre)"); c8.setChecked(bool(getattr(app, "video_obj_drift", False)))
    c8.toggled.connect(lambda on: setattr(app, "video_obj_drift", bool(on)))
    from PyQt6.QtWidgets import QSlider, QHBoxLayout
    from PyQt6.QtCore import Qt
    row = QHBoxLayout(); row.addWidget(QLabel("OBJ opacity"))
    sl = QSlider(Qt.Orientation.Horizontal); sl.setRange(10, 100); sl.setValue(int(round(_opacity(app) * 100)))
    sl.valueChanged.connect(lambda v: setattr(app, "video_obj_opacity", v / 100.0)); row.addWidget(sl)
    c5 = QCheckBox("Party Mode in the video: curvature = musical significance, hue = pitch class, tints = spectrum, light/dark mesh")
    c5.setChecked(_context_on(app)); c5.toggled.connect(lambda on: setattr(app, "video_context_fx", bool(on)))
    row2 = QHBoxLayout(); row2.addWidget(QLabel("Party strength"))
    sl2 = QSlider(Qt.Orientation.Horizontal); sl2.setRange(0, 100); sl2.setValue(int(round(_context_strength(app) * 100)))
    sl2.valueChanged.connect(lambda v: setattr(app, "video_context_strength", v / 100.0)); row2.addWidget(sl2)
    row3 = QHBoxLayout(); row3.addWidget(QLabel("Visual FX strength"))
    sl3 = QSlider(Qt.Orientation.Horizontal); sl3.setRange(0, 100); sl3.setValue(int(round(float(getattr(app, "video_obj_fx_strength", 0.72)) * 100)))
    sl3.valueChanged.connect(lambda v: setattr(app, "video_obj_fx_strength", v / 100.0)); row3.addWidget(sl3)
    lay.addWidget(c1); lay.addWidget(c2); lay.addWidget(c3); lay.addWidget(c6); lay.addWidget(c7); lay.addWidget(c8)
    lay.addLayout(row); lay.addWidget(c5); lay.addLayout(row2); lay.addLayout(row3)
    lay.addWidget(status)
    app._project_obj_window = dlg
    dlg.show()
    return dlg
