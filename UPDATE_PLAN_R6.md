# Update plan R6 (2026-11-12)

All code for this round is written first and archived. Tests and video exports run only after that archive is sent.

## Party Mode = contextual UI visuals + UI sound (one law)

The law: z' = λz, with λ = a(2σ − 1) + iω. σ is significance.

- σ < ½ (sink): an ordinary, comfortable change.
  - Rings are concentric.
  - Textures float in and vanish at the point.
  - The sound decays onto a consonant degree.
- σ > ½ (source): a sensitive, consequential change.
  - Curvature κ = 2σ − 1 bends the rings and the mesh.
  - Material is pushed out.
  - The sound swells, bends and is cut, with sample-and-hold grit.

Each channel informs you about the composition:

| channel | encodes |
|---|---|
| curvature | significance σ of what you are changing |
| light / dark mesh | brightness ∝ 1/\|det J\| of the flow map: compressed cells are lit, spread cells are darker |
| hue | pitch class: key-chart degree / steps × 360° |
| tint regions | spectrum: one region per band (low = warm, high = cool), opacity = band energy; they only move and morph |
| textures | snippets of the recent material carried by the flow |
| caption | which control changed, its value, and comfortable / sensitive |
| sound | project tuning (base Hz × active key-chart ratio); stochastic energy (Poisson micro-grains); resampling of the recent track |

## Items (55, problems to fix included)

| # | item | files |
|---|---|---|
| 1 | Party Mode defaults ON at level 0.19758 (19.758 %); intensity stored as a float; one-time migration of saved settings | compat_settings.py |
| 2 | Bug: Party Mode never started at launch (only the 🎉 toggle started it), so it starts after startup now | groovebox.py |
| 3 | Party sound engine: σ envelope, consonant sink and bent source, Poisson stochastic energy, resampling, sample-and-hold | party_sound.py |
| 4 | Shared field core: flow map, Jacobian light mesh, spectral tint regions, audio analysis, video frame effect | context_field.py |
| 5 | Overlay: spectral tint regions that only move and morph (soft light) | party_overlay.py |
| 6 | Overlay: light/dark curvature mesh, brightness ∝ 1/\|det J\| | party_overlay.py |
| 7 | Overlay: hue = pitch class (live dominant degree, or the control position as a degree) | party_overlay.py |
| 8 | Overlay: captions naming the control, its value and comfortable / sensitive | party_overlay.py |
| 9 | Overlay: sound hooks (click, wheel, focus, adjust) and ambient Poisson grains | party_overlay.py |
| 10 | System Settings: 0.001 % level slider, Party sounds checkbox, keeps the 🎉 button in sync | sos_system_settings.py |
| 11 | 🎉 button: new default and tooltip with the current level | groovebox.py |
| 12 | Party sound uses the ACTIVE tuning (`_keychart_ratio`, including composition_tools tunings) | party_sound.py |
| 13 | Party sound follows Master Volume on the audition-mixer path (0 = silent) | party_sound.py |
| 14 | Party sound: a full concurrent bus never raises; the sound is skipped instead | party_sound.py |
| 15 | Party Mode is silent and draws nothing over the PIN lock screen | party_overlay.py |
| 16 | Party off also clears the caption state | party_overlay.py |
| 17 | Video: "Party Mode in the video" context layer in the OBJ system (σ from novelty, hue from degree, tints from bands, centre at the spectral centroid) | project_obj.py |
| 18 | Video: OBJ meshes follow the same flow map (`flow_deform`) | project_obj.py |
| 19 | OBJ window: toggle + strength slider; project schema keys (off by default, so exports stay bit-identical) | project_obj.py, project_schema.py |
| 20 | Video context is deterministic: state resets at frame 0 of every render | project_obj.py |
| 21 | thread_budget: caller-runs for a nested submit from a saturated managed worker (deadlock guard) | thread_budget.py |
| 22 | thread_budget: per-lane stats (submitted / completed / failed / cancelled / inline / wait / run) | thread_budget.py |
| 23 | thread_budget: memory-headroom probe cached for 2 s | thread_budget.py |
| 24 | thread_budget: live lane registry + `lane_report()` | thread_budget.py |
| 25 | System Settings: live thread-lane readout (busiest lanes, caller-runs, waits), updated only while visible | sos_system_settings.py |
| 26 | scode window host: fast path for its app-wide event filter; tooltips, popups and menus no longer get task scopes and lanes | scode/window_host.py |
| 27 | groovebox.py: literal `\n` in the "Part … encode failed" message | groovebox.py |
| 28 | groovebox.py: release the export master with `master = None` instead of `del` (a closure still referenced it) | groovebox.py |
| 29 | game_editor install hook tolerates hosts without `_classify_live_game` | game_editor.py |
| 30 | composition_tools tuning hook tolerates hosts without `_keychart_ratio` | composition_tools.py |
| 31 | instrument_mixer hook tolerates hosts without `_render_instrument_voice` | instrument_mixer.py |
| 32 | Dev Overlay scratchpad: toolchain report (py / C++ / Rust / Julia / sCode), with reasons for missing ones | dev_overlay.py, dev_overlay_ui.py |
| 33 | Bookmarks: UTF-8, closed file handles, atomic save | state_bookmark.py |
| 34 | Session notes: UTF-8 read/write, atomic save | session_notes.py |
| 35 | Session notes autosave 1.5 s after typing stops | session_notes.py |
| 36 | UTF-8 writes: appliance_tuning, pool_matrix | 2 modules |
| 37 | UTF-8 writes: update_signing (two files) | update_signing.py |
| 38 | UTF-8 write: signal_converters feature CSV | signal_converters.py |
| 39 | UTF-8 writes in groovebox.py (session layout, project save, resume file) | groovebox.py |
| 40 | UTF-8 reads in groovebox.py (session layout, deserialize_project) | groovebox.py |
| 41 | r32_deck: the retry budget was a shared mutable default; it is per window now | r32_deck.py |
| 42 | Pathway log: rotate at 2 MB (it grew without bound) | pathway_hub.py |
| 43 | Pathway log: `recent()` reads only the tail | pathway_hub.py |
| 44 | engine_auditor `--tail`: reports a stale live status (the flag was computed and never used) | engine_auditor.py |
| 45 | UTF-8 reads + closed handles: engine_auditor, site_directory | 2 modules |
| 46 | Seed → MP4 with sound (`seed_tools.render_av`): streamed, deterministic, context field reading the music | seed_tools.py |
| 47 | Bilinear frame upscaling helper for the field | context_field.py |
| 48 | Seed algebra tab: "🎬 Seed → 1080p video + sound…" | seed_canonical_window.py |
| 49 | Field guard for tiny frames | context_field.py |
| 50 | Unused imports removed in the touched modules | composition_tools, instrument_mixer, session_notes, project_obj |
| 51 | compat describe(): Party level with 3 decimals + sounds | compat_settings.py |
| 52 | `party_sounds` saved and cleaned like the other booleans | compat_settings.py |
| 53 | Party docs rewritten (law, channels, rules, video, files) | PARTY_MODE_NOTES.md |
| 54 | Overlay and video share one flow implementation (`context_field.flow_point` / `flow_lambda`) | party_overlay.py, context_field.py |
| 55 | Runtime payload sync of every changed file (BUILD_KIT / ISO copies) | scripts/sync_runtime_payload.py |

## After the archive
1. Tests:
   - pyflakes
   - new tests for party_sound, context_field, party_overlay and thread_budget
   - existing dev overlay, seed tools and hotfix contract tests
   - golden hashes
   - offscreen screenshots
2. Fix anything found, and send an archive after each set of tests.
3. Full-HD (1920×1080) video-with-sound exports from seeds, zipped.
