# R124 features + ISO Julia fix — UNVERIFIED candidate (written blind, not yet tested)

## ISO builder fix
- `BUILD_ISO/stamp_final_initramfs_v35_22zz.sh`: before the Julia smoke test, the project-root `julia/*.jl`
  sources are always installed into `/opt/groovebox/julia`. A reused cached `$WORK/root` kept the old
  `GrooveboxHybrid.jl` (`ccall((:gb_voice_synth_f32, lib))`, the "ccall function name and library
  expression cannot reference local variables" error at line 70/77). The stage now fails early, with a
  clear message, if the old form is still staged.

## New modules (Science & Live menu)
measure_core, master_chain, signal_truth, repro_stamp, constraint_composer, param_lineage, scene_pads,
av_scene_graph, game_export_check, connect_probe, midi_learn, command_palette (Ctrl+K, merged with the
accessibility palette — one palette), device_profiles, safe_mode, r124_features (hub, installed 1.4 s
after start). Set GROOVEBOX_NO_SAFE_PROMPT=1 to skip the crash prompt in automated runs.

## Known open reports (being investigated)
- Patch Modular tab button in the Expand frame does not open the editor.
- Markov Resampler launcher shows "Error -3".
- Randomizers reported as not working.

## Follow-up patch (blind)
- error_report.py: every launcher failure now says the exception type, message and code location
  (e.g. "KeyError: -3 — file.py:212 in fn"), with the full traceback in the session log. Uncaught
  exceptions in any button (randomizers included) also show in the status bar instead of failing silently.
- Expand frame: the four editor tabs (EDIT SYNTH · WRITE SCRIPT · PATCH MODULAR · CALC DOMAIN) have their own
  equal-width row, so a narrow square on a 1366-wide laptop screen can no longer squeeze PATCH MODULAR out.
- Headless check on a fresh session (xvfb 1920x1080): PATCH MODULAR tab opens the patch bay (3 of 3 clicks),
  the Markov Resampler opens and previews, and 8 of 8 randomizer buttons changed the sequence. The reported
  failures therefore depend on project state or the ISO platform; the new messages will name the cause.
