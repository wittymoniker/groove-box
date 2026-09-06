# Groovebox v3[final] — Canonical Trio Engine

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

Groovebox v3[final] is a deterministic mathematical composition environment with three synchronized output domains:

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

## 18. MEUM CALCULUS — DEFINITIONS, OPERATIONS, AND EXAMPLES

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
