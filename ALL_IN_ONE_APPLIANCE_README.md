# Mathematician's Groovebox — all-in-one required-sCode appliance build

This tree is the source of truth for both normal Linux launch and the standalone x86_64 appliance ISO.

## Required sCode

`run_groovebox.py` and Groovebox startup require the bundled native `sCode/bootstrap/linux-x86_64/scode0` optimizer and ABI 3 script. The Python/PyQt application remains the UI/DSP reference implementation; sCode supplies mandatory deterministic number/logic cross-casting, dirty-state planning, lane scheduling, work coalescing, and pool identities. A failed sCode preflight stops launch rather than silently bypassing it.

## Performance media

Performance stores timed audio/video/still-image playlists, external display/audio routes, and Parametric Remix settings in project state. Parametric Remix can render edits back to a media file. Draw Wave and Record share the layered Signal Lab, with reusable Draw/Sample/Record tabs, relative time scalars, Morph or Pooled Overlay composition, heuristic/parametric interpolation, total duration, frequency peaks/spectrum, Play Sample, WAV export, and routing to Global or Selected Operator.

## Project round trip

Project snapshots include `media_workbench_state`, required sCode optimizer policy/audit state, and the cached author-number font scheme. Live optimizer plans are deliberately recomputed after load from restored authoritative state rather than trusting stale serialized scheduling decisions.

## Desktop

```bash
./install_deps_linux.sh
python3 run_groovebox.py
```

## Build appliance ISO on Fedora

```bash
sudo ./BUILD_GROOVEBOX_APPLIANCE_ISO.sh
```

Default output: `dist/Groovebox-sCode-Appliance-x86_64.iso` plus SHA-256.

## Burn to a USB device

```bash
sudo ./BURN_GROOVEBOX_APPLIANCE_USB.sh dist/Groovebox-sCode-Appliance-x86_64.iso /dev/sdX
```

Verify the target device carefully; writing an image destroys its previous contents.

## Cross-platform ISO build/burn wrappers

See `appliance_tools/README_CROSS_PLATFORM_APPLIANCE.md`. Linux builds natively;
macOS and Windows use a Fedora 43 amd64 Docker/Podman build container so all three
platforms emit the same appliance image. The bundled sCode installer path performs
its own logic/pool/scheduler preflight before delegating privileged host operations.
