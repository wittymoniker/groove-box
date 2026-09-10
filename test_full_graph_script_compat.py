import ast
from pathlib import Path

import numpy as np

from graph_script_context import build_graph_context, evaluate_graph_script
from dj_effects import LiveDJEffects
from videogame_engine import classify_from_composition, generate_game_script


def test_legacy_and_full_graph_scripts_share_context():
    ctx = build_graph_context(t=0.25, t_norm=0.5, x=0.2, y=-0.3, z=0.4,
                              seed=1.1975807343, domain_value=0.15,
                              sequence=2, step=3)
    legacy = "def evaluate_wave(x,y,z):\n    return x+y+z"
    modern = """def evaluate_wave(x,y,z,t=0.0,t_norm=0.0,graph=None):
    v=sin(graph_x+graph_y+graph_phase)+domain_value
    return {'wave':v,'amp':0.5+0.5*graph_u,'pitch':1+0.1*graph_curvature,'z':graph.z}
"""
    old = evaluate_graph_script(legacy, ctx)
    new = evaluate_graph_script(modern, ctx)
    assert abs(old["scalar"] - 0.3) < 1e-9
    assert {"wave", "amp", "pitch", "z", "scalar"}.issubset(new)


def test_rand_param_cached_scalar_changes_realtime_safe_processor():
    engine = LiveDJEffects(sample_rate=48000)
    engine.amount_random = 0.68
    engine.set_context(seed=1.1975807343, pair=(2, 7), sample_rate=48000)
    x = np.linspace(-0.5, 0.5, 2048, dtype=np.float32)
    a = engine.process(x, start_sample=0, random_scalar=-1.25, bpm=120.0)
    b = engine.process(x, start_sample=0, random_scalar=1.75, bpm=120.0)
    assert a.shape == x.shape == b.shape
    assert np.isfinite(a).all() and np.isfinite(b).all()
    assert not np.array_equal(a, b)


def test_generated_game_reads_graph_scripts_in_av_and_gameplay():
    fp_a = "1" * 16
    fp_b = "2" * 16
    ida = classify_from_composition(1.1975807343, live_dj_random=True,
                                    graph_scripts_fingerprint=fp_a)
    idb = classify_from_composition(1.1975807343, live_dj_random=True,
                                    graph_scripts_fingerprint=fp_b)
    assert ida.composition_fingerprint != idb.composition_fingerprint
    meta = {
        "bpm": 120, "seq_length": 16,
        "seed_script": "sin(t*MEUM)",
        "instrument_scripts": {
            "Instrument 1": "def evaluate_wave(x,y,z,t=0.0,t_norm=0.0,graph=None):\n    return {'wave':sin(graph_x+t),'speed':1+0.1*graph_w,'world_z':graph_z}"
        },
        "global_algo": {
            "apply_enabled": True,
            "script": "def global_script(t,name,i,graph=None):\n    return {'drive':cos(graph_phase+t),'rotation':graph_angle}",
            "params": {"mix": 0.4},
        },
        "live_dj_random": True,
        "live_dj_random_script": "def global_script(t,name,i,graph=None):\n    return {'drive':isn(graph_radius*MEUM+t),'speed':0.8+0.4*graph_w,'world_z':graph_z}",
        "graph_context_contract": "full_graph_v1",
    }
    script = generate_game_script(ida, meta)
    ast.parse(script)
    assert "composition_script_channels" in script
    assert "graph_drive" in script
    assert "graph_world_z" in script


def test_docs_and_canonical_writer_advertise_contract():
    root = Path(__file__).resolve().parent
    source = (root / "groovebox.py").read_text(encoding="utf-8")
    help_text = (root / "HELP_TEXT.md").read_text(encoding="utf-8")
    assert '"graph_context_contract": "full_graph_v1"' in source
    assert "generate_random_param_graph_script" in source
    assert "generate_random_instrument_graph_script" in source
    assert "FULL GRAPH SCRIPT CONTEXT" in help_text
    assert "graph_curvature" in help_text and "domain_value" in help_text
    # Domain equations and expensive graph projection use the same shared context.
    assert "local_base = graph_context_env(_base_ctx)" in source
    assert "_graph_context_cache" in source
    # The requested authoring paths all materialize richer full-graph programs.
    assert "generate_random_seed_script" in source
    assert "generate_random_global_play_algo" in source
    assert "_on_heuristic_seq_synth" in source
