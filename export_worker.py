"""Export render worker (EXPORT_WORKER_20261102).

The main window packs the canonical project document (the same document Save writes) and starts this
program as a separate process. The worker loads the document into its own headless engine, renders the
shared mixdown buffer, and writes it as a float32 .npy plus a small JSON note. The main window keeps its
own thread, GIL and event loop, so scrolling, editing and playing stay smooth while a long render runs.

    python export_worker.py JOB.json

JOB.json: {"project": "<project .MCC path>", "sample_rate": 48000, "out_npy": "...", "out_meta": "...",
           "kind": "audio", "purpose": "Export prepare"}

Progress lines on stdout:  PROGRESS <0-100> <text>   and finally   DONE <out_npy>   (or   FAIL <message>).
"""
from __future__ import annotations

import json
import os
import sys


def _say(*parts):
    print(" ".join(str(p) for p in parts), flush=True)


_QAPP = None
_APP = None


def _make_app():
    """One headless engine per worker process (a warm worker reuses it for many jobs)."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ["GROOVEBOX_HEADLESS_WORKER"] = "1"
    here = os.path.dirname(os.path.abspath(__file__))
    if here not in sys.path:
        sys.path.insert(0, here)
    from PyQt6.QtWidgets import QApplication
    global _QAPP, _APP
    _QAPP = QApplication.instance() or QApplication(["export_worker"])   # module-level: must outlive this call
    _say("PROGRESS", 2, "worker starting")
    import groovebox as g
    app = _APP = g.MathematiciansGrooveboxApp()
    try:
        t = getattr(app, "_autosave_timer", None)
        if t is not None:
            t.stop()                      # a worker never autosaves anyone's project
    except Exception:
        pass
    _say("PROGRESS", 8, "engine ready")
    return app




def _write_float_pcm_wav(path, sample_rate, samples, bit_depth=24, chunk_samples=1_048_576):
    """Write mono PCM WAV in bounded chunks, avoiding full-size packed-byte copies."""
    import struct
    import numpy as np
    data = np.asarray(samples, dtype=np.float32).reshape(-1)
    bits = 24 if int(bit_depth or 16) >= 24 else 16
    width = 3 if bits == 24 else 2
    data_bytes = int(data.size) * width
    if data_bytes > 0xFFFFFFFF - 36:
        raise ValueError("WAV soundtrack exceeds the RIFF 4 GiB limit")
    fmt = struct.pack("<HHIIHH", 1, 1, int(sample_rate), int(sample_rate) * width, width, bits)
    header = b"RIFF" + struct.pack("<I", 4 + len(b"WAVE") + 8 + len(fmt) + 8 + data_bytes) + b"WAVE"
    header += b"fmt " + struct.pack("<I", len(fmt)) + fmt
    header += b"data" + struct.pack("<I", data_bytes)
    tmp = str(path) + ".part"
    try:
        os.makedirs(os.path.dirname(os.path.abspath(str(path))), exist_ok=True)
        with open(tmp, "wb") as f:
            f.write(header)
            for start in range(0, int(data.size), max(1, int(chunk_samples))):
                x = np.clip(data[start:start + chunk_samples], -1.0, 1.0)
                if bits == 24:
                    q = np.rint(x * 8388607.0).astype(np.int32, copy=False)
                    u = q.astype(np.uint32, copy=False) & np.uint32(0xFFFFFF)
                    packed = np.empty((u.size, 3), dtype=np.uint8)
                    packed[:, 0] = (u & 0xFF).astype(np.uint8)
                    packed[:, 1] = ((u >> 8) & 0xFF).astype(np.uint8)
                    packed[:, 2] = ((u >> 16) & 0xFF).astype(np.uint8)
                    f.write(memoryview(packed).cast("B"))
                else:
                    q = np.rint(x * 32767.0).astype("<i2", copy=False)
                    f.write(memoryview(q).cast("B"))
            f.flush(); os.fsync(f.fileno())
        os.replace(tmp, path)
    except Exception:
        try: os.remove(tmp)
        except OSError: pass
        raise


def _reset_between_jobs(app, job):
    """WARM_WORKER_R31: undo per-job state so the next job starts clean."""
    if app is None:
        return
    for attr, val in (("_render_stem_filter", None), ("_render_raw_no_fx", False), ("_export_preset", None)):
        try:
            setattr(app, attr, val)
        except Exception:
            pass
    if job.get("kind") in ("stem_file", "bake_compare"):
        try:
            app._shared_mixdown_cache.clear()    # filtered / manifest renders must never be reused
        except Exception:
            pass


def run(job: dict, app=None) -> int:
    # The final video stitch is intentionally Qt-/Groovebox-free. It operates
    # only on already committed part files and a pre-rendered WAV soundtrack.
    if str(job.get("kind") or "") == "video_mux":
        import export_mux
        o = dict(job.get("options") or {})
        o.setdefault("out_file", job.get("out_file"))
        o.setdefault("out_meta", job.get("out_meta"))
        if not o.get("master_rms") and o.get("master_meta"):
            try:
                with open(str(o["master_meta"]), "r", encoding="utf-8") as f:
                    o["master_rms"] = float((json.load(f) or {}).get("master_rms", 0.0))
            except Exception:
                pass
        export_mux.run(o)
        return 0
    import numpy as np
    if app is None:
        app = _make_app()
    _say("PROGRESS", 10, "loading project")
    if not app.open_project_path(job["project"], show_message=False):
        _say("FAIL", "project document could not be loaded")
        return 2
    _say("PROGRESS", 15, "project loaded")
    try:   # R31: progress for EVERY job kind (video / stem / bake jobs used to look frozen at 15 %)
        app._set_work_progress = lambda label, pct, text="": _say("PROGRESS", 15 + int(max(0, min(100, pct)) * 0.8), text)
    except Exception:
        pass
    if job.get("kind") == "audio_master":
        # SHARED_MASTER_R31: the same mixdown call the video exporter makes, rendered once and shared.
        o = dict(job.get("options") or {})
        app._snapshot_render_inputs()
        buf, rate = app._get_shared_mixdown_buffer(purpose="Export prepare")
        # Bake the project DJ stage exactly once, before the master is shared by
        # parallel video workers. This prevents every part process from holding
        # a second full-song copy of the same audio array.
        try:
            buf = app._bake_dj_write(buf, rate)
        except Exception as exc:
            _say("WARN", f"DJ bake skipped: {type(exc).__name__}: {exc}")
        arr = np.asarray(buf, dtype=np.float32)
        # Sanitize in bounded slices; np.nan_to_num on a multi-GB song would
        # otherwise allocate another multi-GB buffer in each export worker.
        block = 1_048_576
        bad = False
        for start in range(0, int(arr.size), block):
            if not np.isfinite(arr[start:start + block]).all():
                bad = True
                break
        if bad:
            arr = np.nan_to_num(np.array(arr, dtype=np.float32, copy=True),
                                nan=0.0, posinf=1.0, neginf=-1.0)
        dst = str(o["master_npy"])
        tmp = dst + ".tmp.npy"
        np.save(tmp, arr, allow_pickle=False)
        os.replace(tmp, dst)
        master_rms = 0.0
        audio_path = str(o.get("audio_path") or "")
        if bool(o.get("include_audio")) and audio_path:
            # Prepare the exact master-bus audio once, alongside the shared
            # waveform. The later MP4 assembly worker never needs to load a
            # project, synth engine, or full-song NumPy buffer.
            _say("PROGRESS", 82, "preparing export soundtrack")
            duration_s = float(o.get("duration_s") or 0.0)
            n_audio = min(int(arr.shape[0]), int(round(duration_s * int(rate)))) if duration_s > 0 else int(arr.shape[0])
            audio_clip = np.asarray(arr[:max(1, n_audio)], dtype=np.float32)
            audio_clip, _clip_report = app._master_hardclip(audio_clip, rate, apply_master_vol=True)
            audio_clip = np.asarray(audio_clip, dtype=np.float32).reshape(-1)
            # RMS is accumulated in 1M-sample blocks; no full float64 copy.
            rms_sum = 0.0
            for _i in range(0, int(audio_clip.size), 1_048_576):
                _x = np.asarray(audio_clip[_i:_i + 1_048_576], dtype=np.float64)
                if _x.size:
                    rms_sum += float(np.dot(_x, _x))
            master_rms = float(np.sqrt(rms_sum / max(1, int(audio_clip.size)))) if audio_clip.size else 0.0
            bit_depth = 24 if int(o.get("bit_depth", 24) or 24) >= 24 else 16
            _write_float_pcm_wav(audio_path, int(rate), audio_clip, bit_depth=bit_depth)
            del audio_clip
        with open(dst + ".json", "w", encoding="utf-8") as f:
            json.dump({"sample_rate": int(rate), "frames": int(arr.shape[0]),
                       "dj_baked": True, "finite": True,
                       "audio_path": audio_path if os.path.isfile(audio_path) else "",
                       "master_rms": float(master_rms)}, f)
        with open(job["out_meta"], "w", encoding="utf-8") as f:
            json.dump({"file_path": "", "part_paths": [], "peak": 0.0, "sample_rate": int(rate),
                       "audio_path": audio_path if os.path.isfile(audio_path) else "",
                       "master_rms": float(master_rms)}, f)
        _say("DONE", dst)
        return 0
    if job.get("kind") == "video_file":
        return _write_video_file(app, job)
    if job.get("kind") == "stem_file":
        return _write_stem_file(app, job, np)
    if job.get("kind") == "project_obj":
        # R32.11.3: Project → OBJ (3D song model with the exact audio and project inside), in the worker.
        import project_obj
        _say("PROGRESS", 30, "rendering the song")
        app._snapshot_render_inputs()
        r = project_obj.export_project(app, str(job["out_file"]))
        with open(job["out_meta"], "w", encoding="utf-8") as f:
            json.dump({"file_path": r["path"], "samples": r["samples"], "sample_rate": r["sr"],
                       "vertices": r["vertices"], "bytes": r["bytes"]}, f)
        _say("DONE", r["path"])
        return 0
    if job.get("kind") == "bake_compare":
        os.environ["GROOVEBOX_VIDEO_EXPORT_GUI_THREAD"] = "1"
        o = dict(job.get("options") or {})
        report, identical, ratio = app._bake_compare_compute(o.get("target") or {}, str(o.get("file_label") or ""))
        with open(job["out_meta"], "w", encoding="utf-8") as f:
            json.dump({"file_path": "", "report": report, "identical": bool(identical), "rms_ratio": float(ratio)}, f)
        _say("DONE", "identical" if identical else "rms %.6f" % ratio)
        return 0
    sr = int(job.get("sample_rate") or 0)
    if sr > 0:
        app.preferred_sample_rate = sr
    try:
        app._set_work_progress = lambda label, pct, text="": _say("PROGRESS", 15 + int(max(0, min(100, pct)) * 0.8), text)
    except Exception:
        pass
    # EXPORT_SNAPSHOT_20261102: the render reads its settings from this snapshot; without it the worker rendered
    # the defaults (120 bpm, 32 rows) instead of the project's own values.
    app._snapshot_render_inputs()
    mr = job.get("max_rows")
    buf, rate = app._get_shared_mixdown_buffer(max_rows=(int(mr) if mr else None),
                                               purpose=str(job.get("purpose") or "Export prepare"),
                                               force=False)   # R31: same frozen state → reuse (keyed on full render state)
    buf = np.array(buf, dtype=np.float32, order="C", copy=True)   # private copy: the cached render stays pristine
    if job.get("kind") == "audio_file":
        return _write_audio_file(app, job, buf, rate, np)
    if job.get("final"):
        # GROOVEBOX_R23R_EXPORT_MERGE_20261103: Batch Export — this project's own DJ bake +
        # master volume + hard clip, so each file is exactly what its project would export.
        _say("PROGRESS", 96, "master bus")
        try:
            buf = app._bake_dj_write(buf, rate)
        except Exception:
            pass
        buf, _info = app._master_hardclip(buf, rate, apply_master_vol=True)
        buf = np.ascontiguousarray(np.asarray(buf, dtype=np.float32))
    np.save(job["out_npy"], buf)
    with open(job["out_meta"], "w", encoding="utf-8") as f:
        json.dump({"sample_rate": int(rate), "frames": int(buf.shape[0]), "channels": 1 if buf.ndim == 1 else int(buf.shape[1]),
                   "final": bool(job.get("final"))}, f)
    _say("DONE", job["out_npy"])
    return 0


class _SayEmitter:
    """Stand-in for a pyqtSignal: forwards progress to stdout for the parent window."""
    def __init__(self, kind, sink):
        self.kind, self.sink = kind, sink

    def emit(self, *args):
        self.sink(self.kind, args)


class _SaySignals:
    def __init__(self):
        self.result = None
        self.error = None
        self.progress = _SayEmitter("progress", self._on)
        self.finished = _SayEmitter("finished", self._on)
        self.failed = _SayEmitter("failed", self._on)

    def _on(self, kind, args):
        if kind == "progress":
            _say("PROGRESS", int(args[1]), str(args[2]))
        elif kind == "finished":
            self.result = args[1]
        else:
            self.error = str(args[1])


def _write_audio_file(app, job, buf, rate, np):
    """EXPORT_SCHEDULER_R31: the whole audio export runs here, in this process.

    One DJ bake, then the canonical post-render pipeline (_AudioExportTask: one master
    hardclip, resample, quantize, parts, stitch, verify). The parent window only queues
    the job and reads progress lines, so it never waits on a render or an encode.
    """
    import groovebox as g
    _say("PROGRESS", 90, "DJ bake")
    try:
        buf = app._bake_dj_write(buf, rate)
    except Exception:
        pass
    o = dict(job.get("options") or {})
    master = np.ascontiguousarray(np.nan_to_num(np.asarray(buf, dtype=np.float32), nan=0.0, posinf=1.0, neginf=-1.0))
    master.setflags(write=False)
    try:
        prov = app._export_provenance_payload()
        prov = prov.encode("utf-8") if isinstance(prov, str) else bytes(prov or b"")
    except Exception:
        prov = b""
    if int(o.get("bit_depth", 24) or 24) >= 32 or bool(o.get("clip_bypass")):
        return _write_unbounded_audio(app, job, master, rate, o, np)
    clip = float(o.get("clip_ratio_pct", 50.0))
    vol = float(o.get("master_volume", getattr(app, "master_volume", 0.72)))
    snap = g._AudioExportSnapshot(
        token=1, file_path=str(job["out_file"]), master=master,
        render_sample_rate=int(rate), output_sample_rate=int(o.get("output_sample_rate") or rate),
        bit_depth=int(o.get("bit_depth", 24)), n_parts=int(o.get("n_parts", 1)),
        audio_format=str(o.get("audio_format", "wav")),
        bitrate_kbps=(int(o["bitrate_kbps"]) if o.get("bitrate_kbps") else None),
        stitch_parts=bool(o.get("stitch_parts", True)), provenance_bytes=prov,
        clip_ratio_pct=clip, master_volume=max(0.0, min(1.0, vol)),
        cancel_event=None, preview=np.empty(0, dtype=np.float32))
    sig = _SaySignals()
    g._AudioExportTask(snap, app._write_audio_parts_and_final, sig).run()
    if sig.error:
        _say("FAIL", sig.error)
        return 3
    res = sig.result or {}
    with open(job["out_meta"], "w", encoding="utf-8") as f:
        json.dump({"file_path": str(res.get("file_path") or ""), "part_paths": list(res.get("part_paths") or []),
                   "peak": float(res.get("peak", 0.0) or 0.0), "sample_rate": int(res.get("sample_rate") or 0)}, f)
    _say("DONE", res.get("file_path") or job["out_file"])
    return 0


def _write_unbounded_audio(app, job, master, rate, o, np):
    """UNBOUNDED_OUTPUT_R31_6: 32-bit float and/or clip-bypass export.

    Master volume is applied; the hardclip runs only when clip bypass is OFF. The file is
    written as IEEE float WAV (32-bit) or, for integer depths, PCM clipped at full scale only.
    Multichannel masters (frames × channels) are written as-is.
    """
    from scipy.io import wavfile
    from scipy.signal import resample_poly
    from math import gcd
    vol = max(0.0, min(1.0, float(o.get("master_volume", getattr(app, "master_volume", 0.72)))))
    x = np.asarray(master, dtype=np.float64)
    if bool(o.get("clip_bypass")):
        _say("PROGRESS", 92, "master volume (clip bypassed)")
        x = x * vol
    else:
        _say("PROGRESS", 92, "canonical master hardclip")
        import groovebox as g
        flat, _rep = g._master_hardclip_snapshot(x.ravel(), float(o.get("clip_ratio_pct", 50.0)), vol)
        x = np.asarray(flat, dtype=np.float64).reshape(x.shape)
    out_sr = int(o.get("output_sample_rate") or rate)
    if out_sr != int(rate):
        _say("PROGRESS", 94, "resample %d → %d" % (int(rate), out_sr))
        d = gcd(int(rate), out_sr)
        x = resample_poly(x, out_sr // d, int(rate) // d, axis=0)
        if not bool(o.get("clip_bypass")):
            x = np.clip(x, -1.0, 1.0)              # resampler ringing must not exceed the clip
    path = str(job["out_file"])
    if not path.lower().endswith(".wav"):
        path = os.path.splitext(path)[0] + ".wav"
    bits = int(o.get("bit_depth", 24) or 24)
    _say("PROGRESS", 97, "write %s" % ("32-bit float" if bits >= 32 else "%d-bit PCM" % bits))
    if bits >= 32:
        data = x.astype(np.float32)
    elif bits >= 24:
        data = (np.rint(np.clip(x, -1.0, 1.0) * 8388607.0).astype(np.int32) << 8)
    else:
        data = np.rint(np.clip(x, -1.0, 1.0) * 32767.0).astype(np.int16)
    wavfile.write(path, out_sr, data)
    peak = float(np.max(np.abs(x))) if x.size else 0.0
    with open(job["out_meta"], "w", encoding="utf-8") as f:
        json.dump({"file_path": path, "part_paths": [], "peak": peak, "sample_rate": out_sr}, f)
    _say("DONE", path)
    return 0


def _write_stem_file(app, job, np):
    """EXPORT_SCHEDULER_R31: one stem (bus / rows / instruments filter) rendered and written here."""
    from audio_os_backend import write_wav
    o = dict(job.get("options") or {})
    app._render_stem_filter = {"bus": o.get("bus"), "rows": set(o["rows"]) if o.get("rows") else None,
                               "instruments": set(o["instruments"]) if o.get("instruments") else None}
    app._render_raw_no_fx = bool(o.get("raw"))
    app._snapshot_render_inputs()
    buf, sr = app._get_shared_mixdown_buffer(purpose="stem export", force=True)
    _say("PROGRESS", 92, "master hard clip")
    pcm, _info = app._master_hardclip(np.asarray(buf, dtype=np.float32), sr)
    write_wav(str(job["out_file"]), int(sr), np.asarray(pcm, dtype=np.float32))
    with open(job["out_meta"], "w", encoding="utf-8") as f:
        json.dump({"file_path": str(job["out_file"]), "part_paths": [], "peak": float(np.max(np.abs(pcm))) if np.size(pcm) else 0.0,
                   "sample_rate": int(sr)}, f)
    _say("DONE", job["out_file"])
    return 0


def _write_video_file(app, job):
    """EXPORT_SCHEDULER_R31: run the normal video exporter headless with the frozen options."""
    os.environ["GROOVEBOX_VIDEO_EXPORT_GUI_THREAD"] = "1"      # no UI to keep live here: run frame waits inline
    from PyQt6.QtWidgets import QMessageBox
    notes = {"fail": ""}

    def _info(*a, **k):
        _say("PROGRESS", 99, str(a[2] if len(a) > 2 else "")[:160].replace("\n", " "))
        return QMessageBox.StandardButton.Ok

    def _bad(*a, **k):
        notes["fail"] = str(a[2] if len(a) > 2 else "video export failed")[:400].replace("\n", " ")
        return QMessageBox.StandardButton.Ok
    QMessageBox.information = staticmethod(_info)
    QMessageBox.warning = staticmethod(_bad)
    QMessageBox.critical = staticmethod(_bad)
    o = dict(job.get("options") or {})
    _resume = bool(dict(o.get("preset") or {}).get("resume", True))
    QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes if _resume
                                        else QMessageBox.StandardButton.No)   # resume or restart .part sets
    app._export_preset = dict(o.get("preset") or {}, path=str(job["out_file"]))
    app.export_video_dialog(include_audio=bool(o.get("include_audio", True)), container=str(o.get("container", "mp4")))
    out = str(job["out_file"])
    if notes["fail"]:
        _say("FAIL", notes["fail"]); return 4
    pre = dict(o.get("preset") or {})
    if pre.get("only_parts") is not None:
        # PARALLEL_PARTS_R31: a part-set job succeeds when each of its .partNN segments exists.
        d = os.path.dirname(os.path.abspath(out)); stem = os.path.splitext(os.path.basename(out))[0]
        cont = str(o.get("container", "mp4"))
        missing = [i for i in pre["only_parts"] if not (os.path.isfile(os.path.join(d, f"{stem}.part{int(i):02d}.{cont}"))
                   and os.path.getsize(os.path.join(d, f"{stem}.part{int(i):02d}.{cont}")) > 64)]
        if missing:
            _say("FAIL", "part(s) not written: %s" % ", ".join(str(m) for m in missing)); return 6
        with open(job["out_meta"], "w", encoding="utf-8") as f:
            json.dump({"file_path": "", "part_paths": [], "peak": 0.0, "sample_rate": 0}, f)
        _say("DONE", "parts %s" % ",".join(str(i) for i in pre["only_parts"]))
        return 0
    if not (os.path.isfile(out) and os.path.getsize(out) > 0):
        _say("FAIL", "the video file was not written"); return 5
    with open(job["out_meta"], "w", encoding="utf-8") as f:
        json.dump({"file_path": out, "part_paths": [], "peak": 0.0, "sample_rate": 0}, f)
    _say("DONE", out)
    return 0


def serve(max_jobs=8) -> int:
    """WARM_WORKER_R31: read job.json paths from stdin, one per line; after each job print
    "JOBEND <rc>". Exits after max_jobs (the parent starts a fresh worker) or on EOF."""
    try:
        import parent_watch
        parent_watch.start()               # PARENT_WATCH_R31: no orphan renders after a crash
    except Exception:
        pass
    # Start light. A video_mux job must not instantiate QApplication or the
    # Groovebox synthesis engine; other jobs lazily create one reusable engine.
    app = None
    _say("READY")
    done = 0
    for line in sys.stdin:
        path = line.strip()
        if not path:
            continue
        job = {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                job = json.load(f)
            if str(job.get("kind") or "") != "video_mux" and app is None:
                app = _make_app()
            rc = int(run(job, app) or 0)
        except Exception as exc:
            _say("FAIL", f"{type(exc).__name__}: {exc}")
            rc = 1
        try:
            _reset_between_jobs(app, job)
        except Exception:
            pass
        _say("JOBEND", rc)
        done += 1
        if done >= max_jobs:
            break
    return 0


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print(__doc__)
        return 64
    if argv[0] == "--serve":
        try:
            n = int(argv[1]) if len(argv) > 1 else 8
        except ValueError:
            n = 8
        return serve(max(1, n))
    try:
        with open(argv[0], "r", encoding="utf-8") as f:
            job = json.load(f)
        return run(job)
    except Exception as exc:  # report, never hang the caller
        _say("FAIL", f"{type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
