# R123 phase 8 (interim, after flight) — UNVERIFIED CANDIDATE

Not verified: the GUI and ISO acceptance steps have not passed on your hardware yet.

See HELP_TEXT.md ▸ "R123 (UNVERIFIED CANDIDATE) — WHAT IS NEW ▸ Phase 8" for the user-facing list.

ISO-relevant fixes in this drop
- julia/GrooveboxHybrid.jl: ccall takes a cached Libdl pointer (fixes "ccall function name and library
  expression cannot reference local variables" in smoke_test.jl that stopped stamp_final_initramfs_v35_22zz.sh).
- julia_bridge.py: PYTHON_JULIACALL_EXE pairs with PROJECT only when that project already holds PythonCall;
  otherwise the julia binary is handed to JuliaPkg (PYTHON_JULIAPKG_EXE).
- BUILD_ISO/initrd_lib.sh: gb_fast_is strips NUL bytes (removes "ignored null byte in input" warning).
- Runtime payload re-synced into BUILD_ISO/app-overlay-v35.22zz.

Please rerun the ISO build and send the log plus boot results (Dell Latitude 3510 / Acer Nitro 5).

## Remaining plan
See PLAN-R123-REMAINING.md (verification in progress, ISO acceptance pending, next improvements).

## Phase 8 UI fixes (user report, 2026-11-19)
- Panel synth: the square now fits the window (side = min(half panel width, window height − 160));
  it was 2,468 px tall. Its overview is a 2×2 grid of the four editors (click to open inside).
- Hover/wheel inside the panel: the Expand frame was briefly shown as its own window before it had a
  parent, so the window-scroll filter wrapped it in an extra scroll area. Fixed (no stray window,
  `gb_no_auto_scroll` on the frame and on embedded editors).
- Geometrics row: no AlignTop; the four synths share one height (no empty bars under the shorter ones).
- Top pane: LIVE DECK background is transparent, so it shows the workspace pane colour.
- Mod Path: the duplicate fields were removed from the panel; Mod Path stays on the ring view's
  side rails next to the Multidim sphere.
- Wheel: a click arms only the control it lands on (pad, slider, list, text, 3-D view), never the
  panel around it. Bubbled presses no longer arm parents, so the window keeps scrolling over the
  Mod Path Bay and the ring view unless you clicked that exact control.
- Cleanup: groovebox.py.bak and the nested MATH-GROOVEBOX_v3/ copy moved to attic/ (not shipped).
  pytest.ini skips the BUILD_ISO/V3_REFERENCE/attic duplicates. audio_routing.py no longer imports a
  missing module at import time.
- Dependencies: requirements-optional.txt lists every guarded third-party import. The ISO
  installs psutil, soundfile, mido, py7zr, threadpoolctl, cryptography and pyudev best-effort.
