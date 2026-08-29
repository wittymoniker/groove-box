# Groovebox — Complete V3.8.0

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
|---------|----------|
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

No soft-clip, slew, peak-floor, or tanh limiter on the amplitude path. Phase continuity (`_voice_phase_carry`) and Nyquist partial caps remain (correctness of Meum oscillators, not dynamics cosmetic).

## Meum effect residue bank
`meum_effect_residue(seed, label)` and `meum_effect_bank(seed, count)` map seed×label into independent cyclic residues — infinitely varied, non-redundant effect identities without lookup tables.

## Module interoperability (V3.8.0+)

### Fixed (V3.8.0)
- **Toggle state management**: Atomic `CompositionToggleState` ensures every toggle transition is deterministic and reproduces the same fingerprint across all uses (Randomizer, Phaselock, Live DJ, Apply Algorithm, Apply Composition).
- **GOAVA pitch bias**: Fixed by symmetrizing drive around unity (1.0 center) instead of always biasing upward. Modulation is now bipolar and DC-corrected, removing audible pitch drift on repeated toggles.
- **Consistency audit layer**: New `CompositionAudit` class validates that UI state, toggle state, saved state, and export state all agree. Detects stale fingerprints, UI sync mismatches, and parameter bounds violations.
- **Patch cable persistence** (new in 3.8.0): Per-cable settings (depth, curve, polarity, auto-normalize) now persist in `patch_connections` and save/load correctly.
- **Undo stack for toggles**: Track toggle history so multiple toggle sequences don't "get worse" — each state is stored and can be reverted.

### Still working correctly
- Amplitude constants + `meum_hard_scale_to_wav_max` are pure functions of stream / n / volume — **not** saved state; same composition fingerprint as before.
- `_voice_phase_carry` / any residual runtime caches remain non-persisted (derived from seed + render order).
- Save / load / export / game export still share `_canonical_fingerprint` inputs (seed, weight, FullWeight, BPM, base Hz, canonical toggles, step presence).
- UI layout and color keys unchanged.
- Patch Modular per-cable settings now in `patch_connections` persistence (previously dialog-local).

## Layout (2026 pass)
- **GLOBAL** panel region: seed / FullWeight / Full Unison, transport,
  **GLOBAL · COMPOSITION CANONICALS** (directly below PLAYLIST button), global effects, global play patcher, LIVE DJ, and
  **GLOBAL monitors** (waveform · square scenograph · spectrum) + EXPORT.
- **Wave/Scope** and **Spectrum/Geometry** dropdowns sit directly above
  the visualizer row they control.
- **WAV / Video carrier import** controls float directly above the left-hand oscilloscope pane.
- **Global Play Patcher** has a resizable scroll area with taller viewport.
- **Patch Modular** scrolls with real per-cable settings (depth, response curve, polarity, auto-gain-normalize) + deterministic "Randomize Patch" button.
- **LOCAL** region: active-instrument editors (EDIT SYNTH / WRITE SCRIPT / PATCH MODULAR / CALC DOMAIN) and step sequencer.
- RANDOMIZE and PHASE-LOCK recolored as teal-cyan pair (both "paint Playlist" operators).
- GOAVA has distinct amber/gold identity.
- Scenograph is a large **square**. Side meters are rectangles.
- LIVE DJ macros: **GOAVA DJ** / **PKP BOOST** / **RAND PARAM** (short fixed labels).

## Bug fixes (V3.8.0 — new in this pass)
- **Toggle state inconsistency**: Toggles no longer leave stale memory. Each toggle (Randomizer, Phaselock, GOAVA DJ, Random Parametric, Apply Algorithm, Apply Composition) atomically invalidates runtime caches and recomputes the fingerprint. Same toggle sequence always produces the same result (order-independent).
- **GOAVA upward pitch tendency**: Drive was biased upward (`1 + 2.8 * (0.25 + 0.75 * ratio)`). Now centered at 1.0 with symmetric ±1.4x modulation. Modulation is bipolar and DC-corrected, eliminating audible pitch drift.
- **Fingerprint staleness on export**: Export now uses the current fingerprint, not a cached old one. Audit detects and warns if export fingerprint diverges from toggle state.
- **Patch cable settings lost on save/load**: Depth, curve, polarity, and auto-normalize now persist in `patch_connections`.

## New features (V3.8.0)
- **Atomic toggle state** (`CompositionToggleState`): Every toggle is part of a single, hashable, immutable state object. No toggle can corrupt another.
- **Composition audit layer** (`CompositionAudit`): Validates consistency between UI, toggle state, saved state, and exports. Call `audit()` before save to catch issues early.
- **Undo stack** for toggles: Press Ctrl+Z or click Undo to revert toggle history without affecting the audio/composition.
- **Deterministic patch randomizer**: "Randomize Patch" button generates repeatable patches seeded from the project seed.

## Credits / collaboration (V3.8.0)

**Core architecture & original design**: project author

**Implementation assistance**:
- *Realtime audio, additive engines, domain partitions, bootstrap/simplify, Help system*: Grok (xAI), Gemini (Google), Claude (Anthropic), ChatGPT (OpenAI), Mistral.ai, Cursor Grok 4.6
- *V3.8.0 toggle state design, atomic composition state, GOAVA pitch bias fix, consistency audit layer, patch persistence, undo stack*: **GitHub Copilot** (Claude Sonnet via Cursor)

## Features (carried over)
- **Full Unison Blend: ON/OFF** — ON locks ideal blend 1.0; OFF uses the
  spin (defaulting to **0.55**).
- **Randomize Global Play Algorithm** — writes Script / Domain / Wire / Params
  from the shared Meum vocabulary and applies to the project.
- Seed randomizer includes the same scriptable parameter families.
- Canonical fingerprint (`id: …`) on the monitor status bar.
- Export audio: WAV, FLAC, OGG, AIFF, MP3, Opus, CAF + video + game script.
