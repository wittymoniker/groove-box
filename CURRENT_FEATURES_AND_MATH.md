# Mathematician's Groovebox V3 — Current Feature, Math, Hardware & Networking Guide

**Rollout date:** 2026-09-05  
**Design split:** Main Window = precise/scientific Operation Station. Performance = live/touch-friendly GOAVA Radio workspace.

## 1. Canonical zero-state and current defaults

Fresh boot, Clear Memory, and new sequence memory use the same zero-state unless a saved project explicitly supplies another value.

- Playlist / sequence row count: **32**.
- Row length: **8**.
- Step envelope fallback: **50%**.
- Sequence Attack / Release: **50% / 50%**.
- Canonical Resonance: **1.0 = 100%**.
- Canonical→Instrument Convolve: **0.5 = 50%**.
- FullWeight Seed: **ON**, with exact internal dynamic fallback **e−2 = 0.718281828459045…** (the earlier 0.72 operating value refined to an irrational equivalent).
- Canonical adherence / unison fallback: **0.55**; Full Unison ON remains authoritative at unity without destroying the stored fallback.
- EQR: **0.4014**.
- Fractallizer: **0.5995**.
- PKP Envelope: **0.5**.

Meaningful identities remain exact: **0 = off**, **0.5 = symmetric midpoint**, **1 = identity/full unity**. Irrational values are used as secondary modulation/indexing fallbacks only when they reduce short-cycle coincidence or improve phase/traversal coverage without redefining canonical identity.

Useful secondary basis:

- `M−1 = 0.1975807343385265…`
- `1/M = 0.8350167728377339…`
- `2−M = 0.8024192656614735…`
- `(M−1)/M = 0.1649832271622660…`
- `sqrt(2)−1 = 0.4142135623730950…`
- `phi−1 = 0.6180339887498948…`
- `e−2 = 0.7182818284590452…`
- `pi−3 = 0.1415926535897932…`

These do **not** prove that irrational defaults contain more information about a seed. Their engineering role is non-short-period phase/index coverage and deterministic secondary differentiation.

## 2. Reversible writer theorem / implementation contract

All **writing** controls are modeled as independently addressable deterministic contributions rather than destructive cumulative mutations.

`CURRENT = ZERO/USER STATE ⊕ SIMPLIFY(ACTIVE WRITER CONTRIBUTIONS)`

where `⊕` means the appropriate deterministic composition law for the affected state. The operational requirements are:

1. Every writer is a visible ON/OFF toggle.
2. Turning a writer OFF removes **only its own** contribution.
3. Toggle order must not change the final state for the same set of active writers.
4. Turning every writer OFF returns the exact zero/user state from any activation pathway.
5. GLOBAL and LOCAL heuristic scope are mutually exclusive. Switching scope first removes/restores the active writer state, then applies the other scope.
6. Derived writer state is not userdata. Only an explicit Bake / Commit / Scribe-as-User-Data action is allowed to make it user-owned.
7. Common transforms are simplified before evaluation: inverse scale pairs cancel, offsets combine, phase offsets reduce modulo cycle, and compatible multiplicative weights collapse to one factor. Provenance remains separate from the simplified numerical transform.

This is a software determinism contract, not an independently established mathematical theorem.

## 3. Heuristic composition

The single **HEURISTIC WRITE** control has GLOBAL / LOCAL scope and reversible ON/OFF state.

- **GLOBAL:** transcribes the selected seed-derived heuristic across the applicable sequence and automation space.
- **LOCAL:** writes only to the selected instrument + selected sequence + its automation.
- Families include ℤ-Lattice, Prime/Modular, Farey/Fraction, Tree/Ratio, Geometric, Harmonic, Seed Function, and Hybrid.
- Biases include Balanced, Sparse, Dense, Self-Similar, and T-Independent.
- Continuous heuristic outputs become editable automation; discrete values become deterministic sequence structure.

## 4. Draw / Signal Lab

Performance includes a real **Draw / Signal Lab** rather than only the synth-editor wavetable canvas.

- **Carrier:** draw a literal audio carrier waveform.
- **Sample:** draw/save literal sample audio.
- **Program:** draw explicit mapped control data.
- **Tuning:** draw derived tuning/modulation data; it remains non-userdata unless explicitly baked.
- Save drawn audio to WAV.
- Send a derived carrier globally or to the selected instrument.
- Analyze a selected reference with the reverse-engineering descriptor engine.
- Detect a candidate **Fundamental Loop**.
- Derive non-destructive **Sounds Like**, **Harmonic Complement**, and **Opposite** transforms.

The original per-instrument freehand WavetableCanvas remains available in Edit Synth.

## 5. GOAVA and Meum framework

The project defines the Meum constant as:

`M = 1.1975807343385265188…`

with project-use forms including `M−1`, `1/M`, powers of M, normalized ratios, Meum phase fields, and the user-defined `isn` / `ics` family. In the current implementation/documentation:

- `isn(theta) = 2 sin(theta/2)`
- `isn^-1(y) = 2 asin(y/2)` on its real-domain branch
- `ics(theta) = 2 cos(theta/2)`
- `ics^-1(y) = 2 acos(y/2)` on its real-domain branch

The user's Equation-of-Reality / P-E-D framework, operator-theory mappings, ℤ-Lattice language, GOAVA numeric transduction, and Meum calculus are **project-defined mathematical hypotheses/frameworks**. Where the UI/help uses terms such as “claimed exact,” that means exact **under the project's stated definitions and implementation contract**, not a claim of independent mathematical or physical validation.

GOAVA uses numeric seed structure as a deterministic composition/modulation source shared across audio, visuals, and game-state fingerprints. The implementation seeks seed-to-signal congruence and deterministic replay; numerical tests verify software invariants, not universal number-theory truth.

## 6. Main GUI and GOAVA Radio identity

The GUI now uses a coherent dark scientific palette with cyan signal accents, gold mathematical/GOAVA identity, red for GLOBAL editing authority, white/light styling for LOCAL context, and symbols on performance/navigation controls. A generated **GOAVA Radio** visual identity is packaged in `assets/` and used by the Main Window and Performance workspace.

- GLOBAL PLAY / ALL INSTRUMENTS is intentionally large and red.
- LOCAL CONTEXT / SELECTED INSTRUMENT is intentionally large and white/light.
- Global Processor Controls typography is enlarged.
- Value rollers/spin boxes/dropdowns are guarded against accidental mouse-wheel changes while the containing page is being scrolled; deliberate focus/editing still permits value changes.
- Performance is non-modal and can be docked/floated while the scientific editor remains active.

## 7. Hardware / Groovebox OS contract

Groovebox OS is **not touch-only**. Keyboard, mouse/trackpad and touchscreen coexist.

Performance → **Hardware** reports OS-visible input devices, displays, audio devices, MIDI inputs, USB entries, connected Bluetooth devices and key system tools. Device discovery is read-only and cannot alter canonical composition identity.

Hardware layers supported when the underlying OS exposes them:

- USB/Bluetooth keyboards and mice/trackpads.
- Touchscreens/digitizers through Qt + the Linux input stack.
- Gamepads/joysticks/controllers exposed through the OS/game runtime.
- HDMI/VGA/USB displays; DisplayLink-class devices work when their OS driver exposes a display.
- PipeWire/Pulse/default audio targets, USB audio, HDMI audio, already-paired Bluetooth audio.
- Microphone/audio input through the app's sounddevice-compatible paths where available.
- MIDI input when the optional MIDI backend is installed and the OS exposes the device.
- Local FFmpeg/ffprobe and mpv/VLC/ffplay playback helpers.

Hot-plugging/routing is deliberately separated from canonical math: reconnecting a display, controller, audio sink, or network interface does not change the seed/composition fingerprint.

## 8. Performance media and VLC

External-player launch prefers mpv, then VLC, then ffplay. VLC is launched with an independent-instance mode instead of `--play-and-exit`; loop playback uses VLC's loop option. A deferred process check reports immediate launch failure rather than silently hiding it.

Performance includes mixed-media playlist playback, cutups, pitch normalization, deterministic beat/file cutting, live parametric remix, Draw/Signal Lab, device routing, Wi-Fi/LAN TV output, Drive/Clone transport, box-mode readiness, and batch re-rendering.

## 9. Local Wi-Fi / Ethernet game networking

Generated games already contain an authoritative TCP transport. This rollout exposes it directly in **Performance → Game / Wi-Fi** and in the Main Window live-game launcher.

- **Solo** — local game only.
- **Host on local network** — bind a selected TCP port and authoritatively broadcast player/world snapshots.
- **Join local network** — connect to `host-ip:port` on the same Wi-Fi/Ethernet network.
- `--host --port=N` and `--connect=HOST:PORT` remain supported by exported launchers.
- Host/join can be forced even if a seed originally classified the social mode as single-player; requesting network mode makes the runtime network-capable for that session.
- This is live synchronized game state, not merely game-ZIP sharing.
- Internet play may require router/firewall configuration; ordinary same-LAN play does not require a public server.

## 10. Practical first-run workflow

1. Start Groovebox and choose **GLOBAL PLAY** for project-wide work or **LOCAL CONTEXT** for the selected instrument/sequence.
2. Enter a seed/script. Fresh startup uses 32 rows × 8 steps with 50% step envelopes and 50/50 sequence attack/release.
3. Press Play/Render for the canonical result. Secondary engines are identity-preserving/derived unless explicitly committed.
4. Use HEURISTIC WRITE in GLOBAL or LOCAL scope; toggle it back OFF to recover the underlying state exactly.
5. Open **Performance · GOAVA Radio** for playlist/media, live cutups, Draw/Signal Lab, hardware, output routing, Drive/Clone and game networking.
6. In Game / Wi-Fi choose Solo, Host, or Join. The host machine displays/uses its LAN address; clients enter that address and port.
7. Use Device Manager / Hardware to confirm HDMI/audio/touch/keyboard/controller visibility before installation deployment.
8. Save the project to preserve explicit userdata/project state. Derived transient modulation is regenerated deterministically from its seed/state rather than silently becoming userdata.

## 11. Verification scope

The regression suite checks deterministic composition behavior, instrument→visual determinism, media-cutup routing, media-output helpers, and sequence→game influence. A generated-game localhost smoke test also ran a real host and client together; the host accepted one remote and both sessions advanced. GUI interaction and specific physical devices still require real-machine testing because the build environment used to assemble this package does not provide the full PyQt6/hardware stack.

## Program Identity + portable .MG artifacts (2026-09-05)

### Read Program → ID
`⌬ Read Program → ID` computes two separate identities:
- **Program ID**: semantic/structural identity. Python is normalized through its AST so ordinary whitespace, comments, and docstrings do not create a new Program ID; meaningful executable/code-structure changes do.
- **Exact source SHA-256**: byte-for-byte identity for verification and archival comparison.
ZIP packages are fingerprinted from normalized member content, so repacking/path changes do not automatically redefine the semantic program.

### .MG Project / Synth / Profile
Groovebox can export and load three portable artifact kinds:
- `.MGproject` → full project snapshot, loaded into the Main project state.
- `.MGsynth` → one selected synth/instrument snapshot, loaded into the currently selected instrument slot while preserving the artifact's own stable identity/provenance separately from the slot name/index.
- `.MGprofile` → reusable Performance/global/reference settings profile, loaded into the relevant Performance/global settings state.

Each .MG carries an **Artifact ID**, Program ID provenance, Composition ID provenance, integrity digest, tags, and a separate mutable analytics ledger. The artifact identity is derived from saved content; longitudinal statistics do **not** change the Artifact ID.

### Longitudinal use + related results
The analytics ledger may accumulate load/use counts, first/last-use times, companion/co-use counts, and outcome summaries. The software can scan Projects/Samples/Exports and rank related .MG artifacts from:
1. shared Program ID,
2. shared Composition ID,
3. tag/math/provenance overlap,
4. numeric parameter similarity,
5. repeated co-use / companion history.
The score is advisory and non-destructive. It never silently rewrites canonical/user data or artifact identity.

Performance includes **⌬ .MG Related**, which scans the library, displays longitudinal statistics, loads a selected artifact into its appropriate slot, and surfaces related/common-result candidates.


## GOAVA Radio responsive UI + LAN radio (2026-09-05)

- The configurable Radio identity header sits **above GLOBAL PROCESSOR CONTROLS**. Station name and logo are stored in Groovebox application data (`radio_identity.json` plus a copied `radio_logo.*`), so changing radio branding does not alter Program ID, Composition ID, or `.MG` artifact identity.
- GLOBAL PLAY remains red and LOCAL CONTEXT remains white, but the selector footprint is reduced by about 17% from the earlier oversized playtest control.
- PLAYLIST, RANDOMIZE, PHASE-LOCK and GOAVA are equal-footprint primary canonical controls designed to expand across the available row.
- Performance uses a softer rounded control palette and a vertical tab/navigation rail so tabs do not overflow the right margin.
- Performance → Live Broadcast can start **GOAVA LAN Radio**. The station serves a browser page and a continuous **192 kbps MP3** stream on TCP 8780; it cycles local project/render/sample audio and emits low-level 432-Hz-family bleeps when no suitable audio exists.
- Nearby Groovebox radios announce/listen over local UDP discovery; discovered station names and web URLs are shown in-app and on the station web page. Discovery works only across network segments that permit local broadcast; Wi-Fi radio range alone is not sufficient unless devices are associated with the same reachable LAN.
- For an appliance where `http://device/` is desired, `DEPLOYMENT_KIT/enable_radio_port80.sh` (installed as `groovebox-radio-port80`) can create a root-owned TCP/80 redirect to the unprivileged radio service. This avoids running the GUI as root.

## OS hardware dependency preflight

`DEPLOYMENT_KIT/bin/groovebox-hardware-preflight` reports Wi-Fi, Bluetooth, ALSA/PipeWire, MIDI, touch/input, USB, video/VLC and Python runtime readiness. `DEPLOYMENT_KIT/install_detected_hardware.sh` installs common host packages when Internet access is available and falls back to an offline report when it is not. The normal existing-Linux appliance installer invokes this best-effort preflight automatically.


## 2026-09-05 — Meum + Operator Theory + Isosceles-Trig integration

Groovebox now treats the author's mathematical writing as a **selectable creative/analytic dialect** for deterministic indexing. It does not silently redefine ordinary Python/IEEE arithmetic. The implementation is designed so these transforms can be inspected, disabled, simplified and reversed.

### Meum basis
The principal constant used by the engine is `M = 1.1975807343…`. The default modulation vocabulary includes `M-1`, `1/M`, `2-M`, `(M-1)/M`, plus independent irrational traversals `e-2`, `phi-1`, `sqrt(2)-1`, and `pi-3`. Meaningful identity values `0`, `0.5`, and `1` remain unchanged when they mean OFF, symmetry, or unity.

### Isosceles trigonometry
The book defines inverse isosceles sine as `isn^-1(x) = 2 asin(x/2)`. Groovebox also exposes the inverse-pair coordinate `isn(theta)=2 sin(theta/2)` for bounded seed phase mapping. `ics/ics^-1` are kept as handedness-aware complementary coordinates for spatial/game modulation. These functions are used for *indexing and geometry*; they do not overwrite ordinary `sin/cos` globally.

### Operator Theory (OT)
For reversible transforms, Groovebox implements the book's stated symbolic inverse pairing: add↔subtract, multiply↔divide, power↔root, with operation order reversed for an inverse path. This is especially useful for the writer-toggle zero-state rule: active transforms are collected, simplified to one canonical transform, evaluated once, and their provenance is preserved separately.

### Temporal Seed Dynamics
Generated games now include deterministic **Build → Modulate → Stabilize** epochs. Their boundaries use Meum-derived proportions and their field values use the isosceles phase mapping. This adds evolving seed character without activation-history dependence.

### Numerical gameplay identity
Items, actions, events and starter-world elements now receive deterministic numeric sound signatures from seed + semantic label + Meum/isosceles indexing. Frequencies, durations and harmonic counts are inspectable, repeatable and tied to the generated identity instead of random sound assignment.

### Longitudinal .MG history
`.MGproject`, `.MGsynth` and `.MGprofile` analytics remain separate from Artifact ID. History may now be **compressed** (retain strongest companion relations and summaries) or **cleared** without changing the saved program/synth/profile identity. Clearing can preserve aggregate totals so long-term statistics can be retained without carrying detailed co-use history.

### Source framing
The in-app math help preserves the terminology and claims of the author's supplied papers as author-defined/theoretical material. Groovebox uses these ideas as deterministic compositional and geometric transforms; this software implementation is not itself an external proof of the broader mathematical or physical claims.

## Universal Field / part-count invariance (2026-09-05)
Groovebox now computes a `Universal Field` before instrument, visual-object, game-object, or export-part decomposition.  A part count N is an additive factorization of the same field: each part receives exact rational weight `1/N`; reconstruction uses compensated summation and must reproduce the same upstream coordinates within floating-point precision.  Rational anchors (0, 1/2, 1) are used for identity, symmetry, and partitioning.  Irrational ratios (M−1, 1/M, 2−M, (M−1)/M, √2−1, φ−1, e−2, π−3) are used for traversal, phase coverage, and secondary indexing rather than identity partition weights.

The visualizer and game are sibling projections of this field.  The game does not generate visual identity.  Twenty selectable projections are registered: Canonical Geometry, Meum Field, Isosceles/ISN Scope, OT Transform Graph, Phase Torus, Lissajous/Harmonic Orbit, Spectrogram, Partial Constellation, Canonical Delta, Sequence Geometry, Playlist Timeline Terrain, Number-Theory Scope, Fractal/L-System, Complex Plane/Riemann, Wave Surface, Vector/Flow Field, Seed Fingerprint, Network Radio Constellation, Game World Map, and A/V/G Correspondence.  Every projection stores both selected coordinates and the complementary coordinates, so the split is selective/subtractive rather than a new random generation path.

Game logic consumes a game-only projection of the same field for event density, NPC temporal variation, remote/world motion scaling, lighting/activity metadata, terrain/map state, and A/V/G correspondence.  None of these values accept instrument count as an identity input.

`.MG` history maintenance now includes Export History (JSON/CSV/HTML) as well as Compress History and Clear History.  Export is read-only and includes Artifact ID, Program ID, Composition ID, timestamps, aggregates, companion/co-use data, outcomes, and compression/clear metadata without changing the source artifact or Artifact ID.

## Total Correspondence / Self-Procedure
The Universal Field now emits a self-procedure plan and a five-domain correspondence manifest (audio, visual, game, UI, network). Representation counts are downstream work/detail choices and are explicitly excluded from canonical field identity. A greedy visual projection cover minimizes redundant display dimensions while each selective/subtractive projection retains an exact complement. Correspondence diagnostics distinguish exact shared identity/provenance from lossy-domain invertibility.
