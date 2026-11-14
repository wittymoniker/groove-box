"""Cross-application import map and lazy import fabric.

The fabric inventories Python modules without importing them, keeps user/developer
application roots scoped, and exposes optional integrations through explicit lazy
loads. It deliberately does not preload every mapped module or share mutable module
state across processes.
"""
from __future__ import annotations

import ast
import contextlib
import hashlib
import importlib
import importlib.util
import json
import os
import sys
import sysconfig
import threading
import time
from pathlib import Path
from typing import Iterable, Iterator

_LOCK = threading.RLock()
_IMPORT_STATS: dict[str, dict] = {}
_CACHE_VERSION = 1
_SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", "node_modules", "target", "dist",
              "build", "tests", "test", "release-tests", "BUILD_ISO", "BUILD_KIT"}
_OPTIONAL = {"mido", "juliacall", "cv2", "torch", "cupy", "moderngl", "OpenGL",
             "PyQt6.QtWebEngineWidgets", "soundfile", "av", "serial", "bleak"}


def _roots(root: Path, extra_roots: Iterable[os.PathLike | str] = ()) -> list[Path]:
    found = [root.resolve()]
    for value in extra_roots:
        try:
            p = Path(value).expanduser().resolve()
            if p.is_dir() and p not in found:
                found.append(p)
        except (OSError, TypeError, ValueError):
            continue
    return found


def application_roots(root: os.PathLike | str) -> dict[str, list[str]]:
    """Read configured user/dev app roots; return existing paths only."""
    base = Path(root).resolve()
    result = {"core": [str(base)], "user": [], "developer": []}
    try:
        from groovebox_paths import base_dir
        data_root = Path(base_dir())
    except Exception:
        data_root = Path.home() / ".groovebox"
    for key, env_name, fallback in (
        ("user", "GROOVEBOX_USER_APP_PATHS", data_root / "apps"),
        ("developer", "GROOVEBOX_DEV_APP_PATHS", data_root / "dev-overlay" / "src"),
    ):
        raw = os.environ.get(env_name, "")
        paths = [Path(x).expanduser() for x in raw.split(os.pathsep) if x.strip()] if raw else [fallback]
        result[key] = [str(p.resolve()) for p in paths if p.is_dir()]
    return result


def _module_name(path: Path, base: Path) -> str | None:
    try:
        rel = path.relative_to(base).with_suffix("")
    except ValueError:
        return None
    parts = list(rel.parts)
    if parts[-1:] == ["__init__"]:
        parts.pop()
    if not parts or any(not part.isidentifier() for part in parts):
        return None
    return ".".join(parts)


def _classify(name: str, local: set[str], stdlib: set[str]) -> str:
    top = name.split(".", 1)[0]
    if top in stdlib or top == "__future__":
        return "stdlib"
    if top in local:
        return "local"
    if top in _OPTIONAL or name in _OPTIONAL:
        return "optional"
    return "external-or-review"


def _source_signature(roots: Iterable[Path]) -> str:
    digest = hashlib.sha256()
    for base in roots:
        for dp, dirs, names in os.walk(base):
            dirs[:] = sorted(d for d in dirs if d not in _SKIP_DIRS and not d.startswith("."))
            for filename in sorted(names):
                if filename.endswith(".py") and not filename.startswith("test_"):
                    path = Path(dp) / filename
                    try:
                        st = path.stat()
                        digest.update(f"{path.relative_to(base)}\0{st.st_size}\0{st.st_mtime_ns}\n".encode())
                    except OSError:
                        continue
    return digest.hexdigest()


def build_import_map(root: os.PathLike | str, extra_roots: Iterable[os.PathLike | str] = (),
                     *, include_source_imports: bool = True) -> dict:
    """Build a deterministic import-to-file map for core and app roots."""
    roots = _roots(Path(root), extra_roots)
    files: dict[str, list[str]] = {}
    source_imports: dict[str, list[dict]] = {}
    local_names: set[str] = set()
    for base in roots:
        for dp, dirs, names in os.walk(base):
            dirs[:] = sorted(d for d in dirs if d not in _SKIP_DIRS and not d.startswith("."))
            for filename in sorted(names):
                if not filename.endswith(".py") or filename.startswith("test_"):
                    continue
                path = Path(dp) / filename
                module = _module_name(path, base)
                if module:
                    local_names.add(module.split(".", 1)[0])
                    files.setdefault(module, []).append(str(path))
    stdlib = set(getattr(sys, "stdlib_module_names", ()))
    if include_source_imports:
        for module, paths in sorted(files.items()):
            rows = []
            for raw in paths:
                p = Path(raw)
                try:
                    tree = ast.parse(p.read_text(encoding="utf-8", errors="replace"))
                except (OSError, SyntaxError, UnicodeError):
                    continue
                for node in ast.walk(tree):
                    names = []
                    if isinstance(node, ast.Import):
                        names = [a.name for a in node.names]
                    elif isinstance(node, ast.ImportFrom) and node.module:
                        names = [node.module]
                    for name in names:
                        rows.append({"name": name, "class": _classify(name, local_names, stdlib),
                                     "line": int(getattr(node, "lineno", 0)), "source": raw})
            if rows:
                source_imports[module] = rows
    return {"schema": _CACHE_VERSION, "python": sys.implementation.cache_tag,
            "roots": [str(p) for p in roots], "signature": _source_signature(roots),
            "modules": {k: list(dict.fromkeys(v)) for k, v in sorted(files.items())},
            "imports": source_imports, "created": time.time()}


def _cache_path(root: Path) -> Path:
    override = os.environ.get("GROOVEBOX_IMPORT_MAP_CACHE", "").strip()
    if override:
        return Path(override).expanduser()
    try:
        from groovebox_paths import base_dir
        return Path(base_dir()) / "cache" / "import-fabric" / f"map-{sys.implementation.cache_tag}.json"
    except Exception:
        return Path.home() / ".cache" / "groovebox" / "import-fabric" / f"map-{sys.implementation.cache_tag}.json"


def load_or_build_map(root: os.PathLike | str, extra_roots: Iterable[os.PathLike | str] = (),
                      *, force: bool = False) -> dict:
    base = Path(root).resolve()
    roots = _roots(base, extra_roots)
    cache = _cache_path(base)
    with _LOCK:
        if not force:
            try:
                data = json.loads(cache.read_text(encoding="utf-8"))
                if (data.get("schema") == _CACHE_VERSION and data.get("python") == sys.implementation.cache_tag
                        and data.get("roots") == [str(p) for p in roots]
                        and data.get("signature") == _source_signature(roots)):
                    return data
            except (OSError, ValueError, TypeError):
                pass
        data = build_import_map(base, roots[1:])
        try:
            cache.parent.mkdir(parents=True, exist_ok=True)
            temp = cache.with_name(cache.name + f".{os.getpid()}.part")
            temp.write_text(json.dumps(data, separators=(",", ":"), sort_keys=True), encoding="utf-8")
            os.replace(temp, cache)
        except OSError:
            pass  # Read-only installs still work; the map remains available in memory.
        return data


def configure(root: os.PathLike | str, *, map_now: bool = False) -> dict:
    """Set safe defaults and optionally warm the map; no modules are imported."""
    os.environ.setdefault("GROOVEBOX_IMPORT_FABRIC", "1")
    os.environ.setdefault("GROOVEBOX_IMPORT_SCOPE", "core")
    if map_now:
        configured = application_roots(root)
        return load_or_build_map(root, [*configured["user"], *configured["developer"]])
    return {"enabled": True, "mapped": False, "scope": os.environ["GROOVEBOX_IMPORT_SCOPE"]}


def timed_import(name: str):
    """Import a requested module and record cold/warm wall time for diagnostics."""
    start = time.perf_counter()
    try:
        return importlib.import_module(name)
    finally:
        elapsed = (time.perf_counter() - start) * 1000.0
        with _LOCK:
            row = _IMPORT_STATS.setdefault(name, {"count": 0, "total_ms": 0.0, "last_ms": 0.0, "max_ms": 0.0})
            row["count"] += 1
            row["total_ms"] += elapsed
            row["last_ms"] = elapsed
            row["max_ms"] = max(row["max_ms"], elapsed)


def import_timings() -> dict[str, dict]:
    """Return a snapshot of requested-import timings, without triggering imports."""
    with _LOCK:
        return {name: dict(row) for name, row in sorted(_IMPORT_STATS.items())}


def import_optional(name: str, *, feature: str | None = None, required: bool = False):
    """Load an optional integration only when the feature is actually requested."""
    try:
        return timed_import(name)
    except ImportError as exc:
        if required:
            raise ImportError(f"Optional integration {feature or name!r} requires {name!r}") from exc
        return None


@contextlib.contextmanager
def application_scope(name: str, paths: Iterable[os.PathLike | str] = ()) -> Iterator[dict]:
    """Temporarily expose an app's import roots; always restore sys.path."""
    clean = []
    for value in paths:
        p = Path(value).expanduser().resolve()
        if p.is_dir() and str(p) not in clean:
            clean.append(str(p))
    before = list(sys.path)
    previous_scope = os.environ.get("GROOVEBOX_IMPORT_SCOPE", "core")
    try:
        for item in reversed(clean):
            if item not in sys.path:
                sys.path.insert(0, item)
        os.environ["GROOVEBOX_IMPORT_SCOPE"] = str(name)
        importlib.invalidate_caches()
        yield {"scope": str(name), "paths": clean}
    finally:
        sys.path[:] = before
        os.environ["GROOVEBOX_IMPORT_SCOPE"] = previous_scope
        importlib.invalidate_caches()


def module_status(root: os.PathLike | str, *, extra_roots=()) -> dict:
    data = load_or_build_map(root, extra_roots)
    return {"module_count": len(data["modules"]), "import_count": sum(map(len, data["imports"].values())),
            "root_count": len(data["roots"]), "cache_tag": data["python"], "mapped_roots": data["roots"]}
