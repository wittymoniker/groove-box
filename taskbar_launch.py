"""GROOVEBOX_R123_TASKBAR_LAUNCH_REGISTRY_20261119 — one source of truth for Task Bar launches.

Every "＋ New window" entry, the "▦ Apps" button, and ``main.open_extra_window(kind)`` resolve
through ``ENTRIES``. Each entry is checked against the *installed* module and callable
(importlib.util.find_spec + attribute check on first use), so the bar can

  * disable an entry whose module is missing and say why (tooltip / status line), and
  * report a useful error when a launch raises or returns nothing, instead of the old
    silent ``print(...)`` / ``return None``.

kind            label                        module                  callable
-----------------------------------------------------------------------------------------
performance     🎛 Performance                (main: builtin)
player          ▶ Media Player               (main: builtin)
live_player     🎧 Live Player                (main: builtin)
video_synth     🎬 Video Synth                (main: _r32_open_clip_editor)
multidim        🎹 Multidim Synth             multidim_ui             open_multidim_window
studio_3d       🧱 3D / Scenograph            studio_3d               open_window
game_studio     🕹 Game Editor / Playability  game_editor             open_window
composition_lab 🎼 Composition Lab            composition_workbench   open_window
seed_atlas      🧬 Seed Atlas                 seed_atlas              open_window
script_studio   🧪 Seed / Script Studio       script_studio           open_window
plugins         🔌 Plugin Library / Apps      plugin_library          open_window
lua             🌙 Lua Workspace              lua_workspace           open_window
programs        🛠 Program Builder            program_builder         open_window
files           📂 File Studio                file_studio             open_window
experiences     🗺 Experiences                experiences             open_window
science         📈 Project / Science Tools    project_tools           open_window
console         ⌨ Command Console            command_console         open_window
monitor         🩺 Monitor Center             monitor_center          open_monitor_center
performance_suite ⏱ Performance Suite         performance_suite       open_window
"""
from __future__ import annotations

import importlib
import importlib.util
from dataclasses import dataclass
from typing import Callable, Dict, Optional, Tuple

BUILTIN = "__main__"


@dataclass(frozen=True)
class Entry:
    kind: str
    label: str
    module: str          # BUILTIN → method on the main window
    attr: str
    tip: str = ""


ENTRIES: Tuple[Entry, ...] = (
    Entry("performance", "🎛 Performance", BUILTIN, "open_extra_window", "Another Performance window (multi-instance)"),
    Entry("player", "▶ Media Player", BUILTIN, "open_extra_window", "Another media player — scan media side by side"),
    Entry("live_player", "🎧 Live Player", BUILTIN, "open_extra_window", "Live Player: rigs, takes, broadcast"),
    Entry("video_synth", "🎬 Video Synth", BUILTIN, "_r32_open_clip_editor", "Clip / timeline video synth"),
    Entry("multidim", "🎹 Multidim Synth", "multidim_ui", "open_multidim_window", "Multidimensional synth"),
    Entry("studio_3d", "🧱 3D / Scenograph", "studio_3d", "open_window", "OBJ scenes, stereo video, scene → game level"),
    Entry("game_studio", "🕹 Game Editor / Playability", "game_editor", "open_window", "Game identity overrides, live macros, playability"),
    Entry("composition_lab", "🎼 Composition Lab", "composition_workbench", "open_window", "Seed → canonical composition workbench"),
    Entry("seed_atlas", "🧬 Seed Atlas", "seed_atlas", "open_window", "Browse the seed space; send to apps"),
    Entry("script_studio", "🧪 Seed / Script Studio", "script_studio", "open_window", "Seed scripts and sCode"),
    Entry("plugins", "🔌 Plugin Library / Apps", "plugin_library", "open_window", "Shipped Lua / hybrid plugins and installed apps"),
    Entry("lua", "🌙 Lua Workspace", "lua_workspace", "open_window", "LuaJIT workspace"),
    Entry("programs", "🛠 Program Builder", "program_builder", "open_window", "Compile and run C/C++/Rust/Go/Julia/Lua/Python"),
    Entry("files", "📂 File Studio", "file_studio", "open_window", "Files, drives, imports"),
    Entry("experiences", "🗺 Experiences", "experiences", "open_window", "Guided experiences"),
    Entry("science", "📈 Project / Science Tools", "project_tools", "open_window", "Project analysis and science tools"),
    Entry("console", "⌨ Command Console", "command_console", "open_window", "doctor · threads · abi · toolchains · env"),
    Entry("monitor", "🩺 Monitor Center", "monitor_center", "open_monitor_center", "CPU/RAM/workers/exports/system health"),
    Entry("performance_suite", "⏱ Performance Suite", "performance_suite", "open_window", "Benchmarks for DSP, render, export and UI paths (R119)"),
)

# Old / alternate kinds still used by other modules.
ALIASES: Dict[str, str] = {"game": "game_studio", "apps": "plugins", "monitor_center": "monitor"}

_BY_KIND: Dict[str, Entry] = {e.kind: e for e in ENTRIES}
_STATUS: Dict[str, Tuple[bool, str]] = {}


class LaunchError(RuntimeError):
    """A launch failed with a user-readable reason."""


def canonical(kind: str) -> str:
    return ALIASES.get(kind, kind)


def entry(kind: str) -> Optional[Entry]:
    return _BY_KIND.get(canonical(kind))


def check(kind: str, main=None, *, refresh: bool = False) -> Tuple[bool, str]:
    """(available, reason). Cheap: find_spec does not import the module."""
    kind = canonical(kind)
    if not refresh and kind in _STATUS and main is None:
        return _STATUS[kind]
    e = _BY_KIND.get(kind)
    if e is None:
        res = (False, f"unknown window type {kind!r}")
    elif e.module == BUILTIN:
        if main is None:
            res = (True, "built in")
        else:
            res = (callable(getattr(main, e.attr, None)), "built in" if callable(getattr(main, e.attr, None))
                   else f"main window has no {e.attr}()")
    else:
        try:
            spec = importlib.util.find_spec(e.module)
        except Exception as exc:  # broken package metadata
            spec = None
            why = f"{type(exc).__name__}: {exc}"
        else:
            why = f"module {e.module}.py is not installed"
        res = (True, f"{e.module}.{e.attr}") if spec is not None else (False, why)
    if main is None:
        _STATUS[kind] = res
    return res


def audit(main=None) -> Dict[str, Tuple[bool, str]]:
    """Check every entry; additionally imports each module to confirm the callable exists."""
    out = {}
    for e in ENTRIES:
        ok, why = check(e.kind, main, refresh=True)
        if ok and e.module != BUILTIN:
            try:
                mod = importlib.import_module(e.module)
                if not callable(getattr(mod, e.attr, None)):
                    ok, why = False, f"{e.module}.py has no {e.attr}()"
            except Exception as exc:
                ok, why = False, f"import {e.module} failed: {type(exc).__name__}: {exc}"
        out[e.kind] = (ok, why)
        _STATUS[e.kind] = (ok, why)
    return out


def resolve(kind: str) -> Callable:
    """Return the module-level launcher for a non-builtin kind, or raise LaunchError."""
    e = entry(kind)
    if e is None:
        raise LaunchError(f"Unknown window type “{kind}”.")
    if e.module == BUILTIN:
        raise LaunchError(f"{e.label} is a built-in window (use the main window).")
    ok, why = check(e.kind)
    if not ok:
        raise LaunchError(f"{e.label} is unavailable: {why}.")
    try:
        mod = importlib.import_module(e.module)
    except Exception as exc:
        raise LaunchError(f"{e.label} could not load ({e.module}): {type(exc).__name__}: {exc}") from exc
    fn = getattr(mod, e.attr, None)
    if not callable(fn):
        raise LaunchError(f"{e.label}: {e.module}.py has no {e.attr}() entry point.")
    return fn


def launch_module(kind: str, main):
    """Open a module-backed window. Returns the window or raises LaunchError."""
    e = entry(kind)
    fn = resolve(kind)
    try:
        result = fn(main)
    except LaunchError:
        raise
    except Exception as exc:
        raise LaunchError(f"{e.label} failed while opening: {type(exc).__name__}: {exc}") from exc
    if result is None:
        raise LaunchError(f"{e.label} did not open a window ({e.module}.{e.attr} returned nothing).")
    if hasattr(result, "show"):
        try:
            result.show(); result.raise_(); result.activateWindow()
        except Exception:
            pass
    return result
