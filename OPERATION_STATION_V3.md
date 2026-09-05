# Mathematician's Groovebox V3 — Operation Station

V3 Operation Station packages the scientific Groovebox editor and the live Performance workspace as one application.

## Operation model

- **Main Window**: canonical/userdata composition, seed mathematics, sequence/playlist editing, deterministic rendering and inspection.
- **Performance**: live media, cutups, devices, broadcast, game controls and portable `.mgbmpf` module/effect patches.
- Performance opens as a **non-modal dock** in the Main Window. Playback continues while the dock is open; it may be docked or floated for touch/second-screen use.
- `/modules/` is reserved for `MathematiciansGrooveboxModulePatchFile` (`.mgbmpf`) patches.
- `/samples/` contains carrier, recording and video sample subfolders.

## Portable build/deployment

`BUILD_KIT/` builds application executables for Windows, macOS and Linux.
`DEPLOYMENT_KIT/` contains Linux appliance/image installation helpers for mini-PC, ARM64 and Raspberry Pi targets.

## Launch

Linux source launch: `./launch_desktop.sh`
Python launch: `python3 groovebox.py`

For deployment images, read `DEPLOYMENT_KIT/README_DEPLOYMENT.md`.

## Drive / clone transport

Operation Station can act as a portable project/export drive and as a versioned deployment source.
Performance → **Drive / Clone** can create a `.mgbclone.zip` containing source, build assets/executables and dependency/offline-install assets. Every file is recorded in `manifest.json` with a SHA-256 checksum.

The clone may be served over ordinary HTTP on Wi-Fi or Ethernet, or copied to mounted USB/removable storage together with a `.sha256` sidecar. Personal projects/samples/modules are excluded by default and can be explicitly included.

This is deliberately a transfer mechanism rather than remote execution: receiving machines verify/unpack/install the bundle using the included build/deployment tooling.
