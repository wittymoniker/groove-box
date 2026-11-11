# Release notes moved out of the README (2026-11-10)

Kept verbatim for history.

> **R28.4.50 HF16 cross-platform media diagnostics (2026-10-27):** current guidance covers Windows, macOS, Linux/Fedora, sOS/ISO, and the mobile helper path. This source archive includes a read-only platform/audio diagnostic utility and updated audio/video troubleshooting guidance. It is not a substitute for native OS CI or physical-hardware certification; see the HF15 section below for exact boundaries.

---

## Safe V3 merge, 2026-11-05

The working V3 GUI is retained, with compatible features selected from the two comparison archives. See [the safe-merge release notes](RELEASE-NOTES-SAFE-V3-MERGE.md) for layout/features, build commands and validation limits, and [threading and sCode options](THREADING-AND-SCODE-OPTIONS.md) for further optimization ideas with pros and cons.

`BUILD_ISO` and `BUILD_KIT` share a root runtime-module inventory. Run `bash BUILD_ISO/sync_overlay_from_root.sh` after source edits and `bash RUN_ME_ZERO_STATE.sh --check` for the non-installing source/boot-contract preflight.

The current feature guide is embedded in `ReadmeGuideDialog.HELP_TEXT` in
`groovebox.py` and mirrored in [the full help text](HELP_TEXT.md). It covers the
merged controls, launcher behavior, data/context limits and remaining overhead;
see [launcher and context revision notes](LAUNCHER-AND-CONTEXT-NOTES.md) for this
source revision. No app, verifier suite or release build was run for it.

### HF15 — Cross-platform support and deployment guide

Use the launcher/native package for your operating system and architecture.
Run `python scripts/diagnose_platform.py` with the selected runtime interpreter
for read-only diagnostics, optionally adding `--json groovebox-platform-report.json`
to save a report. Source compatibility and a successful ISO build are not
physical-hardware audio/video certification; the in-app Help and
`PLATFORM_RUNTIME_README.txt` explain deployment and troubleshooting boundaries.

---

## R32.8 — what is proven, the mathematics, and the output dominion

### Measured in this release (offscreen app, real code paths)
| Claim | Result |
|---|---|
| Save → load keeps the workspace | 303 of 312 changed controls restored exactly. Remaining: hardware volume and the find field (not saved on purpose), 6 linked controls recomputed from others (±1 step), the Mod Osc scope-dependent "On". Project 1.08 MB (was 423 MB for a 9,394-row playlist). No control handler took > 1 s |
| Any kind → any kind | **81 / 81** pairs pass (sound, image, video, MIDI, text, data, seed, project, game) after the game-reader fix (9 / 9 game pairs re-run) |
| Symbolic completeness | Any finite note sequence has an exact seed: P = (p₀…p_{L−1}), i = ⌊4t⌋ mod L, f = 440·2^((Pᵢ−69)/12). 200 / 200 random melodies reproduced at every step, max error 0.0 Hz. MIDI → seed now uses it (lossless) |
| Engine sync | project_schema.verify (snapshot → apply → snapshot): every engine's state survives, with defaults and with the Seeded + Euclidean + Phase-Lock engines on |
| Seed determinism | Same seed → bit-identical canonical audio **and** video frames, in one process and across two separate processes (SHA-256 equal); program signature σ and seed_child identical; a different seed differs |
| Lossless compact storage | pack/unpack of a 13.7 MB playlist → 0.11 MB, restored identically |
| Signed updates | Ed25519 implementation equals the RFC 8032 test vector |

### Core equations
* **Constants.** Meum M = 1.1975807343385265188, M⁻¹ = 0.83501677…, MEUM_NORM = (M − 1)/M, φ = (1 + √5)/2.
* **Seed program.** A program P is a pure function of beat time t: v(t) = P(t; env), compiled once and cached by BLAKE2b(P).
  Its signature is σ(P) = BLAKE2b‑64( ⊕ over t∈T of round₁₂(v(t)) ) mod 2³¹, with
  T = {0, ¼, ½, …, 3¾, 6, 8, 12, 16} (20 probes). σ seeds every engine, so two programs that agree only at t = 0 still differ.
* **Sub-seeds.** seed_child(s, l₁…lₙ) = SplitMix64 folded over the labels:
  z ← s ⊕ (h(lᵢ)·γ); z ← z+γ; z ← (z ⊕ z≫30)·c₁; z ← (z ⊕ z≫27)·c₂; s ← z ⊕ z≫31, with γ = 0x9E3779B97F4A7C15.
  Every label changes every output bit, and order matters: one seed addresses every part of a project.
* **Divergence.** For value v, index i, domain salt k and amount a: u = BLAKE2b(v, i, k)/2⁶⁴ ∈ [0,1);
  D(v) = v + (2u − 1)·|v|·a (sign kept). a = 0 is exactly the legacy behaviour; default a = 0.6 only while a canonical engine is on.
* **Automation (canonical lane).** x(b) = clamp(x₀ + A·(c(b) − ½)·(hi − lo)), where c(b) is the seed program at beat b,
  rank-normalised per lane. Applied per playlist row in audio renders and per frame in video renders, so exports equal playback.
* **Instrument Mixer.** gᵢ = 10^(dBᵢ/20) · [not muted] · [soloed or no solo]; canonical mode adds
  dBᵢ += 24·depth·(uᵢ − ½), with uᵢ = BLAKE2b(σ, nameᵢ)/2³².
* **Difference media.** D = A − B (B resampled to A's rate, zero-padded). Exact identity: B + D = A (float WAV).
  Images: D = 128 + (A − B)/2 (signed) or |A − B|.
* **Colour schemes.** One linear map c' = M·c on every UI colour (and optionally video). Daltonised schemes:
  M = I + S·(I − Sim), where Sim is the Machado 2009 simulation matrix and S moves the lost contrast into the channels still seen.
* **RAM tier.** tier = small (< 6 GB) · medium (< 14 GB) · large. Budget B = RAM·p. Export workers ≤ ⌊B / 1.5 GB⌋;
  all sizes halve when MemAvailable < 12 % of RAM.

### Is it "a fractal of all ways to make music from seeds"? — what is proven, precisely
1. **Self-similar.** Every part of a project (instrument, sequence, engine, frame, game object) gets its seed from its
   parent by one rule, seed_child(s, label) (SplitMix64): the same map at every scale, so the seed tree is self-similar.
2. **Deterministic.** Same seed → bit-identical audio and frames (measured, in-process and across processes).
3. **Complete for symbolic music.** Every finite note sequence — every melody, rhythm, or MIDI file on a 16th grid — is
   exactly some seed program (the table form above; measured 200 / 200, 0.0 Hz error). So the seed space contains
   *all* discrete music, not only the music the canonical engines would invent.
4. **Not claimed:** that every *recorded sound* has a short seed. Audio → seed is a structural estimate; arbitrary
   recordings are reproduced exactly only by the direct converters (and A − B).

### Output dominion (A → seed → B)
* Forward, seed → B, is a pure function: the canonical mixdown and video engine render it, and the same seed + settings give the same
  bytes — measured: identical SHA-256 for audio and frames, re-rendered and in a second process.
* Reverse, A → seed, is a structural estimate: tempo, base pitch, brightness, onset density and a Fourier energy envelope.
  No finite seed reproduces an arbitrary recording sample for sample.
  Exactness where it is possible comes from the direct converters and from A − B.
* Every kind has an in-app editor: Clip Editor (sound / video), Image Editor, MIDI note table, text / data / seed editor
  (with checks), Game Editor, the main window (project), the seed field. "Open result in editor" routes each result to its editor.

### Guidelines
1. Decide with the seed and edit structure on canonical lanes; keep artistic edits on user lanes. The defaults are neutral, so only structural enhancement is heard.
2. To compare two versions, export both and save A − B. Silence or grey means identical.
3. On small machines set the RAM budget (Monitor panel). The tiers keep exports serial and video chunks small.
4. Games keep one savestate each per Groovebox (system store). Delete one or all from the Game Editor. Unpacked game folders are removed when the game exits; stale extracts are swept every 30 minutes.

---

## R28.4.35 — README-HELP rollout

The in-app **README / Help** window now documents the composition contract: normalized 50/50 seed-versus-authored influence; deterministic composition without hidden probability; recursive, resolution-aware fractal structure; a shared canonical timeline for audio, video, and interactive worlds; idempotent imports and provenance; real-time-safe worker behavior; and release-validation boundaries. It also links Tabletime as a companion service and explicitly preserves the Moksha/Karma, scoping, time-delay, and one-credit/one-impression requirements.

See `wasmer-site/` for the refreshed Wasmer-facing product page and `RELEASE-R28.4.35-README-HELP-TABLETIME-20261023.txt` for the rollout summary.
