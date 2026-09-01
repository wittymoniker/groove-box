# Groovebox — Complete V1

## Goal
Groovebox is a deterministic audiovisual composition system built around a shared mathematical state. The same composition state drives audio, live visualization, video export, and generated software/game packages.

Design pillars:
1. **Deterministic:** the same seed and composition inputs reproduce the same canonical state.
2. **Order-independent:** canonical engine activation is reconciled from state, not activation order.
3. **Non-destructive:** user-authored composition remains the carrier; canonical engines fill or transform available structure without silently replacing protected material.
4. **Unified:** audio, visual, video, and game outputs derive from the same composition fingerprint and phase/harmonic vocabulary.
5. **Self-describing visuals:** every live instrument owns exactly one visual object whose geometry, motion, color, fade, and harmonic detail are derived from that instrument's live composition record.

## Dependencies (all platforms)

**Python packages (pip)** — required on every OS:

| Package | Purpose |
|---|---|
| `PyQt6` | UI |
| `numpy` | DSP / buffers |
| `scipy` | WAV I/O helpers, signal utilities |
| `sounddevice` | Real-time audio I/O |
| `Pillow` | Frame export (PNG) for video |

**System tools**

| Tool | Purpose |
|---|---|
| **Python 3.9+** (3.10–3.12 recommended) | Runtime |
| **ffmpeg** + **ffprobe** (full build with encoders) | Video/audio export (mp4/webm/avi, mp3/flac/…) |
| PortAudio / ALSA / CoreAudio (via sounddevice) | Playback |

### One-shot installers (preferred)

```bash
# Linux — auto-detects Fedora vs Ubuntu/Debian
./install_deps_linux.sh
# or force a family:
./install_deps_linux.sh --fedora
./install_deps_linux.sh --ubuntu

# macOS (Homebrew + pip)
./install_deps_macos.sh

# Windows (PowerShell; uses winget when available)
./install_deps_windows.ps1
```

These scripts install the pip packages above **and** a usable ffmpeg, then verify imports.

### Manual install

**Ubuntu / Debian**
```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv python3-dev build-essential \
  ffmpeg libasound2-dev portaudio19-dev
python3 -m pip install --upgrade pip
python3 -m pip install numpy scipy PyQt6 sounddevice Pillow
```

**Fedora**
```bash
# Full ffmpeg codecs come from RPM Fusion
sudo dnf install -y \
  https://download1.rpmfusion.org/free/fedora/rpmfusion-free-release-$(rpm -E %fedora).noarch.rpm \
  https://download1.rpmfusion.org/nonfree/fedora/rpmfusion-nonfree-release-$(rpm -E %fedora).noarch.rpm
sudo dnf install -y python3 python3-pip python3-devel gcc gcc-c++ \
  ffmpeg ffmpeg-libs alsa-lib-devel portaudio-devel
python3 -m pip install --upgrade pip
python3 -m pip install numpy scipy PyQt6 sounddevice Pillow
```

**macOS**
```bash
brew install python ffmpeg portaudio
python3 -m pip install --upgrade pip
python3 -m pip install numpy scipy PyQt6 sounddevice Pillow
```

**Windows**
```powershell
# Python 3.12 from python.org or:
winget install Python.Python.3.12
winget install Gyan.FFmpeg
python -m pip install --upgrade pip
python -m pip install numpy scipy PyQt6 sounddevice Pillow
```

Optional: place static `ffmpeg` / `ffprobe` binaries in `./bin/` next to `groovebox.py` (the app checks there first).

### Verify
```bash
python3 -c "import numpy, scipy, PyQt6.QtCore, sounddevice, PIL; print('python deps OK')"
ffmpeg -hide_banner -version | head -1
```

## Run
```bash
./launch_desktop.sh
# or: ./launch_mobile.sh
# or: python3 groovebox.py
```

## Defaults
| Control | Default |
|---|---|
| BPM | **120** |
| Base Global Frequency | **432 Hz** |
| Seed Weight | **0.72** |
| FullWeight Seed | **ON** |
| Full Unison Blend | **OFF**; blend control defaults to **0.55** |
| Meum lattice | **MEUM ≈ 1.19758…** |

## Open-World Sandbox Contract

Games classified as `open_world` or `sandbox` are free-roaming by design. The player
controls movement and look; the world never auto-spins or traps the player in a sigil,
activity, or region. Sigils, hazards, portals, NPCs, resources, and rare activities
are optional world content rather than progression cages.

The world is region-based and sandboxable. Each procedural Loom region has persistent
local state for placed objects, removed objects, notes, and visit count. Useful commands
inside the game chat/console include:

```text
/sandbox              inspect the current region's editable state
/build crate My Box  place a lightweight persistent sandbox object
/remove               remove the most recently placed local object
/note <text>          attach a note to the current region
/region               alias for /sandbox
```

The GUI chat box is also the game console: slash commands are routed through the same
command parser as the CLI, while ordinary text remains chat. This keeps local play and
multiplayer chat on the same interaction path.

## Quick Start
1. Set BPM and sequence length.
2. Select an instrument and program its pads/sequence.
3. Leave Seed blank/0 for the no-seed mode, or enter a non-zero seed.
4. Use Playlist to arrange operators over time.
5. Press **Play** or export audio/video.
6. Optionally use Euclidean/Phase-Lock, Seeded Harmonic Randomizer, Domain Equations, Patch Modular, or GOAVA.
7. Use **Global Play** to author Script/Domain/Wire algorithms (Randomize is authoring-only; **Apply Algo to Master Mix** broadcasts). See *Global Play Panel* below.

## Global Play Panel — algorithms, params, and launched windows

The **Global Play** group on the main window is the project-level algorithm layer. It does **not** overwrite the seed field or per-instrument seed scripts. Authored algorithm text lives in `global_algo_state` until you **apply** it to the master mix / ensemble.

### Layout (main panel)

| Control | Role |
|---|---|
| **🎲 Randomize Global Play Algorithm** | Fills Script, Domain, Wire, and amount params from the Meum/PED vocabulary. **Authoring only** — does **not** apply to the ensemble until you press Apply. |
| **▶ Apply Algo to Master Mix** | Toggle. When ON, script / domain / wire (as enabled in params) broadcast to the ensemble. When OFF, written music/shapes are left alone. Undoable. |
| **Script Algo** (multi-line) | Project-level script over `t`, `MEUM`, `PHI`, `seed`, instrument `name` / `i`. Typical form: `def global_script(t, name, i): return …` |
| **Domain Algo** (single line) | Equation string, e.g. `sin(t * MEUM) + cos(t * PHI)`. Hints update live (sin/cos → phase, log/exp → scale, domain → transmutor). |
| **Wire Algo** button | Opens the **Global Wire Algo** window — routing matrix from detectors to targets. |
| **Algo Params** button | Opens the **Global Algo Params** window — extended convolution / enable flags. |
| **Mix / Script / Domain / Wire amount** sliders | 0–100%. Relative wet amounts for each layer when Apply is on. |

### Launched windows (`Wire Algo` / `Algo Params`, and optional script/domain editors)

Four panel kinds share the same chrome (translucent + math décor). Edits write only into `global_algo_state`:

1. **Global Script Algo** — full multi-line editor for the script body (same language as the seed field: `sin`/`cos`/`isn`/`ics`, `MEUM`, `t`, conditionals, `return`).
2. **Global Domain Algo** — domain equation editor + hints.
3. **Global Wire Algo** — list of wires `{source, target, amount}`:
   - **Detectors (sources):** `phase`, `energy`, `spectrum`, `goava`, `euclidean`, `seed`, `bpm`, `pair`
   - **Targets:** `master_mix`, `fractallizer`, `eqr`, `pkp`, `ensemble`, `scenograph`, `domain`, `unison`
4. **Global Algo Params** — structured params, including:
   - `mix` — overall wet level (default ~0.35)
   - `enable_script` / `enable_domain` / `enable_wire` — per-layer gates
   - `script_amount` / `domain_amount` / `wire_amount` — same as the main-panel sliders

Close a panel; state remains. Re-open raises the existing window if still alive.

### Scripting guide (Script Algo)

Same expression environment as seed scripts (Operator Theory routes `sin`/`cos`/… through the equivalence kernel when OT is on):

```text
# Global script algo
def global_script(t, name, i):
    v = isn(t * MEUM) * 0.4 + ics(t * PHI) * 0.3
    return v * 0.35
```

Also accepted: bare expressions, `if/elif` shorthands, `return` lines. Arguments:

| Name | Meaning |
|---|---|
| `t` | Time (seconds / phase axis used by the renderer) |
| `name` | Instrument name string when applied per voice |
| `i` | Instrument index |

**Domain Algo** examples:

```text
sin(t * MEUM) * 0.35 + cos(t * PHI) * 0.65
MEUM_NORM * sin(t * 0.5) + (1 - MEUM_NORM) * cos(t * 0.3)
isn(sin(t * MEUM)) * cos(t * PHI)
```

### Apply semantics (important)

- **Randomize** = write fields only (`apply_enabled = False`). Music/shapes unchanged.
- **Apply ON** = push enabled layers to the ensemble (script/domain/wire as gated by params).
- **Apply OFF** = stop broadcasting; prior user composition remains the carrier where protected.
- Algorithm state is **userdata** (saved in the project document) and is **undoable** (Ctrl+Z).
- Global Play never writes the **seed** field; seed stays user-controlled.

### Workflow

1. Optionally **Randomize** to get a starting script/domain/wire set, or type your own.
2. Tweak **Mix / Script / Domain / Wire** amounts.
3. Open **Wire Algo** / **Algo Params** if you need routing or enable flags.
4. Press **▶ Apply Algo to Master Mix** to hear the overlay.
5. Toggle Apply off or Undo to revert the ensemble overlay.

## Per-instrument synth geometry
Each instrument has five live patch parameters:
- **Morph Rate / Speed**
- **Harmonic Frequency**
- **Feedback / Chaos Blend**
- **Recursive Fold Depth**
- **Harmonic Lattice**

The visual engine reads these five values directly from `instrument_param_state`, alongside the instrument's canonical phase/frequency identity, sequence length/steps/amplitude/pitch statistics, playlist participation, seed, and active canonical engines. The same state vector is reduced through one `InstrumentVisualObject` route.

The object is dimension-agnostic: its deterministic identity selects a 1D filament, 2D closed surface, or 3D projected shell. The selection is stable for the instrument and composition; it is not rerolled frame-to-frame. All dimensions share the same harmonic contour and phase driver.

**Instrument count is the graphic count.** There is no independent graphical-object number control. With 2 instruments there are 2 canonical visual objects; with 64 there are 64. The construction law does not use ensemble size for an object's identity placement, so the same instrument identity follows the same visual law when the ensemble grows or shrinks.

### Visual motion and color
Visuals use continuous phase motion, harmonic breathing, energy response, and non-zero fade floors so active objects remain visible while continuously moving and fading. Color is continuous rather than a small fixed palette: instrument identity, harmonic frequency, harmonic lattice, phase, chaos, entropy, and live energy contribute to hue/saturation/value. GOAVA retains its own second graphical class because its identity is an irrational numerical stream rather than an ordinary instrument voice.

## Composition ↔ output contract
The three output families are generated from the same composition identity:

- **Music:** canonical voices, live patch state, sequence state, master effects, and GOAVA feed the audio path.
- **Video / music-video:** the video synthesizer follows the same canonical instrument state and live audio analysis; exported video can carry the rendered audio.
- **Video-game / software package:** `videogame_engine.py` derives a deterministic `GameIdentity`, asset manifest, software kind, input contract, music bed, visual scene, UI, and replay/telemetry contract from the same composition fingerprint.

The game generator supports a safe lattice of software kinds including videogame, network tool, utility, simulator, media player, radio study toolkit, data visualization, chat server, protocol lab, instrument lab, office suite, file manager, terminal lab, offline browser shell, and IDE-lite. Each kind has an explicit input schema; safety-limited kinds are simulation-only and never execute an arbitrary shell or live RF transmission.

Every exported game package includes its identity, input contract, sound/visual/UI contract, asset manifest, software-kind coverage proof, launchers, and play guide. In-app Play uses the same `install_game()` path as exported packages and caches generated assets under a fingerprinted temporary directory, so the first generation and subsequent reuse share one deterministic source.

## Deterministic Meum Video Render Contract (2026-09-01)

The offline video renderer is intentionally separated from the live viewer state.
Each export creates a fresh `VideoSynthEngine`, binds it to the same canonical project
source, and renders every frame at the explicit time `frame_index / fps`. Repainting the
viewer before export therefore cannot change the exported visual identity.

The scenograph raster helpers treat their caller-provided alpha as authoritative. The
previous global 1.65x line/dot density boost was removed because it saturated translucent
lattice marks and buried camera/fractal structure. Camera fitting is now uniform in X/Y,
which preserves projected aspect changes and makes the deterministic yaw/pitch/roll path
visually legible. A restrained world-axis cue uses the same camera transform as the scene.

GOAVA video geometry re-evaluates the supplied numeric seed list at the current render
time and uses the same time-indexed GOAVA event construction as the composition layer.
Cached activation-time events remain available for normal UI state, but they no longer
freeze the offline/live scenograph on one frequency. GOAVA frequency values are not
artificially floor-clamped in the visual path; only non-finite/non-positive failures use
a deterministic 432 Hz fallback.

For throughput, frame pixels are streamed as deterministic RGB24 directly into ffmpeg
for each recoverable encoded part. This removes per-frame PNG staging while preserving
the 16-part crash/recovery boundary. The completed parts are still concatenated/muxed
atomically into the final container.

## Export
The export menu is organized as:
- **Audio only:** WAV / FLAC / MP3
- **Video + audio:** MP4 / WebM / AVI
- **Video only:** MP4 / WebM / AVI
- **Video-game:** deterministic `.zip` software/game package

## Save / Load
Save/load preserves the composition inputs needed by canonical audio and visual generation, including engine toggles, visualization state, instrument parameters, sequence state, and imported carrier references where supported. The canonical fingerprint is the primary round-trip identity check.

## Seed rules
- Blank, `0`, and `0.0` mean no seed.
- Any non-zero numeric value is a geometric anchor.
- Scriptable seed input may produce a list of evaluated values; those values can reshape composition and visualization deterministically.
- Same evaluated seed/composition state produces the same canonical identity.

## Credits
Core architecture & original EQR design by the project author.
Grok (xAI), Gemini (Google), Claude (Anthropic), ChatGPT (OpenAI), Mistral.ai (Mistral), Meta AI (Meta), GitHub Copilot (GitHub), Cursor Grok 4.6, and opencode (anomalyco).

## Fractallizer — formulas and fractal repetition of the audio signal

The audio-signal Fractallizer is a **global frequency-domain fractal
resonator**. It never wraps or folds the waveform in the time domain; it
operates on the spectral **magnitude** of the Hann-windowed FFT while
preserving the input **phase exactly** at every bin, so all fractal/
subharmonic detail stays on-phase with the canonical source (no grit, no
aliased sidebands, no hard harmonic creation by a waveshaper).

**Stage 1 — spectral warping (the fractal repetition).**
With `X = rfft(x·Hann)`, magnitude `M = |X|`, phase `φ = ∠X`, the magnitude
is repeated across four log-frequency scale copies:

```
g          = max(1.05, gamma)                      (gamma 1.5 + 2·MEUM_NORM ≈ 1.83)
scales     = (1/g, 1, g, g²)
M_sc       = interp(clip(safe·s, 1, Kmax), bins, M)   for each s in scales
new_M      = Σ_s w_s · M_sc,   w = (0.20, 0.35, 0.30, 0.15)
safe       = max(bins, 1)                          (DC/near-DC singularity guard)
```

So the fractal repetition is a **magnitude self-convolution across
log-frequency**: each bin re-reads its own spectrum shifted down by one
octave-step (`1/g`), unshifted (`1`), up one (`g`), and up two (`g²`)
Meum-tuned gamma steps, blended by fixed weights. A source peak therefore
reproduces itself at `g` and `g²` above and at `1/g` below — the
"repeats a time-invariant fractal wave" behavior (time-invariant because
the scale map is fixed per render, never a function of the sample index
except through the envelope below).

**Stage 2 — smooth spectral detail (fractal fine-grain).**
`detail_amount = 0.10·activation`:

```
logmag     = log(1 + M)
smooth     = (1/9)-tap moving average of logmag
residual   = logmag − smooth                       (fine spectral ripple)
taper      = sqrt(freescale bins)                  (more detail up high, tapering pre-Nyquist)
detail     = exp(log(1 + max(smooth + detail_amount·residual·taper, −20, 20)))
new_M      = 0.88·new_M + 0.12·detail
new_M[0]   = M[0]                                  (DC anchored)
```

The detail term is a smooth, high-resolution spectral residual — it follows
the source envelope and cannot fabricate hard harmonics on its own.

**Stage 3 — phase reconstruction and amplitude normalization.**

```
y_spec     = new_M·e^{j·φ}
y          = irfft(y_spec, n)
y          *= peak_in / peak_out                   (undo the Hann energy change)
```

**Stage 4 — tempo-locked envelope and the 50% wet rule.**

The fractal detail is extracted as the difference signal and enveloped by
the same tempo-locked plane the PKP/EQR masters use (`0.55 + swing·sin(2π·t·bpm/60)`,
swing damped by PKP Decay), then crossfaded so the effect never exceeds a
**50% mix at 100% activation**:

```
detail     = (fractal − dry) · clip(pkp_env, 0, 1.5)
out        = dry + (0.5·activation)·detail
```

The `HarmonicLattice` per-synth stage is the same pipeline with gamma
`max(1.15, gamma_fixed)`, weights `(0.30, 0.45, 0.25, 0.00)` and
`detail_amount = 0.07·activation` — the lighter, harmonic-only sibling.

## Equation-of-Reality (EQR) reality tensor — formulas

The EQR effect is the book's reality tensor (p.78, "Theoretical Equation
Parameters for Graphing or Predicting a reality tensor"). Three levels are
evaluated for every harmonic context along the wave (each context = the
current sample, its ±window neighbours at distances `d_n`, and the running
time fraction `t`), producing a **single-point z-value** `Z = P·E + D`:

```
I      = 134964355                          (finite infinity, p.68/p.79)
isn(x) = sin(x)·MEUM_NORM + sin(x·MEUM)·(1 − MEUM_NORM)     (Meum-normalized, MEUM_NORM = (M−1)/M)
d_n    = |sample − neighbour_n| + ε          (point-to-point distance)
t      = i / (N − 1)                         (time fraction along the wave)

P = Σ_{n=0}^{k} k·isn⁻¹( (isn(d_n) + isn(t)) / 2 )      structure / evolution
E = Σ_{n=0}^{k} k·isn(θ_n)/d_n,   θ_n = neighbour amplitude   energy/direction
D = Σ_{n=0}^{k} k·isn⁻¹( isn(θ_n)·E / (I·P) )             determination of direction

Z = P·E + D
```

The components are evaluated on a sparse control grid (≤ 64 points), P/E
are mean-normalized per render (scale-invariant structural relation), the
z-values are followed through a **time-predictive envelope** (forward
maximum window, so EQR anticipates transients instead of lagging them) and
crossfaded against dry with the **up-to-50%-at-100%** rule:

```
P_n = P / mean(|P|),  E_n = E / mean(|E|)
rel = clip(Z / mean(Z), 0.25, 2.5)
env = forward-max(rel) with 0.85/0.15 release
out = (1 − 0.5·act)·dry + 0.5·act · dry·(0.65 + 0.35·tanh(env))·pkp_env
```

The unconditional "PED" reality tint on the final bus is the same tensor
evaluated on the pre-clip buffer at `1 + 0.14·tanh(rel − 1)`.

**The three master effects share one envelope-follow doctrine.** EQR's
follow envelope is time-predictive: a forward maximum window anticipates
upcoming transients and releases at 0.85/0.15, so the reality-tensor z-value
guides the shape *ahead* of the waveform instead of chasing it. PKP
(percussion pads keys) is an envelope **follow with decay** — the same
tempo-locked plane, with its swing amplitude damped by the PKP Decay slider
(`swing = 0.45·(1 − 0.7·decay)`) so each percussive pad click rides a decaying
swing. The Fractallizer **envelope-follows and repeats a time-invariant
fractal wave** — its log-frequency magnitude copies are fixed per render
(time-invariant) and the detail/fractal contribution is enveloped by the
same PKP plane before it is added back. All three are **mixed in up to 50%
at 100% activation** (`wet = 0.5·activation`), and all three step to the
same shared `pkp_env`, so EQR, PKP, and the Fractallizer move together as a
single tempo-locked master entity instead of drifting independently:

## Operator Theory — the book's alternative arithmetic

From the book ("Further Abstract Conclusions and Operator Theory", p.49-50).
A **large toggle** ("Operator Theory") in the global-operator bar selects the
execution route for mathematics in the DSP pathway and game logic.

**Equivalence policy (important):** enabling Operator Theory must not retune a
project. Shared engine paths use an **equivalence kernel** (`ot_equiv_*` /
`math_*`) whose numeric results are identical to ordinary arithmetic and
transcendentals. The book's alternate symbolic operators (`ot_add`, `ot_prod`,
…) remain available to explicit scripts when you want those rules directly.

Covered under the equivalence route (same output with OT ON or OFF):

| Family | Functions |
|---|---|
| Arithmetic | `math_add` `math_sub` `math_mul` `math_div` `math_pow` `math_scale` |
| Trig | `math_sin` `math_cos` `math_tan` `math_asin` `math_acos` `math_atan` `math_atan2` |
| Hyperbolic | `math_sinh` `math_cosh` `math_tanh` |
| Transcendental | `math_sqrt` `math_exp` `math_log` `math_log2` `math_log10` |
| Book isn / ics | `book_isn` `book_isn_inv` `book_ics` `book_ics_inv` / EQR isn path |

Seed/domain scripts see `sin`/`cos`/`tan`/`asin`/… bound to the `math_*`
wrappers, so OT ON still yields the normal values. Explicit `ot_*` names keep
the book's alternate hand/band rules.

```
1)  +/- are directional operators:
      neg + neg  = further negative
      neg − pos  = adds its value back toward/through zero
      ot_add(n,v)  = n+v, band-hopped by the enclosing integer of the larger |operand|
      ot_sub(n,v)  = n+v for (n<0, v>0), else ot_add(n, −v)

2)  products keep their hand (ot_prod):
      (−)·(−) = −                       (+)·(+) = +
      mixed    = imaginary (±), taken on the negative branch
      0·0 = 1                            (rule c — fixes factorial-0)

3)  signed powers/roots (ot_pow): same-hand resolves to the magnitude with its
    own orientation; differing hands → indeterminate (±) magnitude.

a)  division by hand (ot_div):  (−1)/(−x) = −1/X, (+1)/(+x) = 1/X,
    mixed signs → (±)X/1 (net absolute, the continued-2^x family);
    0 / 0 = 1.

b)  multiplying a graph by (±)1 flips one side's orientation.

d)  imaginary unit (ot_i_phase): i^k alternates +1/−1 — even powers land on
    the negative side.

e)  add/sub band hop: |v| ∈ (0,1] hops at 1, (1,2] at 2, (2,3] at 3, >3 folds
    back to 1.

f)  dividing by a divisor in absolute (0,2) re-expresses the dividend in the
    "higher-value" numeric field (refined once by the Meum residue
    (1 + MEUM_NORM)).
```

**Master-bus gate** (`ot_master_transform`, applied at the end of the master
render when enabled, always re-normalized to −1 dBFS):

```
m     = x / peak0
hop   = sign(m)·band(|m|)                    (rule e)
out   = (m + 0.35·hop) / (|out| + 0.2) · (1 + MEUM_NORM)     (rule f)
out   = −|out|·1.15 where adjacent negatives combine             (rules 1, 2)
out   = out / peak · 0.89                                       (−1 dBFS headroom)
```

**Game-logic gate**: the videogame-engine residue and angle-step numerics
run through the same `ot_*` kernels when the flag is set, keeping the whole
lattice deterministic per toggle state. Both toggles (DSP and game) are
driven by the one large button, so a project's identity is fully
reproducible from the toggle position alone.


## Deterministic visual synthesis
The visual renderer now has a seed-defined 64-slot master image lattice. A
continuous RGB image field is synthesized from the same composition state used
by the audio path: seed, spectral bands, waveform energy, centroid, playhead,
and master visual atoms. Instrument Count does not seed, randomize, or otherwise
change that latent image. Counts from 2 through 64 deterministically
repartition the same master material into different visual instrument
factorizations, while avoiding duplicate decorative complexity.

## Deterministic Visual + Game View-Space Rollout (2026-08-31)

This build shares one deterministic visual view-space contract across the host visualizer and generated games:

`seed -> canonical composition -> view state -> projection`

Camera state includes yaw, pitch, roll, distance and FOV. View lattices use equal-area Fibonacci-sphere sampling and deterministic greedy max-min coverage selection. Visual composition fingerprints are order-independent, and projection identities are cryptographic functions of the canonical seed/composition/view tuple. Generated game packages include `visual_determinism.py` so their visual/game camera state is self-contained and reproducible.


## Native Four-Engine Spatial 2026.3
The spatial/game layer is sculpted from the four non-GOAVA canonical engines: randomizer, phase-lock, Euclidean, and seeded. Five spatial channels project that state into position, phase, scale, topology, and complexity. GOAVA is an optional post-projection adapter and is never required for generation, topology, recursion, or infinite-world identity.
