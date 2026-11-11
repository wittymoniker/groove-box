"""process_policy.py — GROOVEBOX_R32_PROCESS_POLICY_20261109

ONE helper-spawn policy on every OS, and dynamic forwarding of work to the best
available language backend.

Spawn policy (``install()`` wraps ``subprocess.Popen`` process-wide, so every existing
call site — players, encoders, export workers, device probes, games — gets it without
being edited):

  * kind inferred from argv: render | encode | media | helper | game | app | other
  * environment: BLAS/OMP/MKL/NUMEXPR thread caps sized by kind from thread_budget,
    GROOVEBOX_PARENT_PID / GROOVEBOX_PROCESS_KIND for the child, PYTHONUNBUFFERED,
    PYTHONDONTWRITEBYTECODE for helpers (no __pycache__ litter in the overlay)
  * priority: POSIX nice (render 5, encode 5, helper 10, media/game 0); Windows
    BELOW_NORMAL_PRIORITY_CLASS for batch kinds, CREATE_NO_WINDOW for helpers/encoders
  * registry: every child is tracked; ``reap()`` collects finished ones (no zombies),
    ``shutdown()`` terminates the rest at exit; ``watch_parent()`` is the child-side
    guard that exits when the parent is gone (orphan prevention)

Language backends (``Backends``): python (always), native (ctypes .so/.dll from native/),
julia (julia_bridge), scode (sCode runtime).  ``forward(op, fn_python, *args)`` runs an
operation on the backend that has been fastest for it so far (EMA of measured time), with a
periodic re-probe so a backend that got faster (or became available) wins again — the
"process migration dynamics" between languages, in-process and allocation-free.

``ProcessPool`` is a generic reusable-worker pool for line-JSON helper modules with
dynamic sizing (cores and memory headroom), idle shrink and job migration from a dead or
overloaded worker to an idle one.
"""
from __future__ import annotations

import atexit
import json
import os
import subprocess
import sys
import threading
import time
import weakref

try:
    import thread_budget as _tb
except Exception:          # pragma: no cover
    _tb = None

_IS_WIN = sys.platform.startswith("win")
_ORIG_POPEN = subprocess.Popen
_INSTALLED = [False]
_REGISTRY = weakref.WeakSet()
_REG_LOCK = threading.Lock()

NICE = {"render": 5, "encode": 5, "helper": 10, "media": 0, "game": 0, "app": 0, "other": 2}
_ENCODERS = ("ffmpeg", "ffprobe", "sox", "lame", "opusenc", "flac", "x264", "vpxenc")
_MEDIA = ("mpv", "aplay", "arecord", "vlc", "cvlc", "paplay", "pw-play", "pw-cat", "speaker-test", "mplayer", "ffplay")
_HELPERS = ("device_probe_helper", "rig_worker", "--request-scan", "--request-format", "--request-mount")
_RENDER = ("export_worker", "--serve", "render_worker", "bake")


def usable_cores():
    try:
        if _tb is not None:
            return max(1, int(_tb.usable_cores()))
    except Exception:
        pass
    try:
        return max(1, len(os.sched_getaffinity(0)))
    except Exception:
        return max(1, os.cpu_count() or 1)


def compute_threads():
    try:
        if _tb is not None:
            return max(1, int(_tb.compute_threads()))
    except Exception:
        pass
    return max(1, usable_cores() - 1)


def classify(argv):
    """Kind of child from its command line."""
    try:
        parts = [str(a) for a in (argv if isinstance(argv, (list, tuple)) else [argv])]
    except Exception:
        return "other"
    if not parts:
        return "other"
    joined = " ".join(parts).lower()
    base = os.path.basename(parts[0]).lower()
    if any(h in joined for h in _HELPERS):
        return "helper"
    if any(r in joined for r in _RENDER):
        return "render"
    if any(base.startswith(e) for e in _ENCODERS):
        return "encode"
    if any(base.startswith(m) for m in _MEDIA):
        return "media"
    if "game" in joined and (".py" in joined or "groovebox-run-script" in joined):
        return "game"
    if "run_groovebox" in joined or base.startswith("groovebox"):
        return "app"
    return "other"


def thread_caps(kind):
    if kind == "render":
        return compute_threads()
    if kind in ("encode",):
        return max(1, min(usable_cores(), 4))
    if kind in ("media", "game"):
        return 2
    if kind == "helper":
        return 1
    return max(1, min(2, usable_cores()))


def child_env(kind="other", base=None, extra=None):
    env = dict(os.environ if base is None else base)
    n = str(thread_caps(kind))
    for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS",
              "VECLIB_MAXIMUM_THREADS", "NUMBA_NUM_THREADS"):
        env.setdefault(k, n)
    env["GROOVEBOX_PARENT_PID"] = str(os.getpid())
    env["GROOVEBOX_PROCESS_KIND"] = kind
    env.setdefault("PYTHONUNBUFFERED", "1")
    if kind in ("helper", "render"):
        env.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    if extra:
        env.update({str(k): str(v) for k, v in extra.items()})
    return env


def _preexec(nice_val):
    def _fn():
        try:
            if nice_val:
                os.nice(int(nice_val))
        except Exception:
            pass
    return _fn


def popen_kwargs(argv, kind=None, **kw):
    """Fill in the policy for a Popen call (never overrides what the caller set)."""
    kind = kind or classify(argv)
    kw = dict(kw)
    kw["env"] = child_env(kind, kw.get("env"))
    if _IS_WIN:
        flags = int(kw.get("creationflags", 0) or 0)
        if kind in ("render", "encode", "helper"):
            flags |= getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0x00004000)
        if kind in ("helper", "encode", "render"):
            flags |= getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        kw["creationflags"] = flags
    else:
        if "preexec_fn" not in kw and NICE.get(kind, 0):
            kw["preexec_fn"] = _preexec(NICE[kind])
    kw.setdefault("close_fds", True)
    return kind, kw


class _PolicyPopen(_ORIG_POPEN):
    """subprocess.Popen with the Groovebox policy applied and the child registered."""

    def __init__(self, args, *a, **kw):
        kind = kw.pop("groovebox_kind", None)
        try:
            kind, kw = popen_kwargs(args, kind, **kw)
        except Exception:
            pass
        super().__init__(args, *a, **kw)
        self.groovebox_kind = kind
        self.groovebox_started = time.monotonic()
        with _REG_LOCK:
            _REGISTRY.add(self)


def install():
    """Route every subprocess.Popen in this process through the policy (idempotent)."""
    if _INSTALLED[0]:
        return True
    subprocess.Popen = _PolicyPopen
    _INSTALLED[0] = True
    atexit.register(shutdown)
    return True


def popen(argv, kind=None, **kw):
    """Explicit policy spawn (works whether or not install() ran)."""
    kind, kw = popen_kwargs(argv, kind, **kw)
    p = _ORIG_POPEN(argv, **kw)
    p.groovebox_kind = kind
    p.groovebox_started = time.monotonic()
    with _REG_LOCK:
        _REGISTRY.add(p)
    return p


def children(alive_only=True):
    with _REG_LOCK:
        ps = list(_REGISTRY)
    if alive_only:
        ps = [p for p in ps if p.poll() is None]
    return ps


def reap():
    """Collect exit statuses of finished children (prevents zombies); returns how many."""
    n = 0
    with _REG_LOCK:
        ps = list(_REGISTRY)
    for p in ps:
        try:
            if p.poll() is not None:
                n += 1
                _REGISTRY.discard(p)
        except Exception:
            pass
    return n


def shutdown(timeout=1.5):
    """Terminate every live child this process started (called at exit)."""
    ps = children()
    for p in ps:
        try:
            p.terminate()
        except Exception:
            pass
    t_end = time.monotonic() + timeout
    for p in ps:
        try:
            p.wait(timeout=max(0.05, t_end - time.monotonic()))
        except Exception:
            try:
                p.kill()
            except Exception:
                pass


def watch_parent(interval=1.0, on_exit=None):
    """Child side: exit when the parent Groovebox is gone (set GROOVEBOX_PARENT_PID)."""
    try:
        ppid = int(os.environ.get("GROOVEBOX_PARENT_PID", "0") or 0)
    except Exception:
        ppid = 0
    if not ppid:
        return None

    def _alive(pid):
        if _IS_WIN:
            try:
                import ctypes
                h = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
                if not h:
                    return False
                code = ctypes.c_ulong()
                ok = ctypes.windll.kernel32.GetExitCodeProcess(h, ctypes.byref(code))
                ctypes.windll.kernel32.CloseHandle(h)
                return bool(ok) and code.value == 259
            except Exception:
                return True
        try:
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            return True

    def _loop():
        while True:
            time.sleep(interval)
            if not _alive(ppid):
                if on_exit:
                    try:
                        on_exit()
                    except Exception:
                        pass
                os._exit(0)

    th = threading.Thread(target=_loop, name="groovebox-parent-watch", daemon=True)
    th.start()
    return th


def status():
    ps = children()
    by = {}
    for p in ps:
        by[getattr(p, "groovebox_kind", "other")] = by.get(getattr(p, "groovebox_kind", "other"), 0) + 1
    return {"installed": _INSTALLED[0], "live": len(ps), "by_kind": by, "cores": usable_cores(),
            "compute_threads": compute_threads()}


# ---------------------------------------------------------------------------
# Language backends + dynamic forwarding
# ---------------------------------------------------------------------------
class Backends:
    """Registry of per-operation implementations in several languages and the forwarder."""
    ORDER = ("native", "julia", "scode", "python")
    _impl = {}            # op -> {backend: fn}
    _ema = {}             # (op, backend) -> seconds (EMA)
    _calls = {}           # op -> count
    _avail = {}
    _lock = threading.Lock()
    REPROBE_EVERY = 64    # every N calls try the second-best backend once

    @classmethod
    def available(cls, name):
        with cls._lock:
            if name in cls._avail:
                return cls._avail[name]
        ok = False
        try:
            if name == "python":
                ok = True
            elif name == "julia":
                import julia_bridge
                ok = bool(julia_bridge.julia_available())
            elif name == "scode":
                import scode  # noqa: F401
                ok = True
            elif name == "native":
                here = os.path.dirname(os.path.abspath(__file__))
                ok = any(os.path.isfile(os.path.join(here, "native", f)) for f in
                         ("libgroovebox_accel.so", "libgroovebox_rust_accel.so", "groovebox_accel.dll",
                          "libgroovebox_accel.dylib"))
        except Exception:
            ok = False
        with cls._lock:
            cls._avail[name] = ok
        return ok

    @classmethod
    def register(cls, op, backend, fn):
        with cls._lock:
            cls._impl.setdefault(op, {})[backend] = fn

    @classmethod
    def candidates(cls, op):
        with cls._lock:
            impls = dict(cls._impl.get(op, {}))
        return [(b, impls[b]) for b in cls.ORDER if b in impls and cls.available(b)]

    @classmethod
    def best(cls, op):
        cands = cls.candidates(op)
        if not cands:
            return None
        with cls._lock:
            scored = sorted(cands, key=lambda bf: cls._ema.get((op, bf[0]), 0.0))
            n = cls._calls.get(op, 0)
        if len(scored) > 1 and n and n % cls.REPROBE_EVERY == 0:
            return scored[1]          # re-probe the runner-up now and then
        return scored[0]

    @classmethod
    def forward(cls, op, fn_python, *args, **kw):
        """Run ``op`` on the currently fastest backend; fall back to Python on any error."""
        if "python" not in cls._impl.get(op, {}):
            cls.register(op, "python", fn_python)
        choice = cls.best(op) or ("python", fn_python)
        backend, fn = choice
        t0 = time.perf_counter()
        try:
            out = fn(*args, **kw)
            if out is None and backend != "python":
                raise RuntimeError("backend returned None")
        except Exception:
            if backend == "python":
                raise
            with cls._lock:
                cls._ema[(op, backend)] = 1e9       # disqualify until re-probe
            backend, fn = "python", fn_python
            t0 = time.perf_counter()
            out = fn(*args, **kw)
        dt = time.perf_counter() - t0
        with cls._lock:
            key = (op, backend)
            prev = cls._ema.get(key)
            cls._ema[key] = dt if prev is None or prev >= 1e8 else prev * 0.8 + dt * 0.2
            cls._calls[op] = cls._calls.get(op, 0) + 1
        return out

    @classmethod
    def report(cls):
        # Resolve availability outside _lock: available() also consults and
        # updates the registry lock, so doing it under this non-reentrant lock
        # would deadlock diagnostics and startup capability reporting.
        available = {b: cls.available(b) for b in cls.ORDER}
        with cls._lock:
            return {"available": available,
                    "ops": {op: {b: round(cls._ema.get((op, b), 0.0) * 1e6, 1) for b in impls}
                            for op, impls in cls._impl.items()},
                    "calls": dict(cls._calls)}


forward = Backends.forward
register_backend = Backends.register


# ---------------------------------------------------------------------------
# Generic reusable worker pool (line-JSON helpers)
# ---------------------------------------------------------------------------
class ProcessPool:
    """Reusable helper processes with dynamic sizing and job migration.

    argv_fn()        -> argv that starts one worker reading JSON lines on stdin and writing
                        one JSON line per finished job on stdout.
    submit(job)      -> Future-like handle (.done(), .result(), .cancel()).
    Workers idle longer than ``idle_s`` are retired; a worker that dies mid-job has its
    job migrated to another worker (up to ``retries``).
    """

    def __init__(self, argv_fn, kind="render", min_workers=1, max_workers=None, idle_s=45.0, retries=1):
        self.argv_fn = argv_fn
        self.kind = kind
        self.min_workers = max(0, int(min_workers))
        self.max_workers = max(1, int(max_workers or self._auto_max()))
        self.idle_s = float(idle_s)
        self.retries = int(retries)
        self._workers = []
        self._queue = []
        self._lock = threading.Lock()
        self._cv = threading.Condition(self._lock)
        self._closed = False
        self._thread = threading.Thread(target=self._loop, name="groovebox-pool-%s" % kind, daemon=True)
        self._thread.start()

    @staticmethod
    def _auto_max():
        cores = usable_cores()
        try:
            avail = os.sysconf("SC_AVPHYS_PAGES") * os.sysconf("SC_PAGE_SIZE") / 2.0 ** 30
            mem_cap = max(1, int(avail // 1.5))        # ~1.5 GB per render worker
        except Exception:
            mem_cap = cores
        return max(1, min(cores - 1 if cores > 1 else 1, mem_cap, 6))

    class _Job:
        def __init__(self, payload):
            self.payload = payload
            self._done = threading.Event()
            self._result = None
            self._error = None
            self.attempts = 0
            self.cancelled = False

        def done(self):
            return self._done.is_set()

        def cancel(self):
            self.cancelled = True

        def result(self, timeout=None):
            if not self._done.wait(timeout):
                raise TimeoutError("job not finished")
            if self._error:
                raise RuntimeError(self._error)
            return self._result

    class _W:
        __slots__ = ("proc", "job", "idle_since", "reader")

        def __init__(self, proc):
            self.proc = proc
            self.job = None
            self.idle_since = time.monotonic()
            self.reader = None

    def submit(self, payload):
        job = self._Job(payload)
        with self._cv:
            if self._closed:
                raise RuntimeError("pool closed")
            self._queue.append(job)
            self._cv.notify_all()
        return job

    def _spawn(self):
        argv = self.argv_fn()
        p = popen(argv, kind=self.kind, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                  stderr=subprocess.DEVNULL, text=True, bufsize=1)
        w = self._W(p)
        w.reader = threading.Thread(target=self._read, args=(w,), daemon=True)
        w.reader.start()
        self._workers.append(w)
        return w

    def _read(self, w):
        try:
            for line in w.proc.stdout:
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                except Exception:
                    continue
                with self._cv:
                    job, w.job = w.job, None
                    w.idle_since = time.monotonic()
                    if job is not None:
                        if isinstance(msg, dict) and msg.get("error"):
                            job._error = str(msg["error"])
                        else:
                            job._result = msg
                        job._done.set()
                    self._cv.notify_all()
        except Exception:
            pass
        finally:
            with self._cv:
                job, w.job = w.job, None
                if w in self._workers:
                    self._workers.remove(w)
                if job is not None and not job.done():
                    job.attempts += 1
                    if job.attempts <= self.retries and not job.cancelled:
                        self._queue.insert(0, job)        # migrate to another worker
                    else:
                        job._error = "worker exited before finishing the job"
                        job._done.set()
                self._cv.notify_all()

    def _loop(self):
        while True:
            with self._cv:
                self._cv.wait(timeout=0.5)
                if self._closed:
                    return
                self._queue = [j for j in self._queue if not j.cancelled]
                idle = [w for w in self._workers if w.job is None]
                while self._queue and (idle or len(self._workers) < self.max_workers):
                    w = idle.pop() if idle else self._spawn()
                    job = self._queue.pop(0)
                    w.job = job
                    try:
                        w.proc.stdin.write(json.dumps(job.payload) + "\n")
                        w.proc.stdin.flush()
                    except Exception:
                        w.job = None
                        self._queue.insert(0, job)
                        try:
                            w.proc.kill()
                        except Exception:
                            pass
                        if w in self._workers:
                            self._workers.remove(w)
                        break
                now = time.monotonic()
                for w in list(self._workers):
                    if w.job is None and len(self._workers) > self.min_workers and now - w.idle_since > self.idle_s:
                        try:
                            w.proc.stdin.close()
                        except Exception:
                            pass
                        self._workers.remove(w)

    def stats(self):
        with self._lock:
            return {"workers": len(self._workers), "busy": sum(1 for w in self._workers if w.job is not None),
                    "queued": len(self._queue), "max": self.max_workers}

    def close(self):
        with self._cv:
            self._closed = True
            ws = list(self._workers)
            self._workers.clear()
            self._cv.notify_all()
        for w in ws:
            try:
                w.proc.stdin.close()
            except Exception:
                pass
