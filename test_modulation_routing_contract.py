"""Contract checks for reversible Meum exchange and per-route mixing semantics."""
from pathlib import Path
import ast
from modulation_math import MEUM, normalize_signed_amounts

ROOT = Path(__file__).resolve().parent
GROOVEBOX = (ROOT / "groovebox.py").read_text()
UI = (ROOT / "multidim_ui.py").read_text()
MD = (ROOT / "multidim_synth.py").read_text()


def test_master_io_has_three_inputs_and_three_outputs_and_signed_picker():
    tree = ast.parse(GROOVEBOX)
    node = next(n for n in ast.walk(tree) if isinstance(n, ast.ClassDef) and n.name == "GrooveboxApp")
    store = next(n for n in node.body if isinstance(n, ast.FunctionDef) and n.name == "_md_io_store")
    src = ast.get_source_segment(GROOVEBOX, store)
    assert 'range(3)' in src and '"inputs"' in src and '"outputs"' in src
    assert 'amt.setRange(-1.0, 1.0)' in UI
    assert '"master_volume", 0.72' in GROOVEBOX


def test_signed_six_route_budget_is_l1_and_master_volume_half():
    vals = normalize_signed_amounts([1, -2, 1, -1, 0, 1], 0.36)
    assert abs(sum(abs(v) for v in vals) - 0.36) < 1e-12
    assert vals[0] > 0 and vals[1] < 0 and vals[3] < 0
    assert 'budget = 0.5 * float(np.clip(float(getattr(self, "master_volume", 0.72))' in GROOVEBOX
    assert '_normalize_signed_mod_amounts' in GROOVEBOX


def test_bidirectional_exchange_and_meum_peak_in_triad():
    assert 'g2m, m2g, bi' in MD
    assert 'main2 = main * (1.0 + a * g2m * gn)' in MD
    assert 'geo2 = geo * (1.0 + a * m2g * mn)' in MD
    assert 'md_out = md_out * (_MEUM * pi / pmd)' in MD
    assert MEUM > 1.19 and MEUM < 1.20


def test_heuristic_and_synth_shift_rules_remain_exact():
    assert 'return _stable_heuristic_share(frac, k, MEUM, canonical_active=True)' in GROOVEBOX
    assert 'return _stable_synth_shift_factor(v, mean, MEUM)' in GROOVEBOX
    assert 'amps = [float(np.clip(a * f, 0.0, 4.0)) for a in amps]' in GROOVEBOX
    assert 'probs = [int(np.clip(round(p * f), 1, 100)) for p in probs]' in GROOVEBOX
    # Pitch is deliberately not multiplied by the synth-shift factor.
    assert 'pits = [float(np.clip(max(1e-9, pits[i]) ** w' in GROOVEBOX
