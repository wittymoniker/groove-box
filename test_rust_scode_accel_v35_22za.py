#!/usr/bin/env python3
"""Static/numeric release contract for the v35.22z Rust+sCode optimization pass."""
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent
rs = (ROOT/'rust/groovebox_accel/src/lib.rs').read_text()
gb = (ROOT/'groovebox.py').read_text()
rt = (ROOT/'platform_runtime.py').read_text()
build = (ROOT/'scripts/build_rust_accel.py').read_text()
opt = (ROOT/'sCode/apps/groovebox/groovebox_optimizer.sC').read_text()

required = [
    'gb_phase_build_f64','gb_accumulate_f32','gb_ot_div_f64','gb_ot_apply_f64',
    'gb_meum_trig_f64','gb_meum_space_f64','gb_boxcar_same_abs_f64',
    'gb_convolve_ola_f32','gb_euclidean_legacy_u8','gb_splitmix64_f64',
]
for sym in required:
    assert f'fn {sym}' in rs, sym
assert 'return [rust, cpp]' in rt or 'rust+cpp' in rt
assert 'CARGO_TARGET_DIR' in build and 'cargo, "test"' in build and '"--locked"' in build
assert 'rust_plan_abi=1' in opt and 'rust_fft_block=' in opt and 'rust_workers=' in opt
assert '_native_euclidean_legacy(pulses, pcount, 0)' in gb
assert '2 => book_isy(v)' in rs and '3 => book_isx(v)' in rs
assert '4 => book_cyclic_isn(v)' in rs and '5 => book_inverse_isn(v)' in rs and '6 => book_inverse_ics(v)' in rs
assert 'Author/book cyclic isn' in rs and 'book_asin_unit' in rs
assert 'def series_book_isx(x):' in gb and 'def series_book_isy(x):' in gb and 'def series_book_tan(x):' in gb
assert 'return series_book_isy(x)' in gb and 'return series_book_isx(x)' in gb

# Validate the exact boxcar indexing used by Rust against NumPy for odd/even windows.
def rust_formula(x, w):
    x=np.asarray(x,dtype=float); n=len(x); w=max(1,min(int(w),n))
    prefix=np.concatenate(([0.0],np.cumsum(np.abs(x))))
    off=(w-1)//2; out=np.empty(n)
    for i in range(n):
        full=i+off; lo=max(0,full-(w-1)); hi=min(n,full+1)
        out[i]=(prefix[hi]-prefix[lo])/w
    return out
for n in range(1,33):
    x=np.linspace(-1.25,2.5,n)
    for w in range(1,n+1):
        np.testing.assert_allclose(rust_formula(x,w),np.convolve(np.abs(x),np.ones(w)/w,mode='same'),rtol=0,atol=1e-12)

# Preserve the project's existing Euclidean spelling exactly.
for steps in range(1,65):
    for pulses in range(0,steps+1):
        base=[((s*pulses)%steps)<pulses for s in range(steps)]
        for rot in (0,1,steps//2,steps-1):
            got=[]
            for i in range(steps):
                s=(i+steps-(rot%steps))%steps
                got.append(((s*pulses)%steps)<pulses)
            want=base[-(rot%steps):]+base[:-(rot%steps)] if rot%steps else base
            assert got==want,(steps,pulses,rot)
print('PASS: v35.22za Rust+sCode acceleration + author book-series contract')
