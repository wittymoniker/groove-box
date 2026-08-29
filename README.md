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
- **Master-FX separation — exactly three effects, applied on the master
  tail only.** Fractallizer (spectral fractal resonator), EQR (tensor), and
  PKP (tempo-locked amplitude envelope) are the only audio effects, and they
  are applied on the master bus after the unison canonical engines. All
  per-voice EQR and PKP coloring was removed from the canonical voice stage
  (voice stage keeps only the neutral decay floor the per-synth Harmonic
  Lattice needs), so the effect sliders can never factor into the canonical
  fingerprint or the unison engines. PKP Decay now defines the per-note
  envelope binding with the follower always on: hold = step × seq_len^(2d−1),
  so 0.5 = normal 1:1 note-per-step envelope (hold = 1 step), 1 = hold spans
  the whole sequence length, 0 = hold is (1 step)/(sequence length); every
  note also always sweeps ~1 note duration before and after. PKP Decay still
  damps the master PKP swing too (default 0.5 → 0.2925 swing). No additional
  Nyquist-domain processors were added — frequency-domain work is confined
  to the one sanctioned spectral effect above.
- **Export menu is now exactly 3 × 3.** Audio only (WAV / FLAC / MP3),
  video+audio (MP4 / WebM / AVI), video only (MP4 / WebM / AVI).
- **Video-game export is a single dropdown option that packages a .zip** —
  deterministic game script + identity JSON + `launch_windows.bat` /
  `launch_macos.command` / `launch_linux.sh`, with unix executable bits
  preserved inside the archive. The Play dialog now also shows the full
  world coordinates: objective, difficulty, level type, sigil count, and
  world fingerprint.
- **Exported game scenes are instrument-trigger driven (zero RNG).** The
  generated script's LCG `SeedRNG` stream was removed entirely. Scene layers
  are now `TriggerSculptor` instruments mirroring the app's
  DeterministicTriggerSculptor closed-form: per-instrument density/phase
  residues plus a `sin`-thresholded step mask decide when each object fires,
  and every appearance/orbit/collectible is closed-form f(seed, i, beat)
  MEUM-residue calculus. `grep random` in a generated game finds nothing
  but a comment.
- **Semantic role theme.** Every control is painted BY FUNCTION via shared
  object-name rules in the app stylesheet, with one consistent decoration
  pattern: green = transport/play, red/pink = stop/danger/clear, cyan =
  export/playlist, blue = canonical engines, violet = deterministic
  randomizers, magenta = video game, amber = media/import/protect, teal =
  save/load + local instrument editors. Group boxes get matching accent
  borders and tinted titles.
- **Save/Load unison pass-through (project v3.7.7).** Save and load are the
  two halves of one round-trip over the exact inputs the unison engine reads.
  This pass closed every asymmetry: the euclidean live-lock and seeded
  randomizer toggles now ride the save doc (previously they silently reset
  to OFF, changing the canonical fingerprint), `mode_combo`/`viz_mode_combo`
  are saved as {index, text} and restored by text, the per-sequence editing
  checkbox is persisted, the WAV/video carrier is re-loaded from its saved
  path (so audio and video exports see identical reference material after
  load), and all UI-state restoration blocks signals so BPM/synth-count
  spins can't double-process during load. Round-trip verified: canonical
  fingerprint and engine mask are bit-identical before save and after load.
- **Code comments now trace the unison contract.** `_project_snapshot`,
  `load_project_dialog`, `_ensure_perfect_unison`, `_render_mixdown_buffer`,
  and the save/load/export suite carry comments explaining exactly how each
  piece passes state along — and where the three master effects deliberately
  sit outside the canonical engines.

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
- Export audio: WAV / FLAC / MP3, video+audio and video-only each in MP4 /
  WebM / AVI, plus video-game `.zip` package (script + JSON + 3 OS launchers).

## Credits
Core architecture & original EQR design by the project author. Implementation
assistance from Grok (xAI), Gemini (Google), Claude (Anthropic), ChatGPT (OpenAI),
Mistral.ai (Mistral), Meta AI (Meta), GitHub Copilot (GitHub), and Cursor Grok 4.6
(polyphony, unison memory, visualizer). Maintenance + level-up fixes by
opencode (anomalyco).

## Maintenance pass (dedup + wiring)
- **Duplicate toggle handlers removed** — `MathematiciansGrooveboxApp` carried two
  copies each of `_on_goava_toggled`, `_randomize_local_context`,
  `_phase_lock_local_context`, `_on_euclidean_live_toggled`,
  `_on_seeded_live_toggled` (~200 lines). The earlier copies were dead code
  silently clobbered by the later "perfect unison" versions; the dead copies
  are now gone so the active toggle behavior is unambiguous.
- **composition_state.py is now importable and correct** — the "new
  unimplemented module" actually failed at import (`NameError` on module scope,
  duplicate `CompositionToggleState`, missing `math`/`field`/`List` imports).
  It imports cleanly now, exposes a single immutable `CompositionToggleState`,
  and the loose module-level pseudo-methods are a proper
  `CompositionToggleMixin` (attach and call `set_composition_toggle`).
- **composition_state.py wired into groovebox.py** — the app maintains an
  order-independent `CompositionToggleState` summary
  (`_sync_composition_toggle_state`) and folds its digest into the canonical
  fingerprint together with the full engine vector (now including euclidean /
  seeded live engines). Same active set → same id regardless of toggle order.
- **GOAVA upward pitch bias fixed** — `goava_get_note()` is non-negative by
  construction, so every GOAVA note sat above the base frequency (measured
  +14…+28 semitone mean across seeds). `goava_frequency` now DC-centers the
  scalar against the set mean, so pitch lands symmetrically above/below base
  (mean ≈ 0 semitones, verified) while staying fully seed-deterministic.
- **UI layout stability while playing** — the Play button previously changed
  width with its PLAY/PAUSE/RESUME text, reflowing the whole transport row and
  visibly shifting widget sizes when a track started. The button now has a
  fixed width, and the monitor row (square scenograph + side meters) no longer
  recomputes its square side from window bounds during playback, so widget
  relative sizes stay put while a track plays.
- **Global Composition Randomizer engaged color** — once clicked, the
  "🎲 Randomize Global Play Algorithm" button takes a persistent green
  engaged style so a rewritten global play algorithm is visible at a glance.
