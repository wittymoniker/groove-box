"""Canonical .MCC project file type + per-user OS association helpers.

.MCC is the public Mathematician's Groovebox composition/project document.
The payload remains the unified JSON project snapshot so saves stay transparent,
diffable, recoverable and compatible with the existing deterministic loader.
"""
from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_EXTENSION = ".MCC"
LEGACY_PROJECT_EXTENSIONS = (".mgpr", ".mgpr.part")
MIME_TYPE = "application/x-mathematicians-groovebox-mcc"
WINDOWS_PROGID = "MathematiciansGroovebox.MCC"
DESKTOP_ID = "mathematicians-groovebox.desktop"


def ensure_project_extension(path: str) -> str:
    """Return the canonical save path. Existing legacy suffixes are replaced."""
    value = str(path or "").strip()
    if not value:
        return value
    low = value.lower()
    if low.endswith(PROJECT_EXTENSION.lower()):
        return value
    if low.endswith(".mgpr.part"):
        return value[:-10] + PROJECT_EXTENSION
    if low.endswith(".mgpr"):
        return value[:-5] + PROJECT_EXTENSION
    return value + PROJECT_EXTENSION


def is_project_path(path: str) -> bool:
    low = str(path or "").lower()
    return low.endswith(PROJECT_EXTENSION.lower()) or any(low.endswith(x) for x in LEGACY_PROJECT_EXTENSIONS)


def project_argument(argv=None):
    """Find a project document supplied by shell/double-click invocation."""
    args = list(sys.argv[1:] if argv is None else argv)
    for arg in args:
        if arg and not str(arg).startswith("-") and is_project_path(arg):
            return os.path.abspath(os.path.expanduser(str(arg)))
    return None


def _launch_command(app_script=None):
    if getattr(sys, "frozen", False):
        return [os.path.abspath(sys.executable)]
    script = os.path.abspath(app_script or os.path.join(os.path.dirname(__file__), "groovebox.py"))
    return [os.path.abspath(sys.executable), script]


def _quote_linux(parts):
    import shlex
    return " ".join(shlex.quote(str(p)) for p in parts)


def register_filetype(app_script=None, *, quiet=True):
    """Idempotently register .MCC for the current user; never requires admin."""
    system = platform.system().lower()
    try:
        if system == "windows":
            return _register_windows(app_script)
        if system == "linux":
            return _register_linux(app_script)
        if system == "darwin":
            return _register_macos(app_script)
        return False, f"Unsupported OS: {system}"
    except Exception as exc:
        if not quiet:
            raise
        return False, str(exc)


def _register_windows(app_script=None):
    import winreg
    cmd = _launch_command(app_script)
    command = " ".join(f'"{x}"' for x in cmd) + ' "%1"'
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\.MCC") as key:
        winreg.SetValueEx(key, "", 0, winreg.REG_SZ, WINDOWS_PROGID)
        winreg.SetValueEx(key, "Content Type", 0, winreg.REG_SZ, MIME_TYPE)
    base = rf"Software\Classes\{WINDOWS_PROGID}"
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, base) as key:
        winreg.SetValueEx(key, "", 0, winreg.REG_SZ, "Mathematician's Groovebox Composition")
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, base + r"\DefaultIcon") as key:
        winreg.SetValueEx(key, "", 0, winreg.REG_SZ, f'"{cmd[0]}",0')
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, base + r"\shell\open\command") as key:
        winreg.SetValueEx(key, "", 0, winreg.REG_SZ, command)
    return True, "Windows .MCC association registered for current user"


def _register_linux(app_script=None):
    home = Path.home()
    apps = home / ".local/share/applications"
    mime_pkgs = home / ".local/share/mime/packages"
    apps.mkdir(parents=True, exist_ok=True)
    mime_pkgs.mkdir(parents=True, exist_ok=True)
    command = _quote_linux(_launch_command(app_script)) + " %f"
    desktop = apps / DESKTOP_ID
    desktop.write_text(
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=Mathematician's Groovebox\n"
        f"Exec={command}\n"
        f"MimeType={MIME_TYPE};\n"
        "Terminal=false\n"
        "Categories=AudioVideo;Audio;\n"
        "StartupNotify=true\n",
        encoding="utf-8",
    )
    xml = mime_pkgs / "mathematicians-groovebox-mcc.xml"
    xml.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<mime-info xmlns="http://www.freedesktop.org/standards/shared-mime-info">\n'
        f'  <mime-type type="{MIME_TYPE}">\n'
        "    <comment>Mathematician's Groovebox Composition</comment>\n"
        '    <glob pattern="*.MCC"/>\n'
        '    <glob pattern="*.mcc"/>\n'
        "  </mime-type>\n"
        "</mime-info>\n",
        encoding="utf-8",
    )
    umd = shutil.which("update-mime-database")
    if umd:
        subprocess.run([umd, str(home / ".local/share/mime")], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    xdg = shutil.which("xdg-mime")
    if xdg:
        subprocess.run([xdg, "default", DESKTOP_ID, MIME_TYPE], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return True, "Linux .MCC MIME/default association registered for current user"


def _register_macos(app_script=None):
    # Built .app bundles receive CFBundleDocumentTypes in BUILD_KIT/build.py.
    exe = Path(sys.executable).resolve()
    app = next((p for p in [exe, *exe.parents] if p.suffix == ".app"), None)
    if app:
        lsregister = Path("/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister")
        if lsregister.exists():
            subprocess.run([str(lsregister), "-f", str(app)], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True, "macOS .MCC LaunchServices association refreshed"
    return False, "macOS source mode cannot own a file type; build the .app bundle first"
