"""live_master.py — master a whole Live Play take into a full-length, full-quality export.

A live take records the live output mix (composition + live keys + imported media + FX) in real time, and its
video is a capture of the live view (frames are repeated when the disk is busy). Mastering turns it into a finished
release:

  audio   DC removed, loudness brought to about −16 dBFS RMS (at most +12 dB), peaks held under −1 dBFS by a smooth
          block limiter (1 ms attack, 80 ms release) and a final soft clip; written as 24-bit WAV.
  video   REMASTER (default when the take has a recorded video): the live capture itself — camera, imported media
          and everything that was on screen — has its repeated (held) frames detected and dropped, the gaps rebuilt
          by motion-compensated interpolation at a steady frame rate (every frame filled in), then Lanczos-scaled to
          the target size, lightly sharpened and colour-balanced.
          RE-RENDER (for audio-only takes, or when chosen): every frame is rendered again offline with the export
          engine (scenograph, OBJ / GOAVA / L-system layers, video plan), driven by the mastered audio.
          Either way the result is muxed with the mastered audio (H.264 CRF 18, AAC 256 kb/s), full length.

Runs on a background thread (never the UI thread); progress(fraction, text) reports while it works.
"""
from __future__ import annotations

import math
import os
import subprocess
import wave

import numpy as np

SIZES = {"1080p": (1920, 1080), "720p": (1280, 720), "square 1080": (1080, 1080), "vertical 1080": (1080, 1920)}


def _load_audio(path, ff=None):
    """Any take audio → (sr, float array): PCM WAV directly; float WAV / FLAC / MP3 / OGG through FFmpeg."""
    try:
        return _read_wav(path)
    except Exception:
        ff = ff or _ffmpeg()
        if not ff:
            raise
        tmp = os.path.splitext(path)[0] + "_pcm24.wav"
        subprocess.run([ff, "-y", "-i", path, "-vn", "-acodec", "pcm_s24le", tmp], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return _read_wav(tmp)


def _read_wav(path):
    with wave.open(path, "rb") as w:
        sr, ch, sw, n = w.getframerate(), w.getnchannels(), w.getsampwidth(), w.getnframes()
        raw = w.readframes(n)
    if sw == 2:
        a = np.frombuffer(raw, dtype="<i2").astype(np.float64) / 32768.0
    elif sw == 3:
        b = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 3)
        a = (b[:, 0].astype(np.int32) | (b[:, 1].astype(np.int32) << 8) | (b[:, 2].astype(np.int32) << 16))
        a = np.where(a >= 1 << 23, a - (1 << 24), a).astype(np.float64) / float(1 << 23)
    elif sw == 4:
        a = np.frombuffer(raw, dtype="<i4").astype(np.float64) / 2147483648.0
    else:
        a = (np.frombuffer(raw, dtype=np.uint8).astype(np.float64) - 128.0) / 128.0
    return sr, a.reshape(-1, ch) if ch > 1 else a.reshape(-1, 1)


def _write_wav24(path, sr, x):
    x = np.clip(np.asarray(x, dtype=np.float64), -1.0, 1.0 - 1.0 / (1 << 23))
    i = np.round(x * (1 << 23)).astype(np.int32).reshape(-1)
    b = np.empty((i.size, 3), dtype=np.uint8)
    b[:, 0] = i & 0xFF; b[:, 1] = (i >> 8) & 0xFF; b[:, 2] = (i >> 16) & 0xFF
    with wave.open(path, "wb") as w:
        w.setnchannels(x.shape[1] if x.ndim > 1 else 1); w.setsampwidth(3); w.setframerate(int(sr))
        w.writeframes(b.tobytes())


def master_audio(x, sr, target_rms_db=-16.0, ceiling_db=-1.0, max_gain_db=12.0):
    x = np.asarray(x, dtype=np.float64)
    if x.ndim == 1:
        x = x[:, None]
    x = x - x.mean(axis=0, keepdims=True)
    rms = float(np.sqrt(np.mean(x * x))) or 1e-9
    g = 10.0 ** (min(max_gain_db, target_rms_db - 20.0 * math.log10(rms)) / 20.0)
    y = x * g
    c = 10.0 ** (ceiling_db / 20.0)
    blk = max(16, int(sr * 0.001))                                    # 1 ms blocks
    n = y.shape[0]
    nb = (n + blk - 1) // blk
    pad = np.zeros((nb * blk - n, y.shape[1]))
    peaks = np.abs(np.vstack([y, pad])).reshape(nb, blk, -1).max(axis=(1, 2))
    want = np.minimum(1.0, c / np.maximum(peaks, 1e-12))
    rel = math.exp(-1.0 / max(1.0, 0.080 * sr / blk))                # 80 ms release
    gr = np.empty(nb); cur = 1.0
    for k in range(nb):                                               # instant attack, smooth release
        cur = want[k] if want[k] < cur else (1.0 - rel) * want[k] + rel * cur
        gr[k] = cur
    env = np.interp(np.arange(n), np.arange(nb) * blk + blk / 2.0, gr)
    y = y * env[:, None]
    y = c * np.tanh(y / c)                                            # final soft safety clip
    return y


def _ffmpeg():
    try:
        import format_converter as fc
        return fc.find_ffmpeg(exit_on_missing=False)[0]
    except Exception:
        import shutil
        return __import__("sos_tools").which("ffmpeg")


def remaster_video(ff, src, master_wav, out_mp4, size="1080p", fps=30):
    """The recorded live video, remastered: held frames dropped, gaps rebuilt by motion interpolation at a steady
    rate, Lanczos-scaled into the frame, lightly sharpened and colour-balanced, muxed with the mastered audio."""
    W, H = SIZES.get(size, SIZES["1080p"])
    vf = ("mpdecimate=hi=768:lo=320:frac=0.33,"
          "minterpolate=fps=%d:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1,"
          "scale=%d:%d:flags=lanczos:force_original_aspect_ratio=decrease,"
          "pad=%d:%d:(ow-iw)/2:(oh-ih)/2:color=0x30343a,unsharp=5:5:0.55:5:5:0.0,"
          "eq=contrast=1.03:saturation=1.05,format=yuv420p" % (int(fps), W, H, W, H))
    cmd = [ff, "-y", "-i", src, "-i", master_wav, "-map", "0:v:0", "-map", "1:a:0", "-vf", vf, "-fps_mode", "cfr",
           "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-c:a", "aac", "-b:a", "256k", "-shortest",
           "-movflags", "+faststart", out_mp4]
    r = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    if r.returncode != 0:      # older FFmpeg: -vsync instead of -fps_mode
        cmd[cmd.index("-fps_mode"):cmd.index("-fps_mode") + 2] = ["-vsync", "cfr"]
        r = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    if r.returncode != 0 or not os.path.isfile(out_mp4):
        raise RuntimeError("video remaster failed: %s" % (r.stderr or "")[-300:])
    return out_mp4


def master_take(host, paths, size="1080p", fps=30, progress=None, video_mode="auto"):
    """paths: the take's files (an audio file and/or a video file). video_mode: "auto" (remaster the recorded video
    when there is one, else re-render), "remaster" or "rerender". Returns {"wav", "video", "frames", "mode"}."""
    say = progress or (lambda f, t: None)
    paths = [str(p) for p in (paths or []) if p]
    ff = _ffmpeg()
    vid = next((p for p in paths if p.lower().endswith((".mp4", ".mkv", ".mov", ".webm", ".avi"))), None)
    wav = next((p for p in paths if p.lower().endswith((".wav", ".flac", ".mp3", ".ogg"))), None)
    if wav is None:
        if vid is None or not ff:
            raise RuntimeError("the take has no audio to master")
        wav = os.path.splitext(vid)[0] + "_audio.wav"
        subprocess.run([ff, "-y", "-i", vid, "-vn", "-acodec", "pcm_s24le", wav], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    say(0.02, "mastering audio")
    sr, x = _load_audio(wav, ff)
    y = master_audio(x, sr)
    base = os.path.splitext(wav)[0]
    out_wav = base + "_master.wav"
    _write_wav24(out_wav, sr, y)
    result = {"wav": out_wav, "video": None, "frames": 0, "mode": None}
    if not ff:
        say(1.0, "mastered audio (no FFmpeg for video)")
        return result
    if vid is not None and video_mode in ("auto", "remaster"):
        say(0.10, "remastering the recorded video (filling every frame)…")
        out = remaster_video(ff, vid, out_wav, os.path.splitext(vid)[0] + "_master.mp4", size=size, fps=fps)
        result.update(video=out, mode="remaster")
        say(1.0, "mastered take: %s" % os.path.basename(out))
        return result
    W, H = SIZES.get(size, SIZES["1080p"])
    fps = max(12, min(60, int(fps)))
    dur = y.shape[0] / float(sr)
    n_frames = max(1, int(math.ceil(dur * fps)))
    import live_player as lp
    gb = lp._gb()
    eng = lp.clone_export_engine(gb, host)
    out_mp4 = base + "_master.mp4"
    cmd = [ff, "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (W, H), "-r", str(fps), "-i", "-",
           "-i", out_wav, "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "256k", "-shortest", "-movflags", "+faststart", out_mp4]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    mono = y.mean(axis=1)
    win = 2048
    try:
        for fi in range(n_frames):
            t = fi / float(fps)
            c0 = int(t * sr)
            seg = mono[max(0, c0 - win // 2): c0 + win // 2]
            if seg.size < win:
                seg = np.pad(seg, (0, win - seg.size))
            eng.set_waveform(seg.astype(np.float32), playhead=min(1.0, t / dur) if dur > 0 else 0.0, sr=sr)
            eng.t = t
            fr = eng.render_frame(W, H, export=True, frame_index=fi)
            fr = np.nan_to_num(np.asarray(fr), nan=0, posinf=255, neginf=0).astype(np.uint8, copy=False)
            try:
                fr = host._apply_video_plan_to_frame(fr, fi, n_frames)
            except Exception:
                pass
            fr = np.ascontiguousarray(np.asarray(fr)[:H, :W, :3], dtype=np.uint8)
            if fr.shape[0] != H or fr.shape[1] != W:
                fr = np.ascontiguousarray(np.pad(fr, ((0, H - fr.shape[0]), (0, W - fr.shape[1]), (0, 0))))
            proc.stdin.write(fr.tobytes())
            if fi % max(1, n_frames // 100) == 0:
                say(0.05 + 0.93 * fi / n_frames, "rendering frame %d / %d" % (fi + 1, n_frames))
    finally:
        try:
            proc.stdin.close()
        except Exception:
            pass
        rc = proc.wait()
    if rc != 0 or not os.path.isfile(out_mp4):
        raise RuntimeError("FFmpeg could not write the mastered video (exit %s)" % rc)
    result.update(video=out_mp4, frames=n_frames, mode="rerender")
    say(1.0, "mastered take: %s" % os.path.basename(out_mp4))
    return result
