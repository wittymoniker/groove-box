
## V34 Stability Pass

- Reversible randomizer toggle contract: ON captures a full project baseline and generates a fresh variation; OFF restores the exact pre-randomize state; each subsequent ON cycle rerandomizes and shifts the control color palette.
- Canonical Signal Control defaults to Full Canonical / 100% authority and self-heals missing canonical coverage through canonical-owned runtime overlays without rewriting user data.
- Canonical Resonance / Activity is 50–150%, independent of the 50/50 source coefficients; 150% is activity/continuation drive, not output volume.
- Canonical→Instrument convolution influence is 0–100%.
- Maximum active instruments: 128. Default playlist row duration: 16 beats.
- ParametricMathBackground is integrated with a deep navy gradient field.
- Performance controls are consolidated into one horizontal deck; Automator controls are compacted into a multi-row grid.
- UI initialization order and Qt stylesheet declarations were hardened; division-by-zero-sensitive paths use explicit degenerate-case handling rather than epsilon denominators where practical.

# Groovebox — Mathematicians Groovebox

> **Modern architecture:** Python + C++17 + Julia, sharing one deterministic canonical state model.
>
> The project is a generative audio/visual/game composition engine rather than three unrelated generators. The working abstraction is the **Canonical Trio**: one state/seed function tree is projected into **Audio**, **Visual**, and **Game** domains. The projections may have different representations, but they are driven by the same canonical inputs, deterministic ordering, and seed identity.

## Table of Contents

1. [What v3[final] is](#1-what-v3final-is)
2. [Mathematical model and proof-of-concept](#2-mathematical-model-and-proof-of-concept)
3. [Canonical Trio architecture](#3-canonical-trio-architecture)
4. [Engine and feature reference](#4-engine-and-feature-reference)
5. [Audio pathway](#5-audio-pathway)
6. [DJ effects and live performance](#6-dj-effects-and-live-performance)
7. [Visual pathway](#7-visual-pathway)
8. [Video-game proof of concept](#8-video-game-proof-of-concept)
9. [Seed system](#9-seed-system)
10. [Rendering, partitions, and recovery](#10-rendering-partitions-and-recovery)
11. [Media import and export](#11-media-import-and-export)
12. [OT master transform and tensor correspondence](#12-ot-master-transform-and-tensor-correspondence)
13. [Numerical exactness and determinism](#13-numerical-exactness-and-determinism)
14. [Hybrid build and runtime dependencies](#14-hybrid-build-and-runtime-dependencies)
15. [First-launch provisioning](#15-first-launch-provisioning)
16. [Project layout](#16-project-layout)
17. [How to use the mathematical layer](#17-how-to-use-the-mathematical-layer--from-pad-to-canonical-generation)
18. [Meum calculus](#18-meum-calculus--definitions-operations-and-examples)
19. [Operator Theory (OT)](#19-operator-theory-ot--complete-project-math-reference)
20. [Canonical number-theory and congruence claims](#20-canonical-number-theory--congruence-claims--what-claimed-exact-means)
21. [Unison master transform](#21-unison-master-transform--formula-and-practical-example)
22. [Verification, redistribution, and numerical boundaries](#22-verification-redistribution-and-numerical-boundaries)

---

## 1. What v3[final] is

Groovebox is a deterministic mathematical composition environment with three synchronized output domains:

- **Audio:** oscillators, harmonic/inharmonic synthesis, Meum AM/FM/PM modulation, sequenced voices, canonical unison, imported-carrier influence, effects, live DJ transforms, and master rendering.
- **Visual:** a 2.5D scenograph driven by the same canonical seed, sequential values, phase, energy, spectrum, GOAVA, and engine masks used by the audio side.
- **Game:** a generated playable world used as a proof-of-concept that the same canonical state can be decoded into interactive mechanics rather than merely rendered as a picture.

The design goal is **repeatable generative capacity**: changing canonical input changes the output, while replaying the same canonical input reproduces the same output. Activation order is not allowed to become a hidden source of variation. The project therefore treats the trio as a **self-referential function tree at the state level**: the canonical state contains the vocabulary needed to decode audio, visual, and game behavior, and explicitly wired cross-domain routes may feed derived values back into later stages. This is not a claim that every subsystem is already one mathematically closed feedback tensor; each correspondence is documented and tested at the level actually implemented.

The Python layer remains authoritative for application state. C++ handles contiguous numerical hot paths. Julia is the readable numerical/reference layer and can call the C++ ABI directly for batch work. Julia is intentionally not placed in the default realtime callback unless an embedded runtime is explicitly configured.

---

## 2. Mathematical model and proof-of-concept

The core abstraction is a deterministic function tree:

\[
C = F(S, Q, P, M, T)
\]

where:

- `S` = seed representation;
- `Q` = sequence/playlist coordinates;
- `P` = canonical parameters (BPM, base frequency, engine mask, waveform and modulation state);
- `M` = imported media descriptors and optional carrier measurements;
- `T` = normalized or absolute time.

The output is a structured canonical state rather than one scalar:

\[
C \rightarrow \{A(t), V(t), G(t), I\}
\]

where `A` is audio state, `V` visual state, `G` game state, and `I` identity/provenance.

### 2.1 Canonical tensor view

For a finite render, represent canonical state as a rank-3 tensor

\[
\mathcal C[d,r,k]
\]

with domain `d ∈ {audio, visual, game}`, row/step coordinate `r`, and feature coordinate `k`.

A projection is a contraction with a domain-specific operator:

\[
Y_d(t) = \sum_{r,k} W_d(t,r,k)\,\mathcal C[d,r,k].
\]

This is not a claim that every current Python function is literally implemented as an ndarray contraction. It is the mathematical correspondence used to specify the implementation. Where a direct tensor implementation would allocate large temporary matrices, the runtime uses equivalent streaming/indexed operations for speed and memory locality.

### 2.2 Meum constants and mathematical vocabulary

The canonical vocabulary includes the project Meum lattice identity and common mathematical anchors:

\[M \approx 1.1975807343385265,\qquad M_n = \frac{M-1}{M},\qquad \Phi = \frac{1+\sqrt5}{2}.\]

Derived values such as `M²`, `M³`, `M⁻¹`, `log₂(M)`, and golden-ratio terms are used as deterministic parameter anchors. These constants are **engineering parameters of this project**, not claims of newly established mathematical constants or theorems.

### 2.3 Why this is useful

The same canonical features can be decoded differently:

- Audio maps phase/energy/harmonic features to samples.
- Visuals map phase/energy/seed/GOAVA features to geometry, hue, density, and motion.
- Games map the same stable features to world parameters, objective, difficulty, topology, events, and deterministic replay.

This creates a **Canonical Trio** instead of three loosely coupled randomizers.

### 2.4 Proof-of-concept: video games

A generated game is a stronger test than a static visual because it must preserve identity over time. A seed must deterministically produce a world, player state, event ordering, and replay stream. The exported game package therefore carries a composition fingerprint and can record/replay gameplay data. The game package already treats SOUND, VISUAL, and UI as a multimodal contract, while software-kind changes the function panel rather than stripping the other domains.

The intended mathematical proof is therefore:

\[
S \xrightarrow{F} C \xrightarrow{\pi_A,\pi_V,\pi_G} (A,V,G)
\]

and, for replay:

\[
(S,C,R) \xrightarrow{F_G} G_R = G'_R.
\]

A successful replay means the decoded game trajectory is the same canonical trajectory, subject to the documented floating-point/codec boundaries.

---

## Official identity and mathematical framework

**Official software names:** Groovebox; Mathematicians Groovebox.

**Primary mathematical framework:** Meum Calculus.

**Related project-defined arithmetic/operator framework:** Operator Theory (OT).

Meum Calculus is the mathematical framework developed and documented by Noah
Girouard King (Eski) in connection with *Scientific Theories and Inventions* and
related works. Groovebox implements the project-defined constants, transformations,
operators, coordinate systems, and derived quantities as a reproducible
computational system.

The release phrase **CLAIMED EXACT** means exact according to the project's declared
definitions, formulas, constants, serialization rules, and tested implementation
contract. It does not by itself assert that a project-defined result is an
independently established theorem of mathematics or physics.

When prose and implementation differ, the released source code and regression
tests are the final implementation authority; documentation discrepancies should
be corrected rather than silently interpreted as new mathematical rules.

## 3. Canonical Trio architecture

### Python — authoritative state and orchestration

Python owns UI, project serialization, sequencing, canonical unison, seed parsing, high-level effects, imported media, video/game integration, and deterministic bookkeeping.

### C++17 — numerical hot path

C++ owns the tight contiguous loops where they provide measurable benefit: Meum modulation vectors, voice harmonic/inharmonic synthesis, and hard clipping. The native build uses `-O3` and LTO where supported and deliberately does **not** use `-ffast-math`, preserving predictable IEEE-style behavior.

### Julia — numerical reference and optimization layer

Julia provides readable mathematical implementations, batch experiments, profiling candidates, and a direct `ccall` bridge to the C++ ABI. This gives the project a second executable numerical description without introducing a process boundary into realtime audio.

### Deterministic data flow

`Seed/Project → Python canonical state → optional Julia numerical analysis → C++ contiguous kernel → Python effect/output projections`

Parallelism must use per-voice/per-domain buffers followed by deterministic reduction. Never use unordered floating-point accumulation for the canonical renderer.

---

## 4. Engine and feature reference

| Feature | Purpose | Canonical role |
|---|---|---|
| Canonical Unison | Combines active engines in stable order | Identity |
| Seed Engine | Numeric, scripted and structured seed generation | Root input |
| Meum AM/FM/PM | Modulation family | Phase/frequency/amplitude |
| Harmonic Engine | Harmonic partial synthesis | Audio spectrum |
| Inharmonic Engine | Seed/entropy-derived partial family | Spectral diversity |
| GOAVA | Seed-linked sequence/scalar projection | Cross-domain feature |
| Euclidean / Phase-Lock / Randomizer / Seeded | Deterministic sequence sources | Temporal structure |
| Fractal sets | Mathematical shape families | Audio/visual parameterization |
| Domain equations | Multivariate longitudinal modulation | Cross-domain modulation |
| Global Play | Script/domain/wire overlay | Project-level transform |
| EQR / Fractallizer / PKP | Effect engines | Non-canonical/live or per-voice processing |
| DJ GOAVA | Live GOAVA-derived ring/drive morph | Reversible performance transform |
| RAND PARAM | Deterministic live parameter macro | Reversible performance transform |
| Imported carrier | Audio/video reference influence | External canonical input |
| 2.5D Scenograph | Audio-linked visual projection | Visual domain |
| Video-game generator | Playable projection of canonical state | Game domain |
| Provenance/fingerprint | Reproducibility and reverse analysis | Identity |
| Atomic `.part` saves | Crash-safe project recovery | Persistence |

The current UI already defines routing detectors including phase, energy, spectrum, GOAVA, Euclidean, seed, BPM, and pair, with targets including master mix, effects, ensemble, scenograph, domain, and unison.

---

## 5. Audio pathway

The canonical audio path is:

`seed → canonical unison → voice parameters → modulation → partial synthesis → imported-carrier/domain modulation → live DJ (optional) → master volume → hard clip → export`

The final export path intentionally avoids a hidden master EQ, limiter, normalizer, or spectral pass. The historical master-bus EQR/PKP/PED stack is disabled because its stacked amplitude/envelope multiplication produced the reported “filtered/pumping” behavior. **This does not disable the FX system.** Per-voice and explicitly routed effects remain available, including DJ effects and their envelopes. The final master-stage contract is simply: composition output → Master Volume/drive factor → hard clip.

**Important:** there are still *per-voice* filter/resonator/formant parameters and effects, and DJ Boost Hit intentionally has a transient envelope. Those are not hidden final-bus filters. If the sound is still overly resonant, inspect the explicitly routed per-voice/effect parameters first.

### Audio exactness

The native voice kernel has been regression-tested against the NumPy reference for canonical harmonic/inharmonic, waveform, and GOAVA paths with exact float32 array equality in the supplied validation report. The C++ hardclip kernel is likewise tested for exact float32 equality.

---

## 6. DJ effects and live performance

DJ effects are intentionally **reversible bus transforms**. They do not rewrite canonical composition state.

- **GOAVA DJ:** ring/drive morph derived from the current canonical GOAVA scalar and unordered sound-pair identity.
- **RAND PARAM:** deterministic macro that sounds stochastic but is stable for seed/pair/BPM and does not call an RNG from the audio callback.
- **Live media steering:** imported WAV/video energy can participate in the live morph path.
- **Apply/Unapply discipline:** authoring operations may modify the project state; live DJ transforms should remain clearly separated from canonical identity.

This separation is essential: a performance gesture should not silently change the mathematical identity of a saved composition.

---

## 7. Visual pathway

The visualizer is a projection, not an independent random animation system. Visual state is derived from the canonical feature vector and time/step coordinate.

Recommended v3[final] visual policy (carried into the opencode merge):

1. Prefer fewer, stronger objects over dense line fields.
2. Use particle/geometry density as a bounded function of energy and seed entropy.
3. Keep the same phase anchors used by audio.
4. Use deterministic soft stamps/geometry rather than uncontrolled accumulation.
5. Preserve a low-detail mode for realtime play and a high-detail mode for export.
6. Avoid visual “line spam” when the same mathematical information can be encoded as motion, scale, topology, or sparse points.

The existing game/visual code already uses seed, sequence, Meum-family constants, phase and entropy to derive object positions and colors.

---

## 8. Video-game proof of concept

The generated game is deliberately small: it is a proof that the canonical state can produce rules, not merely pixels.

A generated package contains:

- deterministic world fingerprint;
- objective/difficulty/level type;
- sigil/world data;
- music bed and live SFX;
- visual scenograph;
- PyQt6 UI or CLI fallback;
- record/replay data;
- codec/provenance metadata.

The existing package format documents deterministic recording and replay and exposes JSON/GZ/CSV/TXT/WAV/PNG jobs.

### Playability refinements for v3[final]

- Reduce excessive GOAVA ornamentation; make GOAVA affect meaningful world variables rather than every visual surface.
- Keep movement response continuous and deterministic.
- Separate world-generation entropy from control sensitivity.
- Make difficulty a function of bounded canonical features rather than arbitrary random spikes.
- Keep a stable seed → world fingerprint mapping.
- Record input events as discrete canonical events and reconstruct continuous state from those events.

---

## 9. Seed system

The seed system accepts ordinary numeric seeds and scriptable mathematical forms. v3[final] should treat the following as first-class demonstrations:

### Scalar
`432`

### List/vector
`1, 3, 5, 7, 11, 13`

### Parametric
`[sin(t*MEUM), cos(t*PHI), t]`

### Cylinder / periodic parameterization
`theta=t*tau; r=0.5+0.5*sin(theta*MEUM); x=r*cos(theta); y=r*sin(theta)`

### Multivariate
`x=sin(t*MEUM); y=cos(t*PHI); z=isn(t); return x + y + z`

### L-function / number-theoretic family
A deterministic arithmetic series may be represented as a finite Dirichlet-like sample or another explicit sequence; the implementation must label it as a seed family, not imply a theorem merely by naming it an L-function.

### Loop-based
`[sin(i*MEUM) for i in range(16)]` (or equivalent supported list syntax).

### Conditional / logic
`if(sin(t*MEUM)>=0) 64 elif cos(t*PHI)>=0 32 elif 7`

### Fractal-set families
The existing six named forms are retained: Divergent Space, Wormhole, Wormhill, Worms, Star, and Starburst. Their documented expressions are `xc+c`, `x^c+x`, `x+c`, `c√x`, `c^x`, and `√c·x`, respectively.

All seed forms must be folded into the same canonical identity path. A syntactically different spelling that evaluates to the same canonical numeric sequence should be able to normalize to the same identity where exact normalization is defined.

---

## 10. Rendering, partitions, and recovery

All long renders expose a **Part Count** setting rather than hard-code 16. Recommended range: `1–128`, with a default chosen from render duration and available memory. The setting is independently applicable to WAV/audio, video, and video+audio jobs.

The partition count applies independently to:

- video;
- video+audio renders;
- WAV/audio renders;
- other long offline jobs where partitioning is beneficial.

Each part is written atomically as `<stem>.partNN.<ext>.part` or `<stem>.partNN.<ext>`, completed parts can be reused, and the final artifact is atomically promoted into place.

The existing video renderer already uses recoverable part files and keeps the output next to the selected destination; v3[final] generalizes the policy to audio as well.

For WAV, parts are PCM-compatible and concatenated without a lossy codec boundary. This makes WAV the cleanest render/recovery target.

---

## 11. Media import and export

The media importer should be **codec-oriented**, not extension-oriented. ffmpeg/ffprobe are the canonical decoder/metadata layer.

Supported import should include common audio/video containers and codecs that the installed ffmpeg build can decode, including WAV, AIFF/CAF, FLAC, MP3, OGG/Opus, MP4/MOV/M4V, MKV, WebM, AVI and future formats exposed by ffmpeg.

A file-dialog extension list is only a convenience; the actual decoder capability comes from ffmpeg. Import is therefore capability-oriented and can accept additional formats as the installed ffmpeg build gains decoders.

Exports currently cover WAV/FLAC/OGG/AIFF/MP3/Opus/CAF and MP4/WebM/AVI paths where the installed encoder supports them.

---

## 12. OT master transform and tensor correspondence

The master transform is:

\[
B_n = \sum_k I_{kn}V_k,
\quad
H_n = \operatorname{sign}(x_n)B_n,
\]

\[
y_n = x_n + 0.35H_n,
\]

\[
y_n \leftarrow y_n\left(1 + 0.15\,m/(1+|y_n|)\right),
\]

followed by a one-sample memory rule and negative-run transform.

The band selection is exactly representable as an indicator/value tensor contraction. The previous-sample operation is exactly a shift matrix `S` with the first sample mapped to itself:

\[
\mathbf p = S\mathbf y.
\]

The negative-run mask is then

\[
N_n = 1[y_n<0]1[p_n<0].
\]

The current implementation is intentionally vectorized/streaming rather than constructing an `n×n` shift matrix, because the explicit matrix has unnecessary memory and computational cost. The tensor formulation is therefore a **proof-level correspondence**, not a demand to materialize the tensor.

The project should extend this same discipline to the Canonical Trio: define the tensor schema first, then prove individual runtime projections against it with numerical regression tests. Do not claim a global tensor equivalence unless the implementation and raw-output comparison support it.

---

## 13. Numerical exactness and determinism

Rules:

1. Canonical input order is stable.
2. Engine activation order is sorted before canonical application.
3. No ambient RNG is used in canonical render paths.
4. Realtime DJ randomness is derived from deterministic state rather than an audio-thread RNG.
5. Parallel renderers reduce in deterministic order.
6. C++ canonical builds avoid `-ffast-math`.
7. Native and reference kernels have regression tests.
8. Project snapshots store the inputs required to reconstruct canonical identity.
9. Export provenance stores the canonical fingerprint.

The existing unison contract explicitly describes seed+BPM+base-frequency+playlist/per-sequence/global-algorithm state as the canonical identity and excludes final master effects from identity.

---

## 14. Hybrid build and runtime dependencies

### Required

- Python 3.10–3.12 recommended
- PyQt6
- NumPy
- SciPy
- sounddevice
- Pillow
- C++17 compiler/toolchain
- ffmpeg + ffprobe

### Optional

- Julia 1.10+ (or a project-supported current Julia release)
- juliacall for Python↔Julia embedding/experiments
- platform audio development packages

The project already keeps C++ and Julia sources under the same project tree as Python scripts and launch/build files. The Julia layer calls the same C ABI rather than spawning a second process for each DSP block. The export package also carries platform launchers, dependency installers, and first-launch provisioning helpers.

---

## 15. First-launch provisioning

The launch path should:

1. create `./bin/` if absent;
2. detect a bundled/local ffmpeg first;
3. detect a system ffmpeg second;
4. if missing, run the platform provisioning helper;
5. verify `ffmpeg` and `ffprobe` with a real version/probe command;
6. create native/build directories;
7. build the C++ library if absent or stale;
8. run a lightweight Python/native smoke test;
9. launch the UI.

This makes a fresh export directory self-provisioning where the OS permits package/download installation. Offline machines still receive a precise diagnostic instead of a mysterious missing-binary failure.

The generated game packages already ship platform-specific dependency installers and describe placing ffmpeg in a local `bin` directory.

---

## 16. Project layout

```text
Groovebox/
├── groovebox.py                 # authoritative application/UI
├── videogame_engine.py          # game projection
├── groovebox_reference.py       # reference numerical path
├── canonical_triad.py           # canonical tensor/state correspondence
├── README.md
├── HELP_TEXT.md                 # synchronized long-form help source
├── TRIO_ARCHITECTURE.md
├── TEST_REPORT.md
├── cpp/
│   ├── CMakeLists.txt
│   └── groovebox_accel.cpp
├── julia/
│   ├── GrooveboxHybrid.jl
│   └── smoke_test.jl
├── native/                      # generated shared library
├── bin/                         # local ffmpeg/ffprobe when provisioned
├── scripts/
│   ├── build_linux.sh
│   ├── build_macos.sh
│   ├── build_windows.ps1
│   └── provision_first_launch.py
├── run_hybrid.sh
├── launch_desktop.sh
├── launch_mobile.sh
├── launch groovebox.sh
├── launcher groovebox.py
├── install_deps_linux.sh
├── install_deps_macos.sh
└── install_deps_windows.ps1
```

C++ and Julia are intentionally **not** stored in a separate source tree: all three languages form one exportable project directory.

---

## 17. HOW TO USE THE MATHEMATICAL LAYER — FROM PAD TO CANONICAL GENERATION

This section is the practical path for using the mathematics without needing to
understand the implementation first.

### 17.1 The shortest useful workflow

1. Choose BPM and sequence length.
2. Choose an instrument and turn on a few pads.
3. Leave Seed blank/zero for ordinary authoring, or enter a non-zero numeric seed.
4. Press **Play** and listen to the carrier.
5. Enable **Phase-Lock**, **Randomize**, **Seeded**, **GOAVA**, or **Operator Theory** one at a time.
6. Open Playlist when you want the generated structure written into arrangement rows.
7. Use Domain Equations for time/space functions and Instrument Scripts for per-instrument rules.
8. Save the project before experimenting with a new mathematical recipe.

### 17.2 First scripting examples

```python
# A simple two-frequency carrier
sin(2*pi*t*2) + 0.5*cos(2*pi*t*3)

# Meum phase field
sin(t*MEUM) * cos(t*PHI)

# Seed-dependent motion
sin(t*MEUM + seed) * (0.5 + 0.5*cos(t*PHI))

# The project's isn / ics forms
isn(t*MEUM) * 0.6 + ics(t*PHI) * 0.4

# A multivariate domain expression
sin(x*MEUM + y*PHI + z*pi)

# Function-style script
return isn(t*MEUM) + 0.25*ics(t*PHI)
```

`sin`, `cos`, `isn`, `ics`, `MEUM`, `PHI`, `pi`, `e`, `tau`, `seed`, `x`, `y`,
`z`, and the public reference constants are available to the appropriate
script evaluators. Use the Help panel as the authoritative list for the build
being run.

### 17.3 How generated math reaches sound

The canonical pipeline is conceptually:

`seed → canonical context → instrument lattice → operator/sequence transforms → voice parameters → mix`

The seed is therefore an input to a deterministic construction, not an assertion
that every generated result is a theorem of number theory. When a canonical
fingerprint is identical, the implementation is intended to regenerate the same
canonical state.

## 18. MEUM CALCULUS — PROJECT DEFINITIONS, OPERATIONS, AND EXAMPLES

**MEUM CALCULUS — CLAIMED EXACT.** In this project, “Meum calculus” means the
project-defined family of transformations built from the constant `MEUM`, its
reciprocals/powers, phase rotations, modular coordinates, and derived normalized
weights. “Claimed exact” describes the project's internal symbolic contract: the
same stored inputs and formulas are intended to give the same canonical result.
It is **not** a claim that Meum calculus is an independently established branch
of mathematics or that its special constant has been proved irrational here.

### 18.1 Public constants

The canonical Meum value is stored as

`M = MEUM = 1.1975807343385265188`

with the public reference inverse

`M⁻¹ = MEUM_INV = 0.83501677283773394333148276154833054143874793150691`.

Important derived values include:

- `M² = 1.43419961525880442984053780233084675344`
- `M³ = 1.7175698284296712120687451889540584671690563022583`
- `M⁴ = 2.0569285364085026523421673878967788864920989745683`
- `(M−1)/M = 0.16498322716226605666851723845166945856125206849309`
- `2^M = 2.2935474173287805635918286442792609595802586606571`
- `log₂(M) = 0.26012291784344212146116471128795687966817094961902`

Reference constants are also exposed as `PI_IRR`, `E_IRR`, `PHI`, `PHI_INV`,
`SQRT2`, `SQRT3`, and `SILVER`.

### 18.2 Meum power lattice

For instrument slot `i`, the canonical power table is generated from

`P_j = M^(j−6),   j = 0,…,35`

and the slot coordinate uses the dense project-defined phase position

`u_i = (3 i M) mod 36`.

If `j = floor(u_i)` and `r = u_i − j`, the interpolated lattice factor is

`L_i = (1−r) P_j + r P_(j+1 mod 36)`.

This is a deterministic geometric mapping. “Dense” here means the use of a
non-rational-looking project constant is intended to avoid a short visual
period; it should not be read as a proof of equidistribution.

### 18.3 Meum normalization

The standard normalized weight is

`N_M = (M−1)/M`.

A Meum-weighted pair can be written

`F_M(a,b) = N_M a + (1−N_M)b`.

The canonical `isn` implementation uses this style of Meum blending in its EQR
execution path; the exact implementation should be consulted when auditing a
specific version.

### 18.4 Meum phase rotation

A slot phase reference is

`φ_i = 2π i / 48`.

A second deterministic phase coordinate used by the canonical translator is

`ψ_i = τ ((i N_M Φ⁻¹) mod 1)`.

These are coordinates, not random numbers. They are reproducible from `i` and
the public constants.

### 18.5 GOAVA irrational-sampling example

For continuous time `t`, base frequency `f_b`, and channel `c`, the project uses

`s(t) = 0.5 f_b M⁻¹ t`.

A seed-list contribution has the form

`C_v(t) = [1 + cos(β_v + (π/2)(|v|+|n|)s(t))] / (N + |n−v|)`

with the zero-valued seed entry receiving the additional `s(t)` term in its
base phase. The stream is then formed from the note/reference difference and a
fixed Meum-family gain. The important user-facing property is that the stream is
seeded and continuous in `t`; it is not an RNG call in the audio callback.

## 19. OPERATOR THEORY (OT) — COMPLETE PROJECT MATH REFERENCE

**OT THEORY — CLAIMED EXACT.** Operator Theory is the project's alternative
arithmetic vocabulary. In canonical paths it is primarily an execution/notation
layer around deterministic scalar operations. The word “exact” means “exact
according to the project's stated OT rules and regression contract,” not a claim
that these rules replace ordinary arithmetic in established mathematics.

### 19.1 OT band function

For `x`, let `a=|x|`. The project's band selector is

`B(x) = 1,  if a≤1;  2, if 1<a≤2;  3, if 2<a≤3;  1, if a>3.`

### 19.2 OT addition and subtraction

Let `b` be the band of the operand with the greater magnitude. Then

`OT_ADD(n,v) = n+v + 0.5 B`, when `n+v ≥ 0`,

and

`OT_ADD(n,v) = n+v − 0.5 B`, when `n+v < 0`.

Subtraction is defined by the project's directional rule; otherwise it routes
through `OT_ADD(n,−v)`.

### 19.3 OT multiplication

Magnitude is ordinary multiplication:

`|OT_MUL(a,b)| = |a b|`.

The project's sign rule is intentionally nonstandard. **The implementation is
the authoritative definition**: positive×positive returns `+|ab|`; negative×negative
returns `−|ab|`; unlike signs return `−|ab|`. The special identity is `OT_MUL(0,0)=1`, while zero with a nonzero
operand returns `0`.

### 19.4 OT powers and roots

For power,

`OT_POW(b,e) = s |b|^|e|`,

where `s=+1` when `b` and `e` have the same sign convention and `s=−1`
otherwise. This is a project-defined signed-power rule.

Roots use ordinary magnitude roots with the project's real-sign convention.
Undefined real-domain cases remain undefined rather than being silently
reinterpreted as ordinary positive magnitudes.

### 19.5 OT division and zero

For nonzero denominator,

`|OT_DIV(a,b)| = |a|/|b|`, with the sign taken from `a`.

The project defines `0/0 = 1` in OT mode. Division by zero for nonzero `a` uses
the project's large finite sentinel convention. This is a compatibility rule,
not ordinary field arithmetic.

### 19.6 OT phase operator

The integer phase marker is

`OT_I_PHASE(x,k) = −x` for even `k`, and `+x` for odd `k`.

It is used as a symbolic orientation marker and is not intended to introduce a
new complex-valued audio stream by itself.

### 19.7 `isn` and `ics`

The canonical book-form definitions are

`isn(θ) = 2 sin(θ/2)`

`isn⁻¹(y) = 2 arcsin(y/2)` on the real principal domain, and

`ics(θ) = 2 cos(θ/2)`

`ics⁻¹(y) = 2 arccos(y/2)` on the real principal domain.

The inverse functions necessarily have a real-domain requirement `|y/2|≤1`.
That mathematical domain restriction is not a claim about audio clipping; it is
the domain of the inverse function.

### 19.8 EQR reality tensor

The project uses the following documented EQR form for sequences indexed by `n`:

`P = (1/k) Σ[n=0..k] isn⁻¹((isn(d_n)+isn(t))/2)`

`E = (1/k) Σ[n=0..k] isn(θ_n)/d_n`

`D = (1/k) Σ[n=0..k] isn⁻¹(isn(θ_n) E/(I P))`

`Z = P E + D`

with the project constant `I = 134964356` as its finite-infinity reference.

These equations describe the project's model. They do not establish a physical
law or a mathematically proven theory of reality.

## 20. CANONICAL NUMBER-THEORY / CONGRUENCE CLAIMS — WHAT “CLAIMED EXACT” MEANS

The project may label a canonical generation **CLAIMED EXACT** when the claim is
restricted to the following reproducible implementation contract:

1. The same canonical inputs are serialized in the same order.
2. The same public constants are used.
3. The same deterministic formulas and integer/index rules are applied.
4. The same canonical state fingerprint is regenerated.
5. Regression tests compare the resulting canonical records or buffers.

This supports a claim of **implementation-level deterministic correctness under
the tested contract**. It does not justify the stronger statement that the
software has proved new number theory, proved that MEUM is irrational, or proved
perfect congruence for all possible future inputs.

For modular indexing, the ordinary congruence notation is

`a ≡ b (mod n)  ⇔  n | (a−b)`.

For a cyclic slot permutation

`p(i) = (a i + b) mod n`,

a sufficient condition for a bijection over the residue classes is

`gcd(a,n)=1`.

This is an established finite-number-theory fact and can be used as a real
correctness statement when the implementation follows it. A project-specific
lattice built from MEUM should instead be described as a deterministic mapping
unless a separate proof establishes stronger properties.

### Reference-only scripting constants

The following names are intentionally exposed for inspection and scripting:

`MEUM`, `MEUM_CONSTANT`, `MEUM_INV`, `MEUM_MINUS_1`, `MEUM_SQ`, `MEUM_CUBE`,
`MEUM_FOURTH`, `MEUM_NORM`, `MEUM_OVER_1_5`, `MEUM_TWO_POW`,
`MEUM_TWO_POW_OVER_SQ`, `MEUM_LOG2`, `MEUM_UNISON_STEP_FACTOR`, `MEUM_POWERS_36`,
`INSTRUMENT_PHASE_LOCK_48`, `PHI`, `PHI_INV`, `PI_IRR`, `E_IRR`, `SQRT2`,
`SQRT3`, and `SILVER`.

They are reference values, not hidden controls. Scripts should read them rather
than duplicating rounded literals when reproducibility matters.

## 21. UNISON MASTER TRANSFORM — FORMULA AND PRACTICAL EXAMPLE

The canonical full-unison idea is identity cancellation: every active voice is
translated from the same shared context rather than receiving an independent
random identity.

A useful abstract form is

`U_i = T(C, i, E)`

where `C=(seed, base, ratio, s_int, sequential_nums)` is the canonical context,
`i` is the roster slot, and `E` is the set of active engine flags.

Outside full unison, the pitch carrier uses the lattice factor `L_i`:

`f_i = base · L_i · r_i`.

Inside full unison, the canonical translator uses the shared base and ratio:

`f_i = base · ratio`.

The shared entropy coordinate is derived from the canonical entropy function;
the phase reference is shared rather than independently randomized. The result
is intended to be an ensemble identity rather than 48 unrelated oscillators.

### A reference scripting recipe

```python
# Inspect the canonical constants
M = MEUM
invM = MEUM_INV
phi = PHI

# Reproduce the unison step coordinate for slot i
u = (3*i*M) % 36

# Continuous GOAVA coordinate
s = 0.5 * base_frequency * invM * t

# A compact master modulation
master = isn(t*M) * (M - 1) / M + ics(t*phi) * (1 - (M - 1)/M)
return master
```

The recipe is for reference and experimentation. It does not promise that a
user script reproduces every internal voice parameter unless it uses the same
canonical function and state inputs as the implementation.

## 22. VERIFICATION, REDISTRIBUTION, AND NUMERICAL BOUNDARIES

### 22.1 What should be verified before redistribution

- Python syntax compiles.
- The root `groovebox.py`, `README.md`, and `HELP_TEXT.md` contain the same
  mathematical documentation where duplication is intentional.
- Public constants are present in the script namespace and reference evaluator.
- Canonical generation is deterministic for fixed serialized input.
- Canonical fingerprints remain stable across save/load.
- Python/reference and native implementations agree where the release contract
  requires parity.
- Nested redistribution archives contain the refreshed files.

### 22.2 No hidden canonical clamp

The canonical frequency-reference helper is intentionally transparent: it does
not silently force a requested mathematical frequency into a fixed audible
interval. Explicit instrument/effect constraints are separate from the
reference transform.

A file-format conversion can still impose a representation limit. For example,
integer PCM encoding has a finite numeric range. That is a property of the target
file representation, not a hidden mathematical clamp in the canonical transform.

Likewise, an inverse such as `arcsin(y/2)` has a mathematical domain. A caller
that supplies an out-of-domain value has supplied an undefined real input; this
must not be described as evidence that the canonical forward transform is
clamping its output.

### 22.3 Redistribution rule

Every nested archive included in a redistribution package is a distribution
artifact, not a separate source of truth. When source documentation or
`groovebox.py` changes, refresh every nested ZIP/TAR.GZ that contains those files
and verify that its contents match the outer package.

The release phrase **CLAIMED EXACT** therefore means:

> exact with respect to the project's declared formulas, constants, serialization,
> and tested deterministic implementation contract; approximate/potential with
> respect to broader mathematical or physical truth.

That distinction should remain in public documentation so users can reproduce
results without mistaking a project claim for an independently proved theorem.

---

## License / project policy

Keep the project-specific license and attribution files supplied with the distribution.
This README describes implementation behavior and project-defined mathematics. It
must not be read as a scientific claim that Meum calculus or Operator Theory is an
established mathematical theory. Established number-theory statements should be
limited to statements that follow from ordinary definitions and proofs; project
specific claims should remain explicitly labeled **CLAIMED EXACT** and tied to a
reproducible test contract.


## Planetary flight kernel (2026-09-04)

The game world uses a deterministic 3-D planetary gravity model rather than a
flat terrain-only world. Each seed produces a solar-system layout, planets have
mass/radius/orbit/inclination, and the player is integrated with gravity plus
player thrust. Flight is continuous: orbit, escape, transfer, approach and
landing are physical state changes. Portals remain as visual/navigation
landmarks but do not teleport the player in planetary mode.

The camera uses a gravity-relative frame every tick: its forward/look axis is
perpendicular to the instantaneous gravity acceleration, with screen-up aligned
against gravity. This keeps the horizon/camera stable while flying around a
planet or transitioning into deep space.

### Finite sprite vocabulary, unbounded game composition

`SpriteGrammar` composes a small deterministic vocabulary (`core`, `ring`,
`panel`, `wing`, `engine`, `crystal`, `antenna`, `window`, `spike`, `orb`) into
seeded entities. This lets sectors, encounters, stations, creatures and props
be generated from finite helper sprite parts instead of requiring one asset file
per game object.


## 23. Canonical authority and cross-media single-source policy

The canonical composition is the authoritative representation of the project at
engine, persistence, export, provenance, and cross-media boundaries. Audio, video,
and videogame generation consume that same composition rather than independently
reconstructing separate projects.

Legacy engine attributes may remain as compatibility mirrors because Groovebox is
a large existing application. They are not intended to become competing sources
of truth. Canonical save/load, export, provenance, and cross-media operations pass
through the canonical authority layer.

The conceptual relationship is:

```text
             ONE CANONICAL COMPOSITION
                       │
             ┌─────────┼─────────┐
             ▼         ▼         ▼
           AUDIO     VIDEO      GAME
             │         │         │
             ▼         ▼         ▼
            WAV       MP4   GAME DATA/ENGINE
```

The same principle applies to imported media: audio and video references are part
of composition state when their supported roles affect the work. Missing external
media should be reported rather than silently replaced with unrelated content.

## 24. Credits and attribution

Main editor and author: **Noah Girouard King (Eski)**.

Development and research assistance credited by the project includes Grok (xAI),
Gemini (Google), Claude (Anthropic), ChatGPT (OpenAI), Mistral.ai (Mistral),
Meta AI (Meta), GitHub Copilot (GitHub), Cursor Grok 4.6, jcode(1jehuang), and
opencode (anomalyco). These credits describe project tooling/assistance and do not
imply endorsement, ownership, authorship, or scientific validation by those services.

## 25. Final release principle

Groovebox is intended to be one mathematical composition environment rather than
three disconnected programs:

**ONE COMPOSITION = SOUND + IMAGE + INTERACTION**

The mathematical framework is part of the creative and computational identity of
the project. The reproducibility contract is part of its engineering identity.
The distinction between project-defined mathematics and independently established
mathematical or physical truth is part of its documentation standard.


--------------------------------------------------------------------------------
PLAYLIST ROWS / ROW BEATS
-------------------------
  Playlist Rows controls how many arrangement rows exist. Row beats controls the
  wall-clock duration of each playlist row. These are arrangement timing controls,
  not automation-step selectors; automation has its own Length and Step controls.

AUTOMATION STEP EDITOR — SEQUENCER-STYLE CONTROL
--------------------------------------------------------------------------------
  The automation strip is a second step sequencer directly under the main
  sequencer. It is intentionally simple and behaves like the normal step pads.

  • Length controls how many automation steps are shown. The orange strip grows
    or scrolls horizontally to match that count.
  • Sequence Attack and Sequence Release default to 50% each and remain directly
    controllable per sequence by the canonical composition state.
  • First click on an automation step = SELECT + TELEPORT. The Step, Operator,
    Sequence, and Offset ± controls above immediately show that step's state.
  • Second click on the SAME automation step = toggle ON/OFF. ON steps are bright
    orange; OFF steps are dim orange/brown. The selected step has a bright outline.
  • Operator chooses the instrument/operator for that automation step.
  • Sequence chooses the sequence bank used at that step.
  • Offset ± is the per-note sequence-step offset.
  • Changing Operator, Sequence, or Offset ± edits the currently selected step
    immediately; there is no POINT/apply button.
  • There is no automation-points counter and no playlist-row selector here.
    Automation is edited in the same step-oriented context as the sequencer.
  • The highlighted AUTO step is the active teleport target. The Step box above
    follows it, and Operator / Sequence / Offset ± edit that same step live.
  • Master Volume is deliberately outside canonical control. Canonicals control
    composition state (including synth pitch/amp and sequence/pattern envelopes),
    never the final Master Volume.
  • CLEAR removes all direct automation steps.
  • RANDOMIZE AUTOMATION IN SEQUENCE randomizes only the currently selected
    Operator / Sequence automation lane. It does not alter other sequences or
    Master Volume.
  • RANDOMIZE ALL SEQ rebuilds automation across every
    instrument and sequence. It changes automation only; Master Volume remains
    untouched. Both randomizers create one undoable edit.

  Typical use:
      1. Set Length (for example 16).
      2. Click AUTO 1 once to select it.
      3. Choose Operator / Sequence / Offset ±.
      4. Click AUTO 1 again to turn that automation step ON.
      5. Click another step once to teleport to it, edit it, then click it again
         when you want it ON.

  The automation state is written through the canonical composition boundary and
  participates in Live Play / Audio Export / Video Export. Disabled automation steps do not drive the
  render. The Automator popup is a UI-only teleport indicator; Operator, Sequence,
  and Offset edits are written to the selected automation point.

## AUTOMATION RANDOMIZATION

Automation has two deliberately separate randomizers:

- **Randomize Automation In Sequence** — operates only on the currently selected instrument/operator and sequence.
- **Randomize All Automation Everywhere** — operates across every instrument and every sequence.

These controls modify automation steps/offsets only. They do **not** control or randomize Master Volume.


### v13.1 Signal Conversion / Path Parity
- **Master Vector Synth** is a bounded post-composition conversion layer. User XYZ direction and the deterministic canonical XYZ direction are blended 50/50; Drive controls conversion strength.
- **Signal Guard** preserves finite/nonzero support when the bounded vector field is active; it is not a claim that an absent/zero input contains recoverable information.
- **Signal Conversion Monitor** reports RMS, peak, headroom, finite status, and signal presence after vector conversion. It is observational and cannot become a second composition authority.
- **SAFE VECTOR** restores the recommended starting point: conversion ON, guard ON, Drive 50%. **RESET VECTOR** zeros only the user XYZ direction; canonical direction remains active at 50%.
- Project JSON save/load already carries `master_vector_state`. Export provenance now also carries the vector coordinates, Drive, enabled/guard flags, and the fixed 50/50 ownership weights.
- Live Play and audio/video export all pass through `_render_mixdown_buffer`, so the Master Vector Synth is applied consistently before the final master hard-clip stage.

### v13 UI / Master Vector Synth
- SEQUENCER and AUTOMATOR STEPS interaction labels are green.
- Sequencer ON cells are gold; OFF cells are dark blue.
- Automator enabled cells use a brown-red base and become more red on hover; OFF cells are dark blue.
- Edit Synth Per Seq is a brown active-state button and prepares sequence-local synth/panel editing.
- Automator teleport inspector is a top-level anchored popup positioned above the selected cell when screen space allows.
- Added MASTER VECTOR SYNTH: bounded XYZ resonant direction visualizer, fixed 50/50 user/canonical direction blend, drive control, and signal guard.
- Added SIGNAL CONVERSION MONITOR with post-vector RMS/peak/headroom telemetry plus SAFE VECTOR and RESET VECTOR shortcuts.
- Added top-right MATH GROOVEBOX. logo and expanded Live DJ panel width.


### v15 User Media + Canonical Morph Bridge
- **Load Carrier** accepts common audio and video containers. Audio is decoded as the carrier; video audio becomes the carrier while the original video path remains available to the audiovisual export path.
- **Load Sample → Selected Operator** accepts audio and video files per operator. Video samples are represented as user-owned per-operator media; their decoded audio stream participates in the selected operator's render path.
- **PRE-CANONICAL SAMPLE MORPH** uses the selected operator's synth parameter state, script, incident patch topology/gains, and domain definition to shape a transformed sample branch.
- The local sample bridge is explicitly **50% untouched user waveform + 50% transformed branch**, so user sample material has a minimum 50% local contribution. Adaptive Fit and Phase Lock only shape the transformed branch.
- **FINITE / DC / PEAK GUARD** keeps the transformed branch finite and bounded without silently replacing the user sample.
- Project save/load stores media references and sample-morph settings; decoded waveform arrays are runtime-derived and re-decoded from the saved paths.
- Live Play and Audio/Video Export share `_render_mixdown_buffer`, so sample morph, canonical composition, and Master Vector conversion stay on the same render transaction.
- Export provenance records operator media references and sample-morph settings in addition to Master Vector state.

### v15 UI / Teleport Reliability
- Main Sequencer step editor is a top-level anchored popup, clamped to the physical display rather than the scrolling viewport.
- Automator teleport inspector is also top-level and repositions when its horizontal scroll bar moves, preventing the inspector from remaining over an old cell.
- `Edit Synth\nPer Seq` is the sequence-local synth/panel editing control.
- `MATH GROOVEBOX.` is enlarged in the Global Processor Controls header.
- Master Vector Synth is stacked above the Play Video Game and Live DJ controls, making the conversion layer visually upstream of those performance surfaces.


V16 UI / automation update: Randomize Automation + Sequence now randomizes automation values together with reference operator, reference sequence number, and per-step offset. Local mode scopes by source instrument/sequence; global mode covers all instrument/sequence banks. Track Offset is persisted per sequence and applied before per-step offset. Global XMOD and Input XMOD plus 0–200% Synth Panel / Mod Patch / Write Script / Calc Domain modulation weights are saved in project/export provenance. Media carrier/sample controls are in the upper control deck, and visualizers have bidirectional scrolling with scalable monitor sizes.


## MEUM SPATIAL EQUATION FORMS — GROOVEBOX CANONICAL MATH

Groovebox uses the following stripped-down spatial forms as an implementation language for its mathematical audio/composition pathways. They are **not presented as replacements for the established physical theories**; they are compact computational forms used by the Groovebox engine. Operator Theory (OT) changes expression/method routing only; it does not select a different mathematical output model.

### 1. Spatial Curvature & Metric Evaluation

Accepted reference form:

$$G_{\mu\nu} + \Lambda g_{\mu\nu} = \frac{8\pi G}{c^4}T_{\mu\nu}$$

Groovebox / Meum spatial form:

$$\nabla^2\Psi(x,y,z)=S(x,y,z)$$

The engine treats this as a direct scalar-field relation over the x/y/z computational field rather than constructing a full spacetime metric.

### 2. Field Potential & Attenuation

Accepted electrostatic reference form:

$$\Phi(r)=\frac{q}{4\pi\epsilon_0r}$$

Groovebox / Meum spatial form:

$$\Phi(x,y,z)=\frac{q}{\sqrt{x^2+y^2+z^2}}$$

The form supplies a compact geometric distance/potential expression for bounded computational fields.

### 3. Wave Propagation & Transform Mapping

Accepted Fourier reference form:

$$\psi(k)=\frac{1}{\sqrt{2\pi}}\int_{-\infty}^{\infty}\psi(x)e^{-ikx}dx$$

Groovebox / Meum bounded spatial form:

$$\psi(x,y,z)=\sum A_n\sin\left(\frac{n\pi x}{L_x}\right)\sin\left(\frac{m\pi y}{L_y}\right)\sin\left(\frac{k\pi z}{L_z}\right)$$

The renderer uses bounded harmonic fields and Meum phase fields for its procedural wave/modulation calculations.

### 4. Dynamic State Transition

Accepted perturbative reference form:

$$E_n=E_n^{(0)}+\langle n|H'|n\rangle+\sum_{k\ne n}\frac{|\langle k|H'|n\rangle|^2}{E_n^{(0)}-E_k^{(0)}}+\cdots$$

Groovebox / Meum state-transition form:

$$S_{t+1}(x,y,z)=\sum_{\mathrm{neighbors}}S_t(x\pm\Delta x,y\pm\Delta y,z\pm\Delta z)\cdot W_{geometry}$$

This is used as a deterministic state-propagation pattern for computational fields and effect/context generation.

### Default canonical operating point

- Adaptive Fit = **50%**
- Phase Lock = **50%**
- Pre-Canonical Sample Morph = **ON**
- Finite/Peak Guard = **ON**
- Global XMOD = **100%**
- Global Input XMOD = **100%**
- Synth/Mod Patch/Write Script/Calc Domain window modulation = **100%**
- User sample branch remains at least **50%** of the local sample-morph blend.

The five Synth Rack controls (Morph, Harmonic Frequency, Chaos, Fold Depth, Harmonic Lattice) are canonical projections when a canonical composition engine is active. The canonical state remains the authoritative project state for save/load/live playback/export.


## V17 — Meum Direct Spatial Math + Canonical Factory Defaults

Groovebox uses the direct x,y,z Meum expressions as canonical mathematical forms. Operator Theory (OT) is an execution/representation handle: when OT is enabled, these expressions route through the OT equivalence kernel; when OT is disabled, the same expressions use ordinary arithmetic. The numerical output of these Meum DSP paths is therefore invariant to the OT toggle.

### 1. Spatial curvature / metric field

The accepted tensor description is represented here by the direct spatial Poisson-style form:

$$\nabla^2 \Psi(x,y,z)=S(x,y,z)$$

The Groovebox implementation samples a bounded scalar field directly over normalized $x,y,z$ coordinates rather than changing a metric tensor.

### 2. Field potential

The direct Meum potential form is:

$$\Phi(x,y,z)=\frac{q}{\sqrt{x^2+y^2+z^2}}$$

The implementation uses this bounded potential term as one component of the Meum spatial audio effect.

### 3. Wave mechanics

The direct bounded standing-wave form is:

$$\psi(x,y,z)=\sum A_n\sin\left(\frac{n\pi x}{L_x}\right)\sin\left(\frac{m\pi y}{L_y}\right)\sin\left(\frac{k\pi z}{L_z}\right)$$

The audio effect uses the first bounded spatial harmonic as its sampled wave component.

### 4. State transitions

The direct neighboring-node form is:

$$S_{t+1}(x,y,z)=\sum_{\mathrm{neighbors}}S_t(x\pm\Delta x,y\pm\Delta y,z\pm\Delta z)\cdot\mathrm{GeometryWeight}$$

The Groovebox effect uses a deterministic adjacent-coordinate state field as the local transition contribution.

These four forms are mathematical expressions/methods used by the engine; they are not claims that the simplified forms replace general relativity, electrodynamics, Fourier analysis, or perturbation theory in physics.

### Canonical factory defaults

The productive default state is intentionally non-neutral: Adaptive Fit = **50%**, Phase Lock = **50%**, Pre-Canonical Sample Morph = **ON**, finite/peak guard = **ON**, and the Global XMOD / Input XMOD / four window modulation controls start at **100%**. The canonical engine can therefore autocompose directly against a seed while empty/default placeholder slots remain useful as remix/writing fallbacks. User sample contribution remains protected at a minimum 50% in the bounded sample-morph bridge.


## Meum Equation Field — ParametricMathBackground

The `ParametricMathBackground` is not decorative placeholder mathematics: its equation cells are a visual index of the same mathematical vocabulary used by Groovebox. Exactly **12 equation cells** are drawn at a time so the field remains readable rather than becoming a wall of formulas. The background is display-only and does not alter audio state.

The current 12-cell field presents these direct forms:

1. **Field potential:** `Φ(x,y,z) = q / √(x²+y²+z²)`
2. **Wave mechanics:** `ψ(x,y,z) = Σ Aₙ sin(nπx/Lₓ) sin(mπy/Lᵧ) sin(kπz/L_z)`
3. **State transition:** `Sₜ₊₁(x,y,z) = Σ_neighbors Sₜ(x±Δx,y±Δy,z±Δz) · W_g`
4. **Spatial curvature/source field:** `∇²Ψ(x,y,z) = S(x,y,z)`
5. **Meum isn:** `isn(x) = 2·sin(x/2)`
6. **Meum ics:** `ics(x) = 2·cos(x/2)`
7. **isn inverse:** `isn⁻¹(y) = 2·asin(y/2)`
8. **ics inverse:** `ics⁻¹(y) = 2·acos(y/2)`
9. **Meum field:** `F_M(x,y,z,t) = isn(M·t+x)·ics(M⁻¹·t+y)+z`
10. **Standing node:** `uₙ = sin(nπx/Lₓ)·sin(mπy/Lᵧ)·sin(kπz/L_z)`
11. **Neighbor weight:** `W_g = 1/(1+√(Δx²+Δy²+Δz²))`
12. **Spatial radius:** `r = √(x²+y²+z²)`

These cells are expressions/methods, not a second hidden computation path. OT may provide an equivalent execution handle for supported operations, while the displayed Meum expressions remain stable.

The project also retains the book-derived `isn`/`ics` family and inverse forms in the executable math layer. The exact source text of the user's book is not bundled in this build; when a book PDF/source is supplied, its additional equations can be added to the 12-cell rotating/indexed field without replacing the existing canonical forms.


## V19 — Canonical Signal Floor + Sequence Wrap/Schedule

- **Canonical signal control invariant:** a single authoritative control scalar is clamped to **50–100%** and is independent of whether an imported carrier exists.
- **User-data floor:** user-owned sample/program data is not silently downmixed to make canonical room; the protected local user branch remains 50%.
- **No-slot rule:** if canonical material has nowhere to write, it creates canonical sequence/automation/AM/FM/PM/envelope/effect structure or uses the seeded global layer instead of rewriting user parameters.
- **Sequence → Playlist mode:** each sequence can be edited as **Wrap to Playlist** or **Schedule Across Playlist**.
- **Force Wrap / Force Schedule:** playlist paint can override the sequence mapping per painted row. Force Schedule permits a sequence to cross/cut through playlist-row boundaries instead of being silently re-fit.
- **Track Offset startup fix:** restores `_on_track_offset_changed` so the v18 Track Offset control no longer aborts application startup.
- **Persistence:** canonical signal control and sequence mapping metadata travel through project save/load.

## V20 — Canonical Control Options + Paint Tempo

Canonical signal control is an invariant 50–100% authority band, but it is **not a naked clamp**. The UI exposes four strategies: Coverage Adaptive, Engine Stack, Full Canonical, and Seeded Baseline. Missing canonical lanes are materialized in canonical-owned runtime overlays rather than rewriting user program slots.

Canonical coverage includes sequence, automation, pitch, amp, phase, trigger, AM, FM, PM, and a canonical effect layer. Canonical-owned synth slots can use direct amp/pitch/phase/trigger values and simultaneous deterministic chord ratios. User-owned program data remains the protected source and is never downmixed merely to create canonical room.

### Paint Tempo

Playlist paint now records a tempo-aware mode: Row Loop / Wrap, Center Snap / Schedule, Retrigger Rows / Schedule, or Canonical Cut / Row Boundaries. Row Loop repeats a sequence to the row duration at the master BPM and cuts at the row boundary. Center Snap schedules the sequence around the middle of the row grid. Retrigger Rows restarts at each row. Canonical Cut allows boundary clipping when the canonical strategy determines that preserving row-local coverage is preferable. Explicit Force Wrap / Force Schedule settings override automatic mapping.

## V23 blend and carrier contract

Groovebox supports multi-target playlist blending. A row may retain multiple `blend_targets` with normalized `blend_weights`, while each target can retain an independent `blend_time_offsets` value in seconds. Operator `operator_time_offsets` remain authoritative render offsets.

Imported audio/video carrier data is a modulation/reference source: Global Input XMOD can use carrier waveform values, synthesized voices can receive 50% carrier phase-reference steering, and Global Convolve can use the carrier as a kernel. The carrier is not an uncontrolled third additive bus.

At the composition boundary the source-coefficient contract is:

`M0 = 0.50*C + 0.50*U`

where `C` is canonical-engine material and `U` is user data after bounded carrier-derived modulation. Thus both source coefficients have a mathematical minimum of 0.50 and sum to 1.00. This is a coefficient invariant, not a post-hardclip RMS/energy theorem.

Project save/load now explicitly persists the playlist blend contract, multi-target data, offsets, canonical control/overlay state, and the measured canonical/user/carrier ledger. Export provenance records the same contract and canonical fingerprint.


### v24 UI / Canonical additions — Wavetable Projector & Automator anchoring

The global Canonical Morph Bridge now lives directly beneath GLOBAL · COMPOSITION CANONICALS in the upper-right canonical deck. Global XMOD, Input XMOD, and the four editor-window modulation depths are kept in the lower editor deck and do not control Master Volume.

The new **GLOBAL WAVETABLE PROJECTOR** provides 1D Wave, 2D Field, and 3D Resonance-inspired representations with phase, curvature, twist, and fold shaping. It is a global wavetable guide for the Master Vector Synth. User field and deterministic canonical guide are blended 50/50; the projector does not replace canonical composition or Master Volume. Its state is project-save/load persistent and is included in the same render/export pathway.

The Automator teleport inspector is anchored at the selected cell's lower boundary midpoint, with Operator, Sequence, and Offset controls remaining attached to the selected automation step.


**Automator timing:** the automation strip now has an explicit **Wrap / Syncopate** mode. Wrap tracks the active Sequencer length and cycles its control points; Syncopate permits an independent polymetric length using the existing ± syncopation control. The selected mode is saved with the project and restored before live rendering/export.


## CANONICAL ACTIVITY HANDOFF — 2026

Groovebox now treats the 50% requirement as an activity/continuation architecture, not a post-mix clamp. Canonical continuation maintains an autonomous mathematical stream after user input ceases. Shared user/canonical coordinates include time, rhythm, pitch, envelope, phase, and modulation. The canonical activity ledger records coverage separately from the 0.50/0.50 composition coefficients. The imported carrier remains a modulation/reference source rather than an uncontrolled third additive bus.

The project snapshot persists canonical continuation state and its activity ledger so save/load/export provenance retains the same model. The activity metric is not a claim of 50% final RMS after nonlinear processing; clipping and nonlinear effects can change energy.


## Algorithm XMOD + Per-Sequence Algorithm Editing (2026)
- **Edit Algorithm Per Sequence** forces the number-theoretic step algorithm to address only the selected instrument and selected sequence.
- **Algorithm XMOD Local 0–200%** controls algorithmic cross-modulation for the active local instrument/sequence.
- **Algorithm XMOD Global 0–200%** controls the global algorithmic cross-modulation depth across the composition.
- The two controls are independent and saved/restored with the project; 100% is neutral.
- The existing global/user XMOD and imported-carrier Input XMOD remain separate from Algorithm XMOD.
- The Global Wavetable Projector is a shared 1D/2D/3D guide feeding Master Vector; its user/canonical guide remains a 50/50 structural blend.


### Meum Spatial Activity Resolution (v28)

Groovebox now includes a direct X/Y/Z activity-field resolver between the canonical and user buses. The resolver uses explicit orthogonal coordinates and local neighbor propagation as a deterministic composition mechanism. It compares canonical and user activity with an L1 activity modulus and structurally expands the canonical branch to the user activity modulus when needed before the fixed 50/50 composition boundary. This is an algorithmic signal-activity invariant, not a final-output limiter.

Shared user/canonical features are tracked across 12 coordinates: time, rhythm, pitch, envelope, phase, modulation, tempo, AM, FM, PM, wavetable/vector, and playlist mapping.

`Edit Algorithm Per Sequence` forces the number-theoretic step algorithm to write only the currently selected instrument + selected sequence. `Algorithm XMOD Local 0–200%` and `Algorithm XMOD Global 0–200%` independently control the local/global algorithmic cross-modulation depth.

# V34 — MEUM CALCULUS 50% → 100% PROOF, UI COLOR/LEGIBILITY PASS, MEDIA + OFFSET AUDIT

## The 50% floor and the 100% ceiling are now separately proven

Groovebox now records a deterministic, machine-checkable `canonical_range_proof` in its project/export provenance. The proof distinguishes three different invariants that must not be conflated:

1. **Canonical authority range:** the canonical control is structurally constrained to `0.50 ≤ S ≤ 1.00`.
2. **User-data floor:** the protected user branch remains a 0.50 coefficient at the composition boundary.
3. **Final audio energy:** this is deliberately *not* claimed to be a 50% RMS theorem after nonlinear processing.

The named canonical strategies are now documented and tested as:

- `Seeded Baseline` → **50%** minimum.
- `Engine Stack` → **50–100%**, reaching **100%** at five active canonical engines.
- `Full Canonical` → **100%** ceiling by explicit strategy.
- `Coverage Adaptive` → **50–100%**, with sequence, automation, modulation and active-engine coverage contributing authority rather than silently stealing user slots.

The composition boundary remains exactly:

`M0 = 0.50 · C + 0.50 · U`

That equation proves the source coefficients. It does **not** say that nonlinear EQR, Master Vector conversion, hard clipping, or other later transformations preserve equal RMS energy. Master Volume remains the final user-controlled gain and is not secretly manipulated by canonical authority.

## Meum Calculus / spatial activity proof

The Meum Spatial Activity Resolution layer is now part of the documented proof chain. It uses direct orthogonal coordinates:

- `x` = temporal position
- `y` = normalized user amplitude/activity
- `z` = normalized local gradient

The temporal field receives a deterministic three-sample local propagation `(left + center + right)/3`, representing the reduced one-dimensional form of the requested neighbor idea. The canonical field is then compared with the user field through an L1 activity modulus. If canonical L1 activity is below user L1 activity, the canonical branch is structurally expanded to the user activity level **before** the fixed 50/50 composition boundary; the user bus itself is not rewritten.

This is a **procedural Meum field mechanism**, not a claim to solve physical Navier–Stokes. The mathematical distinction matters: the system borrows the user's loss/neighbor/vector intuition while remaining deterministic, bounded and auditable inside the music engine.

A deterministic 2048-sample proof vector currently gives approximately **64.516% canonical activity modulus**, above the 50% floor. The proof is stored as `meum_spatial_activity_modulus` and `meum_spatial_loss` in the canonical ledger.

## 100% shared feature completeness

The user/canonical shared feature plane is now explicitly twelve-dimensional:

`time, rhythm, pitch, envelope, phase, modulation, tempo, AM, FM, PM, wavetable_vector, playlist_mapping`

The ledger records `shared_feature_count = 12` and `shared_feature_completeness = 1.0` (**100% of the defined shared-feature plane**).

This 100% is a feature-coverage claim, not an assertion that every possible audio property in existence is controlled.

## Automation / Step Teleport contract

The Automator teleport inspector is now a real two-row editor rather than a cramped status strip. First click selects and teleports; second click toggles ON/OFF. The inspector exposes:

- Target Operator
- Target Sequence index (1–128)
- Morph 0–100%
- Sequence Attack 0–100%
- Sequence Release 0–100%
- Offset roller −1024…+1024 steps

The target sequence's synth/panel state and sequence envelope are the morph destination. Changes are written into the automation point/target sequence rather than being visual-only.

The main Step Sequencer teleport popup and the Automator popup are now explicitly **static after selection**. Horizontal scrollbar motion does not repeatedly reposition the popup, and the step editor no longer calls `ensureWidgetVisible()` during popup positioning.

## Canonical Morph Bridge workspace

The Canonical Morph Bridge is no longer duplicated in the narrow global side column. It is a dominant lower-deck panel with three explicit rows and an expanding horizontal footprint, allowing the right-hand blank workspace to become usable editing space instead of clipping the bridge in place.

## Track Offset is a real render input

`Track Offset` is persisted per sequence/instrument, exposes a continuous `−16 … +16` row-unit control, and is applied in the render timeline before the per-step offset. Save/load and export provenance retain the value.

## Multiformat audio/video inputs

The media decoder uses FFmpeg for non-WAV media and now advertises common audio and video containers including:

- Audio: WAV, MP3, FLAC, OGG/OGA, M4A, AAC, AIFF/AIF, OPUS, CAF, ALAC, WMA, APE, WV.
- Video: MP4, MOV, MKV, WEBM, AVI, M4V, MPEG/MPG, FLV, TS/M2TS/MTS, 3GP/3G2, OGV, VOB.

A global carrier may use audio directly or the decoded audio stream of a video. Each selected instrument can independently own an imported audio **or video** source. Per-instrument video inputs retain `video_path`, `video_input_enabled`, `source_kind`, decoded waveform and user ownership through project save/load. The source participates in the same 50% user-data sample morph before canonical composition.

## UI visual language — no generic white/grey control theme

The V34 visual pass removes generic white/grey control defaults from the main application stylesheet. Sliders, spin boxes, combo boxes, labels, tables, headers, buttons, progress bars and text fields now use functional colors rather than default white/grey treatment. Gold/amber marks authority and important values; cyan/teal marks editable data and routing; violet/blue marks mathematical/canonical systems; green marks active/play/randomization; red-brown marks Automator state and warning/danger functions.

**Master Volume is deliberately dominant:** its title and value are **24pt yellorange/amber**, its slider is wider and taller, and its handle is enlarged. Canonical processing never writes to Master Volume.

## Seed / Help / README placement

The global Seed editor is explicitly top-anchored and compact enough to keep `🎲 Random Seed Script` and `❓ README / Help` visible at the top of the global workspace. The seed remains user-controlled; the Random Seed button creates example scripts but does not silently overwrite a user's seed on startup.

## Today’s feature chain

V34 retains the work from the current development pass: Meum Spatial Activity Resolution; canonical 50–100% strategy control; autonomous canonical continuation; 12-feature shared plane; Algorithm XMOD global/local controls; Edit Algorithm Per Sequence; sequence Wrap/Schedule and Paint Tempo modes; multi-target playlist blending and time offsets; carrier-as-modulation/reference rather than a third additive bus; 50/50 user-sample morphing; Wavetable Projector; Master Vector Synth; sequence-wide attack/release follow; canonical amp/pitch/phase/trigger/chord material; static Step/Automator teleport inspectors; Track Offset; multiformat media decoding; per-instrument video/audio inputs; project save/load; and export provenance.


--------------------------------------------------------------------------------
V34 — 50%→100% VERIFIED RANGE / MEUM CALCULUS
--------------------------------------------------------------------------------

The canonical authority range is a real bounded control interval, not a label:

  S ∈ [0.50, 1.00]

  Seeded Baseline       = 0.50
  Engine Stack (n)      = min(1.00, 0.50 + 0.10 n)
  Coverage Adaptive     = 0.50 … 1.00
  Full Canonical        = 1.00 exactly

Therefore five active canonical engines reach the 1.00 ceiling, while the
minimum remains 0.50 even with no carrier. The source-composition boundary is
independently fixed as:

  M0 = 0.50 C + 0.50 U

so canonical and userdata each retain a 50% source coefficient at the linear
composition boundary. The 100% maximum refers to canonical control/authority;
it is NOT a claim of 100% post-effect RMS energy after nonlinear processing.

MEUM CALCULUS / SPATIAL ACTIVITY
  Direct X/Y/Z coordinates track temporal position, normalized user activity,
  and local gradient. Neighbor propagation uses a deterministic six-neighbor-like
  temporal reduction; the canonical field is expanded to at least the user L1
  activity when necessary before the 50/50 boundary. This gives a measurable
  activity modulus of at least 0.50 without a final-output clamp. It is a
  procedural Meum field construction, not a physical Navier–Stokes solver.

SHARED FEATURE COMPLETENESS = 100%
  time, rhythm, pitch, envelope, phase, modulation, tempo, AM, FM, PM,
  wavetable_vector, playlist_mapping

MEDIA / TIMELINE IMPLEMENTATION
  Track Offset: per-instrument/per-sequence −16…+16 playlist-row units,
  persisted and applied before per-step offsets.
  Audio inputs: WAV, MP3, FLAC, OGG/OGA, M4A, AAC, AIFF/AIF, OPUS, CAF,
  ALAC, WMA, APE, WV.
  Video inputs: MP4, MOV, MKV, WEBM, AVI, M4V, MPEG/MPG, FLV, TS/M2TS/MTS,
  3GP/3G2, OGV, VOB. Each instrument may retain its own media source; video
  sources retain video_path/source_kind/video_input_enabled and their audio
  stream can enter the user sample/canonical morph path.

UI AUDIT V34
  Master Volume title/value = 24pt yellorange/amber. Generic white/grey control
  defaults were removed from the main palette. Sliders use amber/teal rails and
  handles; spin boxes and combos use blue/teal fields; action states use green,
  amber, violet, cyan, and red-brown semantics. Canonical Morph Bridge is a
  three-row responsive panel. Instrument selection is width-capped so the main
  editor does not become a giant Instrument Windows column.
  Main action text: RANDOMIZE ALL SEQ.
  Step and Automator teleport inspectors are independent top-level Tool windows
  with fixed screen anchors; neither follows the horizontal scroller, and both
  may remain visible simultaneously.


--------------------------------------------------------------------------------
V34 — AUTOMATOR PARAMETER TELEPORT / UI RE-ARCHITECTURE
--------------------------------------------------------------------------------
  The Automator teleport now uses the same two-click selection model as the Step
  Sequencer: first click selects/teleports; second click toggles ON/OFF. The
  inspector is a top-level, non-activating Tool window with an independent screen
  anchor. Two inspectors may remain visible simultaneously and neither follows a
  horizontal scrollbar.

  Editable teleport destination:
    Operator; Sequence 1–128; Morph 0–100%; Sequence Attack 0–100%;
    Sequence Release 0–100%; Offset −1024…+1024; Synth Param; Param Value.
  The source instrument/sequence is frozen at selection, while the destination
  operator/sequence is the morph target. Synth parameter edits are written into
  the selected destination sequence panel, and envelope edits are written into
  that sequence's envelope state.

  UI color audit: white/grey defaults in the main application controls were
  replaced with the Groovebox semantic palette. Amber/yellorange identifies
  master/seed authority, green identifies randomization/active canonical action,
  cyan/teal identifies signal and media pathways, violet identifies Operator
  Theory/math controls, and red-brown identifies Automator state.
  Master Volume remains 24pt yellorange/amber with an enlarged control.
  Instrument context is width-capped and responsive so the editor does not become
  an oversized Instrument Windows panel.


## V34 Stability / Canonical Control Update

- **Canonical Signal Control:** defaults to **100% Full Canonical**. The control remains a 50–100% authority mechanism, separate from final mix gain.
- **Self-correcting canonical coverage:** when required canonical sequence/automation/AM/FM/PM/effect lanes are absent, canonical runtime overlays are materialized instead of lowering authority or overwriting user-owned sequence data.
- **Canonical Resonance / Activity:** independently adjustable **50–150%**. Full user activity targets the 50% floor; user inactivity ramps autonomous canonical activity toward the selected ceiling, with a smoothed handoff.
- **Canonical→Instrument Convolve:** new bounded **0–100%** control. At 100%, canonical material is the full convolution reference, while the transformed user branch retains a direct 50% user component; the fixed `M0 = 0.50*C + 0.50*U` boundary remains intact.
- **Maximum instruments:** increased from 64 to **128** for the active synth/visual ensemble and canonical master identity lattice.
- **Default playlist row length:** **16 beats**.
- **UI initialization:** Master Volume value is now constructed before stylesheet/object-name access, eliminating the `lbl_master_vol` startup AttributeError.

CANONICAL RESONANCE / 50–150% STABILITY PASS (V34)

  • Canonical resonance/activity is an independent 50–150% continuation-drive control; it is not master volume and does not alter the fixed 0.50*C + 0.50*U composition coefficients.
  • Full Canonical signal authority defaults to 100%. Missing canonical lanes are materialized in canonical-owned runtime overlays instead of weakening authority or rewriting user-owned data.
  • 100% canonical→instrument convolution is bounded as a normalized influence transform; the transformed user branch retains a direct 50% user component.
  • Playlist row length defaults to 16 beats; Playlist Rows remains the separate arrangement-row count control.
  • Instrument Count supports 2–128 active instruments; the canonical identity lattice remains 128 slots.
  • V34 removes several direct zero-denominator bypasses and uses explicit invalid/zero cases instead of epsilon values where those cases can occur in live/export paths.
  • Save/load restores canonical resonance and 100% Full Canonical defaults correctly.


## V34 UI / Stability Pass
- Qt stylesheet alpha values use Qt-compatible integer alpha channels; the prior decimal `rgba(...,0.xx)` forms were removed to prevent QPushButton stylesheet parse warnings.
- UI construction order is dependency-safe for the seed panel and master-volume widgets.
- Synth/window launchers, LIVE DJ, and GLOBAL PLAY PATCHER share one horizontal performance deck.
- Automator controls use a compact two-row grid so the controls fit the sequencer window without forcing horizontal overflow.
- Canonical authority defaults to Full Canonical / 100%; missing canonical lanes self-materialize in canonical-owned runtime overlays without rewriting user memory.
- Canonical resonance/activity is independently driven from 50% to 150%, with smooth user-activity handoff and explicit zero cases rather than epsilon denominator bypasses.
- Canonical→Instrument Convolve is independently bounded 0–100%; zero canonical/user inputs are handled explicitly.
- Maximum live instrument capacity is 128; default playlist row duration is 16 beats.
