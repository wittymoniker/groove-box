# Canonical morph and predictive trigger placement (Live Play, R7)

Live Play row: `🧬 Canonical morph  [amount]  keys  samples   ⏱ Place triggers: [off | ¼ beat | ½ beat | 1 beat | 1 bar]`.
Settings are saved with the project (`live_morph` in `project_schema`).

## Canonical morph: one mechanism, spectral-envelope transfer

- Target T: the cepstral envelope (20 coefficients, N=512) of the composition only. The engine keeps a
  composition-only tap (`comp_scope`), so keys, samples and the mic never feed back into their own target.
  It is refreshed at about 10 Hz and smoothed in the log domain.
- Per frame: E is the source envelope, and G = (T/E)^a clamped to [1/8, 8], where a is the amount in [0, 1].
  The frame is renormalised to its own energy, so loudness is kept.
- Keys (and pads): morphed once per note, offline, time aligned, with no added latency.
- Samples (loaded media): a streaming STFT with sqrt-periodic-Hann analysis and synthesis windows, N=512 with
  hop 256, which is exact reconstruction at G=1. Latency is a constant N-1 = 511 samples for any audio block size
  (10.6 ms at 48 kHz).
- Bypass: morph off is an exact pass-through. A silent target means G=1.

## Place triggers on the predictive time-invariant process pathway

Each Live Play row is a fixed schedule of onsets (event `t0`). It is time-invariant, so the next onset
after any instant is known exactly from the current row and from the next row shifted by `row_dur`. An empty
row falls back to the beat grid. When a key press or a sample start comes within the window before a predicted
onset, it is delayed to land on that exact sample. Outside the window it plays at once, so nothing is ever held
back by more than the window. The `N placed` readout counts placements.

Code: `canonical_morph.py` (EnvelopeMorph, cepstral_envelope, next_onset_delay), plus
`live_player.LiveEngine` (comp_scope, morph, place_window_s, trigger_delay_samples) and
`LivePlayerWindow._apply_morph` / `_morph_tick`.
