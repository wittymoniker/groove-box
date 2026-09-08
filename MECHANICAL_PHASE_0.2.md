# Mechanical Phase 0.2

This pass starts the mechanical translation phase without pretending that static structure equals behavioral parity.

## What changed

- `tools/reverse_decode_groovebox.py` now builds a persistent **mechanical holdings account**.
- It produces eight strategic behavioral scopes: randomize/restore, seed authority, audio render parity, save/load fingerprint, visual determinism, media carrier, performance identity, and game bridge.
- Every decoded function now carries a static semantic-risk score, branch/try metadata, dynamic-call risk, cross-struct edge count, and a conservative `mechanical_static_ready` flag.
- The scoper expands highest-risk cross-struct regions first and leaves low-risk regions compressed.
- Generated outputs now include:
  - `mechanical_scope_plan.json`
  - `mechanical_scope_plan.md`
  - `mechanical_holdings.json`
  - the normal reverse translation tensor and generated sCode.

## Current static gauge

Reference source: `groovebox.py` (40,369 lines)

- classes: 95
- functions: 1,129
- UI controls: 216
- shared-state edges: 4,141
- cross-struct state edges: 1,453
- statically mechanical candidates: 741
- semantic-review candidates: 388

`741 / 1129` is **not** a behavioral completion percentage. It is the number of functions that have no obvious AST-level large/dynamic/cross-struct hazard under this pass. Behavioral parity remains gated by differential tests and scoped semantic agreement.

## Strategic use

The translator should now attack the high-risk common hubs first (`init_ui_components`, `_render_mixdown_buffer`, `_apply_project_snapshot`, canonical playlist reconciliation/finalization, media/game bridges), then re-run the scoper. As those hubs are split and certified, their downstream regions should become mechanically emit-able without repeatedly re-decoding the whole application.
