"""OBJ models as timeline layers — textured by an image, a video or the scene.

GROOVEBOX_R23R_OBJ_SCENE_20261103

* load_obj(path)            → mesh (vertices, uvs, triangles, MTL texture path)
* render_frame(mesh, ...)   → RGBA frame from a numpy z-buffer rasterizer with
                              perspective-correct texture mapping and Lambert shade
* render_clip(...)          → an alpha video (.mov, PNG codec) of the spinning
                              model; frames are independent, so they render in
                              CHUNKS across a process pool (several frames per task)

Texture modes: "none" (shaded colour), "mtl" (the OBJ's own map_Kd), "image",
"video" (texture follows time), "scene" (a pre-rendered video of the timeline
layers below — the scene wrapped onto the model).
"""
from __future__ import annotations

import math
import os
import subprocess
from concurrent.futures import ProcessPoolExecutor

import numpy as np


# ---------------------------------------------------------------- loading
def load_obj(path):
    verts, uvs, tris, tuv = [], [], [], []
    mtllib, tex = None, None
    base = os.path.dirname(os.path.abspath(path))
    with open(path, encoding="utf-8", errors="replace") as fh:
        for ln in fh:
            p = ln.split()
            if not p:
                continue
            if p[0] == "v" and len(p) >= 4:
                verts.append([float(p[1]), float(p[2]), float(p[3])])
            elif p[0] == "vt" and len(p) >= 3:
                uvs.append([float(p[1]), float(p[2])])
            elif p[0] == "f" and len(p) >= 4:
                idx = []
                for tok in p[1:]:
                    a = tok.split("/")
                    vi = int(a[0]); ti = int(a[1]) if len(a) > 1 and a[1] else 0
                    vi = vi - 1 if vi > 0 else len(verts) + vi
                    ti = (ti - 1 if ti > 0 else len(uvs) + ti) if ti else -1
                    idx.append((vi, ti))
                for k in range(1, len(idx) - 1):          # fan triangulation
                    tris.append([idx[0][0], idx[k][0], idx[k + 1][0]])
                    tuv.append([idx[0][1], idx[k][1], idx[k + 1][1]])
            elif p[0] == "mtllib" and len(p) >= 2:
                mtllib = os.path.join(base, " ".join(p[1:]))
    if mtllib and os.path.isfile(mtllib):
        with open(mtllib, encoding="utf-8", errors="replace") as fh:
            for ln in fh:
                p = ln.split()
                if p and p[0] == "map_Kd" and len(p) >= 2:
                    cand = os.path.join(os.path.dirname(mtllib), p[-1])
                    if os.path.isfile(cand):
                        tex = cand
                        break
    if not verts or not tris:
        raise ValueError(f"{os.path.basename(path)}: no geometry")
    v = np.asarray(verts, dtype=np.float64)
    v -= (v.max(axis=0) + v.min(axis=0)) / 2.0
    _r = float(np.max(np.linalg.norm(v, axis=1))) if len(v) else 0.0
    if _r > 0.0:                  # all vertices at the centre: nothing to scale
        v /= _r
    t = np.asarray(tris, dtype=np.int64)
    uv = np.asarray(uvs, dtype=np.float64) if uvs else None
    tu = np.asarray(tuv, dtype=np.int64) if uvs else None
    if uv is None:                                     # spherical UVs when the file has none
        uv = np.stack([0.5 + np.arctan2(v[:, 2], v[:, 0]) / (2 * math.pi), 0.5 + np.arcsin(np.clip(v[:, 1], -1, 1)) / math.pi], axis=1)
        tu = t.copy()
    tu = np.where(tu < 0, t, tu)
    return {"v": v, "t": t, "uv": uv, "tu": tu, "texture": tex}


def load_image_rgb(path, size=512):
    from PIL import Image
    im = Image.open(path).convert("RGB")
    im.thumbnail((size, size))
    return np.asarray(im, dtype=np.uint8)


# -------------------------------------------------------------- rendering
def _rot(yaw, pitch):
    cy, sy, cp, sp = math.cos(yaw), math.sin(yaw), math.cos(pitch), math.sin(pitch)
    ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    rx = np.array([[1, 0, 0], [0, cp, -sp], [0, sp, cp]])
    return rx @ ry


def render_frame(mesh, w, h, t_sec, params=None, tex=None):
    """RGBA uint8 (h, w, 4); transparent background."""
    prm = dict(params or {})
    spin = math.radians(float(prm.get("spin_deg_s", 30.0))) * t_sec + math.radians(float(prm.get("yaw_deg", 0.0)))
    tilt = math.radians(float(prm.get("tilt_deg", 15.0)))
    scale = float(prm.get("scale", 0.8))
    color = np.array(prm.get("color", (200, 220, 255)), dtype=np.float64)
    R = _rot(spin, tilt)
    v = (mesh["v"] @ R.T) * scale
    dist = 2.6
    z = v[:, 2] + dist
    f = 0.5 * min(w, h) * 1.6
    sx = w / 2.0 + f * v[:, 0] / z
    sy = h / 2.0 - f * v[:, 1] / z
    out = np.zeros((h, w, 4), dtype=np.uint8)
    zbuf = np.full((h, w), np.inf)
    tris, tu, uv = mesh["t"], mesh["tu"], mesh["uv"]
    p0, p1, p2 = v[tris[:, 0]], v[tris[:, 1]], v[tris[:, 2]]
    nrm = np.cross(p1 - p0, p2 - p0)
    _nl = np.linalg.norm(nrm, axis=1)[:, None]
    nrm = np.divide(nrm, _nl, out=np.zeros_like(nrm), where=_nl != 0)   # degenerate triangle: no normal
    light = np.array([0.4, 0.6, -0.7]); light /= np.linalg.norm(light)
    shade_all = np.clip(np.abs(nrm @ light), 0.15, 1.0)
    th = tw = 0
    if tex is not None:
        th, tw = tex.shape[:2]
    order = np.argsort(-(z[tris].mean(axis=1)))         # far → near (helps early z-reject)
    for k in order:
        i0, i1, i2 = tris[k]
        x0, y0, x1, y1, x2, y2 = sx[i0], sy[i0], sx[i1], sy[i1], sx[i2], sy[i2]
        minx = max(int(math.floor(min(x0, x1, x2))), 0); maxx = min(int(math.ceil(max(x0, x1, x2))), w - 1)
        miny = max(int(math.floor(min(y0, y1, y2))), 0); maxy = min(int(math.ceil(max(y0, y1, y2))), h - 1)
        if minx > maxx or miny > maxy:
            continue
        den = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
        if abs(den) < 1e-12:
            continue
        xs, ys = np.meshgrid(np.arange(minx, maxx + 1) + 0.5, np.arange(miny, maxy + 1) + 0.5)
        a = ((y1 - y2) * (xs - x2) + (x2 - x1) * (ys - y2)) / den
        b = ((y2 - y0) * (xs - x2) + (x0 - x2) * (ys - y2)) / den
        c = 1.0 - a - b
        inside = (a >= 0) & (b >= 0) & (c >= 0)
        if not inside.any():
            continue
        iz = a / z[i0] + b / z[i1] + c / z[i2]         # perspective-correct 1/z
        depth = np.divide(1.0, iz, out=np.full_like(iz, np.inf), where=iz != 0)   # 1/0 = infinitely far
        zb = zbuf[miny:maxy + 1, minx:maxx + 1]
        m = inside & (depth < zb)
        if not m.any():
            continue
        zb[m] = depth[m]
        sh = shade_all[k]
        if tex is not None:
            j0, j1, j2 = tu[k]
            u = (a * uv[j0, 0] / z[i0] + b * uv[j1, 0] / z[i1] + c * uv[j2, 0] / z[i2]) * depth
            vv = (a * uv[j0, 1] / z[i0] + b * uv[j1, 1] / z[i1] + c * uv[j2, 1] / z[i2]) * depth
            tx = np.clip((u % 1.0) * (tw - 1), 0, tw - 1).astype(np.int64)
            ty = np.clip((1.0 - (vv % 1.0)) * (th - 1), 0, th - 1).astype(np.int64)
            rgb = tex[ty[m], tx[m]].astype(np.float64) * (0.35 + 0.65 * sh)
        else:
            rgb = np.broadcast_to(color * sh, (int(m.sum()), 3))
        blk = out[miny:maxy + 1, minx:maxx + 1]
        blk[m, :3] = np.clip(rgb, 0, 255).astype(np.uint8)
        blk[m, 3] = 255
    return out


# ------------------------------------------------- chunked parallel export
_W = {}


def _init_worker(obj_path, params, static_tex):
    _W["mesh"] = load_obj(obj_path)
    _W["params"] = params
    _W["tex"] = static_tex


def _render_chunk(args):
    """Render several frames in one task: [(fi, t, tex_or_None)] → [(fi, bytes)]."""
    w, h, items = args
    out = []
    for fi, t, tex in items:
        fr = render_frame(_W["mesh"], w, h, t, _W["params"], tex if tex is not None else _W["tex"])
        out.append((fi, fr.tobytes()))
    return out


def _video_texture_frames(ffmpeg, path, fps, duration, size=256):
    """Yield RGB frames (size×size) of a texture video at the timeline fps."""
    cmd = [ffmpeg, "-v", "error", "-i", path, "-t", f"{duration:.6f}", "-r", str(fps),
           "-vf", f"scale={size}:{size}", "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    n = size * size * 3
    last = np.zeros((size, size, 3), dtype=np.uint8)
    try:
        while True:
            b = p.stdout.read(n)
            if len(b) < n:
                break
            last = np.frombuffer(b, dtype=np.uint8).reshape(size, size, 3)
            yield last
        while True:                                   # hold the last frame if the video is shorter
            yield last
    finally:
        try:
            p.kill()
        except Exception:
            pass


def render_clip(obj_path, out_path, w, h, fps, duration, params=None, texture_mode="mtl", texture_path=None,
                ffmpeg="ffmpeg", workers=None, chunk=8, progress=None):
    """Write an alpha .mov (PNG codec) of the model; parallel chunked rendering."""
    mesh = load_obj(obj_path)
    static_tex = None
    if texture_mode == "mtl" and mesh.get("texture"):
        static_tex = load_image_rgb(mesh["texture"])
    elif texture_mode == "image" and texture_path:
        static_tex = load_image_rgb(texture_path)
    vid_iter = None
    if texture_mode in ("video", "scene") and texture_path:
        vid_iter = _video_texture_frames(ffmpeg, texture_path, fps, duration)
    n = max(1, int(round(duration * fps)))
    enc = subprocess.Popen([ffmpeg, "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{w}x{h}",
                            "-r", str(fps), "-i", "pipe:0", "-c:v", "png", "-pix_fmt", "rgba", out_path],
                           stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    workers = int(workers or max(1, min(8, (os.cpu_count() or 2) - 1)))
    jobs = []
    for c0 in range(0, n, chunk):
        items = []
        for fi in range(c0, min(n, c0 + chunk)):
            tex = next(vid_iter) if vid_iter is not None else None
            items.append((fi, fi / float(fps), tex))
        jobs.append((w, h, items))
    done = 0
    try:
        with ProcessPoolExecutor(max_workers=workers, initializer=_init_worker,
                                 initargs=(obj_path, dict(params or {}), static_tex)) as ex:
            for res in ex.map(_render_chunk, jobs):        # ordered results, parallel work
                for _fi, buf in res:
                    enc.stdin.write(buf)
                done += len(res)
                if progress:
                    progress(done, n)
        enc.stdin.close()
        if enc.wait() != 0:
            raise RuntimeError((enc.stderr.read() or b"").decode("utf-8", "replace")[-800:] or "OBJ encode failed")
    finally:
        try:
            enc.kill()
        except Exception:
            pass
    return out_path
