#!/usr/bin/env python3
"""PASTE_ME_NEAR_MCC — browse your .MCC files as a simple gallery.

Copy this file (and the launcher for your system) into any folder that holds
.MCC files and run it:
    Windows : double-click PASTE_ME_NEAR_MCC.bat
    macOS   : double-click PASTE_ME_NEAR_MCC.command
    Linux   : ./PASTE_ME_NEAR_MCC.sh   (or: python3 PASTE_ME_NEAR_MCC.py)

It writes MCC_GALLERY/index.html next to the files and opens it in your browser:
  * MCC images   -> PNG
  * MCC audio    -> playable WAV
  * MCC video    -> frame thumbnails (+ MP4 when ffmpeg is installed)
  * MCC packages -> file list (games, exports)
  * MCC projects -> title / seed / tempo summary
Needs only Python 3 (numpy is used when present to go faster). Nothing is sent
anywhere; source files are never modified.
"""
from __future__ import annotations

import hashlib
import html
import json
import os
import shutil
import struct
import subprocess
import sys
import webbrowser
import zlib

MAGIC = b"MCCMEDIA"
try:
    import numpy as np  # optional
except Exception:  # noqa: BLE001
    np = None


# ---------------------------------------------------------------- MCC reading
def read_header(path):
    with open(path, "rb") as f:
        if f.read(8) != MAGIC:
            return None
        _ver, n = struct.unpack(">BI", f.read(5))
        return json.loads(f.read(n))


def blocks(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        f.read(8)
        _ver, n = struct.unpack(">BI", f.read(5))
        h.update(f.read(n))
        while True:
            tag = f.read(1)
            if tag == b"E":
                if f.read(32) != h.digest():
                    raise ValueError("integrity check failed")
                return
            if tag != b"B":
                raise ValueError("truncated file")
            bt = f.read(1)
            (ml,) = struct.unpack(">I", f.read(4)); mraw = f.read(ml); h.update(mraw)
            (cl,) = struct.unpack(">Q", f.read(8)); payload = zlib.decompress(f.read(cl)); h.update(payload)
            yield bt, json.loads(mraw), payload


def write_png(path, w, h, c, rows):
    """rows: iterable of bytes per image row (c channels)."""
    ctype = {1: 0, 3: 2, 4: 6}[c]
    raw = b"".join(b"\x00" + bytes(r) for r in rows)

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, ctype, 0, 0, 0))
                + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))


def _unpredict_row(res, c):
    out = bytearray(res)
    for i in range(c, len(out)):
        out[i] = (out[i] + out[i - c]) & 0xFF
    return out


def image_png(path, hdr, out_png):
    w, h, c = int(hdr["width"]), int(hdr["height"]), int(hdr.get("channels", 3))
    for bt, _m, payload in blocks(path):
        if bt == b"I":
            if np is not None:
                a = np.cumsum(np.frombuffer(payload, dtype=np.uint8).reshape(h, w, c), axis=1, dtype=np.uint8)
                write_png(out_png, w, h, c, (a[y].tobytes() for y in range(h)))
            else:
                stride = w * c
                write_png(out_png, w, h, c, (_unpredict_row(payload[y * stride:(y + 1) * stride], c) for y in range(h)))
            return True
    return False


def _pcm(payload, kind, frames, channels):
    item = {"f32": 4, "i16": 2, "i32": 4}[kind]
    n = frames * channels
    if np is not None:
        udt = {"f32": np.uint32, "i16": np.uint16, "i32": np.uint32}[kind]
        b = np.frombuffer(payload, dtype=np.uint8).reshape(item, n)
        res = np.ascontiguousarray(b.T).view(udt).reshape(channels, frames).T
        iv = np.cumsum(res, axis=0, dtype=udt)
        x = iv.view({"f32": np.float32, "i16": np.int16, "i32": np.int32}[kind])
        if kind == "i16":
            return x.astype(np.int16)
        if kind == "i32":
            return np.clip(x.astype(np.float64) / max(1.0, float(np.max(np.abs(x))) or 1.0) * 32767, -32768, 32767).astype(np.int16)
        return np.clip(np.nan_to_num(x.astype(np.float64)) * 32767, -32768, 32767).astype(np.int16)
    # pure-Python fallback
    planes = [payload[k * n:(k + 1) * n] for k in range(item)]
    mask = (1 << (8 * item)) - 1
    vals = []
    for ch in range(channels):
        acc = 0
        col = []
        for i in range(frames):
            j = ch * frames + i
            v = 0
            for k in range(item):
                v |= planes[k][j] << (8 * k)
            acc = (acc + v) & mask
            col.append(acc)
        vals.append(col)
    out = []
    for i in range(frames):
        for ch in range(channels):
            u = vals[ch][i]
            if kind == "i16":
                s = u - 65536 if u >= 32768 else u
            elif kind == "i32":
                s = (u - (1 << 32) if u >= (1 << 31) else u) >> 16
            else:
                s = int(max(-1.0, min(1.0, struct.unpack("<f", struct.pack("<I", u))[0])) * 32767)
            out.append(max(-32768, min(32767, s)))
    return out


def audio_wav(path, hdr, out_wav):
    import wave
    sr = int(hdr.get("sample_rate", hdr.get("audio_rate", 48000)) or 48000)
    chans = int(hdr.get("channels", hdr.get("audio_channels", 1)) or 1)
    with wave.open(out_wav, "wb") as wv:
        wv.setnchannels(chans); wv.setsampwidth(2); wv.setframerate(sr)
        any_audio = False
        for bt, m, payload in blocks(path):
            if bt != b"A":
                continue
            ch = int(m.get("channels", chans))
            x = _pcm(payload, m["pcm"], int(m["frames"]), ch)
            wv.writeframes(x.tobytes() if np is not None else struct.pack("<%dh" % len(x), *x))
            any_audio = True
    return any_audio


def video_thumbs(path, hdr, out_dir, stem, max_thumbs=4):
    w, h = int(hdr["width"]), int(hdr["height"])
    prev = None; thumbs = []; i = 0
    every = max(1, int(hdr.get("keyframe", 48)))
    for bt, _m, payload in blocks(path):
        if bt == b"K":
            prev = bytearray(payload)
        elif bt == b"D" and prev is not None:
            if np is not None:
                prev = bytearray((np.frombuffer(bytes(prev), np.uint8) + np.frombuffer(payload, np.uint8)).tobytes())
            else:
                prev = bytearray((a + b) & 0xFF for a, b in zip(prev, payload))
        else:
            continue
        if i % every == 0 and len(thumbs) < max_thumbs:
            pth = os.path.join(out_dir, f"{stem}_f{i}.png")
            write_png(pth, w, h, 3, (prev[y * w * 3:(y + 1) * w * 3] for y in range(h)))
            thumbs.append(os.path.basename(pth))
        i += 1
    return thumbs, i


def _frames(path):
    prev = None
    for bt, _m, payload in blocks(path):
        if bt == b"K":
            prev = bytearray(payload)
        elif bt == b"D" and prev is not None:
            prev = bytearray((a + b) & 0xFF for a, b in zip(prev, payload)) if np is None else \
                bytearray((np.frombuffer(bytes(prev), np.uint8) + np.frombuffer(payload, np.uint8)).tobytes())
        else:
            continue
        yield bytes(prev)


def video_mp4(path, hdr, out_mp4, wav=None):
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return False
    w, h, fps = int(hdr["width"]), int(hdr["height"]), float(hdr.get("fps", 24.0))
    for vcodec in (["-c:v", "libx264", "-pix_fmt", "yuv420p"], ["-c:v", "mpeg4", "-q:v", "3", "-pix_fmt", "yuv420p"]):
        cmd = [ffmpeg, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}", "-r", f"{fps}", "-i", "-"]
        if wav:
            cmd += ["-i", wav, "-c:a", "aac", "-shortest"]
        cmd += vcodec + [out_mp4]
        p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
        try:
            for fr in _frames(path):
                p.stdin.write(fr)
            p.stdin.close()
        except (BrokenPipeError, OSError):
            pass
        if p.wait() == 0:
            return True
    return False


# ---------------------------------------------------------------- gallery
def card(title, body, kind):
    return (f'<div class="card {kind}"><div class="kind">{html.escape(kind.upper())}</div>'
            f'<div class="title">{html.escape(title)}</div>{body}</div>')


def main():
    here = os.path.dirname(os.path.abspath(sys.argv[0])) if len(sys.argv) < 2 else os.path.abspath(sys.argv[1])
    out = os.path.join(here, "MCC_GALLERY")
    os.makedirs(out, exist_ok=True)
    files = sorted(f for f in os.listdir(here) if f.lower().endswith(".mcc") and os.path.isfile(os.path.join(here, f)))
    cards = []
    for name in files:
        src = os.path.join(here, name)
        stem = os.path.splitext(name)[0]
        size = os.path.getsize(src)
        try:
            hdr = read_header(src)
            if hdr is None:   # project .MCC (plain JSON)
                try:
                    with open(src, "r", encoding="utf-8") as f:
                        doc = json.load(f)
                    keys = ("title", "seed", "seed_script", "bpm", "base_frequency_hz", "project_notes")
                    rows = "".join(f"<tr><td>{k}</td><td>{html.escape(str(doc.get(k))[:120])}</td></tr>" for k in keys if k in doc)
                    cards.append(card(name, f"<table>{rows}</table><div class=meta>{size:,} bytes · project</div>", "project"))
                except Exception:
                    cards.append(card(name, f"<div class=meta>{size:,} bytes · unrecognised .MCC</div>", "other"))
                continue
            kind = hdr.get("kind")
            if kind == "image":
                png = stem + ".png"; image_png(src, hdr, os.path.join(out, png))
                cards.append(card(name, f'<img src="{png}"><div class=meta>{hdr["width"]}×{hdr["height"]} · {size:,} bytes</div>', "image"))
            elif kind == "audio":
                wav = stem + ".wav"; audio_wav(src, hdr, os.path.join(out, wav))
                dur = int(hdr.get("frames", 0)) / max(1, int(hdr.get("sample_rate", 48000)))
                cards.append(card(name, f'<audio controls src="{wav}"></audio><div class=meta>{dur:.1f} s · {hdr.get("sample_rate")} Hz · {size:,} bytes</div>', "audio"))
            elif kind == "video":
                thumbs, n = video_thumbs(src, hdr, out, stem)
                body = "".join(f'<img class=thumb src="{t}">' for t in thumbs)
                wav = None
                if hdr.get("audio_rate"):
                    wav = os.path.join(out, stem + ".wav")
                    if not audio_wav(src, hdr, wav):
                        wav = None
                mp4 = stem + ".mp4"
                if video_mp4(src, hdr, os.path.join(out, mp4), wav):
                    body = f'<video controls src="{mp4}"></video>' + body
                elif wav:
                    body += f'<audio controls src="{os.path.basename(wav)}"></audio>'
                cards.append(card(name, body + f'<div class=meta>{n} frames · {hdr["width"]}×{hdr["height"]} @ {hdr.get("fps")} fps · {size:,} bytes</div>', "video"))
            elif kind == "package":
                listing = [m for bt, m, _p in blocks(src) if bt == b"F"]
                man = hdr.get("manifest") or {}
                rows = "".join(f"<li>{html.escape(m['path'])} <span class=meta>{m.get('size', 0):,} B</span></li>" for m in listing[:40])
                more = f"<li>… {len(listing) - 40} more</li>" if len(listing) > 40 else ""
                cards.append(card(name, f"<div>{html.escape(str(man.get('title', '')))}</div><ul>{rows}{more}</ul><div class=meta>{len(listing)} files · {size:,} bytes</div>", "package"))
            else:
                cards.append(card(name, f"<div class=meta>{html.escape(str(kind))} · {size:,} bytes</div>", "other"))
        except Exception as exc:  # noqa: BLE001
            cards.append(card(name, f"<div class=err>could not read: {html.escape(str(exc))}</div>", "other"))
    page = f"""<!doctype html><meta charset=utf-8><title>MCC gallery — {html.escape(os.path.basename(here))}</title>
<style>body{{background:#0b1020;color:#e8f0ff;font:14px system-ui,sans-serif;margin:24px}}
h1{{font-size:20px}} .grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:14px}}
.card{{background:#141b30;border:1px solid #2f6fe0;border-radius:10px;padding:12px}} .kind{{font-size:11px;color:#7fb3ff;letter-spacing:.1em}}
.title{{font-weight:700;margin:4px 0 8px;word-break:break-all}} img,video{{max-width:100%;border-radius:6px;background:#000}}
.thumb{{width:48%;margin:1%}} audio{{width:100%}} .meta{{color:#9cb0d0;font-size:12px;margin-top:6px}} table td{{padding:2px 6px;vertical-align:top}}
.err{{color:#ff8a8a}} ul{{padding-left:18px;margin:6px 0}}</style>
<h1>MCC gallery · {len(files)} file(s) in {html.escape(here)}</h1><div class=grid>{''.join(cards) or '<p>No .MCC files in this folder.</p>'}</div>"""
    index = os.path.join(out, "index.html")
    with open(index, "w", encoding="utf-8") as f:
        f.write(page)
    print(f"Gallery: {index}")
    try:
        webbrowser.open("file://" + index.replace(os.sep, "/"))
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
