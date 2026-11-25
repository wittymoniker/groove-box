"""app_limits.py — external applications and user programs stay strictly UNDER a share of the machine.

Default share: 0.19758 of the CPU and 0.19758 of the memory on board (compat setting `external_app_share`), always
strictly less, never equal or more:
  memory  RLIMIT_DATA (R123; was RLIMIT_AS) = share × physical RAM − 1 page (the program gets an allocation error above it, not the system)
  CPU     the process is niced (+10) and a 4 Hz governor measures its CPU time (all its threads) from /proc; when it
          has used more than share × cores × wall time it is paused (SIGSTOP) just long enough to fall back under,
          then resumed (SIGCONT). Its affinity is also limited to ⌈share × cores⌉ cores when that is fewer than all.
  R132    resident memory is watched too: a program over share × RAM for 3 s is stopped (runtimes that need a
          looser launch limit — Julia, Go, JVM, browsers — are held to the share this way).
Applies to: Apps & scripts launches, Seed Atlas "send to app", Program Builder runs, plugin-library programs in
compiled languages. Groovebox's own export workers are not affected (they have their own budget).
"""
from __future__ import annotations
import math, os, signal, subprocess, threading, time

DEFAULT_SHARE = 0.19758


def share():
    try:
        import compat_settings as cs
        v = float(cs.load().get("external_app_share", DEFAULT_SHARE))
    except Exception:
        v = DEFAULT_SHARE
    return max(0.01, min(DEFAULT_SHARE if v <= 0 else v, 0.95))


def _ram():
    try:
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
    except Exception:
        return 8 << 30


def _cores():
    try:
        return len(os.sched_getaffinity(0))
    except Exception:
        return os.cpu_count() or 2


# GROOVEBOX_R123_APP_LIMITS_NO_PREEXEC_20261119
# * No preexec_fn: CPython documents it as unsafe in multi-threaded parents (fork while
#   another thread holds the allocator/import lock can deadlock the child). Groovebox runs
#   dozens of threads, so limits are applied to the child pid right after spawn instead
#   (resource.prlimit / setpriority / sched_setaffinity all accept a pid on Linux).
# * RLIMIT_DATA instead of RLIMIT_AS: Go, Julia, the JVM and Chromium reserve large
#   PROT_NONE address ranges at start-up; an address-space cap made them abort at launch
#   even though their resident use was tiny. RLIMIT_DATA counts writable private memory.
_ADDRESS_SPACE_HEAVY = ("julia", "go", "java", "node", "electron", "chrome", "chromium", "firefox", "code", "blender", "godot")


def _apply_limits(pid, sh, argv0=""):
    try:
        import resource
        lim = int(sh * _ram()) - os.sysconf("SC_PAGE_SIZE")
        which = getattr(resource, "RLIMIT_DATA", None)
        if which is not None and hasattr(resource, "prlimit"):
            base = os.path.basename(str(argv0 or "")).lower()
            if any(base.startswith(h) for h in _ADDRESS_SPACE_HEAVY):
                lim = max(lim, int(0.5 * _ram()))
            resource.prlimit(pid, which, (lim, lim))
    except Exception:
        pass
    try:
        os.setpriority(os.PRIO_PROCESS, pid, 10)
    except Exception:
        pass
    try:
        n = max(1, math.ceil(sh * _cores()))
        if n < _cores():
            allc = sorted(os.sched_getaffinity(0)); os.sched_setaffinity(pid, allc[-n:])
    except Exception:
        pass


def _cpu_s(pid):
    try:
        with open("/proc/%d/stat" % pid) as f:
            parts = f.read().rsplit(")", 1)[1].split()
        return (int(parts[11]) + int(parts[12]) + int(parts[13]) + int(parts[14])) / float(os.sysconf("SC_CLK_TCK"))
    except Exception:
        return None


def _rss(pid):
    """Resident memory (bytes) of the process, or None."""
    try:
        with open("/proc/%d/status" % pid) as f:
            for ln in f:
                if ln.startswith("VmRSS:"):
                    return int(ln.split()[1]) * 1024
    except Exception:
        return None
    return None


def _governor(p, sh):
    """Keep the child's CPU use strictly under sh × all cores — and (R132) its resident memory under sh × RAM.

    RLIMIT_DATA cannot hold address-space-heavy runtimes (Julia, Go, JVM, browsers) at the share, so they get a
    looser launch limit; their *real* use is checked here instead: over the share for 3 s in a row → the program is
    stopped with SIGTERM (then SIGKILL) and the reason is recorded on the Popen as p.groovebox_limit_reason."""
    cap = sh * _cores() * 0.98
    mem_cap = int(sh * _ram()) - 4096
    over = 0
    t0 = time.monotonic(); c0 = _cpu_s(p.pid) or 0.0
    while p.poll() is None:
        time.sleep(0.25)
        c = _cpu_s(p.pid)
        if c is None:
            break
        r = _rss(p.pid)
        over = over + 1 if (r is not None and r >= mem_cap) else 0
        if over >= 12:
            p.groovebox_limit_reason = ("memory %.0f MB ≥ add-on limit %.0f MB (%.3f of RAM)"
                                        % (r / 1e6, mem_cap / 1e6, sh))
            try:
                p.terminate(); p.wait(3)
            except Exception:
                try: p.kill()
                except Exception: pass
            break
        el = time.monotonic() - t0; used = c - c0
        excess = used - cap * el
        if excess > 0:
            pause = min(2.0, excess / cap)
            try:
                os.kill(p.pid, signal.SIGSTOP); time.sleep(pause)
            finally:
                try: os.kill(p.pid, signal.SIGCONT)
                except Exception: pass
        if el > 10:                       # sliding window: keep the account recent
            t0 = time.monotonic(); c0 = _cpu_s(p.pid) or c


def popen(argv, **kw):
    """subprocess.Popen with the external-app limits applied (thread-safe, no preexec_fn)."""
    sh = share()
    if kw.get("env") is None:
        try:
            import toolchain_env
            kw["env"] = toolchain_env.native_env()
        except Exception:
            pass
    p = subprocess.Popen(argv, **kw)
    p.groovebox_share = sh
    if os.name == "posix":
        _apply_limits(p.pid, sh, argv[0] if isinstance(argv, (list, tuple)) and argv else argv)
        threading.Thread(target=_governor, args=(p, sh), name="app-limit-%d" % p.pid, daemon=True).start()
    return p
