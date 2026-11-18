# R89 — Reliability & Autopilot completion (not tested)

Built on R88. Packaged before any test run, by request.

- **Project transactions & recovery** (`project_transactions.py`): full checkpoints (project document plus the selected instrument and sequence, the export jobs and the live-buffer path) before Clear Memory, before and after Configure Entire Project, around every Autopilot project, and before any restore. An unclean exit is detected at the next start and the Recovery window opens. Restore always goes through `_apply_project_snapshot`, the same loader File ▸ Open uses; Studio session restore checkpoints first. Task pad ▸ 🛟 Checkpoints.
- **Autopilot Supervisor** (`autopilot_composer.py` + Autopilot window): Pause, Resume, Skip instrument, Skip project and Restart. Each phase has a time budget, and the supervisor holds (keeping the project) when playback makes no progress for 20 s, an export fails, or a phase runs too long. It shows the project, phase, operation, instrument, progress, phase time and total time. Delay between projects is settable (0 = continuous). Live Player stays one-shot with Loop OFF; export is opt-in, and the project is kept until playback and the export finish.
- **Audio diagnostics** (`audio_diagnostics.py`): Live Player meters per source (composition, media, keys, mic, final, recording) with clip and non-finite flags. There is a pre-export integrity check of the cached mixdown, and the check is part of the health report.
- **Resource supervisor** (`resource_supervisor.py`): CPU, RAM, threads, audio underruns, UI lag and idle worker processes in the status bar. Autopilot authoring slows down when audio underruns or the UI lags.
- **Math Lab**: inverse root, reciprocal, sigmoid, absolute, modulo and fold transforms; iteration depth and resolution levels; analysis of Seed, Canonical (selected sequence), User and combined values; the most efficient lossless representation (constant, curve, periodic or list); a preview with data points.
- **Project tools** (Task pad ▸ 🩺): health report, project comparison, batch browser (folders and checkpoints: open, or open and export), render preview of the first N rows, an instrument template library (save, apply, combine), and sequence morph.
- **Edit Synth Per Seq**: the sequence selector, geometric panels and multidim rack glow in the sequence's own colour (🎨 button or right-click to set it). A hint says which sequence you're editing, and tooltips are prefixed with it. Outside that mode the hint is white and tooltips are normal.
- **Release gate**: `scripts/release_gate.py [cycles]` covers compose, checkpoint, Clear Memory, restore, health, audio integrity and memory per cycle.

## R98 additions (not tested)

- Randomizer off / Random seed no longer reset tempo, playlist / sequence length, base frequency, row beats, track offset, the three seed fields or the other engines' toggles.
- Party background crash fix: a frame waveform held as an array made the paint handler raise, and Qt aborted the app.
- Threads: Live Player pool +1–2 workers (cap 8); video rig +1; recording streamer 2; live-audio lane +1; second interactive worker; canonical engine reserve up to 3; shared pool up to 6 (one core kept free on 4+ cores); one more parallel export when RAM allows (cap 8); larger rig / export / chunk allowances per machine size.
- Export verification: every finished export gets `<file>.verify.json` (size, SHA-256, duration, sample rate, channels, bit depth; silent / clipped / non-finite check). A pre-export audio check runs when the mixdown export opens.
- Provenance inspector: Alt + right-click any control for a read-only card with its user, canonical, per-sequence, live and final render values, the seed values and the active canonicals.
- 🧰 Extras (Task pad): find any control (Ctrl+Shift+F), project history (jump to any undo step), stem export (one WAV per instrument in use, each from a frozen project with only that instrument soloed), crash report bundle.
- The release gate compares the sequence data itself (load normalisation adds empty per-step lanes).

## R99 (not tested)

- **Settings and Compatibility fix**: `compat_settings.py` no longer fails when `groovebox_runtime/default_migrations.py` is missing from an install (it has a built-in fallback), so Settings and Compatibility always open.
- **.MCC player**: video blocks are decompressed in parallel; frames become images and are scaled to the view in the decode thread; the decode-ahead holds up to 256 MB of frames. Each frame is shown at its own time from the audio device clock (samples handed to the device, minus its latency) or a monotonic clock without audio. Late frames are dropped and counted, early ones held. The video waits for the audio to start, so the two begin together.
- **Master Mod Matrix** (Task pad ▸ Studio ▸ 🧬): sources are LFOs, the seed, canonical level, the playhead, MIDI CC, patch-bay fan-in, any automation target, and the output of earlier rows (so the matrix is its own patch bay). Methods: add, multiply, ring, min, max, crossfade, FM, fold, sample-and-hold, gate, quantize. Targets are any automation target, including global tuning. A per-row Canonical blend mixes in the seed curve of the target, in unison. It runs live and per row in every export, and is saved with the project.
- **Carrier layers** (🎞): layers for the global carrier and for each instrument carrier. Each import gets a start row, length in rows, stretch (pitch kept), pitch (length kept), gain, offset, fade, loop, reverse, mute and solo, shown as lanes over the playlist. The mix becomes the carrier the renderer reads.
- **🔔 Notices**: a compact status-bar button (newest notice, 42 characters max, plus a count) that opens the full list. It collects UI stalls, canonical updates skipped because nothing changed, Live Player audio errors, export check warnings and resource warnings; repeats are folded. The resource monitor label is now short, with details in its tooltip.
- **✨ Features**: piano roll, arrangement blocks (move, duplicate), clip launcher, MIDI clock in and out, MIDI learn, scale lock, swing and groove from audio, sample slicer, audio → sequence, sidechain and FX matrix view, cut list (CSV + EDL), title layer and colour grade or LUT on finished videos, 3D camera path keys, standalone game export, game input mapping, panel presets, project templates, A/B snapshots with morph, a what-changed view after canonical commits, a render profiler, audio plugins (VST3 / LV2 / AU through `pedalboard` when installed), folder mirroring, a guided tour, and accessibility names for every control. Hardware video encoding (NVENC / QSV) is a choice; the default is still software.
- The Task pad now has a separate Studio row for the new tools.
- **Mod matrix, canonical control**: while canonicals are active, every row blends toward the canonical curve of its target by at least *Canonical authority × the canonical level* (default 0.5, saved with the project). **⚙ Add canonical entries** creates a seed-driven, fully canonical row for every pathway group. The pathways now include the global panel states (mod, algo, sidechain, EQ, patch motion, hyperdrive, vector, sample morph, per-seq) and the global panel controls themselves (EQR, Fractallizer, PKP, convolve, canonical knobs, seed reach and divergence, tuning, Global Play sliders, energy and harmonic, base frequency).
- **Translucency**: the multidim synth panel, its 3D view and its control rack are translucent to the parametric math and Party Mode backgrounds. Every group box and frame that is not primary interactive UI gets about 72 % opacity (buttons, inputs, sliders, lists and text editors stay solid), in the main window and in every window as it opens.
- **Canonical distribution** (Mod Matrix window): the canonicals' effect (budget × canonical level) is spread over every enabled pathway with a convolution kernel, so many controls each move a little and no single control carries the effect. You choose:
  - **What:** scope, by pathway group.
  - **How:** the kernel (convolve, gaussian, uniform or seed), the spread width and the row method.
  - **How much:** a total budget and a cap per control.
  - **Process:** which inputs it reads (seed, canonical level, current values) and whether to skip targets you modulate yourself.
  
  A new distribution replaces the old one only if it scores higher on J = coverage × (1 − concentration) × fit. That is a stated, cheap, parameter-space objective, not a listening test. It runs automatically after every synchronous canonical commit (it can be switched off, and doesn't yet run after the sliced/cooperative commit GOAVA uses). Preview / Distribute / Distribute (ignore J) buttons are included, and everything is saved with the project.
- **🌌 Seed Atlas** (Task pad ▸ Studio): a bounded, deterministic fractal of the ways a seed becomes media.
  - **Address:** reading ▸ domain ▸ method, repeated for each level.
  - **Readings:** value, text, orbit over t, decimal digits.
  - **Domains and methods:**
    - sound: additive, FM, Karplus–Strong, granular, logistic orbit, cellular-automaton rhythm, L-system melody;
    - image: Mandelbrot, Julia, contractive IFS, automaton, L-system turtle, spectrogram of the node's own sound;
    - game: maze, diamond-square terrain, automaton cave, rhythm chart, L-system platformer;
    - 3D: torus knot, terrain mesh, L-system tree, as OBJ;
    - external apps.
  - **Fractal:** each level is rendered from a child seed H(parent, address), so the tree is self-similar.
  - **Limits:** 4 levels and 88 children per level, expanded only when you open a node. Media size is bounded: 4 s of audio, 256² images, 48×32 levels, 4096 vertices.
  - **Per node:** play, save, use in the project (carrier, window background or video OBJ), use its child seed as the Global Seed, or send the file and seed to an installed app (`GROOVEBOX_SEED`, `GROOVEBOX_ATLAS_ADDRESS`, `GROOVEBOX_ATLAS_FILE`).
  - **Checked:** every method was rendered for three seeds and three readings with no error (3.4 s). The external-app send was not run.
- **🗺 Experiences** (Task pad ▸ Studio): one catalogue of every creation and its science.
  - **What it lists:** exports (with their verification), takes, checkpoints, Autopilot projects, saved projects, Seed Atlas renders, stems and music videos.
  - **Per entry:** time, kind, size, seed and its fingerprint, canonicals, BPM, base frequency, tuning, distribution score J, and the audio check. You can add a rating, tags and notes.
  - **Tools:** search and filter, a science sheet, open or play, re-open the project, use its seed, compare two, lineage (everything that shares a seed), and export as CSV or JSON.
  - **How it fills:** entries are recorded as they are produced, and **⟳ Scan** indexes existing folders. Nothing is moved or deleted.
- **Autopilot:**
  - **Cursor:** the visual operator re-fits and repaints ten times a second, stays on top, drops deleted targets, and scrolls only when the target is off screen (at most twice a second). It now follows every phase: Configure Entire Project, each instrument page with a "play in ≈ N s" countdown, and the playing project.
  - **New options:** "Visit every instrument page" (on; off goes straight to Live Player), "Record each Autopilot play" (OFF) and "Master each recorded take" (OFF). A FULL CPU preset that records respects this choice while Autopilot runs.
- **Seed Atlas → engines:**
  - any node's sound can become the selected instrument's voice layer;
  - every image node can become a music video (.MCC with its own soundtrack; the reading moves through time);
  - game nodes are playable: maze, cave, platformer, and a rhythm chart on D F J K with its own sound. Keys follow the game input mapping;
  - every node can be heard through its paired sonification.

## R100 (not tested)

- **🌐 Network** (`net_hub.py`, one small SQLite database):
  - **Radio:** name, logo, a running order you arrange, on air on the LAN, and a /radio page with comments, messages to the host and ratings.
  - **Nearby radios:** radios on the LAN pop up. Trusted and Housemate stations can auto-play (setting `radio_autoplay`).
  - **Blog:** a blog editor; posts appear at /blog.
  - **Hosting:** hosted files with embed players at /hosted and /embed/<id>, with range streaming and comments on each file.
  - **Trust levels:** Housemate / Trusted / Friend / Public / Blacklist 1–3, enforced on every site request.
  - **Host / repeater network:** a network name and key, with primary and gig hosts that sync rows and files with each other (HMAC-signed, last writer wins). Members announce their libraries, get notices and fail over between hosts. Boot mode is `network_mode` (or `GROOVEBOX_NETWORK_HOST=1`).
- **🔌 Plugins** (`plugins_library/`, `plugin_library.py`):
  - **What's included:** 73 Groovebox plugins in Python, Lua, C, C++, Rust, Go, Julia and shell: 37 that make content, 28 informative ones, 4 games and 4 live tools.
  - **Browser:** a browser to run them, plus LAN sharing and install (validated, never auto-run) and public ratings.
  - **Bindings:** a plugin can be an instrument's carrier, its controls.json values can be Mod Matrix sources, or it can run on seed change, canonical commit, export finished or project load.
  - **🎲 Randomize project:** random plugins with their own states and/or random samples (list or disk scan), with an original-synth participation percentage.
- **Protection** (`plugin_guard.py`): process isolation, a cleaned environment, one request door, a whitelist, validation, rate limits, transactions with rollback, and output checks. External apps and programs stay strictly under 0.19758 of CPU and RAM (`app_limits.py`).
- **🌙 Lua workspace** (LuaJIT via lupa, sandboxed, with bytecode compile) and **🛠 Program Builder** (C, C++, Rust, Go, Julia, Lua, Python and shell, with Install Julia).
- **Hybrid router** (`hybrid_runtime.py`): NumPy, Rust, LuaJIT and Julia, parity-gated and timed. **sCode coordinator**: directions plus a 🌳 window showing the process tree.
- **Builders:**
  - The ISO setup adds lupa as an optional, non-fatal install.
  - The ISO overlay carries the plugin library.
  - The executable builders collect the plugin library, the new modules, and lupa / juliacall when installed.
  - The installers add lupa without failing.
- **Help:** chapter 45 covers all of the above.

## R101 tool sweep (not tested)
- **ISO → USB writer:** no longer needs `dd`. It writes 4 MiB blocks itself, with fsync and a check of the first block. Without device access it runs through pkexec / sudo, and falls back to `dd` only after that.
- **`sos_tools.py`:** finds every external tool through PATH, the standard system directories and busybox applets, and has a privileged-run helper. 171 `shutil.which` calls in 47 modules now use it. PATH is completed with the system directories at startup, and the health report lists missing required tools.
- **Image:** adds parted, exfatprogs, usbutils and xdg-utils.
- **Ported:** the microSD / PHY module bundle and the launcher import-probe report.
