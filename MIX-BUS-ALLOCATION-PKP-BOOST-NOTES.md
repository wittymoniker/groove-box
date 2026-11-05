# Spatial Synth Bus Allocation + PKP DJ Boost defaults

Requested defaults:
- Vector, Wavetable, Bouncing Ball, Cellular Automata: shared spatial/canonical bus gain `0.19758`.
- Remaining synth/instrument lanes: other-instruments bus gain `0.8024`.
- PKP DJ Boost amount/wet mix default: `0.5` (50%); source bus gain metadata remains `1.0` (100%).
- Peer lanes remain concurrent and have no lane-priority policy. Gain is metadata attached to each scheduled event and lane; it does not affect event ordering.

Files changed: `shared_synth_context.py`, `groovebox.py`, `test_shared_synth_context.py`, plus synchronized copies in `BUILD_ISO/app-overlay-v35.22zz/`.

Validation performed: `py_compile` for main Python modules; 8 unit tests passed, including new bus allocation and concurrency tests.

Important limitation: the current Shared Synth Context remains a deterministic event/context layer, not yet a fully wired multibus audio renderer for all live synth voices. Thus the bus gains are now explicit on the shared schedule, but this patch alone does not prove those ratios are applied to every live audio callback or every exported mixdown. PKP's existing DJ boost voice path uses the changed 0.5 default directly. No ISO build or GUI/audio end-to-end test was performed.
