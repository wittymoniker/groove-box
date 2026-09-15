#!/usr/bin/env python3
"""Cross-platform executable builder for Mathematician's Groovebox.

This file intentionally lives in BUILD_KIT/ and resolves the application root
as its parent, so the kit can stay in a subfolder.
"""
from __future__ import annotations

import argparse
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

KIT = Path(__file__).resolve().parent
ROOT = KIT.parent
# BUILD_KIT/build.py is executed from inside BUILD_KIT, so Python otherwise
# puts BUILD_KIT (not the Groovebox project root) on sys.path.  Add ROOT
# explicitly so local modules such as groovebox_media_tools import reliably.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
ENTRY = ROOT / "run_groovebox.py"
VENV = ROOT / ".groovebox-build-venv"
BUILD = ROOT / "build_executable"
DIST = ROOT / "dist"
APPNAME = "MathematiciansGroovebox"


def run(cmd, *, cwd=ROOT, env=None):
    print("+", " ".join(map(str, cmd)), flush=True)
    subprocess.run([str(x) for x in cmd], cwd=str(cwd), env=env, check=True)


def venv_python() -> Path:
    if os.name == "nt":
        return VENV / "Scripts" / "python.exe"
    return VENV / "bin" / "python"


def ensure_venv() -> Path:
    py = venv_python()
    if not py.exists():
        print(f"Creating build environment: {VENV}")
        run([sys.executable, "-m", "venv", str(VENV)])
    return py


def install_python_deps(py: Path):
    req = ROOT / "requirements.txt"
    run([py, "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"])
    if req.exists():
        run([py, "-m", "pip", "install", "-r", req])
    run([py, "-m", "pip", "install", "pyinstaller>=6.10,<7"])


def valid_local_modules():
    mods = []
    skip_prefix = ("test_", "tests", "benchmark_")
    for p in sorted(ROOT.glob("*.py")):
        stem = p.stem
        if p.name == ENTRY.name or stem.startswith(skip_prefix):
            continue
        if re.fullmatch(r"[A-Za-z_]\w*", stem):
            mods.append(stem)
    return mods




def enforce_runtime_import_policy():
    """Fail standalone builds if active runtime code reintroduces banned direct deps."""
    import ast
    violations = []
    skip = {"groovebox_reference.py", "groovebox_seqfix.py"}
    for path in ROOT.glob("*.py"):
        if path.name.startswith(("test_", "tests", "benchmark_")) or ".pre_" in path.name or path.name in skip:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
        except Exception:
            continue
        for node in ast.walk(tree):
            mod = None
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            for name in names:
                if name == "scipy" or name.startswith("scipy."):
                    violations.append(f"{path.name}:{getattr(node, 'lineno', '?')} direct SciPy import")
                if (name == "sounddevice" or name.startswith("sounddevice.")) and path.name != "audio_os_backend.py":
                    violations.append(f"{path.name}:{getattr(node, 'lineno', '?')} direct sounddevice import; use audio_os_backend")
    if violations:
        raise SystemExit("Standalone import policy failed:\n  " + "\n  ".join(violations))

def compile_native():
    system = platform.system().lower()
    native = ROOT / "native"
    native.mkdir(exist_ok=True)
    src = ROOT / "cpp" / "groovebox_accel.cpp"
    if not src.exists():
        return
    try:
        if system == "linux":
            compiler = shutil.which("g++") or shutil.which("c++")
            if not compiler:
                print("WARNING: no C++ compiler found; executable will use Python fallback.")
                return
            run([compiler, "-std=c++17", "-O3", "-DNDEBUG", "-fPIC", "-fvisibility=hidden",
                 "-shared", str(src), "-o", str(native / "libgroovebox_accel.so")])
        elif system == "darwin":
            compiler = shutil.which("c++") or shutil.which("clang++")
            if not compiler:
                print("WARNING: no C++ compiler found; executable will use Python fallback.")
                return
            run([compiler, "-std=c++17", "-O3", "-DNDEBUG", "-fPIC", "-fvisibility=hidden",
                 "-dynamiclib", str(src), "-o", str(native / "libgroovebox_accel.dylib")])
        elif system == "windows":
            cl = shutil.which("cl")
            gxx = shutil.which("g++")
            if cl:
                run([cl, "/nologo", "/std:c++17", "/O2", "/DNDEBUG", "/LD", str(src),
                     f"/Fe:{native / 'groovebox_accel.dll'}"])
            elif gxx:
                run([gxx, "-std=c++17", "-O3", "-DNDEBUG", "-shared", str(src),
                     "-o", str(native / "groovebox_accel.dll")])
            else:
                print("WARNING: MSVC/MinGW C++ compiler not found; executable will use Python fallback.")
    except subprocess.CalledProcessError:
        print("WARNING: native accelerator build failed; continuing with Python fallback.")



def patch_macos_bundle_filetype():
    """Declare .MCC as a document type in a PyInstaller macOS .app bundle."""
    if platform.system().lower() != "darwin":
        return
    import plistlib
    app = DIST / f"{APPNAME}.app"
    plist = app / "Contents" / "Info.plist"
    if not plist.exists():
        return
    with plist.open("rb") as f:
        info = plistlib.load(f)
    info["CFBundleDocumentTypes"] = [{
        "CFBundleTypeName": "Mathematician's Groovebox Composition",
        "CFBundleTypeRole": "Editor",
        "LSHandlerRank": "Owner",
        "LSItemContentTypes": ["com.mathematiciansgroovebox.mcc"],
        "CFBundleTypeExtensions": ["MCC", "mcc"],
    }]
    info["UTExportedTypeDeclarations"] = [{
        "UTTypeIdentifier": "com.mathematiciansgroovebox.mcc",
        "UTTypeDescription": "Mathematician's Groovebox Composition",
        "UTTypeConformsTo": ["public.data", "public.json"],
        "UTTypeTagSpecification": {
            "public.filename-extension": ["MCC", "mcc"],
            "public.mime-type": "application/x-mathematicians-groovebox-mcc",
        },
    }]
    with plist.open("wb") as f:
        plistlib.dump(info, f)
    print(f"Registered .MCC document declaration in {plist}")

def add_arg(cmd, kind: str, source: Path, dest: str):
    # PyInstaller's add-data/add-binary syntax is platform dependent.
    sep = ";" if os.name == "nt" else ":"
    cmd.extend([kind, f"{source}{sep}{dest}"])


def ensure_local_ffmpeg():
    """Build input is invalid until the exact local codec pair exists."""
    sys.path.insert(0, str(ROOT))
    try:
        from groovebox_media_tools import require_local_pair
        return require_local_pair()
    except Exception:
        provision = ROOT / "scripts" / "provision_first_launch.py"
        run([sys.executable, str(provision)])
        from groovebox_media_tools import require_local_pair
        return require_local_pair()


def build(onefile=False, console=False, clean=True, install=True, native=True):
    if not ENTRY.exists():
        raise SystemExit(f"Cannot find {ENTRY}")
    ensure_local_ffmpeg()
    py = ensure_venv()
    if install:
        install_python_deps(py)
    enforce_runtime_import_policy()
    if native:
        compile_native()

    cmd = [py, "-m", "PyInstaller", str(ENTRY),
           "--name", APPNAME,
           "--noconfirm",
           "--distpath", str(DIST),
           "--workpath", str(BUILD / "work"),
           "--specpath", str(BUILD / "spec"),
           "--paths", str(ROOT)]
    if clean:
        cmd.append("--clean")
    cmd.append("--onefile" if onefile else "--onedir")
    cmd.append("--console" if console else "--windowed")

    # Local modules include dynamically loaded/optional Groovebox components.
    for mod in valid_local_modules():
        cmd.extend(["--hidden-import", mod])

    # These packages have platform/native hooks, but explicit collection makes
    # the build resilient to optional submodule imports inside Groovebox.
    for pkg in ("PyQt6", "numpy", "sounddevice", "PIL"):
        cmd.extend(["--collect-submodules", pkg])

    # Runtime resources that are intentionally external to Python imports.
    # Keep the known-good build.py path, but include every current data tree the
    # shipping application resolves by filesystem path.
    for dirname in ("native", "julia", "assets", "sCode", "scode", "scode_models", "scode_os", "modules"):
        p = ROOT / dirname
        if p.exists():
            add_arg(cmd, "--add-data", p, dirname)
    for filename in ("README.md", "HELP_TEXT.md", "PERFORMANCE_BOX.md", "CURRENT_FEATURES_AND_MATH.md", "DEPENDENCIES.md"):
        p = ROOT / filename
        if p.exists():
            add_arg(cmd, "--add-data", p, ".")

    # Use the project's actual Groovebox logo for executable/bundle metadata.
    icon = ROOT / "assets" / "logo.png"
    if icon.exists():
        cmd.extend(["--icon", str(icon)])

    # FFmpeg/ffprobe are mandatory build inputs and are bundled from local bin only.
    local_bin = ROOT / "bin"
    for base in ("ffmpeg", "ffprobe"):
        candidates = [local_bin / base, local_bin / f"{base}.exe"]
        p = next((q for q in candidates if q.is_file()), None)
        if p is None:
            raise SystemExit(f"Required local codec missing: {base}. Run scripts/provision_first_launch.py")
        add_arg(cmd, "--add-binary", p, "bin")

    run(cmd)
    patch_macos_bundle_filetype()
    exe = DIST / (f"{APPNAME}.exe" if onefile and os.name == "nt" else APPNAME)
    print("\nBUILD COMPLETE")
    print(f"Output: {exe if onefile else DIST / APPNAME}")
    if platform.system().lower() == "linux":
        print(f"Run:    {DIST / APPNAME / APPNAME if not onefile else DIST / APPNAME}")


def doctor():
    print("Mathematician's Groovebox build doctor")
    print("ROOT:", ROOT)
    print("Python:", sys.executable, sys.version.replace("\n", " "))
    print("OS:", platform.platform())
    print("Entry:", ENTRY, "OK" if ENTRY.exists() else "MISSING")
    from groovebox_media_tools import resolve_local_tool, validate_local_tool
    for tool in ("ffmpeg", "ffprobe"):
        print(f"local {tool:10s}", resolve_local_tool(tool, False) or "not found", "OK" if validate_local_tool(tool) else "INVALID")
    for tool in ("g++", "c++", "clang++", "cl"):
        print(f"{tool:10s}", shutil.which(tool) or "not found")
    for lib in ("native/libgroovebox_accel.so", "native/libgroovebox_accel.dylib", "native/groovebox_accel.dll"):
        p = ROOT / lib
        if p.exists():
            print("native:", p)
    scode = ROOT / "sCode" / "bootstrap" / "linux-x86_64" / "scode0"
    opt = ROOT / "sCode" / "apps" / "groovebox" / "groovebox_optimizer.sC"
    print("sCode:", scode, "OK" if scode.exists() else "MISSING")
    print("sCode optimizer:", opt, "OK" if opt.exists() else "MISSING")
    if platform.system().lower() == "linux" and platform.machine().lower() in {"x86_64", "amd64"}:
        if not scode.exists() or not opt.exists():
            raise SystemExit("Required bundled sCode runtime/optimizer is missing")
        env = os.environ.copy()
        env.update({"GB_OPT_ID":"1","GB_OPT_DIRTY":"255","GB_OPT_FRAME":"0","GB_OPT_LANES":"4","GB_OPT_POOL":"64","GB_OPT_SHAPE":"1"})
        probe = subprocess.run([str(scode), "run", str(opt.relative_to(ROOT / "sCode"))], cwd=str(ROOT / "sCode"), env=env, capture_output=True, text=True)
        if probe.returncode != 0 or "scode_optimizer_abi=9" not in probe.stdout:
            raise SystemExit("Required bundled sCode ABI9 preflight failed")
        print("sCode ABI9: OK")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--onefile", action="store_true", help="single executable; slower startup, less debuggable")
    ap.add_argument("--console", action="store_true", help="keep console visible for diagnostics")
    ap.add_argument("--no-install", action="store_true", help="do not pip-install/refresh build dependencies")
    ap.add_argument("--no-native", action="store_true", help="skip C++ accelerator compilation")
    ap.add_argument("--no-clean", action="store_true")
    ap.add_argument("--doctor", action="store_true")
    args = ap.parse_args()
    if args.doctor:
        doctor()
        return 0
    build(args.onefile, args.console, not args.no_clean, not args.no_install, not args.no_native)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
