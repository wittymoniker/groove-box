"""Child-process launch helpers that work from source and from a frozen executable.

GROOVEBOX_FROZEN_HELPER_DISPATCH_20261031

In a PyInstaller build ``sys.executable`` is the Groovebox binary itself, not a
Python interpreter. Running ``[sys.executable, "device_probe_helper.py", ...]``
therefore started a second full Groovebox (the "everything relaunches" bug when
opening Performance or pressing Refresh Devices) and the device probe never ran,
so no audio/video devices were listed and recording was blocked.

Every child-process launch now goes through this module:

* ``helper_argv(module, *args)``  - run a bundled helper module (whitelisted)
* ``script_argv(path, *args)``    - run a Python script file (exported games)
* ``app_argv(*args)``             - start another Groovebox instance on purpose

From source these are the plain interpreter commands used before. When frozen
they re-enter the executable with a dispatch flag that ``run_groovebox.py``
handles first thing, before any GUI, provisioning or appliance logic runs.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

HELPER_FLAG = "--groovebox-helper"
SCRIPT_FLAG = "--groovebox-run-script"
# Only these bundled modules may be run through the helper dispatch.
HELPER_MODULES = frozenset({"device_probe_helper", "export_worker", "rig_worker"})   # GROOVEBOX_R23R_EXPORT_MERGE_20261103

_HERE = Path(__file__).resolve().parent


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def helper_argv(module: str, *args: str) -> list[str]:
    module = str(module)
    if module not in HELPER_MODULES:
        raise ValueError(f"not a Groovebox helper module: {module}")
    if is_frozen():
        return [sys.executable, HELPER_FLAG, module, *map(str, args)]
    return [sys.executable, str(_HERE / f"{module}.py"), *map(str, args)]


def script_argv(path: str | os.PathLike, *args: str) -> list[str]:
    if is_frozen():
        return [sys.executable, SCRIPT_FLAG, str(path), *map(str, args)]
    return [sys.executable, str(path), *map(str, args)]


def app_argv(*args: str) -> list[str]:
    if is_frozen():
        return [sys.executable, *map(str, args)]
    return [sys.executable, str(_HERE / "run_groovebox.py"), *map(str, args)]


def dispatch(argv: list[str] | None = None) -> None:
    """Handle a helper/script re-entry and exit; return normally otherwise."""
    argv = list(sys.argv if argv is None else argv)
    if len(argv) < 3 or argv[1] not in (HELPER_FLAG, SCRIPT_FLAG):
        return
    import runpy
    target = argv[2]
    if argv[1] == HELPER_FLAG:
        if target not in HELPER_MODULES:
            sys.stderr.write(f"Groovebox: refused unknown helper module {target!r}\n")
            raise SystemExit(64)
        sys.argv = [f"{target}.py", *argv[3:]]
        runpy.run_module(target, run_name="__main__", alter_sys=True)
        raise SystemExit(0)
    script = Path(target)
    if not script.is_file():
        sys.stderr.write(f"Groovebox: script not found: {script}\n")
        raise SystemExit(66)
    sys.argv = [str(script), *argv[3:]]
    try:
        import import_fabric
        with import_fabric.application_scope("user-script", [script.parent]):
            runpy.run_path(str(script), run_name="__main__")
    except ImportError:
        sys.path.insert(0, str(script.parent))
        runpy.run_path(str(script), run_name="__main__")
    raise SystemExit(0)
