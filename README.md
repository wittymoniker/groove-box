# Groovebox — Complete V1

## Goal
Groovebox is a deterministic audiovisual composition system built around a shared mathematical state. The same composition state drives audio, live visualization, video export, and generated software/game packages.

Design pillars:
1. **Deterministic:** the same seed and composition inputs reproduce the same canonical state.
2. **Order-independent:** canonical engine activation is reconciled from state, not activation order.
3. **Non-destructive:** user-authored composition remains the carrier; canonical engines fill or transform available structure without silently replacing protected material.
4. **Unified:** audio, visual, video, and game outputs derive from the same composition fingerprint and phase/harmonic vocabulary.
5. **Self-describing visuals:** every live instrument owns exactly one visual object whose geometry, motion, color, fade, and harmonic detail are derived from that instrument's live composition record.

## Run
```bash
pip install PyQt6 numpy sounddevice scipy
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

## Quick Start
1. Set BPM and sequence length.
2. Select an instrument and program its pads/sequence.
3. Leave Seed blank/0 for the no-seed mode, or enter a non-zero seed.
4. Use Playlist to arrange operators over time.
5. Press **Play** or export audio/video.
6. Optionally use Euclidean/Phase-Lock, Seeded Harmonic Randomizer, Domain Equations, Patch Modular, or GOAVA.

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
A **large toggle** ("Operator Theory") in the global-operator bar enables
the rules on **all mathematics in the DSP pathway and the game logic**.
Off by default → every canonical render is byte-identical to before. When
enabled the scalar kernels below replace the ordinary arithmetic at the
gated surfaces (final master-bus transform; game residue/angle numerics)
and are also exposed to seed scripts as `ot_add/ot_sub/ot_prod/ot_div/
ot_pow/ot_i_phase`.

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
