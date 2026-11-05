================================================================================
R28.4.35 — CANONICAL FRACTAL COMPOSITION, CROSS-MEDIA WORKFLOW, AND TABLETIME
================================================================================

This section describes the intended operating contract for the current release.
Controls remain authoritative: a feature described here is active only when its
corresponding control, engine, input, or platform capability is available.

1. THE 50 / 50 COMPOSITION BALANCE
----------------------------------
The composition has two normalized sources of influence:
  • 50% seed identity and source evidence — the recognizable core of the piece.
  • 50% the remaining composition — arrangements, user-authored material,
    annotations, automation, and subsequent creative decisions.

This is a weighting rule, not equal file sizes, event counts, durations, or screen
area. Neither half may silently erase the other. Derived/canonical material and
user writables remain distinguishable so you can revise either without losing
the identity or the authorship of the other.

2. DETERMINISTIC GENERATION — NO HIDDEN PROBABILITY
--------------------------------------------------
Composition behavior must be reproducible. Given the same project, explicit seed,
settings, canonical state, and input media, the same rules should produce the same
planned result. Do not use a true/random probability draw to decide composition
content. Use deterministic mappings, explicit seeded values, ordered transforms,
and documented tie-breaks instead.

An explicit user-requested randomize action may create a new authored starting
state; once captured in the project, that state must be saved and reproducible.
This is different from hidden random draws occurring during playback or export.

Phase/step shifting and omission are intentional composition choices, not silent
error recovery. They are permitted only as a decisive, explicit scenario while
Canonical controls are enabled. Otherwise, preserve the source events and report
what cannot be represented rather than arbitrarily dropping material.

3. CONCENTRIC FRACTAL STRUCTURE AT ANY RESOLUTION
------------------------------------------------
Think from the most identity-defining structure outward:
  Seed/source evidence → global form → major sections → phrases and layers →
  local events → fine details → output-resolution realization.

This hierarchy is recursive, not a fixed number of levels. High- and low-resolution
outputs should be realizations of the same canonical structure. Resolution changes
may simplify, aggregate, interpolate, or omit detail only under explicit rules;
important structure remains prioritized by prominence, concentricity, relevance,
fit to the target resolution, novelty, and provenance. Keep a loss/uncertainty note
when the target cannot preserve all detail.

4. ONE COMPOSITION FOR SOUND, VIDEO, AND INTERACTION
---------------------------------------------------
The canonical project is the shared source for musical events, audiovisual timing,
procedural scenes, and compatible game/interactivity fields. Shared graph context
may include musical time, normalized time, seed, spatial coordinates, phase, energy,
curvature, sequence/step indices, domain values, and project-specific identifiers.
Each output consumes only the channels it supports; audio, video, and game output
should not drift into unrelated seed identities.

Timeline mappings must be explicit: timebase, interpolation, quantization, event
collision handling, and conversion loss should not depend on execution order.
Live performance may preserve phase continuity; a fresh export should start from
a documented reproducible phase state.

5. SAVE, IMPORT, ROUND-TRIP, AND PROJECT HISTORY
------------------------------------------------
Keep one canonical source of truth, stable event identifiers, provenance, and a
transformation history. Save the seed, relevant engine/control state, user-written
content, media references or included media, and export-relevant parameters.

Import should be idempotent: importing the same source twice must not duplicate
its content. Reverse import reconstructs what the source actually contains; it
must not invent missing values. Record unresolved ambiguity and lossy conversions.
Prefer canonical diffs/merges and reversible, versioned migrations. Never overwrite
the original project during migration; keep a recoverable copy.

6. REAL-TIME SAFETY AND BACKGROUND WORK
---------------------------------------
The audio callback must remain bounded and nonblocking: no disk access, heavy
calculations, process launches, or unsafe blocking locks in the real-time callback.
Do expensive parsing, analysis, and rendering on owned background workers; publish
immutable, versioned snapshots to the audio path. Reject stale results using
operation/project-generation identifiers. Progress, completion, cancellation, and
errors should be distinguishable. Stop/cancel must stop the actual operation and
not create relaunch loops or orphaned workers.

Keep the Mathematical Composition Lab scrollable so every control remains
accessible. Preserve verified hardware routing and working audio/performance
behavior unless a reproducible test identifies a specific defect. Worker-pool
limits must retain the R28.4.33 portability policy: bounded adaptive workers, a
logical CPU reserved for GUI/audio/OS work where feasible, and no more than eight
background workers under that policy.

7. MATHEMATICAL COMPOSITION LAB
-------------------------------
Use the Lab to inspect and shape deterministic relationships between phase, seed,
structure, density, and canonical contribution. A phase seed is a stable input,
not a request for a hidden random trial. Canonical contribution curves should be
deterministic. Keep the Lab scrollable; changing resolution must not create a
separate, contradictory composition.

8. TABLETIME — COMPANION WORKFLOW
---------------------------------
Tabletime is the companion scheduling and community/context workflow. Open the
Tabletime web app at https://tabletime.app/ . This Groovebox package links to the
Tabletime service; it does not bundle Tabletime's separately hosted backend or
claim that a remote Tabletime deployment was changed by installing Groovebox.

For Tabletime features that are enabled on your account/build, use the app's
existing timetable, scheduling, and post/context workflows. Preserve its established
Moksha/Karma features, scoping sliders, and post time-delay controls (including
the existing 5–10–… range/behavior) during future integration work. Do not silently
replace those controls or change ad accounting: one ad credit equals exactly one
impression. Account-specific availability and live service behavior are determined
by the deployed Tabletime app, not by this desktop README.

9. EXPORT AND DELIVERY CHECKLIST
--------------------------------
Before relying on a deliverable, verify the relevant layer independently:
  • Source: syntax/compile and focused regression tests.
  • Project: save → close/reopen → deterministic re-render and import idempotence.
  • Audio: output selection, playback continuity, Stop/Cancel, and export.
  • Video/game: shared timeline, supported media inputs, and deterministic replay.
  • Package: ZIP integrity, file size, current release metadata, and no superseded
    release accidentally stacked into the download.
  • Deployment: verify the live URL and served release after authenticated publish.

A source archive or local preview is not proof that a privileged ISO build, physical
hardware test, or live Wasmer deployment has succeeded. Report those states separately.

================================================================================
END R28.4.35 ADDITIONAL HELP

## Global carrier synths and reset behavior (R28.4.42)

Vector, Wavetable, Bouncing Ball, and Cellular Automata are intended as peer,
single-instance global carrier-wave generators. Vector and Wavetable provide
separate User and Canonical influence controls with a neutral 50/50 reset that
preserves authored program data. A manual Ball bounce or Cellular Automata
single-cell lock is user activity: Canonical must not auto-start or replace that
lane until its lane-specific Reset control clears the lock. Ball Reset clears the
Ball activity lock; Cellular Automata Reset clears the cell-lane activity lock.
These are lane resets, not destructive project resets.

The four global carriers have a 0.5 sidechain-depth scale relative to other
instruments. The shared context API supports independent activity locks and reset;
actual UI gesture wiring and live DSP application must be verified separately.
Do not treat metadata or passing unit tests as proof of a live audio build.
## Global geometric carriers: base-frequency tracking

Vector, Wavetable, Bouncing Ball, and Cellular Automata share the global base-frequency tuning value (the Base Frequency spinner). Canonical predictions write derived event frequencies from that value using equal-tempered pitch ratios, with MIDI pitch 69 as the reference pitch. Canonical frequency fields are regenerated on tuning changes; fields/events explicitly marked `user_data_protected` are preserved. The four carriers remain global single-instance lanes and use 0.5 of the global sidechain depth. This source contract must be connected to the UI spinner and verified in each live renderer before claiming end-to-end runtime integration.


## R28.4.42 Seed Script canonical variable handles

Seed scripts use a restricted deterministic numeric expression environment (no arbitrary builtins, file access, imports, or network access). `t`, `x`, `y`, `z`, `seed`, graph/sequence variables and the math/Meum/ISN/ICS functions remain supported. If a project supplies canonical context, explicit numeric scalar fields override the documented defaults below.

| Handle | Meaning | Default |
|---|---|---:|
| `vector_x`, `vector_y`, `vector_z`, `vector_drive` | Vector carrier state | 0, 0, 0, 0.5 |
| `wavetable_phase`, `wavetable_curvature`, `wavetable_twist`, `wavetable_fold`, `wavetable_canonical_share` | Wavetable state | 0, 0.5, 0.5, 0.2, 0.5 |
| `ball_gravity`, `ball_gravity_angle`, `ball_radius`, `ball_vx`, `ball_vy`, `ball_polarity` | Bouncing Ball state | 0.25, 90°, 1, 0.7, -0.4, 1 |
| `cell_width`, `cell_height`, `cell_types`, `cell_generations`, `cell_rule` | Cellular Automata state | 16, 16, 3, 16, 30 |
| `sidechain_depth`, `sidechain_attack_ms`, `sidechain_release_ms` | Sidechain envelope parameters | 0.5, 10, 120 |
| `eq_poles`, `eq_low_hz`, `eq_high_hz` | EQ topology and frequency limits | 128, 10, 24000 |
| `mix_seeded`, `mix_rand`, `mix_lock`, `mix_euclidean`, `mix_goava` | Canonical engine contributions | 1, 1, 0.5, 1, 0.19758 |
| `goava_canonical_amplitude` | GOAVA active default amplitude contract | 0.19758 |

Examples: `0.5*sin(2*pi*t)`, `lerp(ball_vx, vector_drive, 0.25)`, `clamp(sidechain_depth*mix_goava, 0, 1)`, and `eq_low_hz + (eq_high_hz-eq_low_hz)*t_norm`. Use `clamp(value, low, high)` to keep authored ranges bounded. Scripts remain deterministic: no random/probability calls are added to composition logic. `eq_poles` is clamped to 2–128; canonical EQ policy uses `max(2, min(128, 130 - instrument_count))`, with linear frequency spacing from 10 Hz to 24 kHz. These handles are exposed to the safe evaluator; runtime coupling to each renderer/mixer must still be verified before claiming all engines consume every handle end-to-end.

## Ball and Cellular Automata controls

The main window exposes numeric controls for Ball gravity/angle/radius/velocity/polarity reversal and Cellular Automata grid width/height/state count/generations/rule/neighborhood. These are deterministic editable parameters. Activity-lock controls protect user activity until explicit reset; engine-level lock integration and actual hardware playback require runtime verification.

## Audio compatibility and troubleshooting

The app's canonical render/export rate is independent of physical device support. For live playback, use a device-supported rate (commonly 44.1 or 48 kHz), verify the selected non-null output device, then test one source at a time before combining streams. The persistent audition path sanitizes non-finite samples and caps pre-output peaks to 0.98 to preserve headroom. This source-level guard does not prove a PortAudio device is successfully opened; inspect runtime stream errors and test playback repeatedly with both main and Performance master sliders.
