

## V34 Stability Pass

- Reversible randomizer toggle contract: ON captures a full project baseline and generates a fresh variation; OFF restores the exact pre-randomize state; each subsequent ON cycle rerandomizes and shifts the control color palette.
- Canonical Signal Control defaults to Full Canonical / 100% authority and self-heals missing canonical coverage through canonical-owned runtime overlays without rewriting user data.
- Canonical Resonance / Activity is 50–150%, independent of the 50/50 source coefficients; 150% is activity/continuation drive, not output volume.
- Canonical→Instrument convolution influence is 0–100%.
- Maximum active instruments: 128. Default Step Sequence Length: 12 steps. Default Automation Sequence Length: 12 steps. Playlist row duration remains 8 beats; Playlist Rows defaults to 32.
- ParametricMathBackground is integrated with a deep navy gradient field.
- Performance controls are consolidated into one horizontal deck; Automator controls are compacted into a multi-row grid.
- UI initialization order and Qt stylesheet declarations were hardened; division-by-zero-sensitive paths use explicit degenerate-case handling rather than epsilon denominators where practical.


--------------------------------------------------------------------------------
FULL GRAPH SCRIPT CONTEXT — SEED / INSTRUMENT / ALGORITHM / DOMAIN / AV / GAME
--------------------------------------------------------------------------------
All programmable graph readers now share one coordinate contract. Old scripts
remain valid (including `evaluate_wave(x, y, z)` and `global_script(t,name,i)`),
but new scripts may read the complete graph context at the same evaluation point.

Core variables:
  t, t_norm, x, y, z, seed, seed_w, graph, graph_vector
  graph_x, graph_y, graph_z, graph_scalar, graph_radius, graph_angle
  graph_energy, graph_curvature, graph_phase, graph_u, graph_v, graph_w
  graph_index, graph_count, graph_slot, sequence_index, step_index
  domain_value, domain_weight, graph_id, domain_id, bpm, sample_rate

`graph` is the same context as an attribute/dictionary view (for example
`graph.x`, `graph.energy`). A script may still return one scalar, or may
return named channels such as `wave`, `amp`, `pitch`, `pan`, `x`, `y`, `z`,
`opacity`, `scale`, `rotation`, `drive`, `speed`, and `world_z`. Consumers use
only channels that make sense for them; extra channels are harmless.

Cross-media rule: the graph is sampled as a varying mathematical object rather
than being prematurely collapsed to one seed number. Instrument and applied
Algorithm scripts can therefore influence actual sound, video/scenograph
geometry, and generated-game audiovisual/gameplay fields from the same graph
coordinate. Domain values are resolved at that coordinate too. While a Domain equation evaluates
itself, `domain_value` is 0 to prevent recursive/order-dependent self-feedback;
downstream Instrument/Algorithm/AV/Game scripts receive the final blended value.

Canonical/writer rule: Canonical sequence payloads carry the Instrument Script,
the `full_graph_v1` contract, and the public graph-variable list. Seeded/Canonical
writers, Random Seed, Global Algorithm randomization, Randomize All/Rand Params,
and Heuristic Write to Seq Synth may author multivariate/time-varying graph
programs. Stock/engine-authored Instrument Scripts may be upgraded; user-authored
Instrument Scripts are not replaced by these writers.

RAND PARAM is now itself an authored full-graph performance program. It is
pre-evaluated on the control/row lattice so realtime audio reads cached scalars
instead of parsing Python in the PortAudio callback. The same authored program
is saved/loaded and is exported to video/game composition metadata.

Examples:

    def evaluate_wave(x, y, z, t=0.0, t_norm=0.0, graph=None):
        field = sin(graph_x*MEUM + graph_y*PHI + graph_phase)
        return {'wave': field, 'amp': 0.7 + 0.3*graph_u,
                'pitch': 1.0 + 0.1*graph_curvature,
                'pan': 2*graph_v-1, 'opacity': graph_energy}

    def global_script(t, name, i, graph=None):
        v = isn(graph_radius*MEUM + t*tau) + domain_value*0.2
        return {'drive': v, 'rotation': graph_angle,
                'speed': 0.8 + 0.4*graph_w, 'world_z': graph_z}

Compatibility: scalar-only scripts and the previous function signatures are
still accepted. Full-graph fields add capability; they do not require projects
to be rewritten.

--------------------------------------------------------------------------------
FINITE INFINITY GREP + FINITE INFINITY–MEUM HYPERDRIVE
--------------------------------------------------------------------------------
Groovebox and sCode use the project reference I = 134964356 as a bounded
"Finite Infinity" index space. The compiler/search path can hash normalized
source tokens into 0..I-1 for fast grep-style candidate lookup, then verifies
the exact normalized token before reporting a semantic match. The finite index
is therefore an accelerator/organization mechanism, not a claim that all
mathematical infinity is literally finite.

The optional **Finite Infinity–Meum HyperDrive** is a single cross-media
resonator/drive state shared by SOUND + IMAGE + INTERACTION. It is OFF by
default and is saved with the project.

For a project seed/canonical fingerprint, HyperDrive derives a deterministic
index h modulo I and finite coordinate u=h/I. A Meum phase is formed from u and
time. With Trigonometry Engine ON the modulation uses the project book forms:

    isn(theta) = 2 sin(theta/2)
    ics(theta) = 2 cos(theta/2)

and combines their unit-equivalent components with Meum terms such as M-1 and
1/M. With Trigonometry Engine OFF the compatibility path uses ordinary sin/cos.
With Operator Theory ON the same phase uses the OT orientation/sign rule. Thus
OT/Trig change the calculation route while the seed/fingerprint remains the
single identity source.

HyperDrive then applies the SAME modulation state to:
  • Audio — a pre-hardclip Meum resonator/drive gain field plus a small cubic
    drive curvature. It does not replace Master Volume or the final hard clip.
  • Visuals — deterministic field/brightness and Meum-phase color deformation.
  • Game generation — deterministic world/behavior identity modulation by the
    same finite coordinate; it does not introduce an unrelated random seed.

Drive controls cross-media modulation amount. Resonance controls the Meum
resonator depth and defaults to M-1. HyperDrive, Operator Theory, Trigonometry
Engine, Math Symbols, Meum engine simplification, and the other saved project
controls are restored on load so save→load→audio/video/game uses the same math
configuration.

================================================================================
  GROOVEBOX — Mathematician's / Scientist's Groovebox
  Full Documentation, Scripting Syntax & Design Philosophy
================================================================================
  Main editor and author: Noah Girouard King (Eski)
  Credits: Grok (xAI), Gemini (Google), Claude (Anthropic), ChatGPT (OpenAI),
  Mistral.ai (Mistral), Meta AI (Meta), GitHub Copilot (GitHub),
  Cursor Grok 4.6, jcode(1jehuang), and opencode (anomalyco).

--------------------------------------------------------------------------------
1. GOAL OF THE SOFTWARE
--------------------------------------------------------------------------------
Groovebox uses *mathematical specification* to maximize initial harmonic
diversity while letting you program simple or complicated music with the same
ease:

  • Simple: paint a few pads → Play. Engines fill, phase-lock, and balance
    around your carrier without overwriting it.
  • Complex: domains, scripts, patch topology, seeds, Euclidean lock, and
    fractal randomization scale up without changing the basic model
    (pads, playlist, seed, transport).

Design pillars:
  1) User data is the *carrier wave* — engines add around it; they do not wipe it.
  2) Seeds/constants (including pi, e, and Meum) are geometric anchors. Project theorem MEUM-T1 proves the mathematical Meum root irrational; finite IEEE-754 runtime values remain approximations.
  3) Empty slots are for convergent harmonic fill, not noise dumps.
  4) Redundant definitions are simplified first so fill engines have free capacity.
  5) Only inputs with *net effect* on the playlist timeline are treated as
     protected user data; silent or off-timeline data may be reshaped.

USER NOTE — WHY THE AUTHOR'S MATHEMATICS IS USEFUL HERE
The project author's work is not merely decorative notation. In Groovebox it supplies
a stable vocabulary for deterministic identity, phase/traversal, reversible transforms,
and cross-domain correspondence. That structure has practical engineering value:
repeatable seeds can be cached; the same canonical state can feed audio/visual/game/UI/
network projections; rational partition weights can conserve an upstream identity while
irrational or irrational-candidate traversals can be reserved for ordering and coverage.
The benefit comes from the structure and invariants, not from a claim that one constant
makes a CPU intrinsically faster.


--------------------------------------------------------------------------------
1A. MEUM COMPRESSION / LOGIC SEARCH (PROJECT METHOD)
--------------------------------------------------------------------------------
Groovebox/sCode uses "Meum Compression" as a project-defined semantic reduction
method: preserve the observable/canonical identity while reducing repeated work or
the number of independent obligations. It is NOT ordinary ZIP/audio compression and
it is not a claim that arbitrary information can be reconstructed from a seed.

Current search roles:
  normalize/key logic : (2 - M)·x = [1 - (M - 1)]·x
  locate ambiguity    : x/M, x/M², x/M³
  predict/reflection  : (M - 1)^p·x, normally p = 1..3
  ideal-form compare  : 2^M, with Meum's defining check
                        2^M = M^4 + M^2 - M
The compiler/reverse-grep may also compare the other named irrational constants
from the author's book as candidate coordinates. Numeric proximity alone is only a
locator. A reduction is accepted only after interval/direction, dependency and
behavioral/canonical parity agree. `why()` is intended to retain that provenance.

For cyclic/native state, finite repeated trajectories can additionally be stored as
preperiod + period + certified jump information. The resulting "compression ratio"
reported by native tests is a representation/reuse ratio for that certified cycle,
not a universal data-compression theorem.

--------------------------------------------------------------------------------
1B. PERFORMANCE MEDIA PLAYER + SUPPORTED FILE FORMATS
--------------------------------------------------------------------------------
The Performance button opens a reusable dock. Closing it hides the workspace; pressing
Performance again reopens the same live workspace. It contains the project/render file
browser, playlist/cut-up player, game player, device/output routing, broadcast controls,
DJ remixer and batch re-render tools.

Player routing is deliberately hard-coded and deterministic:
  1. mpv when available (including JSON-IPC for live speed changes),
  2. VLC as the next external-player backend,
  3. ffplay as the final fallback.
The Groovebox composition remains the authority; the player is an output/performance
surface and does not silently rewrite canonical state.

MAIN MEDIA IMPORT — carrier/reference inputs
  Audio: .wav .mp3 .flac .ogg .oga .m4a .aac .aiff .aif .opus .caf
         .alac .wma .ape .wv
  Video: .mp4 .mov .mkv .webm .avi .m4v .mpeg .mpg .flv .ts .m2ts
         .mts .3gp .3g2 .ogv .vob
WAV is read natively when possible; other audio/video decoding routes through FFmpeg.
Video-only files are valid visual carriers and receive a silent carrier stream.

PROJECT / PROGRAM FORMATS
  .MCC       canonical transparent Groovebox composition/project document
  .mgpr      legacy project input compatibility
  .MGproject .MGsynth .MGprofile .MG
             portable artifact identities/profiles/synths
  .zip       generated videogame/software package and reverse-engineering import

MAIN EXPORT MENU
  Audio:       .wav .flac .mp3
  Video+Audio: .mp4 .webm .avi
  Video only:  .mp4 .webm .avi
  Videogame:   .zip
The audio writer/reconversion layer also understands .ogg .opus .caf and .aiff where
the local FFmpeg build supports them. Exports can be written as recoverable `.part`
segments and optionally stitched. Reconvert/Bake-and-Compare recognizes
.wav .flac .mp3 .ogg .opus .caf .aiff .mp4 .webm .avi and .zip.

PERFORMANCE PLAYER BROWSER
  Audio: .wav .flac .mp3 .ogg .opus .aiff .aif .caf .oga .m4a .aac .alac
         .wma .ape .wv
  Video: .mp4 .webm .avi .mov .mkv .m4v .mpeg .mpg .flv .ts .m2ts .mts
         .3gp .3g2 .ogv .vob

--------------------------------------------------------------------------------
2. DISCLAIMER — ADVANCED INSTRUMENT
--------------------------------------------------------------------------------
This is intentionally more advanced than many consumer synthesizers or DAW
step-sequencers. It exposes multivariate equations, domain partitions, modular
patch topology, Euclidean phase geometry, and seed-driven fractal composition.

You do *not* need a research background to start — pads + Play + Export work
immediately. Opening Domain Equations or Instrument Scripts puts you in a
mathematician/scientist-oriented workspace. Expect experimental behavior and
listen critically.

Not a full commercial DAW replacement. Specialized groovebox for exploration,
generative structure, and mathematically guided composition.

--------------------------------------------------------------------------------
3. QUICK START
--------------------------------------------------------------------------------
  1. Set BPM and sequence length.
  2. Select an instrument; toggle PKP pads (cyan = on).
  3. Optional: enter a *non-zero* Seed (blank or 0 / 0.0 = no seed).
  4. Optional: open Playlist and paint operators into the timeline.
  5. Press ▶ Live Audio Play (sounddevice) or Export .wav.
  6. Optional: Euclidean Phase-Lock and/or Seeded Harmonic Randomizer
     to additive-fill empty structure around your carrier.

--------------------------------------------------------------------------------
4. SEED RULES & FULL SCRIPTING
--------------------------------------------------------------------------------
  • Empty field, 0, and 0.0 all mean **no seed** (same treatment).
  • Any non-zero number is a real geometric anchor.
  • Non-numeric text that cannot be evaluated is hashed into a seed token.
  • The seed field is a **full script panel** (scrollable QTextEdit).

  RANDOM SEED BUTTON
  ------------------
  "🎲 Random Seed Script" (directly above the seed field) inserts a new random
  script each click: pure numbers, time-conditional if/elif branches, math in t,
  return-style scripts, or comma-lists of values. Only scripts that evaluate
  cleanly for composition state, several time samples, and all instrument
  indices are inserted (invalid candidates are retried, never emitted).
  Edits remain fully user-owned. See also README.md in the project root.

  COMPOSITION vs TIME-AXIS EVALUATION
  -----------------------------------
  • get_numeric_seed()  — static/global snapshot (t = 0.0). Used for RNG seeding,
    playlist paint, domain bias, and UI fingerprinting. Never call per-sample.
  • evaluate_seed_expression_at_time(script, t, ctx) — render-time T-axis.
    Time-varying scripts (sin(t), if(sin(t)...) elif ..., lists indexed by t)
    modulate the master bus and visual engines during Play / Export.

  ACCEPTED FORMS
  --------------
  Plain number:
      432
      123.45
      (7)

  Math expression (constants + functions; t available):
      sin(t) * 100 + 50
      MEUM * 432
      clamp(sin(t * MEUM) * 200, -100, 100)
      lerp(100, 800, 0.5 + 0.5 * sin(t))

  Python-style ternary:
      1 if sin(t) >= -0.5 else 2

  Shorthand if / elif (balanced parentheses):
      if(sin(t)>=-0.5) 1 elif 2
      if(sin(t * MEUM) * cos(t) > 0) 432 elif 216

  Script-style return (last return wins on multiline):
      return sin(t * MEUM) * 100 + 50
      # comment
      return 1 if t < 1 else 2

  Comma / newline lists — each component is evaluated as a full expression.
  Instruments receive list[i % n] via get_seed_value_for_index(i) (never a
  hash/byte token). Time-axis evaluation still walks the list with t:
      1, 2, 3, 5, 8
      100, 200, MEUM*100, 50+sin(0)
      100
      200
      300

  choose(a, b, c, ..., index_expr):
      choose(100, 200, 300, 400, floor(abs(t * 2)))

  AVAILABLE NAMES
  ---------------
  Functions: sin cos tan sqrt log log2 log10 exp abs min max floor ceil round
             pow hypot atan2 asin acos atan sinh cosh tanh degrees radians
             clamp(v,lo,hi)  lerp(a,b,u)  choose(...)
             isn(x) ics(x)  isn_inv/arcisn  ics_inv/arcics
             P(s,c) E(s,c) D(s,c)  tensor_z(s,c) tensor_rel(s,c)
  Constants: pi e tau PHI MEUM MEUM_NORM MEUM_INV MEUM_SQ MEUM_LOG2
             SILVER SQRT2 SQRT3
  Variables: t (time), x (=t), y, z
  Canonical context flags (when a render transaction is active) may also
  appear as simple numeric/bool names for if/elif branching.

  EXAMPLES
  --------
  if(sin(t * MEUM) >= 0) 432 elif 216
  return lerp(110, 880, 0.5 + 0.5 * sin(t * 0.25))
  64, 96, 128, 160, 192
  clamp(exp(sin(t)) * MEUM * 100, 20, 2000)

--------------------------------------------------------------------------------
5. BOOTSTRAP (missing seed and/or program)

--------------------------------------------------------------------------------

Runs automatically before Euclidean lock / Seeded randomizer.

  Program = net-effect data only (playlist-effective instruments with audible steps).

  Case A — no seed AND no program (system is free to assign):

      50% → BOTH: random kit seed + kit program parameters
      25% → SEED ONLY: random kit seed; pads/playlist left empty
      25% → PROGRAM ONLY: kit program parameters; seed field stays empty

  Case B — program present, no seed:

      Derive seed from fingerprint of net-effect steps (simplifies playlist superwrite)

  Case C — non-zero seed present, no program:

      Provide seed-derived program parameters on pads + blank playlist fields only

  Case D — non-zero seed AND program:

      No bootstrap changes

6. NET-EFFECT USER INPUT (INCLUDING DEPENDENCIES)
--------------------------------------------------------------------------------
Protected "user" data must be able to change the mix at some playlist time t:

  • Step ON with amplitude > ~0.02 (not near-silent)
  • Instrument is a playlist operator OR feeds one (directly or transitively)
    through user-accessible patch / GLOBAL_BUS routing — because changing that
    parameter changes another path that *does* hit the timeline
  • If playlist is empty/off, all instruments are in scope

Ignored for protection (engines may reshape freely):
  • Instruments with no playlist presence and no dependency path into one
  • Silent ON steps, empty patterns with no audible contribution

Fingerprint / "program present" checks use the same net-effect rules.

--------------------------------------------------------------------------------
7. SIMPLIFY (before additive fill)
--------------------------------------------------------------------------------
  • Continuous amplitudes (no ¼ ladder quantize)
  • Instruments stay distinct (no cross-instrument pattern amp snap)
  • Deduplicate patch cables (app + GLOBAL_BUS)
  • Merge domain partitions with identical bounds/logic/equation
  • Count identical scripts as shared definitions
  • Sequence scale: each pattern fits playlist row beats via inst_step = row/N

Order:  Bootstrap → Simplify → Additive fill / phase-lock / patch optimize

--------------------------------------------------------------------------------
8. ADDITIVE ENGINES (NON-DESTRUCTIVE)
--------------------------------------------------------------------------------
Euclidean Phase-Lock
  • Never turns OFF protected user steps; never lowers user amps
  • Fills empty slots with Euclidean structure + soft spectral opposites
  • Sporadic probability commutation only on non-user slots

Seeded Harmonic Randomizer
  • Fractal echoes of your carrier into empty slots
  • Scripts updated only if still stock templates
  • Triggers additive patch optimizer

Patch Bay Optimizer
  • Never removes user cables or changes their gain/polarity
  • Sparse links only to unserved targets (activity + family + golden-ratio score)
  • Mirrors into GLOBAL_BUS only when edge is new

--------------------------------------------------------------------------------
9. DOMAIN TIME / SPACE EQUATIONS  (∫ button)
--------------------------------------------------------------------------------
Partitionable domains; each row:

  Name | Axis (time|space|both) | t0 t1 | x0 x1 | y0 y1
  Logic | Equation | Limits lo|hi | Weight|SeedW

Equation environment (safe):
  t, x, y, z, seed, seed_w, t_norm
  MEUM, sin, cos, tan, abs, sqrt, exp, log, pi, e
  clip, minimum, maximum, where, np

Logic examples:
  True
  t < 0.5
  abs(x) + abs(y) < 1.2
  seed_w > 0.3

Equation examples:
  sin(2 * pi * t * 2) * exp(-t * 3)
  sin(x * MEUM + t * 4) * cos(y * pi) * (1.0 - 0.2 * seed_w)
  sin(pi * t) * cos(2 * pi * t * (1 + seed_w))

Overlaps blend by weight; seed_weight longitudinally biases early vs late
partitions. Render modulation (additive):
  master *= (1 + 0.45 * domain_modulation)

--------------------------------------------------------------------------------
10. INSTRUMENT SCRIPTS  (📝 button)
--------------------------------------------------------------------------------
Per-operator script workspace. Typical form:

  def evaluate_wave(x, y, z):
      return series_sin(x * 3.0) * series_cos(y) - z

Custom scripts are preserved by the randomizer; only stock auto-templates
are replaced during seeded fill.

--------------------------------------------------------------------------------
11. PLAYLIST PAINTBRUSH & AUTOMATION
--------------------------------------------------------------------------------
  Wide unquantized grid (48 free rows by default) — not hard-bound to one instrument.

  Columns:
    Time Marker | Operator Identity | Script Tag | Velocity |
    Auto Target | Auto Amount | Direction Vector | Multi-Seq | Coverage | Blend Partner | GOAVA Sequence

  Paint subject menu:
    1. Identity + Steps + Automation (default)
    2. Selected instrument identity only
    3. Selected instrument step sequence (no automation)
    4. Step sequence + Automation
    5. Automation of selected instrument

  Draw Random Synth ON/OFF still chooses random vs selected identity when identity is painted.

  Snap to grid: OFF by default (fully unquantized). Enable checkbox to snap time markers.

  Overlap / blend:
    • Painting over existing paint builds per-operator coverage on that row
    • Full cover → automation applies at 100%; half cover → ~50%, etc.
    • Overlapping identities blend synth param snapshots up to Half (50%) or Quarter (25%)
      of the distance between the two instruments' settings (Blend max menu)

  Automation:
    • Written by paint modes that include Automation
    • Randomizer / Euclidean may fill *empty* automation lanes only (never overwrite yours)
    • apply_playlist_automation_to_ui pushes amounts onto EQR / Fractalizer / PKP knobs
      and gently scales patch gains (direction vector = sign)

--------------------------------------------------------------------------------
12. MAIN CONTROLS

--------------------------------------------------------------------------------
Transport
  ▶ Live Audio Play / ⏸ Stop   Realtime stream (sounddevice) + scope
  BPM, Seed field              Tempo + geometric anchor
  ✨ Euclidean & Geometry Global Lock
  🎲 Seeded Harmonic Global Randomizer
  💾 Save & Export .wav

Macros
  EQR Mod, Fractalizer, PKP Decay, PKP Envelope Follower, Tuning
  Master Vol (beside oscilloscope)

PKP Pad Bank (toggle)
  Independent 16th-note clock; orange playhead; short hits on programmed steps

Windows
  🛠 Synth / Wavetable     📜 Playlist Paintbrush
  🔌 Modular Patch Bay     📝 Instrument Script Editor
  ∫ Domain Time/Space Equations
  ❓ Help / Readme (this document)

--------------------------------------------------------------------------------
13. GOAVA NUMERICAL MATH
--------------------------------------------------------------------------------
  GOAVA is the engine-owned numerical composition layer ported from the supplied
  Java Composer.getNote() implementation. For each assigned number n, step k,
  and seed-number list N, the scalar note value is accumulated over every value v
  in N using a cosine phase term. In simplified form:

      G(n,k,N) = | Σ_v F(n,k,v) / (|N| + |n-v|) |

  where the cosine phase is based on π/2, |n|, |v|, and the step k; the original
  GOAVA zero-value branch adds the step directly to that phase. The audible path
  uses the Java arpeggio scaling G × 16, with a safety fallback for pathological
  values and a final realtime-safe frequency clamp.

  GOAVA remains non-user engine data. Its numerical seed list creates one GOAVA
  event per supplied seed number, retaining the raw scalar, frequency, pitch ratio,
  and enabled state. In the playlist it occupies the dedicated GOAVA Sequence
  column and is appended after canonical Euclidean/Seeded composition so the normal
  comma-separated operator/member lists remain authoritative. The GOAVA visual
  engine uses these same numerical values as geometry seeds, while Meum calculus
  values modulate scale, rotation, density, depth, and temporal activation.

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

  • Length controls 1–1024 automation steps. The orange strip fills the row when it fits
    and scrolls horizontally at readable cell width when it does not.
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
      1. Set Length (for example 12).
      2. Click AUTO 1 once to select it.
      3. Choose Operator / Sequence / Offset ±.
      4. A newly created AUTO cell is stored ON by default; click the same cell again to toggle it OFF.
      5. Click another step once to teleport to it, edit it, then click it again
         when you want it ON.

  The automation state is written through the canonical composition boundary and
  participates in Live Play / Audio Export / Video Export. Disabled automation steps do not drive the
  render. The Automator popup is a UI-only teleport indicator; Operator, Sequence,
  and Offset edits are written to the selected automation point.

--------------------------------------------------------------------------------
14. AUDIO
--------------------------------------------------------------------------------
  Realtime: sounddevice OutputStream callback consumes the same shared rendered buffer used by export.
  Export: shared _render_mixdown_buffer → WAV; 2.5D MP4 includes the same rendered audio.
  Master Vector Synth runs in that shared render path, so Live Play and Export see the same vector conversion.
  Signal Conversion Monitor observes the post-vector buffer; it does not silently rewrite canonical data.
  PKP hits: non-blocking sd.play blips when pad bank is armed
  (Install / dependencies are listed at the bottom of this guide.)

--------------------------------------------------------------------------------
15. 48 OPERATORS
--------------------------------------------------------------------------------
Families span topological wave-folding, multivector/phase-space, quantum/soliton,
stochastic/entropic, spatial/spectral effects, and dynamic resonators.
Each has sequencer memory (steps, amplitudes, gates, probabilities) and optional script.

--------------------------------------------------------------------------------
16. RECOMMENDED WORKFLOW
--------------------------------------------------------------------------------
  A. Sketch carrier pads on one or more instruments
  B. Paint playlist rows if arranging over time
  C. Set a non-zero seed — or leave blank/0 for bootstrap
  D. Run Euclidean lock and/or Seeded randomizer (bootstrap + simplify auto-run)
  E. Optional: Domain equations for sectional form
  F. Optional: Patch bay for modular routing accents
  G. Play → refine → Export

================================================================================

--------------------------------------------------------------------------------
17. SEQUENCER AMP / PITCH & LIVE ENGINES
--------------------------------------------------------------------------------
  Step pads: click once = select (Amp/Vel + Pitch sliders). Click again = toggle on/off.
  Amp = velocity / step-trigger blend. Pitch = frequency ratio (automation param for steps).
  Euclidean + Seeded are LIVE TOGGLES (periodic regenerate against user carrier).
  "User program only" suspends both live engines.
  Save/Load Project (JSON). Keyboard/Test + Trigger All (global).
  Playlist: Convolve Color Coding for per-instrument hues + blend labels.
  Visualizer dropdown: master / effected / overall pattern / per-instrument activity.
  Global Cross-Loaded mode is default.

  POLYPHONY & PANELS
  ------------------
  Playlist focus is arrangement metadata, not a solo. Every sounding
  instrument and every ON step is mixed (equal-power) so any number of
  notes can play at once. Canonical unison writes playlist operators,
  sequence refs, pattern lengths, and irrational time offsets.

  Master synth/script/patch/domain is the carrier mix. Per-sequence addon
  panels blend into that master by coverage / panel blend amount — they
  never replace the master bus. Engines may resize the selected sequence
  (and other bank slots) when the user has not touched any of its steps.

--------------------------------------------------------------------------------
GLOBAL PLAY PANEL — ALGORITHMS, PARAMS & LAUNCHED WINDOWS
--------------------------------------------------------------------------------
  The Global Play group is the project-level algorithm layer. It never overwrites
  the seed field or per-instrument seed scripts. Text lives in global_algo_state
  until you apply it to the master mix / ensemble.

  MAIN CONTROLS
  -------------
  🎲 Randomize Global Play Algorithm
      Fills Script, Domain, Wire, and amount params from the Meum/PED vocabulary.
      AUTHORING ONLY — does not apply to the ensemble until you press Apply.

  ▶ Apply Algo to Master Mix  (toggle)
      ON  → enabled layers (script / domain / wire) broadcast to the ensemble.
      OFF → written music/shapes left alone. Undoable (Ctrl+Z).

  Script Algo (multi-line text)
      Project-level script over t, MEUM, PHI, seed, instrument name / i.
      Typical form:
          def global_script(t, name, i):
              v = isn(t * MEUM) * 0.4 + ics(t * PHI) * 0.3
              return v * 0.35
      Same expression language as the seed field (sin/cos/isn/ics, conditionals,
      return). When Operator Theory is ON, sin/cos/… use the equivalence kernel.

  Domain Algo (single line)
      Equation string, e.g. sin(t * MEUM) + cos(t * PHI).
      Live hints: sin/cos → phase · log/exp → scale · domain → transmutor.

  Wire Algo button  → opens Global Wire Algo window
      Routing matrix: detectors → targets with amounts.
      Detectors: phase, energy, spectrum, goava, euclidean, seed, bpm, pair
      Targets:   master_mix, fractallizer, eqr, pkp, ensemble, scenograph,
                 domain, unison

  Algo Params button → opens Global Algo Params window
      mix                  overall wet (default ~0.35)
      enable_script/domain/wire   per-layer gates
      script_amount / domain_amount / wire_amount   same as main sliders

  Mix / Script / Domain / Wire amount sliders (0–100%)
      Relative wet amounts when Apply is on.

  APPLY RULES
  -----------
  • Randomize never auto-applies (authoring only).
  • Apply ON pushes enabled layers; Apply OFF stops the overlay.
  • Algorithm state is userdata (saved in the project) and undoable.
  • Global Play never writes the seed field.

  WORKFLOW
  --------
  1. Randomize or type Script / Domain text.
  2. Adjust amount sliders; open Wire / Params windows if needed.
  3. Press Apply Algo to Master Mix to hear the overlay.
  4. Toggle Apply off or Undo to revert the ensemble overlay.

--------------------------------------------------------------------------------
DEPENDENCIES (install last — same list as project README.md)
--------------------------------------------------------------------------------
  Python packages (pip) — every OS:
    PyQt6          UI
    numpy          DSP / buffers
    wave/FFmpeg    OS/stdlib WAV + bundled media I/O
    sounddevice    Real-time audio I/O
    Pillow         Frame export (PNG) for video

  System tools:
    Python 3.9+ (3.10–3.12 recommended)
    ffmpeg + ffprobe (full build with encoders) for video/audio export
    PortAudio / ALSA / CoreAudio (via sounddevice) for playback

  One-shot installers (preferred):
    Linux:   ./install_deps_linux.sh   [--fedora | --ubuntu]
    macOS:   ./install_deps_macos.sh
    Windows: ./install_deps_windows.ps1

  Manual pip (any OS):
    python3 -m pip install --upgrade pip
    python3 -m pip install numpy PyQt6 sounddevice Pillow

  Ubuntu/Debian system packages:
    sudo apt install -y python3 python3-pip python3-venv python3-dev \
      build-essential ffmpeg libasound2-dev portaudio19-dev

  Fedora:
    sudo dnf install -y python3 python3-pip python3-devel gcc gcc-c++ \
      ffmpeg ffmpeg-libs alsa-lib-devel portaudio-devel
    (enable RPM Fusion for full ffmpeg codecs)

  macOS:
    brew install python ffmpeg portaudio

  Windows:
    winget install Python.Python.3.12
    winget install Gyan.FFmpeg

  Optional: place static ffmpeg / ffprobe in ./bin/ next to groovebox.py
  (the app checks there first).

  Verify:
    python3 -c "import numpy, PyQt6.QtCore, sounddevice, PIL; print('OK')"
    ffmpeg -hide_banner -version | head -1

  Run:
    ./launch_desktop.sh
    # or: python3 groovebox.py

--------------------------------------------------------------------------------

# 17. CANONICAL CROSS-MEDIA COMPOSITION
Groovebox v13 uses one readable/writable canonical composition document as the source of truth at every engine, save/load, import, and export boundary. Sequencer steps, gates, pitch, amplitude, probability, operator timing offsets, instrument parameters, instrument samples, playlist arrangement, patchbay connections, modulation/routing state, global algorithms, mathematical controls, imported media references, seeds, timing, and engine toggles are represented on the same composition surface.

The canonical authority exposes explicit READ and WRITE operations. UI controls write to the canonical surface; legacy engine attributes are compatibility mirrors synchronized from it. Audio, video, and videogame consumers read the canonical document rather than maintaining separate authoritative composition copies.

The rendered music wave additionally contributes deterministic waveform analysis: RMS, peak, energy envelope, zero-crossing rate, spectral centroid, spectral flatness, and normalized spectrum. Visual/game behavior can therefore be derived from the actual musical wave as well as the event-level composition that generated it.

# 18. SAVE/LOAD + IMPORT/EXPORT PARITY
Project save/load is a canonical read/write loop. Save serializes the authoritative canonical document; load restores that document through the canonical authority and then rebuilds the compatibility mirrors used by older engine code. Imported WAV/audio, instrument samples, and imported video are canonical media references and are restored when possible.

Audio exports, video exports, and videogame packages carry the canonical authority version/revision/fingerprint together with the cross-media fingerprint/provenance. Thus every exported medium can be traced to the same project state. Import handlers also write their new media references into the canonical surface before the next engine/export boundary.

Re-rendering audio refreshes waveform analysis; video and game generation then read that refreshed canonical cross-media state.

# 19. MUSIC-WAVE → VIDEO → VIDEOGAME
The cross-media rule is: one canonical musical source, multiple deterministic expressions. Beat/note/sequence timing, waveform energy, spectral information, phase, arrangement, mathematical parameters, and canonical routing can drive corresponding visual and game events. A strong transient can become a visual pulse and a game event; a sequence transition can become a visual scene/state transition; pitch and spectral changes can influence geometry, world parameters, or gameplay values.

The videogame receives the same canonical document and waveform-analysis contract used by the audiovisual side, not an independently authored game-only state. Video likewise reads the same canonical composition and wave-derived projection. This is the v13 single-source-of-truth rule: if a parameter changes the composition, it is canonical and readable/writable by the authority; if it is only a local display preference, it stays outside the composition.

The videogame package receives the canonical composition plus waveform-analysis contract rather than only a seed and a few UI settings. The generated game therefore has access to the same musical identity used by the audio/video side. Exported audio, video, and game artifacts carry compatible fingerprints for cross-verification.

The design target is:
    CANONICAL MUSIC → ACTUAL WAVE + MUSICAL EVENTS
                         ↓
                  CROSS-MEDIA CONTRACT
                    ↙           ↘
                 VIDEO          GAME

No separate hidden music, video, or game composition should become authoritative. A new control belongs in the canonical document when it changes the composition; otherwise it remains a local UI/render preference.

  End of Help — Groovebox
  Credits: Grok (xAI), Gemini (Google), Claude (Anthropic), ChatGPT (OpenAI),
  Mistral.ai (Mistral), Meta AI (Meta), GitHub Copilot (GitHub),
  Cursor Grok 4.6, jcode(1jehuang) and opencode (anomalyco).
================================================================================

--------------------------------------------------------------------------------
18. HOW TO USE THE MATHEMATICAL LAYER — FROM PAD TO CANONICAL GENERATION
--------------------------------------------------------------------------------
This section is the practical path for using the mathematics without needing to
understand the implementation first.

CANONICAL COMPOSITION ENGINE — ONE SOURCE, ALL MEDIA

Groovebox uses a canonical composition model so that the same musical composition
can drive audio, video, and videogame generation without creating separate or
contradictory versions of the project.

The canonical composition contains the musical information that defines the work,
including:

• Sequence banks and sequence lengths
• Per-step pitch, amplitude, gate, probability, and timing
• Instrument and effect parameters
• Instrument sample assignments
• Operator timing offsets and predictive timing information
• Playlist structure and arrangement
• Global algorithms and mathematical parameters
• Modulation and routing information
• Master patchbay relationships
• Composition-matrix relationships
• Performance/macroscopic controls
• Randomization state and deterministic seeds
• Tempo, timing, phase, and synchronization information
• Imported audio/media references and their composition roles
• Game-generation metadata derived from the composition

The canonical state is the authoritative representation of the project.

Audio rendering reads this state to produce the musical waveform.

Video rendering reads the same state to determine visual timing, motion,
transformations, procedural geometry, modulation, synchronization, and
imported-video behavior.

Videogame generation reads the same state to determine the game's world
parameters, objects, timing, procedural behavior, musical synchronization,
and composition-derived game metadata.

The conceptual model is:

    CANONICAL COMPOSITION
             │
       ┌─────┼─────────────┐
       │     │             │
       ▼     ▼             ▼
     AUDIO  VIDEO       VIDEOGAME
       │     │             │
       ▼     ▼             ▼
      WAV    MP4       GAME DATA/ENGINE

Changes made through the Master Patchbay, Composition Matrix, Modulation Routing,
Sequencer, Instruments, Playlist, or other canonical controls should propagate
through every compatible output engine.

The objective is deterministic correspondence: if a musical parameter changes,
every generated medium that depends upon that parameter should receive the same
underlying information.

--------------------------------------------------------------------------------
19. PROJECT SAVE/LOAD AND IMPORT/EXPORT PARITY
--------------------------------------------------------------------------------
Project save/load is based on the canonical composition rather than isolated
copies of individual editor controls.

A saved project should preserve enough information to reconstruct the composition
and its relationships across all supported media.

Project state includes, where applicable:

• Complete sequence information
• Instrument parameter state
• Instrument sample paths and sample configuration
• Playlist/arrangement information
• Operator time offsets
• Global synthesis and algorithm settings
• Modulation and patchbay routing
• Composition Matrix relationships
• Imported audio references
• Imported video references
• Imported-media metadata
• Video composition parameters
• Game-generation metadata
• Randomization state and deterministic seeds
• Rendering/export configuration when applicable

External media files are referenced by path or project-relative location rather
than assuming that a temporary decoded buffer is itself the project.

When a project is loaded, Groovebox attempts to restore the referenced media and
reconstructs the canonical composition before rebuilding dependent audio, video,
and game representations.

Import and export operations remain subordinate to the canonical composition.
Audio import can become part of the musical composition, including use as an
imported waveform, carrier, convolution source, or instrument sample where
supported. Video import can become part of the visual composition while retaining
its relationship to the musical timeline.

The intended persistence loop is:

    SAVE → LOAD → RENDER AUDIO
                    │
                    ├── RENDER VIDEO
                    │
                    └── GENERATE GAME

Missing external media should be reported rather than silently replaced with
unrelated content. Where a deterministic procedural fallback is supported, that
fallback should preserve the composition's mathematical and timing structure.

--------------------------------------------------------------------------------
20. MUSIC-DERIVED VIDEO AND VIDEOGAME GENERATION
--------------------------------------------------------------------------------
Groovebox treats the musical waveform and its canonical generating parameters as
sources of information for the other media engines.

Derived media should not merely react to final audio amplitude. The complete
composition contains substantially more information than amplitude alone.

Video and videogame generation can derive behavior from:

• Waveform amplitude
• Frequency and spectral characteristics
• Rhythmic events
• Beat and subdivision timing
• Note/pitch information
• Gate events
• Probability events
• Sequence transitions
• Instrument identity
• Instrument parameters
• Modulation values
• Operator offsets
• Playlist/arrangement changes
• Mathematical algorithms
• Phase relationships
• Deterministic randomization
• Imported-media relationships

For example:

    KICK EVENT
       ↓
    musical event
       ├── audio transient
       ├── visual pulse
       └── game event

    PITCH CHANGE
       ↓
    canonical note information
       ├── oscillator frequency
       ├── visual frequency/geometry parameter
       └── game-world parameter

    SEQUENCE CHANGE
       ↓
    canonical arrangement event
       ├── audio pattern change
       ├── visual scene/state change
       └── game-state transition

    OPERATOR TIME OFFSET
       ↓
    canonical timing relationship
       ├── audio timing
       ├── synchronized visual timing
       └── synchronized game timing

The intended system is:

             MUSICAL COMPOSITION
                     │
         ┌───────────┼───────────┐
         │           │           │
      waveform    events     parameters
         │           │           │
         └───────────┼───────────┘
                     ▼
            COMPOSITION ANALYSIS
                     │
          ┌──────────┼──────────┐
          ▼          ▼          ▼
         AUDIO      VIDEO      GAME
          │          │          │
          ▼          ▼          ▼
       waveform   frames    world/state

Imported video should participate in the canonical visual layer rather than
existing as an unrelated background asset. Imported audio should remain capable
of participating in the canonical audio/composition pipeline.

Generated videogames receive composition metadata describing the musical
structure that drives them, including timing, arrangement, instrument-related
information, algorithmic parameters, and other supported canonical controls.

The intended result is one mathematical composition expressed through multiple
media:

    ONE COMPOSITION = SOUND + IMAGE + INTERACTION

Whenever a new control is added, ask:

    Does this control modify the canonical composition?

If YES: expose its state through the canonical composition, save/load it with the
project, and make it available to every output engine for which it has a meaningful
interpretation.

If NO: keep it as a local UI/rendering preference and do not duplicate it into
unrelated composition engines.

--------------------------------------------------------------------------------
21. THE SHORTEST USEFUL WORKFLOW
--------------------------------------------------------------------------------
1. Choose BPM and sequence length.
2. Choose an instrument and turn on a few pads.
3. Leave Seed blank/zero for ordinary authoring, or enter a non-zero numeric seed.
4. Press Play and listen to the carrier.
5. Enable Phase-Lock, Randomize, Seeded, GOAVA, or Operator Theory one at a time.
6. Open Playlist when you want generated structure written into arrangement rows.
7. Use Domain Equations for time/space functions and Instrument Scripts for
   per-instrument rules.
8. Save the project before experimenting with a new mathematical recipe.

--------------------------------------------------------------------------------
22. FIRST SCRIPTING EXAMPLES
--------------------------------------------------------------------------------
A simple two-frequency carrier:
    sin(2*pi*t*2) + 0.5*cos(2*pi*t*3)

Meum phase field:
    sin(t*MEUM) * cos(t*PHI)

Seed-dependent motion:
    sin(t*MEUM + seed) * (0.5 + 0.5*cos(t*PHI))

The project's isn / ics forms:
    isn(t*MEUM) * 0.6 + ics(t*PHI) * 0.4

A multivariate domain expression:
    sin(x*MEUM + y*PHI + z*pi)

Function-style script:
    return isn(t*MEUM) + 0.25*ics(t*PHI)

sin, cos, isn, ics, MEUM, PHI, pi, e, tau, seed, x, y, z, and public reference
constants are available to the appropriate script evaluators. Use the Help panel
as the authoritative list for the build being run.

--------------------------------------------------------------------------------
23. HOW GENERATED MATH REACHES SOUND
--------------------------------------------------------------------------------
The canonical pipeline is conceptually:

    seed → canonical context → instrument lattice → operator/sequence transforms
         → voice parameters → mix

The seed is therefore an input to a deterministic construction, not an assertion
that every generated result is a theorem of number theory. When a canonical
fingerprint is identical, the implementation is intended to regenerate the same
canonical state.

--------------------------------------------------------------------------------
24. MEUM CALCULUS — PROJECT DEFINITIONS, OPERATIONS, AND EXAMPLES
--------------------------------------------------------------------------------
MEUM CALCULUS — PROJECT MATHEMATICAL FRAMEWORK

Meum Calculus is the mathematical framework developed and documented by Noah
Girouard King (Eski) in connection with Scientific Theories and Inventions and
related works. Groovebox implements the project's stated constants,
transformations, operators, coordinate systems, and derived quantities as a
reproducible computational system.

CLAIMED EXACT means exact according to the project's declared definitions,
formulas, constants, serialization rules, and tested implementation contract.
It does not by itself assert that a project-defined result constitutes an
independently established theorem of mathematics or physics.

PUBLIC CONSTANTS

The canonical Meum value is:
    M = 
# -----------------------------------------------------------------------------
# Author-series trigonometry kernels (radians)
# Direct summation/recurrence implementations: no math/NumPy circular or inverse
# trig calls.  These are the canonical Groovebox kernels for scalar/array use.
# -----------------------------------------------------------------------------
SERIES_PI = 3.14159265358979323846264338327950288419716939937510
SERIES_TAU = 2.0 * SERIES_PI

def _series_arr(x):
    return np.asarray(x, dtype=np.float64)

def _series_out(v):
    a=np.asarray(v)
    return a.item() if a.ndim==0 else a

def _series_reduce(x):
    a=_series_arr(x)
    with np.errstate(invalid='ignore'):
        return np.remainder(a + SERIES_PI, SERIES_TAU) - SERIES_PI

def series_sin(x):
    a=_series_reduce(x)
    a=np.where(a>SERIES_PI/2, SERIES_PI-a, np.where(a<-SERIES_PI/2, -SERIES_PI-a, a))
    term=a.copy(); total=a.copy()
    for n in range(1, 19):
        term *= -(a*a)/((2.0*n)*(2.0*n+1.0)); total += term
    return _series_out(total)

def series_cos(x):
    a=_series_reduce(x); sign=np.ones_like(a)
    hi=a>SERIES_PI/2; lo=a<-SERIES_PI/2
    sign=np.where(hi|lo,-1.0,1.0)
    a=np.where(hi,SERIES_PI-a,np.where(lo,-SERIES_PI-a,a))
    term=np.ones_like(a); total=term.copy()
    for n in range(1,19):
        term *= -(a*a)/((2.0*n-1.0)*(2.0*n)); total += term
    return _series_out(sign*total)

def series_asin(x):
    z=_series_arr(x); a=np.abs(z); bad=a>1.0; reduce=a>0.5
    with np.errstate(invalid='ignore'):
        w=np.where(reduce,np.sqrt((1.0-a)/2.0),a)
    term=w.copy(); total=w.copy()
    for n in range(1,33):
        term *= (w*w*(2.0*n-1.0)**2)/((2.0*n)*(2.0*n+1.0)); total += term
    total=np.where(reduce,SERIES_PI/2.0-2.0*total,total)
    total=np.copysign(total,z); total=np.where(bad,np.nan,total)
    return _series_out(total)

def series_acos(x):
    z=_series_arr(x); bad=np.abs(z)>1.0
    with np.errstate(invalid='ignore'):
        q=2.0*np.asarray(series_asin(np.sqrt((1.0-np.abs(z))/2.0)))
    out=np.where(z>=0.0,q,SERIES_PI-q); out=np.where(bad,np.nan,out)
    return _series_out(out)

def series_atan(x):
    z=_series_arr(x); a=np.abs(z); inv=a>1.0
    with np.errstate(divide='ignore',invalid='ignore'):
        a=np.where(inv,1.0/a,a)
        a=a/(1.0+np.sqrt(1.0+a*a))
    term=a.copy(); total=a.copy()
    for n in range(1,33):
        term *= -(a*a); total += term/(2.0*n+1.0)
    total*=2.0; total=np.where(inv,SERIES_PI/2.0-total,total)
    return _series_out(np.copysign(total,z))

def series_atan2(y,x):
    y,x=np.broadcast_arrays(_series_arr(y),_series_arr(x))
    with np.errstate(divide='ignore',invalid='ignore'):
        out=np.asarray(series_atan(y/x))
    out=np.where(x<0.0,out+np.copysign(SERIES_PI,y),out)
    out=np.where(x==0.0,np.copysign(SERIES_PI/2.0,y),out)
    out=np.where(y==0.0,np.where(np.signbit(x),np.copysign(SERIES_PI,y),y),out)
    return _series_out(out)

def series_tan(x):
    with np.errstate(divide='ignore',invalid='ignore'):
        return _series_out(np.asarray(series_sin(x))/np.asarray(series_cos(x)))

def series_sinh(x):
    z=_series_arr(x); a=np.abs(z); scale=np.zeros(a.shape,dtype=np.int32)
    a=np.where(np.isfinite(a),np.minimum(a,710.0),0.0)
    for _ in range(11):
        m=a>0.5; a=np.where(m,a*0.5,a); scale += m
    term=a.copy(); total=a.copy()
    for n in range(1,19):
        term *= (a*a)/((2.0*n)*(2.0*n+1.0)); total += term
    with np.errstate(over='ignore',invalid='ignore'):
        for k in range(11): total=np.where(scale>k,2.0*total*np.sqrt(1.0+total*total),total)
    total=np.where(np.abs(z)>710.0,np.inf,total); total=np.where(np.isnan(z),np.nan,total)
    return _series_out(np.copysign(total,z))

def series_cosh(x):
    q=np.asarray(series_sinh(_series_arr(x)/2.0)); return _series_out(1.0+2.0*q*q)

def series_tanh(x):
    z=_series_arr(x); q=np.clip(z,-20.0,20.0)
    with np.errstate(divide='ignore',invalid='ignore'):
        out=np.asarray(series_sinh(q))/np.asarray(series_cosh(q))
    return _series_out(np.where(np.abs(z)>20.0,np.copysign(1.0,z),out))

def series_sinc(x):
    z=_series_arr(x)
    with np.errstate(divide='ignore',invalid='ignore'):
        out=np.where(z==0.0,1.0,np.asarray(series_sin(SERIES_PI*z))/(SERIES_PI*z))
    return _series_out(out)

def series_book_isn(x):
    # sum (-1)^n*x^(2n+1)/(2^(2n)*(2n+1)!)
    return _series_out(2.0*np.asarray(series_sin(_series_arr(x)/2.0)))

def series_book_isn_inverse(x):
    return _series_out(2.0*np.asarray(series_asin(np.clip(_series_arr(x)/2.0,-1.0,1.0))))

def series_cyclic_isn(x):
    # author's even-power series: x^2/2! - x^4/4! + x^6/6! - ...
    a=_series_reduce(x); term=a*a/2.0; total=term.copy()
    for n in range(2,25):
        term *= -(a*a)/((2.0*n-1.0)*(2.0*n)); total += term
    return _series_out(total)

MEUM = 1.1975807343385265188

Public reference inverse:
    M⁻¹ = MEUM_INV = 0.83501677283773394333148276154833054143874793150691

Important derived values:
    M² = 1.43419961525880442984053780233084675344
    M³ = 1.7175698284296712120687451889540584671690563022583
    M⁴ = 2.0569285364085026523421673878967788864920989745683
    (M−1)/M = 0.16498322716226605666851723845166945856125206849309
    2^M = 2.2935474173287805635918286442792609595802586606571
    log₂(M) = 0.26012291784344212146116471128795687966817094961902

Reference constants are also exposed as PI_IRR, E_IRR, PHI, PHI_INV, SQRT2,
SQRT3, and SILVER.

MEUM POWER LATTICE

For instrument slot i, the canonical power table is generated from:
    P_j = M^(j−6), j = 0,…,35

The slot coordinate uses the dense project-defined phase position:
    u_i = (3 i M) mod 36

If j = floor(u_i) and r = u_i − j, the interpolated lattice factor is:
    L_i = (1−r) P_j + r P_(j+1 mod 36)

This is a deterministic geometric mapping. “Dense” means the use of a
non-rational-looking project constant is intended to avoid a short visual period;
it is not a proof of equidistribution.

PRACTICAL NOTE — WHAT MEUM CONTRIBUTES TO GROOVEBOX
Meum gives the software a compact family of related coordinates (M, M−1, 1/M, 2−M,
(M−1)/M and powers of M) that can be precomputed once and reused. This is logically
useful for deterministic phase indexing, modulation vocabulary, spatial traversal,
procedural placement, canonical fingerprints, and progressive refinement. Reuse makes
these paths cache-friendly and permits fused/native implementations instead of repeatedly
reconstructing equivalent relationships in Python. The useful property is reproducible
structure. Whether Meum is superior to phi, sqrt(2), or other low-discrepancy choices is
an empirical question and should be benchmarked rather than assumed.

MEUM-T1 — EXISTENCE, UNIQUENESS, AND IRRATIONALITY
The project formally defines mathematical Meum as the unique root M in (1,2) of
    2^M = M^4 + M^2 - M,
or F(x)=2^x-x^4-x^2+x=0.

Existence: F is continuous, F(1)=1>0, and F(2)=-14<0, so the Intermediate
Value Theorem gives at least one root in (1,2).

Uniqueness: F'(x)=2^x ln(2)-4x^3-2x+1 and
F''(x)=2^x(ln 2)^2-12x^2-2. On [1,2], 2^x(ln2)^2<2 while
12x^2+2>=14, hence F''<0. Therefore F' is strictly decreasing; since
F'(1)=2 ln2-5<0, F'<0 throughout [1,2]. F is strictly decreasing and its
root there is unique.

Irrationality: if M=p/q in lowest terms, then M^4+M^2-M is rational, so
2^(p/q) must be rational. Writing 2^(p/q)=a/b in lowest terms and raising
to q gives a^q=2^p b^q. Unique prime factorization forces b=1 and q|p;
with p/q reduced, q=1. Thus every rational solution would be an integer,
but the unique Meum root lies strictly between 1 and 2. Hence M is irrational.

Groovebox stores the long decimal reference and a correctly-rounded binary64 value.
The finite machine value is necessarily rational, but every subsystem now receives the
same binary64 representation and pre-rounded derived constants rather than separately
truncated decimal copies.

MEUM NORMALIZATION

The standard normalized weight is:
    N_M = (M−1)/M

A Meum-weighted pair can be written:
    F_M(a,b) = N_M a + (1−N_M)b

The canonical isn implementation uses this style of Meum blending in its EQR
execution path; the exact implementation should be consulted when auditing a
specific release.

MEUM PHASE ROTATION

A slot phase reference is:
    φ_i = 2π i / 48

A second deterministic phase coordinate is:
    ψ_i = τ ((i N_M Φ⁻¹) mod 1)

These are coordinates, not random numbers. They are reproducible from i and the
public constants.

GOAVA IRRATIONAL-SAMPLING EXAMPLE

For continuous time t, base frequency f_b, and channel c, the project uses:
    s(t) = 0.5 f_b M⁻¹ t

A seed-list contribution has the form:
    C_v(t) = [1 + cos(β_v + (π/2)(|v|+|n|)s(t))] /
             (N + |n−v|)

with the zero-valued seed entry receiving the additional s(t) term in its base
phase. The stream is seeded and continuous in t; it is not an RNG call in the
audio callback.

--------------------------------------------------------------------------------
25. OPERATOR THEORY (OT) — COMPLETE PROJECT MATH REFERENCE
--------------------------------------------------------------------------------
OT THEORY — PROJECT DEFINITION

Operator Theory is the project's alternative arithmetic vocabulary. In canonical
paths it is primarily an execution/notation layer around deterministic scalar
operations. “Exact” means exact according to the project's stated OT rules and
regression contract, not a claim that these rules replace ordinary arithmetic in
established mathematics.

OT BAND FUNCTION
    B(x) = 1, if |x|≤1
         = 2, if 1<|x|≤2
         = 3, if 2<|x|≤3
         = 1, if |x|>3

OT ADDITION AND SUBTRACTION

Let b be the band of the operand with the greater magnitude. Then:
    OT_ADD(n,v) = n+v + 0.5B, when n+v ≥ 0
    OT_ADD(n,v) = n+v − 0.5B, when n+v < 0

Subtraction follows the project's directional rule; otherwise it routes through
OT_ADD(n,−v).

OT MULTIPLICATION

Magnitude is ordinary multiplication:
    |OT_MUL(a,b)| = |ab|

The project's sign rule is intentionally nonstandard:
positive×positive returns +|ab|; negative×negative returns −|ab|; unlike signs
return −|ab|. The special identity is OT_MUL(0,0)=1, while zero with a nonzero
operand returns 0.

OT POWERS AND ROOTS

Power is defined by:
    OT_POW(b,e) = s |b|^|e|

where s follows the project's signed-power convention. Roots use ordinary
magnitude roots with the project's real-sign convention. Undefined real-domain
cases remain undefined rather than being silently reinterpreted as positive
magnitudes.

OT DIVISION AND ZERO

ENGINEERING NOTE — WHY OT IS USEFUL IN THIS APPLICATION
Operator Theory gives Groovebox an explicit reversible-operation vocabulary rather than
hiding inverse behavior in ad-hoc cleanup code. Add↔subtract, multiply↔divide and
power↔root pairings are useful for writer toggles, provenance, zero-state restoration,
transform simplification, and inspection. The contextual zero-division policy also lets
the owning operation deliberately select 0, 1, signed infinity, numerator n, a solved
ratio, or a fallback instead of silently injecting an epsilon. OT remains project-defined
mathematics; its engineering value here is that its rules are explicit and testable.

For a nonzero denominator:
    |OT_DIV(a,b)| = |a|/|b|

with sign taken from a. The project defines 0/0 = 1 in OT mode. Division by zero for nonzero a uses signed infinity in OT mode. Ordinary/DSP compatibility paths choose an explicit context policy (0, 1, signed infinity, numerator/n, or an explicitly solved x/y-equivalent value) rather than adding a hidden epsilon. These are project compatibility rules, not ordinary field arithmetic.

OT PHASE OPERATOR
    OT_I_PHASE(x,k) = −x for even k, and +x for odd k.

It is a symbolic orientation marker and is not intended to introduce a new
complex-valued audio stream by itself.

isn AND ics

The canonical book-form definitions are:
    isn(θ) = 2 sin(θ/2)
    isn⁻¹(y) = 2 arcsin(y/2)
    ics(θ) = 2 cos(θ/2)
    ics⁻¹(y) = 2 arccos(y/2)

The inverse functions require |y/2|≤1 on the real principal domain. This is a
mathematical domain restriction, not a claim about audio clipping.

--------------------------------------------------------------------------------
26. EQR REALITY TENSOR
--------------------------------------------------------------------------------
The documented EQR form for sequences indexed by n is:

    P = (1/k) Σ[n=0..k] isn⁻¹((isn(d_n)+isn(t))/2)

    E = (1/k) Σ[n=0..k] isn(θ_n)/d_n

    D = (1/k) Σ[n=0..k] isn⁻¹(isn(θ_n) E/(I P))

    Z = P E + D

with the project constant I = 134964356 as its finite-infinity reference.

These equations describe the project's model. They do not establish a physical
law or a mathematically proven theory of reality.

--------------------------------------------------------------------------------
27. CANONICAL NUMBER-THEORY / CONGRUENCE CLAIMS
--------------------------------------------------------------------------------
The project may label a canonical generation CLAIMED EXACT when the claim is
restricted to this reproducible implementation contract:

1. The same canonical inputs are serialized in the same order.
2. The same public constants are used.
3. The same deterministic formulas and integer/index rules are applied.
4. The same canonical state fingerprint is regenerated.
5. Regression tests compare the resulting canonical records or buffers.

This supports a claim of implementation-level deterministic correctness under
the tested contract. It does not prove new number theory, prove that MEUM is
irrational, or prove perfect congruence for all possible future inputs.

For modular indexing:
    a ≡ b (mod n)  ⇔  n | (a−b)

For a cyclic slot permutation:
    p(i) = (a i + b) mod n

a sufficient condition for a bijection over residue classes is:
    gcd(a,n)=1

That is an established finite-number-theory fact when the implementation follows
it. A project-specific lattice built from MEUM should instead be described as a
deterministic mapping unless a separate proof establishes stronger properties.

REFERENCE-ONLY SCRIPTING CONSTANTS

MEUM, MEUM_CONSTANT, MEUM_INV, MEUM_MINUS_1, MEUM_SQ, MEUM_CUBE,
MEUM_FOURTH, MEUM_NORM, MEUM_OVER_1_5, MEUM_TWO_POW,
MEUM_TWO_POW_OVER_SQ, MEUM_LOG2, MEUM_UNISON_STEP_FACTOR, MEUM_POWERS_36,
INSTRUMENT_PHASE_LOCK_48, PHI, PHI_INV, PI_IRR, E_IRR, SQRT2, SQRT3, SILVER.

These are reference values, not hidden controls. Scripts should read them rather
than duplicating rounded literals when reproducibility matters.

--------------------------------------------------------------------------------
28. UNISON MASTER TRANSFORM — FORMULA AND PRACTICAL EXAMPLE
--------------------------------------------------------------------------------
The canonical full-unison idea is identity cancellation: every active voice is
translated from the same shared context rather than receiving an independent
random identity.

    U_i = T(C, i, E)

where C=(seed, base, ratio, s_int, sequential_nums), i is the roster slot, and E
is the set of active engine flags.

Outside full unison, the pitch carrier uses the lattice factor L_i:
    f_i = base · L_i · r_i

Inside full unison, the canonical translator uses the shared base and ratio:
    f_i = base · ratio

The shared entropy coordinate is derived from the canonical entropy function;
the phase reference is shared rather than independently randomized. The result is
intended to be an ensemble identity rather than 48 unrelated oscillators.

Reference scripting recipe:
    M = MEUM
    invM = MEUM_INV
    phi = PHI
    u = (3*i*M) % 36
    s = 0.5 * base_frequency * invM * t
    master = isn(t*M) * (M - 1) / M + ics(t*phi) * (1 - (M - 1)/M)
    return master

The recipe is for reference and experimentation. It does not promise that a user
script reproduces every internal voice parameter unless it uses the same canonical
function and state inputs as the implementation.

--------------------------------------------------------------------------------
29. VERIFICATION, REDISTRIBUTION, AND NUMERICAL BOUNDARIES
--------------------------------------------------------------------------------
WHAT SHOULD BE VERIFIED BEFORE REDISTRIBUTION

- Python syntax compiles.
- groovebox.py, README.md, and HELP_TEXT.md contain the same mathematical
documentation where duplication is intentional.
- Public constants are present in the script namespace and reference evaluator.
- Canonical generation is deterministic for fixed serialized input.
- Canonical fingerprints remain stable across save/load.
- Python/reference and native implementations agree where the release contract
requires parity.
- Nested redistribution archives contain the refreshed files.

NO HIDDEN CANONICAL CLAMP

The canonical frequency-reference helper is intentionally transparent: it does
not silently force a requested mathematical frequency into a fixed audible
interval. Explicit instrument/effect constraints are separate from the reference
transform.

A file-format conversion can still impose a representation limit. Integer PCM,
for example, has a finite numeric range. That is a property of the target file
representation, not a hidden mathematical clamp in the canonical transform.

Likewise, an inverse such as arcsin(y/2) has a mathematical domain. An out-of-domain
real input is undefined; it must not be described as evidence that the canonical
forward transform is clamping its output.

REDISTRIBUTION RULE

Every nested archive included in a redistribution package is a distribution
artifact, not a separate source of truth. When source documentation or
groovebox.py changes, refresh every nested ZIP/TAR.GZ that contains those files and
verify that its contents match the outer package.

The release phrase CLAIMED EXACT therefore means:

    exact with respect to the project's declared formulas, constants, serialization,
    and tested deterministic implementation contract;
    approximate/potential with respect to broader mathematical or physical truth.

This distinction should remain in public documentation so users can reproduce
results without mistaking a project claim for an independently proved theorem.

--------------------------------------------------------------------------------
30. IMPLEMENTATION AUTHORITY AND DOCUMENTATION POLICY
--------------------------------------------------------------------------------
The Help/README documents the intended mathematical and software specification of
Groovebox. When auditing a particular release, the released source code and its
regression tests are the final implementation authority.

A discrepancy between prose and implementation should be treated as a
documentation defect to be corrected, not silently interpreted as a new rule.

The canonical authority is the project's single-source composition model. Legacy
engine attributes may exist as compatibility mirrors, but canonical save/load,
export, provenance, and cross-media boundaries must remain synchronized through
the canonical authority layer.

--------------------------------------------------------------------------------
31. OFFICIAL PROJECT TERMINOLOGY
--------------------------------------------------------------------------------
Official software names:
    Groovebox
    Mathematicians Groovebox

Primary mathematical framework:
    Meum Calculus

Related project-defined arithmetic/operator framework:
    Operator Theory (OT)

Reference work:
    Scientific Theories and Inventions — Noah Girouard King (Eski)

These names should be used consistently in the application, Help, README,
project archives, and release documentation.

--------------------------------------------------------------------------------
32. CREDITS AND ATTRIBUTION
--------------------------------------------------------------------------------
Main editor and author:
    Noah Girouard King (Eski)

Development and research assistance credited by the project:
    Grok (xAI)
    Gemini (Google)
    Claude (Anthropic)
    ChatGPT (OpenAI)
    Mistral.ai (Mistral)
    Meta AI (Meta)
    GitHub Copilot (GitHub)
    Cursor Grok 4.6
    jcode(1jehuang)
    opencode (anomalyco)

Credits describe project contributions and tooling/assistance; they do not imply
endorsement, ownership, authorship, or scientific validation by those services.

--------------------------------------------------------------------------------
33. LICENSE / PROJECT POLICY
--------------------------------------------------------------------------------
Keep the project-specific license and attribution files supplied with the
distribution.

This documentation describes implementation behavior and project-defined
mathematics. It must not be read as a scientific claim that Meum Calculus or
Operator Theory is an established mathematical theory.

Established number-theory statements should be limited to statements that follow
from ordinary definitions and proofs. Project-specific claims should remain
explicitly labeled CLAIMED EXACT and tied to a reproducible test contract.

--------------------------------------------------------------------------------
34. FINAL RELEASE PRINCIPLE
--------------------------------------------------------------------------------
Groovebox is intended to be one mathematical composition environment rather than
three disconnected programs.

    ONE CANONICAL COMPOSITION
             │
       ┌─────┼─────┐
       ▼     ▼     ▼
     AUDIO VIDEO  GAME

The purpose of the canonical model is correspondence, reproducibility, and
creative control: the musician/researcher authors a composition once, and each
compatible engine interprets that same canonical information in its own medium.

The mathematical framework is part of the creative and computational identity of
the project. The reproducibility contract is part of its engineering identity.
The distinction between project-defined mathematics and independently established
mathematical or physical truth is part of its documentation standard.

================================================================================
  End of Help — Groovebox / Mathematicians Groovebox
  Main editor and author: Noah Girouard King (Eski)
================================================================================


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


## V17 MEUM DIRECT SPATIAL MATH
The audio engine includes a bounded Meum spatial effect using direct x,y,z potential, standing-wave, and neighboring-state expressions. OT ON and OT OFF use the same mathematical expressions and numerically equivalent execution handles; the OT switch does not retune this effect. Factory defaults are Adaptive Fit 50%, Phase Lock 50%, sample morph ON, guard ON, and all global/window modulation depths 100%.


--------------------------------------------------------------------------------
PARAMETRIC MATH BACKGROUND — BOOK-DERIVED MEUM / SERIES EQUATION CELLS
--------------------------------------------------------------------------------
ParametricMathBackground still draws exactly 12 compact equation cells at a time
for predictable paint cost, but those 12 cells now page through a larger corpus
transcribed from THIS BOOK. Long expressions wrap rather than being replaced by
short implementation identities. The display corpus includes:

  • Meum defining root:
      (M−1)^M + (M−1)^(1/M) = 2^M/M² − M
  • Meum alternate identities:
      2^M/M² − (M−1)/M = M²
      (M−1)M + (M−1)(1/M) = 2^M/M² − M
      2^M/M² + 1 = M³ + M
      2^M/M² − M³ = M − 1
  • Full inverse-isosceles-sine series:
      isn⁻¹(x) = Σₙ₌₀^∞ [(2n)! x^(2n+1)]/[16^n (n!)² (2n+1)]
  • Full inverse-isosceles-cosine relation/series:
      ics⁻¹(x) = π − Σₙ₌₀^∞ [(2n)! x^(2n+1)]/[16^n (n!)² (2n+1)]
                 = π − isn⁻¹(x)
  • Cyclic isn series:
      isn(x) = Σₙ₌₁^∞ [x^(2n)/(2n)!] i^n,  i=√(−1)
  • Complement series:
      1−isn(x) = Σₙ₌₀^∞ [x^(2n)/(2n)!] i^(n−1)
  • Component functions:
      isx(γ)=1−isn(γ)
      isy(γ)=1−isn(γ−π/2)
  • π series simplified from isn⁻¹:
      π = Σₙ₌₀^∞ [(2n)! 2^(1−2n)]/[(n!)²(2n+1)]

The spatial field/wave/state equations remain in the rotation as Groovebox
application equations. The background remains display-only and does not execute
these strings in the realtime audio, visual, or game paths.


## Canonical signal control — never below 50%

The canonical signal-control contract is always **50–100%**, with or without a carrier. This is separate from the user-data survival floor. User-owned data is never rewritten or downmixed merely because program space is full. Canonicals can instead materialize their own sequence, automation, attack/release, AM, FM, PM, phase, patch, script, domain, or global-effect layer.

### Sequence → Playlist mapping

Each selected sequence has an editable **Wrap to Playlist** / **Schedule Across Playlist** mode. Wrap restarts/fits the sequence inside each playlist row. Schedule keeps the sequence on the playlist clock and permits a sequence whose length does not match the playlist grid to cross or be cut by row boundaries.

Playlist Paint adds **Auto (sequence)**, **Force Wrap**, and **Force Schedule**. These are routing/mapping controls; they do not rewrite the sequence's user-authored steps.

## V20 — CANONICAL CONTROL OPTIONS / PAINT TEMPO

Canonical signal control is always 50–100%. The percentage is earned by a selectable strategy, not merely clamped: Coverage Adaptive, Engine Stack, Full Canonical, or Seeded Baseline. The canonical system may materialize sequence, automation, pitch, amp, phase, trigger, AM, FM, PM, and effect-layer structures in canonical-owned runtime overlays when user program space is full. It does not rewrite a user parameter to make room.

Paint Tempo modes are Row Loop · Wrap, Center Snap · Schedule, Retrigger Rows · Schedule, and Canonical Cut · Row Boundaries. Wrap repeats a sequence for the complete BPM-derived row duration and cuts at the row end. Schedule can align to the row grid, center a sequence, retrigger at row starts, or permit boundary cuts. Explicit Force Wrap / Force Schedule controls remain higher priority than canonical automatic scheduling.

Canonical-owned synth slots expose direct canonical amp, pitch, phase and trigger values and can render simultaneous deterministic chord ratios. User-owned program slots remain readable and are not downmixed solely to increase canonical authority.


## V23 — MULTI-TARGET BLEND / TIME-OFFSET / CARRIER PROOF

### Multi-target Playlist Paint

Playlist overlap is no longer limited conceptually to one primary + one secondary. A painted row can retain `blend_targets` and normalized `blend_weights` for multiple secondary instruments. Numeric synth parameters use the multi-target weighted blend primitive; Script, Domain, Synth, and Patch identities remain represented in the playlist consensus.

### Time offsets

Operator-specific `operator_time_offsets` are authoritative render offsets in seconds. Blended targets also retain `blend_time_offsets`, so multiple targets may enter the same playlist row at different absolute offsets. Sequence mapping (Wrap/Schedule) and Paint Tempo remain independent of those offsets.

### Carrier is a modulation/reference source

An imported WAV or video-derived audio carrier is not treated as an uncontrolled third additive bus. It can contribute as:

  • Global Input XMOD modulation reference
  • 50% phase-reference steering of synthesized voices
  • optional Global Convolve kernel source
  • carrier-aware seed/context information

The carrier therefore modulates/steers the composition rather than bypassing the canonical/user blend contract.

### Optional Canonical Live Overblend composition contract

At the explicit waveform-composition boundary, Groovebox uses an adjustable crossfade:

    M0 = (1 − b) · U + b · C
    b = Canonical Live Overblend / 100

where `C` is the canonical-engine contribution and `U` is the user-data/live contribution after bounded carrier-derived modulation. `b` ranges from 0 to 1 and the two waveform coefficients always sum to 1. The default is **b = 0**, preserving maximum user/live waveform dynamics; **b = 0.50** reproduces the legacy 50/50 waveform blend. Canonical authority, activity, convolution, phase, timing, synthesis and modulation remain separate from this optional additive waveform share. Canonical-only rows fall back to `C` so generative material does not become silent.

This is a **coefficient contract**, not an energy/RMS theorem. Later nonlinear operations such as EQR, vector conversion, the intentional master hard clip and optional effects can change measured amplitude. The exported provenance records the selected overblend coefficient and pre-effect branch ledger so the distinction remains auditable.

### Save / Load / Export parity

Project save/load preserves playlist blend targets, blend weights, time offsets, Paint Tempo, sequence mapping, canonical control strategy, canonical runtime overlays, carrier references, sample-morph state, global modulation state, Master Vector state, automation, sequence banks, scripts, patch connections, domain equations, notes, UI controls, and the canonical blend ledger. Audio/video/game exports use the same canonical snapshot/fingerprint and carry the blend-contract provenance.


### v24 UI / Canonical additions — Wavetable Projector & Automator anchoring

The global Canonical Morph Bridge now lives directly beneath GLOBAL · COMPOSITION CANONICALS in the upper-right canonical deck. Global XMOD, Input XMOD, and the four editor-window modulation depths are kept in the lower editor deck and do not control Master Volume.

The new **GLOBAL WAVETABLE PROJECTOR** provides 1D Wave, 2D Field, and 3D Resonance-inspired representations with phase, curvature, twist, and fold shaping. It is a global wavetable guide for the Master Vector Synth. User field and deterministic canonical guide are blended 50/50; the projector does not replace canonical composition or Master Volume. Its state is project-save/load persistent and is included in the same render/export pathway.

The Automator teleport inspector is anchored at the selected cell's lower boundary midpoint, with Operator, Sequence, and Offset controls remaining attached to the selected automation step.


**Automator timing:** the automation strip now has an explicit **Wrap / Syncopate** mode. Wrap tracks the active Sequencer length and cycles its control points; Syncopate permits an independent polymetric length using the existing ± syncopation control. The selected mode is saved with the project and restored before live rendering/export.


## CANONICAL ACTIVITY HANDOFF — 2026

Groovebox now treats the 50% requirement as an activity/continuation architecture, not a post-mix clamp. Canonical continuation maintains an autonomous mathematical stream after user input ceases. Shared user/canonical coordinates include time, rhythm, pitch, envelope, phase, and modulation. The canonical activity ledger records coverage separately from the optional Canonical Live Overblend waveform coefficients (50% canonical waveform by default). The imported carrier remains a modulation/reference source rather than an uncontrolled third additive bus.

The project snapshot persists canonical continuation state and its activity ledger so save/load/export provenance retains the same model. The activity metric is not a claim of 50% final RMS after nonlinear processing; clipping and nonlinear effects can change energy.


## Algorithm XMOD + Per-Sequence Algorithm Editing (2026)
- **Edit Algorithm Per Sequence** forces the number-theoretic step algorithm to address only the selected instrument and selected sequence.
- **Algorithm XMOD Local 0–200%** controls algorithmic cross-modulation for the active local instrument/sequence.
- **Algorithm XMOD Global 0–200%** controls the global algorithmic cross-modulation depth across the composition.
- The two controls are independent and saved/restored with the project; 100% is neutral.
- The existing global/user XMOD and imported-carrier Input XMOD remain separate from Algorithm XMOD.
- The Global Wavetable Projector is a shared 1D/2D/3D guide feeding Master Vector; its user/canonical guide remains a 50/50 structural blend.


### Meum Spatial Activity Resolution (v28)

Groovebox now includes a direct X/Y/Z activity-field resolver between the canonical and user buses. The resolver uses explicit orthogonal coordinates and local neighbor propagation as a deterministic composition mechanism. It compares canonical and user activity with an L1 activity modulus and structurally expands the canonical branch to the user activity modulus when needed before the optional Canonical Live Overblend boundary (50% by default). This is an algorithmic signal-activity invariant, not a final-output limiter.

Shared user/canonical features are tracked across 12 coordinates: time, rhythm, pitch, envelope, phase, modulation, tempo, AM, FM, PM, wavetable/vector, and playlist mapping.

`Edit Algorithm Per Sequence` forces the number-theoretic step algorithm to write only the currently selected instrument + selected sequence. `Algorithm XMOD Local 0–200%` and `Algorithm XMOD Global 0–200%` independently control the local/global algorithmic cross-modulation depth.


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
minimum remains 0.50 even with no carrier. The source-composition boundary is independently adjustable as:

  M0 = (1 − b) U + b C,    b = Canonical Live Overblend

The default is b=0 for maximum live/user dynamics; b=0.50 reproduces the legacy
50/50 source blend. The 100% maximum refers to canonical control/authority; it
is independent of waveform overblend and is NOT a claim of post-effect RMS energy.

MEUM CALCULUS / SPATIAL ACTIVITY
  Direct X/Y/Z coordinates track temporal position, normalized user activity,
  and local gradient. Neighbor propagation uses a deterministic six-neighbor-like
  temporal reduction; the canonical field is expanded to at least the user L1
  activity when necessary before the optional live-overblend boundary. This gives a measurable
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
- **Canonical→Instrument Convolve:** bounded **0–100%** control. At 100%, canonical material is the convolution reference while the transformed user branch remains directly audible. Final waveform share is independently controlled by **Canonical Live Overblend**, default **50%**.
- **Maximum instruments:** increased from 64 to **128** for the active synth/visual ensemble and canonical master identity lattice.
- **Default playlist row length:** **8 beats**.
- **UI initialization:** Master Volume value is now constructed before stylesheet/object-name access, eliminating the `lbl_master_vol` startup AttributeError.

CANONICAL RESONANCE / 50–150% STABILITY PASS (V34)

  • Canonical resonance/activity is an independent 50–150% continuation-drive control; it is not master volume and does not alter the independently selected Canonical Live Overblend coefficients.
  • Full Canonical signal authority defaults to 100%. Missing canonical lanes are materialized in canonical-owned runtime overlays instead of weakening authority or rewriting user-owned data.
  • 100% canonical→instrument convolution is bounded as a normalized influence transform; the transformed user branch retains a direct 50% user component.
  • Playlist row length defaults to 8 beats; Playlist Rows remains the separate arrangement-row count control.
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
- Maximum live instrument capacity is 128; default playlist row duration is 8 beats.


## V35 Canonical Command — Wavetable, Automator, Playlist Routing

Under canonical authority, **Master Vector Synth**, **Global Wavetable Projector**,
**Global / Input XMOD**, **Algorithm XMOD**, and **Canonical Resonance** are
first-class destinations for playlist Auto Target, Automator sequence params,
modular patch targets, and algo routing — the same blend/coverage surface as
Script Tag / Domain Tag / Synth Snapshot / Modular Patch.

### Playlist Auto Target names
- `master_vector_x` | `master_vector_y` | `master_vector_z` | `master_vector_drive`
- `wavetable_frame` | `wavetable_phase` | `wavetable_curvature` | `wavetable_twist` | `wavetable_fold`
- `global_xmod` | `global_input_xmod`
- `algorithm_xmod_local` | `algorithm_xmod_global`
- `canonical_resonance`
- `synth_panel_mod` | `patch_mod` | `script_mod` | `domain_mod`
- classic macros remain: `eqr`, `fractalizer`, `pkp_envelope`, `filter`, `drive`, `pitch`

Coverage scales depth; Direction Vector sets sign; Blend Partner and multi-target
`blend_weights` mix instruments on one row. Modular Patch stays the edge list.
Algo XMOD local/global depth sequence algorithms.

### Automator sequence (end-to-end)
1. Paint/toggle Automator steps (orange strip). Timing: **Wrap** or **Syncopate**.
2. First click teleports Operator / Sequence # / Offset; second click toggles ON/OFF.
3. Popup sets morph, attack/release, and any numeric param including Master Vector,
   Wavetable, XMOD, and Resonance names above.
4. Lanes interpolate longitudinally between enabled steps; length may lock to the
   Sequencer or run polymetric (SYNC OFF + syncopate delta).
5. `apply_playlist_automation_to_ui` pushes those targets onto live UI + canonical
   state so Live Play, Export, Video, and Game share one command surface.

### Scripting directions
- Seed field is a full script panel. Names: `t`, `x`, `y`, `z`, `pi`, `e`, `tau`,
  `PHI`, `MEUM`, `MEUM_NORM`, `MEUM_INV`, `isn`, `ics`, `clamp`, `lerp`, `choose`, …
- Example — resonance activity from time (natural 50–150% band):
  `return lerp(0.50, 1.50, 0.5 + 0.5 * sin(t * MEUM))`
- Example — vector-like live_parametrics token:
  `return sin(t), cos(t * MEUM), sin(t * PHI_INV)`
- Playlist **Live Parametrics** may carry a one-phase predicted blob read with
  Script / Domain / Synth / Patch structure columns.
- **Wavetable Synth** (engine combo) + freehand `WavetableCanvas` shapes are
  per-instrument; **Global Wavetable Projector** (1D Wave / 2D Field / 3D Resonance)
  feeds Master Vector conversion on the shared render path (50/50 user/canonical guide).

### Resonance — 50–150% vs 0–200%
Canonical Resonance / Activity is **activity / continuation drive** (not Master
Volume and not the optional Canonical Live Overblend waveform mix). The legal band follows User Data Overwrite:

| Mode | Control | Range |
|------|---------|-------|
| **Protect ON** (default) | `Canonical: skip overwrite user composition` checked | **50–150%** |
| **User Data Overwrite ON** | Protect unchecked | **0–200%** |

- Protect ON: user locks kept; 50% floor with active userdata; up to 150% when user activity is low.
- Overwrite ON: userdata snapshotted, locks wiped; 0% = silent autonomous activity; 200% = maximum continuation while engines may rewrite the composition.

The Resonance spin and status label switch with the protect toggle.

### Automation pattern library (playlist combo)
Additional lanes: Master Vector X/Y/Z sweeps, Wavetable Frame Morph / Phase,
Global XMOD Depth, Canonical Resonance Drive, Algo XMOD Local Sweep — selectable
from the playlist automation pattern combo alongside classic filter/resonance ramps.


### TrackOffset (user-owned)
Global TrackOffset is user-set in **beats**; legacy per-sequence `track_offset`
remains in playlist-row units — both use the same ownership model as Canonical Resonance amount.
Audio, video, and game engines respond to them; canonical engines do **not**
treat them as modification handles and do not rewrite them. Negative starts
earlier; positive later. Values are mirrored into `composition_snapshot` and
game composition meta for all consumers.


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

Heuristic composition is split into two independent reversible writers: **HEURISTIC WRITE STEP** and **HEURISTIC WRITE AUTOMATION**. Both share the GLOBAL / LOCAL scope selector, but each has its own exact revert memory.
These are the **only two Heuristic Composer write controls**. The older separate/third “Heuristic Step Write” direct-lattice button was retired because it duplicated STEP writing and introduced a second revert/activation path. ℤ-Lattice mode, modulus, and depth remain available as inputs to the Heuristic Composer and Algorithm → Seed.

- **HEURISTIC WRITE STEP:** writes only sequence structure (steps, gates, amplitudes, pitches, probabilities, offsets and pattern length).
- **HEURISTIC WRITE AUTOMATION:** writes only the continuous automation lane/tiles.
- **GLOBAL:** each enabled writer applies its own layer across applicable project sequences.
- **LOCAL:** each enabled writer applies only to the selected instrument + selected sequence.
- Switching GLOBAL/LOCAL restores each active writer's previous scope first, then reapplies it in the new scope; turning one writer OFF never removes the other writer's layer.
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

APPLICATION NOTE — GOAVA / NUMERIC TRANSDUCTION
Treating numbers and semantic labels as deterministic compositional inputs gives the app a
repeatable alternative to opaque random assignment. The same numeric identity can be
translated into notes, timing, visual geometry, game signatures and metadata while keeping
provenance. This makes renders reproducible, comparisons meaningful, and regression tests
possible. It does not prove that a generated composition is mathematically optimal; it
does make the generation rule inspectable and repeatable.

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

PROGRAM ID + .MG PORTABLE SAVES
-------------------------------
Use **⌬ Read Program → ID** to read a Python source or ZIP and compute a semantic Program ID plus an exact SHA-256. The semantic Python ID ignores comments, whitespace and docstrings but changes when executable structure changes.

Use **⬆ Export .MG** for Project / Synth / Profile:
- Project restores the complete project/canonical workspace.
- Synth restores into the currently selected instrument slot.
- Profile restores reusable Performance/global/reference settings.

Use **⬇ Load .MG** from Main or **Performance → ⌬ .MG Related**. Every artifact has its own content-derived Artifact ID. Slot names/indexes do not redefine it. Usage history is tracked separately and can include use/load counts, first/last use, common companions, and outcomes. Related results are ranked from Program/Composition provenance, shared parameters/math/tags and longitudinal co-use; recommendations remain derived/advisory and never overwrite userdata by themselves.


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
The book defines inverse isosceles sine as `isn^-1(x) = 2 asin(x/2)`. Groovebox also exposes the inverse-pair coordinate `isn(theta)=2 sin(theta/2)` and the complementary `ics(theta)=2 cos(theta/2)` family.  Operator Theory is enabled by default.  Conventional trig semantics are routed through these identities in hot contiguous native-array paths when that is profitable (`sin(x)=isn(2x)/2`, `cos(x)=ics(2x)/2`); scalar/libm calls remain direct when an extra dispatch would be slower.  Explicit Meum-normalized isn/ics transforms are used where the composition asks for the Meum coordinate rather than conventional sine/cosine.

ENGINEERING NOTE — WHY THE ISOSCELES TRIG PAIR IS USEFUL
The isn/isn^-1 and ics/ics^-1 pairs provide bounded, invertible-on-branch coordinate mappings and a common expression language for audio, visual and game projections.  The implementation separates **meaning** from **execution route**: ordinary DSP/Euclidean trig keeps its conventional numerical meaning, while the same operation can be executed through the project's isn/ics identities and native C++ kernels.  This preserves interoperability while still letting the author's formulas collapse repeated coordinate transforms, share kernels across domains, and remain independently testable.

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

TOTAL CORRESPONDENCE / SELF-PROCEDURE
Groovebox can derive Audio, Visual, Game, UI, and Network manifestations from the same Universal Field ID. Representation part/object counts are chosen after identity and may be raised or lowered without changing the canonical source. Extended visualizer modes display the field prefix, selected projection-cover size, and correspondence score. Correspondence means shared canonical identity/provenance; it does not mean a lossy file format can always be inverted exactly.


## Research note — what the Meum/OT work is actually buying Groovebox

Groovebox now treats the author's Meum/Operator-Theory work as a **computational architecture**, not merely as decorative constants.  The practical advantages are measurable engineering properties: one canonical mathematical identity can be cached and projected into audio/visual/game/UI/network views; Meum-family traversals can be advanced by deterministic modular recurrence instead of rebuilt from an RNG; rational anchors remain available for exact conservation/partitioning; OT keeps inverse/write operations explicit; and the `isn/ics` family provides a compact coordinate vocabulary that can be fused into native array kernels.  These properties reduce recomputation, stabilize cache keys, simplify reversible state transitions, and make Python/C++ parity easier to test.

### MEUM-T1 — existence, uniqueness and irrationality

For the project's formal definition, let `M` be the root in `(1,2)` of

`2^M = M^4 + M^2 - M`, equivalently `F(x)=2^x-x^4-x^2+x=0`.

`F(1)=1>0` and `F(2)=-14<0`, so continuity gives at least one root.  On `[1,2]`,

`F''(x)=2^x(ln 2)^2-12x^2-2 < 4(ln 2)^2-14 < 0`,

therefore `F'` is strictly decreasing; because `F'(1)=2 ln 2-5<0`, `F'<0` throughout the interval, so the root is unique.  If that root were rational, `M=p/q` in lowest terms, then the polynomial side would be rational and hence `2^(p/q)` would be rational.  Unique prime factorization forces `q=1`; but no integer lies in `(1,2)`.  Thus the mathematically defined root is irrational.  Runtime IEEE-754 values are, as always, finite rational approximations of that mathematical value.

### Trigonometric execution model

Operator Theory is enabled by default.  Groovebox distinguishes **semantic trig** from **execution trig**.  Where conventional sine/cosine meaning is required, the result must remain conventional; hot contiguous arrays may nevertheless be evaluated through the project's identities

`sin(x) = isn(2x)/2`, `cos(x) = ics(2x)/2`, with `isn(t)=2 sin(t/2)` and `ics(t)=2 cos(t/2)`,

using the native C++ kernel.  Scalar calls stay on ordinary libm when that is faster, because adding a Python/ABI layer merely to rename the same operation would be a regression.  Where the composition explicitly asks for the Meum-normalized `isn/ics` family, the Meum transform itself is used rather than an equivalence route.  This lets the project apply the author's formulas broadly **without silently retuning conventional DSP, Euclidean geometry, or reference mathematics**.

### What is established, what is empirical

The theorem above establishes the irrationality of the formally defined Meum root.  It also implies that nonzero integer multiples of `M`, `M-1`, `1/M`, and `2-M` cannot form an exact finite rational phase cycle modulo 1.  It does **not** by itself prove that Meum is universally more even than every other irrational sequence, nor does software behavior prove a physical-energy theorem.  Groovebox therefore treats spectral entropy, discrepancy, autocorrelation, collision rate, spatial coverage, cache cost and render cost as benchmarkable questions.  This separation is deliberate: it makes positive results reproducible and gives mathematicians/physicists something concrete to inspect rather than requiring them to accept an application claim first.

### Invitation to review / falsify

The project is intentionally inspectable.  Researchers are invited to challenge the formal Meum definition and proof, compare Meum-family traversals against `phi-1`, `sqrt(2)-1`, `e-2`, `pi-3`, rational controls and seeded pseudorandom controls, and attempt to break Universal-Field reconstruction, part-count invariance, Python/native parity, writer reversibility, or cross-domain identity.  A counterexample is useful: the implementation and documentation should be corrected rather than protected from falsification.

## 2026-09-05 — Full OT-adapted vector trig routing

Groovebox now routes the remaining **NumPy vector sine/cosine call sites in the main runtime** through the OT-compatible trig adapters whenever Operator Theory is enabled (the default). The adapters preserve ordinary sine/cosine semantics through the book identities

\[
\sin(x)=\tfrac12\,\operatorname{isn}(2x),\qquad
\cos(x)=\tfrac12\,\operatorname{ics}(2x),
\]

with `isn(t)=2 sin(t/2)` and `ics(t)=2 cos(t/2)`. Large contiguous arrays can therefore enter the native C++ book-isn/book-ics kernel instead of building extra NumPy trig temporaries. Small/scalar operations retain the conventional libm path where crossing the native ABI would cost more than the arithmetic.

This is an **equivalence-preserving execution rewrite**, not a claim that every Euclidean identity has been replaced by a different geometry. It lets the project use the author's trig vocabulary as an optimization layer while keeping reference DSP/geometry results testable against their conventional definitions. The unified regression suite remains `19 passed / 1 optional PyQt6 skip / 0 failed` after the broader routing pass.

### Research invitation

Groovebox is also an executable research artifact. Mathematicians, physicists, DSP/numerical programmers, generative artists, and simulation developers are invited to test the Meum root theorem, OT equivalence routes, `isn`/`ics` transforms, Universal Field decomposition invariance, traversal distributions, native/reference parity, and performance claims. Useful contributions include proofs or counterexamples, reproducible benchmarks, profiling results, alternative constants/bases, and simpler equivalent formulations.

The project distinguishes: (1) proved statements under its declared definitions, (2) implementation invariants backed by tests, and (3) empirical hypotheses such as whether coupled Meum-family traversal outperforms other irrational or low-discrepancy bases in a particular audio/visual/game workload.

## Author Symbol Language — literal reading guide (Math Symbols defaults OFF (public build))


### Base-16 / squiggle subscale number spelling

The numeric symbol display is **base-16-first, with deliberate exceptions for compact integer and fractional spelling**. Ordinary symbol cells carry values **0 through 15**. A separate semantic **16 / completed-cycle cell** is available when one full cycle is the clearer spelling; it is not treated as a fifth hexadecimal digit. The underlying QSpinBox/QDoubleSpinBox/project value remains authoritative and is never replaced by the compact visual spelling.

The **16 / completed-cycle cell is fully saturated: all 12 main strokes are solid and its four dividing/subdivider bars are also all solid**. Each solid dividing bar counts as **`1/1` in its ordered place**. A dotted dividing bar is not stylistic decoration: it means **`0.5` / half of that ordered place**. Therefore automatic cell `16` uses four solid dividers (solid mask `1111`, dotted mask `0000`); it must never be drawn as four dotted dividers.

Fractions begin *inside the integer/count cell*. A **squiggle on the least-significant integer cell can carry the first fractional subdivision, `2^-1 = 1/2`, without consuming another cell**. If more precision is required, additional fractional cells follow that in-cell squiggle/no-squiggle state. Fractional slot `k` has the base weight

`16^-k = 2^(-4k)`  for `k = 1, 2, 3, ...`.

Therefore the first added subscale cell is weighted `2^-4 = 1/16`, the next `2^-8 = 1/256`, then `2^-12`, and so on. Groovebox uses only as many subscale cells as are needed to preserve the numeric field's visible precision; exact integers omit the fractional chain.

**Spacing is semantic inside a fractional/subscale position.** A spaced straight/count is the full **`1/1` of that slot**. The same straight/count in the **unspaced** authored form is **`1/2` of that slot**. Automatic conversion of ordinary numeric controls uses the spaced/full form so ordinary base-16 fractional weighting remains unambiguous. Explicit authored notation may use the unspaced half-slot form.

Examples of automatic spelling:

- `1.5` -> integer cell `1` with the in-cell half/squiggle; no extra fractional cell is required.
- `1.25` -> integer `1`, no half squiggle, then value `4` in subscale slot 1: `4 * 2^-4 = 0.25`.
- `1.20` -> the formatter may use more than one subscale cell because one `1/16` cell cannot preserve two visible decimal places closely enough. The symbol spelling is a display approximation to the requested visible precision; the stored value remains exactly the application's `1.20` value.
- At slot 1, value `4` spaced contributes `4 * 2^-4 * 1/1 = 0.25`; the same value `4` unspaced contributes `4 * 2^-4 * 1/2 = 0.125`.

The codec identifier written into project/export provenance is `base16-squiggle-crossbar-subscale-v7`. Every glyph packet carries **four ordered cross-bar positions**. Each cross-bar state is explicit: absent = `0`, dotted = `0.5`, solid = `1`. Together with 17 cell values (`0..16`), squiggle/no-squiggle, and spaced/unspaced state, this yields **5,188 precomputed semantic glyph states** (`(16 × 3^4 + 1) × 2 × 2`). Cell `16` is invariant: **all 12 main strokes are solid and all 4 subdividers are solid** `(solid mask 1111, dotted mask 0000)`; alternate dotted/missing 16 faces are invalid. The bundled required sCode symbol ABI validates the same contract, while Qt consumes cached immutable packets rather than re-deriving notation semantics during paint events.

Mathematician's Groovebox starts with **Math Symbols OFF** in the public build because the author notation carries information that an ordinary decimal numeral does not show directly: four-way direction/reference, counted/skipped strokes, contextual stroke modifiers, operation enclosure, continued-series structure, event multiplicity, and variable/result role. **Operator Theory (OT)** is a separate switch: OT ON selects the OT calculation route; OT OFF keeps the symbol display available for comparison. **Math Symbols OFF** exposes the ordinary base-10 / conventional mathematical spelling of the same inspectable value. This makes base-10 a secondary inspection and interoperability view rather than deleting it.

### Literal visual grammar

A numeric cell has **four groups of three strokes = twelve possible strokes**, plus **four ordered cross-bars that every glyph accounts for**. The four pathways are **UP, RIGHT, DOWN, LEFT**. UP/RIGHT are the two positive-oriented pathways and DOWN/LEFT the two negative-oriented pathways, so direction space has two of four negative-oriented choices rather than a single unary minus. A **missing stroke is skipped**. A **straight stroke is an ordinary/full counted stroke**. A **squiggly stroke is contextual**: according to its enclosing expression it can mark imaginary participation, decimal/fractional participation, a half-count (`0.5` rather than `1`), or symbolic doubling (`×2`). In the numeric `base16-squiggle-crossbar-subscale-v7` context specifically, the in-cell fractional squiggle has the explicit `2^-1` meaning described above. Each of the four cross-bars independently carries state `0` (absent), `0.5` (dotted), or `1` (solid); this is semantic data, not decoration.

Four optional separator positions provide the compact counted-state/intersection layer. **Open outer/partial square = multiplication; dotted outer square = sum/difference; solid outer square = division; dotted enclosing square = ordinary continued inner expansion; line-connected solid square = multiplicity/events in place.** Adjacent cells form a row for adjunct addition/subtraction or further contextual composition. A plain box can contain a letter to name a variable.

Role colors are semantic, not magnitude: **red = independent variable; green = independent constant; blue = result; black = dependent constant; white = dependent variable.**

### Portable ASCII analogy

The drawn symbols remain authoritative. Plain-text documents/logs use this analogy when the graphical painter is unavailable:

`U R D L` = up/right/down/left pathway; `|` = straight/full count; `~` = squiggly/context-modified count; `.` = missing/skipped count; `:` = dotted sum/difference enclosure; `[>` = open multiplication enclosure; `[]` = solid division enclosure; `::...::` = dotted continued-expansion enclosure; `-[xN]` = line-connected multiplicity square; `<x>` = boxed variable letter. The ordinary `0..F` values are the base-16-first symbol cells used by the current author-approved Groovebox spelling; the separate semantic value 16 marks one completed cycle. The exact stroke/separator packing remains a Groovebox rendering convention, while the numeric spelling rules above are the current project contract.

Example schematic cell: `U:|||~..|||~..:5<x>` means an UP-oriented boxed `x`, with straight, modified and skipped strokes, and separator state 5. The meaning of each `~` is supplied by the surrounding operation/context.

### Why prefer it contextually?

Use the author symbols when direction, handedness/reference, continued structure, multiplicity, dependency role, or contextual half/imaginary/decimal/doubling information matters. They can keep those relationships visible without repeatedly flattening them into a signed decimal plus separate annotations. Prefer conventional/base-10 notation when exchanging values with software or readers that do not know the glyph grammar, when checking a conventional identity, or when an ordinary scalar is the clearest representation. The switches deliberately allow four comparisons: OT+symbols, OT+base-10, conventional math+symbols, and conventional math+base-10.

### Equation translations — conventional first, author-symbol/ASCII analogy immediately below

The ASCII lines are **analogies of the drawn notation**, not a replacement alphabet. They preserve the best currently specified context; where the source does not uniquely assign a stroke pattern, the line names the operation rather than inventing one.

Conventional: `isn(theta) = 2 sin(theta/2)`  
Author/ASCII: `<isn>[> <theta> [] 2 ] = [>2] <sin>(<theta>[]2)`

Conventional: `isn^-1(x) = 2 asin(x/2)`  
Author/ASCII: `<isn^-1><x> = [>2] <asin>(<x>[]2)`

Conventional: `ics(theta) = 2 cos(theta/2)`  
Author/ASCII: `<ics>[> <theta> [] 2 ] = [>2] <cos>(<theta>[]2)`

Conventional: `sin(x) = isn(2x)/2`  
Author/ASCII: `<sin><x> = []2 ( <isn>([>2]<x>) )`

Conventional: `cos(x) = ics(2x)/2`  
Author/ASCII: `<cos><x> = []2 ( <ics>([>2]<x>) )`

Conventional: `2^M = M^4 + M^2 - M`  
Author/ASCII: `<result:blue> = : ([pow]2,<M>,4) + ([pow]<M>,2) - <M> :`  
Here `<M>` is a boxed/named constant; in the painter it should use the role color appropriate to whether M is independent or dependent in the active expression.

Conventional: `F(x) = 2^x - x^4 - x^2 + x = 0`  
Author/ASCII: `<F><x> = : [pow](2,<x>) - [pow](<x>,4) - [pow](<x>,2) + <x> : = 0`

Conventional contextual direction: `C = sigma * hand * reference * concentric`, with each factor in `{UP,RIGHT,DOWN,LEFT}` orientation state rather than merely a unary sign.  
Author/ASCII: `<C> = [> <sigma> <hand> <reference> <concentric> ]`; direction markers `U/R/D/L` remain attached to the participating cells.

Conventional odd-context transfer: `isn(C*x) = C*isn(x)` (where the selected branch/context makes this correspondence valid).  
Author/ASCII: `<isn>([><C><x>]) = [><C><isn><x>]` — the direction pathway may move outside the odd transform while its context is retained.

Conventional even-context rule: `ics(C*x) = ics(x)` for `C = +/-1` at the scalar parity level.  
Author/ASCII: `<ics>([><C><x>]) = <ics><x> ; keep U/R/D/L context` — the scalar sign can disappear from an even function, but the directional/reference state must **not** be discarded.

Conventional inverse-operation pairs: `+ <-> -`, `* <-> /`, `power <-> root`.  
Author/ASCII: `:sum <-> :difference`, `[>multiply <-> []divide`, `[power] <-> [root]`; reverse operation order when traversing an inverse path where the OT rule requires it.

Conventional continued expansion: `a0 + 1/(a1 + 1/(a2 + ...))`.  
Author/ASCII: `:: <a0> : [] ( <a1> : [] ( <a2> : ... ) ) ::` — the dotted outer enclosure says the inner symbol row is an ordinary continued expansion. A single-square continued-series symbol can leave the inner repetition implicit; multiple delimited squares expose successive series structure.

Conventional multiplicity: `N * event(x)` or `event(x)` repeated N times in place.  
Author/ASCII: `<event><x>-[xN]` — the line-connected solid square carries event multiplicity without requiring N separately drawn copies.

### Source vs. author clarification vs. Groovebox machine convention

The supplied book explicitly describes four sets of three lines, conflicting/nonconflicting directions, optional grid intersections, operation intensity/dynamics, and boxes for variables. The author has clarified for this implementation that missing strokes are skipped; squiggles are contextual imaginary/decimal/half/doubling modifiers; four-way pathways are up/down/left/right; and the border/continued/multiplicity/color rules above are intended parts of the notation. Groovebox's exact bit packing, separator-to-`0..15` index, and ASCII spelling are implementation conventions chosen to make the notation reversible and inspectable. They should not be mistaken for additional claims printed verbatim in the book.
    \n--------------------------------------------------------------------------------\nMEUM LOGIC SEARCH / REVERSE-GREP (PROJECT RESEARCH TOOL)\n--------------------------------------------------------------------------------\nThe current compiler/reverse-decoder experiments assign distinct jobs to Meum\nforms instead of treating every Meum-derived number as interchangeable:\n\n  normalize/key logic:       N(x) = (2 - M) x = [1-(M-1)]x\n  ambiguity/problem locate:  A_p(x) = x / M^p,       p = 1,2,3,...\n  interval prediction:       R_p(x) = (M - 1)^p x,   p = 1,2,3,...\n  ideal-form comparison:     T(x) = x / 2^M\n\nThe Meum root relation supplies a consistency route:\n\n  2^M - M^4 - M^2 + M = 0\n  therefore 2^M = M^4 + M^2 - M.\n\nThe search is LINEAR in responsibility: normalize -> locate ambiguity -> test\ninterval/reflection prediction -> compare already-equivalent target forms ->\nverify -> emit sCode.  2^M is not a command to force program outputs toward one\nnumber; it is a target-coordinate / preference test after behavioral equivalence.\n\nINTERVAL DIRECTION.  Because M>1 and M-1>0, multiplication by (M-1)^p\npreserves the ordinary ordering of real interval endpoints.  A candidate math\ncollapse is therefore stronger when value family, interval, direction, extrema,\ndependencies, and regression behavior agree.  Min/max or slope reversals are\nlandmarks that help reject a false semantic match.\n\nBOOK-CONSTANT SECOND STAGE.  Other named irrational/self-referential constants\nfrom the author's work may be used as additional locator coordinates.  Numerical\nproximity is evidence for where to inspect, not proof of semantic identity.  A\nmatch is promoted only after dependency, interval/direction, cross-resolution,\nand behavioral checks.\n\nWHY() / PROVENANCE TARGET.  A verified sCode reduction should retain the source\naddress X, semantic class Y, normalization, ambiguity probe, powered interval\nprediction, target comparison, and verification certificate so why() can invert\nthe route and explain the emitted syntax.\n\nMATH SYMBOL DISPLAY.  Math Symbols is a reversible presentation layer only.\n0 is the empty author cell. Numeric values remain unchanged underneath.  All\nQSpinBox/QDoubleSpinBox controls, including controls created later in floating\nwindows, are discovered and masked while unfocused; focusing a control reveals\nthe ordinary editable number, and leaving focus restores its symbol mask.\n


## 2026-09-07 project-local media / FFmpeg / Draw-Record completion

- Each project owns a named folder: `<Projects>/<Project Name>/`. The `.MCC`, samples/imports, recordings, layered Draw/Record sources, audio/video/frame exports, games, metadata and index live below that root. Legacy/external project documents use a sibling project workspace until the next canonical save.
- Main Window and Performance resolve the same active-project sample/render/game roots. Imported operator samples and Draw/Record layers are copied or recorded into the project before they become persistent sources.
- Runtime codec behavior is pinned to `./bin/ffmpeg` + `./bin/ffprobe`. System-PATH fallback is disabled. First launch and `build.py` invoke the provisioning step when the local pair is absent; packaged builds include that exact pair.
- Draw and Record share the layered Signal Lab. Draw, Sample and Record layers can be combined with independent relative-time scalars and rendered/sent together.
- GOAVA Radio uses a fixed default viewport independent of artwork size. Larger artwork remains at authored scale and is accessed by a normal interactive scrollbar.
- Heuristic STEP and AUTOMATION remain the only persistent heuristic writers. `APPLY HEURISTIC → SEQ SYNTH` is a one-shot project edit that authors per-sequence synth/script/domain/patch context without creating notes or automation. Applied algorithms can modulate the numeric variables of an existing automation-resolved state at runtime, but do not compose automation points.

## 2026-09-07 final project-local media / UI contract

- **Draw + Record are merged** into one layered Draw / Record / Sample Lab. Add drawn, microphone-recorded, or imported sample layers in one editor, then render/send the result globally or to the selected operator.
- **Project-local storage** keeps samples, recordings, layers, audio/video/frame exports, games, and metadata under the named project folder; Performance and the main window resolve the same workspace.
- **GOAVA Radio artwork viewport is fixed at 384×148**. Artwork remains at authored/native scale and scrolls horizontally/vertically when larger; artwork size never resizes the panel.
- **Apply Heuristic → Seq Synth** is a one-shot sequence-context authoring operation for synth preset/mod patch/script/domain fields. It does not add another persistent heuristic writer.
- **Algorithm XMOD parity:** applied Algorithm processing can modulate existing synth/sequence automation variables with the same runtime reach as its step-side effect; it does not compose step or automation lanes.
- **Local FFmpeg contract:** runtime media calls resolve only the project `bin/ffmpeg` + `bin/ffprobe` pair. First-launch/build provisioning must populate and validate that pair before execution; PATH codecs are never selected by the application runtime.


## Performance · Record / Import / Draw Video Clip (2026-09-07)
Performance now includes **🎥 Record / Import / Draw Clip**.

- Explicit **Camera**, **Microphone**, and **Tablet / media source** selectors with Refresh Devices.
- Live **Camera Preview** and **Mic Preview** level meter before recording.
- Record selected camera + microphone directly into the active project's `recordings/` folder.
- Import video from ordinary files or mounted/MTP tablet media into the same project folder/index.
- Basic RGBA image paint layer: Brush, Eraser, Line, Rectangle, Ellipse, color picker, size, Undo, Clear.
- **Take Picture From Camera** captures one fresh frame into a new drawable layer. If preview/recording was not already active, Groovebox opens the selected camera only for the snapshot and releases it immediately afterward.
- Camera/microphone ownership is demand-driven: idle mic metering is stopped, stopping preview releases the capture objects, stopping a recording releases the physical camera before/while file finalization continues, and leaving the video workspace releases idle capture devices.
- Time-varying graph lanes: layer opacity, X, Y, scale, rotation, Drawn Sound pitch/gain, and Sound→Color amount.
- **Draw Sound**, **Color→Sound**, and **Sound→Color** are independent and OFF by default.
- **Color→Sound Translation Detail** is a final-mix option: Off / Basic / Detailed. Off performs no color-derived sound calculation.
- Basic mode maps global hue/saturation/value; Detailed mode deterministically maps multiple color regions into a partial bank.
- Final generated sound mixes with source audio using FFmpeg `amix normalize=0`. No normalizer, limiter, compressor, or extra generic clipper is introduced.
- Paint/graph state is saved to the active project's `layers/`; rendered clips are indexed with project video exports.


### Main Window access
The Main Window **✎🎙🎥 Draw / Record / Video** button opens the same project-shared media workbench. Its audio tab retains the layered Signal Lab, while its video tab exposes the full camera/microphone/tablet device selectors, live camera preview, mic meter preview, camera+mic recording, tablet/video import, paint layer, time-varying graph lane, optional Draw Sound / Color→Sound / Sound→Color paths, and final Color→Sound Translation Detail. Video Clip state is synchronized with Performance project state on save/load.

## Canonical Live Overblend default
Canonical Live Overblend now defaults to **50%**, preserving the net 50/50 user/canonical waveform contract. The control remains adjustable: 0% selects the user waveform branch only, 50% is equal user/canonical waveform share, and 100% selects the canonical waveform branch. The intentional existing master hard clip and its 50% Clip/Gain default are unchanged.

### Storage Maintenance and Recovery

Open **Performance → Storage** to see Groovebox-managed storage and disk free space. Safe emergency cleanup removes only cache/temp/log/incomplete-recording scratch data. Project documents, imported originals, completed recordings, autosaves, and exports are protected from that action. Export cleanup and unreferenced-media deletion are separate, explicit confirmations.

Every project autosave carries the working Project Title, Project Notes, and project path. Startup recovery shows those details and offers **Recover**, **Delete Autosave**, or **Ignore for Now**. Recover restores the autosaved workspace without automatically overwriting the last explicit project save.

Known Grooveboxes history is metadata-only and can be cleared in **Performance → Drive / Clone** using **Forget Selected** or **Reset Known Grooveboxes History**. This does not delete anything from the Nearby Inbox.

On the sOS appliance, writable Groovebox data lives under `/var/lib/groovebox`; the launcher and installer auto-create and write-test the required project/media/export/cache/temp/log/state/network directories before ordinary file operations begin.

## Four Canonicals + 3D Voxel Draw/Record (2026-09-10)

The public composition canonical row is now exactly **SEEDED / RAND / LOCK / GOAVA**. All four buttons are independently selectable, color-coded, and use the same button footprint. **Euclidean Rhythm Assist** remains available as a rhythm helper but is not a fifth canonical vote.

- **SEEDED** is deterministic from the project seed.
- **RAND** captures one fresh operating-system entropy token when switched ON. That token is then frozen into project/Undo/export provenance so playback and renders reproduce the generated state until RAND is deliberately reactivated.
- **LOCK** controls phase/relationship behavior. Its main level is joined by tuned characteristic controls: Coupling 62%, Timing Pull 50%, Pitch/Detune Link 62%, Velocity Link 65%, Phase Spread 20%.
- **GOAVA** remains independently selectable. When RAND and GOAVA are both active, the entropy still originates from RAND; GOAVA shapes/maps that captured random state.
- **Canonical Levels** for SEEDED, RAND, LOCK, and GOAVA live in the bottom **CANONICAL MORPH BRIDGE**. These are real engine contribution levels, not display-only controls.

The four levels and LOCK characteristics are first-class composition state: they are included in project save/load, Undo/Redo snapshots, canonical fingerprints, export provenance, and the same render state used for WAV, MP3, and MP4 output.

**Draw / Record · 3D Voxel Kit** is available from the shared media controls. It supports X/Y voxel drawing and erasing on selectable Z slices, a project-wide **Overall Alias** control, video-frame voxelization, OBJ/PLY/STL import plus glTF/GLB model references, and OBJ/PLY geometry export. The same project-owned voxel state is rendered by the video/scenograph path and is available to the game/export context. Voxel geometry, model reference, grid size, alias amount, and canonical contribution state all round-trip with the project.
