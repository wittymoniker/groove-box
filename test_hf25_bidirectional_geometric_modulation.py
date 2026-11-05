from pathlib import Path
import ast
import numpy as np
from spatial_synth_engines import canonical_geometric_rhythm_plan, generate_geometric_carrier_audio, normalize_chord_slot_features, chord_slot_feature_tracks

ROOT=Path(__file__).resolve().parent
SOURCE=(ROOT/'groovebox.py').read_text(encoding='utf-8')


def test_modulation_plan_is_deterministic_bounded_and_reacts_to_ensemble():
    sr=8000; t=np.arange(2048,dtype=np.float64)/sr
    ref=np.sin(2*np.pi*110*t)
    a=canonical_geometric_rhythm_plan(t,ref,bpm=123,ensemble_mod_amt=.5)
    b=canonical_geometric_rhythm_plan(t,ref,bpm=123,ensemble_mod_amt=.5)
    assert np.array_equal(a['rhythm_gate'],b['rhythm_gate'])
    assert a['external_mod_amt']==.5
    assert 0 <= a['internal_mod_amt'] <= .5
    assert np.all((a['rhythm_gate']>=0)&(a['rhythm_gate']<=1))
    for lane in ('vector','wavetable','ball','cellular'):
        assert np.all((a['lane_schedule'][lane]>=.5)&(a['lane_schedule'][lane]<=1.0))


def test_geometric_carriers_cross_modulate_in_both_directions_and_stay_finite():
    sr=8000; t=np.arange(4096,dtype=np.float64)/sr
    ref=np.sin(2*np.pi*123*t).astype(np.float32)
    mix={'vector':.8,'wavetable':.75,'ball':.65,'cellular':.7,'cross_mod':.0024,'ensemble_mod_amt':.5}
    audio,geo_mod=generate_geometric_carrier_audio(t,432.0,sample_rate=sr,total_duration=t[-1]+1/sr,
      mix_state=mix,ensemble_reference=ref,bpm=120,return_modulation=True)
    dry=generate_geometric_carrier_audio(t,432.0,sample_rate=sr,total_duration=t[-1]+1/sr,
      mix_state={**mix,'ensemble_mod_amt':0.0},ensemble_reference=None,bpm=120)
    assert audio.shape==geo_mod.shape==dry.shape==t.shape
    assert np.isfinite(audio).all() and np.isfinite(geo_mod).all()
    assert np.max(np.abs(geo_mod)) <= 1.0
    assert not np.allclose(audio,dry)
    zero,zero_mod=generate_geometric_carrier_audio(t,0.0,return_modulation=True)
    assert np.count_nonzero(zero)==0 and np.count_nonzero(zero_mod)==0


def test_chord_each_note_feature_lanes_are_independent_and_bounded():
    features=normalize_chord_slot_features([
      {'velocity':25,'gate':50,'probability':100,'timbre':10,'attack':0,'release':0,'fine_cents':-20},
      {'velocity':110,'gate':100,'probability':100,'timbre':90,'attack':15,'release':10,'fine_cents':35}],2)
    mask=np.ones(100,dtype=bool)
    tracks=chord_slot_feature_tracks(mask,features,2,event_seed=7)
    assert tracks['gain'].shape==(100,)
    assert set(np.unique(tracks['slot_ids']))=={0,1}
    assert tracks['fine_cents'][0] == -20 and tracks['fine_cents'][-1] == 35
    assert tracks['timbre'][0] == 10 and tracks['timbre'][-1] == 90
    assert np.max(tracks['gain']) <= 1.27


def test_ui_modulation_control_is_project_persisted_and_used_by_global_audio_bus():
    """R23r: the shared carrier is retired; geometry runs per instrument instance."""
    ast.parse(SOURCE)
    for token in (
      'def _on_geometric_ensemble_mod_changed(self, value):',   # saved values still load
      '"ensemble_mod_amt": .12',
      'GROOVEBOX_R23R_GEOMETRY_PER_INSTRUMENT_20261031',
      '_instance_voice_geometry(op_name, int(_vo), params=',
      'GROOVEBOX_R28_4_50_HF25_PREDICTIVE_BIDIRECTIONAL_GEOMETRIC_MOD_20261028'):
        assert token in SOURCE, token
    assert '_geo,_geo_mod=generate_geometric_carrier_audio(' not in SOURCE


def test_iso_builder_uses_extended_per_download_timeouts_and_retries():
    bi=ROOT/'BUILD_ISO'
    tools=(bi/'prepare_debian_copy_tools_v32t.py').read_text()
    busy=(bi/'prepare_debian_busybox_v34n.py').read_text()
    kernel=(bi/'prepare_debian_kernel_v35_22i.sh').read_text()
    modules=(bi/'prepare_debian_kernel_modules_v32n.sh').read_text()
    assert 'timeout=180, attempts=8' in tools and 'urlopen(req,timeout=360)' in tools
    assert 'timeout=180, attempts=8' in busy and 'urlopen(req,timeout=360)' in busy
    assert 'urlopen(req, timeout=360)' in kernel
    assert 'urlopen(req, timeout=360)' in modules
    assert 'timeout 1800s python3 -u "$HERE/prepare_debian_copy_tools_v32t.py"' in (bi/'build_from_v31c_layered_cache_v32x.sh').read_text()
