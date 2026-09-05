# V3 Dynamic Canonical Playtest Defaults

Authoritative playtest startup / Clear Memory baseline:

- FullWeight Seed: ON
- Seed transduction weight: 0.72
- Full Unison: ON
- Canonical adherence / unison fallback when Full Unison is OFF: 0.55
- Canonical Resonance: 1.00 (100% unity)
- Canonical -> Instrument Convolve: 0.50 (50% midpoint)
- EQR: 0.4014
- Fractallizer: 0.5995
- PKP Envelope: 0.5000

Design rule: non-unity secondary values provide dynamic/spectral headroom but remain downstream of canonical identity. Disabling a secondary removes its contribution; these values must not act as hidden always-on authorities or write derived state into userdata.

EQR and Fractallizer use high-resolution percentage spin controls so 0.4014 and 0.5995 are represented exactly as 40.14% and 59.95% rather than rounded integer sliders.


---

# CURRENT V3 ROLLOUT APPENDIX
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
