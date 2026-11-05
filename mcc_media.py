"""MCC media: lossless audio, video and package storage in the .MCC family.

GROOVEBOX_R23R_MCC_MEDIA_CODEC_20261101

A media .MCC is told apart from a project .MCC (plain JSON) by its magic. Layout:

    b"MCCMEDIA" | u8 version | u32 header_len | header JSON
    blocks:  b"B" | u8 type | u32 meta_len | meta JSON | u64 comp_len | deflate(payload)
    end:     b"E" | sha256(header JSON + every block's meta JSON and decoded payload)  (32 bytes)

Block types: A = audio PCM, K = video keyframe, D = video delta frame, F = file, I = image.

Codecs (all lossless, numpy + zlib only — no external codec needed):
  audio  "mcc-pcm-v1"   int16/int32: first-order prediction per channel (wrap-around),
                        float32: the same on its exact 32-bit integer view; then the
                        sample bytes are split into byte planes and deflated.
  video  "mcc-rgb-v1"   RGB24 frames; a keyframe every ``keyframe`` frames (deflate of
                        the frame), other frames are the byte-wise difference from the
                        previous frame (mod 256) deflated. Optional interleaved audio.
  pack   "mcc-pack-v1"  a file tree (games and exports) — one F block per file.
  image  "mcc-img-v2"   RGB/RGBA/gray still: each row picks the best of none / left / up / up-left
                        prediction (mod 256), residuals split into channel planes, deflated. Lossless.
                        (mcc-img-v1, left prediction only, still decodes.)
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import struct
import zlib
from pathlib import Path

import numpy as np

MAGIC = b"MCCMEDIA"
VERSION = 1
AUDIO_BLOCK = 1 << 16


# ------------------------------------------------------------------ framing
class _Writer:
    def __init__(self, path, header: dict, level: int = 6):
        self.path = str(path)
        self.tmp = self.path + ".part"
        self.f = open(self.tmp, "wb")
        self.h = hashlib.sha256()
        self.level = int(level)
        hj = json.dumps(header, sort_keys=True, separators=(",", ":")).encode()
        self.f.write(MAGIC + struct.pack(">BI", VERSION, len(hj)) + hj)
        self.h.update(hj)                       # the header is covered by the digest too

    def block(self, btype: bytes, meta: dict, payload: bytes):
        mj = json.dumps(meta, sort_keys=True, separators=(",", ":")).encode()
        self.h.update(mj)
        self.h.update(payload)
        comp = zlib.compress(payload, self.level)
        self.f.write(b"B" + btype + struct.pack(">I", len(mj)) + mj + struct.pack(">Q", len(comp)) + comp)

    def close(self):
        self.f.write(b"E" + self.h.digest())
        self.f.flush()
        try:
            os.fsync(self.f.fileno())
        except OSError:
            pass
        self.f.close()
        os.replace(self.tmp, self.path)


def read_header(path) -> dict:
    with open(path, "rb") as f:
        if f.read(8) != MAGIC:
            raise ValueError(f"{path}: not an MCC media file")
        ver, n = struct.unpack(">BI", f.read(5))
        if ver != VERSION:
            raise ValueError(f"{path}: unsupported MCC media version {ver}")
        return json.loads(f.read(n))


def _blocks(path):
    """Yield (type, meta, payload) and verify the end digest."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        if f.read(8) != MAGIC:
            raise ValueError(f"{path}: not an MCC media file")
        _ver, n = struct.unpack(">BI", f.read(5))
        h.update(f.read(n))
        while True:
            tag = f.read(1)
            if tag == b"E":
                if f.read(32) != h.digest():
                    raise ValueError(f"{path}: MCC media SHA-256 integrity check failed")
                return
            if tag != b"B":
                raise ValueError(f"{path}: truncated or corrupt MCC media")
            btype = f.read(1)
            (ml,) = struct.unpack(">I", f.read(4))
            mraw = f.read(ml)
            h.update(mraw)
            meta = json.loads(mraw)
            (cl,) = struct.unpack(">Q", f.read(8))
            payload = zlib.decompress(f.read(cl))
            h.update(payload)
            yield btype, meta, payload


def media_kind(path):
    """'audio' | 'video' | 'image' | 'package' for a media .MCC, else None (e.g. a project .MCC)."""
    try:
        with open(path, "rb") as f:
            if f.read(8) != MAGIC:
                return None
        return str(read_header(path).get("kind") or "") or None
    except (OSError, ValueError):
        return None


# ------------------------------------------------------------------ audio
def _planes(a: np.ndarray) -> bytes:
    b = np.ascontiguousarray(a).view(np.uint8).reshape(a.size, a.itemsize)
    return np.ascontiguousarray(b.T).tobytes()


def _unplanes(raw: bytes, dtype, n: int) -> np.ndarray:
    item = np.dtype(dtype).itemsize
    b = np.frombuffer(raw, dtype=np.uint8).reshape(item, n)
    return np.ascontiguousarray(b.T).view(dtype).reshape(n)


def _encode_pcm(x: np.ndarray) -> tuple[bytes, str]:
    """x: (frames, channels). Prediction residual on the exact integer view."""
    if x.dtype == np.float32:
        iv, kind = x.view(np.uint32), "f32"
    elif x.dtype == np.int16:
        iv, kind = x.view(np.uint16), "i16"
    elif x.dtype == np.int32:
        iv, kind = x.view(np.uint32), "i32"
    else:
        raise TypeError(f"unsupported PCM dtype {x.dtype}")
    res = np.empty_like(iv)
    res[0] = iv[0]
    res[1:] = iv[1:] - iv[:-1]                  # unsigned wrap-around: exact inverse by cumsum
    return _planes(res.T.copy().reshape(-1)), kind  # channel-major


def _decode_pcm(raw: bytes, kind: str, frames: int, channels: int) -> np.ndarray:
    udt = {"f32": np.uint32, "i16": np.uint16, "i32": np.uint32}[kind]
    res = _unplanes(raw, udt, frames * channels).reshape(channels, frames).T
    iv = np.cumsum(res, axis=0, dtype=udt)
    return iv.view({"f32": np.float32, "i16": np.int16, "i32": np.int32}[kind])


def encode_audio(path, samples, sample_rate: int, level: int = 6, extra: dict | None = None) -> str:
    x = np.asarray(samples)
    if x.ndim == 1:
        x = x[:, None]
    if x.dtype not in (np.float32, np.int16, np.int32):
        x = x.astype(np.float32)
    x = np.ascontiguousarray(x)
    hdr = {"kind": "audio", "codec": "mcc-pcm-v1", "sample_rate": int(sample_rate),
           "channels": int(x.shape[1]), "frames": int(x.shape[0]), "dtype": str(x.dtype)}
    if extra:
        hdr["extra"] = extra
    w = _Writer(path, hdr, level)
    for s in range(0, x.shape[0], AUDIO_BLOCK):
        chunk = x[s:s + AUDIO_BLOCK]
        payload, kind = _encode_pcm(chunk)
        w.block(b"A", {"frames": int(chunk.shape[0]), "pcm": kind}, payload)
    w.close()
    return str(path)


def decode_audio(path):
    """Return (samples (frames, channels), sample_rate, header). Exact inverse of encode_audio."""
    hdr = read_header(path)
    if hdr.get("kind") not in ("audio", "video"):
        raise ValueError(f"{path}: no audio track")
    ch = int(hdr.get("channels", hdr.get("audio_channels", 1)) or 1)
    parts = []
    for btype, meta, payload in _blocks(path):
        if btype == b"A":
            parts.append(_decode_pcm(payload, meta["pcm"], int(meta["frames"]), int(meta.get("channels", ch))))
    if not parts:
        return np.zeros((0, ch), dtype=np.float32), int(hdr.get("sample_rate", hdr.get("audio_rate", 48000))), hdr
    return np.concatenate(parts, axis=0), int(hdr.get("sample_rate", hdr.get("audio_rate", 48000))), hdr


def audio_to_wav(path, wav_path) -> str:
    import wave
    x, sr, _ = decode_audio(path)
    if x.dtype != np.int16:
        x = np.clip(np.asarray(x, dtype=np.float64), -1.0, 1.0)
        x = np.round(x * 32767.0).astype(np.int16)
    with wave.open(str(wav_path), "wb") as w:
        w.setnchannels(int(x.shape[1])); w.setsampwidth(2); w.setframerate(int(sr))
        w.writeframes(np.ascontiguousarray(x).tobytes())
    return str(wav_path)


# ------------------------------------------------------------------ video
class VideoWriter:
    """Lossless RGB24 video (+ optional interleaved audio) in one .MCC."""

    def __init__(self, path, width: int, height: int, fps: float, keyframe: int = 48,
                 audio_rate: int | None = None, audio_channels: int = 2, level: int = 6):
        self.w, self.h, self.keyframe = int(width), int(height), max(1, int(keyframe))
        hdr = {"kind": "video", "codec": "mcc-rgb-v1", "width": self.w, "height": self.h,
               "fps": float(fps), "keyframe": self.keyframe}
        if audio_rate:
            hdr.update({"audio_rate": int(audio_rate), "audio_channels": int(audio_channels), "audio_codec": "mcc-pcm-v1"})
        self._wr = _Writer(path, hdr, level)
        self._prev = None
        self.frames = 0

    def write(self, frame):
        f = np.ascontiguousarray(np.asarray(frame, dtype=np.uint8)[:, :, :3])
        if f.shape[:2] != (self.h, self.w):
            raise ValueError(f"frame {f.shape[:2]} != {(self.h, self.w)}")
        if self._prev is None or self.frames % self.keyframe == 0:
            self._wr.block(b"K", {"i": self.frames}, f.tobytes())
        else:
            self._wr.block(b"D", {"i": self.frames}, (f - self._prev).tobytes())   # uint8 wrap
        self._prev = f
        self.frames += 1

    def write_audio(self, samples):
        x = np.asarray(samples)
        if x.ndim == 1:
            x = x[:, None]
        if x.dtype not in (np.float32, np.int16, np.int32):
            x = x.astype(np.float32)
        x = np.ascontiguousarray(x)
        for s in range(0, x.shape[0], AUDIO_BLOCK):
            chunk = x[s:s + AUDIO_BLOCK]
            payload, kind = _encode_pcm(chunk)
            self._wr.block(b"A", {"frames": int(chunk.shape[0]), "pcm": kind, "channels": int(x.shape[1])}, payload)

    def close(self):
        self._wr.close()


def iter_video_frames(path):
    """Yield RGB24 frames (H, W, 3) of a media .MCC video, exactly as written."""
    hdr = read_header(path)
    w, h = int(hdr["width"]), int(hdr["height"])
    prev = None
    for btype, meta, payload in _blocks(path):
        if btype == b"K":
            prev = np.frombuffer(payload, dtype=np.uint8).reshape(h, w, 3).copy()
            yield prev
        elif btype == b"D":
            prev = prev + np.frombuffer(payload, dtype=np.uint8).reshape(h, w, 3)
            yield prev


def video_to_mp4(path, mp4_path, ffmpeg="ffmpeg") -> str:
    """Transcode a media .MCC video (and its audio) to MP4 for players that need it."""
    import subprocess
    import tempfile
    hdr = read_header(path)
    w, h, fps = int(hdr["width"]), int(hdr["height"]), float(hdr.get("fps", 24.0))
    tmpdir = tempfile.mkdtemp(prefix="mcc_")
    wav = None
    if hdr.get("audio_rate"):
        wav = os.path.join(tmpdir, "a.wav")
        audio_to_wav(path, wav)
    for vcodec in (["-c:v", "libx264", "-pix_fmt", "yuv420p"], ["-c:v", "mpeg4", "-q:v", "3", "-pix_fmt", "yuv420p"]):
        cmd = [ffmpeg, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}",
               "-r", f"{fps}", "-i", "-"]
        if wav:
            cmd += ["-i", wav, "-c:a", "aac", "-shortest"]
        cmd += vcodec + [str(mp4_path)]
        p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
        try:
            for fr in iter_video_frames(path):
                p.stdin.write(fr.tobytes())
            p.stdin.close()
        except (BrokenPipeError, OSError):
            pass
        if p.wait() == 0:
            return str(mp4_path)
    raise RuntimeError("ffmpeg could not transcode the MCC video")


# ------------------------------------------------------------------ packages
def pack_tree(src_dir, out_path, level: int = 9, manifest: dict | None = None, files=None, progress=None) -> str:
    """Store a directory tree (e.g. a generated game) as one .MCC package.

    files: optional iterable of paths inside src_dir (default: every file).
    progress: optional callback(done_files, total_files).
    """
    src = Path(src_dir)
    files = sorted(Path(p) if Path(p).is_absolute() else src / p for p in files) if files is not None \
        else sorted(p for p in src.rglob("*") if p.is_file())
    hdr = {"kind": "package", "codec": "mcc-pack-v1", "files": len(files)}
    if manifest:
        hdr["manifest"] = manifest
    w = _Writer(out_path, hdr, level)
    for i, p in enumerate(files):
        rel = p.relative_to(src).as_posix()
        st = p.stat()
        w.block(b"F", {"path": rel, "mode": st.st_mode & 0o777, "size": st.st_size}, p.read_bytes())
        if progress:
            progress(i + 1, len(files))
    w.close()
    return str(out_path)


def list_package(path) -> list:
    return [meta for btype, meta, _ in _blocks(path) if btype == b"F"]


def unpack_tree(path, dest_dir) -> list:
    """Extract a package .MCC (paths are confined to dest_dir)."""
    dest = Path(dest_dir).resolve()
    for _ in _blocks(path):        # verify the whole package before writing anything
        pass
    out = []
    for btype, meta, payload in _blocks(path):
        if btype != b"F":
            continue
        target = (dest / meta["path"]).resolve()
        if dest not in target.parents and target != dest:
            raise ValueError(f"refusing path outside the package: {meta['path']}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        try:
            os.chmod(target, int(meta.get("mode", 0o644)))
        except OSError:
            pass
        out.append(str(target))
    return out


def read_package_file(path, rel) -> bytes | None:
    for btype, meta, payload in _blocks(path):
        if btype == b"F" and meta.get("path") == rel:
            return payload
    return None


# ------------------------------------------------------------------ images
_IMG_FILTERS = ("none", "left", "up", "up-left")   # all decodable with whole-row numpy operations


def _img_residuals(img: np.ndarray):
    """Per-row best of four lossless predictors (uint8 wrap-around). Returns (filter ids, residual rows)."""
    h = img.shape[0]
    prev = np.zeros_like(img)
    prev[1:] = img[:-1]
    cands = []
    cands.append(img.copy())                                         # 0 none
    left = img.copy(); left[:, 1:] = img[:, 1:] - img[:, :-1]; cands.append(left)          # 1 left
    cands.append(img - prev)                                         # 2 up
    d = img - prev; ul = d.copy(); ul[:, 1:] = d[:, 1:] - d[:, :-1]; cands.append(ul)      # 3 up-left
    cost = np.stack([np.abs(c.astype(np.int16).reshape(h, -1) if False else
                            ((c.astype(np.int16) + 128) % 256 - 128).reshape(h, -1)).sum(axis=1) for c in cands])
    fid = np.argmin(cost, axis=0).astype(np.uint8)
    res = np.empty_like(img)
    for k in range(4):
        m = fid == k
        if m.any():
            res[m] = cands[k][m]
    return fid, res


def encode_image(path, image, level: int = 9, extra: dict | None = None) -> str:
    """MCC picture (codec mcc-img-v2): lossless; each row picks the best of none/left/up/up-left prediction,
    then the residual bytes are split into per-channel planes and deflated."""
    img = np.ascontiguousarray(np.asarray(image, dtype=np.uint8))
    if img.ndim == 2:
        img = img[:, :, None]
    h, w, c = img.shape
    if c not in (1, 3, 4):
        raise ValueError("image must have 1, 3 or 4 channels")
    fid, res = _img_residuals(img)
    planes = np.ascontiguousarray(np.transpose(res, (2, 0, 1)))       # channel planes
    hdr = {"kind": "image", "codec": "mcc-img-v2", "width": int(w), "height": int(h), "channels": int(c)}
    if extra:
        hdr["extra"] = extra
    wr = _Writer(path, hdr, level)
    wr.block(b"I", {"rows": int(h), "filters": "v2"}, fid.tobytes() + planes.tobytes())
    wr.close()
    return str(path)


def decode_image(path) -> np.ndarray:
    hdr = read_header(path)
    w, h, c = int(hdr["width"]), int(hdr["height"]), int(hdr.get("channels", 3))
    v2 = str(hdr.get("codec", "")) == "mcc-img-v2"
    for btype, _meta, payload in _blocks(path):
        if btype != b"I":
            continue
        if not v2:                                                   # mcc-img-v1: left prediction only
            res = np.frombuffer(payload, dtype=np.uint8).reshape(h, w, c)
            return np.cumsum(res, axis=1, dtype=np.uint8)
        fid = np.frombuffer(payload[:h], dtype=np.uint8)
        res = np.transpose(np.frombuffer(payload[h:], dtype=np.uint8).reshape(c, h, w), (1, 2, 0))
        out = np.empty((h, w, c), dtype=np.uint8)
        prev = np.zeros((w, c), dtype=np.uint8)
        for y in range(h):
            r = res[y]; k = int(fid[y])
            if k == 0:
                row = r
            elif k == 1:
                row = np.cumsum(r, axis=0, dtype=np.uint8)
            elif k == 2:
                row = r + prev
            else:
                row = np.cumsum(r, axis=0, dtype=np.uint8) + prev
            out[y] = row; prev = out[y]
        return out
    raise ValueError(f"{path}: no image block")


def read_picture(path) -> np.ndarray:
    """Any ordinary picture (PNG, JPEG, WebP, BMP, GIF, TIFF) as uint8 gray/RGB/RGBA. Needs Pillow."""
    from PIL import Image
    with Image.open(path) as im:
        if im.mode not in ("L", "RGB", "RGBA"):
            im = im.convert("RGBA" if ("A" in im.getbands() or im.mode == "P" and "transparency" in im.info) else "RGB")
        return np.asarray(im, dtype=np.uint8)


PICTURE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tif", ".tiff")


def picture_to_mcc(src, out_dir=None, level: int = 9) -> str:
    """Convert one ordinary picture to a lossless MCC picture next to it (or in out_dir). Never overwrites."""
    arr = read_picture(src)
    base = os.path.splitext(os.path.basename(str(src)))[0]
    folder = str(out_dir or os.path.dirname(os.path.abspath(str(src))))
    os.makedirs(folder, exist_ok=True)
    out, n = os.path.join(folder, base + ".MCC"), 1
    while os.path.exists(out):
        n += 1
        out = os.path.join(folder, base + ("_converted" if n == 2 else f"_converted{n - 1}") + ".MCC")
    return encode_image(out, arr, level=level, extra={"source": os.path.basename(str(src))})


def write_png(path, image) -> str:
    """Minimal dependency-free PNG writer (8-bit gray/RGB/RGBA, filter 0)."""
    img = np.ascontiguousarray(np.asarray(image, dtype=np.uint8))
    if img.ndim == 2:
        img = img[:, :, None]
    h, w, c = img.shape
    ctype = {1: 0, 3: 2, 4: 6}[c]
    raw = b"".join(b"\x00" + img[y].tobytes() for y in range(h))

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, ctype, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))
    with open(path, "wb") as f:
        f.write(png)
    return str(path)


def image_to_png(path, png_path) -> str:
    return write_png(png_path, decode_image(path))


def playable_path(path, ffmpeg: str | None = None) -> str:
    """A path ordinary players can open: the file itself unless it is media .MCC,
    in which case a cached WAV (audio) or MP4 (video) transcode is returned."""
    kind = media_kind(path)
    if kind not in ("audio", "video", "image"):
        return str(path)
    import tempfile
    st = os.stat(path)
    key = hashlib.sha256(f"{os.path.abspath(path)}|{st.st_size}|{st.st_mtime_ns}".encode()).hexdigest()[:16]
    cache = os.path.join(tempfile.gettempdir(), "groovebox_mcc_play")
    os.makedirs(cache, exist_ok=True)
    out = os.path.join(cache, key + {"audio": ".wav", "video": ".mp4", "image": ".png"}[kind])
    if not os.path.isfile(out):
        if kind == "image":
            image_to_png(path, out)
        elif kind == "audio":
            audio_to_wav(path, out)
        else:
            video_to_mp4(path, out, ffmpeg or "ffmpeg")
    return out


def convert_mcc_file(path, out_dir=None, ffmpeg="ffmpeg") -> str:
    """MCC_CONVERT_20261102: convert one media .MCC to an ordinary file next to it (or in out_dir).

    audio -> .wav, video -> .mp4 (H.264 + AAC), image -> .png, package -> a folder of its files.
    Never overwrites: an existing target gets _converted / _converted2 ... Returns the new path.
    """
    kind = media_kind(path)
    if kind not in ("audio", "video", "image", "package"):
        raise ValueError("not a media .MCC (a project .MCC opens with File > Open)")
    base = os.path.splitext(os.path.basename(str(path)))[0]
    folder = str(out_dir or os.path.dirname(os.path.abspath(str(path))))
    os.makedirs(folder, exist_ok=True)
    ext = {"audio": ".wav", "video": ".mp4", "image": ".png", "package": ""}[kind]
    out, n = os.path.join(folder, base + ext), 1
    while os.path.exists(out):
        n += 1
        out = os.path.join(folder, base + ("_converted" if n == 2 else f"_converted{n - 1}") + ext)
    if kind == "audio":
        return audio_to_wav(path, out)
    if kind == "video":
        return video_to_mp4(path, out, ffmpeg)
    if kind == "image":
        return image_to_png(path, out)
    unpack_tree(path, out)
    return out
