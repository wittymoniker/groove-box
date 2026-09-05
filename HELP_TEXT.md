
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
  2) Seeds (irrationals: pi, e, Meum ≈ 1.1975807343, …) are geometric anchors.
  3) Empty slots are for convergent harmonic fill, not noise dumps.
  4) Redundant definitions are simplified first so fill engines have free capacity.
  5) Only inputs with *net effect* on the playlist timeline are treated as
     protected user data; silent or off-timeline data may be reshaped.

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
  • get_numeric_seed()  — composition-state (t = 0.0). Used for RNG seeding,
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
      return np.sin(x * 3.0) * np.cos(y) - z

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
    scipy          WAV I/O helpers, signal utilities
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
    python3 -m pip install numpy scipy PyQt6 sounddevice Pillow

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
    python3 -c "import numpy, scipy, PyQt6.QtCore, sounddevice, PIL; print('OK')"
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
    M = MEUM = 1.1975807343385265188

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

For a nonzero denominator:
    |OT_DIV(a,b)| = |a|/|b|

with sign taken from a. The project defines 0/0 = 1 in OT mode. Division by zero
for nonzero a uses the project's large finite sentinel convention. These are
compatibility rules, not ordinary field arithmetic.

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
PARAMETRIC MATH BACKGROUND — 12 MEUM EQUATION CELLS
--------------------------------------------------------------------------------
The ParametricMathBackground draws exactly 12 compact equation cells at a time.
They are a visual index of the mathematical vocabulary used by Groovebox, not a
separate audio calculation path. The displayed direct forms are:

  1. Φ(x,y,z) = q / √(x²+y²+z²)
  2. ψ(x,y,z) = Σ Aₙ sin(nπx/Lₓ) sin(mπy/Lᵧ) sin(kπz/L_z)
  3. Sₜ₊₁(x,y,z) = Σ_neighbors Sₜ(x±Δx,y±Δy,z±Δz) · W_g
  4. ∇²Ψ(x,y,z) = S(x,y,z)
  5. isn(x) = 2·sin(x/2)
  6. ics(x) = 2·cos(x/2)
  7. isn⁻¹(y) = 2·asin(y/2)
  8. ics⁻¹(y) = 2·acos(y/2)
  9. F_M(x,y,z,t) = isn(M·t+x)·ics(M⁻¹·t+y)+z
 10. uₙ = sin(nπx/Lₓ)·sin(mπy/Lᵧ)·sin(kπz/L_z)
 11. W_g = 1/(1+√(Δx²+Δy²+Δz²))
 12. r = √(x²+y²+z²)

The engine's existing book-derived isn/ics family remains executable and the
ParametricMathBackground is intentionally display-only. Operator Theory can
select an equivalent execution route for supported operations without changing
the displayed Meum expression or its declared mathematical role.

If the user's source book is supplied as a file, additional exact book equations
can be incorporated into the indexed 12-cell vocabulary.


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

### 50% linear composition proof

At the explicit composition boundary, Groovebox uses the source-coefficient invariant:

    M0 = 0.50 · C + 0.50 · U

where `C` is the canonical-engine contribution and `U` is the user-data contribution after any bounded carrier-derived modulation. Therefore:

    canonical coefficient >= 0.50
    user-data coefficient >= 0.50
    canonical coefficient + user-data coefficient = 1.00

This is a **coefficient proof**, not an energy/RMS theorem. Later nonlinear operations such as EQR, vector conversion, and hard clipping can change measured amplitude and can destroy a literal 50/50 energy decomposition. The exported provenance records the contract and the measured pre-effect branch ledger so the distinction is auditable.

### Save / Load / Export parity

Project save/load preserves playlist blend targets, blend weights, time offsets, Paint Tempo, sequence mapping, canonical control strategy, canonical runtime overlays, carrier references, sample-morph state, global modulation state, Master Vector state, automation, sequence banks, scripts, patch connections, domain equations, notes, UI controls, and the canonical blend ledger. Audio/video/game exports use the same canonical snapshot/fingerprint and carry the blend-contract provenance.


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
Volume, not the 50/50 C/U mix). The legal band follows User Data Overwrite:

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
Global TrackOffset and per-sequence `track_offset` are user-set timing controls
in playlist-row units — same ownership model as Canonical Resonance amount.
Audio, video, and game engines respond to them; canonical engines do **not**
treat them as modification handles and do not rewrite them. Negative starts
earlier; positive later. Values are mirrored into `composition_snapshot` and
game composition meta for all consumers.
