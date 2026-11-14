"""Seed algebra for Groovebox — SEED_TOOLS_20261112 (replaces the R31 placeholders).

Every operation lands in the existing canonical seed spaces, so the results stay exact and deterministic:

  file_to_seed(path)            ANY file → "MGLB1:" byte-literal seed that rebuilds the file bit-for-bit
                                (mode="signal": its decoded audio as a literal MGLS1 spectral seed; images /
                                video as a literal MGLV1 pixel seed).  seed_to_file() is the inverse.
  find_common_seed(paths)       the structure every file shares: each file's long-term magnitude spectrum
                                (unit-energy), intersected with the fuzzy AND (element-wise minimum); rendered
                                with seed-determined phase and returned as a literal spectral seed.
  diff_to_seed(a, b)            (seed, location): the exact residual b − a over the region where they differ
                                ("MGLD1:" wrapper holding the offset + a literal spectral seed for media,
                                the replaced byte span for anything else).  apply_diff(a, seed) == b.
  plan_render(seed, …)          validated, ready-to-queue export job (+ which canonical the seed belongs to).
  synthesize_any(seed)          one seed → every medium it reaches (audio, video frames, bytes).

Inputs are anything spectral_canonical.coerce_signal accepts; media files are decoded with scipy / Pillow /
FFmpeg when present, and every other file is read as its bytes (so nothing is ever "unsupported").
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import shutil
import struct
import subprocess
import zlib
from typing import Dict, Optional, Sequence, Tuple

import numpy as np

import spectral_canonical as sc

BYTES_PREFIX = "MGLB1:"
DIFF_PREFIX = "MGLD1:"
AUDIO_EXT = {".wav", ".wave", ".flac", ".mp3", ".ogg", ".opus", ".aiff", ".aif", ".m4a", ".aac", ".wma"}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp", ".tif", ".tiff"}
VIDEO_EXT = {".mp4", ".mkv", ".webm", ".mov", ".avi", ".m4v", ".mpg", ".mpeg"}
RESOLUTIONS = {"480p": (854, 480), "720p": (1280, 720), "1080p": (1920, 1080), "1440p": (2560, 1440), "2160p": (3840, 2160)}


# ----------------------------------------------------------------------------- decoding anything
def _ffmpeg() -> Optional[str]:
    return shutil.which("ffmpeg")


def _decode_audio(path: str, sr: int) -> Tuple[np.ndarray, int]:
    if path.lower().endswith((".wav", ".wave")):
        try:
            import audio_os_backend as _aob          # audited audio boundary (build import policy)
            r, x = _aob.read_wav(path)
            return sc.coerce_signal(np.asarray(x), r)
        except Exception:
            pass
    ff = _ffmpeg()
    if not ff:
        raise RuntimeError("FFmpeg is needed to decode " + os.path.basename(path))
    r = subprocess.run([ff, "-v", "error", "-i", path, "-f", "f32le", "-ac", "2", "-ar", str(sr), "-"],
                       capture_output=True, timeout=3600)
    if r.returncode != 0 or not r.stdout:
        raise RuntimeError("decode failed: " + r.stderr.decode(errors="replace")[-200:])
    x = np.frombuffer(r.stdout, dtype="<f4")
    return sc.coerce_signal(x[: x.size // 2 * 2].reshape(-1, 2), sr)


def load_signal(source, sr: int = 48000) -> Tuple[np.ndarray, int, str]:
    """Path / array / bytes / seed → ((ch, n) float64, sample_rate, kind)."""
    if isinstance(source, (str, os.PathLike)) and os.path.isfile(str(source)):
        p = str(source); ext = os.path.splitext(p)[1].lower()
        if ext in AUDIO_EXT or ext in VIDEO_EXT:
            try:
                x, r = _decode_audio(p, sr)
                return x, r, "audio"
            except Exception:
                pass
        with open(p, "rb") as f:
            x, r = sc.coerce_signal(f.read(), sr)
        return x, r, "bytes"
    if isinstance(source, str) and source.startswith(BYTES_PREFIX):
        x, r = sc.coerce_signal(seed_to_bytes(source)[1], sr)
        return x, r, "bytes"
    x, r = sc.coerce_signal(source, sr)
    return x, r, "signal"


def _resample(x: np.ndarray, sr_from: int, sr_to: int) -> np.ndarray:
    if sr_from == sr_to:
        return x
    import audio_os_backend as _aob              # anti-aliased polyphase via the audited boundary
    a = np.asarray(x, dtype=np.float64)
    if a.ndim == 1:
        return np.asarray(_aob._resample_for_hardware(a, sr_from, sr_to), dtype=np.float64)
    return np.asarray(_aob._resample_for_hardware(a.T, sr_from, sr_to), dtype=np.float64).T


def _mono(x: np.ndarray) -> np.ndarray:
    return x.mean(axis=0) if x.shape[0] > 1 else x[0]


# ----------------------------------------------------------------------------- exact byte seeds
def bytes_to_seed(data: bytes, name: str = "") -> str:
    nm = os.path.basename(name).encode("utf-8")[:255]
    head = struct.pack("<4sB", b"MGLB", len(nm)) + nm + hashlib.sha256(data).digest()
    return BYTES_PREFIX + base64.b64encode(zlib.compress(head + data, 9)).decode("ascii")


def seed_to_bytes(seed: str) -> Tuple[str, bytes]:
    """→ (original file name, exact bytes). The SHA-256 stored in the seed is checked."""
    if not (isinstance(seed, str) and seed.startswith(BYTES_PREFIX)):
        raise ValueError("not a Groovebox byte seed (MGLB1:)")
    try:
        raw = zlib.decompress(base64.b64decode(seed[len(BYTES_PREFIX):].strip()))
    except Exception as exc:
        raise ValueError(f"byte seed is damaged or truncated ({exc})") from None
    if raw[:4] != b"MGLB":
        raise ValueError("not a Groovebox byte seed")
    n = raw[4]; name = raw[5:5 + n].decode("utf-8", "replace"); dig = raw[5 + n:37 + n]; data = raw[37 + n:]
    if hashlib.sha256(data).digest() != dig:
        raise ValueError("byte seed checksum mismatch")
    return name, data


def file_to_seed(path, mode: str = "exact", sr: int = 48000, video_size: Tuple[int, int] = (320, 180), fps: int = 24) -> str:
    """Inverse: any file → deterministic seed. exact: bit-for-bit; signal: its audio / pixels as a literal seed."""
    path = str(path)
    if mode == "exact":
        with open(path, "rb") as f:
            return bytes_to_seed(f.read(), path)
    ext = os.path.splitext(path)[1].lower()
    import video_canonical as vc
    if ext in IMAGE_EXT:
        from PIL import Image
        with Image.open(path) as im:
            return vc.analyse(vc.coerce_frames(np.asarray(im.convert("RGB"))), 1)
    if ext in VIDEO_EXT and mode == "video":
        ff = _ffmpeg(); w, h = video_size
        r = subprocess.run([ff, "-v", "error", "-i", path, "-vf", f"scale={w}:{h},fps={fps}", "-f", "rawvideo",
                            "-pix_fmt", "rgb24", "-"], capture_output=True, timeout=3600)
        fr = np.frombuffer(r.stdout, dtype=np.uint8); n = fr.size // (w * h * 3)
        return vc.analyse(fr[: n * w * h * 3].reshape(n, h, w, 3), fps)
    x, r, _ = load_signal(path, sr)
    return sc.analyse(x, r)


def seed_to_file(seed: str, out_dir: str) -> str:
    name, data = seed_to_bytes(seed)
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, os.path.basename(name) or ("seed-" + hashlib.sha256(data).hexdigest()[:12] + ".bin"))
    tmp = out + ".part"
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, out)
    return out


# ----------------------------------------------------------------------------- common structure
def _long_term_spectrum(x: np.ndarray, n_fft: int) -> np.ndarray:
    m = np.abs(sc.stft(_mono(x), n_fft)).mean(axis=0)
    e = float(np.sqrt(np.sum(m * m))) or 1.0
    return m / e                                         # unit energy: loudness never decides "common"


def find_common(paths: Sequence, seconds: float = 8.0, sr: int = 48000, n_fft: int = 2048) -> Dict:
    if len(paths) < 1:
        raise ValueError("give at least one file")
    specs, ids = [], []
    for p in paths:
        x, r, _ = load_signal(p, sr)
        specs.append(_long_term_spectrum(_resample(x, r, sr), n_fft))
        ids.append(hashlib.sha256(np.ascontiguousarray(x).tobytes()).hexdigest())
    S = np.stack(specs)
    common = S.min(axis=0)                               # fuzzy intersection (Gödel t-norm)
    share = float(np.sum(common ** 2))                   # 1.0 = identical timbre, 0 = nothing shared
    # render: the common magnitude with phases decided by the (order-independent) set of inputs
    st = sc._Stream(b"common|" + "|".join(sorted(ids)).encode())
    n = max(1, int(round(seconds * sr))); hop = n_fft // 2; frames = 1 + (n + 3 * n_fft) // hop
    ph = st.units(frames * common.size).reshape(frames, common.size) * 2 * np.pi
    sig = sc.istft(common[None, :] * np.exp(1j * ph), n, n_fft)
    pk = float(np.max(np.abs(sig))) or 1.0
    sig = (sig / pk * 0.8)[None, :]
    return {"seed": sc.analyse(sig, sr), "shared_energy": share, "spectrum": common, "inputs": len(paths),
            "sample_rate": sr, "peak_hz": float(np.argmax(common) * sr / n_fft)}


def find_common_seed(paths, **kw) -> str:
    """Return a literal seed that regenerates the structure shared by every file."""
    return find_common(paths, **kw)["seed"]


# ----------------------------------------------------------------------------- differences
def _wrap_diff(meta: Dict, inner: bytes) -> str:
    h = json.dumps(meta, sort_keys=True).encode("utf-8")
    return DIFF_PREFIX + base64.b64encode(zlib.compress(struct.pack("<I", len(h)) + h + inner, 9)).decode("ascii")


def _unwrap_diff(seed: str) -> Tuple[Dict, bytes]:
    if not (isinstance(seed, str) and seed.startswith(DIFF_PREFIX)):
        raise ValueError("not a Groovebox difference seed (MGLD1:)")
    try:
        raw = zlib.decompress(base64.b64decode(seed[len(DIFF_PREFIX):].strip()))
        n = struct.unpack("<I", raw[:4])[0]
        return json.loads(raw[4:4 + n].decode("utf-8")), raw[4 + n:]
    except Exception as exc:
        raise ValueError(f"difference seed is damaged or truncated ({exc})") from None


def _byte_diff(a: bytes, b: bytes) -> Tuple[str, str]:
    i = 0; m = min(len(a), len(b))
    while i < m and a[i] == b[i]:
        i += 1
    j = 0
    while j < m - i and a[len(a) - 1 - j] == b[len(b) - 1 - j]:
        j += 1
    a_end, b_end = len(a) - j, len(b) - j
    meta = {"kind": "bytes", "start": i, "a_end": a_end, "a_len": len(a), "b_len": len(b),
            "b_sha256": hashlib.sha256(b).hexdigest()}
    loc = "identical" if a == b else f"bytes {i}–{a_end} of A replaced by {b_end - i} bytes (B {i}–{b_end})"
    return _wrap_diff(meta, b[i:b_end]), loc


def diff_to_seed(path_a, path_b, sr: int = 48000, hop: int = 1024, rel_floor: float = 1e-6) -> Tuple[str, str]:
    """Return (seed, location_description) for the structural difference A → B."""
    a_kind = b_kind = None
    if isinstance(path_a, (str, os.PathLike)) and isinstance(path_b, (str, os.PathLike)) \
            and os.path.isfile(str(path_a)) and os.path.isfile(str(path_b)):
        ea, eb = (os.path.splitext(str(p))[1].lower() for p in (path_a, path_b))
        media = (AUDIO_EXT | VIDEO_EXT)
        if not (ea in media and eb in media):
            with open(path_a, "rb") as fa, open(path_b, "rb") as fb:
                return _byte_diff(fa.read(), fb.read())
    xa, ra, a_kind = load_signal(path_a, sr); xb, rb, b_kind = load_signal(path_b, sr)
    xa, xb = _resample(xa, ra, sr), _resample(xb, rb, sr)
    ch = max(xa.shape[0], xb.shape[0]); n = max(xa.shape[1], xb.shape[1])
    A = np.zeros((ch, n)); B = np.zeros((ch, n))
    A[:xa.shape[0], :xa.shape[1]] = xa if xa.shape[0] == ch else np.repeat(xa[:1], ch, 0)[:, :xa.shape[1]]
    B[:xb.shape[0], :xb.shape[1]] = xb if xb.shape[0] == ch else np.repeat(xb[:1], ch, 0)[:, :xb.shape[1]]
    d = B - A
    nb = (n + hop - 1) // hop
    e = np.zeros(nb * hop); e[:n] = np.sum(d * d, axis=0)
    e = e.reshape(nb, hop).sum(axis=1)
    ref = max(float(np.sum(A * A)), float(np.sum(B * B))) / max(1, nb)   # mean block energy of the louder input
    thr = max(1e-20, rel_floor * ref)
    hot = np.nonzero(e > thr)[0]
    if hot.size == 0:
        meta = {"kind": "signal", "start": 0, "length": 0, "sr": sr, "channels": ch, "n": n}
        return _wrap_diff(meta, b""), "identical (no audible difference)"
    s0, s1 = int(hot[0] * hop), int(min(n, (hot[-1] + 1) * hop))
    inner = sc.analyse(d[:, s0:s1], sr).encode("ascii")
    meta = {"kind": "signal", "start": s0, "length": s1 - s0, "sr": sr, "channels": ch, "n": n,
            "regions": int(np.sum(np.diff(np.concatenate([[0], (e > thr).astype(int), [0]])) == 1))}
    loc = f"{s0 / sr:.3f}–{s1 / sr:.3f} s (samples {s0}–{s1}, {meta['regions']} region(s), {ch} ch)"
    return _wrap_diff(meta, inner), loc


def apply_diff(a, seed: str, sr: int = 48000):
    """A + difference seed → B (bytes for byte diffs; (signal, sr) for signal diffs)."""
    meta, inner = _unwrap_diff(seed)
    if meta["kind"] == "bytes":
        if isinstance(a, (str, os.PathLike)) and os.path.isfile(str(a)):
            with open(a, "rb") as f:
                a = f.read()
        a = bytes(a)
        if len(a) != meta["a_len"]:
            raise ValueError("this difference seed was made from a different A (length differs)")
        b = a[:meta["start"]] + inner + a[meta["a_end"]:]
        if hashlib.sha256(b).hexdigest() != meta["b_sha256"]:
            raise ValueError("this difference seed was made from a different A (checksum differs)")
        return b
    xa, ra, _ = load_signal(a, meta["sr"])
    xa = _resample(xa, ra, meta["sr"])
    out = np.zeros((meta["channels"], meta["n"]))
    out[:xa.shape[0], :xa.shape[1]] = xa[:, :meta["n"]] if xa.shape[0] == meta["channels"] else \
        np.repeat(xa[:1], meta["channels"], 0)[:, :meta["n"]]
    if meta["length"]:
        d, _ = sc.synthesize_literal(inner.decode("ascii"))
        out[:, meta["start"]:meta["start"] + d.shape[1]] += d
    return out, meta["sr"]


# ----------------------------------------------------------------------------- rendering
def seed_kind(seed) -> str:
    if isinstance(seed, str):
        for pre, k in ((sc.LITERAL_PREFIX, "literal-audio"), ("MGLV1:", "literal-video"),
                       (BYTES_PREFIX, "literal-bytes"), (DIFF_PREFIX, "difference")):
            if seed.startswith(pre):
                return k
    return "generative"


def synthesize_any(seed, seconds: float = 8.0, sample_rate: int = 48000, frames: int = 96,
                   width: int = 320, height: int = 180, fps: int = 24) -> Dict:
    """One seed → every medium it reaches. Literal seeds rebuild their own medium exactly."""
    import video_canonical as vc
    k = seed_kind(seed)
    if k == "literal-audio":
        return {"kind": k, "audio": sc.synthesize_literal(seed), "video": None, "bytes": None}
    if k == "literal-video":
        return {"kind": k, "audio": None, "video": vc.synthesize_literal(seed), "bytes": None}
    if k == "literal-bytes":
        name, data = seed_to_bytes(seed)
        return {"kind": k, "audio": sc.coerce_signal(data, sample_rate), "video": (vc.coerce_frames(data), fps),
                "bytes": data, "name": name}
    if k == "difference":
        raise ValueError("a difference seed needs its A: use apply_diff(a, seed)")
    return {"kind": k, "audio": sc.synthesize_generative(seed, seconds=seconds, sample_rate=sample_rate, channels=2),
            "video": vc.synthesize_generative(seed, frames=frames, width=width, height=height, fps=fps), "bytes": None}


def plan_render(seed, duration_s=30, resolution="1080p", audio_rate=48000, engines=None, fps=30, fmt="mp4"):
    """Return a validated dict describing a ready-to-queue export job."""
    if isinstance(resolution, str) and resolution.lower() in RESOLUTIONS:
        w, h = RESOLUTIONS[resolution.lower()]
    elif isinstance(resolution, str) and "x" in resolution.lower():
        w, h = (int(v) for v in resolution.lower().split("x", 1))
    elif isinstance(resolution, (tuple, list)) and len(resolution) == 2:
        w, h = int(resolution[0]), int(resolution[1])
    else:
        raise ValueError(f"resolution must be one of {sorted(RESOLUTIONS)}, 'WxH' or (w, h)")
    w, h = max(16, w // 2 * 2), max(16, h // 2 * 2)                 # yuv420p needs even sizes
    duration_s = float(duration_s); audio_rate = int(audio_rate); fps = int(fps)
    if not (0 < duration_s <= 36000):
        raise ValueError("duration_s must be in (0, 36000]")
    if audio_rate not in (22050, 32000, 44100, 48000, 88200, 96000, 192000):
        raise ValueError("audio_rate must be a standard rate")
    s = seed if isinstance(seed, str) else str(seed)
    return {
        "seed": s, "seed_kind": seed_kind(s),
        "seed_sha256": hashlib.sha256(s.encode("utf-8")).hexdigest(),
        "duration_s": duration_s, "resolution": f"{w}x{h}", "width": w, "height": h, "fps": fps,
        "audio_rate": audio_rate, "engines": list(engines or ["SEEDED", "LOCK"]), "format": fmt,
        "frames": int(round(duration_s * fps)), "samples": int(round(duration_s * audio_rate)),
    }


# ----------------------------------------------------------------------------------------------- seed → A/V file
def render_av(seed, out_path: str, seconds: float = 8.0, size=(1920, 1080), fps: int = 30, strength: float = 0.6,
              base_size=(480, 270), sample_rate: int = 48000, crf: int = 18, progress=None) -> Dict:
    """SEED_AV_RENDER_R6: one seed → an MP4 with sound. The generative audio and video come from the seed
    (spectral_canonical / video_canonical); every frame then gets the context field (context_field.apply_frame)
    driven by the audio under that frame, so the picture reads the music: curvature = novelty (significance),
    hue = dominant key-chart degree, tint regions = spectral bands, light/dark mesh = 1/|det J|.

    Streams frames to ffmpeg (memory stays ~ the base-resolution clip), deterministic for a given seed."""
    import tempfile
    import wave
    import context_field as cf
    import video_canonical as vc
    ff = _ffmpeg()
    if not ff:
        raise RuntimeError("ffmpeg is required to write a video file")
    W, H = (RESOLUTIONS[size.lower()] if isinstance(size, str) else (int(size[0]), int(size[1])))
    if W < 16 or H < 16 or W % 2 or H % 2:
        raise ValueError("size must be even and at least 16 x 16")
    seconds = max(0.5, float(seconds)); fps = max(1, int(fps))
    n_frames = int(round(seconds * fps))
    sig, sample_rate = sc.synthesize_generative(seed, seconds=seconds, sample_rate=sample_rate, channels=2)
    audio = np.asarray(sig, dtype=np.float32)
    audio = audio.T if audio.ndim == 2 and audio.shape[0] <= 8 else audio      # (channels, n) → (n, channels)
    if audio.ndim == 1:
        audio = np.stack([audio, audio], axis=1)
    elif audio.shape[1] == 1:
        audio = np.repeat(audio, 2, axis=1)
    pk = float(np.max(np.abs(audio))) or 1.0
    audio = audio / pk * 0.89
    mono = audio.mean(axis=1)
    bw, bh = int(base_size[0]), int(base_size[1])
    clip, _fps = vc.synthesize_generative(seed, frames=n_frames, width=bw, height=bh, fps=fps)
    tmpdir = tempfile.mkdtemp(prefix="seed-av-")
    wav = os.path.join(tmpdir, "audio.wav")
    with wave.open(wav, "wb") as wf:
        wf.setnchannels(2); wf.setsampwidth(2); wf.setframerate(int(sample_rate))
        wf.writeframes((np.clip(audio, -1, 1) * 32767.0).astype("<i2").tobytes())
    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
    tmp_out = out_path + ".part.mp4"
    cmd = [ff, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-framerate", str(fps),
           "-i", "-", "-i", wav, "-map", "0:v:0", "-map", "1:a:0", "-c:v", "libx264", "-preset", "medium", "-crf", str(int(crf)),
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "256k", "-shortest", "-movflags", "+faststart", tmp_out]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    spf = sample_rate / float(fps)
    state = type("CtxState", (), {})()
    try:
        steps = 12
        for i in range(n_frames):
            a = int(i * spf); b = int(min(mono.size, a + max(2048, spf)))
            ctx = cf.video_state(state, mono[a:b], sample_rate, 432.0, steps)
            frame = cf._upsample_rgb(clip[i], H, W)
            frame = cf.apply_frame(frame, i / float(fps), ctx, strength)
            proc.stdin.write(frame.tobytes())
            if progress is not None and i % max(1, fps // 2) == 0:
                progress(i + 1, n_frames)
        proc.stdin.close()
        err = proc.stderr.read().decode(errors="replace")
        rc = proc.wait()
        if rc != 0:
            raise RuntimeError(f"ffmpeg failed ({rc}): {err[-800:]}")
        os.replace(tmp_out, out_path)
    except BaseException:
        try:
            proc.kill()
        except Exception:
            pass
        try:
            os.remove(tmp_out)
        except OSError:
            pass
        raise
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
    return {"path": out_path, "frames": n_frames, "fps": fps, "size": (W, H), "seconds": seconds,
            "seed_sha256": hashlib.sha256(str(seed).encode("utf-8")).hexdigest()[:16]}
