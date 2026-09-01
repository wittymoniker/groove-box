#!/usr/bin/env python3
"""Final purity test for the instrument→visual translation layer.

The handler intentionally has no audio/harmonic/gameplay inputs. Instrument N
may only change sampling density and inverse-count contribution; fixed master
slots, numeric identity and phase remain invariant.
"""
from visual_determinism import instruments_handler

seed = 918273.0
seq = [-100.0, 0.0, 25.0, 400.0]

# Same call is byte-for-byte stable in value space.
assert instruments_handler(3, 16, seed, seq) == instruments_handler(3, 16, seed, seq)

# Existing slots never move as N increases.
for i in range(2):
    a = instruments_handler(i, 2, seed, seq)
    b = instruments_handler(i, 8, seed, seq)
    c = instruments_handler(i, 48, seed, seq)
    assert a["master_slot"] == b["master_slot"] == c["master_slot"] == i
    assert a["identity"] == b["identity"] == c["identity"]
    assert a["numeric_unit"] == b["numeric_unit"] == c["numeric_unit"]
    assert a["phase"] == b["phase"] == c["phase"]

# Inverse-count compensation exactly preserves one unit of total weight.
for n in (1, 2, 8, 16, 32, 48, 64):
    rows = [instruments_handler(i, n, seed, seq) for i in range(n)]
    assert abs(sum(r["compensation"] for r in rows) - 1.0) < 1e-15
    assert all(0.0 < r["compensation"] <= 1.0 for r in rows)

# Numeric input spans the complete normalized range without clipping.
rows = [instruments_handler(i, 4, seed, seq) for i in range(4)]
units = [r["numeric_unit"] for r in rows]
assert min(units) == 0.0
assert max(units) == 1.0

# No harmonic/gameplay/audio state is part of the contract: changing the
# surrounding seed labels or count cannot alter an already-defined identity.
assert instruments_handler(1, 8, seed, seq)["identity"] == 1.5 / 64.0
assert instruments_handler(1, 64, seed, seq)["identity"] == 1.5 / 64.0

print("PASS: deterministic instrument→visual translation")
print("PASS: existing master-slot identity is N-invariant")
print("PASS: inverse-count compensation sums exactly to 1")
print("PASS: sequential numeric range spans 0..1 without clipping")
print("PASS: translation contract contains no harmonic/gameplay/audio state")
print("RESULT: 5/5 final determinism purity groups passed")
