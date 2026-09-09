import pathlib, inspect
from graph_context import build_graph_context, coerce_graph_output, GRAPH_VARIABLES, GRAPH_CONTEXT_VERSION
import dj_effects
import videogame_engine
import canonical_cross_media
import numpy as np

def test_graph_context_has_shared_variables():
    c=build_graph_context(t=.25,t_norm=.25,x=.3,y=.4,z=.5,seed=17)
    for k in GRAPH_VARIABLES:
        assert k in c
    assert c['graph_context_version']==GRAPH_CONTEXT_VERSION
    assert abs(c['graph_radius']-(.3**2+.4**2+.5**2)**.5)<1e-12

def test_named_and_vector_outputs_are_backward_compatible():
    assert coerce_graph_output(2.0)['scalar']==2.0
    assert coerce_graph_output([3,4])['vector']==[3.0,4.0]
    assert coerce_graph_output({'value':5,'amp':.7})['named']['amp']==.7

def test_rand_param_is_repeatable_and_graph_driven():
    e=dj_effects.LiveDJEffects(48000); e.set_context(seed=1.1975807343,pair=(2,9)); e.amount_random=.8
    x=np.linspace(-.2,.2,512,dtype=np.float32)
    a=e.random_parametric(x,start_sample=2048,bpm=123)
    b=e.random_parametric(x,start_sample=2048,bpm=123)
    assert np.array_equal(a,b)
    assert not np.array_equal(a,x)

def test_game_identity_accepts_graph_fingerprint():
    sig=inspect.signature(videogame_engine.classify_from_composition)
    assert 'graph_context_fingerprint' in sig.parameters
    a=videogame_engine.classify_from_composition(4.0,graph_context_fingerprint='aaaaaaaaaaaaaaaa')
    b=videogame_engine.classify_from_composition(4.0,graph_context_fingerprint='bbbbbbbbbbbbbbbb')
    assert a.composition_fingerprint != b.composition_fingerprint

def test_cross_media_contract_is_v14_graph_aware():
    assert canonical_cross_media.VERSION=='cross_media_v14_full_graph'
    src=pathlib.Path('canonical_cross_media.py').read_text()
    assert 'instrument_scripts' in src and 'graph_context' in src

def test_source_writers_and_help_are_graph_aware():
    src=pathlib.Path('groovebox.py').read_text()
    for token in ['FULL-GRAPH SCRIPT CONTEXT','Full-graph Global script algo','heuristic:{family}:{bias} · full-graph','graph_script_fingerprint','snap["graph_context"]']:
        assert token in src
    assert 'graph_radius' in pathlib.Path('HELP_TEXT.md').read_text()
    assert 'graph_radius' in pathlib.Path('README.md').read_text()

def test_appliance_mirror_contains_patch():
    root=pathlib.Path('APPLIANCE_ISO/source/rootfs/opt/groovebox')
    for name in ['graph_context.py','groovebox.py','dj_effects.py','videogame_engine.py','canonical_cross_media.py','HELP_TEXT.md','README.md']:
        assert (root/name).exists()
    assert 'FULL_GRAPH_RAND_PARAM_20260909' in (root/'dj_effects.py').read_text()
