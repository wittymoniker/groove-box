"""Regression contract for the 2026-09-09 final realtime/idle lag pass.

Static by design: it can run on build machines without PyQt6/audio hardware.
"""
from pathlib import Path

SRC = Path(__file__).with_name("groovebox.py").read_text(encoding="utf-8", errors="ignore")


def _body(name, next_name=None):
    start = SRC.index(f"    def {name}")
    end = SRC.index(f"    def {next_name}", start) if next_name else min(len(SRC), start + 12000)
    return SRC[start:end]


def test_component_registry_restored():
    assert "COMPONENT_CLASS_REGISTRY = _build_component_class_registry()" in SRC


def test_main_math_background_does_not_start_in_constructor():
    cls = SRC[SRC.index("class ParametricMathBackground"):SRC.index("class ParametricMathBackground") + 4200]
    init = cls[cls.index("def __init__"):cls.index("def showEvent")]
    assert "self._timer.start()" not in init
    show = cls[cls.index("def showEvent"):cls.index("def hideEvent")]
    assert "self._timer.start()" in show


def test_domain_editor_does_not_construct_throwaway_background():
    body = _body("open_domain_equation_editor", "_open_calc_domain") if "    def _open_calc_domain" in SRC else _body("open_domain_equation_editor")
    assert "bg = ParametricMathBackground(self, cw)" not in body
    assert "_ensure_single_math_background(self, cw)" in body


def test_portaudio_callback_has_no_qt_clip_widget_read():
    body = _body("_audio_callback")
    assert "spin_clip_ratio.value()" not in body
    assert "_rt_clip_ratio_pct" in body


def test_live_dj_callback_has_no_seed_parse_or_bpm_widget_read():
    body = _body("_apply_live_dj_chunk", "_live_canonical_offset_and_effects")
    assert "get_numeric_seed()" not in body
    assert "spin_bpm.value()" not in body
    assert "_rt_numeric_seed" in body
    assert "_rt_bpm" in body


def test_goava_scalar_is_realtime_safe_and_uses_precomputed_media_energy():
    body = _body("_live_dj_goava_scalar", "_bake_dj_write")
    assert "spin_bpm.value()" not in body
    assert "_dj_row_samples(" not in body
    assert "_media_carrier_energy(" not in body
    assert "get_numeric_seed" not in body
    assert "_rt_dj_row_samples" in body
    assert "_rt_media_energy_rows" in body


def test_live_canonical_modulation_is_control_rate_not_every_scope_tick():
    body = _body("_update_scope_from_playhead")
    assert "_live_canonical_control_tick" in body
    assert "_canon_stride = 3 if _low_power_mode() else 2" in body
    assert "self._live_canonical_control_tick % _canon_stride == 0" in body
