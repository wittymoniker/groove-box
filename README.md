# EQR Groovebox — Mathematician's / Scientist's Groovebox

Mathematical specification for maximum initial harmonic diversity. Simple pads-and-play projects and complex multi-engine compositions use the same model.

**Credits:** core EQR design — project author; implementation assistance — Grok (xAI), Gemini (Google), Claude (Anthropic), and ChatGPT (OpenAI).

---

## Requirements

- Python 3.10+
- PyQt6
- NumPy
- Optional: `sounddevice` (live audio), `scipy` (WAV I/O), `ffmpeg` (video export)

```bash
pip install PyQt6 numpy sounddevice scipy
python groovebox.py
```

---

## Quick start

1. Set **BPM** and sequence length.
2. Select an instrument; toggle PKP pads (cyan = on).
3. Optional: enter a **Seed** (blank / `0` / `0.0` = no seed), or click **🎲 Random Seed Script**.
4. Optional: open the Playlist and paint operators into the timeline.
5. Press **▶ PLAY Audiovisual Track** or export WAV / video.
6. Optional: enable **Euclidean Phase-Lock** and/or **Seeded Live Randomizer** to additive-fill empty structure around your carrier.

Design pillars:

1. User data is the **carrier wave** — engines add around it; they do not wipe it.
2. Seeds (irrationals: π, e, Meum ≈ 1.1975807343, …) are geometric anchors.
3. Empty slots are for convergent harmonic fill, not noise dumps.
4. Only inputs with **net effect** on the playlist timeline are protected user data.

---

## Seed field — full scripting

The global seed is a **scrollable script panel**, not a single number box. It drives composition RNG, per-instrument assignment, GOAVA numerical events, domain bias, and (when time-varying) render-time modulation.

### Random Seed button

**🎲 Random Seed Script** sits directly above the seed field. Each click inserts a new script that has been **validated** to evaluate cleanly for composition state, several time samples, and all instrument indices. Invalid candidates are never inserted.

### Composition vs time-axis evaluation

| API | When | `t` | Purpose |
|-----|------|-----|---------|
| `get_numeric_seed()` / `get_seed_values()` | UI, paint, engines | `0.0` | Deterministic composition seed |
| `get_seed_value_for_index(i)` | Per instrument / row | `0.0` (or render `t`) | Instrument `i` → `list[i % n]` |
| `evaluate_seed_expression_at_time(script, t)` | Play / Export DSP | real time | Time-varying modulation |

List scripts assign **real evaluated numbers** to every instrument **and every
sequence** via `get_seed_value_for_index(i)` / `_instrument_seed_int(i, sequence_id=…)`.
Euclidean Phase-Lock, Seeded Randomizer, canonical reconcile, and program
bootstrap iterate the full sequence bank (`_iter_sequence_mems`), not only the
currently selected sequence. Sequence slots rotate through list components so
`100, 200, 300, 400` maps cleanly across instruments and sequences.
Instrument **name hashes are never the primary seed**. Hash/byte tokens are only
a last resort when nothing in the field can be evaluated.

### Accepted forms

**Plain number**
```text
432
123.45
(7)
```

**Math** (constants + functions; `t` available)
```text
sin(t) * 100 + 50
MEUM * 432
clamp(sin(t * MEUM) * 200, -100, 100)
lerp(100, 800, 0.5 + 0.5 * sin(t))
choose(100, 200, 300, 400, floor(abs(t * 2)))
```

**Conditionals**
```text
1 if sin(t) >= -0.5 else 2
if(sin(t)>=-0.5) 1 elif 2
if(sin(t * MEUM) * cos(t) > 0) 432 elif 216
```

**Return / multiline**
```text
return sin(t * MEUM) * 100 + 50

# comment
return 1 if t < 1 else 2
```

**Comma / newline lists** — each top-level part is evaluated; function-call commas inside `()` are preserved:
```text
1, 2, 3, 5, 8
100, 200, MEUM*100, 50
lerp(100, 200, 0.5), lerp(300, 400, 0.25)
```

Instrument 0 receives the first value, instrument 1 the second, and so on (wrapping).

### Available names

| Kind | Names |
|------|--------|
| Functions | `sin` `cos` `tan` … `clamp` `lerp` `choose` · **`isn` `ics` `isn_inv`/`arcisn` `ics_inv`/`arcics`** · **`P` `E` `D` `tensor_z` `tensor_rel`** |

| Constants | `pi` `e` `tau` `PHI` `MEUM` `MEUM_NORM` `MEUM_INV` `MEUM_SQ` `MEUM_LOG2` `SILVER` `SQRT2` `SQRT3` |
| Variables | `t` (time), `x` (= `t`), `y`, `z` |

### File carriers (WAV / video) and seed scripts

Loading a WAV or video carrier (or a saved project) refreshes the seed
environment for **every instrument**:

- `carrier_present`, `carrier_rms`, `carrier_peak` update in seed scripts
- List seeds re-assign `list[i % n]` across the ensemble
- Active canonical engines rebuild against the new carrier
- Convolve-fit depth is scaled per instrument from the evaluated seed
- Carrier mix gain responds gently to the seed field mean

Scripts may branch on carrier state, e.g.:

```text
if(carrier_present) 432 elif 216
100, 200, 300, 400
```

### Examples

```text
if(sin(t * MEUM) >= 0) 432 elif 216
return lerp(110, 880, 0.5 + 0.5 * sin(t * 0.25))
64, 96, 128, 160, 192
clamp(exp(sin(t)) * MEUM * 100, 20, 2000)
100, 200, 300, 400
```

---

## Live engines (toggles)

| Control | Role |
|---------|------|
| Euclidean Phase-Lock | Additive Euclidean fill; preserves user steps |
| Seeded Live Randomizer | Seed-stable harmonic randomization around the carrier |
| Phase-Lock / Local Randomize | Local context engines on the active instrument |
| GOAVA | Engine-owned numerical composition from the seed list |
| Global Playlist | Timeline drives which operators sound per row |

Engines are **additive**: they fill empty structure and do not erase net-effect user data (unless Canonical Overwrite is explicitly enabled).

---

## Playlist

Unquantized global playlist with columns for time, operator identity, script/domain/synth/patch tags, velocity, automation, direction, multi-seq, coverage, blend partner, GOAVA sequence, and paint metadata.

- Paint operators into rows; coverage/blend enables virtual Unison overlap.
- Optional snap-to-grid vs free time base.
- Playlist length is resizable; user rows are preserved across resize.

---

## Per-instrument panels

- **Synth rack** — morph, harmonic frequency, chaos, fold depth, harmonic lattice  
- **Instrument script** — per-operator code memory  
- **Domain equations** — partitionable time/space multivariate equations  
- **Modular patch bay** — operator routing  

Optional **Edit panels per sequence** stores synth/script/domain/patch overrides per sequence slot.

---

## Transport & export

- **Play / Pause / Resume / Stop** over the rendered audiovisual buffer (`sounddevice`)
- **Export mixdown** → WAV  
- **Export video** → MP4 / WebM / AVI (requires `ffmpeg`); pure Meum scenograph frames, optional source-video blend  
- Monitors: waveform oscilloscope, FFT spectrum, Meum 2.5D/3D scenograph (drag to orbit)

---

## Meum constant

```text
M  = 1.19758073433…   (MEUM)
```

Used as a geometric invariant for spacing, UI tokens, spectral scaling, and scenograph calculus — not as an arbitrary percentage knob.

---

## Project save / load

Use **Save Project** / **Load Project** to snapshot seed text, playlist, sequencer banks, instrument parameters, and engine state.

---

## In-app help

Press **❓ README / Help** in the main window for the full guide (philosophy, bootstrap rules, domain syntax, GOAVA, workflow). This `README.md` mirrors the same seed-scripting and quick-start material for offline reading.

---

## Disclaimer

Advanced, experimental instrument. Pads + Play work immediately; domain equations and deep scripting are mathematician/scientist-oriented. Not a full commercial DAW replacement.
