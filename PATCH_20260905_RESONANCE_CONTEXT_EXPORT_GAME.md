# 2026-09-05 Resonance / Context / Export / Game / Logo patch

This patch adds the following user-facing contracts:

- Canonical Resonance keeps the active protection domain (50–150% protected,
  0–200% overwrite) but no longer uses `np.clip` to flatten legal resonance
  values. Legal values pass through exactly; malformed/out-of-domain external
  values fall back explicitly instead of saturating silently.
- Playlist automation follows the active resonance domain, including the full
  0–200% overwrite range.
- Context-selectable divide-by-zero helper supports explicit useful policies:
  `0`, `1`, signed infinity, numerator/n, or an explicitly supplied solved
  x/y-equivalent value. OT retains 0/0→1 and uses signed infinity for nonzero/0.
  Ordinary DSP compatibility division uses explicit zero→0 rather than epsilon.
- GLOBAL / LOCAL context is taken from the visible selector itself. LOCAL uses
  the currently selected instrument dropdown as the authoritative destination.
  Blank/new automation lanes therefore do not inherit Z-Pinch Resonator unless
  Z-Pinch is actually the selected/owning operator.
- The Main Window now exposes Draw Wave Matrix, Record Global, and Record →
  Operator controls. Recording runs on a worker thread so the UI remains live.
- Generated game launch tracks one child process at a time. Successful launch
  dismisses the launcher dialog automatically while the game continues running.
- Audio and video exports expose `Stitch .part files into final output`, default
  ON. Audio stitching verifies the written WAV parts reconstruct the exact PCM
  before final output. Video stitching remains ffmpeg concat based. OFF leaves
  the recoverable part set without forcing a final stitch.
- The old blocking video size-confirmation dialog is removed. Size and learned
  render-time estimates are shown in the status bar while rendering begins
  immediately after Save/options confirmation.
- Live visual monitors now use adaptive UI backpressure. Waveform feedback stays
  responsive while FFT/scenograph/HUD cadence automatically backs off when paint
  cost approaches the UI timer budget. Audio processing is untouched.
- Branding uses `assets/logo.png` and root `logo.png`, window title is exactly
  `Mathematician's Groovebox`, QApplication identity is set, and Linux `.desktop`
  entries/install script install/use the icon theme name `mathematicians-groovebox`.

Validation: `python -m py_compile groovebox.py signal_lab.py` passes. Unified
`python tests.py` result: 16 passed, 1 skipped (optional PyQt6 component registry),
0 failed.
