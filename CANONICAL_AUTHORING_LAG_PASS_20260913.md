# Canonical authoring lag pass — 2026-09-13

- Canonical results remain exact and deterministic; no approximation or reduced-quality preview path was introduced.
- Repeated authoring signals now use a restartable 140 ms idle debounce. Continuous slider drags, wheel edits, and typing postpone the expensive canonical transaction until input goes quiet instead of rebuilding in the middle of the gesture.
- Canonical level and LOCK-characteristic sliders no longer recompute the project fingerprint on every drag tick. The fingerprint is refreshed once by the canonical flush.
- UI labels/slider positions still update immediately.
- Long, quiet, black, transparent, static, or sparse renders remain valid outputs. No content-based cancellation threshold was added.
- This pass changes scheduling only; canonical synthesis/composition mathematics and export identity are unchanged.
