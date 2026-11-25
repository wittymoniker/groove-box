"""Shared non-live Content Library services for Mathematician's Groovebox.

The library is an index over existing project/user roots, not a second copy of
content. Performance remains the live-playback surface; this module owns browse,
prepare, organize, edit and launch metadata for non-live resources.
"""
from __future__ import annotations
import os
from pathlib import Path

CATEGORIES = {
    "Projects": {".mcc", ".mgpr", ".gbproj"},
    "Scripts": {".py", ".pyw", ".sh", ".bash", ".zsh", ".lua", ".jl", ".js", ".bat", ".cmd", ".ps1"},
    "Applications": {".desktop", ".app", ".exe", ".appimage", ".deb", ".rpm", ".flatpakref"},
    "Instruments and presets": {".preset", ".fxp", ".fxb", ".sfz", ".synth", ".gbinst", ".sf2", ".sf3", ".gig", ".nki"},
    "Samples and audio": {".wav", ".wave", ".aif", ".aiff", ".flac", ".mp3", ".ogg", ".opus", ".m4a", ".aac", ".wma"},
    "Patterns and sequences": {".pattern", ".seq", ".mid", ".midi", ".gbseq", ".musicxml"},
    "Images and graphics": {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg", ".tif", ".tiff", ".xcf", ".ora", ".psd"},
    "Video": {".mp4", ".mkv", ".mov", ".webm", ".avi", ".m4v", ".mpeg", ".mpg"},
    "Plugins and extensions": {".vst", ".vst3", ".lv2", ".clap", ".component"},
    "Documents and configuration": {".txt", ".md", ".pdf", ".rtf", ".doc", ".docx", ".odt", ".json", ".toml", ".yaml", ".yml", ".ini", ".cfg", ".conf", ".xml", ".csv", ".tsv"},
    "Archives": {".zip", ".tar", ".gz", ".tgz", ".bz2", ".xz", ".7z"},
}
PLUGIN_BUNDLE_SUFFIXES = {".vst3", ".lv2", ".component"}



def roots():
    """Return existing shared roots; no content is duplicated or moved."""
    from groovebox_paths import base_dir, projects_dir
    base = Path(base_dir())
    candidates = [("Projects", Path(projects_dir())), ("User content", base)]
    out, seen = [], set()
    for label, path in candidates:
        try:
            resolved = path.expanduser().resolve()
            if resolved.is_dir() and resolved not in seen:
                out.append((label, resolved)); seen.add(resolved)
        except OSError:
            continue
    return out


def classify(path):
    suffix = Path(path).suffix.lower()
    for category, extensions in CATEGORIES.items():
        if suffix in extensions:
            return category
    return "Imported files"


def scan(query="", category="All", *, limit=2000):
    """Index shared content roots, including native plugin bundle directories."""
    needle = str(query or "").casefold().strip()
    wanted = str(category or "All")
    blocked = {".git", ".venv", "venv", "__pycache__", "node_modules", "cache", "build", "dist"}
    rows = []
    seen_paths = set()

    def add(path, root_label, cat):
        try:
            if path.is_symlink():
                return
            resolved = str(path.resolve())
            if resolved in seen_paths:
                return
            if needle and needle not in path.name.casefold() and needle not in str(path).casefold():
                return
            st = path.stat()
            seen_paths.add(resolved)
            rows.append({"name": path.name, "path": str(path), "category": cat,
                         "root": root_label, "size": st.st_size,
                         "modified": st.st_mtime, "suffix": path.suffix.lower(),
                         "is_directory": path.is_dir()})
        except OSError:
            return

    for root_label, root in roots():
        for current, dirs, files in os.walk(root, followlinks=False):
            current_path = Path(current)
            plugin_dirs = []
            for dirname in list(dirs):
                candidate = current_path / dirname
                if candidate.is_symlink():
                    continue
                if candidate.suffix.lower() in PLUGIN_BUNDLE_SUFFIXES:
                    plugin_dirs.append(dirname)
                    if wanted in ("All", "Plugins and extensions"):
                        add(candidate, root_label, "Plugins and extensions")
            dirs[:] = sorted(d for d in dirs if d.casefold() not in blocked
                             and not d.startswith(".") and d not in plugin_dirs
                             and not (current_path / d).is_symlink())
            for name in sorted(files):
                path = current_path / name
                try:
                    if path.is_symlink() or not path.is_file():
                        continue
                    cat = classify(path)
                    if wanted not in ("All", cat):
                        continue
                    add(path, root_label, cat)
                    if len(rows) >= max(1, int(limit)):
                        return rows
                except OSError:
                    continue
            if len(rows) >= max(1, int(limit)):
                return rows
    return rows

