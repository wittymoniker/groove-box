#!/usr/bin/env python3
"""v35.22ze canonical book-series trig contract."""
from pathlib import Path
import math
import numpy as np

ROOT=Path(__file__).resolve().parent
from trig_series import cyclic_isn, isx, isy, tan, inverse_isn_scalar, inverse_ics_scalar

# Direct book series must reproduce conventional forward values without using
# modern sin/cos/tan in the implementation path.
xs=np.linspace(-math.pi, math.pi, 129)
np.testing.assert_allclose(isx(xs), np.cos(xs), rtol=0, atol=4e-13)
np.testing.assert_allclose(isy(xs), np.sin(xs), rtol=0, atol=4e-13)
mask=np.abs(np.cos(xs))>1e-6
np.testing.assert_allclose(np.asarray(tan(xs))[mask], np.tan(xs)[mask], rtol=0, atol=2e-11)
np.testing.assert_allclose(1.0-np.asarray(cyclic_isn(xs)), isx(xs), rtol=0, atol=0)
np.testing.assert_allclose(1.0-np.asarray(cyclic_isn(xs-math.pi/2.0)), isy(xs), rtol=0, atol=0)

# Inverse-isosceles coordinates use the separate Maclaurin/binomial series.
for y in (-1.9,-1.0,-0.25,0.0,0.25,1.0,1.9):
    assert abs(inverse_isn_scalar(y)-2.0*math.asin(y/2.0)) < 2e-12
    assert abs(inverse_ics_scalar(y)-(math.pi-2.0*math.asin(y/2.0))) < 2e-12

py=(ROOT/'groovebox.py').read_text()
rs=(ROOT/'rust/groovebox_accel/src/lib.rs').read_text()
cpp=(ROOT/'cpp/groovebox_accel.cpp').read_text()
jl=(ROOT/'julia/GrooveboxHybrid.jl').read_text()
sm=(ROOT/'sCode/scode/libs/math_compat.sC').read_text()
sg=(ROOT/'sCode/scode/libs/groovebox_math.sC').read_text()

start=py.index('    def _trig_engine_transform(self, op, x, *args, **kwargs):')
blk=py[start:py.index('\n    def _apply_engine_with_shared_context',start)]
assert 'return series_book_isy(x)' in blk
assert 'return series_book_isx(x)' in blk
assert 'return series_book_tan(x)' in blk
assert '_ot_sin' not in blk and '_ot_cos' not in blk and '_ot_tan' not in blk

assert '2 => book_isy(v)' in rs and '3 => book_isx(v)' in rs and '4 => book_cyclic_isn(v)' in rs
assert '.sin()' not in rs and '.cos()' not in rs and '.tan()' not in rs
assert 'std::sin' not in cpp and 'std::cos' not in cpp and 'std::tan' not in cpp
for tok in ('book_isy(', 'book_isx('): assert tok in jl
assert 'return isy(x)' in sm and 'return isx(x)' in sm and 'return isy(x) / isx(x)' in sm
assert 'return isy(x)' in sg and 'return isx(x)' in sg and 'return isy(x) / isx(x)' in sg
print('PASS: v35.22ze direct book isn -> isx/isy trig-engine contract')
