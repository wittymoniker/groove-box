import unittest
from spatial_synth_engines import polynomial_gravity, throw_ball, cellular_automaton

class SpatialSynthTests(unittest.TestCase):
    def test_polynomial_gravity(self):
        self.assertAlmostEqual(polynomial_gravity(2, (1, 2, 3)), 17)
        self.assertAlmostEqual(polynomial_gravity(2, (1, 2, 3), degree=1), 5)
    def test_ball_is_deterministic_and_bounded(self):
        a=throw_ball(steps=300, x=0.2, y=0.1, vx=2.0, vy=-0.5, gravity_coefficients=(0, 0, 0.01))
        b=throw_ball(steps=300, x=0.2, y=0.1, vx=2.0, vy=-0.5, gravity_coefficients=(0, 0, 0.01))
        self.assertEqual(a,b)
        self.assertTrue(all((p['x']**2+p['y']**2) <= 1.000001 for p in a['samples']))
    def test_multi_state_cellular_automaton_is_deterministic(self):
        initial=[[0,1,2],[1,2,0],[2,0,1]]
        rules=[{'state':1,'neighbor_type':2,'count':2,'next':2},{'state':2,'neighbor_type':1,'count':1,'next':0}]
        a=cellular_automaton(3,3,3,initial,rules,5)
        b=cellular_automaton(3,3,3,initial,rules,5)
        self.assertEqual(a,b)
        self.assertEqual(len(a['frames']),6)
        self.assertTrue(all(0 <= v < 3 for row in a['frames'][-1] for v in row))

    def test_ball_restarts_curvature_and_reverses_polarity_on_hit(self):
        a=throw_ball(steps=120, x=0.8, y=0, vx=2.0, vy=0.0, gravity_coefficients=(0,0,0.1), gravity_angle_degrees=90)
        hits=[s for s in a["samples"] if s["collision"]]
        self.assertTrue(hits)
        self.assertTrue(any(h["gravity_polarity"] == -1 for h in hits))
        self.assertTrue(any(h["gravity_phase"] == 0.0 for h in hits))
        rotated=throw_ball(steps=10, gravity_angle_degrees=270, reverse_polarity_on_hit=False)
        self.assertEqual(rotated["gravity_angle_degrees"],270.0)

if __name__=='__main__': unittest.main()

class ChordSlotPitchTests(unittest.TestCase):
    def test_chord_slots_map_to_equal_pitch_subdivisions(self):
        import numpy as np
        from spatial_synth_engines import apply_chord_slot_pitch
        track = np.ones(12, dtype=np.float64)
        mask = np.array([False, False] + [True] * 8 + [False, False])
        apply_chord_slot_pitch(track, mask, 1.0, [0, 12, 7], 3, 3)
        self.assertEqual(track[:2].tolist(), [1.0, 1.0])
        self.assertEqual(track[10:].tolist(), [1.0, 1.0])
        self.assertEqual(track[2:10].tolist(), [1.0, 1.0, 1.0, 2.0, 2.0, 2.0, 2**(7/12), 2**(7/12)])

    def test_chord_slot_pitch_clamps_budget_and_handles_empty_masks(self):
        import numpy as np
        from spatial_synth_engines import apply_chord_slot_pitch
        track = np.ones(4, dtype=np.float64)
        apply_chord_slot_pitch(track, np.zeros(4, dtype=bool), 1.0, [12], 1, 1)
        self.assertTrue(np.array_equal(track, np.ones(4)))
        mask = np.ones(4, dtype=bool)
        apply_chord_slot_pitch(track, mask, 1.0, [12, 24, 36, 48], 4, 2)
        # Only the two-slot budget is active; the rest of the list cannot expand voice work.
        self.assertEqual(track.tolist(), [2.0, 2.0, 4.0, 4.0])

    def test_reduced_chord_count_preserves_authored_interval_tail(self):
        from spatial_synth_engines import normalize_chord_intervals
        authored = [0, 3, 7, 14, 21, -5]
        reduced = normalize_chord_intervals(authored, 2, 512)
        self.assertEqual(reduced, authored)
        expanded = normalize_chord_intervals(reduced, 8, 512)
        self.assertEqual(expanded[:len(authored)], authored)
        self.assertEqual(len(expanded), 8)
        self.assertTrue(all(-96 <= x <= 96 for x in expanded))
