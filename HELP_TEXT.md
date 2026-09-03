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
17. [Optimization policy](#17-optimization-policy)
18. [Troubleshooting](#18-troubleshooting)
19. [Deprecated/removed behavior](#19-deprecatedremoved-behavior)
20. [OpenCode merge / release contract](#20-opencode-merge--release-contract)
21. [Extended verification checklist](#21-extended-verification-checklist)
22. [Final verification checklist](#22-final-verification-checklist)

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

## 17. Optimization policy

The next optimizations should improve throughput without changing canonical output:

- reuse NumPy/C++ output buffers;
- reduce Python↔C++ boundary crossings by batching voices;
- vectorize C++ transcendental-heavy paths only when output equivalence is tested;
- keep Julia for batch analysis and candidate optimization;
- avoid materializing large tensor matrices when a contraction can be streamed;
- cache invariant seed/identity features per render;
- use deterministic per-voice buffers for parallelism;
- reduce visual geometry density rather than lowering mathematical fidelity;
- keep DJ effects on a separate live bus;
- use partitioned offline rendering to bound peak memory.

**Do not optimize by deleting mathematical structure merely because a visual or audio effect is expensive.** Optimize the representation of the same function.

---

## 18. Troubleshooting

### Audio sounds filtered/resonant

The final master path intentionally does not run the former EQR/PKP/PED spectral/amplitude stack. Check per-voice filter/resonator/formant parameters, Harmonic Lattice, and DJ effects first.

### Visualizer has too many lines

Use sparse projection mode. Geometry density should be bounded by canonical energy/entropy, not by a fixed “draw everything” rule.

### Game has too much GOAVA

GOAVA should be treated as one canonical feature among several. It should modulate topology/tempo/events where useful, not dominate every visual primitive.

### ffmpeg missing

Launchers attempt local/system detection and provisioning. A manually supplied static build can always be placed in `./bin/`.

### Julia missing

The application remains functional with Python+C++. Julia is a numerical/reference layer and is not required for basic realtime operation.

---

## 19. Deprecated/removed behavior

The v3[final] documentation intentionally removes or de-emphasizes obsolete architecture claims:

- no separate legacy master-bus “secret filter” is part of the canonical export path;
- no hard-coded 16-part limit should be treated as a design invariant;
- no claim that GOAVA/audio/visual/game already form one mathematically proven tensor unless a regression test exists;
- no `-ffast-math` canonical build;
- no RNG calls in the realtime canonical callback;
- no requirement that Julia be a realtime process;
- no final-bus normalizer/limiter/EQ silently inserted after canonical composition.

Legacy OT scalar helpers remain available for explicit compatibility/scripts, but the shared equivalence path should preserve canonical scalar results where that is the stated contract.

---

## 20. OpenCode merge / release contract

The v3[final] release incorporates the useful OpenCode work without regressing the established DSP contract:

- dependency-aware desktop/mobile launchers;
- local `bin/` ffmpeg/ffprobe resolution and first-launch provisioning;
- broader seed-language demonstrations, including parametric, cylindrical, multivariate, loop-based, and finite L-function-style samples;
- mathematical channel routing for additional seed variables;
- expanded game/video provenance and deterministic testing;
- additional audit/probe/test utilities;
- native C++ and Julia source references kept beside the Python application.

**Explicit non-regression rule:** the merge must not restore the historical stacked master-bus envelope layering. DJ/per-voice FX are preserved. The distinction is intentional: an effect that the user explicitly enables or routes is a real effect; an unconditional master envelope multiplier is not.

## 21. Extended verification checklist

In addition to the numerical checklist below, release tests should exercise:

- [ ] launch from a clean directory with no system ffmpeg;
- [ ] local `bin/` creation and ffmpeg/ffprobe discovery;
- [ ] Python-only fallback when Julia is absent;
- [ ] C++ acceleration with reference fallback;
- [ ] WAV render with 1, 2, 4, 8, 16, and larger part counts;
- [ ] DJ Boost Hit remains audible when explicitly enabled;
- [ ] GOAVA Pair Morph remains reversible and deterministic;
- [ ] per-voice filter/resonator settings survive save/load;
- [ ] no unconditional master EQR/PKP/PED envelope stage appears in the final waveform path;
- [ ] imported media is accepted according to ffmpeg decoder capability;
- [ ] initial track-step offset survives canonical fingerprinting and project reload.

## 22. Final verification checklist

Before shipping an export-ready build:

- [ ] Python syntax passes.
- [ ] C++ shared library builds on the target OS.
- [ ] Native symbols load.
- [ ] Native/reference audio tests match.
- [ ] OT tensor-equivalence tests match.
- [ ] Seed normalizer tests pass.
- [ ] Partitioned WAV render concatenates bit-identically to the unpartitioned reference.
- [ ] Partitioned video preserves frame order and final duration.
- [ ] ffmpeg + ffprobe are discoverable locally.
- [ ] Media import accepts codec-supported formats.
- [ ] Initial track offset is serialized and restored.
- [ ] Game record/replay reproduces canonical world identity.
- [ ] Provenance/fingerprint survives export/import.
- [ ] Fresh-launch provisioning creates `bin/` and native directories without manual debugging.

---

## License / project policy

Keep the project-specific license and attribution files supplied with the distribution. This README describes implementation behavior; it is not a scientific claim that the mathematical metaphors used by the project constitute established mathematics. Where a result is called “proven,” the project should include a reproducible numerical test and raw-output comparison.
