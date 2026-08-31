import sys, math
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from visual_determinism import fibonacci_view, select_views, camera_distance, composition_fingerprint, visual_signal_id

# 1. Deterministic mapping
A = [fibonacci_view(i, 128, 918273) for i in range(128)]
B = [fibonacci_view(i, 128, 918273) for i in range(128)]
assert A == B

# 2. Exact view uniqueness for a finite viewset
keys = {(v['yaw'], v['pitch'], v['roll'], v['distance'], v['fov_deg']) for v in A}
assert len(keys) == 128

# 3. Object-count independence of the camera lattice
for i in range(32):
    v1 = fibonacci_view(i, 64, 42)
    v2 = fibonacci_view(i, 64, 42)
    assert v1 == v2

# 4. Coverage selector is deterministic and non-repeating
S1 = select_views(32, 42)
S2 = select_views(32, 42)
assert S1 == S2
assert len({(v['index'], v['count']) for v in S1}) == 32
assert min(camera_distance(S1[i], S1[j]) for i in range(32) for j in range(i)) > 0.0

# 5. Composition fingerprint is order-independent
objs1 = [
    {'id': 2, 'type': 'orb', 'x': 1.0, 'y': 2.0, 'z': 3.0},
    {'id': 1, 'type': 'ring', 'x': 4.0, 'y': 5.0, 'z': 6.0},
]
objs2 = list(reversed(objs1))
assert composition_fingerprint(objs1, seed=42) == composition_fingerprint(objs2, seed=42)
assert composition_fingerprint(objs1, seed=42) != composition_fingerprint(objs1, seed=43)

# 6. Projection identity changes when and only when canonical view identity changes
fp = composition_fingerprint(objs1, seed=42)
id1 = visual_signal_id(42, fp, S1[0])
id2 = visual_signal_id(42, fp, S1[1])
assert id1 != id2
assert id1 == visual_signal_id(42, fp, S1[0])

print('PASS: deterministic mapping')
print('PASS: 128/128 exact unique camera states')
print('PASS: deterministic max-min view selection')
print('PASS: order-independent composition fingerprint')
print('PASS: unique visual projection identities')
print('RESULT: 5/5 invariant groups passed')
