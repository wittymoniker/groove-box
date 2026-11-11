"""Canonical Python interpreter and process-start contract for Groovebox."""
from __future__ import annotations

import sys

MIN_PYTHON = (3, 10)

# Import targets and their distribution names are shared by the desktop launcher
# and the optional source-runtime provisioner. Keep QtWebEngine optional.
REQUIRED = (
    ("numpy", "numpy"),
    ("scipy", "scipy"),
    ("cffi", "cffi"),
    ("PyQt6.QtCore", "PyQt6"),
    ("PyQt6.QtMultimedia", "PyQt6"),
    ("PyQt6.QtMultimediaWidgets", "PyQt6"),
    ("sounddevice", "sounddevice"),
    ("PIL", "Pillow"),
)
OPTIONAL = (("PyQt6.QtWebEngineWidgets", "PyQt6-WebEngine"),)

def interpreter_is_supported(implementation_name=None, version_info=None):
    """Return True only for the supported CPython baseline or newer."""
    implementation_name = implementation_name or sys.implementation.name
    version_info = version_info or sys.version_info
    return implementation_name == "cpython" and tuple(version_info[:2]) >= MIN_PYTHON

def interpreter_error(implementation_name=None, version_info=None):
    """Describe an unsupported runtime, or return None when it is supported."""
    implementation_name = implementation_name or sys.implementation.name
    version_info = version_info or sys.version_info
    if interpreter_is_supported(implementation_name, version_info):
        return None
    found = ".".join(str(x) for x in tuple(version_info)[:3])
    required = ".".join(str(x) for x in MIN_PYTHON)
    return f"Groovebox requires CPython {required} or newer; found {implementation_name} {found}."
