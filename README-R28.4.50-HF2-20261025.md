# Groovebox R28.4.50 HF2 — volume-verifier contract correction

**Base:** `Groovebox-R28.4.50-GAME-MEDIA-OUTPUT-BRIDGE-20261024.2.zip`  
**Base SHA-256:** `f1e1d316e538646feae4b579c83e4cbf9ecf4d04da63d008b53ad6f83fa0d69f`  
**Patch label:** R28.4.50 HF2 · 2026-10-25

This archive contains the R28.4.50 source tree with the HF1 feature changes and HF2 verifier-contract correction integrated. It is a **patched source archive**, not a newly built ISO or a hardware-validated binary release.

## Included changes

### Musical Explorer and Fractal Seed

- Adds the standalone Musical Explorer asset at `docs/fractal-seed-mode/musical_explorer.html` and a GUI button to open it.
- Adds the `groovebox_v3.fractal_seed_engine` deterministic, bounded seed interpreter and CLI entrypoint.
- Persists Fractal Seed mode in project state, stores event provenance, defaults the feature on for new/legacy projects, and preserves an explicit saved OFF state.
- Uses deterministic trigger gates; probability is not used as a stochastic decision gate. Intentional omission and phase-shift preview scenarios require both Fractal Seed mode and Canonical controls to be enabled.
- Adds the feature to desktop packaging and the sOS initramfs overlay.

### Composition lab

- Keeps the Mathematical Composition Lab controls inside a scroll area.
- Uses fully certain trigger gates in generated steps and carries any user-chosen structural profile as separate metadata rather than multiplying by chance.
- Retains the existing Canonical controls and Euclidean/canonical sequence state, including the current schema-6 save contract.

### Master volume and hardware audio

- Fresh Master Volume defaults to **72%**. Saved values override this fresh-session default, including a deliberate **0%**.
- Persists/restores Master Volume in project snapshots and synchronizes the visible master-volume slider.
- Prevents live hardware-volume changes and playback route checks from replaying `alsactl init` and resetting mixer state.
- Restores the persisted hardware level, accepts saved values in the range 0–100, and reasserts playback-only unmute/volume controls without changing microphone capture controls.
- Keeps the one-time audio initialization on the sOS boot path, preserves the active analog/HDMI route choice, and avoids re-running analog speaker UCM on every playback.

### sOS launcher and installer/build integration

- Uses the appliance's already provisioned runtime via `run_groovebox.py` rather than the desktop dependency-installer launcher.
- Includes the Fractal Seed package, Explorer documentation/HTML, and Mathematical Composition Lab in the final initramfs staging path and desktop packaging list.
- Retains the R28.4.50 CRC32C/ext4 installation preflight and ext4/VFAT support, and updates source-packaging exclusions to use the current `BUILD_ISO` tree.

## Use the source archive

1. Extract the ZIP into a writable project directory. Keep a backup of the original release.
2. For desktop development, use the same project launch path you previously used for R28.4.50 (normally `python3 run_groovebox.py`). Do not run the builder as root just to launch the GUI.
3. Open **Musical Explorer** from the main GUI. Fractal Seed plans are deterministic for a given seed/configuration and are bounded; explicit OFF state is respected after loading a project.
4. Set the main Master Volume as desired. A fresh run starts at 72%; a saved project or hardware-volume state is restored, including 0%.
5. Run the focused regression commands below before release.

### Focused source validation

From the extracted root folder:

```bash
python3 -m py_compile groovebox.py performance.py mathematical_composition_lab.py hardware_volume.py media_output_router.py groovebox_v3/__init__.py groovebox_v3/fractal_seed_engine.py groovebox_v3/cli.py BUILD_KIT/build.py BUILD_ISO/bundle_crc32c_modules_v35_22zq.py BUILD_ISO/verify_crc32c_install_v35_22zq.py
bash -n LAUNCH_GROOVEBOX_SOS.sh
bash -n BUILD_ISO/stamp_final_initramfs_v35_22zz.sh
sh -n BUILD_ISO/v35_22zz/sos-hardware-volume-v35_22zz_r23h
sh -n BUILD_ISO/sos-system-media-ready-v35_22zs
python3 BUILD_ISO/verify_crc32c_install_v35_22zq.py BUILD_ISO
```

The project carries historical test snapshots and the test environment may need PyQt6 for the UI-import tests; use `VALIDATION-R28.4.50-HF2-20261025.txt` for the tests actually run here and their limits.

### Building an sOS ISO

The source tree's maintained entry point is `BUILD_ISO/RUN_ME_ZERO_STATE.sh`, which dispatches into `RUN_ME_v35_22.sh` and the finalizer chain. On a build host with the documented Rust/Cargo toolchain and required system dependencies, run from the project root:

```bash
bash BUILD_ISO/RUN_ME_ZERO_STATE.sh
```

This package does **not** include a newly built ISO. An ISO build and install/boot testing should be performed on the target build host before calling the candidate production-ready.

### R23h/R23j verifier contract correction

- The prior R23h verifier compared the helper's agreed 72% first-launch default against stale 100%/70% expectations. The corrected checker validates 72%, confirms PipeWire post-start volume initialization uses the same 72% fallback, and accepts persisted 0% as a valid saved setting.
- The previous playback-mixer assertion searched for an obsolete compact string representation of an `amixer` call. It now checks the current command structure that applies the stored volume and unmutes playback-only controls, while retaining the capture/microphone/input exclusion contract.
- The adjacent R23j stored-volume assertion was updated to the same source syntax so that both verifiers agree with the implementation. These are source-verifier fixes; no runtime audio behavior was changed in this hotfix.

## Validation status

- The original uploaded ZIP's SHA-256 matched the official R28.4.50 release asset, and the ZIP integrity check passed.
- 71 focused pytest checks passed, including 67 existing regression tests plus four new HF2 checks guarding the 72% startup-volume and R23h/R23j verifier contracts. The existing suite covers Fractal Seed, deterministic composition, project volume restoration, hardware audio, microphone/HDMI noninterference, storage/autosave, and installer contracts.
- The standalone fifth-canonical Euclidean integration script passed 24/24 checks.
- `verify_crc32c_install_v35_22zq.py` passed 10/10 source checks.
- Python compile checks and shell syntax checks passed.
- The full historical repository test collection is not green in this container: embedded R28.4.41 snapshot tests expect removed snapshot-local source files; duplicated tests under `BUILD_ISO` conflict during import collection; and a GUI import test requires PyQt6, which is not installed here. A full suite pass is therefore **not claimed**.
- No fresh ISO build, physical sOS boot, physical-speaker audibility, or live microphone-device test is claimed.

## Verification follow-up — 2026-10-25

The received build log exposed one stale **source-contract assertion**, not a failed audio-route behavior test: the verifier expected the pre-existing shorter mixer-token tuple while the current router also contains `playback`. The verifier now explicitly checks the current playback-control token list, requires capture/microphone/input exclusions, and checks that playback unmute is present. No runtime audio routing code was changed for this verifier correction. `BUILD_ISO/verify_v35_22zz_r23f.py` now passes its source checks and simulated analog-speaker routing test.
