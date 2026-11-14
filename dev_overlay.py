"""Developer overlay — write your own Mathematician's Groovebox on top of the installed core. DEV_OVERLAY_20261112

Layout (inside the Groovebox data folder, never inside the install):
    dev-overlay/src/<path>       your files: new modules, or a full override of a core module of the same path
    dev-overlay/append/<path>    text that runs / compiles AFTER the core file of the same path
    dev-overlay/build/           compiler outputs only (native libraries, sCode IR, logs)
    dev-overlay/scratch/         scratchpad scripts — run one at a time in an isolated child process
Languages: .py  .cpp  .sC  .jl  .rs

PROTECTED CORE
  The installed system files are read in place and never edited, moved, copied or duplicated — not even into
  build/.  Python reads them through import hooks (dev_overlay.core(name) gives an override the original
  module); C++ appends are a translation unit that #includes the core path; Rust appends #[path]-mount the core
  file; sCode / Julia appends are concatenated in memory.  Every write is checked by _guard_write().

SESSION-ONLY
  Nothing in the overlay ever loads by itself.  Each launch starts on the installed core; the overlay runs only
  after "Enable for this session" in Performance → 🧪 Dev Overlay, and only if its last compile is current.

ROLLBACK
  While enabled a watchdog samples temperature, free RAM, UI stalls and errors raised from overlay code.  Per
  the compat setting `dev_overlay_rollback` (auto | manual) it falls back to the core on thermal instability,
  low memory, a frozen UI or repeated overlay errors: hooks are removed, appended names and class attributes are
  restored, overridden modules are re-imported from the core and the native function table is restored.
"""
from __future__ import annotations

import ctypes
import glob
import hashlib
import importlib
import importlib.abc
import importlib.machinery
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import traceback
import types
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

CORE_ROOT = Path(__file__).resolve().parent
LANGS = (".py", ".cpp", ".sC", ".jl", ".rs")
# Modules that cannot be re-imported live (the running main window / this module). Appends still apply hot.
NO_RELOAD = {"__main__", "groovebox", "dev_overlay", "dev_overlay_ui", "performance", "compat_settings"}
_LOCK = threading.RLock()


# ============================================================================ paths and the protected core
def overlay_root() -> Path:
    forced = os.environ.get("GROOVEBOX_DEV_OVERLAY_DIR", "").strip()
    if forced:
        root = Path(forced)
    else:
        try:
            import groovebox_paths
            root = Path(groovebox_paths.base_dir()) / "dev-overlay"
        except Exception:
            root = Path.home() / ".groovebox" / "dev-overlay"
    root = root.resolve()
    for sub in ("src", "append", "build", "scratch"):
        (root / sub).mkdir(parents=True, exist_ok=True)
    return root


def _inside(p: Path, root: Path) -> bool:
    try:
        p.relative_to(root)
        return True
    except ValueError:
        return False


class ProtectedCoreError(PermissionError):
    pass


def _guard_write(path) -> Path:
    """Every overlay write goes through here: inside the overlay, never a core file, never via a link."""
    root = overlay_root()
    p = Path(os.path.abspath(path))
    rp = p.resolve()
    if not _inside(rp, root):
        raise ProtectedCoreError(f"refused: {p} is outside the developer overlay")
    if _inside(rp, CORE_ROOT) and not _inside(root, CORE_ROOT):
        raise ProtectedCoreError(f"refused: {p} is an installed system file")
    if p.is_symlink():
        raise ProtectedCoreError(f"refused: {p} is a link")
    if p.exists():
        try:
            st = p.stat()
            if st.st_nlink > 1:
                raise ProtectedCoreError(f"refused: {p} is hard-linked (it may be a system file)")
        except OSError:
            pass
    return p


def _write(path, text: str) -> Path:
    p = _guard_write(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".part")
    _guard_write(tmp)
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, p)
    return p


def _clean_rel(rel: str) -> str:
    rel = str(rel).replace("\\", "/").strip().lstrip("/")
    parts = [x for x in rel.split("/") if x not in ("", ".")]
    if not parts or any(x == ".." for x in parts):
        raise ValueError("use a relative path inside the Groovebox tree, e.g. my_synth.py or cpp/my_kernel.cpp")
    if not rel.endswith(LANGS):
        raise ValueError("overlay files must be one of: " + " ".join(LANGS))
    return "/".join(parts)


def core_path(rel: str) -> Optional[Path]:
    p = (CORE_ROOT / _clean_rel(rel)).resolve()
    return p if p.is_file() and _inside(p, CORE_ROOT) else None


def read_core(rel: str) -> str:
    """Read-only view of an installed file."""
    p = core_path(rel)
    if p is None:
        raise FileNotFoundError(rel)
    return p.read_text(encoding="utf-8", errors="replace")


def import_map(include_user_apps: bool = True) -> Dict:
    """Return the shared import map for core, developer overlay and user apps.

    Mapping is metadata-only: it does not import user code or grant it core access.
    """
    try:
        import import_fabric
        roots = [overlay_root() / "src"]
        if include_user_apps:
            try:
                import groovebox_paths
                roots.append(Path(groovebox_paths.base_dir()) / "apps")
            except Exception:
                roots.append(Path.home() / ".groovebox" / "apps")
        return import_fabric.load_or_build_map(CORE_ROOT, roots)
    except Exception as exc:
        return {"error": str(exc), "modules": {}, "imports": {}}


def core_files(exts=LANGS) -> List[str]:
    skip = ("V3_REFERENCE", "release-tests", "BUILD_ISO", "BUILD_KIT", "__pycache__", ".git", "target")
    out = []
    for dp, dn, fn in os.walk(CORE_ROOT):
        dn[:] = [d for d in dn if not d.startswith(skip)]
        for f in fn:
            if f.endswith(exts) and not f.startswith("test_"):
                out.append(os.path.relpath(os.path.join(dp, f), CORE_ROOT).replace(os.sep, "/"))
    return sorted(out)


# ============================================================================ overlay files
def files() -> List[Dict]:
    root = overlay_root(); out = []
    for kind in ("src", "append"):
        base = root / kind
        for p in sorted(base.rglob("*")):
            if p.is_file() and p.name.endswith(LANGS):
                rel = p.relative_to(base).as_posix()
                out.append({"kind": kind, "rel": rel, "path": str(p), "core": core_path(rel) is not None,
                            "size": p.stat().st_size})
    return out


_PY_OVERRIDE = '''"""Overlay override of {rel} — the installed core is read in place (never copied)."""
from dev_overlay import core as _core_module
_core = _core_module({mod!r})
globals().update({{k: v for k, v in vars(_core).items() if not k.startswith("__")}})

# Your changes below replace or extend the core module's names.
'''
_TEMPLATES = {
    ("append", ".py"): "# Appended to {rel}: runs after the core module, in the same namespace.\n# Redefine functions or patch classes here; rollback restores the originals.\n\n",
    ("append", ".cpp"): "// Appended to {rel}: compiled in the same translation unit, after the core file.\n// Add new extern \"C\" (or GB_EXPORT) functions here; redefining a core symbol is a duplicate-symbol error.\n\n",
    ("append", ".rs"): "// Appended to {rel}: the core file is mounted as `gb_core` and compiled with this one.\n// Add new #[no_mangle] extern \"C\" fns here.\n\n",
    ("append", ".sC"): "# Appended to {rel}: compiled after the core sCode text.\n\n",
    ("append", ".jl"): "# Appended to {rel}: parsed / run after the core Julia file.\n\n",
    ("src", ".cpp"): "// Overlay C++ for {rel}.\n#include <cstddef>\n\nextern \"C\" {{\n}}\n",
    ("src", ".rs"): "// Overlay Rust for {rel} (compiled as a cdylib).\n",
    ("src", ".sC"): "# Overlay sCode for {rel}\n",
    ("src", ".jl"): "# Overlay Julia for {rel}\n",
    ("src", ".py"): '"""{rel} — part of your overlay Groovebox."""\n',
}


def _module_name(rel: str) -> Optional[str]:
    if not rel.endswith(".py"):
        return None
    mod = rel[:-3].replace("/", ".")
    return mod[:-9] if mod.endswith(".__init__") else mod


def new_file(kind: str, rel: str) -> Path:
    """kind: src (new file or full override) | append (runs after the core file of the same path)."""
    if kind not in ("src", "append"):
        raise ValueError("kind must be src or append")
    rel = _clean_rel(rel)
    if kind == "append" and core_path(rel) is None:
        raise FileNotFoundError(f"there is no installed {rel} to append to")
    p = overlay_root() / kind / rel
    if p.exists():
        return p
    ext = os.path.splitext(rel)[1]
    if kind == "src" and ext == ".py" and core_path(rel) is not None:
        text = _PY_OVERRIDE.format(rel=rel, mod=_module_name(rel))
    else:
        text = _TEMPLATES[(kind, ext)].format(rel=rel)
    return _write(p, text)


def save_file(path, text: str) -> Path:
    return _write(path, text)


def delete_file(path) -> None:
    p = _guard_write(path)
    if p.is_file():
        p.unlink()


def _digest() -> str:
    h = hashlib.sha256()
    for f in files():
        h.update(f["kind"].encode() + b"\0" + f["rel"].encode() + b"\0")
        h.update(Path(f["path"]).read_bytes())
    return h.hexdigest()


def _state_path() -> Path:
    return overlay_root() / "build" / "state.json"


def load_state() -> Dict:
    try:
        return json.loads(_state_path().read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_state(st: Dict):
    _write(_state_path(), json.dumps(st, indent=1, sort_keys=True))


def log(msg: str):
    try:
        p = _guard_write(overlay_root() / "build" / "overlay.log")
        with open(p, "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + msg.rstrip() + "\n")
    except Exception:
        pass


# ============================================================================ compiling
def _which(*names):
    for n in names:
        if n and shutil.which(n):
            return shutil.which(n)
    return None


def toolchains() -> Dict[str, Dict]:
    """TOOLCHAIN_REPORT_R6: which scratch / overlay languages can run here, and why not when they cannot."""
    out = {".py": {"ok": True, "tool": sys.executable, "note": "Python (always)"}}
    cxx = _which(os.environ.get("CXX"), "g++", "c++", "clang++")
    out[".cpp"] = {"ok": bool(cxx), "tool": cxx, "note": "C++" if cxx else "no C++ compiler (g++ / clang++)"}
    rc = _which(os.environ.get("RUSTC"), "rustc")
    out[".rs"] = {"ok": bool(rc), "tool": rc, "note": "Rust" if rc else "rustc not installed (scripts/ensure_rust_toolchain.py)"}
    jl = _which(os.environ.get("JULIA"), "julia")
    out[".jl"] = {"ok": bool(jl), "tool": jl, "note": "Julia" if jl else "julia not installed (saved, not run)"}
    try:
        import importlib.util
        ok = importlib.util.find_spec("scode.compiler") is not None
    except Exception:
        ok = False
    out[".sC"] = {"ok": ok, "tool": "scode" if ok else None, "note": "sCode → sIR" if ok else "sCode compiler unavailable"}
    return out


def toolchain_summary() -> str:
    return " · ".join(f"{k} {'✓' if v['ok'] else '✗'}" for k, v in toolchains().items())


def _lib_name(stem: str) -> str:
    if sys.platform.startswith("win"):
        return stem + ".dll"
    return "lib" + stem + (".dylib" if sys.platform == "darwin" else ".so")


def _compile_python(f: Dict) -> Tuple[bool, str]:
    src = Path(f["path"]).read_text(encoding="utf-8")
    try:
        compile(src, f["path"], "exec", dont_inherit=True)
    except SyntaxError as exc:
        return False, f"{exc.filename}:{exc.lineno}: {exc.msg}"
    return True, "syntax ok"


def _isolated_import_check(mods: List[str]) -> Tuple[bool, str]:
    """Import every overridden / appended module in a child interpreter with the overlay active."""
    mods = [m for m in mods if m and m not in NO_RELOAD]
    if not mods:
        return True, "nothing to import-check"
    code = ("import sys; sys.path.insert(0, %r); import dev_overlay as d; d._install_hooks();\n"
            "import importlib\nfor m in %r: importlib.import_module(m)\nprint('IMPORT-OK')" % (str(CORE_ROOT), mods))
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", GROOVEBOX_DEV_OVERLAY_DIR=str(overlay_root()),
               PYTHONDONTWRITEBYTECODE="1")
    try:
        r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120, env=env,
                           cwd=str(overlay_root() / "build"))
    except subprocess.TimeoutExpired:
        return False, "import check timed out (an overlay module blocks at import)"
    if "IMPORT-OK" in r.stdout:
        return True, f"imports ok: {', '.join(mods)}"
    tail = (r.stderr or r.stdout).strip().splitlines()[-6:]
    return False, "import failed:\n  " + "\n  ".join(tail) + (f"\n  (exit {r.returncode})" if r.returncode else "")


def _cpp_unit(files_: List[Dict]) -> Optional[Tuple[List[str], str]]:
    """→ (source list, label) for the overlay accelerator: overlay src replaces the core TU; appends #include it."""
    by = {(f["kind"], f["rel"]): f for f in files_ if f["rel"].endswith(".cpp")}
    if not by:
        return None
    srcs, appends = [f for (k, _), f in by.items() if k == "src"], [f for (k, _), f in by.items() if k == "append"]
    tu = overlay_root() / "build" / "cpp" / "overlay_accel.tu.cpp"
    lines = ["// generated by dev_overlay: references files in place (the core is never copied)"]
    core_cpp = core_path("cpp/groovebox_accel.cpp")
    replaced = any(f["rel"] == "cpp/groovebox_accel.cpp" for f in srcs)
    if core_cpp is not None and not replaced:
        lines.append('#include "%s"' % core_cpp.as_posix())
    for f in srcs + appends:
        lines.append('#line 1 "%s"' % Path(f["path"]).as_posix())
        lines.append('#include "%s"' % Path(f["path"]).as_posix())
    _write(tu, "\n".join(lines) + "\n")
    return [str(tu)], "C++ accelerator"


def _compile_cpp(files_: List[Dict]) -> Tuple[bool, str, Optional[str]]:
    unit = _cpp_unit(files_)
    if unit is None:
        return True, "", None
    cxx = _which(os.environ.get("CXX"), "g++", "c++", "clang++")
    if not cxx:
        return False, "no C++ compiler found (install g++ or clang++)", None
    out = overlay_root() / "build" / "native" / _lib_name("groovebox_overlay_accel")
    _guard_write(out); out.parent.mkdir(parents=True, exist_ok=True)
    inc = [f"-I{CORE_ROOT / 'cpp'}", f"-I{CORE_ROOT / 'sCode' / 'bootstrap_source' / 'portable'}"]
    flags = ["-std=c++17", "-O2", "-DNDEBUG", "-fPIC", *inc, "-shared"]      # default visibility: your extern "C" fns export
    if sys.platform == "darwin":
        flags[-1] = "-dynamiclib"
    tmp = out.with_name(out.name + ".part")
    cmd = [cxx, *flags, *unit[0], "-o", str(tmp)]
    if not sys.platform.startswith("win") and sys.platform != "darwin":
        cmd.append("-Wl,--as-needed")
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if r.returncode != 0:
        tmp.unlink(missing_ok=True)
        return False, "C++ compile failed:\n" + r.stderr.strip()[-2500:], None
    os.replace(tmp, out)
    return True, f"C++ → {out.name}", str(out)


def _compile_rust(files_: List[Dict]) -> Tuple[bool, str, Optional[str]]:
    rs = [f for f in files_ if f["rel"].endswith(".rs")]
    if not rs:
        return True, "", None
    rustc = _which(os.environ.get("RUSTC"), "rustc")
    if not rustc:
        return False, "Rust overlay needs rustc (scripts/ensure_rust_toolchain.py installs it)", None
    root = overlay_root() / "build" / "rust"
    core_lib = core_path("rust/groovebox_accel/src/lib.rs")
    replaced = any(f["kind"] == "src" and f["rel"] == "rust/groovebox_accel/src/lib.rs" for f in rs)
    lines = ["// generated by dev_overlay: mounts files in place (the core is never copied)", "#![allow(dead_code)]"]
    if core_lib is not None and not replaced:
        lines.append('#[path = "%s"] mod gb_core;' % core_lib.as_posix())
    for i, f in enumerate(rs):
        lines.append('#[path = "%s"] mod overlay_%d;' % (Path(f["path"]).as_posix(), i))
    crate = _write(root / "overlay_crate.rs", "\n".join(lines) + "\n")
    out = root / _lib_name("groovebox_overlay_rust")
    _guard_write(out)
    r = subprocess.run([rustc, "--edition", "2021", "--crate-type", "cdylib", "-C", "opt-level=3", "-C", "panic=abort",
                        "--crate-name", "groovebox_overlay_rust", str(crate), "-o", str(out)],
                       capture_output=True, text=True, timeout=900)
    if r.returncode != 0:
        return False, "Rust compile failed:\n" + r.stderr.strip()[-2500:], None
    return True, f"Rust → {out.name}", str(out)


def _compile_scode(f: Dict) -> Tuple[bool, str]:
    text = Path(f["path"]).read_text(encoding="utf-8")
    if f["kind"] == "append":
        text = read_core(f["rel"]) + "\n" + text          # in memory only
    try:
        from scode.compiler import compile_text
        ir, digest = compile_text(text)
    except Exception as exc:
        return False, f"sCode: {type(exc).__name__}: {exc}"
    ir["source"] = f["rel"]; ir["overlay_kind"] = f["kind"]; ir["sha256"] = digest
    _write(overlay_root() / "build" / "sir" / (f["kind"] + "--" + f["rel"].replace("/", "--") + ".sir.json"),
           json.dumps(ir, sort_keys=True))
    return True, f"sIR {digest[:12]} ({len(ir.get('nodes', []))} nodes)"


def _compile_julia(f: Dict) -> Tuple[bool, str]:
    jl = _which(os.environ.get("JULIA"), "julia")
    text = Path(f["path"]).read_text(encoding="utf-8")
    if f["kind"] == "append":
        text = read_core(f["rel"]) + "\n" + text
    if not jl:
        return True, "julia not installed — saved, not parsed (installs with the hybrid runtime)"
    r = subprocess.run([jl, "--startup-file=no", "-e",
                        "ex = Meta.parseall(read(stdin, String)); "
                        "bad = [e for e in ex.args if e isa Expr && e.head in (:error, :incomplete)]; "
                        "isempty(bad) || (println(stderr, bad[1]); exit(1))"],
                       input=text, capture_output=True, text=True, timeout=300)
    return (r.returncode == 0), ("Julia parse ok" if r.returncode == 0 else "Julia: " + r.stderr.strip()[-1500:])


def compile_all(progress: Callable[[str], None] = None) -> Dict:
    """Compile / check every overlay file. Enabling requires the result to be current and ok."""
    say = progress or (lambda s: None)
    with _LOCK:
        fl = files(); report = []; ok = True; native = {}
        for f in fl:
            ext = os.path.splitext(f["rel"])[1]
            if ext == ".py":
                good, msg = _compile_python(f)
            elif ext == ".sC":
                good, msg = _compile_scode(f)
            elif ext == ".jl":
                good, msg = _compile_julia(f)
            else:
                continue
            report.append(f"{'✓' if good else '✗'} {f['kind']}/{f['rel']}: {msg}"); say(report[-1]); ok &= good
        for name, fn in (("cpp", _compile_cpp), ("rust", _compile_rust)):
            good, msg, out = fn(fl)
            if msg:
                report.append(f"{'✓' if good else '✗'} {msg}"); say(report[-1])
            ok &= good
            if out:
                good, msg = _native_smoke(out)
                report.append(f"{'✓' if good else '✗'} {os.path.basename(out)}: {msg}"); say(report[-1]); ok &= good
                if good:
                    native[name] = out
        if ok:
            mods = sorted({_module_name(f["rel"]) for f in fl if f["rel"].endswith(".py")} - {None})
            good, msg = _isolated_import_check(mods)
            report.append(f"{'✓' if good else '✗'} {msg}"); say(report[-1]); ok &= good
        st = load_state()
        st.update({"compiled_digest": _digest() if ok else "", "compiled_ok": ok, "compiled_at": time.time(),
                   "native": native, "report": report})
        _save_state(st)
        log(("COMPILE OK" if ok else "COMPILE FAILED") + f" ({len(fl)} files)")
        return {"ok": ok, "report": report, "native": native, "files": len(fl)}


def compile_is_current() -> bool:
    st = load_state()
    return bool(st.get("compiled_ok")) and st.get("compiled_digest") == _digest()


# ============================================================================ native libraries
_NATIVE_SMOKE = r"""
import ctypes, math, sys
lib = ctypes.CDLL(sys.argv[1])
names = [n for n in sys.argv[2:] if hasattr(lib, n)]
if hasattr(lib, "gb_series_cyclic_isn"):
    f = lib.gb_series_cyclic_isn; f.argtypes = [ctypes.c_double]; f.restype = ctypes.c_double
    v = f(0.37); assert math.isfinite(v)
if hasattr(lib, "gb_hardclip_f32"):
    P = ctypes.POINTER(ctypes.c_float); a = (ctypes.c_float * 8)(*[i - 4 for i in range(8)]); o = (ctypes.c_float * 8)()
    f = lib.gb_hardclip_f32; f.argtypes = [P, P, ctypes.c_size_t, ctypes.c_float, P]; f.restype = None
    f(a, a, 8, 1.0, o)
print("SMOKE-OK", len(names))
"""


def _core_symbols() -> List[str]:
    gb = sys.modules.get("groovebox")
    funcs = getattr(gb, "_GB_ACCEL_FUNCS", None) if gb else None
    if isinstance(funcs, dict) and funcs:
        return sorted({getattr(f, "__name__", "") for f in funcs.values()} - {""})
    return ["gb_hardclip_f32", "gb_series_cyclic_isn", "gb_series_cyclic_isn_vec", "gb_blend_rect_f32", "gb_blend_line_f32"]


def _native_smoke(path: str) -> Tuple[bool, str]:
    """Load + call the new library in a child process first: a crashing library can never take the app down."""
    try:
        r = subprocess.run([sys.executable, "-c", _NATIVE_SMOKE, path, *_core_symbols()], capture_output=True,
                           text=True, timeout=60)
    except subprocess.TimeoutExpired:
        return False, "smoke test hung"
    if "SMOKE-OK" in r.stdout:
        n = r.stdout.split("SMOKE-OK", 1)[1].strip()
        return True, f"loads and runs in isolation · {n} accelerator entry points"
    return False, f"smoke test failed (exit {r.returncode}): " + (r.stderr.strip()[-400:] or "crashed")


# ============================================================================ activation (session only)
class _Session:
    active = False
    enabled_at = 0.0
    finder = None
    reloaded: Dict[str, Dict] = {}      # module -> exact original namespace (restored on rollback)
    appended: Dict[str, Dict] = {}      # module -> {"globals": {...snapshot}, "classes": {name: {...}}}
    native_saved: Optional[Dict] = None
    native_lib = None
    errors = 0
    last_error = ""
    reason = ""
    listeners: List[Callable[[str, str], None]] = []


S = _Session()
_MISSING = object()


def core(name: str) -> types.ModuleType:
    """The installed core version of module `name`, loaded from its file in place (for overrides to build on)."""
    key = "groovebox_core." + name
    if key in sys.modules:
        return sys.modules[key]
    spec = importlib.machinery.PathFinder.find_spec(name.split(".")[-1], [str(CORE_ROOT / Path(*name.split(".")[:-1]))])
    if spec is None or spec.origin is None or not _inside(Path(spec.origin).resolve(), CORE_ROOT):
        raise ImportError(f"no installed core module {name}")
    spec = importlib.util.spec_from_file_location(key, spec.origin)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[key] = mod
    spec.loader.exec_module(mod)
    return mod


class _AppendLoader(importlib.abc.Loader):
    def __init__(self, inner, append_path: str):
        self.inner, self.append_path = inner, append_path

    def create_module(self, spec):
        return self.inner.create_module(spec) if hasattr(self.inner, "create_module") else None

    def exec_module(self, module):
        self.inner.exec_module(module)
        code = compile(Path(self.append_path).read_text(encoding="utf-8"), self.append_path, "exec")
        exec(code, module.__dict__)


class OverlayFinder(importlib.abc.MetaPathFinder):
    def __init__(self, root: Path):
        self.root = root

    def _overlay_file(self, kind, fullname):
        base = self.root / kind / Path(*fullname.split("."))
        for cand in (base.with_suffix(".py"), base / "__init__.py"):
            if cand.is_file():
                return cand
        return None

    def find_spec(self, fullname, path=None, target=None):
        if fullname.startswith("groovebox_core.") or fullname in ("dev_overlay",):
            return None
        src = self._overlay_file("src", fullname)
        app = self._overlay_file("append", fullname)
        if src is not None:
            spec = importlib.util.spec_from_file_location(
                fullname, src, submodule_search_locations=[str(src.parent)] if src.name == "__init__.py" else None)
        else:
            spec = None
            if app is not None:
                for f in sys.meta_path:
                    if f is self or not hasattr(f, "find_spec"):
                        continue
                    try:
                        spec = f.find_spec(fullname, path, target)
                    except Exception:
                        spec = None
                    if spec is not None:
                        break
        if spec is not None and app is not None and spec.loader is not None:
            spec.loader = _AppendLoader(spec.loader, str(app))
        return spec


def _install_hooks():
    if S.finder is None:
        S.finder = OverlayFinder(overlay_root())
        sys.meta_path.insert(0, S.finder)
    importlib.invalidate_caches()


def _remove_hooks():
    if S.finder is not None:
        try:
            sys.meta_path.remove(S.finder)
        except ValueError:
            pass
        S.finder = None
    importlib.invalidate_caches()


def _snapshot(mod) -> Dict:
    snap = {"globals": dict(mod.__dict__), "classes": {}}
    for k, v in list(mod.__dict__.items()):
        if isinstance(v, type) and getattr(v, "__module__", None) == mod.__name__:
            snap["classes"][k] = (v, dict(v.__dict__))
    return snap


def _restore(mod, snap: Dict):
    for k in list(mod.__dict__.keys()):
        if k not in snap["globals"]:
            del mod.__dict__[k]
    mod.__dict__.update(snap["globals"])
    for _name, (cls, attrs) in snap["classes"].items():
        for k in list(vars(cls).keys()):
            if k not in attrs and not k.startswith("__"):
                try:
                    delattr(cls, k)
                except (AttributeError, TypeError):
                    pass
        for k, v in attrs.items():
            if k.startswith("__") or vars(cls).get(k, _MISSING) is v:
                continue
            try:
                setattr(cls, k, v)
            except (AttributeError, TypeError):
                pass


def _live_module(name):
    if name == "groovebox" and "groovebox" not in sys.modules:
        m = sys.modules.get("__main__")
        if m is not None and os.path.basename(getattr(m, "__file__", "") or "") == "groovebox.py":
            return m
    return sys.modules.get(name)


def _swap_native(path: str):
    gb = _live_module("groovebox")
    funcs = getattr(gb, "_GB_ACCEL_FUNCS", None) if gb else None
    if not isinstance(funcs, dict):
        return "native: core function table not loaded — library built, used by new imports only"
    lib = ctypes.CDLL(path)
    saved = {"funcs": dict(funcs)}
    for g in ("_SERIES_CYC_NATIVE", "_SERIES_CYC_VEC_NATIVE"):
        saved[g] = getattr(gb, g, None)
    for g in ("_VIDEO_BLEND_RECT", "_VIDEO_BLEND_LINE"):
        holder = getattr(gb, g, None)
        saved[g] = list(holder) if isinstance(holder, list) else None
    swapped = 0
    new = {}
    for key, f in funcs.items():
        nm = getattr(f, "__name__", None)
        nf = getattr(lib, nm, None) if nm else None
        if nf is None:
            continue
        nf.argtypes, nf.restype = getattr(f, "argtypes", None), getattr(f, "restype", None)
        new[key] = nf; swapped += 1
    funcs.update(new)
    remap = {id(v): new[k] for k, v in saved["funcs"].items() if k in new}
    for g in ("_SERIES_CYC_NATIVE", "_SERIES_CYC_VEC_NATIVE"):
        v = saved[g]
        if v is not None and id(v) in remap:
            setattr(gb, g, remap[id(v)])
    for g in ("_VIDEO_BLEND_RECT", "_VIDEO_BLEND_LINE"):
        holder = getattr(gb, g, None)
        if isinstance(holder, list) and holder and id(holder[0]) in remap:
            holder[0] = remap[id(holder[0])]
    S.native_saved, S.native_lib = saved, lib
    return f"native: {swapped}/{len(funcs)} accelerator entry points now from {os.path.basename(path)}"


def _restore_native():
    saved = S.native_saved
    gb = _live_module("groovebox")
    if not saved or gb is None:
        return
    funcs = getattr(gb, "_GB_ACCEL_FUNCS", None)
    if isinstance(funcs, dict):
        funcs.clear(); funcs.update(saved["funcs"])
    for g in ("_SERIES_CYC_NATIVE", "_SERIES_CYC_VEC_NATIVE"):
        if hasattr(gb, g):
            setattr(gb, g, saved[g])
    for g in ("_VIDEO_BLEND_RECT", "_VIDEO_BLEND_LINE"):
        holder = getattr(gb, g, None)
        if isinstance(holder, list) and saved[g] is not None:
            holder[:] = saved[g]
    S.native_saved = None   # the overlay CDLL stays mapped (unloading a live library is unsafe); nothing calls it


def enable(confirm_session: bool = False) -> Dict:
    """Turn the overlay on for THIS process only. Must be called from the Performance UI (confirm_session=True)."""
    if not confirm_session:
        raise PermissionError("the developer overlay is enabled only from Performance, once per session")
    with _LOCK:
        if S.active:
            return {"ok": True, "report": ["already enabled"]}
        if not compile_is_current():
            return {"ok": False, "report": ["compile first — the overlay changed since its last successful compile"]}
        report = []
        fl = files()
        _install_hooks()
        S.reloaded, S.appended, S.errors, S.last_error, S.reason = {}, {}, 0, "", ""
        try:
            for f in fl:
                mod_name = _module_name(f["rel"])
                if not mod_name:
                    continue
                live = _live_module(mod_name)
                if live is None:
                    report.append(f"{f['kind']}/{f['rel']}: applies when {mod_name} is first imported")
                    continue
                if f["kind"] == "append" and not any(g["kind"] == "src" and g["rel"] == f["rel"] for g in fl):
                    S.appended[mod_name] = _snapshot(live)
                    exec(compile(Path(f["path"]).read_text(encoding="utf-8"), f["path"], "exec"), live.__dict__)
                    report.append(f"append/{f['rel']}: applied live to {mod_name}")
                elif f["kind"] == "src":
                    if mod_name in NO_RELOAD:
                        report.append(f"src/{f['rel']}: {mod_name} is the running app — use append/{f['rel']} to change it live")
                        continue
                    S.reloaded[mod_name] = dict(live.__dict__)
                    importlib.reload(live)
                    report.append(f"src/{f['rel']}: {mod_name} re-imported from the overlay")
            nat = load_state().get("native") or {}
            pref = os.environ.get("GROOVEBOX_NATIVE_BACKEND", "auto").strip().lower()
            order = ["cpp", "rust"] if pref == "cpp" else ["rust", "cpp"]
            for k in order:
                if nat.get(k) and os.path.isfile(nat[k]):
                    report.append(_swap_native(nat[k])); break
        except Exception as exc:
            report.append(f"✗ enable failed: {type(exc).__name__}: {exc} — back to core")
            S.active = True
            disable(f"enable failed: {exc}")
            return {"ok": False, "report": report}
        S.active, S.enabled_at = True, time.time()
        _hook_errors()
        log("ENABLED for this session: " + "; ".join(report))
        _notify("enabled", "; ".join(report))
        return {"ok": True, "report": report or ["enabled (no modules loaded yet)"]}


def disable(reason: str = "manual") -> Dict:
    """Back to the installed core (always safe to call)."""
    with _LOCK:
        if not S.active and S.finder is None:
            return {"ok": True, "report": ["already on the core"]}
        report = []
        _remove_hooks()
        for name, snap in list(S.appended.items()):
            live = _live_module(name)
            if live is not None:
                _restore(live, snap); report.append(f"{name}: appended changes undone")
        for name, ns in S.reloaded.items():
            live = sys.modules.get(name)
            if live is not None:                       # the exact core objects come back (no re-execution)
                live.__dict__.clear(); live.__dict__.update(ns)
                report.append(f"{name}: core module restored")
        for name in [m for m in list(sys.modules) if m not in S.reloaded and _is_overlay_module(sys.modules.get(m))]:
            sys.modules.pop(name, None); report.append(f"{name}: overlay-only module unloaded")
        _restore_native()
        S.active, S.appended, S.reloaded, S.reason = False, {}, {}, reason
        st = load_state(); st["last_rollback"] = {"at": time.time(), "reason": reason}; _save_state(st)
        log(f"DISABLED ({reason}): " + "; ".join(report))
        _notify("disabled", reason)
        return {"ok": True, "report": report or ["back on the core"]}


def _is_overlay_module(m) -> bool:
    f = getattr(m, "__file__", None)
    if not f:
        return False
    try:
        return _inside(Path(f).resolve(), overlay_root())
    except Exception:
        return False


def is_active() -> bool:
    return S.active


def add_listener(fn: Callable[[str, str], None]):
    if fn not in S.listeners:
        S.listeners.append(fn)


def _notify(event: str, detail: str):
    for fn in list(S.listeners):
        try:
            fn(event, detail)
        except Exception:
            pass


# ============================================================================ health watchdog
def _overlay_in_tb(tb) -> bool:
    root = str(overlay_root())
    for fr in traceback.extract_tb(tb):
        if fr.filename.startswith(root):
            return True
    return False


_PREV_HOOKS = {}


def _hook_errors():
    if _PREV_HOOKS:
        return
    _PREV_HOOKS["sys"] = sys.excepthook
    _PREV_HOOKS["thread"] = threading.excepthook

    def sys_hook(t, v, tb):
        if S.active and _overlay_in_tb(tb):
            S.errors += 1; S.last_error = f"{t.__name__}: {v}"
            log("overlay error: " + "".join(traceback.format_exception(t, v, tb))[-1500:])
        _PREV_HOOKS["sys"](t, v, tb)

    def thread_hook(a):
        if S.active and a.exc_traceback is not None and _overlay_in_tb(a.exc_traceback):
            S.errors += 1; S.last_error = f"{a.exc_type.__name__}: {a.exc_value}"
        _PREV_HOOKS["thread"](a)
    sys.excepthook = sys_hook
    threading.excepthook = thread_hook


def report_error(exc: BaseException):
    """For callers that catch exceptions themselves (Qt slots): count it if it came from overlay code."""
    if S.active and exc.__traceback__ is not None and _overlay_in_tb(exc.__traceback__):
        S.errors += 1; S.last_error = f"{type(exc).__name__}: {exc}"


_THERMAL_PATHS: Optional[List[str]] = None


def max_temperature_c() -> Optional[float]:
    global _THERMAL_PATHS
    if _THERMAL_PATHS is None:
        _THERMAL_PATHS = glob.glob("/sys/class/thermal/thermal_zone*/temp") + glob.glob("/sys/class/hwmon/hwmon*/temp*_input")
    best = None
    for p in _THERMAL_PATHS:
        try:
            v = int(open(p).read().strip()) / 1000.0
        except Exception:
            continue
        if 0.0 < v < 150.0:
            best = v if best is None else max(best, v)
    if best is None:
        try:
            import psutil
            for arr in (psutil.sensors_temperatures() or {}).values():
                for t in arr:
                    if t.current and 0 < t.current < 150:
                        best = t.current if best is None else max(best, t.current)
        except Exception:
            pass
    return best


def free_ram_mb() -> Optional[float]:
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemAvailable:"):
                    return int(line.split()[1]) / 1024.0
    except Exception:
        pass
    try:
        import psutil
        return psutil.virtual_memory().available / 1048576.0
    except Exception:
        return None


def settings() -> Dict:
    try:
        import compat_settings as cs
        s = cs.load()
    except Exception:
        s = {}
    return {"policy": s.get("dev_overlay_rollback", "auto"), "max_temp_c": s.get("dev_overlay_max_temp_c", 90),
            "min_free_mb": s.get("dev_overlay_min_free_mb", 512), "stall_s": s.get("dev_overlay_stall_s", 3.0),
            "max_errors": s.get("dev_overlay_max_errors", 3)}


class Watchdog:
    """Sampled by a GUI-thread timer (tick()). Sustained trouble → disable(reason) when policy is auto."""
    INTERVAL = 1.0
    SUSTAIN = 3

    def __init__(self):
        self.last = None; self.hot = 0; self.low = 0; self.stalls = 0
        self.sample = {}

    def tick(self, now: Optional[float] = None, temp=_MISSING, free=_MISSING) -> Optional[str]:
        now = time.monotonic() if now is None else now
        cfg = settings()
        t = max_temperature_c() if temp is _MISSING else temp
        m = free_ram_mb() if free is _MISSING else free
        gap = (now - self.last) if self.last is not None else self.INTERVAL
        self.last = now
        self.sample = {"temp_c": t, "free_mb": m, "gap_s": gap, "errors": S.errors, "active": S.active,
                       "policy": cfg["policy"]}
        if not S.active and not ScriptRun._LIVE:
            self.hot = self.low = self.stalls = 0
            return None
        self.hot = self.hot + 1 if (t is not None and t >= float(cfg["max_temp_c"])) else 0
        self.low = self.low + 1 if (m is not None and m <= float(cfg["min_free_mb"])) else 0
        self.stalls += 1 if gap >= float(cfg["stall_s"]) else 0
        reason = None
        if self.hot >= self.SUSTAIN:
            reason = f"thermal: {t:.0f} °C ≥ {cfg['max_temp_c']} °C for {self.hot} s"
        elif self.low >= self.SUSTAIN:
            reason = f"memory: {m:.0f} MB free ≤ {cfg['min_free_mb']} MB"
        elif self.stalls >= 2:
            reason = f"usability: the interface froze {self.stalls}× (≥ {cfg['stall_s']} s)"
        elif S.errors >= int(cfg["max_errors"]):
            reason = f"errors: {S.errors} from overlay code (last: {S.last_error[:120]})"
        self.sample["trouble"] = reason
        if reason and ScriptRun._LIVE and (self.hot >= self.SUSTAIN or self.low >= self.SUSTAIN):
            ScriptRun.stop_all("stopped by the watchdog — " + reason)
        if reason and cfg["policy"] == "auto" and S.active:
            disable("auto rollback — " + reason)
            self.hot = self.low = self.stalls = 0
            return reason
        return None


def status() -> Dict:
    st = load_state()
    return {"active": S.active, "files": len(files()), "compile_current": compile_is_current(),
            "compiled_ok": st.get("compiled_ok", False), "last_rollback": st.get("last_rollback"),
            "errors": S.errors, "root": str(overlay_root()), "native": st.get("native", {})}


# ============================================================================ scratchpad: run one script
_SC_RUNNER = r"""
import json, sys
sys.path.insert(0, sys.argv[1])
from scode.compiler import compile_text
text = open(sys.argv[2], encoding="utf-8").read()
ir, digest = compile_text(text)
def walk(nodes, depth=0):
    for n in nodes:
        if n["kind"] == "print" and n["name"] and not n["args"]:
            print(n["name"])
        elif n["kind"] == "print":
            print("[print expression]", " ".join([n["name"], *n["args"]]).strip())
        elif n["kind"] == "setting":
            print("setting", n["name"], "=", (n["args"] or [n["attrs"].get("value", "")])[0])
        walk(n["children"], depth + 1)
walk(ir["nodes"])
print("--- sIR", digest[:16], "·", sum(1 for _ in ir["nodes"]), "top-level nodes")
print(json.dumps(ir, indent=1)[:4000])
"""

RUN_LANGS = (".py", ".jl", ".sC", ".cpp", ".rs")


def scratch_path(ext: str = ".py", name: str = "") -> Path:
    if ext not in RUN_LANGS:
        raise ValueError("scratchpad languages: " + " ".join(RUN_LANGS))
    stem = "".join(c for c in (name or time.strftime("scratch-%Y%m%d-%H%M%S")) if c.isalnum() or c in "-_.") or "scratch"
    return overlay_root() / "scratch" / (stem.rsplit(".", 1)[0] + ext)


def _limits(cfg_mem_mb: Optional[float]):
    def pre():
        try:
            os.setsid()
        except Exception:
            pass
        try:
            import resource
            if cfg_mem_mb:
                b = int(cfg_mem_mb * 1048576)
                resource.setrlimit(resource.RLIMIT_AS, (b, b))
            os.nice(5)
        except Exception:
            pass
    return pre if os.name == "posix" else None


def _build_native_runner(path: Path, ext: str) -> Tuple[Optional[List[str]], str]:
    out = overlay_root() / "build" / "run" / (hashlib.sha256(path.read_bytes()).hexdigest()[:16] + (".exe" if os.name == "nt" else ""))
    _guard_write(out); out.parent.mkdir(parents=True, exist_ok=True)
    if out.is_file():
        return [str(out)], "cached build"
    if ext == ".cpp":
        cxx = _which(os.environ.get("CXX"), "g++", "c++", "clang++")
        if not cxx:
            return None, "no C++ compiler found"
        cmd = [cxx, "-std=c++17", "-O2", f"-I{CORE_ROOT / 'cpp'}", str(path), "-o", str(out)]
    else:
        rustc = _which(os.environ.get("RUSTC"), "rustc")
        if not rustc:
            return None, "rustc not installed (scripts/ensure_rust_toolchain.py)"
        cmd = [rustc, "--edition", "2021", "-O", str(path), "-o", str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    if r.returncode != 0:
        return None, "compile failed:\n" + r.stderr.strip()[-3000:]
    return [str(out)], "built " + out.name


def script_command(path, use_overlay: bool = True) -> Tuple[Optional[List[str]], str]:
    """argv that runs one script in a child process (None + reason when it cannot run here)."""
    path = Path(path).resolve(); ext = path.suffix
    if ext == ".py":
        boot = ("import sys, runpy; sys.path.insert(0, %r); sys.argv = [%r]\n" % (str(CORE_ROOT), str(path)))
        if use_overlay:
            boot += "import dev_overlay; dev_overlay._install_hooks()\n"
        boot += "runpy.run_path(%r, run_name='__main__')" % str(path)
        return [sys.executable, "-u", "-c", boot], "python"
    if ext == ".jl":
        jl = _which(os.environ.get("JULIA"), "julia")
        return ([jl, "--startup-file=no", str(path)], "julia") if jl else (None, "julia is not installed")
    if ext == ".sC":
        return [sys.executable, "-u", "-c", _SC_RUNNER, str(CORE_ROOT), str(path)], "sCode → sIR"
    if ext in (".cpp", ".rs"):
        return _build_native_runner(path, ext)
    return None, "cannot run " + ext


class ScriptRun:
    """One running script. Output arrives through on_line(text) from a reader thread; stop() ends the whole tree."""
    _LIVE: "set" = set()

    def __init__(self, path, on_line: Callable[[str], None], on_exit: Callable[[int, float], None] = None,
                 use_overlay: bool = True, timeout_s: Optional[float] = None):
        self.path = str(path); self.on_line = on_line; self.on_exit = on_exit or (lambda c, t: None)
        self.use_overlay = use_overlay; self.proc = None; self.t0 = 0.0; self.code = None
        try:
            import compat_settings as cs
            cfg = cs.load()
        except Exception:
            cfg = {}
        self.timeout_s = float(timeout_s or cfg.get("dev_overlay_script_timeout_s", 600))
        free = free_ram_mb()
        self.mem_mb = max(256.0, min(8192.0, free * 0.6)) if free else None

    def start(self):
        threading.Thread(target=self._run, name="overlay-script", daemon=True).start()
        return self

    def _run(self):
        try:
            argv, how = script_command(self.path, self.use_overlay)
        except Exception as exc:
            argv, how = None, f"{type(exc).__name__}: {exc}"
        if argv is None:
            self.on_line("✗ " + how); self.code = -1; self.on_exit(-1, 0.0); return
        self.on_line(f"▶ {os.path.basename(self.path)} ({how}) · memory cap {self.mem_mb or 0:.0f} MB · "
                     f"time limit {self.timeout_s:.0f} s")
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONUNBUFFERED="1",
                   GROOVEBOX_DEV_OVERLAY_DIR=str(overlay_root()), QT_QPA_PLATFORM=os.environ.get("QT_QPA_PLATFORM", "offscreen"))
        self.t0 = time.monotonic()
        try:
            self.proc = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                         cwd=str(overlay_root() / "scratch"), env=env, text=True, bufsize=1,
                                         errors="replace", preexec_fn=_limits(self.mem_mb))
        except Exception as exc:
            self.on_line(f"✗ could not start: {exc}"); self.code = -1; self.on_exit(-1, 0.0); return
        ScriptRun._LIVE.add(self)
        timer = threading.Timer(self.timeout_s, lambda: self.stop(f"time limit {self.timeout_s:.0f} s"))
        timer.daemon = True; timer.start()
        n = 0
        try:
            for line in self.proc.stdout:
                n += 1
                if n <= 20000:
                    self.on_line(line.rstrip("\n"))
                elif n == 20001:
                    self.on_line("… output truncated (20 000 lines)")
        finally:
            self.code = self.proc.wait(); timer.cancel(); ScriptRun._LIVE.discard(self)
            dt = time.monotonic() - self.t0
            self.on_line(f"■ exit {self.code} after {dt:.2f} s"); self.on_exit(self.code, dt)

    def running(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def stop(self, why: str = "stopped"):
        p = self.proc
        if p is None or p.poll() is not None:
            return
        self.on_line(f"■ {why}")
        try:
            if os.name == "posix":
                import signal
                os.killpg(p.pid, signal.SIGTERM)
                try:
                    p.wait(2)
                except subprocess.TimeoutExpired:
                    os.killpg(p.pid, signal.SIGKILL)
            else:
                p.kill()
        except Exception:
            try:
                p.kill()
            except Exception:
                pass

    @classmethod
    def stop_all(cls, why: str):
        for r in list(cls._LIVE):
            r.stop(why)
