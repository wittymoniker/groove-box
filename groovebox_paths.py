"""
groovebox_paths.py — single source of truth for Groovebox's on-disk layout.

Designed for the dedicated-Linux-Groovebox target (mini PC / Orange Pi):
everything lives under one root so the whole box's content can sit on an
SD card, USB drive, or NAS mount and be swapped/backed-up as one folder.

Root resolution order:
  1. $GROOVEBOX_HOME environment variable, if set
  2. ~/groovebox   (default — matches the dedicated-box convention)

Layout under the root:
  projects/   .mgpr project files                 (was ~/.groovebox/projects)
  renders/    audio/video exports & re-renders     (was ./renders next to CWD)
  games/      packaged (.zip) and unpacked games
  samples/    imported audio/video/game samples — the default read library

Every _dir() function here creates the folder on first call and is safe to
call repeatedly. Falls back to a folder next to the running script if the
home directory isn't writable (e.g. read-only rootfs on some Pi images).
"""

import os
import sys


def _fallback_root() -> str:
    try:
        base = os.path.dirname(os.path.abspath(sys.argv[0] or "groovebox.py"))
    except Exception:
        base = os.getcwd()
    return os.path.join(base, "groovebox_data")


def groovebox_root() -> str:
    root = os.environ.get("GROOVEBOX_HOME")
    if not root:
        root = os.path.join(os.path.expanduser("~"), "groovebox")
    try:
        os.makedirs(root, exist_ok=True)
        # Confirm it's actually writable, not just creatable.
        probe = os.path.join(root, ".write_test")
        with open(probe, "w") as f:
            f.write("ok")
        os.remove(probe)
    except Exception:
        root = _fallback_root()
        os.makedirs(root, exist_ok=True)
    return root


def _sub_dir(name: str) -> str:
    path = os.path.join(groovebox_root(), name)
    try:
        os.makedirs(path, exist_ok=True)
    except Exception:
        pass
    return path


def projects_dir() -> str:
    """Projects (.mgpr) load/save root: <root>/projects/"""
    return _sub_dir("projects")


def renders_dir() -> str:
    """Exports & batch re-renders root: <root>/renders/"""
    return _sub_dir("renders")


def games_dir() -> str:
    """Packaged (.zip) and unpacked games root: <root>/games/"""
    return _sub_dir("games")


def samples_dir() -> str:
    """Imported sample/media library root: <root>/samples/"""
    return _sub_dir("samples")


# One-time migration helper: if the *old* default project/render locations
# have content and the new ones are empty, copy it over so upgrading users
# don't appear to lose their library.
def migrate_legacy_layout() -> None:
    import shutil

    legacy_projects = os.path.join(os.path.expanduser("~"), ".groovebox", "projects")
    legacy_renders = os.path.join(os.getcwd(), "renders")

    for legacy, new in ((legacy_projects, projects_dir()), (legacy_renders, renders_dir())):
        try:
            if not os.path.isdir(legacy):
                continue
            if os.path.abspath(legacy) == os.path.abspath(new):
                continue
            if any(os.scandir(new)):
                continue  # new location already has content, don't clobber
            for entry in os.scandir(legacy):
                dest = os.path.join(new, entry.name)
                if entry.is_dir():
                    shutil.copytree(entry.path, dest, dirs_exist_ok=True)
                else:
                    shutil.copy2(entry.path, dest)
            print(f"[groovebox_paths] Migrated legacy content: {legacy} -> {new}")
        except Exception as e:
            print(f"[groovebox_paths] Migration skipped for {legacy}: {e}")
