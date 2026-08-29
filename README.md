# Groovebox — Complete V1

## Goal
A **unique, deterministic, non-redundant, infinitely varied** platform of
effects — re-expressible in the **simplest possible mathematical terms** —
while still fit to **infinitely varied dataset specifications**.

In practice that means every feature in this codebase is expected to satisfy
four properties at once:
1. **Deterministic** — same seed / same inputs always produce the same
   composition, patch, title, or fingerprint. Nothing here calls raw
   unseeded randomness from a live audio or generation path.
2. **Non-redundant** — the seed → output mapping is built from independent
   residue classes (hashes of seed + label) so different seeds spread across
   the output space instead of clustering or repeating.
3. **Infinitely varied** — the output space is large enough (ideally
   combinatorial, e.g. word banks × genre × topology × mood) that it does not
   feel like a fixed template with a label swapped in.
4. **Simplest possible mathematical terms** — the generators are closed-form
   functions of `seed`, `t`, and a small set of named constants (MEUM, φ,
   BPM) — not opaque lookup tables or black-box ML.

Canonical state is order-independent. Save / load / export / game
classification share one composition fingerprint.

## Run
```bash
pip install PyQt6 numpy sounddevice scipy
./launch_desktop.sh    # 96 kHz desktop
# or: ./launch_mobile.sh  # 48 kHz mobile
# or: python3 groovebox.py
```

## Defaults
| Control | Default |
|---------|---------|
| BPM | **120** |
| Base Global Frequency | **432 Hz** |
| Seed Weight | **0.72** |
| FullWeight Seed | **ON** |
| Full Unison Blend | **OFF** by default — Unison Blend spin defaults to **0.55** (locks to 1.0 only when Full Unison is switched ON) |
| Meum lattice | MEUM ≈ 1.19758… |
| App window | scales to ~92% of the available screen on launch, freely resizable, no min/max lock |


## Amplitude law (Meum hard scale, V1)
Goal-aligned: deterministic, closed-form, no soft-limiter state.

| Symbol | Value | Role |
|--------|-------|------|
| `WAV_MAX` | 1.0 | Full-scale float PCM |
| `WAV_SYNTH_AMP` | **1.0** | One synth = unit peak after shape normalize |
| `WAV_MEUM_AMP_REF` | MEUM−1 ≈ **0.19758073433** | Enters **only** the pathological clip threshold |
| Hard-clip threshold | `n_instruments · 3 · 1 / 0.19758073433…` | Beyond this, samples are hard-clipped |
| Live / mix scale | `buffer · (volume · WAV_MAX / peak)` | Scale buffer max into volume directly |

No soft-clip, slew, peak-floor, or tanh limiter on the amplitude path. Phase continuity (`_voice_phase_carry`) and Nyquist partial caps remain (correctness of Meum oscillators, not dynamics cosmetics).

## Meum effect residue bank
`meum_effect_residue(seed, label)` and `meum_effect_bank(seed, count)` map seed×label into independent cyclic residues — infinitely varied, non-redundant effect identities without lookup tables.

## Module interoperability (this pass)
- Amplitude constants + `meum_hard_scale_to_wav_max` are pure functions of stream / n / volume — **not** saved state; same composition fingerprint as before.
- `_voice_phase_carry` / any residual runtime caches remain non-persisted (derived from seed + render order).
- Save / load / export / game export still share `_canonical_fingerprint` inputs (seed, weight, FullWeight, BPM, base Hz, canonical toggles, step presence).
- UI layout and color keys unchanged in this amplitude pass.
- Patch Modular per-cable settings still dialog-local (not yet in `patch_connections` persistence) — same note as prior pass.

## Layout (2026 pass)
- **GLOBAL** panel region: seed / FullWeight / Full Unison, transport,
  **GLOBAL · COMPOSITION CANONICALS** (now positioned directly below the
  PLAYLIST button), global effects, global play patcher, LIVE DJ, and
  **GLOBAL monitors** (waveform · square scenograph · spectrum) + EXPORT.
- **Wave/Scope** and **Spectrum/Geometry** dropdowns now sit directly above
  the visualizer row they control, instead of several sections above it.
- **WAV / Video carrier import** controls (Load WAV Carrier / Load WAV-Video)
  now float directly above the left-hand oscilloscope pane. This freed space
  in the global controls row for a larger **Playlist Rows** label + spinbox.
- **Global Play Patcher** stays in its existing slot but its scroll area is
  now resizable with a much taller viewport floor, so its contents (script /
  domain / wire / apply controls) have real room to scroll.
- **Patch Modular** now scrolls and has real per-cable settings (depth,
  response curve, polarity, auto-gain-normalize) plus a live cable list you
  can remove/clear from, and a deterministic seed-based "Randomize Patch"
  button.
- **LOCAL** region: active-instrument editors (EDIT SYNTH / WRITE SCRIPT /
  PATCH MODULAR / CALC DOMAIN) and the step sequencer. Synth Editor / EDIT
  SYNTH and Patch Modular floating windows now open sized to fit their
  content and stay freely resizable rather than fighting a fixed cramped
  size against their internal scroll area.
- RANDOMIZE and PHASE-LOCK are recolored as one matched teal-cyan pair
  (both are "engine paints Playlist" operators). GOAVA has its own distinct
  amber/gold identity, since it's a different composition source
  (numerical-seed, not paint/randomize).
- Scenograph is a large **square**. Side meters are rectangles at the same
  height.
- LIVE DJ macros use short fixed labels: **GOAVA DJ** / **PKP BOOST** /
  **RAND PARAM**.

## Bug fixes (this pass)
- **Burst on every row, with or without Apply Algorithm** — the real primary
  cause, found after the first pass's fix (block-normalization smoothing)
  turned out not to be sufficient by itself. Each voice's phase was computed
  as `2π · cumsum(instantaneous_frequency) · dt`, which **restarts from 0 at
  the start of every single row**, for every voice, with no memory of where
  the previous row's phase ended. That is a hard phase discontinuity at
  every row boundary — an audible click/pop each row — completely
  independent of whether a Global Play Patcher algorithm is applied, which
  is exactly why it kept happening "without Apply Algorithm, often." Fixed
  by carrying each instrument's ending phase forward into the next row via
  a new persistent `self._voice_phase_carry` dict (stored mod 2π, same
  precision reasoning as the oscillator phase-wrap fix below).
- **Waveform damage concentrated in part of the material (~seed-dependent,
  not universal)** — harmonic and inharmonic partial counts (`n_harm`,
  `n_inh`) were derived purely from entropy/fold-depth, with no relationship
  to the voice's actual fundamental frequency or the sample rate. For
  higher-pitched voices, the higher partials (and the inharmonic partials,
  whose ratio climbs steeper than a plain harmonic multiple) routinely
  exceeded Nyquist (`sample_rate / 2`) and folded back as aliasing — audible
  as harsh, "damaged" distortion rather than the intended harmonic color.
  Because the fundamental is seed-derived, this only hit the fraction of
  voices whose seed happened to map to a high-enough pitch, which is why it
  read as damage in only part of the material rather than everywhere. Fixed
  by capping both partial counts to what actually fits under Nyquist for
  each voice's fundamental.
- **Burst-separation after Apply Algorithm (block-normalization jump)** —
  per-row/per-block voice normalization used to divide each block by its
  own instantaneous peak (`voice_raw / peak`), recomputed independently
  every row. Because entropy and harmonic content — and therefore peak —
  swing a lot row-to-row (especially once a Global Play Patcher algorithm
  is applied and raises voice variance), the normalization gain could jump
  sharply between adjacent blocks. Fixed by keeping a persistent,
  slew-rate-limited gain per instrument (`self._voice_norm_gain`) and
  ramping smoothly across each block instead of snapping to a new
  instantaneous gain every time. (This fix alone was not sufficient — see
  the phase-continuity fix above, which was the more fundamental cause.)
- **Harmonic drift over long sessions** — the master oscillator's phase
  accumulator only wrapped back into `[0, 2π)` once it exceeded 1e9 radians.
  A float64 keeps ~15-17 significant digits, so as phase approached the top
  of that range, the small per-sample increment began falling below what's
  representable at that magnitude — i.e. the phase accumulator quietly lost
  precision, which is exactly what reads as slow pitch/harmonic drift.
  Fixed by wrapping phase into `[0, 2π)` every sample (negligible cost, phase
  never grows large enough to lose precision).
- Two earlier envelope fixes (steps dying by mid-step; rows going silent
  after ~1-2τ) were confirmed still in place — they were not regressions.

## New features (this pass)
- **Deterministic Game Generator title word-bank** — titles used to be a
  fixed `"{Mood} {Genre} [{fingerprint}]"` template (72 possible shapes).
  Titles are now built from four independent seed-mixed word banks (epithet
  × noun × descriptor × optional flourish glyph), giving ~5.9M distinct
  title shapes while remaining 100% deterministic (same seed → same title
  every time) — directly serving the "unique / deterministic / non-redundant
  / infinitely varied" goal.
- **Multiplayer chat + switchable host/client role** — the exported game
  script's `Game` class now has `send_chat()` (works in any social mode) and
  `toggle_host_mode()`, which can flip a running session between host and
  client at any point (not just at launch). Console commands `/host`,
  `/client`, and `/chat <message>` are wired in during play.
- **Patch Modular per-cable settings** — depth, response curve (linear /
  exponential / logarithmic / S-curve / step-quantized), polarity
  (unipolar/bipolar/inverted), and an auto-gain-normalize toggle so summing
  more cables into one destination doesn't silently change its level — plus
  a deterministic "Randomize Patch" button seeded from the current project
  seed (same seed → same random patch, consistent with the project goal).

## Module interoperability check (asked after every pass)
Do all modules fill in with each other, and does save/load/export still
agree across all of them, after this pass's changes?
- **UI moves** (dropdown position, button position, import row position) are
  purely layout — they reference the same underlying widgets/attributes
  (`self.viz_mode_combo`, `self.spin_playlist_length`, `self.global_composition_group`,
  etc.), so no save/load/export path needed updating; state keys are
  unchanged.
- **Unison Blend default** changed a `QDoubleSpinBox` initial value only; the
  save/load key it writes to is unchanged.
- **Voice normalization fix** adds one new runtime-only dict
  (`self._voice_norm_gain`) that is never persisted — it's a smoothing cache,
  not composition state, so it does not affect save/load/export
  determinism (same seed still renders the same *composition*; only the
  live gain-smoothing path changed, which affects audio dynamics, not the
  canonical fingerprint inputs).
- **Row phase-continuity fix** adds one new runtime-only dict
  (`self._voice_phase_carry`), also never persisted for the same reason —
  it is derived, reproducible state (same seed → same phase trajectory),
  not new composition identity.
- **Nyquist-based partial capping** changes how many harmonic/inharmonic
  partials get rendered for high-pitched voices but does not change any
  save/load key — `n_harm`/`n_inh` were always runtime-computed, never
  stored.
- **Phase-wrap fix** changes internal oscillator state representation
  (`phase` now always in `[0, 2π)`) but not its audible meaning — output is
  unaffected because sin/cos are periodic in phase; nothing in save/load
  stores raw phase across sessions, so no format change was needed.
- **Game Generator titles** are derived purely from `(seed, genre, camera,
  topology, mood, fingerprint)`, all of which are already part of
  `GameIdentity` and already serialized via `export_game_files()` /
  `to_dict()`. No new save-format fields were needed — titles regenerate
  identically from existing saved identity data.
- **Patch Modular new settings** (depth/curve/polarity/normalize) are
  currently dialog-local state (not yet wired into `patch_connections`
  persistence) — flagged here explicitly rather than silently claimed as
  saved: if you want these to survive save/load or affect the Global Play
  Patcher's "wire" algorithm, that wiring is the next concrete step, not yet
  done in this pass.
- **Multiplayer chat/host-switch** lives in the generated game script
  template only (`videogame_engine.py`), which is regenerated fresh each
  export from `GameIdentity` — it doesn't touch the main app's save format.

## Features (carried over)
- **Full Unison Blend: ON/OFF** — ON locks ideal blend 1.0; OFF uses the
  spin (now defaulting to **0.55**).
- **Randomize Global Play Algorithm** — writes Script / Domain / Wire / Params
  from the shared Meum vocabulary and applies to the project.
- Seed randomizer includes the same scriptable parameter families.
- Canonical fingerprint (`id: …`) on the monitor status bar.
- Export audio: WAV, FLAC, OGG, AIFF, MP3, Opus, CAF + video + game script.
