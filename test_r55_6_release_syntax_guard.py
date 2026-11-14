"""Regression guard: release entry point must parse and Auto quality update stays nested."""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def test_main_entrypoint_compiles():
    source = (ROOT / "groovebox.py").read_text(encoding="utf-8")
    ast.parse(source, filename="groovebox.py")

def test_auto_quality_refresh_is_inside_auto_selection_guard():
    source = (ROOT / "groovebox.py").read_text(encoding="utf-8")
    marker = 'if getattr(viewer, "_preview_quality_name", "Auto") == "Auto":\n'
    at = source.index(marker, source.index('def _refresh_power_profile'))
    following = source[at:at + 220]
    assert 'viewer.set_quality_profile("Auto")' in following
    assert following.index('viewer.set_quality_profile("Auto")') > following.index(marker)
