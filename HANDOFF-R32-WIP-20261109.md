# Groovebox R32 — work-in-progress handoff (2026-11-09)

Base: the user's R31 copy (MATGROOVEBOX.zip, RELEASE-R31-20261108.txt, R31.7).
Status: **work in progress, not a release.** The overlay is not synced and the ISO/EXE chain is not updated yet.

## Done in this pass

1. **`hardcoded_fx.py` (new): the Meum FX core.** It implements the five permitted FX in pure NumPy, in a fixed order:
   PKP Envelope → Fractallizer → EQR → ∞M HyperDrive → Master Hard Clipper.
   - Trig uses the author-series kernels; there are no `np.sin`/`math.sin` calls. Every division goes through `ot_div` with an explicit zero policy (no epsilon).
   - It has no SciPy dependency, so output is the same on every OS.
   - Post-processing helpers: `measure`, `remove_dc`, `peak_normalize`, `trim_silence`, `isn_fade`, `render_chain`, `assert_permitted`.
2. **Live Player rack.** `DJChain` now wraps `MeumPerformanceRack`:
   - Fractal tilt replaces the LP/HP filter.
   - EQR replaces echo.
   - ∞M HyperDrive replaces bitcrush.
   - The PKP gate replaces the square gate.
   - Repeat (stutter) is kept.
   - Saved `p` keys are unchanged.
3. **Live Jam (groovebox.py).** The tanh soft clip, FFT filter and delay/reverb/chorus taps are gone and mapped onto the permitted FX. `live_jam_ui.py` toggles are relabelled to match.
4. **Per-step EQ, sidechain key envelope and LUFS K-weighting are SciPy-free.**
   - Per-step EQ is a zero-phase book-isn bell.
   - The sidechain key envelope is a vectorised peak-decay.
   - LUFS uses the series-kernel magnitude response; it matches SciPy's IIR result to 1e-6 LU.
5. **Bug fix:** `_apply_hyperdrive_audio` with the Trigonometry Engine ON used half the phase, which retuned the HyperDrive an octave down. Both modes now share `hardcoded_fx.fi_hyperdrive`.
6. **`window_manager.py` (new).** Fixes **Live Player minimising together with Main**: every non-modal tool window had Main as its transient parent. The new module:
   - clears the transient parent at Show and adds minimise/maximise buttons;
   - remembers geometry per window and clamps windows back on screen after a display hot-plug;
   - adds snap/tile/cascade/minimise-all/restore-all/cycle. Shortcuts: Ctrl+Alt+←/→/↑/↓, T, C, D, R, plus Ctrl+` (Meta variants too);
   - adds a "⊞ Arrange" menu and a right-click menu on window-bar tabs.
7. Tests: `test_r32_window_manager_20261109.py` (4 pass).

## Next (planned)
- labwc `rc.xml`: OS keybinds (snap / iconify / Alt+Tab / Alt+F4) and a titlebar with iconify.
- Simple Synth macros (Tone / Motion / Body) in each Edit Synth rack unit.
- A Post-Process window (offline FX chain plus measure, trim, DC, normalize and fades), batch mode, a take finisher in Live Player, and a before/after loudness compare.
- `scripts/audit_fx_paths.py`: a build preflight that fails on non-permitted FX in audio paths.
- Make processes uniform: one helper-spawn policy (env, priority, thread caps, parent_watch) on every OS.
- UI lag / memory sweep: timers in hidden windows, unbounded lists, extra windows never freed.
- Sync the ISO overlay and runtime manifest, add new modules to the EXE spec and clear caches.
- Package MATH_GROOVEBOX_V3 (.zip + .tar.gz), then tests, then full-length demo exports.

## Continuing in Claude Code
Extract the archive and open a terminal in `MATH_GROOVEBOX-v3/`. Run `claude` and ask it to read this file and continue from "Next".
Offscreen Qt tests: `QT_QPA_PLATFORM=offscreen python3 -m pytest -q test_r32_window_manager_20261109.py`
