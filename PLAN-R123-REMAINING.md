# R123 — Remaining Plan (UNVERIFIED candidate)

Status: everything below is still planned or in progress. Treat this package as an
**unverified repair candidate** until the GUI and ISO acceptance steps pass on real hardware.

## A. Verification (in progress when this archive was sent)

1. **Full pytest run, root tests only** (`--ignore=BUILD_ISO --ignore=V3_REFERENCE`, `-n 2`).
   Compare it with the baseline of 94 pre-existing failures, 989 passed and 8 skipped. Any new failure that
   touches phase-8 files (groovebox.py, panel_synth_deck.py, mm_fields.py, mm_visual.py,
   mm_mirror.py, touch_compat.py, tablet_keyboard.py, live_keys.py, live_deck.py,
   julia_bridge.py) gets fixed before the final archive.
   - Note: collecting the whole tree fails with "import file mismatch" because
     BUILD_ISO/app-overlay-v35.22zz holds copies of root tests with the same names. Plan: add
     `norecursedirs = BUILD_ISO V3_REFERENCE .venv` to pytest config so plain `pytest` works.
2. **Headless GUI checks (/tmp/r123i.py).** These already pass:
   - LIVE DECK builds, with pool and routes text; 41 pads; the BPM+1 pad works
   - panel Mod Path fields are present
   - tablet keyboard: ABC page typing, latching Shift, backspace, mutually exclusive F-key page
   
   Still running:
   - ☰ Menu key → context menu
   - ✎ custom-key dialog save
   - 450 ms touch-hold → right-drag; a hold must not add a pole; a tap adds a pole
   - Stage right-drag (perspective azimuth, plus rotating routing-mirror poles and magnitude)
   - QScroller touch scrolling grab
   - Ctrl+Shift heavy-command debounce
   - full-layout screenshot
3. **New phase-8 test files:** `test_r123_phase8.py` (8 passed earlier) and
   `test_r123_phase8_routes_hybrid.py` (Go/Julia toolchains on PATH).
4. **Hybrid parity rerun with Go on PATH.** C, LuaJIT, Rust and C++ already show parity True with the pool at 24.
5. **Payload sync.** Run `scripts/sync_runtime_payload.py` so the BUILD_ISO app overlay matches the root app.
6. Commit, write the release-notes test-result section, and send the final archives (.tar.gz + .zip).

## B. ISO acceptance (needs the user's hardware)

- Rebuild the ISO with the current BUILD_ISO and send the full build log.
- Boot-test on a Dell Latitude 3510 and an Acer Nitro 5 with Secure Boot both on and off. Confirm:
  - Limine shows no initrd_lib.sh null-byte warning
  - the CXXABI/libstdc++ preload check passes (the system libstdc++ loads first, even when RPATH/RUNPATH or an already-loaded library overrides LD_LIBRARY_PATH)
  - the Julia smoke test passes (ccall/exports fix, juliacall pairing fix)
  - the GUI reaches the main window, audio comes out, and touch/tablet mode works on touch panels
- Only after those pass: build and send the .iso files.

## C. Next improvements (after verification)

Goal: a minimal, full-spectrum, scientifically oriented A/V/game production tool that is
non-redundant and unique in production/composition, post-processing and external app support.

1. **Redundancy sweep.** Merge overlapping randomizers and morph controls under the Global Morph
   Bridge. Each feature should have one canonical control, with aliases only through shortcuts.
2. **Post-processing chain audit.** One ordered, measurable chain (EQ → dynamics → spatial → master
   metering) with a measurement-bus readout on every stage. Remove duplicate limiters.
3. **External app support.** Keep a single route registry (route_handles + patch_bay_sync) for JACK/PipeWire,
   MIDI/OSC, file export and the game/visual outputs. Probe each backend at startup and gray out any that are missing
   instead of failing.
4. **Live performance.**
   - Make the LIVE DECK pad layout user-assignable, using the same QSettings store as the tablet custom keys
   - Add MIDI-learn for pads
   - Add a CPU guard that pauses heavy commands above 85% load
5. **Device compatibility.**
   - Persist a per-device layout profile (small-screen, tablet, desktop)
   - Check high-DPI scaling at 125%, 150% and 200%
   - Pen pressure → Mod Path magnitude
   - On-screen keyboard: honor the system OSK where one exists, otherwise use the fixed dock
6. **Cross-platform builders.**
   - Re-sweep the Windows/macOS EXE builder scripts for path quoting, the
     Python 3.14 wheel availability (PyQt6, lupa, juliacall), and code-signing placeholders
   - The ISO builder needs to keep working on hosts that don't use GNU tools (`tr -d '\000'` style fixes everywhere `$(...)`
     reads binary data)
7. **Memory and long-session stability.**
   - Run a 2-hour soak with autopilot on to watch for leaks (follow-up to the Clear Memory fix)
   - Cap the live-deck pool thread and the meter timers when the window is hidden
8. **Docs.** Merge HELP_TEXT, the Ctrl+/ sheet and the release notes into one generated keybind reference.
