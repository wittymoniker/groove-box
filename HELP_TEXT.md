```text
MATHEMATICIAN'S GROOVEBOX — README / HELP
=========================================

CURRENT BUILD: FEATURES, CONTEXT AND PRACTICAL LIMITS
----------------------------------------------------
This supplements the detailed chapters below. It describes the preserved working
V3 interface and selectively merged features, not the comparison main windows.
Use the Help search box/Find next button, Enter, or Ctrl+F/Cmd+F to find a topic.

NAVIGATION AND EDITING ROOM
  Composition and playback/export have separate horizontal AND vertical scroll
  areas. Scroll within the relevant area to reach its lower/right-hand controls.
  The Workspace menu jumps to major sections; narrow toolbars can place actions
  in their overflow menu. The large master stage is not a substitute for its
  parameter editors: open/edit the appropriate synth panel, scrolling as needed.
  Existing instrument, keyboard, project, hardware, audio/video/game and export
  controls remain available. The detailed chapters explain their core workflows.

ANY WAVE WITH CONTEXT: REPRESENTATION IS NOT UNIVERSAL GENERATION
  A supported import/processing path can accept finite sampled waveform data
  beyond the built-in oscillator presets, within that path's sample type, channel
  layout, sample rate, length and memory limits. Effects/conversions may resample,
  mix channels, quantize, normalize or clip data. Not every path preserves every
  source value, and nonfinite numeric values are not meaningful sound promises.

  Generators produce the families their implemented algorithms define. Importing
  or editing a wave differs from generating it from a seed; there is no proof a
  seed generator reaches every representable wave, visual or game.

  Context includes the seed, time/playlist position, instrument/slot, user edits,
  curves, modulation, bindings, active engines and enabled live sources. Context
  affects output only where an actual synth, renderer or game handler consumes
  it. Stored metadata alone does not add a new algorithm, coupling or game rule.
  Shared context schemas are extensible data, not a universal context interpreter.

  Repeatability requires matching relevant inputs/settings on a supported
  deterministic path. True-random modes, camera/microphone input and other live
  events are not made repeatable by saving a seed. Do not assume bit identity
  across different numerical backends.

  RAM, disk, CPU/GPU time, precision, codecs, devices and control ranges remain
  finite. Clip-studio export controls currently allow durations up to 86400 s,
  rates up to 120 fps and sizes up to 3840 by 2160. These control maxima do not
  mean a laptop can render the maximum combination. Generated games use their
  implemented world/objective/context rules, not arbitrary game logic.

CORE WORKFLOW AND USER OWNERSHIP
  Choose a seed/engines, generate, then edit instrument synths, steps and the
  arrangement. Canonical engines own their generated/untouched material; deliberate
  user edits must not be treated as permission to overwrite user-owned data.
  Live overlays, imported samples and generated assets are not automatically
  replacements for the saved canonical composition. Save Project preserves
  editable state; exported media is a render. Keep media assets with the project.

MASTER GEOMETRY AND MODULATION
  Vector, wavetable, bouncing-ball and cellular lanes contribute configured shape/
  modulation. Per-instrument parameters and shared master controls are distinct.
  XMOD scales shared modulation; Reset Master Mods restores those shared controls,
  not the entire song or every instrument. GOAVA ensemble amount is separate from
  GOAVA level. The stochastic selector chooses its listed random/PROB/GOAVA mode.
  Shared audio bus gains and background scheduling weights are different policies.

LIVE JAM, LIVE PLAYER AND GLOBAL DJ
  Live Jam is a reachable performance overlay with live events, macros, envelopes
  and FX. Auditioning it does not automatically rewrite canonical project data.
  Stop/release live controls when finished; record/save explicitly to keep a take.

  The Live Player combines composition playback with enabled keys/microphone.
  Its local DJ chain offers filter, echo, stutter, crush and gate; Reset FX resets
  that chain, not the song. Live Global DJ contributions use host context and can
  include Beat Gate, Harmonic Fold and Spectral Tilt. Local and global FX states
  are separate; zero/disabled contributions should not add an effect.

  Select recording format/destination before Record live play. With video enabled,
  the take includes the live view's enabled layers where captured. Device access
  and local codecs still matter. Video timing follows recorded audio sample count
  and a constant-frame-rate timeline, not GUI timer ticks. Held frames can fill
  gaps; early uncaptured slots can use a neutral frame. This aligns timeline
  length but cannot recover uncaptured images or guarantee hardware-overload timing.

  Takes get distinct names. Disk/encoder failures report errors; failed finalization
  preserves intermediates where available. Keep the reported recovery directory.
  Previewing is not proof a take finalized. Use Export for deliberate high-quality
  offline output; recording captures a live performance, not an editable project.

STEP RECORD, SAMPLE MIMIC AND RANDOM OBJECT
  STEP REC arms the selected instrument/sequence. Played keys enter steps at the
  running playhead or recording cursor. Check the armed target and disarm when
  done; these are touched-step edits, not an audio recording.

  Sample Mimic estimates useful synth characteristics from an available imported
  sample. It is an editing aid, not an exact inverse synthesizer or a guarantee of
  reconstructing arbitrary source recordings. Keep the original for comparison.

  Random Object generates supported audio, image, video or voxel assets. Start
  with short durations/modest image sizes. Auto-binding defaults OFF; enable it
  only to attach to the intended instrument. Layered binding preserves prior
  objects where supported. Repeated seeds use separate folders rather than
  overwriting bound files. Relevant host synth/video context still affects output.

VISUALS, CLIP STUDIO, GAMES AND LAN
  Visualizers, imported media and Video Synth have distinct input contexts. An
  audio change affects visuals only through implemented couplings. Clip Studio
  provides layers, drawing, capture and export; preview and export settings differ.
  Game export uses composition identity plus implemented world/objective/difficulty
  rules; it is not the full editor embedded into an arbitrary game.

  LAN Chat opens/focuses the existing Performance nearby-device/conversation
  interface. Pick the intended peer there. Game host/join is a separate transport.
  Compatible peers, local connectivity and firewall permissions still apply;
  automatic Internet reachability or confidentiality is not implied.

POOLING, PREDICTION AND "MINIMAL" EXECUTION
  Implemented background paths use copied snapshots/private results and latest-only
  requests. Stale plans must not replace newer edits; Qt/document commits stay on
  the GUI thread. Relevant input digests keep a compact sCode pool index from being
  treated as sufficient proof that cached context is reusable.
  Requested job score:
      0.048 * window-selection relevance
    + 0.19758 * activity relevance
    + 1.0 * active tedious-program/buffer-lane relevance.
  Prediction uses one optional process when budget permits, with an intended
  relevance-weighted share up to one third. This is not a hard OS CPU quota.
  Copying/spawning costs memory/time; audio callbacks do not enter this work queue.

  Experimental cooperative commits remain OFF by default. Opt in only deliberately
  with GROOVEBOX_COOPERATIVE_CANONICAL=1. Large legacy GUI-owned commits can still
  pause the UI. Pooling does not make all activation/seed changes asynchronous.
  Reusable math/data paths are streamlined, but the monolithic GUI, compatibility
  layers, full-buffer renders and legacy commits are not minimal everywhere.

LAUNCHERS AND OPTIONAL BACKENDS
  Linux: bash run_hybrid.sh, START_GROOVEBOX.sh or LAUNCH_GROOVEBOX_LINUX.sh.
  macOS: LAUNCH_GROOVEBOX_MACOS.command shares run_hybrid with Darwin provisioning.
  Windows: LAUNCH_GROOVEBOX_WINDOWS.bat prefers the project venv, then Python's
  launcher/system Python, preserving quoted paths and application arguments.
  sOS: LAUNCH_GROOVEBOX_SOS.sh uses the preinstalled appliance runtime; it does
  not run a desktop package installer at boot.

  run_hybrid changes to the project directory, checks required imports, provisions
  codecs/required sCode stage-0 and enters the shared runner. A selected venv path
  is preserved rather than resolving its symlink to base Python. Source launchers
  remove inherited Python home/path/cache overrides; Fedora keeps its matched Qt.
  Optional WebEngine must not block source editor/audio startup. Required Qt
  Multimedia is separate. Optional Rust/C++ can fall back; required native sCode
  stage-0 retains its strict platform/ABI gate. Normal hybrid launches reuse
  existing optional libraries; GROOVEBOX_REBUILD_NATIVE=1 requests a rebuild.

  GROOVEBOX_PYTHON can select an explicit interpreter. Desktop/mobile launchers
  select profiles, not guaranteed support for phone/tablet operating systems.
  Requested sample rate is not proof of hardware support or the negotiated rate.
  relaunch_groovebox preserves original arguments and the common runtime path.
  It retries abnormal signal crashes up to its limit, not normal exits, Ctrl+C/
  termination or ordinary setup/application errors. Diagnose repeatable crashes.

BUILDS, STORAGE SAFETY AND DIAGNOSTICS
  HF15 — Cross-platform support and deployment guide
  Use the source launcher for your OS, or a native package built for that OS
  and architecture. Source compatibility is not physical-hardware certification.
  Run scripts/diagnose_platform.py using the launcher's selected interpreter;
  --json groovebox-platform-report.json also saves a local report. Its checks
  do not install packages, change audio routing or prove real playback.
  Check device permissions, backend/service state and import errors separately.
  A VM boot or successful build does not prove physical hardware audio/video.

  ISO and BUILD_KIT share their runtime inventory. Build Windows EXEs on Windows;
  Fedora builds a Linux executable. Host-side source compilation is read-only.
  The isolated audio fixture tests both analog fallback and aggregate routing
  without configuring the host sound server. These checks do not prove a full ISO
  build, every laptop boot/install, or every dependency combination.
  The documented conventional x86-64 UEFI/GPT, Secure-Boot-off boundary applies.
  Verify destination disk identity and back up data before installation. Launching
  the editor is not permission to erase storage.
  Keep session logs, the LATEST_CRASH_LOG.txt pointer, first traceback and first
  painter-warning stack when reporting a failure. Preserve recovery directories.
  This launcher/Help revision was not exercised in app/build/hardware tests.


WHAT GROOVEBOX IS (THE SHORT VERSION)
-------------------------------------
Groovebox uses numerical seeds and editable context to make music, video and
playable game worlds. Matching seeds and relevant inputs/settings are repeatable
on supported deterministic paths; live inputs and true-random modes are different.

You type a seed (any number). Groovebox's canonical engines read it and write
a whole composition: 48 instruments with their own synths, sequences, a
playlist (the song's arrangement), automation, effects, and a visualizer that
is drawn from the very same data. Everything you change by hand is kept as
yours; the engines fill in only what you have not touched.

You can use it three ways, and mix them freely:

  1. Generative — type a seed, press 🎲 Randomize Song, press ▶ PLAY.
  2. Hands-on — draw waveforms, program steps, paint the playlist, play keys.
  3. Mathematical — write seed scripts, domain equations and instrument
     scripts that drive any parameter over musical time.

You never need the math to make music with it.


QUICK START (2 MINUTES)
-----------------------
  1. Type any number in the SEED box (try 1.1975807343, 3.14159, 134964356).
  2. Press 🎲 Randomize Song.
  3. Press ▶ PLAY Audio Track.  Press ⏹ Stop to stop.
  4. Change the seed and play again — a new piece, always the same for that seed.
  5. Switch the engine buttons (SEEDED · RAND · LOCK · EUCLIDEAN · GOAVA ·
     FRACTAL SEED) on and off and listen to how the piece is written.
  6. Pick an instrument in the instrument selector and press EDIT SYNTH, or
     draw its wave in the WAVETABLE SYNTH · DRAW panel.
  7. Press ▶ PLAY Audiovisual Track to see the music.
  8. 💾 Save Project.  📻 Export Master WAV Audio, or export MP4 video.

If you hear nothing, see "NO SOUND?" near the end.


THE IDEA THAT RUNS EVERYTHING: CANONICAL vs YOUR DATA
-----------------------------------------------------
Every setting has two possible owners:

  • Canonical — a value still at its default belongs to the canonical
    engines, which write it from the seed and the active engines.
  • You — once you move a value off its default (or draw, paint or type
    something), it is yours and is never overwritten.

When both have a say, continuous values (levels, depths, positions) are a
50 % you / 50 % canonical blend, and choices (rule numbers, modes, lists) are
yours. Panels show this with tags:  C = canonical,  U = yours,
U50 = 50/50 blend.  Reset buttons hand a value back to the canonical engines.

Determinism: same seed + same settings + same engines = the same sound and
the same video, on any machine. With all canonical engines on (or all except
GOAVA) the result for a seed does not depend on how many instruments the
project has; only your own composition data can set instruments apart. In
the video, only the camera / viewing angle may differ between views.


THE MAIN WINDOW
---------------
Top bar
  SEED              the main input. Numbers, lists and seed scripts.
  ↩ Revert Seed     step back through seeds you tried.
  ↪ Undo / ↩ Redo   whole-project undo.
  Master Volume     final output gain (canonicals never touch it).
  BPM, Base Frequency (Hz), Global Track Offset (beats), Reverse Time.

Transport
  ▶ PLAY Audio Track        render, then stream audio.
  ▶ PLAY Audiovisual Track  audio + the visualizer.
  ▶ This Sequence           play only the selected instrument's sequence.
  🎮 PLAY VIDEO GAME        enter the game generated from the composition.
  ⏹ Stop.

Engines (the canonical writers)
  SEEDED      writes the composition directly from the seed.
  RAND        captures fresh entropy when switched on and stores it with the
              project, so playback and export reproduce it.
  LOCK        phase-locks voices (Coupling, Timing Pull, Pitch/Detune Link,
              Velocity Link, Phase Spread).
  EUCLIDEAN   Euclidean rhythm distribution.
  GOAVA       a single-instance irrational-number stream that composes its
              own pure-tone line; "GOAVA to ensemble" sets how much it shapes
              the others (default 0.1975807343).
  FRACTAL SEED  the musical explorer: seeds the composition fractally.
  Each engine has a contribution level in the CANONICAL MORPH BRIDGE.
  Full Unison: with SEEDED + RAND + LOCK + EUCLIDEAN on (GOAVA optional),
  every canonical voice resolves to one parameter set, so the instrument
  count no longer changes the result.

Instrument selector
  Picks the instrument (operator) that every instrument panel edits:
  EDIT SYNTH, WRITE SCRIPT, PATCH MODULAR, CALC DOMAIN, the four geometric
  synth panels, and samples. Rename instruments in the name box under
  PROJECT NOTES.


EACH INSTRUMENT'S SYNTH
-----------------------
Every instrument is one complete synth. Its voice is 50 % the EDIT SYNTH
main synth and 50 % its own instance of the four geometric synths, so both
halves are equally powerful:

  EDIT SYNTH panel — the instrument's own parameters (morph, harmonic
    frequency, chaos, fold depth, harmonic lattice, fractalizer, EQR, AM/FM/PM
    and Meum modulation, tuning, EQ) — the main synth, further shaped by the
    instrument's Mod, PATCH MODULAR, CALC DOMAIN and WRITE SCRIPT windows.

  The four geometric synths — one instance on EVERY instrument (they are not
  a shared global source; only GOAVA is single-instance). The panels in the
  main window edit the selected instrument's instance; their titles show its
  name.

    WAVETABLE SYNTH · DRAW   the instrument's waveform cycle.
      DRAW CYCLE: left-drag draws, right-drag erases back to the canonical
      cycle, double-click clears (canonical owns it again). A drawn cycle is
      played exactly (band-limited, no aliasing) and makes this instrument's
      wavetable yours. Without a drawing the canonical engines write a
      seeded point of waveform space for it — any pitched timbre is
      reachable. Phase / Curvature / Twist / Fold reshape the cycle (they are
      exact harmonic transforms; at their defaults the cycle is unchanged).
      1D / 2D / 3D only change the display.

    VECTOR SYNTH   X / Y / Z direction of the timbre: X shears harmonic
      phases, Y balances odd/even harmonics, Z tilts the spectrum.
      Vector pad: drag = X/Y, mouse wheel or Shift+drag = Z,
      double-click = centre (canonical). Drive scales its depth;
      VECTOR CONVERT turns it off for this instrument.

    BOUNCING BALL SYNTH   a physics trajectory (gravity, angle, radius,
      velocity, collisions with polarity reversal) that moves the voice's
      level and brightness. Click or drag in the box to place the ball; the
      gold ring is the canonical position, the dots are the actual path.
      Lock = all Ball values are yours even at default.
      RESET BALL ACTIVITY = defaults, canonical again.

    CELLULAR AUTOMATA SYNTH   an automaton (rule, size, states, generations,
      neighbourhood) whose density decides how many harmonics are sounding
      over time. Click cells to place your seed cells; gold cells are the
      canonical seed used while you have placed none. Lock / RESET as Ball.

  GEOMETRIC ENGINE MIXER — how strongly the Vector, Ball and Cellular lanes
    act on every instance, and how much of the instance is the wavetable cycle
    (the rest is a pure fundamental). With Vector/Ball/Cellular at 0 and
    Wavetable at 100 % the instance half plays a drawn cycle exactly as drawn.
    Instance × Main synth: the two halves modulate each other.
    Instance × Global mod: the instance follows the global modulation space
    (Meum AM, scaled by XMOD) and its Ball/Cellular activity moves its share.

  Samples — 🎞 Load Media / Load Sample → Selected Operator attaches audio or
    video to the instrument. With no canonical engine on, the recording plays
    exactly as recorded (native rate, no stretching), layered with the synth.
    With engines on, 50 % of it stays the untouched recording and 50 % is
    warped by the instrument's synth, script, patch and domain. ↩ Reverse
    Clip, Reverse From Here and Ping-Pong edit the clip.


SEQUENCES, STEPS AND EDIT SYNTH PER SEQ
---------------------------------------
Each instrument has numbered sequences (step patterns with gates, pitches,
amplitudes, probabilities and offsets). ＋ Add sequence / − Remove sequence.

Edit Synth Per Seq
  OFF: the editors write the instrument's master panel.
  ON:  the editors (Synth, Script, Patch, Domain AND the four geometric
       synths) write the selected sequence's own panel. The button, the panel
       buttons, the geometric panels and every open editor window take that
       sequence's colour and show "SEQ #n"; connector lines show what it
       drives. At playback a sequence panel blends 50 / 50 with the master
       panel — geometric synths included — unless Automation Morph moves it.


THE PLAYLIST (ARRANGEMENT)
--------------------------
The Playlist window is the song: rows in time, each naming which
instruments/sequences play, with columns for timing, velocity, script /
domain / synth / patch tags, automation, direction, coverage and more.
Paint cells with the brush; Snap to Grid is optional.

  Blend Partner + Blend %   choose another sequence to morph toward for
    that row ("Instrument#S3", sequence 1 if no number) and how far
    (0–100 %), exactly like an Automation Morph. A partner with no Blend %
    does nothing.
  🧹 Clear Playlist   clears every written row and its automation (Undo
    restores it). If canonical engines are active they write a fresh
    playlist straight away.

Mouse wheel, sliders and pads
  The mouse wheel always scrolls the page — it never changes a slider, knob,
  number box, drop-down, the Vector Synth XY pad or the focus-zone editor, even
  when the pointer happens to be over one while you scroll.
  Hold Ctrl and use the wheel to adjust the control under the pointer
  (Ctrl+wheel on the Vector Synth pad moves Z; Shift+drag also moves Z).
  ⇢ Flow (Ctrl+Shift+L) shows or hides the numbered workflow arrows.
  📝 Notes opens the notes & diary editor (also a tab in Performance): New,
  Diary (dated entry), Rename, Delete (to notes/.trash, restorable), search,
  autosave, Ctrl+S. Notes are plain .md/.txt files in <data>/notes.

Audio playback & troubleshooting
  Audio files (WAV, FLAC, MP3, OGG, Opus, M4A, AIFF, .MCC …) play in stereo at
  their own level — the synth Master Volume and its drive do not apply to them.
  If playback crackles on a busy laptop, start Groovebox with
  GROOVEBOX_AUDIO_LATENCY=high (or a value in seconds such as 0.08) and/or
  GROOVEBOX_AUDIO_BLOCKSIZE=2048.
  If an action fails, the full details are written to logs/errors.log in the
  Groovebox data folder — include that file when reporting a problem.


AUTOMATION
----------
The automation editor (step-sequencer style) places control points:
  Operator / Sequence      what the point acts on.
  Morph                    0–100 %: morphs from one instrument/sequence panel
                           to another — synth params and the geometric-synth
                           instance alike. Canonical engines also write and
                           predict Morph points.
  Sequence Attack / Release, Offset, Synth Param + Value.
Patch-route destinations include Vector X/Y/Z, Wavetable Phase/Fold, EQ
bands, Filter, Resonance, Pitch, Amplitude, Mod Depth and Sidechain.


GLOBAL MIX, MODULATION AND EFFECTS
----------------------------------
  CANONICAL MIXER (bottom right)
    XMOD — the master modulation amount: how much of the Meum AM / FM / PM
    modulation the canonical engines use (a canonical per-row curve shapes it;
    the Mod Depth patch route adds to it).
    Track Energy and Converge/Diverge knobs — yours only (not canonical),
    like the Sharp/Smooth mix knob; at the middle they change nothing.
  MASTER GLOBAL EQ — draw the curve; canonical while flat, 50/50 once drawn.
  SIDECHAIN — global and per-step ("↯ CANONICAL GLOBAL / LOCAL SIDECHAIN").
  Match loudness — renders land at a matched loudness (−14 LUFS, peak-safe; no limiter).
  LIVE DJ PANEL, ∞M HyperDrive, PATCH MOTION · PERFORMANCE MATRIX — live macros.


VIDEO AND THE VIDEO PLANNER
---------------------------
The visualizer is one renderer, drawn as a fractal of ways to see music,
most direct first:
  front  — the sound itself: waveform, spectrum, rhythm (full strength);
  then   — instrument structure: the canonical constellation, the shared
           instrument object, particles, GOAVA's stream;
  then   — harmonic geometry: roses, orbitals, lattices, filaments;
  back   — seed / fractal residue: terrain, seed morph, numeric fractal.
Each deeper layer recedes by the same irrational ratio (1/M ≈ 0.835 per
layer). Everything is a function of the composition; only the camera moves.

🎬 VIDEO PLANNER — duration, resolution, FPS, parts, overlay, integrity
check, and colour convolution: Channel order (RGB, RBG, GRB, GBR, BRG, BGR)
swaps the output colour channels and Channel mix blends original ↔ swapped.


PERFORMANCE, MEDIA AND DRAWING
------------------------------
  Performance window — media player / browser for audio, video, projects;
    device routing (Refresh Devices).
  ✎🎙🎥 Draw / Record / Video — record audio/video, draw media layers, and
    the 3D Voxel Kit (draw voxels on Z slices, voxelize frames, import OBJ /
    PLY / STL / glTF / GLB, export OBJ / PLY).
  🎹 Keyboard / Test — play instruments live.


SCRIPTS, DOMAINS AND PATCHING (ADVANCED)
----------------------------------------
  Seed scripts — the SEED box accepts expressions over musical time t.
  ∫ CALC DOMAIN — time / space domain equations per instrument.
  📝 WRITE SCRIPT — instrument scripts: evaluate_wave(x, y, z), or the
    full_graph_v1 context (t_norm, graph_*, domain / sequence / step data,
    named audio / video / game outputs).
  PATCH MODULAR — wires between operators and global buses.
  ∿ MATHEMATICAL COMPOSITION LAB — the math explorers.


SAVING, LOADING AND EXPORT
--------------------------
  💾 Save Project / 📂 Load Project — the whole project: seed, engines,
    instruments and their geometric instances (drawn waves, ball positions,
    cells, locks), sequences and per-sequence panels, playlist, automation,
    effects, ownership marks, media references and video plan.
  ⬆ Export .MG / ⬇ Load .MG — compressed project/program format.
  📻 Export Master WAV Audio, MP3, MP4 video (+ multipart), stems.
  Exports start from a clean phase so they reproduce exactly.
  🗑 Clear Memory · Ideal Defaults — back to a fresh canonical baseline.


GAMES
-----
🎮 PLAY VIDEO GAME builds a deterministic world from the composition (its
geometry and physics follow the same canonical state as the sound and
video). Games can be exported with the project.


sOS (THE GROOVEBOX ISO)
-----------------------
Booting the Groovebox ISO starts sOS straight into Groovebox (Wayland /
Labwc). The bar at the top lists and switches Groovebox windows. Quitting
Groovebox powers the machine off. The live system runs from RAM; Install
copies it to a disk. Safe and Recovery boot entries exist for difficult
hardware.


NO SOUND?
---------
  1. Master Volume above zero?
  2. 🎲 Randomize Song, then ▶ PLAY Audio Track.
  3. Is the right output device selected (Performance → Refresh Devices)?
  4. Another app holding the device exclusively? Close it.
  5. Changed audio hardware? Restart Groovebox.
  6. Running from source? Check the audio dependencies are installed.
When reporting a problem include: operating system, Groovebox build, what you
clicked, what you expected, what happened, and any console text.


GLOSSARY
--------
  Seed        the number (or script) everything is derived from.
  Canonical   written by the engines from the seed; used while you haven't
              set the value yourself.
  Operator    one of the 48 instrument slots.
  Sequence    one numbered step pattern of an instrument.
  Instance    an instrument's own copy of the four geometric synths.
  Wavespace   the space of all waveform cycles; every instrument sits at a
              point in it (drawn by you, or written by the canonical engines).
  Morph       automation that moves an instrument from one panel/sequence
              setting to another.
  Meum (M)    the project's constant, the root of 2^M = M^4 + M^2 − M,
              M ≈ 1.1975807343. Its exact relatives (M−1, 1/M, 2−M, (M−1)/M)
              set many default ranges and ratios.

Philosophy: make something interesting from a number, hear it immediately,
and be able to reproduce it later.

CREDITS / AI ASSISTANCE
-----------------------
  Main editor and author: Noah Girouard King (Eski)
  Development and research assistance credited by the project:
  Grok (xAI), Gemini (Google), Claude (Anthropic), ChatGPT (OpenAI),
  Mistral.ai (Mistral), Meta AI (Meta), GitHub Copilot (GitHub),
  Cursor Grok 4.6, jcode(1jehuang), opencode (anomalyco), and
  Perplexity (Perplexity AI).
  Credits describe project contributions and tooling/assistance; they do not
  imply endorsement, ownership, authorship, or scientific validation by
  those services.

PLAYERS, WINDOWS & TOOLS (2026-11-03)
  * .MCC videos play directly in a lossless in-app player (no conversion);
    audio files show a waveform / scope / spectrum visualizer.
  * No window is modal: prompts and file pickers never block other windows.
  * The window bar lists every open window; ✕ closes, wheel scrolls.
  * Quit Groovebox → "Back to startup chooser" restarts the session view.
  * Under EXPORT: Batch Export, Player, File Manager, Exports Folder,
    Save/Load, Recover Autosave, Reconvert, Recordings, Game, Notes, Audio check.
  * Boost Beats (LIVE DJ): Mod, PROB and PKP Env (pluck → solid → swell).
  * Canonical sequences sculpt every lane (phase, probability, envelope,
    automation) from one smooth seed contour; your own edits always win.

COMPOSING, BENDING AND OWNERSHIP (2026-11-03)
  * Heuristic COMPOSES start values (steps, automation, sequence synths,
    geometrics). Lock Heuristic Without Replicating Ensemble = every
    instrument gets its own unique segment (Series); Modes... per instrument.
  * Algorithm never writes - it BENDS. Global Play Patcher bays: GLOBAL,
    LOCAL (one per synth) and GROUP (a named set of playlist rows). Active
    algorithms average per value; each playlist row is bent as a group
    (same-seconds step offset for every synth, +/-1 semitone, +/-10 % level).
  * Canonicals only READ your algorithm/heuristic settings and add their
    own parallel layer; highlighted lines under each panel explain it.
  * Per step: band EQ (dB / Hz / Q), signed Sidechain (- = key: louder,
    and neighbours sharing its spectrum/level duck), FX Prob (rare accents).
  * Contour: dull <-> linear <-> sharp, Per lane..., Contour Sequence.
  * Playlist -> Compose: retrograde, mirror, thin, densify, A-B-A,
    transpose (1 semitone of the 432 Hz unit), row write mode
    (step / automation / both / identity), algorithm groups, heuristic
    compose-section (run again to revert).
  * Under EXPORT: Store A / Store B / A<->B compare while playing.
  * Video export renders frames on a worker; the window stays usable.


MEMORY, SSD SWAP AND PROJECT TABS (2026-11-03)
  • Several projects can be open as tabs (bar at the top of the main window). How many fit is
    computed from your RAM, the sCode pool and the measured size of a project (status line).
  • Only the active tab uses RAM: switching parks the other project — its playback stops, a
    safety autosave is written, and its big buffers move to Groovebox's SSD swap.
  • When RAM runs low the same happens to the coldest buffers of the project you are in (the
    rendered track moves to the SSD and still plays). A prompt tells you, after the autosave.
  • Outputs you plug in are picked up automatically; Hardware & Master → Devices sets formats.

DIMENSIONALITY — THE MULTIDIMENSIONAL SYNTH AND ITS WORLD (2026-11-03)
  Every voice is a triad of three synth groups:
      inner = panel synth  mixed with  its four geometric synths (your balance)
      voice = inner        mixed with  the MULTIDIMENSIONAL synth (33–66 %, default 50 %)
  The multidimensional synth is ONE synth with four dimensions at once:
    • WAVETABLE  — 12 partials whose amplitudes come from its script ("1/k" …)
    • CELLULAR   — an automaton with one cell per partial; each generation decides
                   which partials sound
    • BALL       — a bouncing ball whose height moves pitch and level
    • VECTOR     — a rotating 3-D direction that turns the phase
  It listens to itself: when its own amplitude is loud it climbs in pitch and turns
  its phase forward; when quiet it sinks and turns back (amplitude → frequency →
  phase). A domain equation chooses, block by block, between the automaton-gated
  structure and the full table; a harmonic-geometric rule designates FIXED
  resonators (harmonic / platonic / fibonacci / triangular / square / golden) tied
  to the project base frequency, so they ring the same whatever note plays.
  Main synth ↔ multidimensional synth modulate each other (pathways in the patch).
  The canonicals work mainly through this synth: each active engine programs a
  part of it, and your settings mix with theirs by the "🌀 MULTIDIM canonical ↔
  user" slider in the Global Canonical Mixer (33–66 %, default 50 %), like the
  sequencer. Its defaults are convolved like the other two groups (instrument
  count × Global Convolve). 🌀 Open… shows its live 3-D view.
  The SAME world appears in every video frame (a 3-D layer) and in games (a layer
  plus objects: platforms, a bouncer, wind, pillars, portals, a pulse) — computed
  from the audio's own clock, so picture, game and sound never drift apart.

================================================================================
TECHNICAL REFERENCE (restored 2026-11-03)
================================================================================
The sections below restore the technical guide: complete seed scripting,
every workspace variable a script can read, the mathematics behind the
project (Meum Calculus, Operator Theory, the book series), the canonical
number-theory contract, the unison master transform and the author's books.

--------------------------------------------------------------------------------
SEED SCRIPTING — COMPLETE GUIDE
--------------------------------------------------------------------------------
Where scripts run
  • SEED box (main window) — the project seed. Evaluated once at t = 0 for the
    composition (RNG, playlist paint, fingerprint) and along the time axis
    during Play / Export (t in seconds; t_norm = position 0…1 in the cycle).
  • Domain equations (∫), instrument scripts (📝), GLOBAL PLAY PATCHER and
    the LIVE DJ RAND PARAM all use the same evaluator and vocabulary.
  • 🎲 Random Seed Script rotates through every syntax family below and
    weaves 3–5 workspace variables into each script, so repeated presses
    cover the whole language. Only scripts that evaluate cleanly for all
    instruments and several times are inserted.

The 24 syntax families (all accepted)
  number          432 * (1 + 0.2 * tanh(graph_energy))
  list            220, 330, 440 + 12 * vector_x, 110 * (1 + 0.1 * sin(t))
                  (instrument i gets item i mod n)
  if / elif       if(vector_x > 0.5) 432 elif(isn(t) > 0) 216 elif 108
  ternary         (432 if ball_vx >= ball_vy else 216) * (1 + 0.1 * tanh(phase))
  assign/return   base = 300 * (1 + 0.2 * tanh(energy))
                  wob = 12 * sin(t * 2 + cell_rule)
                  return base + wob
  comment         # lines starting with # are ignored
  parametric xyz  x(t) = 200 * sin(t)  /  y(t) = 150 * cos(t)  /  z(t) = …
  polar r/θ       r(t) = 300 * (1 + 0.1 * sin(t))  /  theta(t) = MEUM * t
  polar()         polar(300, MEUM * t)
  cartesian()     cartesian(x_expr, y_expr, z_expr)
  spherical()     spherical(r, theta, phi)
  cylindrical()   cylindrical(r, theta, z)
  P / E / D       P(isn(t), ics(t)) * 200 + E(sin(t), MEUM) * 100 + D(t, PHI) * 4
  tensor          tensor_z(sin(t), MEUM) * 200 + tensor_rel(cos(t), graph_x) * 50
  choose          choose(100, 200, 300, 400, floor(abs(t * 2)))
  clamp / lerp    clamp(lerp(110, 880, 0.5 + 0.5 * isn(t)), 55, 1760)
  isn family      300 * isx(t) + 200 * isy(t * 2) + 20 * arcisn(clamp(x, -1, 1))
  graph.attr      300 * (1 + 0.2 * tanh(graph.x + graph.energy * graph.phase))
  graph_vector    300 * (1 + 0.2 * tanh(graph_vector[0] - graph_vector[1]))
  logic           and / or / not, comparisons, % and // on numbers
  generator sum   sum(sin(t * k) / k for k in range(1, 6)) * 100
  min / max math  max(110, min(880, 440 * (1 + vector_y)))
  OT math         ot_add / ot_sub / ot_prod / ot_div / ot_pow and ot_equiv_*
  walrus          (k := 1 + 0.25 * cell_rule / 255) * 300

Functions
  D, E, P, abs, acos, arcics, arcisn, asin, atan, atan2,
  author_symbol_decode, author_symbol_fraction, author_symbol_spell,
  cartesian, ceil, choose, clamp, cos, cosh, cylindrical, degrees, exp,
  fabs, floor, hypot, ics, ics_inv, ics_inverse, isn, isn_inv, isn_inverse,
  isx, isy, lerp, log, log10, log2, math_acos, math_add, math_asin,
  math_atan, math_atan2, math_cos, math_cosh, math_div, math_exp, math_log,
  math_log10, math_log2, math_mul, math_pow, math_scale, math_sin,
  math_sinh, math_sqrt, math_sub, math_tan, math_tanh, max, min, no_sat,
  op_theory_enabled, ot_add, ot_band, ot_book_ics, ot_book_ics_inv,
  ot_book_isn, ot_book_isn_inv, ot_div, ot_equiv_acos, ot_equiv_add,
  ot_equiv_asin, ot_equiv_atan, ot_equiv_atan2, ot_equiv_ceil, ot_equiv_cos,
  ot_equiv_cosh, ot_equiv_div, ot_equiv_exp, ot_equiv_fabs, ot_equiv_floor,
  ot_equiv_hypot, ot_equiv_i_pow, ot_equiv_log, ot_equiv_log10,
  ot_equiv_log2, ot_equiv_mul, ot_equiv_pow, ot_equiv_root, ot_equiv_sin,
  ot_equiv_sinh, ot_equiv_sqrt, ot_equiv_sub, ot_equiv_tan, ot_equiv_tanh,
  ot_i_phase, ot_master_transform, ot_pow, ot_prod, ot_sub, parametric,
  polar, pow, radians, round, sin, sinh, spherical, sqrt, tan, tanh,
  tensor_rel, tensor_z

Constants
  MEUM, MEUM_INV, MEUM_LOG2, MEUM_NORM, MEUM_SQ, PHI, SILVER, SQRT2, SQRT3, e, pi, tau
  (MEUM is the project constant M; MEUM_NORM = (M−1)/M; MEUM_INV = 1/M.)

Workspace variables — every live value a script can read (88 names)
  angle
  ball_gravity, ball_gravity_angle, ball_polarity, ball_radius, ball_vx, ball_vy
      → Ball synth: radius, velocity vx/vy, gravity and its angle, polarity
  bpm
  canonical_count, canonical_euclidean, canonical_goava, canonical_mask, canonical_phase_lock, canonical_randomizer, canonical_roster_size, canonical_seeded, canonical_unison
      → which canonical engines are on (0/1 flags), their count, mask, roster size, unison
  carrier_peak, carrier_present, carrier_rms
      → loaded global carrier: present (0/1), RMS, peak
  cell_canonical_share, cell_generations, cell_height, cell_rule, cell_types, cell_width
      → Cellular synth: rule number, cell types, grid width/height, generations, canonical share
  count
  curvature
  domain_id, domain_value, domain_weight
      → domain equation id, value, weight
  energy
  eq_high_hz, eq_low_hz, eq_poles
      → master EQ band edges (Hz) and pole count
  goava_canonical_amplitude
  graph_angle, graph_count, graph_curvature, graph_energy, graph_id, graph_index, graph_phase, graph_radius, graph_scalar, graph_slot, graph_u, graph_v, graph_w, graph_x, graph_y, graph_z
      → the live graph point the script is evaluated on (position x/y/z, u/v/w, radius, angle, phase, energy, curvature, scalar, slot/index/count/id)
  index
  mix_euclidean, mix_goava, mix_lock, mix_rand, mix_seeded
      → engine mix levels (seeded, rand, lock, euclidean, goava)
  phase
  radius
  sample_rate
  scalar
  seed, seed_w
      → the evaluated seed and its weight
  sequence, sequence_index
      → sequence number / index of the voice being evaluated
  sidechain_attack_ms, sidechain_depth, sidechain_release_ms
      → sidechain depth, attack and release (ms)
  slot
  step, step_index
      → step number / index inside the sequence
  t_norm
  u
  v
  vector_drive, vector_x, vector_y, vector_z
      → Vector synth: XY(Z) position and drive
  w
  wavetable_canonical_share, wavetable_curvature, wavetable_fold, wavetable_phase, wavetable_twist
      → Wavetable synth: phase, twist, fold, curvature, canonical share
  x
  y
  z

  Workspace binding (default): while a script is evaluated, these names
  take their values from the live workspace (the panels as they are right
  now), so the script follows your edits.
  "Disable workspace override of seed variables" (checkbox at the bottom of
  the Seed panel): the seed uses only its own defaults (x = t, bpm 120,
  sequence 1, …) — a self-contained seed that sounds the same whatever the
  workspace holds. Saved with the project; re-renders on change.

Graph script variables (32 names, instrument / domain scripts)
  t, t_norm, x, y, z, seed, seed_w, graph, graph_x, graph_y, graph_z,
  graph_scalar, graph_radius, graph_angle, graph_energy, graph_curvature,
  graph_phase, graph_u, graph_v, graph_w, graph_index, graph_count,
  graph_slot, sequence_index, step_index, domain_value, domain_weight,
  graph_id, domain_id, bpm, sample_rate, graph_vector

Rules worth knowing
  • Empty, 0 and 0.0 mean "no seed"; non-numeric text that cannot be
    evaluated is hashed into a stable seed token.
  • Same script + same project = same result on every machine.
  • Scripts are evaluated outside the realtime audio callback; the result
    is cached per render, so heavy scripts slow renders, not playback.

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

The canonical forward book-series definitions are:
    isn(γ) = γ²/2! − γ⁴/4! + γ⁶/6! − ...
    isx(γ) = 1 − isn(γ)
    isy(γ) = 1 − isn(γ − π/2)
    cos(γ) = isx(γ)
    sin(γ) = isy(γ)
    tan(γ) = isy(γ) / isx(γ)

The inverse-isosceles compatibility coordinate remains separate and uses its
own Maclaurin/binomial inverse series. It is not used to implement forward
sin/cos/tan when the Trigonometry Engine is ON.

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
    Perplexity (Perplexity AI)

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

--------------------------------------------------------------------------------
35. DIMENSIONALITY, AND HOW THE AUTHOR'S THEOREMS SIMPLIFY AND OPTIMIZE (2026-11-03)
--------------------------------------------------------------------------------
Labels follow section 33: ESTABLISHED = ordinary mathematics with ordinary proofs;
PROJECT = Meum Calculus / Operator Theory / Finite-Infinity as defined by this
project (CLAIMED EXACT where a test contract checks it). Each item names the code
that uses it.

35.1 The dimensional model
  A voice lives in three nested spaces:
    panel synth (1 oscillator with Meum AM/FM/PM)            — the main axis
    four geometric synths (vector · wavetable · ball · cellular) — 4 axes
    multidimensional synth (the same four, fused, self-conditioned) — the 3rd group
  The multidimensional synth's state per control block b is
      S_b = ( CA row c_b ∈ {0,1}^12 , ball height h_b , vector v_b ∈ R³ ,
              block amplitude a_b , domain weight D_b )
  and its output is the projection
      y(t) = Σ_k A_k(b) · sin(k·θ(t) + ψ_k) / Σ_k |A_k(b)|
      A_k(b) = D_b · table_k · gate(c_b,k) + (1 − D_b) · table_k
  The video layer and the game entities read S_b at the same b the audio used.

35.2 Trigonometric identity — the partial sum (ESTABLISHED)
      Σ_k a_k sin(kθ + ψ_k) = Im Σ_k a_k e^{iψ_k} (e^{iθ})^k
  One complex exponential per sample and its powers replace 12 separate sines
  (multidim_synth.voice). Exact identity; float results equal to rounding.

35.3 Finite-Infinity — exact jumps over "infinite-looking" traversals (PROJECT,
     built on ESTABLISHED cycle detection; finite_infinity.py)
  Rule: a shortcut is taken only when a finite certificate proves it exact —
  never because something "looks periodic".
    • Cellular orbit: 12 cells have at most 4 096 states, so every orbit is a
      pre-period μ plus a cycle of period P (pigeonhole). Found once, then
          row(b) = orbit[b]                 b < μ + P
          row(b) = orbit[μ + (b − μ) mod P] otherwise          — O(1) at any time
      (multidim_synth._ca_orbit; identical to stepping it — checked.)
    • Ball cycle: after its first relaunch the ball restarts from the identical
      state (h = 0, v = √(2g)) — a repeated deterministic state, so the motion is
      exactly periodic; certified when the relaunch recurs, then copied
      (multidim_synth._ball / ball_at — bit-identical, checked).
    • Playlist-pattern memo: a voice's multidimensional output is a function of
      its phase INCREMENTS (taken from their sources, so the row-to-row phase
      carry does not change them), its programme, seed, slot, rate and base.
      Equal inputs ⇒ equal output, so a repeated row reuses it bit-identically
      (cycle_jump's "repeated deterministic state", applied across the playlist).
    • affine_jump / modular_jump / transition_jump remain available for exact
      O(log n) jumps of affine maps, modular steps and finite transition graphs.
  What is NOT shortcut: the per-sample sine sum across cycles. Reusing samples
  would need the phase to advance by a whole number of turns per cycle, which a
  float phase almost never does exactly — so it is computed, not assumed.

35.4 Sync from one clock (ESTABLISHED arithmetic)
  Audio, video and games compute S_b from the same integers: row-relative sample
  index s, block b = ⌊s / blk⌋ with blk = round(block_ms · sr) samples, ball step
  dt = blk / sr, video time = frame / export fps, live time = transport cursor.
  No separate simulation runs, so nothing can accumulate drift (0 mismatches in
  3 000 random samples over 40 rows — the release check).

35.5 Operator Theory division — zero as a defined case (PROJECT)
  While OT is ON every script ( / // % ) uses OT division (ot_script_math):
      b ≠ 0  : the exact quotient (identical to ordinary division)
      0 / 0  : 1          a / 0 : ±∞          a // 0 : as a / 0          a % 0 : a
  The OT equivalence kernel guarantees enabling OT never retunes a project: every
  non-zero division is unchanged. Elsewhere in the engine there are no epsilon
  guards: divisions are exact with an explicit result at exactly zero.

35.6 Meum (PROJECT constant)
  M ≈ 1.1975807343, the root of 2^M = M⁴ + M² − M. Its exact relatives (M − 1,
  1/M, (M − 1)/M, 2 − M) set default ranges and ratios across the engines, so
  those ranges are derived rather than tuned by hand.

35.7 Memory: sCode pooling (ESTABLISHED engineering)
  Size-class slabs (power-of-two capacity per kind / thread / dtype): rows that
  differ by a few samples and every instrument in a row reuse one buffer; the
  multidimensional synth's scratch comes from the same pool. Values are identical
  to fresh allocation; memory stays flat instead of churning.

35.8 Where the savings come from (measured on the build machine)
  multidimensional synth  ≈ 20–30 ms per voice per 2 s row (block grid + pool; see 35.9),
  a repeated row          ≈ 2 ms (memo), CA / ball lookups O(1) at any time,
  tempo / length edits    one canonical rebuild per burst, not per click.

35.9 Six benchmarks — old foundations vs the new ones (benchmark_multidim_fi.py)
  Each pair is checked for equal results before it is timed (exit code 1 if any
  pair disagrees). Measured on the build machine, 48 kHz, best of 3:
                                               old        new     speed-up  max |old−new|
    1 partial sum (trig identity)            16.97 ms    5.91 ms     2.9×     1.8e-12
    2 synth body (block grid + pool)         22.28 ms    7.74 ms     2.9×     5.4e-13
    3 CA, 10-minute timeline (FI orbit)     892.73 ms    0.95 ms   ~940×      0 (identical)
    4 ball at time t, 20 queries (FI cycle)  41.08 ms    0.01 ms  ~4500×      0 (identical)
    5 repeated playlist row (FI memo)        19.25 ms    1.63 ms    11.8×     0 (identical)
    6 world at video frame t = 10 min       211.68 ms    0.08 ms  ~2800×      0 (identical)
  1–2 differ only by float rounding (≈1e-12, far below 24-bit audio resolution);
  3–6 are bit-identical. Run `python benchmark_multidim_fi.py` to reproduce on
  your own machine — numbers vary with the CPU, the ratios stay similar.

(Older per-release notes are kept in docs/HELP_HISTORY.md.)

--------------------------------------------------------------------------------
36. CANON LEAD — PRIMARY WAVE CARRIER MODE  (R23R · 2026-11-03)
--------------------------------------------------------------------------------
36.1 Purpose
  When a Canon Lead is set, one instrument becomes the primary wave carrier for
  the entire composition.  The canonical engine shifts its reconciliation from
  an equal-anarchy ensemble into a lead-dominant mix:

      Lead synth    →  carrier mix = min(1.0, base_mix × 2.5)   (dominant carrier)
      Ensemble      →  carrier mix = base_mix × 0.60             (subordinate voices)
      No lead set   →  carrier mix = base_mix (all instruments equal; "anarchy mode")

  The composition fingerprint (sig) remains seed-deterministic regardless of
  lead status.  The lead affects only how much each synth's wavetable voice
  weights into the canonical carrier mix at reconciliation time.  A project
  saved with a given lead and loaded back produces identical output.

36.2 How to use it
  1. Select an instrument in the instrument selector.
  2. Press 🎯 Lead (the button next to the selector) to designate it as Canon Lead.
  3. All instrument dropdowns immediately show that synth's name in orange text
     with a yellow border and a [lead] tag at the right edge.
  4. Press 🎯 Lead again (while that instrument is selected) to clear the lead
     and return to ensemble anarchy mode.

36.3 Visual markers
  The LeadItemDelegate decorates every instrument combo in the UI:
    • Background   : dark amber (#321800 at 86 % opacity)
    • Name text    : orange  (#FF8C00, bold)
    • Border       : gold    (#FFD700, 2 px)
    • Tag          : "[lead]" in lime (#C8E600) at the right edge

36.4 Persistence
  The Canon Lead name is stored in compat_settings (JSON sidecar) so it
  survives project reload.  The in-memory mirror is host._canon_lead_instrument.
  canon_lead.set_lead() / clear_lead() keep both in sync and immediately call
  SCodeOptimizerBridge.invalidate_work("canonical") to force a canonical re-derive.

36.5 Interaction with Randomize All
  Randomize All (🎲 Randomize Song) always ensures the lead synth's param slot
  exists before the randomize loop runs, so the lead is always hit by the
  randomizer.  It is the only randomizer that may also activate PKP Boost DJ
  (25 % probability when a full randomize is requested).

36.6 Ensemble lead default
  On first launch (or any session where no lead is stored), the first instrument
  in the 48-instrument list is automatically set as Canon Lead.  To revert to
  full ensemble anarchy, press 🎯 Lead while that instrument is selected to
  clear it.

--------------------------------------------------------------------------------
37. SYNTHS MASTER ENGINE — 3D PANEL AND STATUS MONITOR  (R23R · 2026-11-03)
--------------------------------------------------------------------------------
37.1 Geodesic sphere mesh
  The 3D sphere in the Synths Master Engine panel is a UV-parameterized geodesic
  mesh: 24 meridians × 12 latitude rings = 288 body vertices plus 2 poles.
  Every frame each vertex is displaced outward by:

      r(u,v,t) = R + 0.08·wt(k) + 0.14·ca(k) + 0.18·ball_h + 0.10·|vec|

  where wt(k) is the k-th wavetable partial amplitude, ca(k) is the k-th bit
  of the canonical CA row, ball_h is the multidimensional synth's ball height,
  and vec is the 3D direction vector magnitude.

  Rendering: Painter-sorted back-to-front by projected z; edges are thin lines,
  poles are filled with solid triangles.

37.2 Mouse velocity inertia
  Click-drag rotates the sphere in azimuth (horizontal drag) and elevation
  (vertical drag).  On mouse release the last 8 (time, dx, dy) samples are
  averaged to compute a release velocity.  The sphere then coasts at that
  velocity with exponential decay (factor 0.92 × per 20 ms tick, stopping
  below 0.001 rad/frame).  Scroll wheel pans the yaw axis (δ = Δscroll/120 × 0.08).

37.3 Proximity scaling
  Vertices within 100 px of the widget centre are scaled 1.333× outward
  (foreground pops); vertices beyond 300 px are scaled 0.75× (background recedes).
  Between those radii the scale interpolates linearly.

37.4 Arc sliders
  The five instrument macro sliders are arranged in a parabolic arch above the
  sphere: the central slider (index 2) sits highest; the outer sliders are
  offset downward by  Δy = |t| × 36 px  where  t = (idx − 2) / 2.0.

37.5 Bezier wires
  Each slider connects to the sphere centre via a cubic Bézier whose control
  points bend toward the nearest corner of the widget, giving the panel its
  "wired engine" look.

37.6 Ghost label animation
  The "SYNTHS MASTER ENGINE" label cycles through three states per tick:
  full orange glow, mid amber, dim.  It is drawn with a QRadialGradient so it
  appears to breathe without any dedicated QPropertyAnimation.

37.7 SynthsMasterPanel — tabs
  Open by clicking the ⚡ button in the bottom-right of the 3D panel.
  Each tab updates at 200 ms intervals while open:

  Pool Hits       Bar/line chart of sCode pool hit % (blue) and miss % (red)
                  per 100 submissions.  Higher hit rate = faster canonical
                  inference because the pool returned a cached result.

  Wavetable       Bar chart of the 12 partial amplitudes of the currently
  Spectra         selected instrument's wavetable.  Log scale checkbox shows
                  dB headroom; linear mode shows raw normalized amplitude.
                  Useful for understanding how harmonically complex the active
                  synth voice is.

  CA Evolution    Cellular automaton space-time diagram: 48-cell row evolved
                  forward 64 generations using the selected Wolfram rule.
                  The rule spinner (0–255) lets you explore how different CA
                  rules produce different rhythmic and timbral patterns in the
                  multidimensional synth.

  Finite-Infinity Line chart of three interleaved series sampled from the
                  FI pool at a chosen seed.  Each series is  n mod 134 964 356;
                  the three offsets reveal the orbit structure.  Lower seed
                  values explore the near-origin region; higher seeds explore
                  the asymptotic region where cycles lengthen.

  HW Clock        Real-time hardware-clock drift monitor: displays  ppm
  (ppm)           deviation between the hardware audio clock and the CPU wall
                  clock.  Values near zero mean the two clocks are tracking;
                  values ±10–50 ppm are normal for consumer hardware.  High
                  sustained drift (>100 ppm) may cause clicks if the ring
                  buffer is not large enough.  The _ClockAlignedRingBuffer
                  absorbs short-term drift; this chart shows the long-term
                  trend.

  Settings        Live knobs for the canonical engine:
    Canon influence          whether the lead designation modifies the
                             canonical carrier mix (disable for anarchy-only
                             mode even when a lead is defined)
    Lead carrier mix %       base_mix slider (0–100 → 0.0–1.0); the
                             2.5× lead boost and 0.6× ensemble reduction
                             are applied on top of this value
    FI-GREP                  enable/disable the finite-infinity GREP in pool
                             collision decisions (on = faster pool, with
                             deterministic collision resolution)
    sCode work threads       thread-pool size for the sCode optimizer
                             (1–64; default = min(32, CPU count))
    Apply button             pushes all settings into the live optimizer and
                             invalidates the canonical plan immediately

--------------------------------------------------------------------------------
38. FINITE-INFINITY AND FI-GREP  (R23R · 2026-11-03)
--------------------------------------------------------------------------------
38.1 Finite-Infinity constant
  FINITE_INFINITY = 134 964 356  (a project-defined constant, see section 35.3)
  Every pool key is reduced modulo FINITE_INFINITY before lookup, so the pool
  never grows beyond that many distinct entries regardless of how many
  computations the system performs.  This bounds memory and cache pressure
  without any explicit cache eviction policy.

38.2 FI-GREP (scalar, Level 1)
  When two sCode pool keys k₁, k₂ satisfy  k₁ mod FI = k₂ mod FI  they are
  treated as the same canonical computation (a pool hit by finite-infinity
  collision).  SCodeOptimizerBridge._fi_grep_match(candidate_key, known_keys)
  tests this:

      for k in known_keys:
          if candidate_key % FI == k % FI:
              return k    # hit — reuse the existing result

  This turns many apparent cache misses into hits and dramatically reduces
  redundant synthesis for instruments with similar scripts.  FI-GREP is ON
  by default and can be toggled in the SynthsMasterPanel Settings tab.

38.3 Nested 3D vectorized GREP (Levels 2 and 3)  (R23R · 2026-11-03)
  When a scalar FI miss occurs, the system falls into a deeper nested search
  using the multidimensional synth's state space as 3D coordinates.

  Each pool key is registered with a 3D state vector:
      v = (ca_hash mod FI / FI,   ball_height_norm,   |vec_direction|_norm)
      v ∈ [0, 1]³

  Level 2 — vectorized Euclidean proximity (numpy, O(n) across all pool entries):
      ‖v_candidate − v_known‖₂  <  tol_L2  (default 0.05)
      If any known entry is within this radius in 3D state space, it is reused.
      Two computations with similar CA row, ball height, and vector magnitude
      produce nearly identical audio output; reuse introduces sub-perceptible error.

  Level 3 — per-axis relaxed fallback (diagonal near-misses):
      ∀i  |v_candidate[i] − v_known[i]|  <  tol_axis  (default 0.12)
      Catches misses where one axis is close but Euclidean distance exceeds tol_L2.

  The class-level index _POOL_3D_VECS maps (key mod FI) → 3D vector.
  SCodeOptimizerBridge.query_nested_3d_grep(key, known_keys, ca_hash, ball_h, vec_mag)
  runs all three levels in order and reports 3D hit counts in pool_stats().

  Pool Hits tab in the SynthsMasterPanel shows:
    blue  = scalar FI hit (Level 1)
    green = 3D proximity hit (Levels 2–3)
    red   = full miss (subprocess call required)

38.3.1 Adaptive Gate Optimizer (Convolutional Pool Shapeshifting)  (R23R · 2026-11-03)
  The L2/L3 tolerance gates are not static — they reshape themselves around
  the current density of the pool's 3D state space.  A sliding window of the
  last 128 hit/miss outcomes is convolved with a 32-sample rectangular kernel
  to produce a smoothed hit rate.  Separately, the mean inter-point distance
  within the recent dense sub-cloud of hit state vectors is computed and
  halved to yield a density-derived tolerance.

  New tolerances are blended 60% density / 40% rate-driven each tick:
    • If hit rate < 25%: tolerances expand ×1.12 (search wider)
    • If hit rate > 65%: tolerances contract ×0.88 (tighten for precision)
    • Bounds: tol_L2 ∈ [0.02, 0.18]   tol_axis ∈ [0.06, 0.30]

  The Pool Hits tab now shows a yellow "Gate" row with live adaptive values:
    Gate: tol_L2 <value> · tol_axis <value> · hit rate <value>% (n=<window>)
  Call bridge.gate_optimizer_stats() to read the adaptive state programmatically.

38.4 Thread cap
  The sCode worker pool is capped at  min(32, cpu_count)  threads.  On the
  Latitude (8 cores / 32 logical threads) all 32 slots are used when the
  optimizer is under sustained load.

--------------------------------------------------------------------------------
39. HARDWARE RING BUFFER AND CLOCK MONITOR  (R23R · 2026-11-03)
--------------------------------------------------------------------------------
39.1 _ClockAlignedRingBuffer
  Decouples the PortAudio callback (runs on the hardware clock) from the
  Python render thread (runs on the CPU clock).  Structure:

      backing: float32 ndarray of shape (depth=4, block_frames=1024, channels=2)
      write_pos, read_pos: indices into the depth dimension
      full: True when write_pos has wrapped around to meet read_pos

  write(frames) — called from the render thread; returns False if the ring is
                  full (render should pause until a block is consumed).
  read(out)     — called from the PortAudio callback; copies the oldest block
                  into out and returns True; returns False on underrun (the
                  callback should output silence to avoid a glitch).
  fill property — 0.0 when empty, 1.0 when completely full.

  By keeping 4 blocks of headroom the ring absorbs ~85 ms of clock jitter
  before an underrun occurs at 48 kHz / 1024-frame blocks.

39.2 _HardwareClockMonitor
  Tracks the drift between the hardware audio clock and the CPU wall clock in
  parts-per-million (ppm):

      ppm = 1 000 000 × (expected_elapsed − actual_elapsed) / actual_elapsed

  The first 32 PortAudio callbacks are skipped (warm-up phase) before tracking
  begins.  drift_ppm() returns the latest ppm value; hw_ticks() returns the
  total hardware-clock frame count since tracking started.

39.3 Parallel hardware warmup
  warm_hardware_parallel() fires four tasks concurrently in a ThreadPoolExecutor:
    route      — query the default audio device routing
    snapshot   — take a hardware capability snapshot
    resolve    — resolve the preferred device name
    host_api   — detect the host API (ASIO / WASAPI / CoreAudio / ALSA)
  Results are merged and stored in the backend before the first render call.

--------------------------------------------------------------------------------
40. STARTUP SWEEP AND ENTERTAINER MODE  (R23R · 2026-11-03)
--------------------------------------------------------------------------------
40.1 Startup sweep
  Every time Groovebox returns to the main launcher window it plays a 48-note
  chromatic sweep (C2 → B5) through the multidimensional synth:

      hz_n = 65.406 × 2^(n / 12)   for n = 0 … 47

  A random global convolution seed is chosen for the sweep (later restored to
  the project's seed).  The AudioVisualizer is shown as a frameless
  window-stays-on-bottom backdrop for ~2.2 s while the sweep plays, then
  closed automatically.

  To skip the sweep in automated or debug launches, set the environment variable:
      GROOVEBOX_DEBUG_LAUNCH=1

40.2 Entertainer Mode
  Entertainer Mode (🎭 Entertainer Mode in the launcher) scans the filesystem for
  local audio and video exports (skipping external drives at /media/, /mnt/,
  /run/media/).  It shuffles the found files and generates a randomized parametric
  DJ script:

    bpm_hint    — integer BPM target for the track
    crossfade_s — crossfade duration in seconds (0.5–8.0 s)
    fx          — randomly chosen effect name from the installed FX list
    convolve_seed — seed for the global convolution kernel
    gain_db     — relative gain adjustment (−6 to +6 dB)

  The playlist is then sent to the In-App Media Player and playback starts.
  Files too large to hold in RAM are queued and loaded on demand.

40.3 Studio Session / Quick Jam shortcuts
  The launcher also offers:
    🎹 Studio Session  — opens Groovebox in full project-editor mode with
                         a blank patch, all engines on, 120 BPM default.
    ⚡ Quick Jam       — opens with a randomized seed, Randomize All pre-fired,
                         and the sequencer looped on the first four bars.
```
