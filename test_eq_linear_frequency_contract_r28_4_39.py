"""Regression tests for linear-Hz default EQ pole distribution."""
import ast
import math
from pathlib import Path
import numpy as np

SOURCE = Path(__file__).with_name('groovebox.py').read_text(errors='replace')
TREE = ast.parse(SOURCE)
TARGETS = {'_normalize_eq_curve', '_eq_default_poles', '_eq_default_poles_build', '_eq_convolution_default_band_count'}
NODES = [n for n in TREE.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in TARGETS]
ENV = {'math': math, 'np': np}
exec(compile(ast.Module(body=NODES, type_ignores=[]), '<eq-helper-extract>', 'exec'), ENV)


def test_default_frequencies_are_linearly_spaced_for_two_instruments():
    poles = ENV['_eq_default_poles'](bands=128)
    freqs = [p['frequency_hz'] for p in poles]
    assert len(freqs) == 128
    assert freqs[0] == 10.0 and freqs[-1] == 24000.0
    deltas = np.diff(freqs)
    assert np.allclose(deltas, deltas[0], rtol=0, atol=1e-9)


def test_convolution_default_count_and_linear_spacing_at_edge_cases():
    count = ENV['_eq_convolution_default_band_count']
    assert count(2) == 128
    assert count(3) == 127
    assert count(128) == 2
    for instruments in (2, 3, 8, 64, 128):
        poles = ENV['_eq_default_poles'](bands=count(instruments))
        freqs = np.asarray([p['frequency_hz'] for p in poles])
        assert len(freqs) == count(instruments)
        assert freqs[0] == 10.0 and freqs[-1] == 24000.0
        if len(freqs) > 2:
            assert np.allclose(np.diff(freqs), np.diff(freqs)[0], rtol=0, atol=1e-8)


def test_legacy_shape_interpolation_is_preserved():
    poles = ENV['_eq_default_poles']([0, 2, 4, 6, 8, 6, 4, 2], bands=128)
    gains = [p['gain_db'] for p in poles]
    assert len(gains) == 128
    assert gains[0] == 0 and gains[-1] == 2
    assert max(gains) > 7.9
