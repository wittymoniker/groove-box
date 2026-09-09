from pathlib import Path
import re

SRC = Path(__file__).with_name('groovebox.py').read_text(encoding='utf-8')

def test_graph_seed_api_present():
    for name in ('graph_seed_identity', 'graph_seed_state', 'evaluate_dynamic_graph_seed'):
        assert re.search(rf'^def {name}\(', SRC, re.M), name

def test_fixed_graph_sampling_independent_of_instruments():
    assert '_GRAPH_SEED_SAMPLES = 33' in SRC
    block = SRC[SRC.index('def graph_seed_identity'):SRC.index('def graph_seed_state')]
    assert 'len(self.instruments)' not in block
    assert 'instrument_count' not in block
    assert 'math.tau' in block

def test_coordinate_evaluator_uses_dynamic_seed():
    block = SRC[SRC.index('def evaluate_seed_expression_at_time'):SRC.index('def goava_get_note')]
    assert 'graph_seed_state' in block
    assert 'dynamic_seed' in block

def test_hover_tooltip_payload_and_cache():
    for token in ('GraphIdentity=', 'DynamicSeed(t)=', 'curvature=', 'd/dt=', '_graph_seed_tooltip_cache_key'):
        assert token in SRC
    assert 'viewport().setMouseTracking(True)' in SRC
    assert 'viewport().installEventFilter(self)' in SRC

def test_tooltip_does_not_change_graph_sample_count():
    block = SRC[SRC.index('def _graph_seed_hover_tooltip'):SRC.index('def eventFilter', SRC.index('def _graph_seed_hover_tooltip'))]
    assert '_GRAPH_SEED_SAMPLES' not in block
    assert 'graph_seed_state' in block
