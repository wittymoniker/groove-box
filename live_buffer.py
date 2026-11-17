"""live_buffer.py — the project's audio, pre-rendered in the background while you work, saved as RAW (MGR).

Every edit in the main window re-arms a short debounce (an event, not a polling timer). When the project has been
still for a moment, and nothing is playing or exporting, the current mixdown is rendered in a separate process at
medium priority (the same out-of-process renderer Play uses) and written as a RAW Groovebox audio file (MG_R
header + float32 PCM — no encoding, so it is written in about the time it takes to copy the bytes).

Exports, Play and the Live Player look the buffer up by the project's render key first: when nothing changed since
the buffer was made, the mixdown stage is skipped entirely and an export only has to write its output file.

Files: <cache>/live_buffer/<key>.mgr (newest 4 kept, never more than 2 GB, never when the disk has < 2 GB free).
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import struct
import threading
import time

import numpy as np

MAX_FILES = 4
MAX_BYTES = 2 * 1024 ** 3
MIN_FREE = 2 * 1024 ** 3
DEBOUNCE_MS = 4000
_LOCK = threading.Lock()
_PUBLISH_LOCK = threading.Lock()
_PUBLISHING = set()


def cache_dir():
    base = os.environ.get("XDG_CACHE_HOME") or os.path.join(os.path.expanduser("~"), ".cache")
    d = os.path.join(base, "groovebox", "live_buffer")
    os.makedirs(d, exist_ok=True)
    return d


def hash_key(key):
    try:
        raw = json.dumps(key, sort_keys=True, default=str)
    except Exception:
        raw = repr(key)
    return hashlib.sha256(raw.encode("utf-8", "replace")).hexdigest()[:32]


def path_for(hkey):
    return os.path.join(cache_dir(), str(hkey) + ".mgr")

BUFFER_CONTRACT = "groovebox-live-pcm/2"

def describe_key(key, path=None):
    """Return a serializable cache descriptor; never treat it as project state."""
    hkey = hash_key(key)
    p = path or path_for(hkey)
    result = {"contract": BUFFER_CONTRACT, "render_key": hkey, "path": p, "available": False}
    try:
        if os.path.isfile(p):
            import mgr_format as mg
            with open(p, "rb") as f:
                _ver, tcode, meta = mg.read_header(f)
                payload = f.read()
            result.update({"available": True, "type_code": int(tcode), "sample_rate": int(meta.get("sr") or 0),
                           "frames": int(meta.get("n") or 0) // max(1, int(meta.get("ch") or 1)),
                           "channels": max(1, int(meta.get("ch") or 1)), "dtype": str(meta.get("dtype") or "float32"),
                           "bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()})
    except Exception:
        result["available"] = False
    return result

def validate_descriptor(descriptor, expected_key=None):
    """Validate a cache hint before reuse. False means re-render from frozen project."""
    if not isinstance(descriptor, dict) or descriptor.get("contract") != BUFFER_CONTRACT:
        return False
    if expected_key is not None and descriptor.get("render_key") != hash_key(expected_key):
        return False
    p = str(descriptor.get("path") or "")
    if not p or not os.path.isfile(p): return False
    try:
        current = describe_key_from_hash(descriptor.get("render_key"), p)
        return bool(current.get("available") and current.get("sha256") == descriptor.get("sha256")
                    and current.get("sample_rate", 0) > 0 and current.get("frames", 0) > 0
                    and current.get("channels", 0) > 0)
    except Exception:
        return False

def describe_key_from_hash(hkey, path):
    p = str(path); result = {"contract": BUFFER_CONTRACT, "render_key": str(hkey), "path": p, "available": False}
    try:
        import mgr_format as mg
        with open(p, "rb") as f:
            _ver, tcode, meta = mg.read_header(f); payload = f.read()
        ch = max(1, int(meta.get("ch") or 1)); n = int(meta.get("n") or 0)
        result.update({"available": bool(payload), "type_code": int(tcode), "sample_rate": int(meta.get("sr") or 0),
                       "frames": n // ch, "channels": ch, "dtype": str(meta.get("dtype") or "float32"),
                       "bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()})
    except Exception: pass
    return result


def write_raw(path, buf, sr, meta=None):
    """Fast RAW write: MG_R header + float32 frames (no WAV sibling, no encode). Atomic (tmp + rename)."""
    import mgr_format as mg
    arr = np.ascontiguousarray(np.asarray(buf, dtype=np.float32))
    ch = 1 if arr.ndim == 1 else int(arr.shape[1])
    m = dict(meta or {})
    m.update({"sr": int(sr), "n": int(arr.size), "ch": ch, "dtype": "float32", "ts": time.time()})
    tmp = path + ".part"
    with open(tmp, "wb") as f:
        mg.write_header(f, mg.TYPE["audio_pcm_f32"], m)
        f.write(arr.tobytes(order="C"))
    os.replace(tmp, path)
    return path


def read_raw(path):
    """(buffer frames × channels as float32, sr) from any RAW Groovebox audio file (f32, i24, preview audio)."""
    import mgr_format as mg
    with open(path, "rb") as f:
        _ver, tcode, meta = mg.read_header(f)
        raw = f.read()
    sr = int(meta.get("sr") or 44100)
    ch = max(1, int(meta.get("ch") or 1))
    if tcode == mg.TYPE.get("audio_pcm_i24"):
        b = np.frombuffer(raw[: len(raw) // 3 * 3], dtype=np.uint8).reshape(-1, 3)
        v = (b[:, 0].astype(np.int32) | (b[:, 1].astype(np.int32) << 8) | (b[:, 2].astype(np.int32) << 16))
        arr = (((v ^ 0x800000) - 0x800000).astype(np.float32) / float(1 << 23))
    else:
        arr = np.frombuffer(raw[: len(raw) // 4 * 4], dtype=np.float32)
    n = int(meta.get("n") or arr.size)
    arr = np.array(arr[:n], dtype=np.float32)
    if ch > 1:
        arr = arr[: arr.size // ch * ch].reshape(-1, ch)
    return arr, sr


def lookup_key(key):
    """(buffer, sr) for this render key, or None. A buffer that is empty, not finite or silent is deleted and
    ignored, so a bad background render can never replace the real mixdown."""
    p = path_for(hash_key(key))
    if not os.path.isfile(p):
        return None
    try:
        buf, sr = read_raw(p)
        if buf.size == 0 or not np.all(np.isfinite(buf)) or float(np.max(np.abs(buf))) < 1e-7 or int(sr) <= 0:
            try:
                os.remove(p)
            except OSError:
                pass
            return None
        os.utime(p)                                  # most recently used survives pruning
        return buf, sr
    except Exception:
        return None


def store_key(key, buf, sr):
    with _LOCK:
        d = cache_dir()
        try:
            if shutil.disk_usage(d).free < MIN_FREE:
                return None
        except OSError:
            return None
        p = write_raw(path_for(hash_key(key)), buf, sr, {"kind": "live_buffer"})
        files = sorted((os.path.join(d, f) for f in os.listdir(d) if f.endswith(".mgr")),
                       key=os.path.getmtime, reverse=True)
        total = 0
        for i, f in enumerate(files):
            total += os.path.getsize(f)
            if i >= MAX_FILES or total > MAX_BYTES:
                try:
                    os.remove(f)
                except OSError:
                    pass
        return p


def publish_shared_buffer(key, buf, sr):
    """Publish an already-rendered authoritative mixdown to the shared disk cache.

    Playback, Live Player and export consumers all converge on the same PCM
    buffer.  This lets work performed by any consumer warm the Live Buffer
    without launching a second renderer or touching the GUI from a worker.
    """
    try:
        arr = np.asarray(buf)
        if arr.size == 0 or int(sr) <= 0 or not np.isfinite(arr).all():
            return False
        if float(np.max(np.abs(arr))) < 1e-7:
            return False
        hkey = hash_key(key)
        with _PUBLISH_LOCK:
            if hkey in _PUBLISHING:
                return False
            _PUBLISHING.add(hkey)
        def _write():
            try:
                # A complete atomic write makes the same file safe for readers.
                store_key(key, arr, int(sr))
            except Exception:
                pass
            finally:
                with _PUBLISH_LOCK:
                    _PUBLISHING.discard(hkey)
        threading.Thread(target=_write, name="live-buffer-publish", daemon=True).start()
        return True
    except Exception:
        return False


def current_path(app):
    try:
        p = path_for(hash_key(app._shared_mixdown_key(None)))
        return p if os.path.isfile(p) else None
    except Exception:
        return None


def schedule(app):
    """Re-arm the debounce after an edit (cheap: restarts a single-shot timer)."""
    try:
        from PyQt6.QtCore import QTimer
    except Exception:
        return
    t = getattr(app, "_live_buffer_timer", None)
    if t is None:
        t = app._live_buffer_timer = QTimer(app)
        t.setSingleShot(True)
        t.setInterval(DEBOUNCE_MS)
        t.timeout.connect(lambda: _maybe_render(app))
    t.start()


def _busy(app):
    # A visible Live Player is not, by itself, a reason to suspend the cache.
    # It consumes the shared mixdown and can use the cached result; only active
    # real-time transport / recording and mutually-exclusive export work defer
    # a new full render.  This avoids the old permanent starvation condition
    # where simply leaving Live Player open prevented the buffer ever updating.
    if bool(getattr(app, "is_playing", False)) or bool(getattr(app, "_recording_active", False)) or bool(getattr(app, "_export_worker_busy", False)):
        return True
    job = getattr(app, "_canonical_commit", None)
    if job is not None and getattr(job, "running", False):
        return True
    sch = getattr(app, "_export_scheduler_obj", None)
    return bool(sch is not None and any(getattr(j, "state", "") == "running" for j in getattr(sch, "jobs", [])))


def _maybe_render(app):
    if _busy(app):
        schedule(app)                                # try again after the next quiet moment
        return
    try:
        key = app._shared_mixdown_key(None)
    except Exception:
        return
    if os.path.isfile(path_for(hash_key(key))):
        app._live_buffer_state = "ready"
        return
    # A debounce can fire more than once while the GUI is busy.  Keep one
    # render per host/key and do not launch duplicate worker processes.
    inflight = getattr(app, "_live_buffer_inflight_key", None)
    if inflight is not None:
        if inflight == key:
            app._live_buffer_state = "rendering"
            return
        # A newer project state supersedes the older render.  The old worker
        # may finish, but its completion callback will fail the key check.
        return
    render = getattr(app, "_render_in_process_async", None)
    if not callable(render):
        return
    app._live_buffer_state = "rendering"
    app._live_buffer_inflight_key = key

    def done(buf, sr, err=""):
        if getattr(app, "_live_buffer_inflight_key", None) == key:
            app._live_buffer_inflight_key = None
        try:
            if app._shared_mixdown_key(None) != key:
                app._live_buffer_state = "stale"
                schedule(app)
                return
        except Exception:
            app._live_buffer_state = "stale"
            schedule(app)
            return
        try:
            if buf is not None and (np.asarray(buf).size == 0 or float(np.max(np.abs(np.asarray(buf)))) < 1e-7):
                err = err or "silent render (not stored)"
        except Exception:
            err = err or "unreadable render"
        if err or buf is None:
            app._live_buffer_state = "failed: %s" % err
            return
        try:
            if app._shared_mixdown_key(None) != key:     # edited while rendering: the next debounce renders again
                app._live_buffer_state = "stale"
                schedule(app)
                return
        except Exception:
            return
        threading.Thread(target=lambda: (store_key(key, buf, sr), setattr(app, "_live_buffer_state", "ready")),
                         name="live-buffer-write", daemon=True).start()
    try:
        render("Live buffer", done)
    except Exception as exc:
        app._live_buffer_state = "failed: %s" % exc


def save_raw_now(app, dest_dir=None):
    """💾 Save RAW: the current buffer (live buffer or the in-memory mixdown) as a RAW MGR file in the exports
    folder. Returns the path, or None when the project has not been rendered yet (a render is then scheduled)."""
    buf = sr = None
    try:
        key = app._shared_mixdown_key(None)
        ent = (getattr(app, "_shared_mixdown_cache", {}) or {}).get(key)
        if ent is not None:
            buf, sr = ent[0], ent[1]
        else:
            hit = lookup_key(key)
            if hit is not None:
                buf, sr = hit
    except Exception:
        pass
    if buf is None:
        schedule(app)
        return None
    d = dest_dir or (str(app._audio_exports_dir()) if hasattr(app, "_audio_exports_dir") else os.path.expanduser("~"))
    os.makedirs(d, exist_ok=True)
    name = time.strftime("groovebox-raw-%Y%m%d-%H%M%S.mgr")
    return write_raw(os.path.join(d, name), np.asarray(buf), int(sr), {"kind": "raw_save"})
