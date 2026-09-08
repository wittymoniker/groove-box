# Mathematician's Groovebox — sCode Reverse-Decoded Finished Stab

This build deliberately takes the fastest safe route toward a finished Groovebox:

1. **The mature 40k-line Python Groovebox remains the behavioral reference/backend** so the broad feature set is not discarded.
2. `tools/reverse_decode_groovebox.py` reads that Python implementation *backwards* into a progressively refinable sCode structure.
3. It emits `generated/groovebox_finished_stab.sC` plus `generated/groovebox_translation_tensor.json`.
4. The tensor records classes, methods, UI controls, shared-state flows, source locations, domains, and unresolved translation cells.
5. A prompt/target can selectively raise decoder resolution instead of exploding the entire program at once.
6. `scode/runtime.py` attaches this tensor to the live Groovebox as `studio.scode_translation_tensor` and exposes `studio.scode_reverse_target(query, resolution)`.
7. `SCODE_NATIVE_PREVIEW/` contains the current C++ sCode native runtime/toolchain for continuing pure-native replacement in parallel.

## Run

```bash
./RUN_FINISHED_STAB.sh
```

This requires the same Python/PyQt6 dependencies as the mature reference Groovebox. It is **not yet a claim of full pure-sCode/native parity**: unsupported structs deliberately fall back to the mature Python implementation.

## Targeted reverse decode

```bash
python3 tools/reverse_decode_groovebox.py --target "randomize sequence restore" --resolution 10
python3 tools/reverse_decode_groovebox.py --target "visualizer canonical seed" --resolution 12
python3 tools/reverse_decode_groovebox.py --target "save load project" --resolution 10
```

The important rule is coarse-to-fine: preserve the whole program's class identity at low resolution, expand the current prompt's dependency cone, then use the resulting problem tensor to port the highest-leverage structs first.
