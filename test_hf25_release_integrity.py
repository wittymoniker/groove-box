from pathlib import Path
import ast
import numpy as np
from spatial_synth_engines import generate_geometric_carrier_audio

ROOT = Path(__file__).resolve().parent
SOURCE = (ROOT / "groovebox.py").read_text(encoding="utf-8")


def test_each_chord_slot_has_independent_pitch_and_performance_sliders():
    ast.parse(SOURCE)
    required = (
        '("interval", "Semitones", -96, 96, 0)',
        '("fine_cents", "Fine cents", -100, 100, 0)',
        '("velocity", "Velocity", 0, 127, 100)',
        '("gate", "Gate %", 0, 100, 100)',
        '("probability", "Probability %", 0, 100, 100)',
        '("timbre", "Timbre %", 0, 100, 50)',
        '("attack", "Attack %", 0, 100, 0)',
        '("release", "Release %", 0, 100, 0)',
        'mem["chord_slot_features"]=features',
        '"chord_slot_features": copy.deepcopy(normalize_chord_slot_features(',
        'step_env[s_mask] *= _slot_lanes["gain"][s_mask]',
        'chord_timbre_track[s_mask] = _slot_lanes["timbre"][s_mask]',
    )
    for token in required:
        assert token in SOURCE, token


def test_global_frequency_identity_tracks_its_original_base():
    assert 'params["frequency_identity_base_hz"] = max(1e-9, float(base_before))' in SOURCE
    assert 'params["frequency_identity_ratio"] = float(stable_freq_hz[name]) / max(1e-9, float(base_before))' in SOURCE
    assert 'elif "frequency_identity_base_hz" not in _state:' in SOURCE
    assert 'self.global_base_frequency_hz=base' in SOURCE


def test_cellular_carrier_large_configuration_is_deterministic_and_finite():
    sr = 8000
    t = np.arange(4096, dtype=np.float64) / sr
    mix = {"vector": 0, "wavetable": 0, "ball": 0, "cellular": 1, "cross_mod": 0, "ensemble_mod_amt": 0}
    ca = {"width": 64, "height": 64, "cell_types": 3, "generations": 256,
          "rule": 30, "neighborhood": "moore", "manual_cells": [[2, 5], [10, 11]]}
    args = dict(sample_rate=sr, total_duration=t[-1] + 1/sr, mix_state=mix, cellular_state=ca)
    a = generate_geometric_carrier_audio(t, 432, **args)
    b = generate_geometric_carrier_audio(t, 432, **args)
    assert np.array_equal(a, b)
    assert np.isfinite(a).all()
    assert np.max(np.abs(a)) <= 0.5


def test_canonical_engine_lanes_and_extended_iso_download_timeouts_remain_enabled():
    assert "def _canonical_engine_lane(self, engine: str):" in SOURCE
    assert (ROOT / "BUILD_ISO" / "app-overlay-v35.22zz" / "groovebox.py").read_text(encoding="utf-8") == SOURCE
    assert (ROOT / "BUILD_ISO" / "app-overlay-v35.22zz" / "spatial_synth_engines.py").read_text(encoding="utf-8") == (ROOT / "spatial_synth_engines.py").read_text(encoding="utf-8")
    assert (ROOT / "BUILD_ISO" / "app-overlay-v35.22zz" / "performance.py").read_text(encoding="utf-8") == (ROOT / "performance.py").read_text(encoding="utf-8")
    assert "thread_name_prefix=f'canon-{key[:8]}'" in SOURCE
    bi = ROOT / "BUILD_ISO"
    assert "timeout=180, attempts=8" in (bi / "prepare_debian_copy_tools_v32t.py").read_text()
    assert "timeout=180, attempts=8" in (bi / "prepare_debian_busybox_v34n.py").read_text()
    legacy = (bi / "prepare_debian_copy_tools_v32q.py").read_text()
    assert "urlopen(req,timeout=180)" in legacy and "urlopen(req,timeout=360)" in legacy
    assert "range(10)" in legacy
    assert "urlopen(req, timeout=360)" in (bi / "prepare_debian_kernel_v35_22i.sh").read_text()
    assert "urlopen(req, timeout=360)" in (bi / "prepare_debian_kernel_modules_v32n.sh").read_text()
