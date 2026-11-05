"""GROOVEBOX_INHARMONIC_GATE_20261102: canonicals + a seed add no off-harmonic partials by default."""
import re
from pathlib import Path

SRC = (Path(__file__).resolve().parent / "groovebox.py").read_text(encoding="utf-8")


def test_inharmonic_amount_defaults_to_zero_everywhere():
    assert '"ensemble_mod_amt": 0.12, "inharmonic": 0.0}' in SRC                     # live state
    assert SRC.count('"ensemble_mod_amt": .12, "inharmonic": 0.0}') == 2             # snapshot + project load


def test_render_gates_entropy_after_the_ledger_and_before_the_partial_counts():
    gate = "entropy = entropy * _inh_amt"
    assert SRC.count(gate) == 1
    i = SRC.index(gate)
    assert "_union_entropy_sum += entropy" in SRC[:i]                      # audit ledger untouched
    assert SRC.index("n_harm = max(1, int(2 + (1.0 - entropy)", i) - i < 200
    assert "_inh_amt = float(np.clip(float(self._geometric_mixer_snapshot().get(\"inharmonic\", 0.0))" in SRC


def test_ui_control_persists_and_randomize_all_stays_bounded():
    assert "slider_geometric_inharmonic" in SRC and "_on_geometric_inharmonic_changed" in SRC
    assert 'mix["cross_mod"] = float(rng.uniform(0.0, 0.008))' in SRC          # was 0.0-0.02 (up to 8x default)
    assert 'mix["inharmonic"] = float(rng.uniform(0.0, 1.0))' in SRC


def test_no_limiter_or_saturation_added():
    seg = SRC.split("GROOVEBOX_INHARMONIC_GATE_20261102: the seeded")[1].split("R12_PLAYLIST_SEQUENCER_THREADS")[0]
    for banned in ("tanh", "limit(", "soft"):
        assert banned not in seg
