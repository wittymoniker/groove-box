# Groovebox NaN Video Export + Exit Smoothness Fix — 2026-09-12

Applied to the 2026-09-11 20:36:05 Groovebox source archive and synchronized into the embedded APPLIANCE_ISO Groovebox source.

## Video export

- Prevents non-finite (`NaN` / `Inf`) waveform, seed, graph, camera, projection, color, and geometry values from reaching integer raster conversions.
- Fixes the silent-band octave-boundary path that could become `Inf`.
- Fixes degenerate triangle handling (`abs(den) >= 0` previously accepted a zero denominator).
- Skips invalid raster geometry and bounds pathological finite line coordinates so a bad scripted point cannot make a frame perform millions of raster steps.
- Applies a final finite-pixel guard before `uint8` conversion.
- Adds part/frame/time context to video render failures to make any future export fault immediately locatable.

These guards leave already-finite deterministic values unchanged.

## Exit / shutdown

- Makes preview-render shutdown idempotent.
- Rejects new preview work after shutdown starts and ignores late worker/optimizer completions.
- Stops child Qt timers before widget destruction.
- Explicitly closes the main Draw / Record / Video workbench so camera/microphone handles are released.
- Closes the Performance panel before teardown.
- Makes the sCode optimizer shutdown idempotent, clears queued GUI callbacks, cancels pending futures, stops optimizer timers, and shuts down its worker pools.

## Regression checks

The targeted regression set passed 26 tests, covering NaN video safety, video render contracts, MP4 export regression coverage, lag/realtime contracts, idle/camera release behavior, shared V4L2 multi-recording, and project-state integration.

The build-check environment used for this patch does not include PyQt6, so a full GUI launch/render test could not be performed there; Python compilation and the static/contract regression suite passed.
