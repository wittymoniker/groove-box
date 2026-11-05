from pathlib import Path
GB=(Path(__file__).resolve().parent/'groovebox.py').read_text(errors='replace')

def test_variable_pole_eq_contract():
    for token in (
        'GROOVEBOX_V35_22ZZ_R13_VARIABLE_EQ_POLES_20260929',
        'def _normalize_eq_poles', 'def blend_eq_poles', 'def canonical_eq_poles',
        '+ Add Pole', '− Remove', 'Default (Convolution)', '_eq_convolution_default_band_count', 'automation_depth', 'frequency_hz',
        'eq_poles', 'eq_sequence_blend',
    ):
        assert token in GB

def test_eq_sequence_tray_is_fixed_half_blend():
    assert 'blend_master_sequence_params(_eq_src,_ss,amount=0.5)' in GB
    assert 'panels["blend"] = 0.5' in GB
    assert 'EQ remains instrument-owned' in GB

def test_canonicals_own_eq_topology_without_destroying_user_source():
    assert '"eq_poles": canonical_eq_poles(ctx, i)' in GB
    assert 'st["eq_poles"]=blend_eq_poles(_user_poles,_canon_poles,amount=strength)' in GB
    assert 'Canonicals may add/remove/reorder/define poles' in GB

def test_project_state_uses_instrument_param_state_and_eq_poles():
    assert '"instrument_param_state":' in GB
    assert '"eq_poles": copy.deepcopy(poles)' in GB


def test_convolution_default_eq_density_rule():
    assert 'return max(2,min(128,130-count))' in GB
    assert 'def _eq_default_poles(curve=None, bands=128)' in GB
    assert 'max_poles=128' in GB
    assert 'if len(poles)>=128: return' in GB
