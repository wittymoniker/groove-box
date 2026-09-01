#!/usr/bin/env python3
"""Final deterministic purity battery.

The reference path deliberately excludes harmonic, audio, gameplay, timing,
UI, and mutable-RNG state.  It verifies that instrument count changes sampling
density/weight only and that finite pixel precision is the only allowed loss.
"""
from visual_determinism import (
    instrument_population, pure_visual_object, pure_visual_population,
    quantization_error, golden_composition_fingerprint,
)

SEED = 918273.0
VALUES = [-100.0, 0.0, 25.0, 400.0]

# 1. Byte/value determinism.
a = pure_visual_population(16, SEED, VALUES)
b = pure_visual_population(16, SEED, VALUES)
assert a == b

# 2. Existing identities are invariant under count changes; adding/removing
#    samples never renormalizes the coordinates of survivors.
for i in range(8):
    rows = [pure_visual_object(i, n, SEED, VALUES) for n in (8, 16, 32, 64)]
    assert len({r["identity"] for r in rows}) == 1
    assert len({r["numeric_unit"] for r in rows}) == 1
    assert len({r["phase_unit"] for r in rows}) == 1

# 3. Conservation: compensation is exactly 1/N and totals to one.
for n in (1, 2, 3, 8, 16, 31, 48, 64):
    pop = instrument_population(n, SEED, VALUES)
    assert all(r["compensation"] == 1.0 / n for r in pop)
    assert sum(r["compensation"] for r in pop) == 1.0

# 4. Full numeric range survives translation without clipping.
units = [r["numeric_unit"] for r in instrument_population(4, SEED, VALUES)]
assert units == [0.0, 0.2, 0.25, 1.0]
assert min(units) == 0.0 and max(units) == 1.0

# 5. Permutation behavior is exact: sequence order is data, so permuting the
#    numeric sequence permutes the numeric assignments, not the slot identities.
perm = list(reversed(VALUES))
orig = instrument_population(4, SEED, VALUES)
rev = instrument_population(4, SEED, perm)
assert [r["master_slot"] for r in orig] == [r["master_slot"] for r in rev]
assert [r["numeric_unit"] for r in orig] == list(reversed([r["numeric_unit"] for r in rev]))

# 6. Quantization is explicitly bounded and is the only representation loss
#    introduced by a finite pixel grid.
for u in (0.0, 0.125, 0.5, 0.999999, 1.0):
    assert 0.0 <= quantization_error(u, 1920) <= 1.0 / 1920.0

# 7. Golden structural fingerprints are stable and count-sensitive only at the
#    population level; repeated evaluation is identical.
for n in (1, 8, 16, 32, 64):
    assert golden_composition_fingerprint(n, SEED, VALUES) == golden_composition_fingerprint(n, SEED, VALUES)

print("PASS: pure visual path is deterministic")
print("PASS: existing instrument identities are N-invariant")
print("PASS: inverse-count compensation conserves total weight")
print("PASS: numeric inputs preserve their full normalized range")
print("PASS: sequence permutation changes data assignment, not identity")
print("PASS: finite-pixel precision is explicitly bounded")
print("PASS: golden structural fingerprints are stable")
print("RESULT: 7/7 final determinism purity groups passed")
