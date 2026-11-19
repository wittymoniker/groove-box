"""Canonical Python interpreter and process-start contract for Groovebox."""
from __future__ import annotations

import importlib
import sys
import traceback

MIN_PYTHON = (3, 10)

# Keep this contract aligned with BUILD_KIT/build.py: NumPy/SciPy, cffi,
# Debian PyQt6 and Pillow are required. sounddevice is optional because the
# appliance also has a native Qt/OS audio path when PortAudio is unavailable.
REQUIRED = (
    ("numpy", "numpy"),
    ("scipy", "scipy"),
    ("cffi", "cffi"),
    ("PyQt6.QtCore", "PyQt6"),
    ("PyQt6.QtMultimedia", "PyQt6"),
    ("PyQt6.QtMultimediaWidgets", "PyQt6"),
    ("PIL", "Pillow"),
)
OPTIONAL = (
    ("sounddevice", "sounddevice"),
    ("PyQt6.QtWebEngineWidgets", "PyQt6-WebEngine"),
)

def interpreter_is_supported(implementation_name=None, version_info=None):
    implementation_name = implementation_name or sys.implementation.name
    version_info = version_info or sys.version_info
    return implementation_name == "cpython" and tuple(version_info[:2]) >= MIN_PYTHON

def interpreter_error(implementation_name=None, version_info=None):
    implementation_name = implementation_name or sys.implementation.name
    version_info = version_info or sys.version_info
    if interpreter_is_supported(implementation_name, version_info):
        return None
    found = ".".join(str(x) for x in tuple(version_info)[:3])
    required = ".".join(str(x) for x in MIN_PYTHON)
    return f"Groovebox requires CPython {required} or newer; found {implementation_name} {found}."

def validate_runtime():
    """Import required modules with actionable diagnostics; optional ones warn only."""
    error = interpreter_error()
    if error:
        print("PYTHON_RUNTIME_FAIL:", error, file=sys.stderr)
        return 1
    print("PYTHON_RUNTIME_INTERPRETER:", sys.executable, sys.version.replace("\n", " "))
    print("PYTHON_RUNTIME_SYS_PATH:", repr(sys.path))
    failed = []
    for module, distribution in REQUIRED:
        try:
            importlib.import_module(module)
            print(f"PYTHON_RUNTIME_REQUIRED_PASS: {module} ({distribution})")
        except Exception as exc:
            failed.append(module)
            print(f"PYTHON_RUNTIME_REQUIRED_FAIL: {module} ({distribution}): {type(exc).__name__}: {exc}", file=sys.stderr)
            traceback.print_exc()
    for module, distribution in OPTIONAL:
        try:
            importlib.import_module(module)
            print(f"PYTHON_RUNTIME_OPTIONAL_PASS: {module} ({distribution})")
        except Exception as exc:
            print(f"PYTHON_RUNTIME_OPTIONAL_UNAVAILABLE: {module} ({distribution}): {type(exc).__name__}: {exc}")
    if failed:
        print("PYTHON_RUNTIME_RESULT: FAIL; required modules=" + ",".join(failed), file=sys.stderr)
        return 1
    print("PYTHON_RUNTIME_RESULT: PASS")
    return 0
