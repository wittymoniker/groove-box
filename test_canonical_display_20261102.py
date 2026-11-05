import os, sys
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PyQt6.QtWidgets import QApplication
import groovebox as g
_qa = QApplication.instance() or QApplication([])


def _app_with_overlay():
    app = g.MathematiciansGrooveboxApp()
    name = app.instrument_selector_dropdown.currentText()
    app.canonical_runtime_overlays = {f"{name}:0": {"sequence": {
        "steps": [True, False, True, True], "amplitudes": [0.5, 1.0, 0.8, 0.2], "pitches": [1.0, 1.0, 1.5, 2.0],
        "offsets": [0.0, 0.0, 0.1, 0.0]}}}
    return app, name


def test_canonical_steps_and_sliders_visible_when_user_has_none():
    app, name = _app_with_overlay()
    mem = app._current_sequence_mem(name)
    for k in ("steps", "amplitudes", "pitches", "offsets"):
        pass
    mem["pattern_length"] = 4
    view = app._sequence_display_mem(name, mem)
    assert view["_canonical_display"] and view["steps"][:4] == [True, False, True, True]
    assert abs(view["amplitudes"][2] - 0.8) < 1e-9 and view["pitches"][3] == 2.0


def test_first_edit_adopts_canonical_then_changes_only_that_step():
    app, name = _app_with_overlay()
    mem = app._current_sequence_mem(name)
    mem["pattern_length"] = 4
    assert app._adopt_canonical_for_edit(mem, name)
    mem["steps"][1] = True
    assert mem["steps"][:4] == [True, True, True, True] and abs(mem["amplitudes"][2] - 0.8) < 1e-9


def test_fresh_launch_composes_canonical_sequences():
    """STARTUP_CANONICAL_FORCE_20261102: the default Fractal Seed projection must not be skipped by the work-dedup guard."""
    from PyQt6.QtCore import QCoreApplication
    app = g.MathematiciansGrooveboxApp()
    QCoreApplication.processEvents()
    app._initialize_default_fractal_seed_mode()
    n = sum(1 for b in app.instrument_sequence_banks.values() for m in b.values()
            if isinstance(m, dict) and str(m.get("canonical_owner", "")).startswith("canonical:"))
    assert n > 0


def test_stale_scode_claim_self_heals():
    """SCODE_CLAIM_SELF_HEAL_20261102: a dedup claim must not block composing when no canonical output exists."""
    app = g.MathematiciansGrooveboxApp()
    app._scode_force_canonical = False
    app._ensure_perfect_unison()
    for b in app.instrument_sequence_banks.values():
        for k in [k for k, m in b.items() if isinstance(m, dict) and str(m.get("canonical_owner", "")).startswith("canonical:")]:
            b.pop(k)
    app._ensure_perfect_unison()      # identical inputs -> claim says "already ran", output is gone
    assert any(isinstance(m, dict) and str(m.get("canonical_owner", "")).startswith("canonical:")
               for b in app.instrument_sequence_banks.values() for m in b.values())
