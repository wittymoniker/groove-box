# Bouncing Ball gravity collision/polarity update

- Polynomial gravity curvature phase restarts at each circular boundary hit.
- Gravity polarity flips deterministically on each hit by default; this is not random probability.
- `gravity_angle_degrees` rotates the main gravity vector. Rotating by 180 degrees reverses its direction.
- `reverse_polarity_on_hit` and `initial_polarity` are explicit controls.
- Per-sample events expose collision count, local gravity phase, current polarity, and angle for downstream canonical/heuristic/algorithm consumers.

Validation: Python compilation passed; 4 spatial synth unit tests passed. This is a source patch, not a running GUI or ISO verification.
