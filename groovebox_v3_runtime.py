"""
Groovebox V3 full runtime.
Fractal package, seeded video rules, integrity gates, concurrency pools.
Imported by run_groovebox.py before the main window.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
_FRACTAL = _ROOT / "groovebox_fractal"
if _FRACTAL.is_dir() and str(_FRACTAL) not in sys.path:
    sys.path.insert(0, str(_FRACTAL.parent) if (_FRACTAL / "__init__.py").exists() else str(_FRACTAL))

# Threading plan: keep UI, project, and encode pools separate.
try:
    from groovebox_fractal.concurrency import (
        UI_POOL, PROJECT_POOL, ENCODE_POOL, offload_to_ui, RECORDING_GUIDELINES,
    )
except Exception:
    UI_POOL = PROJECT_POOL = ENCODE_POOL = None
    offload_to_ui = None
    RECORDING_GUIDELINES = ""

os.environ.setdefault("GROOVEBOX_V3_FULL", "1")
os.environ.setdefault("GROOVEBOX_VIDEO_INTEGRITY", "1")
os.environ.setdefault("GROOVEBOX_AUDIO_INTEGRITY", "1")
os.environ.setdefault("GROOVEBOX_UI_OFFLOAD", "1")


def load_assembly_rules(seed: int, script_output: dict | None = None):
    """Return VideoAssemblyRules for a seeded video plan. Seed script wins."""
    from groovebox_fractal import VideoAssemblyRules, apply_seed_script_rules
    rules = VideoAssemblyRules(seed=int(seed))
    if script_output:
        rules = apply_seed_script_rules(rules, script_output)
    return rules


def video_integrity_enabled() -> bool:
    return os.environ.get("GROOVEBOX_VIDEO_INTEGRITY", "1") != "0"


def audio_integrity_enabled() -> bool:
    return os.environ.get("GROOVEBOX_AUDIO_INTEGRITY", "1") != "0"


def offload(fn, *args, **kwargs):
    """Run non-UI work off the main thread when the pool is available."""
    if offload_to_ui is not None and os.environ.get("GROOVEBOX_UI_OFFLOAD", "1") != "0":
        return offload_to_ui(fn, *args, **kwargs)
    fn(*args, **kwargs)
    return None


def apply_planner_to_export(window) -> dict:
    """Read Video Planner rules from the window, if any."""
    rules = getattr(window, "_video_assembly_rules", None)
    return dict(rules) if isinstance(rules, dict) else {}
