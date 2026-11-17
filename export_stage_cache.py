"""Content-addressed cache for deterministic export audio-master stages.

The source mixdown remains owned by live_buffer/shared_mixdown. This cache
stores only the later DJ/master/PCM-WAV stage, allowing repeated exports of an
unchanged frozen project to skip that work without sharing mutable arrays.
"""
from __future__ import annotations
import hashlib
import json
import os
import shutil
import tempfile
import time

MAX_FILES = 6
MAX_BYTES = 2 * 1024 ** 3
_CHUNK = 8 * 1024 * 1024


def _root():
    base = os.environ.get("XDG_CACHE_HOME") or os.path.join(os.path.expanduser("~"), ".cache")
    path = os.path.join(base, "groovebox", "export_stages")
    os.makedirs(path, exist_ok=True)
    return path


def _file_digest(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            block = f.read(_CHUNK)
            if not block:
                break
            h.update(block)
    return h.digest()


def key_for_buffer(buf, sample_rate, project_path, options):
    """Hash exact float32 PCM + frozen project + output-stage options."""
    import numpy as np
    arr = np.asarray(buf, dtype=np.float32)
    if not arr.flags.c_contiguous:
        arr = np.ascontiguousarray(arr)
    h = hashlib.sha256()
    h.update(b"groovebox-export-audio-master-v1\0")
    h.update(str(int(sample_rate)).encode())
    h.update(str(tuple(arr.shape)).encode())
    h.update(memoryview(arr).cast("B"))
    h.update(_file_digest(project_path))
    h.update(json.dumps(options, sort_keys=True, separators=(",", ":"), default=str).encode())
    return h.hexdigest()


def lookup(key):
    root = _root()
    wav = os.path.join(root, str(key) + ".wav")
    meta = os.path.join(root, str(key) + ".json")
    if not os.path.isfile(wav) or not os.path.isfile(meta):
        return None
    try:
        with open(meta, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not data.get("complete") or not os.path.getsize(wav):
            return None
        os.utime(wav, None)
        return wav, float(data.get("master_rms", 0.0))
    except Exception:
        return None


def store(key, wav_path, master_rms):
    root = _root()
    dst = os.path.join(root, str(key) + ".wav")
    meta = os.path.join(root, str(key) + ".json")
    fd, tmp = tempfile.mkstemp(prefix=".export-stage-", suffix=".wav", dir=root)
    os.close(fd)
    try:
        shutil.copyfile(wav_path, tmp)
        os.replace(tmp, dst)
        mtmp = meta + ".part"
        with open(mtmp, "w", encoding="utf-8") as f:
            json.dump({"complete": True, "master_rms": float(master_rms), "ts": time.time()}, f)
        os.replace(mtmp, meta)
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass
    files = sorted((os.path.join(root, n) for n in os.listdir(root) if n.endswith(".wav")),
                   key=os.path.getmtime, reverse=True)
    total = 0
    for i, path in enumerate(files):
        total += os.path.getsize(path)
        if i >= MAX_FILES or total > MAX_BYTES:
            base = path[:-4]
            for candidate in (path, base + ".json"):
                try:
                    os.remove(candidate)
                except OSError:
                    pass
    return dst


def copy_cached(entry, destination):
    """Atomically copy a cached stage to the requested export path."""
    if not entry:
        return False
    src = entry[0]
    tmp = str(destination) + ".cache-part"
    try:
        os.makedirs(os.path.dirname(os.path.abspath(str(destination))), exist_ok=True)
        shutil.copyfile(src, tmp)
        os.replace(tmp, destination)
        return True
    except Exception:
        try:
            os.remove(tmp)
        except OSError:
            pass
        return False
