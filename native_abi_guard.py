"""Pin one compatible libstdc++ before mixed native runtimes (Qt/Mesa/LLVM/Z3/Julia) load.

GROOVEBOX_R123_NATIVE_ABI_UNIFICATION_20261119

Failure this prevents
---------------------
Mesa's llvmpipe links LLVM, which links Z3; on Debian trixie those are built with
GCC 14 and need ``CXXABI_1.3.15``.  Julia 1.11 ships a private, older
``libstdc++.so.6`` under ``<julia>/lib/julia``.  libjulia loads that private copy by
*absolute path* (RUNPATH ``$ORIGIN/julia``, and its own probe falls back to the
bundled copy when the probe child cannot run, e.g. in a chroot without /proc).
Once any ``libstdc++.so.6`` is loaded, every later ``DT_NEEDED: libstdc++.so.6``
binds to it by soname, so ``LD_LIBRARY_PATH`` ordering alone cannot help.

The fix has three layers (all idempotent):

1. Build time — ``BUILD_ISO/julia_abi_unify.py`` replaces Julia's private
   libstdc++/libgcc_s with symlinks to the system runtime when the system copy
   defines every version tag the private copy does (same inode → one copy).
2. Launch time — launchers export ``LD_PRELOAD`` with the newest runtime
   (``python3 native_abi_guard.py --shell-env``), so it is loaded first in every
   process, including subprocesses and Julia itself.
3. In-process — importing this module preloads the newest runtime with
   ``RTLD_GLOBAL`` before Qt/NumPy/JuliaCall, and :func:`report` reads
   ``/proc/self/maps`` to prove which copy is actually mapped.

Never raises at import.  Non-Linux platforms are a no-op.
"""
from __future__ import annotations

import ctypes
import os
import re
import sys
from pathlib import Path

REQUIRED_SYMBOL = "CXXABI_1.3.15"
_TAG_RE = re.compile(rb"(GLIBCXX|CXXABI)_(\d+(?:\.\d+)*)\x00")
SYSTEM_DIRS = ("/usr/lib/x86_64-linux-gnu", "/lib/x86_64-linux-gnu", "/usr/lib/aarch64-linux-gnu",
               "/lib/aarch64-linux-gnu", "/usr/lib64", "/lib64", "/usr/lib", "/lib")
_LIBS = ("libstdc++.so.6", "libgcc_s.so.1")


def _vt(text):
    return tuple(int(x) for x in text.split("."))


def version_tags(path):
    """Return {'GLIBCXX': set(), 'CXXABI': set()} of version tuples defined in ``path``."""
    tags = {"GLIBCXX": set(), "CXXABI": set()}
    try:
        data = Path(path).read_bytes()
    except OSError:
        return tags
    for kind, ver in _TAG_RE.findall(data):
        try:
            tags[kind.decode()].add(_vt(ver.decode()))
        except ValueError:
            pass
    return tags


def abi_level(path):
    """Sortable ABI level: (max CXXABI, max GLIBCXX)."""
    t = version_tags(path)
    return (max(t["CXXABI"], default=()), max(t["GLIBCXX"], default=()))


def is_superset(newer, older):
    """True when ``newer`` defines every GLIBCXX/CXXABI tag that ``older`` defines."""
    a, b = version_tags(newer), version_tags(older)
    return bool(a["GLIBCXX"]) and a["GLIBCXX"] >= b["GLIBCXX"] and a["CXXABI"] >= b["CXXABI"]


def _julia_roots():
    roots = []
    for env in ("PYTHON_JULIACALL_EXE", "JULIA_EXE"):
        exe = os.environ.get(env)
        if exe:
            roots.append(Path(os.path.realpath(exe)).parent.parent)
    for fixed in ("/opt/sos/julia",):
        roots.append(Path(fixed))
    out = []
    for r in roots:
        if r not in out and r.is_dir():
            out.append(r)
    return out


def candidates(name="libstdc++.so.6"):
    """System copies first, then Julia private copies (same-level ties keep the system copy)."""
    seen, out = set(), []
    dirs = list(SYSTEM_DIRS) + [str(r / "lib" / "julia") for r in _julia_roots()] + [str(r / "lib") for r in _julia_roots()]
    for d in dirs:
        p = os.path.join(d, name)
        if not os.path.isfile(p):
            continue
        real = os.path.realpath(p)
        if real in seen:
            continue
        seen.add(real)
        out.append(p)
    return out


_SELECT_CACHE = {}


def select(name="libstdc++.so.6"):
    """Newest runtime by ABI level; system copy wins ties.  Returns a path or None.

    Cached per process: child_env() runs on every subprocess spawn and abi_level() reads
    the whole library."""
    if name in _SELECT_CACHE:
        return _SELECT_CACHE[name]
    _SELECT_CACHE[name] = _select_uncached(name)
    return _SELECT_CACHE[name]


def _select_uncached(name):
    best, best_level = None, None
    for p in candidates(name):
        lvl = abi_level(p)
        if best is None or lvl > best_level:
            best, best_level = p, lvl
    return best


def loaded_runtimes():
    """Paths of libstdc++/libgcc_s actually mapped in this process (Linux /proc only)."""
    found = []
    try:
        with open("/proc/self/maps", "r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                parts = line.split(None, 5)
                if len(parts) == 6:
                    path = parts[5].strip()
                    base = os.path.basename(path)
                    if base.startswith(("libstdc++.so", "libgcc_s.so")) and path not in found:
                        found.append(path)
    except OSError:
        pass
    return found


_REPORT = {"preloaded": False, "path": None, "required_symbol": REQUIRED_SYMBOL,
           "platform": sys.platform, "level": None, "conflict": None}


def _preload():
    if not sys.platform.startswith("linux") or os.environ.get("GROOVEBOX_ABI_GUARD", "1") == "0":
        _REPORT["skipped"] = "not linux or disabled"
        return
    chosen = select("libstdc++.so.6")
    if not chosen:
        _REPORT["error"] = "no libstdc++.so.6 candidate found"
        return
    already = [p for p in loaded_runtimes() if os.path.basename(p).startswith("libstdc++")]
    if already and os.path.realpath(already[0]) != os.path.realpath(chosen):
        if abi_level(already[0]) < abi_level(chosen):
            # Too late to swap in-process; the launcher's LD_PRELOAD is the authoritative fix.
            _REPORT["conflict"] = {"loaded": already[0], "wanted": chosen,
                                   "fix": "start through the Groovebox launcher (exports LD_PRELOAD)"}
    try:
        gcc = select("libgcc_s.so.1")
        if gcc:
            ctypes.CDLL(gcc, mode=getattr(ctypes, "RTLD_GLOBAL", 0))
        ctypes.CDLL(chosen, mode=getattr(ctypes, "RTLD_GLOBAL", 0))
        lvl = abi_level(chosen)
        _REPORT.update(preloaded=True, path=chosen, level=[".".join(map(str, v)) for v in lvl])
        _REPORT["has_required_symbol"] = REQUIRED_SYMBOL.encode() in Path(chosen).read_bytes()
        os.environ.setdefault("GROOVEBOX_SYSTEM_LIBSTDCXX", chosen)
    except Exception as exc:  # pragma: no cover - depends on host
        _REPORT["error"] = str(exc)


def child_env(env=None):
    """Environment for subprocesses that may load Mesa/LLVM/Z3 and Julia together.

    Adds the chosen runtimes to LD_PRELOAD and moves Julia's private dirs behind every
    other entry of LD_LIBRARY_PATH.  Returns a new dict.
    """
    env = dict(os.environ if env is None else env)
    if not sys.platform.startswith("linux"):
        return env
    pre = [p for p in (select("libgcc_s.so.1"), select("libstdc++.so.6")) if p]
    old = [x for x in env.get("LD_PRELOAD", "").replace(" ", ":").split(":") if x]
    old = [x for x in old if os.path.basename(x) not in _LIBS]
    if pre:
        env["LD_PRELOAD"] = ":".join(pre + old)
    # Only reorder: Julia private dirs move to the END. System dirs are never *added* —
    # LD_LIBRARY_PATH beats RUNPATH, so injecting /usr/lib would make a pip PyQt6 wheel
    # bind the distro's (different) Qt build.
    parts = [x for x in env.get("LD_LIBRARY_PATH", "").split(":") if x]
    if parts:
        jl = [x for x in parts if "julia" in x.lower()]
        env["LD_LIBRARY_PATH"] = ":".join(dict.fromkeys([x for x in parts if x not in jl] + jl))
    return env


def report():
    out = dict(_REPORT)
    out["mapped"] = loaded_runtimes()
    out["single_runtime"] = len({os.path.realpath(p) for p in out["mapped"]
                                 if os.path.basename(p).startswith("libstdc++")}) <= 1
    return out


REPORT = _REPORT
try:
    _preload()
except Exception as _exc:  # never break application import
    _REPORT["error"] = repr(_exc)


def _main(argv):
    import json
    if "--shell-env" in argv:
        env = child_env()
        for key in ("LD_PRELOAD", "LD_LIBRARY_PATH"):
            if env.get(key):
                val = env[key].replace("'", "'\\''")
                print(f"export {key}='{val}'")
        return 0
    if "--verify" in argv:
        rep = report()
        print(json.dumps(rep, indent=2))
        ok = rep.get("preloaded") and rep.get("single_runtime") and rep.get("has_required_symbol", False)
        if "--allow-missing-symbol" in argv:
            ok = rep.get("preloaded") and rep.get("single_runtime")
        return 0 if ok else 1
    print(__import__("json").dumps(report(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
