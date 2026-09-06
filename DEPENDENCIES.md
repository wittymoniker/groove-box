# Groovebox dependency contract

## Required Python runtime
- Python 3
- PyQt6
- NumPy
- SciPy
- sounddevice
- Pillow

`BUILD_KIT/build.py` installs these from `requirements.txt` for the standalone executable build.

## Required/expected system media tools
- FFmpeg (`ffmpeg`, `ffprobe`) for the full media import/export surface. Project-local binaries in `bin/` are bundled by the standalone build when present.
- A working audio backend supported by `sounddevice`/PortAudio.

## Optional integrations
- `mido`: MIDI device enumeration in `hardware_hub.py`; absence is tolerated.
- `juliacall` + Julia: optional Julia acceleration/parity backend; absence falls back to Python/C++ paths.
- `mpv`, `ffplay`, or VLC: optional external preview/playback routes where available; core rendering does not require all of them.
- PipeWire/PulseAudio utilities (`wpctl`, `pactl`): hardware/status discovery only.
- Bluetooth/USB/display utilities (`bluetoothctl`, `lsusb`, `xrandr`, etc.): optional hardware discovery only.

## Native acceleration
C++ source lives under `cpp/` and is built into `native/` by the BUILD_KIT when a supported compiler exists. The pure Python/NumPy path remains the fallback.

## Project-local modules
The distribution includes every module imported by the current `groovebox.py`, including `meum_constants`, `meum_compression`, MCC handlers, canonical/visual/game helpers, Radio/Performance/Signal Lab, sCode helpers, and project-path support.
