# Safe V3 Feature Merge

## Generated-spec ISO repair and launcher/help revision

The latest supplied traceback exposed a missed source-check dependency on
`build_executable/spec/MathematiciansGroovebox.spec`. This exact issue was not
caught before the preceding snapshots were sent. An ISO source check must not
require that generated, archive-excluded EXE artifact.

- **Shared packaging inventory:** All seven affected feature checks now inspect
  the source inventory. BUILD_KIT uses the same `runtime_module_names()` helper
  for hidden imports. The verifier structurally checks that the builder forwards
  this inventory into PyInstaller's hidden-import list. Its actual source and
  active-overlay checks remain; no dummy spec or unconditional pass was added.
- **Working directory:** Rebuilt native catalog checks receive the project
  working directory explicitly instead of depending on the caller's directory.
- **Launchers:** Preserve virtual-environment interpreter paths; quote paths and
  arguments; clean inherited Python overrides; reuse optional native libraries;
  avoid obsolete installer flags; preserve relaunch arguments without ordinary
  failure/Ctrl+C loops; separate required dependencies from optional WebEngine.
- **Appliance staging:** Include the shared launcher's
  `scripts/runtime_dependencies.py` in the final rootfs and require its presence.
- **Help and context:** Searchable in-application help contains current features,
  context/representation boundaries and the HF15 deployment guidance.
  `HELP_TEXT.md` is regenerated from the actual help string. The README's
  launcher/context notes now exist.

See `ISO-SPEC-DEPENDENCY-REPAIR.md` for the small repair instructions and
`LAUNCHER-AND-CONTEXT-NOTES.md` for the complete launcher/context summary. The
full source archive includes these changes and refreshed active runtime modules.
No application, verifier suite, EXE/ISO build or hardware test was run for this
revision, as requested. This repair addresses the reported dependency; it is not
a claim that every later build stage will succeed.

## Portable ISO and executable builder revision

The supplied Fedora traceback is an audio-fixture assertion, not a demonstrated
Python 3.14 incompatibility. The older fixture required analog index 1 while the
current selector can prefer an aggregate sound-server route at index 0, and
aggregate preparation was not isolated from the build host.

- **ISO checks:** isolate the audio fixture while preserving its assertions;
  remove a personal cache path; compile host source checks without bytecode
  writes; fix launch-directory/import defaults and the active overlay default;
  replace a formatting-sensitive HDMI assertion with structural inspection.
- **Executable builder:** clean child Python path overrides; use project-local
  pip/PyInstaller caches; diagnose non-writable outputs and stale venvs; run
  doctor against the actual build venv; reject invalid active source; repair
  required stage-0 before its strict gate; bundle exact validated codec paths;
  correct one-file archive inspection; propagate PowerShell build failures.

See `PORTABLE-BUILD-FIXES.md` for examples and limits. This is a source package,
not a compiled EXE or ISO. No verifier suite or build was run for this revision;
the working GUI and runtime audio policy are unchanged.

## Painter safety and maintenance sweep

This source revision addresses lifetime hazards consistent with the supplied active-painter warnings. It preserves the first archive's working GUI and the wider master/editor layout; neither comparison archive's main window was transplanted. Runtime testing and full ISO builds were not run for this revision.

- **Archive comparison:** R41 adds event-boundary cleanup, while rev-m/rev-p has an earlier exception-only guard. The current tree had a multidimensional global painter factory and subclass sweep, main-window painters without guaranteed local cleanup, and a paint decorator attached to an editor-opening method. Importing that machinery wholesale would not give every dynamically created widget reliable local ownership.
- **Scoped painters:** Added `qt_painting.py` and explicit scopes at 46 painter construction sites across 13 application modules. The scopes end their own painter after success, exceptions and early returns; skip busy/deleted/off-thread widgets; and reject failed offscreen painting rather than publishing an invalid frame. The real Qt `QPainter` class and its enums remain intact. The standalone game viewport has equivalent inline cleanup without importing application modules.
- **Live composition and media:** Trail-image painters now unwind on failure. Empty scopes render silence instead of indexing an empty array, nonfinite scope samples are sanitized for visualization only, and a zero-width CA preview cannot divide by zero. Media preview images own a copy of the decoder pixels.
- **Recording safety:** Take names include a unique suffix, audio disk/close failures are reported, and failed finalization retains recovery intermediates. Encoder pipes/logs are closed, hung finalization has bounded termination, and the fixed 150 ms GUI-thread encoder-start sleep is removed. If the initial video snapshot arrives late, earlier frame slots use a neutral slate, not future footage.
- **Diagnostics:** Painter/backing-store warnings now include bounded Python call stacks in the existing session log, and update `LATEST_CRASH_LOG.txt`. This can locate a remaining failing call site without unbounded stack/log spam.
- **Packaging:** The new helper and changed authoritative root modules are included in the common runtime inventory and synchronized to the active ISO overlay. This is source packaging, not proof of a successful ISO build, hardware installation, or elimination of every possible native crash.

Read `PAINTER-SAFETY-SWEEP.md` for the findings, scope and remaining limitations. Cooperative canonical batching remains opt-in and unvalidated; the default canonical commit can still pause the GUI.

## Wide editor and live-recording revision

This revision follows the wider-canvas preference and preserves the original working main-window implementation. It is an updated source archive, not a completed ISO or a hardware-certified laptop installation.

- **Master synth:** Restored broad, independently biaxial upper/lower canvases; enlarged the animated master stage and its projection; aligned the sequencer/automation ring with the actual graphic stage. Fixed the overlapping top strip and parameter rack. Script/domain editors and floating synth controls have real editing floors, and the toolbar can center the master graphic.
- **Additional controls:** Imported the compatible sample-mimic, live step-record and LAN-chat handlers and their buttons without importing either comparison GUI. Restored the sample-binding-aware key trigger so Live Jam/replay can pass its binding and pitch-bend metadata. Added reset-master-modulation access.
- **Global Live DJ:** Exposed Beat Gate, Harmonic Fold and Spectral Tilt alongside the original macros. Enabled effects feed live-player output before its recording tap, and have separate DSP history from offline export. Their controls persist in project data.
- **Recording timing:** Captured audio samples, rather than GUI timer count or wall-clock encoder setup, now set the video timeline. Timestamped frames preserve duration by holding the preceding image across stalled ticks or a full queue. One snapshot per UI tick replaces synchronous catch-up loops. Writer shutdown checks prevent finalization or temporary-file deletion while a writer remains active.
- **sCode and seed work:** Added exact-input pooled canonical projections over copied widget-free data, one running/latest replacement request, full digest checking, exact seed-value memoization and bounded EQ reuse. Removed the redundant full-bank reconcile for every active engine. The square-layout helper now requests an asynchronous preview instead of rendering the whole scenograph on the GUI thread.
- **Predictive process:** One optional low-priority spawned process computes an exact adjacent canonical state, with no speculative backlog, an 8 MiB input ceiling and a no-wait foreground lookup. It is disabled on CPU budgets below three cores and can be disabled with `GROOVEBOX_PREDICTIVE_BUFFER=0`. CPU availability now includes Linux cgroup quotas.
- **Requested weights:** Background work uses `0.048 * window_selected + 0.19758 * activity + 1.0 * tedious`. Inputs are clamped to 0–1. The all-active total is 1.24558; normalized shares are approximately 3.85%, 15.86% and 80.28%. Prediction is capped at one third of available capacity; audio callbacks and UI refresh are not subject to this background priority queue.
- **Cooperative commit prototype:** Static generated canonical kernels and an ordered GUI batch controller are included, but remain OFF by default pending further validation. Set `GROOVEBOX_COOPERATIVE_CANONICAL=1` to try them. Large legacy GUI-owned commits can therefore still pause; this archive does not claim the entire canonical engine is fully asynchronous.
- **ISO builder:** Added persistent root-wrapper logs and automatic Podman `cgroupfs` selection when a systemd/D-Bus environment is unavailable. A container startup smoke probe succeeded with that mode. Your original ISO error log was not supplied, so an unrelated error on your machine remains possible.
- **Laptop preparation:** Added VMD/NVMe/AHCI coverage, broader wireless/GPU firmware, and a read-only laptop readiness script integrated before destructive installation. The supported target is conventional x86-64 UEFI/GPT PCs. Treat this as a Secure-Boot-off release; a signed boot chain has not been validated.

Dell documents that changing RAID On to AHCI can prevent an existing Windows installation from booting unless its operating-system image/driver configuration is prepared, so the installer does not change BIOS storage mode automatically ([Dell support](https://www.dell.com/support/kbdoc/en-us/000183948/latitude-systems-shipped-with-default-raid-on-mode-from-the-factory)). Back up your data and keep the device-encryption recovery key before changing firmware settings.

The added MediaTek firmware package covers MediaTek/Ralink network devices, while the NVIDIA firmware package supports the nouveau driver; neither is a guarantee for every Nitro 5 hardware variant ([Debian MediaTek package](https://packages.debian.org/trixie/firmware-mediatek), [Debian NVIDIA firmware package](https://packages.debian.org/trixie/firmware-nvidia-graphics)). No Latitude 3510, Nitro 5, or other physical laptop boot/install test has been performed, and no completed release ISO is included.

Further final/hardware testing was stopped at your request. Read `BUILD_ISO/logs/` for logs produced by future root-wrapper builds, and run `bash BUILD_ISO/check_laptop_readiness.sh` from the live laptop session before installation.

This release keeps the working GUI from `MATH_GROOVEBOX-v3.tar.gz`. The other two archives were comparison material for compatible features and implementation details, not replacement main windows. Subsequent final testing was intentionally stopped at your request.

## What changed

- **Layout:** Removed fixed-height ceilings that were smaller than their contents, including the global EQ and several control groups. The latest revision restores wide native editing canvases instead of compressing them to the viewport.
- **Scrolling and navigation:** Composition and playback/export have separate scroll canvases with readable opaque backgrounds. A persistent Workspace menu jumps to sections, and the new toolbar uses Qt's overflow mechanism on narrow windows.
- **Global Play Patcher:** Rhythm and melody editors no longer occupy the same grid cells as hint/wire controls. The patcher has workspace width instead of a narrow column.
- **Existing controls:** The original instrument, canonical, keyboard, project, export, video, game, hardware and recording controls were retained. Wide scientific editors can still scroll horizontally rather than being squeezed until unreadable.
- **Live Jam:** Added a reachable dialog and the compatible event/audio/video hooks from the comparison sources. Macros, envelopes and FX affect the jam overlay; they do not automatically rewrite canonical project data.
- **Random Object:** Added a reachable generator for seeded audio, image, video and voxel assets. Binding now defaults to off, duration defaults are short, and repeated seeds get separate asset folders instead of overwriting a previously bound sample.
- **Launchers:** Restored the fuller launcher from the supplied ISO overlay, including media/Rust provisioning, safe application exit, root-to-appliance-user handling and early shared-OpenGL setup. The compatibility launcher delegates to this path, and the dependency gate lives in one place.

## Threading and pooling

- **Nonblocking canonical planning:** Canonical activation requests an sCode plan rather than waiting for the optimizer process/lock on the GUI thread. One planning request can run while one latest snapshot waits; intermediate snapshots are coalesced.
- **Stale-result handling:** A generation serial prevents an older foreground planning result from replacing a newer requested one. Results are collected by the GUI timer, not by a worker touching widgets.
- **Conservative scheduling:** A previous idle plan cannot suppress a new explicit canonical edit while a current plan is pending.
- **RNG preparation:** Removed submission, blocking `Future.result()` calls and a second worker deepcopy for tiny private per-engine RNG descriptors. Engine order and seeded streams remain deterministic; this is not a move of document mutation onto worker threads.
- **Scratch buffers:** Filled private buffers no longer copy a cached template's contents merely to overwrite them. Returned buffers remain privately owned; aliasing a cached array into editable user data was not introduced.
- **Shared-lane cancellation:** A running public Future now correctly refuses cancellation. A successfully cancelled queued job will not execute later and mutate state.
- **Viewer completion:** Pooled frame callbacks use a weak viewer reference and a destruction flag. A completed render must not keep a closed viewer alive or refresh its deleted Qt widget.

These are targeted changes, not a claim that the entire canonical commit path is asynchronous. Large canonical transactions still contain GUI-owned iteration and commit work. The next architectural options and their tradeoffs are in `THREADING-AND-SCODE-OPTIONS.md`.

## Feature comparison

| Archive | Used for | Deliberately not imported |
|---|---|---|
| Working V3 | Main window, instrument/sequence controls, existing dialogs and all baseline capabilities | Nothing replaced wholesale |
| R41.2i Claude full merge | Compatible Live Jam / Random Object entry and event handling | Its main-window layout, replacement panel composition and unrelated feature-state rewrites |
| V3 rev-m/rev-p | Jam audition/video integration and comparison of compatible feature behavior | Its main-window layout and unrelated initialization changes |

The comparison archives have many shared modules, not three disjoint sets of features. Existing implementations were reused where already present. The latest revision selectively adds the sample-mimic, step-record and existing LAN-chat entry points; it still does not replace the working main window or blindly import alternate recording/FX window implementations.

## ISO and BUILD_KIT synchronization

Both build paths now use `runtime_payload.py` as their root-module inventory. The active ISO overlay is synchronized from that inventory, and the executable recipe uses the same inventory for local hidden imports. Archived/reference GUI modules such as `groovebox_newold` are excluded from active packaging.

```bash
# After changing source:
bash BUILD_ISO/sync_overlay_from_root.sh

# Read-only comparison of active ISO and executable runtime sources:
python scripts/sync_runtime_payload.py --check

# Source syntax, release contracts and synthetic EFI/hybrid-ISO contracts:
bash RUN_ME_ZERO_STATE.sh --check

# Also inspect host prerequisites:
bash RUN_ME_ZERO_STATE.sh --check-host
```

`--check` does not build a release ISO, install dependencies, flash a drive or prove a laptop can boot. `--check-host` checks tool/engine metadata access and scratch space; actual container startup can still be prohibited by the host.

The builder now checks container-engine access before expensive runtime preparation, supports choosing `GROOVEBOX_CONTAINER_ENGINE=podman` or `docker`, preserves the runtime-image/network overrides across its sudo hop, and uses a fully qualified Debian image name. An opt-in `GROOVEBOX_CONTAINER_NETWORK=host` exists for hosts whose bridge setup is unavailable, but should not be the default on a normal machine.

Several old source verifiers asserted obsolete literal implementation strings. They were updated to check the maintained responsive launcher/layout/pool implementation rather than require the removed implementation. They were not deleted or replaced with unconditional success.

## Build and launch

For the full appliance, use an x86_64 Linux host or VM with working Podman/Docker, sudo, internet access and ample free disk space. The scripts retain their dependency/native-build stages.

```bash
bash RUN_ME_ZERO_STATE.sh
```

For a platform-native executable, use the appropriate operating system with Python and its compiler/runtime prerequisites.

```bash
python BUILD_KIT/build.py --doctor
python BUILD_KIT/build.py
```

For source launch:

```bash
python launch_groovebox.py
```

First source launch can provision required dependencies and codecs. The codec validator was corrected so merely inspecting `/usr/bin/ffmpeg` does not try to chmod a system-owned file and falsely reject it. The ISO bootstrap already replaces host codecs with its Debian runtime's matching pair.

## Completed checks and limits

- **Focused regressions:** 48 passed at the last tested checkpoint, including sCode pooling/completion, cancellation, deterministic ownership, build-kit contracts and viewer lifecycle.
- **Native compilation:** C++ acceleration, sCode stage0 and Rust acceleration built successfully in the sandbox.
- **Executable:** The Linux BUILD_KIT build completed, and its bundled-resource verifier passed. It was built before the last small sizing/allocation edits; it is therefore omitted from this source archive rather than offered as the final source's binary.
- **ISO preflight:** 64 release source/boot-contract commands passed at a checkpoint. The boot contract constructs and inspects a synthetic hybrid/EFI image; that is not a boot of the full appliance.
- **GUI checks:** The working layout was inspected at 1920x1080, 1366x768, 1024x768 and 800x600. Laptop-size checks and the added feature dialogs were clean at the last checkpoint; an intermittent context-group overlap at 1920px/larger fonts prompted the final preferred-height correction.
- **Full ISO attempt:** The default run reached Debian container preparation but hit sandbox nftables restrictions. The host-network retry got past that layer and then stopped because the container runtime could not open sd-bus. No finished release ISO was produced.
- **After the final edits:** The context-group preferred-height correction and filled-buffer allocation adjustment were not followed by another full test/build pass, per your request. Source/overlay synchronization and packaging are included, but this is not a claim of fresh hardware validation.
- **Hardware/platform scope:** No laptop boot, disk install, Secure Boot, suspend/resume, Wi-Fi, speaker/microphone or Windows/macOS executable test is claimed. This appliance build path targets x86_64 UEFI, not every modern laptop architecture.

Generated virtual environments, build caches, the sandbox Linux executable and host codec copies are excluded from the source delivery. Rebuild on the intended platform to obtain an artifact corresponding to the final source.
