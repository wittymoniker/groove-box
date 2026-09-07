# Performance output-routing startup fix — 2026-09-07

Fixed the ABI9 Performance startup regression:

`'Performance' object has no attribute '_apply_output_selection'`

Cause: `restore_state()` retained the former `_apply_output_selection()` method name after the output router was consolidated under `_apply_output_routing()`.

Fix:
- `restore_state()` now applies restored display/audio selections through `_apply_output_routing()`.
- `_apply_output_selection()` remains as a backward-compatible alias so older session/project callback paths cannot trigger the same AttributeError.
- The same `performance.py` is synchronized into `APPLIANCE_ISO/source/rootfs/opt/groovebox/`.
- Python syntax/AST contract checks passed for both copies.

Runtime GUI launch was not executed in the build container because PyQt6 is not installed in that container; the packaged/runtime environment remains responsible for Qt availability.
