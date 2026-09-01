PLAYER / CAMERA FIX — 2026-09-01

Fixes:
- WASD movement is local and works regardless of network authority.
- A/D strafe and W/S move relative to look direction.
- Player is rendered at the camera/world origin instead of orbiting around a sigil.
- Sigils use Cartesian player-relative projection rather than a fixed HUD ring.
- Click no longer adds an artificial yaw/spin impulse.
- Mouse wheel now performs real zoom; Shift+wheel changes camera mode.
- Activation uses actual Cartesian distance to nearby sigils/resources/waypoints.
- Legacy angle remains compatibility metadata only and changes only after player movement.
- Sigils remain opt-in; generated open-world sessions have sigil_count=0 unless explicitly forced.

Validation:
- py_compile passed
- test_game_runtime.py passed
- test_open_world_sandbox.py passed
- test_fractal_spatial_engine.py passed
