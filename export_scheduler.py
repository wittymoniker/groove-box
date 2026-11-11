"""EXPORT_SCHEDULER_R31: queue any number of exports, each one a frozen project state.

Pressing an export button freezes the project document *as it is at that moment*
(the same document Save writes) plus the export options, and queues a job. Jobs
run in separate worker processes (export_worker.py), so the main window keeps its
own interpreter, GIL and event loop: you can keep composing, playing, and pressing
more export buttons on other project states while earlier ones render.

Nothing here waits: QProcess signals drive the state machine, and nothing ever
calls processEvents(), QEventLoop.exec() or Future.result() on the UI thread.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import time
import uuid

from PyQt6.QtCore import QObject, QProcess, pyqtSignal, Qt
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget,
                             QTableWidgetItem, QHeaderView, QProgressBar, QSpinBox, QAbstractItemView)

QUEUED, RUNNING, DONE, FAILED, CANCELLED = "queued", "running", "done", "failed", "cancelled"


def default_parallel():
    """One job per two spare cores, at least 1, at most 3; leave a core for UI + audio."""
    try:
        cores = len(os.sched_getaffinity(0))
    except Exception:
        cores = os.cpu_count() or 2
    try:
        import memory_guard
        free_gb = float(memory_guard.snapshot(force=True).get("available", 0)) / 2**30
        if free_gb <= 0:
            raise RuntimeError("effective available memory unavailable")
    except Exception:
        try:
            import psutil
            free_gb = psutil.virtual_memory().available / 2**30
        except Exception:
            free_gb = 4.0
    by_ram = max(1, int(free_gb // 1.5))        # a headless worker peaks at roughly 1-1.5 GB
    try:   # R32.8 DYNAMIC_RAM: the memory budget / tier caps parallel exports
        import resource_governor as _rg
        by_ram = min(by_ram, int(_rg.recommend()["export_parallel"]))
    except Exception:
        pass
    # R31: video export is CPU-bound per frame, so use every core but one (RAM permitting).
    return max(1, min(6, cores - 1, by_ram))


class ExportJob:
    _next = 1

    def __init__(self, label, kind, out_file, options, project_doc):
        self.id = ExportJob._next; ExportJob._next += 1
        self.label, self.kind, self.out_file, self.options = label, kind, out_file, dict(options or {})
        self.state, self.progress, self.message = QUEUED, 0, "waiting"
        self.created = time.time(); self.started = self.finished = None
        self.result = {}
        self.proc = None
        self.tmp = tempfile.mkdtemp(prefix="groovebox_job%d_" % self.id)
        self.project = os.path.join(self.tmp, "project.MCC")
        self._doc = project_doc

    def elapsed(self):
        if not self.started:
            return 0.0
        return (self.finished or time.time()) - self.started


class ExportScheduler(QObject):
    changed = pyqtSignal(int)          # job id
    job_finished = pyqtSignal(object)  # ExportJob

    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.jobs: list[ExportJob] = []
        self.workers: list = []
        self.parallel = default_parallel()
        # EXPORT_WATCHDOG_20261111: keep the queue moving and fail stuck jobs.
        from PyQt6.QtCore import QTimer
        self._watchdog = QTimer(self)
        self._watchdog.setInterval(5000)
        self._watchdog.timeout.connect(self._watchdog_tick)
        self._watchdog.start()

    # -- public ---------------------------------------------------------
    def submit_audio(self, out_file, options, label=None, project_doc=None):
        """Freeze the current project state (or a stored one) and queue an audio export. Returns the job."""
        return self.submit_job("audio_file", out_file, options, label=label, project_doc=project_doc)

    def submit_video_parallel(self, out_file, preset, include_audio, container, label=None):
        """PARALLEL_PARTS_R31: a video export split across warm workers.

        The exporter already renders recoverable .partNN segments and treats each part as independently
        renderable (resume starts a part with a fresh engine). K sub-jobs each render a set of parts
        (video only, always resuming so siblings never delete each other's parts); a final job for the
        same file then finds every part done, writes the audio, and stitches. Returns the final job."""
        n_parts = max(1, int(preset.get("parts", 1) or 1))
        # R32.5 process planner: balanced part groups from measured per-part cost (no idle tail).
        try:
            import process_planner as _ppl
            _plan = _ppl.plan("video_part", n_parts, self.parallel)
            groups = _plan["groups"]
        except Exception:
            k0 = max(1, min(self.parallel, n_parts))
            groups = [list(range(i, n_parts, k0)) for i in range(k0)]
        groups = [g for g in groups if g]
        if not groups:
            groups = [list(range(n_parts))]
        k = len(groups)
        doc = self.app._project_snapshot()                      # one frozen state for every sub-job
        shared_dir = tempfile.mkdtemp(prefix="gb-master-")
        master_npy = os.path.join(shared_dir, "master.npy")
        out_dir = os.path.dirname(os.path.abspath(out_file)) or os.getcwd()
        os.makedirs(out_dir, exist_ok=True)
        stem = os.path.splitext(os.path.basename(out_file))[0]
        recovery_token = uuid.uuid4().hex[:12]
        # Keep the soundtrack beside the target, not inside the temporary
        # master directory: a SIGKILL/reboot can then resume the mux without
        # rebuilding the expensive audio master.
        audio_path = os.path.join(out_dir, f".{stem}.{recovery_token}.audio.full.part.wav") if include_audio else ""
        name = label or os.path.basename(out_file)
        duration_s = float(preset.get("duration_s", 0.0) or 0.0)
        mjob = self.submit_job("audio_master", out_file,
                               {"master_npy": master_npy, "audio_path": audio_path,
                                "include_audio": bool(include_audio), "duration_s": duration_s,
                                "bit_depth": int(preset.get("audio_bit_depth", 24) or 24)},
                               label="%s · audio master" % name, project_doc=doc)
        if not preset.get("resume", True):
            self._clear_parts(out_file, n_parts, container)    # "start fresh" once, before splitting
        subs = []
        for i, group in enumerate(groups):
            sub_preset = dict(preset, only_parts=list(group), stitch=False, resume=True,
                              master_npy=master_npy)
            subs.append(self.submit_job("video_file", out_file,
                                        {"preset": sub_preset, "include_audio": False, "container": str(container)},
                                        label="%s · parts %d/%d" % (name, i + 1, k),
                                        project_doc=doc, depends_on=[mjob.id]))
        # The final stage is a small standalone FFmpeg process. It never imports
        # Qt, Groovebox, or the project document, and never retains the full-song
        # float buffer while concatenating video parts.
        mux_options = {
            "preset": dict(preset, resume=True), "container": str(container),
            "include_audio": bool(include_audio), "audio_path": audio_path,
            "duration_s": duration_s, "master_meta": master_npy + ".json",
            "ffmpeg": str(preset.get("ffmpeg") or ""),
            "ffprobe": str(preset.get("ffprobe") or ""),
            "audio_codec": str(preset.get("audio_codec") or ""),
            "audio_bitrate_kbps": int(preset.get("audio_bitrate_kbps", preset.get("bitrate", 160)) or 160),
            "video_codec": str(preset.get("video_codec") or ""),
            "video_args": list(preset.get("video_args") or []),
            "provenance": str(preset.get("provenance") or ""),
        }
        final = self.submit_job("video_mux", out_file, mux_options,
                                label="%s · final mux" % name,
                                project_doc=doc, depends_on=[mjob.id] + [j.id for j in subs])
        final.cleanup_dirs = [shared_dir]
        return final

    @staticmethod
    def _clear_parts(out_file, n_parts, container):
        d = os.path.dirname(os.path.abspath(out_file))
        stem = os.path.splitext(os.path.basename(out_file))[0]
        for pi in range(int(n_parts)):
            for p in (os.path.join(d, f"{stem}.part{pi:02d}.{container}"), os.path.join(d, f"{stem}.part{pi:02d}.{container}.part")):
                try:
                    if os.path.isfile(p):
                        os.remove(p)
                except OSError:
                    pass

    def submit_job(self, kind, out_file, options, label=None, project_doc=None, depends_on=None):
        """kind: "audio_file" | "video_file". The project document is frozen now; the worker does the rest."""
        doc = project_doc if project_doc is not None else self.app._project_snapshot()   # in-memory; heavy work is in the worker
        job = ExportJob(label or os.path.basename(out_file), kind, out_file, options, doc)
        job.depends_on = list(depends_on or [])
        if str(kind) != "video_mux":
            try:
                self.app._atomic_write_document(job.project, doc)
                try:
                    import r32_finish as _rf
                    _rf.persist_job(job)      # R32.8: survives a reboot; resumed at next start
                except Exception:
                    pass
                import hashlib as _hl
                with open(job.project, "rb") as _f:
                    job.doc_hash = _hl.sha256(_f.read()).hexdigest()   # worker affinity: same state → same warm cache
            except Exception as exc:
                job.state, job.message = FAILED, "could not freeze project: %s" % exc
        job._doc = None
        self.jobs.append(job)
        self.changed.emit(job.id)
        self._pump()
        return job

    def _group(self, job_id):
        """All jobs of one split video export (part sets + their audio/stitch job)."""
        ids = {job_id}
        changed = True
        while changed:
            changed = False
            for j in self.jobs:
                deps = set(getattr(j, "depends_on", None) or [])
                if j.id in ids and deps - ids:
                    ids |= deps; changed = True
                if deps & ids and j.id not in ids:
                    ids.add(j.id); changed = True
        return ids

    def cancel(self, job_id):
        group = self._group(job_id)
        for j in self.jobs:
            if j.id in group and j.state in (QUEUED, RUNNING):
                was_running = j.state == RUNNING
                j.state, j.message = CANCELLED, ("cancelled · finished parts kept for resume" if j.kind == "video_file" else "cancelled")
                w = self._worker_of(j)
                if was_running and w is not None:
                    w.job = None
                    self._kill_worker(w)           # only this job's worker; others keep running
                j.finished = time.time()
                self._cleanup(j)
                self.changed.emit(j.id)
        self._pump()

    def clear_finished(self):
        self.jobs = [j for j in self.jobs if j.state in (QUEUED, RUNNING)]
        self.changed.emit(0)

    def active_count(self):
        return sum(1 for j in self.jobs if j.state == RUNNING)

    def pending_count(self):
        return sum(1 for j in self.jobs if j.state in (QUEUED, RUNNING))

    def set_parallel(self, n):
        self.parallel = max(1, min(6, int(n)))
        # Retire idle workers above the new limit.
        for w in list(self.workers):
            if len(self.workers) <= self.parallel:
                break
            if w.job is None:
                self._kill_worker(w)
        self._pump()

    def shutdown(self):
        for w in list(self.workers):
            self._kill_worker(w)
        for j in self.jobs:
            self._cleanup(j)

    # -- warm worker pool (WARM_WORKER_R31) ---------------------------------------
    JOBS_PER_WORKER = 8         # recycle a worker after this many jobs (bounds memory growth)
    IDLE_RETIRE_MS = 120000     # an idle warm worker exits after 2 minutes without work

    def _worker_of(self, job):
        return next((w for w in self.workers if w.job is job), None)

    def _spawn_worker(self):
        from PyQt6.QtCore import QProcessEnvironment, QTimer
        w = _Worker()
        proc = QProcess(self)
        proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        env = QProcessEnvironment.systemEnvironment()
        env.insert("QT_QPA_PLATFORM", "offscreen")
        env.insert("GROOVEBOX_HEADLESS_WORKER", "1")
        try:
            # R32.8: two cores stay free for the GUI thread + realtime audio callback
            share = max(1, (len(os.sched_getaffinity(0)) - 2) // max(1, self.parallel))
        except Exception:
            share = 1
        for var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "GROOVEBOX_THREADS"):
            env.insert(var, str(share))
        proc.setProcessEnvironment(env)
        w.proc = proc
        proc.readyReadStandardOutput.connect(lambda ww=w: self._read(ww))
        proc.finished.connect(lambda *_a, ww=w: self._worker_exited(ww))
        proc.errorOccurred.connect(lambda err, ww=w: self._worker_error(ww, err))
        w.idle_timer = QTimer(self); w.idle_timer.setSingleShot(True); w.idle_timer.setInterval(self.IDLE_RETIRE_MS)
        w.idle_timer.timeout.connect(lambda ww=w: self._kill_worker(ww) if ww.job is None else None)
        try:
            from groovebox_subprocess import helper_argv
            argv = helper_argv("export_worker", "--serve", str(self.JOBS_PER_WORKER))
        except Exception:
            argv = [sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "export_worker.py"),
                    "--serve", str(self.JOBS_PER_WORKER)]
        proc.start(argv[0], argv[1:])
        try:
            pid = int(proc.processId() or 0)
            if pid and hasattr(os, "setpriority"):
                os.setpriority(os.PRIO_PROCESS, pid, 15)   # renders never steal the UI / audio core
            if pid and hasattr(os, "sched_setscheduler") and hasattr(os, "SCHED_BATCH"):
                try:
                    os.sched_setscheduler(pid, os.SCHED_BATCH, os.sched_param(0))   # CPU-bound: longer slices, yields to interactive
                except Exception:
                    pass
            if pid and sys.platform.startswith("linux") and shutil.which("ionice"):
                import subprocess as _sp
                _sp.Popen(["ionice", "-c", "3", "-p", str(pid)], stdout=_sp.DEVNULL, stderr=_sp.DEVNULL)   # idle I/O class
        except Exception:
            pass
        self.workers.append(w)
        return w

    def _kill_worker(self, w):
        """Retire a worker without pretending its RSS is gone before QProcess exits."""
        w.dead = True
        try:
            w.idle_timer.stop()
        except Exception:
            pass
        proc = getattr(w, "proc", None)
        if proc is not None:
            try:
                if proc.state() != QProcess.ProcessState.NotRunning:
                    proc.kill()
                    return  # _worker_exited removes it and advances queued work.
            except Exception:
                try:
                    proc.kill()
                    return
                except Exception:
                    pass
        if w in self.workers:
            self.workers.remove(w)

    @staticmethod
    def _is_video_stitch_job(job, jobs):
        """True for the final video/mux job that depends on one or more part jobs."""
        kind = getattr(job, "kind", "")
        if kind not in ("video_file", "video_mux"):
            return False
        preset = dict((getattr(job, "options", {}) or {}).get("preset") or {})
        if kind == "video_file" and preset.get("only_parts") is not None:
            return False
        dep_ids = set(getattr(job, "depends_on", None) or [])
        if not dep_ids:
            return False
        by_id = {j.id: j for j in jobs}
        return any(
            (by_id.get(dep_id) is not None)
            and getattr(by_id[dep_id], "kind", "") == "video_file"
            and dict((getattr(by_id[dep_id], "options", {}) or {}).get("preset") or {}).get("only_parts") is not None
            for dep_id in dep_ids
        )

    def _retire_idle_workers_for_stitch(self):
        """Release every warm worker before final mux; wait asynchronously for OS reclamation."""
        retiring = False
        for w in list(self.workers):
            if w.job is not None:
                continue
            if not w.dead:
                self._kill_worker(w)
            proc = getattr(w, "proc", None)
            try:
                running = proc is not None and proc.state() != QProcess.ProcessState.NotRunning
            except Exception:
                running = False
            retiring = retiring or running
        return retiring

    def _watchdog_tick(self):
        """EXPORT_WATCHDOG_20261111: re-pump the queue and fail jobs that make no progress."""
        try:
            now = time.monotonic()
            for j in list(self.jobs):
                if j.state != RUNNING:
                    continue
                last = float(getattr(j, "_last_progress_at", 0.0) or 0.0)
                if last <= 0:
                    j._last_progress_at = now
                    continue
                # Audio should move within a few minutes; video parts can be slower.
                limit = 600.0 if j.kind in ("video_file", "video_mux") else 300.0
                if now - last > limit:
                    retries = int(getattr(j, "_stall_retries", 0) or 0)
                    if retries < 1:
                        j._stall_retries = retries + 1
                        j.state = QUEUED
                        j.started = None
                        j.finished = None
                        j.message = "no progress for %.0f s · re-queued" % (now - last)
                        j._last_progress_at = now
                        w = self._worker_of(j)
                        if w is not None:
                            w.job = None
                            self._kill_worker(w)
                        self.changed.emit(j.id)
                    else:
                        j.result["fail"] = "export stalled (no progress for %.0f s)" % (now - last)
                        self._finish(j, ok=False)
            self._pump()
        except Exception:
            pass

    def _pump(self):
        while self.active_count() < self.parallel:
            nxt = None
            for j in self.jobs:
                if j.state != QUEUED:
                    continue
                deps = [d for d in self.jobs if d.id in (getattr(j, "depends_on", None) or [])]
                if any(d.state in (FAILED, CANCELLED) for d in deps):
                    j.state, j.message, j.finished = FAILED, "a part job failed or was cancelled · finished parts kept for resume", time.time()
                    self._cleanup(j); self.changed.emit(j.id); self.job_finished.emit(j)
                    continue
                if all(d.state == DONE for d in deps):
                    nxt = j
                    break
            if nxt is None:
                return
            # Final MP4/MKV/WebM assembly is a distinct memory peak. Part workers
            # retain QApplication/project/cache state after finishing; retire all
            # idle warm workers first, then launch the mux in a clean process.
            if self._is_video_stitch_job(nxt, self.jobs):
                # Do not overlap the mux peak with unrelated exports either.
                if any(w.job is not None for w in self.workers):
                    # EXPORT_WATCHDOG_20261111: do not freeze the whole queue.
                    # Skip this stitch for now and try a non-stitch job.
                    skipped_stitch = True
                    nxt = None
                    for j in self.jobs:
                        if j.state != QUEUED or self._is_video_stitch_job(j, self.jobs):
                            continue
                        deps = [d for d in self.jobs if d.id in (getattr(j, "depends_on", None) or [])]
                        if all(d.state == DONE for d in deps):
                            nxt = j
                            break
                    if nxt is None:
                        return
                elif self._retire_idle_workers_for_stitch():
                    return  # QProcess.finished will re-enter _pump; never wait on Qt.
            free = [w for w in self.workers if w.job is None and not w.dead and w.served < self.JOBS_PER_WORKER]
            h = getattr(nxt, "doc_hash", None)
            w = next((w for w in free if h and w.last_hash == h), None) or (free[0] if free else None)
            if w is None:
                if len(self.workers) >= self.parallel:
                    # every worker busy or due for recycling: retire one idle, else wait
                    idle = next((w for w in self.workers if w.job is None), None)
                    if idle is None:
                        return
                    self._kill_worker(idle)
                w = self._spawn_worker()
            self._start(nxt, w)

    def _start(self, job, w):
        jpath = os.path.join(job.tmp, "job.json")
        payload = {"project": job.project, "kind": job.kind, "sample_rate": int(job.options.get("render_sample_rate") or 0),
                   "out_npy": os.path.join(job.tmp, "unused.npy"), "out_meta": os.path.join(job.tmp, "result.json"),
                   "out_file": job.out_file, "options": job.options, "purpose": "Export " + job.label,
                   "max_rows": job.options.get("max_rows")}
        try:
            with open(jpath, "w", encoding="utf-8") as f:
                json.dump(payload, f)
        except Exception as exc:
            job.state, job.message = FAILED, str(exc); self.changed.emit(job.id); return
        w.job = job
        w.served += 1
        w.last_hash = getattr(job, "doc_hash", None)
        try:
            w.idle_timer.stop()
        except Exception:
            pass
        job.state, job.started = RUNNING, time.time()
        job._last_progress_at = time.monotonic()
        job.message = "rendering (warm worker)" if w.served > 1 else "starting worker"
        line = (jpath + "\n").encode("utf-8")
        proc = w.proc
        def _send():
            try:
                if proc is not None and proc.state() != QProcess.ProcessState.NotRunning:
                    n = proc.write(line)
                    if n is not None and int(n) < 0:
                        job.result["fail"] = "could not send job to worker"
                        self._finish(job, ok=False)
                        self._pump()
            except Exception as exc:
                job.result["fail"] = "worker write failed: %s" % exc
                self._finish(job, ok=False)
                self._pump()
        try:
            if proc is not None and proc.state() == QProcess.ProcessState.Running:
                _send()
            elif proc is not None:
                # Process not yet running: send as soon as it starts.
                proc.started.connect(_send)
            else:
                job.result["fail"] = "no worker process"
                self._finish(job, ok=False)
        except Exception:
            _send()
        self.changed.emit(job.id)

    def _read(self, w):
        if w.proc is None:
            return
        w.buf += bytes(w.proc.readAllStandardOutput()).decode("utf-8", "replace")
        *lines, w.buf = w.buf.split("\n")
        for line in lines:
            job = w.job
            if line.startswith("JOBEND"):
                parts = line.split()
                rc = int(parts[1]) if len(parts) > 1 and parts[1].lstrip("-").isdigit() else 1
                w.job = None
                if job is not None:
                    self._finish(job, ok=(rc == 0))
                if w.served >= self.JOBS_PER_WORKER:
                    self._kill_worker(w)           # it exits by itself too; replace on demand
                else:
                    try: w.idle_timer.start()
                    except Exception: pass
                self._pump()
                continue
            if job is None:
                continue
            if line.startswith("PROGRESS "):
                p = line.split(" ", 2)
                try:
                    job.progress = max(job.progress, int(p[1]))
                except Exception:
                    pass
                job.message = p[2] if len(p) > 2 else job.message
                job._last_progress_at = time.monotonic()
                # R32.8: progress lines arrive many times a second per worker; repainting the
                # jobs table for each one starved the GUI thread (keys stopped playing during
                # two exports). Emit at most 4×/s per job; state changes still emit at once.
                now = time.monotonic()
                if now - getattr(job, "_r32_last_emit", 0.0) < 0.25:
                    continue
                job._r32_last_emit = now
            elif line.startswith("FAIL "):
                job.message = line[5:]
                job.result["fail"] = line[5:]
            self.changed.emit(job.id)

    def _worker_error(self, w, err):
        if err == QProcess.ProcessError.FailedToStart:
            job, w.job = w.job, None
            self._kill_worker(w)
            if job is not None:
                job.result["fail"] = "worker failed to start"
                self._finish(job, ok=False)
            self._pump()

    def _worker_exited(self, w):
        job, w.job = w.job, None
        if w in self.workers:
            self.workers.remove(w)
        w.dead = True
        try:
            exit_code = int(w.proc.exitCode()) if w.proc is not None else -1
        except Exception:
            exit_code = -1
        try:
            w.proc.deleteLater()
        except Exception:
            pass
        if job is not None and job.state == RUNNING:
            # Linux OOM-killer / external SIGKILL is reported by Qt as exit code 9.
            # Video part files are atomic/recoverable. Resume from saved video parts
            # in a fresh process instead of throwing away a long render.
            retries = int(getattr(job, "_worker_kill_retries", 0) or 0)
            if job.kind in ("video_file", "video_mux", "audio_master") and exit_code == 9 and retries < 2:
                job._worker_kill_retries = retries + 1
                job.state = QUEUED
                job.started = None
                job.finished = None
                job.result.pop("fail", None)
                job.message = f"worker was killed (code 9) · restarting from saved render artifacts ({retries + 1}/2)"
                job.progress = min(98, max(job.progress, 85))
                self.changed.emit(job.id)
            else:
                job.result.setdefault("fail", "worker exited during the job (code %s)" % exit_code)
                self._finish(job, ok=False)
        self._pump()

    def _finish(self, job, ok):
        if job.finished is not None:
            return
        job.finished = time.time()
        try:
            import r32_finish as _rf
            _rf.forget_job(job)
        except Exception:
            pass
        if job.state != CANCELLED:
            ok = ok and not job.result.get("fail")
            meta = os.path.join(job.tmp, "result.json") if job.tmp else ""
            if ok and meta and os.path.isfile(meta):
                try:
                    with open(meta, "r", encoding="utf-8") as f:
                        job.result.update(json.load(f))
                except Exception:
                    pass
            # EXPORT_WATCHDOG_20261111: a zero exit is not enough — the file must exist.
            if ok and job.kind in ("audio_file", "video_file", "video_mux"):
                out = str(job.result.get("file_path") or job.out_file or "")
                if not out or not os.path.isfile(out) or os.path.getsize(out) <= 0:
                    ok = False
                    job.result["fail"] = "export reported success but the output file is missing or empty"
            job.state = DONE if ok else FAILED
            job.progress = 100 if ok else job.progress
            job.message = ("saved %s in %.1f s" % (os.path.basename(job.result.get("file_path") or job.out_file), job.elapsed())) if ok \
                else (job.result.get("fail") or "worker reported an error")
        self._cleanup(job)
        self.changed.emit(job.id)
        try:
            if ok and job.started:
                import process_planner as _ppl
                _op = (job.options or {}).get("preset", {}).get("only_parts") if isinstance(job.options, dict) else None
                _ppl.record("video_part" if _op else str(job.kind), max(0.1, time.time() - job.started), len(_op) if _op else 1)
        except Exception:
            pass
        self.job_finished.emit(job)

    @staticmethod
    def _cleanup(job):
        # R32.8: multi-GB part folders are removed on a background thread, not the GUI thread
        dirs = [job.tmp] if job.tmp else []
        dirs += list(getattr(job, "cleanup_dirs", None) or [])   # SHARED_MASTER_R31: the shared audio master
        job.tmp = ""
        job.cleanup_dirs = []
        if dirs:
            import threading
            threading.Thread(target=lambda: [shutil.rmtree(d, ignore_errors=True) for d in dirs],
                             name="export-cleanup", daemon=True).start()


class _Worker:
    __slots__ = ("proc", "job", "served", "buf", "dead", "idle_timer", "last_hash")

    def __init__(self):
        self.proc = None
        self.job = None
        self.served = 0
        self.buf = ""
        self.dead = False
        self.idle_timer = None
        self.last_hash = None


class ExportJobsWindow(QWidget):
    """Non-modal list of every queued / running / finished export."""

    def __init__(self, scheduler, parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        self.s = scheduler
        self.setWindowTitle("Export Jobs")
        self.resize(720, 360)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Every export button queues the project exactly as it was when pressed. "
                             "Jobs render in separate processes; keep working, or change the project and export again."))
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["#", "Export", "State", "Progress", "Status"])
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        lay.addWidget(self.table, 1)
        row = QHBoxLayout()
        row.addWidget(QLabel("Run at once:"))
        self.spin = QSpinBox(); self.spin.setRange(1, 6); self.spin.setValue(scheduler.parallel)
        self.spin.valueChanged.connect(scheduler.set_parallel); row.addWidget(self.spin)
        row.addStretch(1)
        b_cancel = QPushButton("Cancel selected"); b_cancel.clicked.connect(self._cancel)
        b_clear = QPushButton("Clear finished"); b_clear.clicked.connect(scheduler.clear_finished)
        b_open = QPushButton("Open folder"); b_open.clicked.connect(self._open_folder)
        b_parts = QPushButton("Leftover parts…"); b_parts.clicked.connect(self._leftover_parts)
        b_parts.setToolTip("Find unfinished .partNN segments no job is using; delete them or keep them to resume.")
        for b in (b_cancel, b_clear, b_open, b_parts):
            row.addWidget(b)
        lay.addLayout(row)
        from PyQt6.QtCore import QTimer as _QT
        self._refresh_timer = _QT(self); self._refresh_timer.setSingleShot(True); self._refresh_timer.setInterval(250)
        self._refresh_timer.timeout.connect(self.refresh)
        scheduler.changed.connect(lambda *_: self._refresh_timer.start() if not self._refresh_timer.isActive() else None)
        self.refresh()

    def showEvent(self, ev):
        super().showEvent(ev); self.refresh()

    def refresh(self):
        if not self.isVisible():
            return                      # R32.8: no table work while the window is hidden
        jobs = self.s.jobs
        self.table.setRowCount(len(jobs))
        for r, j in enumerate(jobs):
            el = j.elapsed()
            eta = ""
            if j.state == RUNNING and el > 5 and 15 < j.progress < 100:
                rem = el * (100 - j.progress) / max(1.0, j.progress - 15)
                eta = " · ~%dm%02ds left" % (int(rem) // 60, int(rem) % 60)
            vals = [str(j.id), j.label, j.state + (" %ds" % el if el else "") + eta, None, j.message]
            for c, v in enumerate(vals):
                if c == 3:
                    bar = self.table.cellWidget(r, 3)
                    if not isinstance(bar, QProgressBar):
                        bar = QProgressBar(); bar.setRange(0, 100); self.table.setCellWidget(r, 3, bar)
                    bar.setValue(int(j.progress))
                    continue
                it = self.table.item(r, c)
                if it is None:
                    it = QTableWidgetItem(); self.table.setItem(r, c, it)
                it.setText(v)

    def _leftover_parts(self):
        """R31: orphaned video/audio .partNN segments in the export folders (not used by a running job)."""
        import glob, re
        from PyQt6.QtWidgets import QMessageBox
        app = self.s.app
        roots = set()
        for fn in ("_exports_dir", "_video_exports_dir", "_audio_exports_dir"):
            try:
                roots.add(os.path.abspath(str(getattr(app, fn)())))
            except Exception:
                pass
        busy = {os.path.splitext(os.path.basename(j.out_file))[0] for j in self.s.jobs if j.state in (QUEUED, RUNNING)}
        pat = re.compile(r"\.(audio\.)?part\d{2}\.[A-Za-z0-9]+(\.part)?$")
        found = []
        for r in roots:
            for f in glob.glob(os.path.join(r, "**", "*.part*"), recursive=True):
                b = os.path.basename(f)
                if not pat.search(b):
                    continue
                stem = pat.sub("", b)
                if stem in busy:
                    continue
                found.append(f)
        if not found:
            QMessageBox.information(self, "Leftover parts", "No leftover part files found.")
            return
        size = sum(os.path.getsize(f) for f in found if os.path.isfile(f))
        box = QMessageBox(self)
        box.setWindowTitle("Leftover parts")
        box.setText("%d leftover part file(s), %.1f MB, from unfinished exports.\n\n"
                    "Keep them to resume (export the same file again with Resume on), or delete them." % (len(found), size / 1e6))
        box.setDetailedText("\n".join(found[:400]))
        b_del = box.addButton("Delete them", QMessageBox.ButtonRole.DestructiveRole)
        box.addButton("Keep", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton() is b_del:
            n = 0
            for f in found:
                try:
                    os.remove(f); n += 1
                except OSError:
                    pass
            QMessageBox.information(self, "Leftover parts", "Deleted %d file(s)." % n)

    def _selected_job(self):
        r = self.table.currentRow()
        return self.s.jobs[r] if 0 <= r < len(self.s.jobs) else None

    def _cancel(self):
        j = self._selected_job()
        if j is not None:
            self.s.cancel(j.id)

    def _open_folder(self):
        j = self._selected_job()
        path = os.path.dirname(j.out_file) if j else ""
        if path:
            from PyQt6.QtGui import QDesktopServices
            from PyQt6.QtCore import QUrl
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))
